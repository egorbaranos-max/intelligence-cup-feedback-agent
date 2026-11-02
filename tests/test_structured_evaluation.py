"""Lifecycle-log auditing only; these records are scripted, not model evidence."""
import copy
import hashlib
import json
import unittest

from scripts.evaluate_live_run import ROOT, audit_structured_completion, sha


class StructuredEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {"model": {"decoding": {"structured_json": {"enabled": True}}}}
        self.calls = {1: {"status": "complete", "raw_response": "{}", "stats": {
            "finish_reason": "stop", "structured_json": {"accepting": True}}}}

    def test_successful_record_is_unchanged(self):
        original = copy.deepcopy((self.manifest, self.calls))
        self.assertIsNone(audit_structured_completion(self.manifest, self.calls))
        self.assertEqual((self.manifest, self.calls), original)

    def test_valid_json_does_not_hide_a_length_stop(self):
        self.calls[1]["stats"]["finish_reason"] = "length"
        with self.assertRaisesRegex(ValueError, "normal stop"):
            audit_structured_completion(self.manifest, self.calls)

    def test_missing_false_or_non_boolean_acceptance_is_rejected(self):
        for accepting in (None, False, 1, "true"):
            self.calls[1]["stats"]["structured_json"] = {"accepting": accepting}
            with self.subTest(accepting=accepting), self.assertRaisesRegex(ValueError, "accepting"):
                audit_structured_completion(self.manifest, self.calls)

    def test_missing_or_malformed_statistics_are_rejected(self):
        for stats in (None, {}, [], {"finish_reason": "stop"},
                      {"structured_json": {"accepting": True}},
                      {"finish_reason": "stop", "structured_json": []}):
            self.calls[1]["stats"] = stats
            with self.subTest(stats=stats), self.assertRaises(ValueError):
                audit_structured_completion(self.manifest, self.calls)

    def test_recorded_grammar_cannot_be_silently_disabled_or_removed(self):
        for manifest in ({}, {"model": {"decoding": {"structured_json": {"enabled": False}}}}):
            with self.subTest(manifest=manifest), self.assertRaisesRegex(ValueError, "provenance"):
                audit_structured_completion(manifest, self.calls)

    def test_failed_call_prefix_is_retained_without_claiming_completion(self):
        self.calls[1].update(status="failed", raw_response=' {"partial":')
        self.calls[1]["stats"].update(finish_reason="length", structured_json={"accepting": False})
        before = copy.deepcopy(self.calls)
        audit_structured_completion(self.manifest, self.calls)
        self.assertEqual(self.calls, before)

    def test_legacy_unconstrained_records_remain_supported(self):
        for manifest in ({}, {"model": {"decoding": {"structured_json": {"enabled": False}}}}):
            for stats in (None, {}, {"finish_reason": "length"}):
                self.calls[1]["stats"] = stats
                audit_structured_completion(manifest, self.calls)


class NamedSchemaEvaluationTests(unittest.TestCase):
    def setUp(self):
        from agent.response_schemas import RESPONSE_SCHEMAS
        schemas = {"generic": {"type": "object"}, **RESPONSE_SCHEMAS}
        self.records = {name: {"schema": copy.deepcopy(schema), "schema_sha256": hashlib.sha256(
            json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
            "grammar_sha256": "a" * 64} for name, schema in schemas.items()}
        self.grammar = {"enabled": True, "mode": "named_json_schemas", "schemas": self.records}
        self.manifest = {"model": {"decoding": {"structured_json": self.grammar}},
            "code_sha256": {"agent/response_schemas.py": sha(ROOT / "agent/response_schemas.py")}}
        self.calls = {}
        for n, stage in enumerate(("extraction", "extraction_repair", "verification", "matching"), 1):
            name = "extraction" if stage == "extraction_repair" else stage
            self.calls[n] = {"stage": stage, "response_schema": name, "status": "complete", "stats": {
                "finish_reason": "stop", "response_schema": name,
                "structured_json": {"accepting": True, "schema_name": name,
                                    "schema_sha256": self.records[name]["schema_sha256"]}}}

    def test_all_stages_including_repair_bind_without_mutation(self):
        before = copy.deepcopy((self.manifest, self.calls))
        audit_structured_completion(self.manifest, self.calls)
        self.assertEqual((self.manifest, self.calls), before)

    def test_wrong_stage_or_generic_fallback_is_rejected(self):
        self.calls[2]["response_schema"] = "generic"
        with self.assertRaisesRegex(ValueError, "stage and requested"):
            audit_structured_completion(self.manifest, self.calls)

    def test_schema_request_and_matcher_statistics_cannot_disagree(self):
        for field in ("response_schema", "schema_name", "schema_sha256"):
            calls = copy.deepcopy(self.calls)
            target = calls[1]["stats"] if field == "response_schema" else calls[1]["stats"]["structured_json"]
            target[field] = "wrong"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "matcher schema"):
                audit_structured_completion(self.manifest, calls)

    def test_missing_or_extra_schema_is_rejected(self):
        del self.records["generic"]
        with self.assertRaisesRegex(ValueError, "inventory"):
            audit_structured_completion(self.manifest, self.calls)

    def test_schema_content_and_canonical_hash_are_bound(self):
        original = copy.deepcopy(self.records["extraction"])
        self.records["extraction"]["schema"]["additionalProperties"] = True
        with self.assertRaisesRegex(ValueError, "frozen response schema"):
            audit_structured_completion(self.manifest, self.calls)
        self.records["extraction"] = original
        self.records["extraction"]["schema_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "frozen response schema"):
            audit_structured_completion(self.manifest, self.calls)

    def test_schema_source_hash_is_required(self):
        self.manifest["code_sha256"] = {}
        with self.assertRaisesRegex(ValueError, "response-schema source"):
            audit_structured_completion(self.manifest, self.calls)

    def test_compiled_grammar_fingerprint_must_be_recorded(self):
        self.records["matching"]["grammar_sha256"] = "not a SHA256"
        with self.assertRaisesRegex(ValueError, "compiled-grammar fingerprint"):
            audit_structured_completion(self.manifest, self.calls)

    def test_named_provenance_cannot_be_silently_changed_to_generic(self):
        self.grammar["mode"] = "json_object"
        with self.assertRaisesRegex(ValueError, "named-schema provenance"):
            audit_structured_completion(self.manifest, self.calls)

    def test_named_schema_cannot_claim_disabled_generation(self):
        self.grammar["enabled"] = False
        with self.assertRaisesRegex(ValueError, "must enable"):
            audit_structured_completion(self.manifest, self.calls)

    def test_boolean_cannot_impersonate_integer_in_exact_schema(self):
        self.records["verification"]["schema"]["properties"]["reason"]["minLength"] = True
        with self.assertRaisesRegex(ValueError, "frozen response schema"):
            audit_structured_completion(self.manifest, self.calls)

    def test_failed_call_has_stage_binding_even_without_processor_statistics(self):
        self.calls[1].update(status="failed", stats=None)
        audit_structured_completion(self.manifest, self.calls)
        self.calls[1]["response_schema"] = "matching"
        with self.assertRaisesRegex(ValueError, "stage and requested"):
            audit_structured_completion(self.manifest, self.calls)


if __name__ == "__main__":
    unittest.main()
