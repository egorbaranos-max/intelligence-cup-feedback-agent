"""Finance contract tests; these prove formulas, not company cash benefits."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "finance_model.py"
SPEC = importlib.util.spec_from_file_location("finance_model", MODULE_PATH)
finance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(finance)


class FinanceModelTests(unittest.TestCase):
    def test_three_year_ceiling_includes_year_one_discount(self):
        case = finance.income_case(120, [1, 1, 1], 0, .2)
        self.assertEqual(case["gross_benefit_by_year_rub"], [120, 120, 120])
        self.assertAlmostEqual(case["pv_by_year_rub"][0], 100)
        self.assertAlmostEqual(case["total_expense_pv_ceiling_rub"], 252.77777777777777)
        self.assertEqual(case["simple_total_expense_ceiling_rub"], 360)

    def test_published_scenarios(self):
        expected = {"cautious": 282996.2966962211,
                    "base": 2985783.333333334,
                    "favorable": 10994077.124945326,
                    "no_verified_cash": 0}
        for name, ceiling in expected.items():
            with self.subTest(name=name):
                self.assertAlmostEqual(finance.income_case(*finance.CASES[name])[
                    "total_expense_pv_ceiling_rub"], ceiling)

    def test_growth_and_ramp_have_independent_timing(self):
        case = finance.income_case(100, [.5, 1, 0], .1, 0)
        self.assertAlmostEqual(case["gross_benefit_by_year_rub"][0], 50)
        self.assertAlmostEqual(case["gross_benefit_by_year_rub"][1], 110)
        self.assertEqual(case["gross_benefit_by_year_rub"][2], 0)

    def test_no_verified_cash_does_not_fund_positive_expenses(self):
        case = finance.budget_case(0, [1, 1, 1], 0, .2, 1, [1, 1, 1])
        self.assertFalse(case["nonnegative_initial_outlay_feasible"])
        self.assertFalse(case["meets_three_year_discounted_threshold_under_assumptions"])
        self.assertIsNone(case["sustained_discounted_payback_year_end_within_horizon"])

    def test_future_costs_reduce_initial_headroom_without_ramp_discount(self):
        case = finance.budget_case(100, [0, 1, 1], 0, 0, 100, [20, 20, 20])
        self.assertEqual(case["future_expense_pv_rub"], 60)
        self.assertEqual(case["max_initial_outlay_after_future_expenses_rub"], 140)
        self.assertEqual(case["npv_at_year_three_rub"], 40)
        self.assertEqual(case["sustained_discounted_payback_year_end_within_horizon"], 3)

    def test_discounted_threshold_can_fail_while_simple_threshold_passes(self):
        income = finance.income_case(100, [1, 1, 1], 0, .2)
        case = finance.budget_case(100, [1, 1, 1], 0, .2, 250, [0, 0, 0])
        self.assertLess(250, income["simple_total_expense_ceiling_rub"])
        self.assertFalse(case["meets_three_year_discounted_threshold_under_assumptions"])

    def test_exact_ceiling_is_zero_npv_and_above_ceiling_fails(self):
        ceiling = finance.income_case(*finance.CASES["base"])["total_expense_pv_ceiling_rub"]
        boundary = finance.budget_case(*finance.CASES["base"], ceiling, [0, 0, 0])
        above = finance.budget_case(*finance.CASES["base"], ceiling + 1, [0, 0, 0])
        self.assertEqual(boundary["npv_at_year_three_rub"], 0)
        self.assertTrue(boundary["meets_three_year_discounted_threshold_under_assumptions"])
        self.assertFalse(above["meets_three_year_discounted_threshold_under_assumptions"])

    def test_temporary_crossing_is_not_sustained_payback(self):
        case = finance.budget_case(100, [1, 0, 0], 0, 0, 50, [0, 0, 100])
        self.assertEqual(case["cumulative_net_pv_at_t0_and_year_ends_rub"], [-50, 50, 50, -50])
        self.assertIsNone(case["sustained_discounted_payback_year_end_within_horizon"])

    def test_future_cost_calendar_and_remaining_initial_threshold(self):
        early = finance.budget_case(100, [1, 1, 1], 0, .2, 0, [60, 0, 0])
        late = finance.budget_case(100, [1, 1, 1], 0, .2, 0, [0, 0, 60])
        self.assertGreater(late["max_initial_outlay_after_future_expenses_rub"],
                           early["max_initial_outlay_after_future_expenses_rub"])
        boundary = finance.budget_case(100, [1, 1, 1], 0, .2,
            early["max_initial_outlay_after_future_expenses_rub"], [60, 0, 0])
        self.assertEqual(boundary["npv_at_year_three_rub"], 0)
        self.assertTrue(boundary["meets_three_year_discounted_threshold_under_assumptions"])

    def test_sensitivity_is_monotonic_and_benefit_linear(self):
        pv = [finance.income_case(100, [.5, 1, 1], .06, r)["total_expense_pv_ceiling_rub"]
              for r in [0, .14, .2, .26]]
        self.assertTrue(all(a > b for a, b in zip(pv, pv[1:])))
        double = finance.income_case(200, [.5, 1, 1], .06, .2)
        self.assertEqual(double["total_expense_pv_ceiling_rub"], 2 * pv[2])

    def test_valid_boundaries_zero_adoption_and_total_benefit_decline(self):
        self.assertEqual(finance.income_case(100, [0, 0, 0], 0, 0)["total_expense_pv_ceiling_rub"], 0)
        self.assertEqual(finance.income_case(100, [1, 1, 1], -1, 0)["gross_benefit_by_year_rub"], [100, 0, 0])
        self.assertGreater(finance.income_case(100, [1, 1, 1], 0, -.1)["total_expense_pv_ceiling_rub"], 300)

    def test_invalid_income_inputs_are_rejected(self):
        invalid = [(-1, [1, 1, 1], 0, 0),
                   (1, [-.1, 1, 1], 0, 0), (1, [1.1, 1, 1], 0, 0),
                   (1, [1, 1], 0, 0), (1, None, 0, 0), (1, "111", 0, 0),
                   (1, [1, 1, 1], -1.1, 0), (1, [1, 1, 1], 0, -1)]
        for nonfinite in [float("nan"), float("inf"), float("-inf"), True, "100"]:
            invalid.extend([(nonfinite, [1, 1, 1], 0, 0),
                            (1, [nonfinite, 1, 1], 0, 0),
                            (1, [1, 1, 1], nonfinite, 0),
                            (1, [1, 1, 1], 0, nonfinite)])
        invalid.append((1e308, [1, 1, 1], 1e308, 0))
        for inputs in invalid:
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                finance.income_case(*inputs)

    def test_invalid_expense_inputs_are_rejected(self):
        for initial, annual in [(-1, [0, 0, 0]), (0, [-1, 0, 0]),
                                (float("nan"), [0, 0, 0]), (0, [0, float("inf"), 0]),
                                (0, [0, 0]), (True, [0, 0, 0])]:
            with self.subTest(initial=initial, annual=annual), self.assertRaises(ValueError):
                finance.budget_case(100, [1, 1, 1], 0, .2, initial, annual)

    def test_cli_scenario_exposes_assumptions_and_conditional_budget(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            finance.main(["--benefit", "100", "--ramp", "0", "1", "1", "--growth", "0",
                          "--discount", "0", "--initial-cost", "100", "--annual-costs", "20", "20", "20"])
        report = json.loads(stream.getvalue())
        self.assertIn("assumptions", report["income"])
        self.assertEqual(report["budget"]["npv_at_year_three_rub"], 40)
        self.assertIn("not verified", report["status"])

    def test_cli_invalid_or_partial_expense_schedule_does_not_emit_json(self):
        for args in [["--benefit", "nan"], ["--initial-cost", "0"],
                     ["--annual-costs", "0", "0", "0"]]:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(SystemExit) as error:
                    finance.main(args)
                self.assertEqual(error.exception.code, 2)
                self.assertEqual(output.getvalue(), "")

    def test_default_report_does_not_assume_zero_expenses_or_measured_payback(self):
        report = finance.report()
        json.dumps(report, allow_nan=False)
        self.assertIn("No expenses supplied", report["budget_status"])
        self.assertNotIn("budget", report)
        self.assertEqual(report["capacity_separate"]["net_hours_half_gross_full_new_work"], 1150)


if __name__ == "__main__":
    unittest.main()
