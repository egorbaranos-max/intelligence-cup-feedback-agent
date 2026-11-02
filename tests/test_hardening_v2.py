"""Evidence and orchestration regressions, not model quality measurements."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from agent.pipeline import extraction_messages, validate_extraction
from agent.spans import source_spans
from agent.verifier_v2 import verification_messages, validate_verification
from agent.runner import run
from tests.test_live_runner import ScriptedTestBackend, input_source, AS_OF


def source(text="Добавьте фильтр по складу. Ночной режим мне не нужен."):
    return {"id": "fixture", "product_id": "inventory", "speaker": "user", "text": text,
            "customer_id": "customer", "episode_id": "episode", "episode_at": "2026-11-01T12:00:00Z"}


def response(span_ids=("span_0001",), statement="Добавить фильтр по складу"):
    return {"status": "ok", "intents": [{"kind": "feature_request", "origin": "user_explicit",
        "statement": statement, "evidence_refs": [{"span_id": identifier} for identifier in span_ids],
        "uncertainties": []}]}


def extract(src=None, answer=None):
    return validate_extraction(json.dumps(answer or response(), ensure_ascii=False), src or source())


def verified(answer, src=None, proposed=None):
    src = src or source()
    proposed = proposed or extract(src).value["intents"][0]
    return validate_verification(json.dumps(answer, ensure_ascii=False), src, proposed)


class SpanEvidenceTests(unittest.TestCase):
    def test_offsets_exact_after_unicode_whitespace_and_repeated_text(self):
        text = "\tЕщё Ёж.\n Ещё Ёж.   Не нужно исправлять ё.\n"
        spans = source_spans(text)
        self.assertEqual([s["span_id"] for s in spans], ["span_0001", "span_0002", "span_0003"])
        self.assertEqual([s["text"] for s in spans], ["Ещё Ёж.", "Ещё Ёж.", "Не нужно исправлять ё."])
        for span in spans:
            self.assertEqual(text[span["start"]:span["end"]], span["text"])
        self.assertNotEqual(spans[0]["start"], spans[1]["start"])
        self.assertEqual(source_spans(text), spans)

    def test_span_selection_disambiguates_repeated_quote_without_rewriting(self):
        src = source("Хочу фильтр. Хочу фильтр.")
        result = extract(src, response(("span_0002",)))
        self.assertTrue(result.ok, result.errors)
        ref = result.value["intents"][0]["evidence_refs"][0]
        self.assertEqual(ref["quote"], "Хочу фильтр.")
        self.assertEqual(ref["locator"]["start"], len("Хочу фильтр. "))
        verdict = verified({"verdict": "supported", "reason": "Fixture only",
                            "evidence_span_ids": ["evidence_0001"]}, src, result.value["intents"][0])
        self.assertTrue(verdict.ok, verdict.errors)
        self.assertEqual(verdict.value["evidence_refs"], [ref])

    def test_no_punctuation_or_whitespace_normalization(self):
        src = source("Ещё\u00a0нужен 🗂️ фильтр…")
        result = extract(src)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.value["intents"][0]["evidence_refs"][0]["quote"], src["text"])

    def test_ids_are_scoped_to_source_and_extra_fields_cannot_replace_quote(self):
        for refs in ([{"span_id": "invented"}], [{"span_id": 1}],
                     [{"span_id": "span_0001"}, {"span_id": "span_0001"}],
                     [{"span_id": "span_0001", "quote": "Model replacement"}],
                     [{"span_id": "span_0001", "start": 0, "end": 3}]):
            data = response()
            data["intents"][0]["evidence_refs"] = refs
            self.assertFalse(extract(answer=data).ok)

    def test_source_payload_only_contains_real_spans_without_labels(self):
        src = {**source(), "gold": "SECRET", "expected_kind": "SECRET"}
        messages = extraction_messages(src)
        payload = json.loads(messages[1]["content"])
        self.assertEqual(payload["source_spans"], [
            {"span_id": s["span_id"], "text": s["text"]} for s in source_spans(src["text"])])
        self.assertNotIn("SECRET", messages[1]["content"])


class IntentGroundingTests(unittest.TestCase):
    def test_verifier_sees_full_context_but_only_own_evidence_ids(self):
        src = source()
        proposed = extract(src).value["intents"][0]
        messages = verification_messages(src, proposed)
        payload = json.loads(messages[-1]["content"])
        self.assertEqual(payload["text"], src["text"])
        self.assertEqual(payload["evidence_spans"], [
            {"span_id": "evidence_0001", "text": "Добавьте фильтр по складу."}])
        self.assertNotIn("Ночной", json.dumps(payload["evidence_spans"], ensure_ascii=False))

    def test_another_intent_quote_cannot_confirm_this_intent(self):
        data = {"verdict": "supported", "reason": "Wrong intent", "evidence_quote": "Ночной режим мне не нужен."}
        result = verified(data)
        self.assertFalse(result.ok)
        self.assertTrue(any("outside this intent" in e for e in result.errors))

    def test_unknown_duplicate_or_source_span_ids_are_rejected(self):
        for ids in (["evidence_0002"], ["span_0001"], ["evidence_0001", "evidence_0001"], [1], "evidence_0001"):
            result = verified({"verdict": "supported", "reason": "Fixture", "evidence_span_ids": ids})
            self.assertFalse(result.ok)

    def test_no_evidence_is_valid_for_refusal_but_not_support(self):
        for verdict in ("unsupported", "unclear"):
            result = verified({"verdict": verdict, "reason": "Fixture", "evidence_span_ids": []})
            self.assertTrue(result.ok, result.errors)
            self.assertIsNone(result.value["evidence_quote"])
        self.assertFalse(verified({"verdict": "supported", "reason": "Fixture", "evidence_span_ids": []}).ok)

    def test_ref_coords_must_belong_to_exact_source_and_intent(self):
        for mutation in ("foreign_source", "wrong_quote", "wrong_offset", "boolean_offset", "missing_refs"):
            proposed = extract().value["intents"][0]
            ref = proposed["evidence_refs"][0]
            if mutation == "foreign_source":
                ref["id"] = "some-other-source"
            elif mutation == "wrong_quote":
                ref["quote"] = "добавьте фильтр по складу."
            elif mutation == "wrong_offset":
                ref["locator"]["end"] -= 1
            elif mutation == "boolean_offset":
                ref["locator"]["start"] = False
            else:
                proposed["evidence_refs"] = []
            with self.assertRaises(ValueError):
                verification_messages(source(), proposed)
            result = verified({"verdict": "supported", "reason": "Fixture", "evidence_span_ids": ["evidence_0001"]}, proposed=proposed)
            self.assertFalse(result.ok)

    def test_multi_span_display_quote_is_itself_exact_not_a_fabricated_concatenation(self):
        src = source("Нужен фильтр. Ещё контекст. Он должен учитывать склад.")
        proposed = extract(src, response(("span_0001", "span_0003"))).value["intents"][0]
        result = verified({"verdict": "supported", "reason": "Fixture", "evidence_span_ids": ["evidence_0001", "evidence_0002"]}, src, proposed)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.value["evidence_quote"], src["text"])
        self.assertEqual(len(result.value["evidence_refs"]), 2)

    def test_exact_evidence_is_not_a_claim_to_solve_negation(self):
        src = source("Мне не нужен фильтр по складу.")
        wrong = extract(src, response(statement="Добавить фильтр по складу")).value["intents"][0]
        result = verified({"verdict": "supported", "reason": "Deliberately wrong semantic fixture",
                           "evidence_span_ids": ["evidence_0001"]}, src, wrong)
        # This deliberate failure mode must remain visible to semantic evals.
        self.assertTrue(result.ok)
        self.assertEqual(result.value["verdict"], "supported")


class ReviewAuditTests(unittest.TestCase):
    def test_failed_review_and_ordinary_sources_remain_auditable(self):
        def output(payload):
            if payload["metadata"]["id"] == "invalid":
                return "not JSON"
            value = response()
            if payload["metadata"]["id"] == "uncertain":
                value["status"] = "needs_review"
                value["intents"][0]["uncertainties"] = ["Контекст неясен"]
            elif payload["metadata"]["id"] == "incident":
                value["intents"][0]["kind"] = "incident"
            return value
        def verification(payload):
            return {"verdict": "supported", "reason": "Scripted test only", "evidence_span_ids": ["evidence_0001"]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = root / "inputs.jsonl"
            inputs.write_text("".join(json.dumps(input_source(name), ensure_ascii=False) + "\n"
                                      for name in ("invalid", "uncertain", "incident", "feature")))
            with contextlib.redirect_stdout(io.StringIO()):
                manifest = run(inputs, root / "run", ScriptedTestBackend(output, verification_override=verification), AS_OF)
            queue = json.loads((root / "run/review-queue.json").read_text())
            audit = json.loads((root / "run/source-audit.json").read_text())
            self.assertEqual({r["source_id"] for r in queue}, {"invalid", "uncertain"})
            self.assertEqual({r["source_id"] for r in audit}, {"invalid", "uncertain", "incident", "feature"})
            self.assertEqual(manifest["review_required_sources"], 2)
            self.assertEqual(manifest["audited_sources"], 4)
            self.assertEqual(manifest["contract_version"], "text-spans-v2")
            self.assertIn("review-queue.json", manifest["output_sha256"])
            self.assertIn("source-audit.json", manifest["output_sha256"])


if __name__ == "__main__":
    unittest.main()
