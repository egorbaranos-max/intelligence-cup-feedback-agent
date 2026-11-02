"""Synthetic evaluator tests: no fixtures here are claimed to be model results."""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from agent.pipeline import validate_extraction
from scripts.evaluate_semantics import evaluate_semantics
from scripts.check_live_runs import HISTORICAL_RUNS, registered_runs


class SemanticEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name)
        self.sources, self.expected, self.results, self.validated = {}, {}, {}, {}
        for n in range(3):
            key = f"unit-{n}"
            text = "Добавьте напоминание о сроке договора."
            self.sources[key] = dict(id=key, product_id="example", speaker="user", text=text,
                customer_id=f"customer-{n % 2}", episode_id=f"episode-{n}", episode_at="2026-11-01T00:00:00Z")
            payload = {"status": "ok", "intents": [{"kind": "feature_request", "origin": "user_explicit",
                "statement": text, "uncertainties": [], "evidence_refs": [{"span_id": "span_0001"}]}]}
            self.validated[key] = validate_extraction(json.dumps(payload, ensure_ascii=False), self.sources[key])
            self.expected[key] = {"expected_delivery": "candidate", "intents": [{"intent_id": f"expected-{n}",
                "kind": "feature_request", "allowed_kinds": ["feature_request"], "origin": "user_explicit",
                "new_demand": True, "review_required": False, "topic_id": "contract_reminder",
                "evidence_quotes": [text]}]}
            self.results[key] = {"assignments": [], "review_required": False}
        self.themes = [{"topic_id": "contract_reminder", "source_ids": list(self.sources),
            "eligible_source_ids": list(self.sources), "expected_recurring": True}]
        self.cards = [{"topic_id": "actual-topic", "title": "Reminder", "recurring": True,
            "evidence": [{"source_id": key, "quote": source["text"]} for key, source in self.sources.items()]}]
        self.receiver = copy.deepcopy(self.cards)
        self.review = []
        self.manifest = {"as_of": "2026-11-02T00:00:00Z", "delivered_local_cards": 1,
            "review_required_sources": 0, "audited_sources": 3, "output_sha256": {}}

    def tearDown(self):
        self.temp.cleanup()

    def evaluate(self):
        audit = [{"source_id": key, "review_required": row["review_required"]} for key, row in self.results.items()]
        for filename, value in (("cards.json", self.cards), ("local-receiver.json", self.receiver),
                                ("review-queue.json", self.review), ("source-audit.json", audit)):
            (self.run / filename).write_text(json.dumps(value, ensure_ascii=False))
            self.manifest["output_sha256"][filename] = __import__("hashlib").sha256((self.run / filename).read_bytes()).hexdigest()
        return evaluate_semantics(self.run, self.sources, self.expected, self.themes,
                                  self.results, self.validated, self.manifest)

    def test_correct_format_and_label_match_are_separate_with_explicit_limits(self):
        report = self.evaluate()
        summary = report["summary"]
        self.assertEqual(summary["valid_extraction_contracts"], 3)
        self.assertEqual(summary["expected_intents_evidence_and_class_matched"], 3)
        self.assertEqual(summary["delivered_cards_supported_by_provisional_labels"], 1)
        self.assertEqual(summary["recurring_themes_missed_or_unconfirmed"], 0)
        self.assertIn("not human gold", report["disclaimer"])
        self.assertIn("faithful paraphrase", report["disclaimer"])

    def test_zero_deliveries_does_not_hide_missed_recurring_theme(self):
        self.receiver = []
        self.manifest["delivered_local_cards"] = 0
        self.assertEqual(self.evaluate()["summary"]["recurring_themes_missed_or_unconfirmed"], 1)

    def test_wrong_class_can_have_perfect_quote_and_valid_contract(self):
        key = "unit-0"
        value = asdict(self.validated[key])
        value["value"]["intents"][0]["kind"] = "service_request"
        from agent.pipeline import ValidationResult
        self.validated[key] = ValidationResult(**value)
        summary = self.evaluate()["summary"]
        self.assertEqual(summary["valid_extraction_contracts"], 3)
        self.assertEqual(summary["expected_intents_evidence_and_class_matched"], 2)

    def test_one_actual_intent_cannot_satisfy_two_expected_intents(self):
        self.expected["unit-0"]["intents"].append({**self.expected["unit-0"]["intents"][0], "intent_id": "second"})
        summary = self.evaluate()["summary"]
        self.assertEqual(summary["expected_intents"], 4)
        self.assertEqual(summary["expected_intents_evidence_and_class_matched"], 3)
        self.assertEqual(summary["sources_all_expected_intents_matched"], 2)

    def test_false_publication_does_not_disappear_behind_exact_quote(self):
        label = self.expected["unit-0"]["intents"][0]
        label.update(kind="service_request", allowed_kinds=["service_request"], new_demand=False, topic_id=None)
        summary = self.evaluate()["summary"]
        self.assertEqual(summary["delivered_cards_contradicting_provisional_labels"], 1)
        self.assertEqual(summary["delivered_cards_supported_by_provisional_labels"], 0)
        self.assertEqual(summary["recurring_themes_missed_or_unconfirmed"], 1)

    def test_ambiguous_shared_quote_stays_unscored(self):
        extra = {**self.expected["unit-0"]["intents"][0], "intent_id": "second", "topic_id": "unrelated"}
        self.expected["unit-0"]["intents"].append(extra)
        summary = self.evaluate()["summary"]
        self.assertEqual(summary["delivered_cards_unscored"], 1)
        self.assertEqual(summary["delivered_cards_supported_by_provisional_labels"], 0)

    def test_missing_detailed_labels_are_not_reported_as_success(self):
        self.expected["unit-0"].pop("intents")
        self.themes = None
        report = self.evaluate()
        self.assertFalse(report["intent_labels_available_for_all_sources"])
        self.assertFalse(report["theme_labels_available"])
        self.assertEqual(report["summary"]["delivered_cards_unscored"], 1)

    def test_missing_review_item_is_a_failure(self):
        self.results["unit-0"]["review_required"] = True
        with self.assertRaisesRegex(ValueError, "Manual review queue"):
            self.evaluate()

    def test_review_burden_counts_unique_sources(self):
        self.results["unit-0"]["review_required"] = True
        self.review = [{"source_id": "unit-0", "source_text": self.sources["unit-0"]["text"]}]
        self.manifest["review_required_sources"] = 1
        self.assertEqual(self.evaluate()["summary"]["review_queue_sources"], 1)
        self.review.append(copy.deepcopy(self.review[0]))
        with self.assertRaisesRegex(ValueError, "Review queue"):
            self.evaluate()

    def test_legacy_workload_proxy_does_not_require_or_create_queue_files(self):
        self.evaluate()  # Save only fixture artifacts, not an evaluation report.
        (self.run / "review-queue.json").unlink()
        (self.run / "source-audit.json").unlink()
        self.manifest["output_sha256"].pop("review-queue.json")
        self.manifest["output_sha256"].pop("source-audit.json")
        for result in self.results.values():
            result.pop("review_required")
        self.results["unit-0"]["assignments"] = [{"status": "needs_review", "topic_id": None}]
        report = evaluate_semantics(self.run, self.sources, self.expected, self.themes,
                                   self.results, self.validated, self.manifest, legacy_review=True)
        self.assertEqual(report["summary"]["review_queue_sources"], 1)
        self.assertNotIn("review_required", self.results["unit-0"])
        self.assertFalse((self.run / "review-queue.json").exists())

    def test_receiver_cannot_claim_nonexistent_or_altered_card(self):
        self.receiver[0]["title"] = "Changed"
        with self.assertRaisesRegex(ValueError, "Local receiver differs"):
            self.evaluate()

    def test_labels_must_quote_real_source_and_theme_count_must_be_reproducible(self):
        self.expected["unit-0"]["intents"][0]["evidence_quotes"] = ["invented"]
        with self.assertRaisesRegex(ValueError, "quote must be exact"):
            self.evaluate()
        self.expected["unit-0"]["intents"][0]["evidence_quotes"] = [self.sources["unit-0"]["text"]]
        self.themes[0]["expected_recurring"] = False
        with self.assertRaisesRegex(ValueError, "recurring label differs"):
            self.evaluate()


