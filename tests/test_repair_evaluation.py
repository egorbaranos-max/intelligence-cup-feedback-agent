"""Audit the bounded model-retry protocol using scripted outputs, never inference."""
import contextlib
from dataclasses import asdict
import io
import json
from pathlib import Path
import tempfile
import unittest

from agent.pipeline import validate_extraction
from agent.runner import run
from scripts.evaluate_live_run import evaluate, sha
from tests.test_live_runner import ScriptedTestBackend, input_source, AS_OF


def response(payload, kind="feature_request"):
    return {"status": "ok", "intents": [{"kind": kind, "origin": "user_explicit",
        "statement": payload["text"], "uncertainties": [], "evidence_refs": [{"span_id": "span_0001"}]}]}


class RepairEvidenceFixture:
    def __init__(self, root):
        self.inputs, self.labels, self.output = root / "inputs.jsonl", root / "expectations.json", root / "run"
        self.sources = [input_source("repairable"), input_source("valid-but-wrong")]
        self.inputs.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in self.sources))
        self.labels.write_text(json.dumps({"author": "AI reviewer, not human gold", "tentative": True,
            "cases": [{"id": s["id"], "accepted_kinds": ["feature_request"],
                       "expected_status": "ok", "expected_explicit_feature": True} for s in self.sources]}))
        def scripted(payload):
            if payload["metadata"]["id"] == "valid-but-wrong":
                return response(payload, "incident")
            return response(payload) if "contract_repair" in payload else "not-json"
        with contextlib.redirect_stdout(io.StringIO()):
            run(self.inputs, self.output, ScriptedTestBackend(extraction_override=scripted), AS_OF,
                {"expectations.json": sha(self.labels)})
        self.manifest = json.loads((self.output / "manifest.json").read_text())
        self.calls = [json.loads(line) for line in (self.output / "calls.jsonl").read_text().splitlines()]
        self.results = [json.loads(line) for line in (self.output / "results.jsonl").read_text().splitlines()]

    def save(self):
        for name, rows in (("calls.jsonl", self.calls), ("results.jsonl", self.results)):
            path = self.output / name
            path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
            self.manifest["output_sha256"][name] = sha(path)
        (self.output / "manifest.json").write_text(json.dumps(self.manifest))

    def evaluate(self):
        return evaluate(self.output, self.inputs, self.labels)


class RepairEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = RepairEvidenceFixture(Path(self.temp.name))

    def test_first_and_final_outcomes_separate_valid_semantic_error_not_retried(self):
        report = self.fixture.evaluate()
        attempts = report["extraction_attempts"]
        self.assertEqual(attempts["first_pass_valid_extractions"], 1)
        self.assertEqual(attempts["extraction_repair_calls"], 1)
        self.assertEqual(attempts["repaired_valid_extractions"], 1)
        self.assertEqual(attempts["final_valid_extractions"], 2)
        self.assertEqual(attempts["first_pass_matched_preliminary_expectations"], 0)
        self.assertEqual(attempts["final_matched_preliminary_expectations"], 1)
        self.assertEqual(len(self.fixture.results[1]["extraction_attempts"]), 1)
        self.assertFalse(report["cases"][1]["matched_preliminary_expectation"])
        self.assertEqual(self.fixture.calls[0]["raw_response"], "not-json")
        self.assertIn("may still change meaning", attempts["disclaimer"])

    def test_third_attempt_or_unselected_last_attempt_rejected(self):
        attempts = self.fixture.results[0]["extraction_attempts"][:]
        self.fixture.results[0]["extraction_attempts"] = [*attempts, 999]
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "one or two"):
            self.fixture.evaluate()
        self.fixture.results[0]["extraction_attempts"] = attempts
        self.fixture.results[0]["extraction_call"] = attempts[0]
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "final selected"):
            self.fixture.evaluate()

    def test_valid_first_pass_cannot_be_retried_for_semantic_disagreement(self):
        source = self.fixture.sources[0]
        raw = json.dumps(response({"text": source["text"]}, "incident"))
        self.fixture.calls[0]["raw_response"] = raw
        self.fixture.results[0]["first_pass_extraction"] = asdict(validate_extraction(raw, source))
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "Contract-valid extraction"):
            self.fixture.evaluate()

    def test_original_raw_errors_and_source_are_bound_to_repair_prompt(self):
        repair = next(c for c in self.fixture.calls if c["stage"] == "extraction_repair")
        payload = json.loads(repair["messages"][-1]["content"])
        payload["contract_repair"]["previous_response"] = "different"
        repair["messages"][-1]["content"] = json.dumps(payload)
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "Repair prompt differs"):
            self.fixture.evaluate()

    def test_repair_call_must_name_the_initial_call(self):
        repair = next(c for c in self.fixture.calls if c["stage"] == "extraction_repair")
        repair["repair_of"] = 900
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "original-call binding"):
            self.fixture.evaluate()

    def test_saved_first_validation_is_not_trusted_without_raw_revalidation(self):
        self.fixture.results[0]["first_pass_extraction"]["ok"] = True
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "First-pass extraction differs"):
            self.fixture.evaluate()

    def test_retry_counts_limit_and_source_code_are_verified(self):
        self.fixture.manifest["extraction_repair_calls"] = 0
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "attempt counts differ"):
            self.fixture.evaluate()
        self.fixture.manifest["extraction_repair_calls"] = 1
        self.fixture.manifest["extraction_repair_limit"] = 5
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "limit of one"):
            self.fixture.evaluate()
        self.fixture.manifest["extraction_repair_limit"] = 1
        self.fixture.manifest["code_sha256"]["agent/repair.py"] = "0" * 64
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "changed repair source"):
            self.fixture.evaluate()

    def test_hidden_unlinked_extra_extraction_is_rejected(self):
        import copy
        extra = copy.deepcopy(self.fixture.calls[0])
        extra["call_id"] = 999
        self.fixture.calls.append(extra)
        self.fixture.manifest["call_count"] = len(self.fixture.calls)
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "not all linked"):
            self.fixture.evaluate()

    def test_first_prompt_cannot_silently_substitute_source_text(self):
        payload = json.loads(self.fixture.calls[0]["messages"][-1]["content"])
        payload["text"] = "Substitute"
        self.fixture.calls[0]["messages"][-1]["content"] = json.dumps(payload)
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "prompt differs from bound source"):
            self.fixture.evaluate()

    def test_partial_raw_prefix_from_failed_call_is_never_a_completed_answer(self):
        selected = self.fixture.results[1]["extraction_call"]
        call = next(call for call in self.fixture.calls if call["call_id"] == selected)
        call.update(status="failed", error_type="StructuredDecodingError", error="Stopped before accepted completion")
        # It even contains syntactically valid JSON; the failed completion status
        # still prevents the partial stream from being treated as a final answer.
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "failed or non-complete"):
            self.fixture.evaluate()
        self.fixture.manifest["status"] = "failed"
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "Failed extraction attempt"):
            self.fixture.evaluate()


if __name__ == "__main__":
    unittest.main()
