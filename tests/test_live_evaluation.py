"""Saved-evidence evaluator tests; fixtures are fabricated, never model runs."""
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from agent.pipeline import validate_extraction
from scripts.evaluate_live_run import ROOT, evaluate, write_evaluation


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SavedEvidenceFixture:
    def __init__(self, root, identifiers=("case-01", "syn-01")):
        self.root = root
        self.run = root / "run"
        self.run.mkdir()
        self.inputs = root / "inputs.jsonl"
        self.expectations = root / "expectations.json"
        self.sources, self.labels, self.calls, self.results = [], [], [], []
        accumulated = {}
        for n, identifier in enumerate(identifiers, 1):
            case = identifier.startswith("case-")
            speaker = "unknown" if case else "user"
            category = "incident" if case else "feature_request"
            status = "needs_review" if case else "ok"
            origin = "observed_pain" if case else "user_explicit"
            episode = "episode-01" if identifier in {"syn-01", "syn-04"} else f"episode-{identifier}"
            customer = "customer-b" if identifier == "syn-02" else "customer-a"
            text = "Кнопка не работает." if case else "Хочу выгрузку заказов в CSV."
            if identifier == "syn-10":
                text = "Хочу выгрузку счетов в CSV."
            if identifier == "syn-07":
                text = "Кнопка не работает. Хочу выгрузку заказов в CSV."
            src = dict(id=identifier, product_id="webneft", speaker=speaker, text=text,
                       origin="case_pdf" if case else "synthetic",
                       customer_id=None if case else customer, episode_id=None if case else episode,
                       episode_at=None if case else "2026-11-01T08:00:00Z")
            self.sources.append(src)
            intent = dict(kind=category, origin=origin, statement=text,
                evidence_refs=[dict(id=identifier, quote=text, locator={"fragment_id": "body"})], uncertainties=[])
            payload = dict(status=status, intents=[intent])
            if identifier == "syn-07":
                extra = copy.deepcopy(intent)
                extra.update(kind="incident", statement="Кнопка не работает.")
                payload["intents"].append(extra)
            raw = json.dumps(payload, ensure_ascii=False)
            checked = validate_extraction(raw, src)
            self.calls.append(dict(call_id=n, source_id=identifier, stage="extraction", raw_response=raw))
            assignments = []
            if not case:
                topic = "invoices" if identifier == "syn-10" else "orders"
                assignments.append(dict(topic_id=topic, status="new" if topic not in accumulated else "matched"))
                accumulated.setdefault(topic, {})[identifier] = src
            cards = []
            for topic, members in accumulated.items():
                values = list(members.values())
                cards.append(dict(topic_id=topic, raw_sources=len(values),
                    independent_episodes=len({s["episode_id"] for s in values}),
                    known_customers=len({s["customer_id"] for s in values})))
            self.results.append(dict(source_id=identifier, extraction_call=n,
                extraction=asdict(checked), assignments=assignments, cards_after_source=cards))
            self.labels.append(dict(id=identifier, accepted_kinds=[category],
                expected_status=status, expected_explicit_feature=not case))
        self.inputs.write_text("".join(json.dumps(s) + "\n" for s in self.sources))
        dump(self.expectations, {"author": "AI reviewer, not human gold", "tentative": True, "cases": self.labels})
        self.manifest = dict(status="complete", as_of="2026-11-02T00:00:00Z", source_count=len(self.sources),
            inputs_sha256=sha(self.inputs), pre_run_artifact_sha256={"expectations.json": sha(self.expectations)},
            call_count=len(self.calls), output_sha256={})
        self.save()

    def save(self):
        for name, rows in (("calls.jsonl", self.calls), ("results.jsonl", self.results)):
            path = self.run / name
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
            self.manifest["output_sha256"][name] = sha(path)
        dump(self.run / "manifest.json", self.manifest)

    def replace_response(self, index, payload):
        raw = json.dumps(payload, ensure_ascii=False)
        self.calls[index]["raw_response"] = raw
        self.results[index]["extraction"] = asdict(validate_extraction(raw, self.sources[index]))
        self.save()

    def add_verification(self, index=1, payload=None, respect_block=True):
        from agent.verifier import verification_messages, validate_verification
        src = self.sources[index]
        intent = self.results[index]["extraction"]["value"]["intents"][0]
        if payload is None:
            payload = {"verdict": "supported", "reason": "The source directly requests this capability.",
                       "evidence_quote": src["text"]}
        raw = json.dumps(payload, ensure_ascii=False)
        verified = validate_verification(raw, src, intent)
        call_id = max(c["call_id"] for c in self.calls) + 1
        self.calls.append(dict(call_id=call_id, stage="verification", source_id=src["id"],
            intent_id=intent["intent_id"], messages=verification_messages(src, intent), raw_response=raw))
        assignment = self.results[index]["assignments"][0]
        assignment.update(intent_id=intent["intent_id"], verification_call=call_id,
                          verification=asdict(verified), matching_call=None)
        if respect_block and (not verified.ok or verified.value["verdict"] != "supported"):
            assignment.update(topic_id=None, status="needs_review")
        self.manifest["call_count"] = len(self.calls)
        self.manifest.setdefault("code_sha256", {})["agent/verifier.py"] = sha(ROOT / "agent" / "verifier.py")
        self.save()
        return assignment, self.calls[-1]

    def evaluate(self):
        return evaluate(self.run, self.inputs, self.expectations)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, **kwargs):
        return SavedEvidenceFixture(self.root, **kwargs)

    def test_separate_material_counts_and_raw_classes(self):
        fixture = self.fixture()
        report = fixture.evaluate()
        self.assertEqual(report["summary"]["all"]["sources"], 2)
        self.assertEqual(report["summary"]["case_pdf"]["matched_preliminary_expectations"], 1)
        self.assertEqual(report["summary"]["synthetic"]["valid_extraction_contracts"], 1)
        self.assertEqual(report["summary"]["all"]["model_statuses"], {"needs_review": 1, "ok": 1})
        self.assertIn("not human gold", report["disclaimer"])

    def test_prefixed_validator_hash_mismatch_is_rejected(self):
        fixture = self.fixture()
        fixture.manifest["code_sha256"] = {
            "agent/pipeline.py": "0" * 64,
            # A valid legacy entry must not hide a wrong current-format entry.
            "pipeline.py": sha(ROOT / "agent" / "pipeline.py"),
        }
        fixture.save()
        with self.assertRaisesRegex(ValueError, "Validator source changed"):
            fixture.evaluate()

    def test_legacy_validator_hash_mismatch_is_still_rejected(self):
        fixture = self.fixture()
        fixture.manifest["code_sha256"] = {"pipeline.py": "0" * 64}
        fixture.save()
        with self.assertRaisesRegex(ValueError, "Validator source changed"):
            fixture.evaluate()

    def test_old_run_revalidation_accepts_changed_prompt_with_same_validator(self):
        fixture = self.fixture()
        baseline = fixture.evaluate()
        original_calls = (fixture.run / "calls.jsonl").read_bytes()
        for prefix in ("agent/", ""):
            with self.subTest(prefix=prefix):
                fixture.manifest["code_sha256"] = {
                    prefix + "pipeline.py": sha(ROOT / "agent" / "pipeline.py"),
                    # Deliberately differs from the currently installed prompt.
                    prefix + "prompts.py": "0" * 64,
                }
                fixture.save()
                report = fixture.evaluate()
                self.assertEqual(report["summary"], baseline["summary"])
                self.assertEqual(report["cases"], baseline["cases"])
                self.assertEqual((fixture.run / "calls.jsonl").read_bytes(), original_calls)

    def test_reject_changed_inputs_and_changed_frozen_expectations(self):
        fixture = self.fixture()
        original = fixture.inputs.read_bytes()
        fixture.inputs.write_bytes(original + b"\n")
        with self.assertRaisesRegex(ValueError, "Input SHA"):
            fixture.evaluate()
        fixture.inputs.write_bytes(original)
        fixture.expectations.write_text(fixture.expectations.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "expectation SHA"):
            fixture.evaluate()

    def test_reject_absent_pre_run_expectation_hash_and_output_tamper(self):
        fixture = self.fixture()
        frozen = fixture.manifest.pop("pre_run_artifact_sha256")
        fixture.save()
        with self.assertRaisesRegex(ValueError, "pre-run"):
            fixture.evaluate()
        fixture.manifest["pre_run_artifact_sha256"] = frozen
        fixture.save()
        with (fixture.run / "calls.jsonl").open("a") as handle:
            handle.write("\n")
        with self.assertRaisesRegex(ValueError, "Saved output SHA"):
            fixture.evaluate()

    def test_empty_intents_do_not_match_even_when_explicit_false(self):
        fixture = self.fixture()
        fixture.replace_response(0, {"status": "needs_review", "intents": []})
        row = fixture.evaluate()["cases"][0]
        self.assertTrue(row["valid_contract"])
        self.assertFalse(row["matched_preliminary_expectation"])
        self.assertIn("kinds outside accepted set or no intents", row["disagreements"])

    def test_semantic_disagreement_survives_valid_quote_contract(self):
        fixture = self.fixture()
        payload = json.loads(fixture.calls[1]["raw_response"])
        payload["intents"][0]["kind"] = "incident"
        fixture.replace_response(1, payload)
        row = fixture.evaluate()["cases"][1]
        self.assertTrue(row["valid_contract"])
        self.assertFalse(row["matched_preliminary_expectation"])
        self.assertIn("explicit feature flag differs", row["disagreements"])

    def test_invalid_contract_cannot_be_hidden_by_saved_ok_flag(self):
        fixture = self.fixture()
        fixture.results[0]["extraction"]["ok"] = False
        fixture.save()
        with self.assertRaisesRegex(ValueError, "revalidation"):
            fixture.evaluate()

    def test_unknown_author_violation_visible_in_raw_response(self):
        fixture = self.fixture()
        payload = json.loads(fixture.calls[0]["raw_response"])
        payload["intents"][0]["origin"] = "user_explicit"
        fixture.replace_response(0, payload)
        report = fixture.evaluate()
        self.assertFalse(report["cases"][0]["valid_contract"])
        focus = {c["name"]: c for c in report["focused_checks"]}
        self.assertFalse(focus["trusted_authorship_respected_by_raw_model"]["passed"])

    def test_four_sources_three_episodes_two_customers_and_invoice_separation(self):
        fixture = self.fixture(identifiers=("syn-01", "syn-02", "syn-03", "syn-04", "syn-10"))
        focus = {c["name"]: c for c in fixture.evaluate()["focused_checks"]}
        self.assertTrue(focus["syn01_04_one_topic_and_deduplicated_snapshot"]["passed"])
        self.assertTrue(focus["syn10_invoices_separate_from_orders"]["passed"])
        self.assertTrue(focus["snapshot_counts_use_only_trusted_known_identities"]["passed"])
        fixture.results[3]["cards_after_source"][0]["independent_episodes"] = 4
        fixture.save()
        focus = {c["name"]: c for c in fixture.evaluate()["focused_checks"]}
        self.assertFalse(focus["syn01_04_one_topic_and_deduplicated_snapshot"]["passed"])
        self.assertFalse(focus["snapshot_counts_use_only_trusted_known_identities"]["passed"])

    def test_syn07_missing_second_intent_fails_focused_check(self):
        fixture = self.fixture(identifiers=("syn-07",))
        focus = {c["name"]: c for c in fixture.evaluate()["focused_checks"]}
        self.assertTrue(focus["syn07_two_separate_intents"]["passed"])
        payload = json.loads(fixture.calls[0]["raw_response"])
        payload["intents"] = payload["intents"][:1]
        fixture.replace_response(0, payload)
        report = fixture.evaluate()
        self.assertTrue(report["cases"][0]["matched_preliminary_expectation"])
        focus = {c["name"]: c for c in report["focused_checks"]}
        self.assertFalse(focus["syn07_two_separate_intents"]["passed"])

    def test_null_explicit_expectation_is_unscored_not_false(self):
        fixture = self.fixture()
        labels = json.loads(fixture.expectations.read_text())
        labels["cases"][1]["expected_explicit_feature"] = None
        dump(fixture.expectations, labels)
        fixture.manifest["pre_run_artifact_sha256"]["expectations.json"] = sha(fixture.expectations)
        fixture.save()
        row = fixture.evaluate()["cases"][1]
        self.assertEqual(row["explicit_feature_comparison"], "not_scored_ambiguous")
        self.assertTrue(row["matched_preliminary_expectation"])

    def test_invented_source_id_and_identity_field_are_reported(self):
        fixture = self.fixture()
        payload = json.loads(fixture.calls[1]["raw_response"])
        payload["intents"][0]["evidence_refs"][0]["id"] = "invented-source"
        payload["customer_id"] = "invented-customer"
        fixture.replace_response(1, payload)
        report = fixture.evaluate()
        self.assertFalse(report["cases"][1]["valid_contract"])
        focus = {c["name"]: c for c in report["focused_checks"]}
        target = focus["no_invented_source_or_identity_fields_in_raw_extraction"]
        self.assertFalse(target["passed"])
        self.assertEqual(target["details"]["violating_sources"], ["syn-01"])

    def test_matching_response_contract_is_checked_without_generation(self):
        fixture = self.fixture()
        fixture.calls.append(dict(call_id=3, source_id="syn-01", stage="matching",
            messages=[{"role": "user", "content": json.dumps({"candidates": [
                {"id": "orders", "product_id": "webneft", "statement": "CSV orders"}]})}],
            raw_response=json.dumps({"matches": [{"candidate_id": "invented", "relation": "same", "basis": "same"}]})))
        fixture.manifest["call_count"] = 3
        fixture.save()
        matching = fixture.evaluate()["matching_contracts"]
        self.assertEqual(matching["calls"], 1)
        self.assertEqual(matching["valid"], 0)
        self.assertTrue(any("unknown ID" in e for e in matching["details"][0]["errors"]))

    def test_failed_partial_run_includes_unprocessed_in_denominator(self):
        fixture = self.fixture()
        fixture.manifest["status"] = "failed"
        fixture.results = fixture.results[:1]
        fixture.calls = fixture.calls[:1]
        fixture.manifest["call_count"] = 1
        fixture.save()
        report = fixture.evaluate()
        self.assertEqual(report["summary"]["all"]["sources"], 2)
        self.assertEqual(report["summary"]["all"]["processed"], 1)
        self.assertEqual(report["summary"]["all"]["matched_preliminary_expectations"], 1)
        self.assertEqual(report["cases"][1]["model_status"], "not_processed")

    def test_verifier_supported_is_separate_and_old_report_has_no_new_block(self):
        fixture = self.fixture()
        baseline = fixture.evaluate()
        self.assertNotIn("verification_contracts", baseline)
        fixture.add_verification()
        report = fixture.evaluate()
        verification = report["verification_contracts"]
        self.assertEqual(verification["verdicts"], {"supported": 1, "unsupported": 0, "unclear": 0, "invalid": 0})
        self.assertEqual(verification["valid_contracts"], 1)
        self.assertEqual(verification["blocking_violations"], 0)
        self.assertIn("not human gold", verification["disclaimer"])
        self.assertEqual(report["summary"], baseline["summary"])
        self.assertEqual(report["cases"], baseline["cases"])

    def test_verifier_unsupported_unclear_invalid_are_separate_blocking_results(self):
        for verdict in ("unsupported", "unclear", "invalid"):
            with self.subTest(verdict=verdict):
                location = self.root / verdict
                location.mkdir()
                fixture = SavedEvidenceFixture(location)
                payload = {"verdict": verdict, "reason": "Insufficient or contradictory evidence.", "evidence_quote": None}
                fixture.add_verification(payload=payload)
                report = fixture.evaluate()
                verification = report["verification_contracts"]
                self.assertEqual(verification["verdicts"][verdict], 1)
                self.assertEqual(verification["blocking_violations"], 0)
                self.assertTrue(verification["details"][0]["requires_blocking"])
                self.assertEqual(verification["details"][0]["valid_contract"], verdict != "invalid")
                # Blocking by a second model never silently relabels extraction.
                self.assertTrue(report["cases"][1]["matched_preliminary_expectation"])

    def test_verifier_call_source_and_intent_binding_are_checked(self):
        fixture = self.fixture()
        assignment, call = fixture.add_verification()
        call["source_id"] = "case-01"
        fixture.save()
        with self.assertRaisesRegex(ValueError, "call/source/intent mismatch"):
            fixture.evaluate()
        call["source_id"] = "syn-01"
        call["intent_id"] = "invented-intent"
        fixture.save()
        with self.assertRaisesRegex(ValueError, "call/source/intent mismatch"):
            fixture.evaluate()
        assignment["intent_id"] = "invented-intent"
        fixture.save()
        with self.assertRaisesRegex(ValueError, "intent absent"):
            fixture.evaluate()

    def test_verifier_prompt_data_is_bound_to_source_and_intent(self):
        fixture = self.fixture()
        _, call = fixture.add_verification()
        data = json.loads(call["messages"][-1]["content"])
        data["text"] = "Substituted source text"
        call["messages"][-1]["content"] = json.dumps(data)
        fixture.save()
        with self.assertRaisesRegex(ValueError, "prompt differs"):
            fixture.evaluate()

    def test_verifier_saved_result_and_source_hash_must_match(self):
        fixture = self.fixture()
        assignment, _ = fixture.add_verification()
        saved = copy.deepcopy(assignment["verification"])
        assignment["verification"]["ok"] = False
        fixture.save()
        with self.assertRaisesRegex(ValueError, "Saved verification differs"):
            fixture.evaluate()
        assignment["verification"] = saved
        fixture.manifest["code_sha256"]["agent/verifier.py"] = "0" * 64
        fixture.save()
        with self.assertRaisesRegex(ValueError, "changed verifier source"):
            fixture.evaluate()
        fixture.manifest["code_sha256"].pop("agent/verifier.py")
        fixture.save()
        with self.assertRaisesRegex(ValueError, "Missing or changed verifier"):
            fixture.evaluate()

    def test_verifier_block_bypass_is_reported(self):
        fixture = self.fixture()
        fixture.add_verification(payload={"verdict": "unsupported", "reason": "Not supported by the quote.",
                                          "evidence_quote": None}, respect_block=False)
        verification = fixture.evaluate()["verification_contracts"]
        self.assertEqual(verification["blocking_violations"], 1)
        self.assertFalse(verification["details"][0]["blocking_respected"])

    def test_unlinked_or_reused_verifier_calls_are_rejected(self):
        fixture = self.fixture()
        assignment, _ = fixture.add_verification()
        fixture.results[1]["assignments"].append(copy.deepcopy(assignment))
        fixture.save()
        with self.assertRaisesRegex(ValueError, "reused"):
            fixture.evaluate()
        fixture.results[1]["assignments"] = []
        fixture.save()
        with self.assertRaisesRegex(ValueError, "not linked"):
            fixture.evaluate()

    def test_write_once_and_preserve_all_existing_evidence(self):
        fixture = self.fixture()
        before = {p.name: p.read_bytes() for p in fixture.run.iterdir()}
        write_evaluation(fixture.run, fixture.inputs, fixture.expectations)
        self.assertTrue((fixture.run / "evaluation.md").exists())
        for name, value in before.items():
            self.assertEqual((fixture.run / name).read_bytes(), value)
        first = (fixture.run / "evaluation.json").read_bytes()
        with self.assertRaises(FileExistsError):
            write_evaluation(fixture.run, fixture.inputs, fixture.expectations)
        self.assertEqual((fixture.run / "evaluation.json").read_bytes(), first)

    def test_existing_markdown_blocks_json_creation(self):
        fixture = self.fixture()
        (fixture.run / "evaluation.md").write_text("keep")
        with self.assertRaises(FileExistsError):
            write_evaluation(fixture.run, fixture.inputs, fixture.expectations)
        self.assertFalse((fixture.run / "evaluation.json").exists())

    def test_duplicate_results_and_incomplete_complete_manifest_rejected(self):
        fixture = self.fixture()
        fixture.results.append(copy.deepcopy(fixture.results[0]))
        fixture.save()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            fixture.evaluate()
        fixture.results = fixture.results[:1]
        fixture.save()
        with self.assertRaisesRegex(ValueError, "every source"):
            fixture.evaluate()


if __name__ == "__main__":
    unittest.main()