class SavedRunInventoryTests(unittest.TestCase):
    def test_missing_run_directory_and_unregistered_run_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            experiments = root / "experiments"
            for name in HISTORICAL_RUNS:
                (experiments / name).mkdir(parents=True)
            (experiments / "recorded-runs.json").write_text(json.dumps({"runs": sorted(HISTORICAL_RUNS)}))
            self.assertEqual(len(registered_runs(root)), 4)
            missing = experiments / sorted(HISTORICAL_RUNS)[0]
            missing.rmdir()
            with self.assertRaisesRegex(ValueError, "inventory differs"):
                registered_runs(root)
            missing.mkdir()
            (experiments / "extra/runs/run-01").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "unregistered"):
                registered_runs(root)

    def test_empty_registry_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "experiments").mkdir()
            (root / "experiments/recorded-runs.json").write_text('{"runs":[]}')
            with self.assertRaisesRegex(ValueError, "missing historical"):
                registered_runs(root)


class V2SavedRunEvaluationTests(unittest.TestCase):
    def test_span_contract_dispatch_and_artifact_tampering(self):
        import contextlib
        import hashlib
        import io
        from agent.runner import run
        from scripts.evaluate_live_run import evaluate, sha
        from tests.test_live_runner import ScriptedTestBackend, input_source, AS_OF
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs, labels, output = root / "inputs.jsonl", root / "expectations.json", root / "run"
            sources = [input_source(f"fixture-{n}", customer_id=f"customer-{n % 2}") for n in range(3)]
            inputs.write_text("".join(json.dumps(source, ensure_ascii=False) + "\n" for source in sources))
            cases = [{"id": source["id"], "accepted_kinds": ["feature_request"], "expected_status": "ok",
                      "expected_explicit_feature": True} for source in sources]
            labels.write_text(json.dumps({"author": "AI reviewer, not human gold", "tentative": True, "cases": cases}))
            def spans(payload):
                return {"status": "ok", "intents": [{"kind": "feature_request", "origin": "user_explicit",
                    "statement": payload["text"], "uncertainties": [], "evidence_refs": [{"span_id": "span_0001"}]}]}
            backend = ScriptedTestBackend(extraction_override=spans,
                verification_override=lambda payload: {"verdict": "supported", "reason": "Fixture only",
                                                        "evidence_span_ids": ["evidence_0001"]})
            with contextlib.redirect_stdout(io.StringIO()):
                run(inputs, output, backend, AS_OF, {"expectations.json": sha(labels)})
            report = evaluate(output, inputs, labels)
            self.assertEqual(report["contract_version"], "text-spans-v2")
            self.assertEqual(report["verification_contracts"]["valid_contracts"], 3)
            self.assertEqual(report["provisional_semantics"]["summary"]["delivered_local_cards"], 1)
            self.assertEqual(report["provisional_semantics"]["summary"]["delivered_cards_unscored"], 1)
            focus = {row["name"]: row for row in report["focused_checks"]}
            self.assertTrue(focus["no_invented_source_or_identity_fields_in_raw_extraction"]["passed"])
            (output / "review-queue.json").write_text('[{"source_id":"invented"}]')
            with self.assertRaisesRegex(ValueError, "Saved output SHA-256 differs: review-queue"):
                evaluate(output, inputs, labels)


if __name__ == "__main__":
    unittest.main()
