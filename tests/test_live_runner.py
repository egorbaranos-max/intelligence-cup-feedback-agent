"""Batch integration tests with an explicitly scripted test backend.

No model is loaded or called here. These tests verify orchestration, provenance
and refusal behavior; their success is not evidence of Qwen accuracy.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from agent.backend import verify_model_manifest
from agent.runner import run


AS_OF = "2026-11-02T12:00:00Z"


def input_source(identifier, **changes):
    value = {"id": identifier, "product_id": "test-product", "customer_id": "client-a",
             "episode_id": identifier, "episode_at": "2026-11-01T12:00:00Z",
             "speaker": "user", "text": "Хочу выгружать заказы в CSV.", "origin": "synthetic"}
    value.update(changes)
    return value


def extracted(payload):
    return {"status": "ok", "intents": [{"kind": "feature_request", "origin": "user_explicit",
        "statement": payload["text"], "evidence_refs": [{"id": payload["metadata"]["id"],
        "quote": payload["text"], "locator": {"fragment_id": "body"}}], "uncertainties": []}]}


class ScriptedTestBackend:
    """TEST FIXTURE ONLY: predetermined outputs, never represents live Qwen."""
    provenance = {"backend": "TEST_ONLY_SCRIPTED_FIXTURE", "model_id": "NO_MODEL",
                  "warning": "Unit-test fixture; no inference or model accuracy measurement"}

    def __init__(self, extraction_override=None, matching_override=None, relation="same", verification_override=None):
        self.extraction_override = extraction_override
        self.matching_override = matching_override
        self.relation = relation
        self.verification_override = verification_override
        self.calls = []

    def generate(self, messages, max_tokens):
        self.calls.append({"messages": messages, "max_tokens": max_tokens})
        payload = json.loads(messages[-1]["content"])
        if "proposed_intent" in payload:
            result = self.verification_override(payload) if self.verification_override else {
                "verdict": "supported", "reason": "Scripted test support", "evidence_quote": payload["text"]}
        elif "metadata" in payload:
            result = self.extraction_override(payload) if self.extraction_override else extracted(payload)
        else:
            result = self.matching_override(payload) if self.matching_override else {"matches": [
                {"candidate_id": c["id"], "relation": self.relation, "basis": "Scripted test relation"}
                for c in payload["candidates"]]}
        if isinstance(result, Exception):
            raise result
        raw = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        return raw, {"fixture": True, "call_index": len(self.calls)}


class RunnerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def execute(self, sources, backend=None, name="run", hashes=None):
        path = self.root / (name + "-inputs.jsonl")
        path.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in sources))
        out = self.root / name
        with contextlib.redirect_stdout(io.StringIO()):
            manifest = run(path, out, backend or ScriptedTestBackend(), AS_OF, hashes)
        return manifest, out

    def read(self, path):
        return json.loads(path.read_text())

    def lines(self, path):
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_inference_matching_dedup_and_threshold_delivery(self):
        sources = [input_source("ticket-a", episode_id="case-a"),
                   input_source("call-a", episode_id="case-a"),
                   input_source("ticket-b", customer_id="client-b"),
                   input_source("ticket-c")]
        manifest, out = self.execute(sources)
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["call_count"], 11)
        self.assertEqual(manifest["delivered_local_cards"], 1)
        receiver = self.read(out / "local-receiver.json")
        self.assertEqual(len(receiver), 1)
        self.assertEqual(receiver[0]["raw_sources"], 4)
        self.assertEqual(receiver[0]["independent_episodes"], 3)
        self.assertEqual(receiver[0]["known_customers"], 2)
        results = self.lines(out / "results.jsonl")
        self.assertFalse(results[2]["cards_after_source"][0]["recurring"])
        self.assertTrue(results[3]["cards_after_source"][0]["recurring"])
        self.assertEqual(manifest["model"]["model_id"], "NO_MODEL")

    def test_missing_real_time_is_excluded_without_invented_episodes(self):
        sources = [input_source(str(i), episode_at=None) for i in range(3)]
        manifest, out = self.execute(sources)
        self.assertEqual(manifest["delivered_local_cards"], 0)
        card = self.read(out / "cards.json")[0]
        self.assertEqual(card["raw_sources"], 0)
        self.assertEqual(card["independent_episodes"], 0)
        self.assertEqual(card["evidence"], [])
        self.assertTrue(all("missing trusted episode time" in r["counting"]
                            for r in self.lines(out / "results.jsonl")))

    def test_unknown_identity_does_not_satisfy_recurrence(self):
        sources = [input_source(str(i), episode_id=None, customer_id=None) for i in range(4)]
        manifest, out = self.execute(sources)
        card = self.read(out / "cards.json")[0]
        self.assertEqual(card["raw_sources"], 4)
        self.assertEqual(card["independent_episodes"], 0)
        self.assertEqual(card["sources_with_unknown_episode"], 4)
        self.assertEqual(manifest["delivered_local_cards"], 0)

    def test_invalid_json_is_retained_and_next_source_is_processed(self):
        def scripted(payload):
            return "not JSON" if payload["metadata"]["id"] == "bad" else extracted(payload)
        manifest, out = self.execute([input_source("bad"), input_source("good")], ScriptedTestBackend(scripted))
        self.assertEqual(manifest["valid_extractions"], 1)
        self.assertEqual(self.lines(out / "calls.jsonl")[0]["raw_response"], "not JSON")
        results = self.lines(out / "results.jsonl")
        self.assertFalse(results[0]["extraction"]["ok"])
        self.assertTrue(results[1]["extraction"]["ok"])
        self.assertEqual(self.read(out / "cards.json")[0]["raw_sources"], 1)

    def test_fabricated_quote_and_model_selected_topic_are_blocked(self):
        for mode in ("quote", "topic"):
            def scripted(payload):
                result = extracted(payload)
                if mode == "quote":
                    result["intents"][0]["evidence_refs"][0]["quote"] = "Вымышленная цитата"
                else:
                    result["intents"][0]["topic_id"] = "model-picked-topic"
                return result
            manifest, out = self.execute([input_source(mode)], ScriptedTestBackend(scripted), name=mode)
            self.assertEqual(manifest["valid_extractions"], 0)
            self.assertEqual(self.read(out / "topics.json"), [])

    def test_unknown_author_review_never_becomes_a_card(self):
        def scripted(payload):
            result = extracted(payload)
            result["status"] = "needs_review"
            result["intents"][0]["origin"] = "observed_pain"
            return result
        manifest, out = self.execute([input_source("unknown", speaker="unknown")], ScriptedTestBackend(scripted))
        self.assertEqual(manifest["valid_extractions"], 1)
        self.assertEqual(self.read(out / "topics.json"), [])
        self.assertEqual(self.lines(out / "results.jsonl")[0]["assignments"][0]["status"], "needs_review")

    def test_matching_cannot_substitute_unknown_topic_or_merge_unclear(self):
        for mode in ("foreign", "unclear"):
            def scripted(payload):
                identifier = "not-in-registry" if mode == "foreign" else payload["candidates"][0]["id"]
                return {"matches": [{"candidate_id": identifier, "relation": "same" if mode == "foreign" else "unclear",
                                     "basis": "Scripted adversarial test output"}]}
            manifest, out = self.execute([input_source("a"), input_source("b")],
                                         ScriptedTestBackend(matching_override=scripted), name=mode)
            results = self.lines(out / "results.jsonl")
            self.assertEqual(results[1]["assignments"][0]["status"], "needs_review")
            self.assertIsNone(results[1]["assignments"][0]["topic_id"])
            self.assertEqual(self.read(out / "cards.json")[0]["raw_sources"], 1)

    def test_products_are_separated_before_matching(self):
        backend = ScriptedTestBackend()
        manifest, out = self.execute([input_source("a"), input_source("b", product_id="other")], backend)
        self.assertEqual(manifest["call_count"], 4)
        topics = self.read(out / "topics.json")
        self.assertEqual({t["product_id"] for t in topics}, {"test-product", "other"})
        self.assertEqual(len({t["id"] for t in topics}), 2)

    def test_truncated_candidate_search_does_not_claim_novelty(self):
        sources = [input_source(str(i), text=f"Отдельная потребность {i}") for i in range(7)]
        manifest, out = self.execute(sources, ScriptedTestBackend(relation="different"))
        results = self.lines(out / "results.jsonl")
        final = results[-1]["assignments"][0]
        self.assertEqual(final["candidate_pool_size"], 6)
        self.assertEqual(len(final["candidate_ids"]), 5)
        self.assertEqual(final["status"], "needs_review")
        self.assertIn("truncated", final["reason"])
        self.assertEqual(len(self.read(out / "topics.json")), 6)

    def test_unconfirmed_support_never_enters_matching_or_counts(self):
        for verdict in ("unsupported", "unclear", "invalid"):
            def verify(payload):
                if payload["metadata"]["id"] == "good":
                    return {"verdict": "supported", "reason": "Test only", "evidence_quote": payload["text"]}
                if verdict == "invalid":
                    return "not JSON"
                return {"verdict": verdict, "reason": "Test only", "evidence_quote": None}
            sources = [input_source("good"), input_source("bad1", customer_id="b"), input_source("bad2", customer_id="c")]
            manifest, out = self.execute(sources, ScriptedTestBackend(verification_override=verify), name=verdict)
            self.assertEqual(manifest["delivered_local_cards"], 0)
            self.assertEqual(self.read(out / "cards.json")[0]["independent_episodes"], 1)
            for row in self.lines(out / "results.jsonl")[1:]:
                assignment = row["assignments"][0]
                self.assertIsNone(assignment["topic_id"])
                self.assertIsNone(assignment["matching_call"])
                self.assertEqual(assignment["status"], "needs_review")

    def test_backend_failure_retains_attempt_and_failed_manifest(self):
        def scripted(payload):
            return RuntimeError("test-only backend failure")
        with self.assertRaisesRegex(RuntimeError, "test-only backend failure"):
            self.execute([input_source("failure")], ScriptedTestBackend(scripted))
        out = self.root / "run"
        manifest = self.read(out / "manifest.json")
        calls = self.lines(out / "calls.jsonl")
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["call_count"], 1)
        self.assertEqual(calls[0]["status"], "failed")
        self.assertEqual(calls[0]["error_type"], "RuntimeError")
        self.assertEqual(calls[0]["error"], "test-only backend failure")
        self.assertIsNone(calls[0]["raw_response"])
        self.assertIn("text", json.loads(calls[0]["messages"][-1]["content"]))
        self.assertIn("calls.jsonl", manifest["output_sha256"])

    def test_replay_is_repeatable_for_identical_scripted_outputs(self):
        sources = [input_source("a"), input_source("b")]
        first, out1 = self.execute(sources, name="first")
        second, out2 = self.execute(sources, name="second")
        # This demonstrates deterministic orchestration only, not that two real
        # MLX runs on different hardware produce byte-identical model outputs.
        self.assertEqual(first["output_sha256"], second["output_sha256"])
        self.assertIn("demo/case_contract_demo.py", first["code_sha256"])
        self.assertIn("agent/runner.py", first["code_sha256"])

    def test_gold_and_origin_are_not_sent_to_backend(self):
        backend = ScriptedTestBackend()
        source = input_source("a", gold={"SECRET_GOLD": "answer"})
        manifest, out = self.execute([source], backend, hashes={"expectations.json": "f" * 64})
        sent = json.dumps(backend.calls, ensure_ascii=False)
        self.assertNotIn("SECRET_GOLD", sent)
        self.assertNotIn('"synthetic"', sent)
        self.assertEqual(manifest["pre_run_artifact_sha256"], {"expectations.json": "f" * 64})

    def test_invalid_input_rejected_before_model_call_and_old_run_not_overwritten(self):
        for name, sources in [("duplicate", [input_source("a"), input_source("a")]),
                              ("future", [input_source("a", episode_at="2027-01-01T00:00:00Z")])]:
            backend = ScriptedTestBackend()
            with self.assertRaises(ValueError):
                self.execute(sources, backend, name=name)
            self.assertEqual(backend.calls, [])
        _, out = self.execute([input_source("a")], name="immutable")
        original = (out / "manifest.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.execute([input_source("b")], name="immutable")
        self.assertEqual((out / "manifest.json").read_bytes(), original)


class ModelManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.model = self.root / "snapshot"
        self.model.mkdir()
        # Tiny test bytes, deliberately not a valid model. The pure verifier
        # does not import MLX or claim to load these fixture files.
        for name in ("config.json", "tokenizer_config.json", "tokenizer.json", "model.safetensors"):
            (self.model / name).write_bytes(b"TEST_ONLY_NOT_MODEL:" + name.encode())
        self.manifest = {"model_id": "TEST_ONLY_NOT_MODEL", "revision": "a" * 40,
                         "local_path": str(self.model), "files": {}}
        for path in self.model.iterdir():
            self.manifest["files"][path.name] = {"bytes": path.stat().st_size,
                                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.path = self.root / "manifest.json"

    def verify(self):
        self.path.write_text(json.dumps(self.manifest))
        return verify_model_manifest(self.path)

    def test_all_listed_files_verify_without_loading_model(self):
        manifest, path = self.verify()
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(path, self.model)

    def test_unlisted_and_modified_files_fail(self):
        extra = self.model / "generation_config.json"
        extra.write_text("{}")
        with self.assertRaisesRegex(ValueError, "file set"):
            self.verify()
        extra.unlink()
        (self.model / "config.json").write_text("changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.verify()

    def test_empty_inventory_and_missing_required_files_fail(self):
        saved = self.manifest["files"].copy()
        for missing in ("config.json", "tokenizer_config.json", "tokenizer.json", "model.safetensors"):
            self.manifest["files"] = {k: v for k, v in saved.items() if k != missing}
            with self.assertRaises(ValueError):
                self.verify()
        self.manifest["files"] = {}
        with self.assertRaisesRegex(ValueError, "nonempty"):
            self.verify()

    def test_manifest_paths_cannot_escape_snapshot(self):
        entry = self.manifest["files"]["config.json"]
        for name in ("../config.json", "/tmp/config.json", "nested/config.json", "..\\config.json", ".."):
            self.manifest["files"][name] = entry
            with self.assertRaisesRegex(ValueError, "basenames"):
                self.verify()
            del self.manifest["files"][name]

    def test_invalid_hash_size_or_unpinned_revision_fails(self):
        for entry in ({"bytes": True, "sha256": "a" * 64}, {"bytes": 1, "sha256": "oops"}):
            self.manifest["files"]["config.json"] = entry
            with self.assertRaisesRegex(ValueError, "hash or size"):
                self.verify()
        self.manifest["revision"] = "main"
        with self.assertRaisesRegex(ValueError, "full commit SHA"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
