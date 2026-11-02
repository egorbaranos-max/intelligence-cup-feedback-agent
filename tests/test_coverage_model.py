"""Hand-authored adjudicated gold fixtures, independent of detector output."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "coverage_model.py"
SPEC = importlib.util.spec_from_file_location("coverage_model", MODULE_PATH)
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)


class CoverageModelTests(unittest.TestCase):
    def test_three_mature_one_timely_one_late_one_missing(self):
        result = coverage.coverage7(coverage.example_input())
        self.assertEqual(result["coverage7"], 1 / 3)
        self.assertEqual(result["counts"]["mature_gold_denominator"], 3)
        self.assertEqual(result["counts"]["timely"], 1)
        self.assertEqual(result["counts"]["late_delivered"], 1)
        self.assertEqual(result["counts"]["missing_as_of"], 1)
        self.assertEqual(result["counts"]["immature_gold_excluded"], 1)

    def test_eight_of_ten_with_two_missing_is_point_eight(self):
        document = coverage.example_input()
        record = document["gold"][0]
        document["gold"] = [{**record, "topic_id": str(i),
                             "delivered_at": record["delivered_at"] if i < 8 else None}
                            for i in range(10)]
        result = coverage.coverage7(document)
        self.assertEqual(result["coverage7"], .8)
        self.assertEqual(result["counts"]["mature_gold_denominator"], 10)
        self.assertEqual(result["counts"]["missing_as_of"], 2)
        self.assertNotIn("confidence_interval", result)

    def test_empty_and_only_immature_are_na_not_perfect(self):
        for gold in [[], [coverage.example_input()["gold"][-1]]]:
            document = coverage.example_input()
            document["gold"] = gold
            result = coverage.coverage7(document)
            self.assertIsNone(result["coverage7"])
            self.assertEqual(result["coverage7_status"], "N/A_no_mature_gold")

    def test_seven_full_days_and_inclusive_deadline(self):
        document = coverage.example_input()
        document["gold"] = [document["gold"][0]]
        document["as_of"] = "2026-11-07T23:59:59.999999Z"
        self.assertIsNone(coverage.coverage7(document)["coverage7"])
        document["as_of"] = "2026-11-08T00:00:00Z"
        self.assertEqual(coverage.coverage7(document)["coverage7"], 1)
        document["gold"][0]["delivered_at"] = "2026-11-08T00:00:00.000001Z"
        document["as_of"] = "2026-11-09T00:00:00Z"
        self.assertEqual(coverage.coverage7(document)["coverage7"], 0)

    def test_half_open_window_and_outside_records_are_counted(self):
        document = coverage.example_input()
        record = document["gold"][0]
        document["gold"] = [record, {**record, "topic_id": "at-end",
                                    "eligible_at": document["cohort_end"],
                                    "delivered_at": None}]
        result = coverage.coverage7(document)
        self.assertEqual(result["counts"]["selected_cohort_gold"], 1)
        self.assertEqual(result["counts"]["outside_cohort_excluded"], 1)
        self.assertEqual(result["coverage7"], 1)

    def test_timezone_offsets_are_normalized_to_utc(self):
        document = coverage.example_input()
        document["gold"] = [document["gold"][0]]
        document["gold"][0]["eligible_at"] = "2026-11-01T03:00:00+03:00"
        document["gold"][0]["delivered_at"] = "2026-11-08T03:00:00+03:00"
        document["as_of"] = "2026-11-08T03:00:00+03:00"
        result = coverage.coverage7(document)
        self.assertEqual(result["coverage7"], 1)
        self.assertEqual(result["as_of_utc"], "2026-11-08T00:00:00Z")

    def test_future_delivery_is_censored_and_stays_missing_as_of(self):
        document = coverage.example_input()
        document["gold"] = [document["gold"][0]]
        document["gold"][0]["delivered_at"] = "2026-11-10T00:00:00Z"
        result = coverage.coverage7(document)
        self.assertEqual(result["coverage7"], 0)
        self.assertEqual(result["counts"]["missing_as_of"], 1)
        self.assertEqual(result["counts"]["late_delivered"], 0)
        self.assertEqual(result["counts"]["selected_future_delivery_events_censored"], 1)

    def test_fallback_stays_in_denominator_and_quality_is_visible(self):
        document = coverage.example_input()
        document["gold"] = [document["gold"][0], document["gold"][2]]
        result = coverage.coverage7(document)
        self.assertEqual(result["coverage7"], .5)
        self.assertEqual(result["cohort_quality"]["mature_history_status"], "fallback_present")
        self.assertEqual(result["cohort_quality"]["mature_history_counts"], {"known": 1, "fallback": 1})

    def test_known_and_fallback_scores_keep_different_cohorts_visible(self):
        result = coverage.coverage7(coverage.example_input())
        self.assertEqual(result["coverage7_population"], "combined_observed_cohorts")
        self.assertEqual(result["coverage7"], 1 / 3)
        known, fallback = result["cohort_scores"]["known"], result["cohort_scores"]["fallback"]
        self.assertEqual((known["timely_numerator"], known["mature_gold_denominator"],
                          known["coverage7"]), (1, 2, .5))
        self.assertEqual((fallback["timely_numerator"], fallback["mature_gold_denominator"],
                          fallback["coverage7"]), (0, 1, 0))
        self.assertIn("first_observed_threshold", fallback["definition"])
        self.assertIn("not a claim", fallback["definition"])

    def test_zero_denominator_is_na_independently_for_each_history_cohort(self):
        document = coverage.example_input()
        document["gold"] = [document["gold"][0]]
        result = coverage.coverage7(document)
        self.assertEqual(result["cohort_scores"]["known"]["coverage7"], 1)
        fallback = result["cohort_scores"]["fallback"]
        self.assertEqual(fallback["mature_gold_denominator"], 0)
        self.assertIsNone(fallback["coverage7"])
        self.assertEqual(fallback["coverage7_status"], "N/A_no_mature_gold")
        document["gold"] = []
        for score in coverage.coverage7(document)["cohort_scores"].values():
            self.assertEqual(score["timely_numerator"], 0)
            self.assertEqual(score["mature_gold_denominator"], 0)
            self.assertIsNone(score["coverage7"])

    def test_duplicate_gold_is_rejected_even_outside_window(self):
        document = coverage.example_input()
        document["gold"].append(copy.deepcopy(document["gold"][0]))
        document["cohort_start"] = "2026-10-01T00:00:00Z"
        document["cohort_end"] = "2026-10-02T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "Duplicate gold"):
            coverage.coverage7(document)

    def test_delivery_before_eligible_is_not_a_qualifying_update(self):
        document = coverage.example_input()
        document["gold"][0]["delivered_at"] = "2026-10-31T23:59:59Z"
        with self.assertRaisesRegex(ValueError, "at or after eligible_at"):
            coverage.coverage7(document)

    def test_invalid_dates_and_scopes_are_explicit_errors(self):
        for field in ["cohort_start", "cohort_end", "as_of"]:
            for value in [None, "unknown", "2026-11-01T00:00:00"]:
                document = coverage.example_input()
                document[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    coverage.coverage7(document)
        for field, value in [("eligible_at", "unknown"), ("delivered_at", "unknown"),
                             ("scope_id", "foreign-product"), ("scope_id", ""),
                             ("topic_id", ""), ("history_status", "unknown")]:
            document = coverage.example_input()
            document["gold"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                coverage.coverage7(document)

    def test_missing_history_or_extra_detector_fields_are_rejected(self):
        document = coverage.example_input()
        del document["gold"][0]["history_status"]
        with self.assertRaisesRegex(ValueError, "missing fields"):
            coverage.coverage7(document)
        document = coverage.example_input()
        document["gold"][0]["detector_found"] = True
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            coverage.coverage7(document)

    def test_invalid_or_reversed_cohort_is_rejected(self):
        document = coverage.example_input()
        document["cohort_end"] = document["cohort_start"]
        with self.assertRaisesRegex(ValueError, "after cohort_start"):
            coverage.coverage7(document)

    def test_cli_stdin_and_example_roundtrip(self):
        example = io.StringIO()
        with contextlib.redirect_stdout(example):
            coverage.main(["--example"])
        result = io.StringIO()
        with patch("sys.stdin", io.StringIO(example.getvalue())), contextlib.redirect_stdout(result):
            coverage.main(["-"])
        self.assertEqual(json.loads(result.getvalue())["coverage7"], 1 / 3)

    def test_cli_json_file_roundtrip(self):
        result = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adjudicated-gold.json"
            path.write_text(json.dumps(coverage.example_input()), encoding="utf-8")
            with contextlib.redirect_stdout(result):
                coverage.main([str(path)])
        self.assertEqual(json.loads(result.getvalue())["counts"]["mature_gold_denominator"], 3)

    def test_cli_corrupt_or_duplicate_json_does_not_emit_a_score(self):
        for raw in ["{", '{"scope_id":"x","scope_id":"y"}']:
            with self.subTest(raw=raw), patch("sys.stdin", io.StringIO(raw)), \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(SystemExit) as error:
                    coverage.main(["-"])
                self.assertEqual(error.exception.code, 2)
                self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
