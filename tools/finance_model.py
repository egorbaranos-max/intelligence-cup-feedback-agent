"""Conditional three-year cash ceilings. Run --help for explicit budget scenarios.

No model, network or company data. Rates are fractions (0.20 means 20%).
All flows and the discount rate must share a tax basis. There is no hourly-to-cash
conversion. Income and annual expenses occur at year end; initial cost is at t=0.
"""
import argparse
import json
import math
from numbers import Real


CASES = {
    "cautious": (230000, (.25, .75, 1), .04, .26),
    "base": (1656000, (.5, 1, 1), .06, .20),
    "favorable": (4830000, (.75, 1, 1), .08, .14),
    "no_verified_cash": (0, (.5, 1, 1), .06, .20),
}


def _finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number, not a boolean/string")
    try:
        value = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{name} must be finite") from error
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _three_numbers(values, name):
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} needs exactly three annual values")
    try:
        values = tuple(values)
    except TypeError as error:
        raise ValueError(f"{name} needs exactly three annual values") from error
    if len(values) != 3:
        raise ValueError(f"{name} needs exactly three annual values")
    return [_finite_number(value, f"{name}[{i + 1}]")
            for i, value in enumerate(values)]


def _finite_results(values):
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Inputs produce non-finite cash flows; reduce their magnitude")


def income_case(b, ramp, nominal_growth, nominal_discount):
    """Independent assumed gross RUB/year in year-one prices, before project costs.

    Exactly three adoption fractions in [0, 1]; growth >= -1 and discount > -1.
    A zero ceiling without verified cash is not proof of a profitable project.
    """
    b = _finite_number(b, "b")
    ramp = _three_numbers(ramp, "ramp")
    nominal_growth = _finite_number(nominal_growth, "nominal_growth")
    nominal_discount = _finite_number(nominal_discount, "nominal_discount")
    if b < 0:
        raise ValueError("b must be nonnegative gross RUB/year")
    if any(u < 0 or u > 1 for u in ramp):
        raise ValueError("ramp values must be adoption fractions between 0 and 1")
    if nominal_growth < -1 or nominal_discount <= -1:
        raise ValueError("Need nominal_growth >= -1 and nominal_discount > -1")
    try:
        gross = [b * u * (1 + nominal_growth) ** t for t, u in enumerate(ramp)]
        pv = [value / (1 + nominal_discount) ** (t + 1)
              for t, value in enumerate(gross)]
        totals = [math.fsum(gross), math.fsum(pv)]
    except (OverflowError, ZeroDivisionError) as error:
        raise ValueError("Inputs exceed the numeric range of this calculator") from error
    _finite_results(gross + pv + totals)
    return {
        "assumptions": {
            "mature_gross_benefit_rub_per_year_in_year_one_prices": b,
            "adoption_by_project_year": ramp,
            "nominal_growth_fraction": nominal_growth,
            "nominal_discount_fraction": nominal_discount,
        },
        "gross_benefit_by_year_rub": gross,
        "pv_by_year_rub": pv,
        "simple_total_expense_ceiling_rub": totals[0],
        "total_expense_pv_ceiling_rub": totals[1],
    }


def budget_case(b, ramp, nominal_growth, nominal_discount, initial_cost, annual_costs):
    """Assess a supplied expense schedule; this does not verify any company benefit.

    Negative headroom is retained: future expenses alone may exceed the ceiling.
    Payback is reported only at year ends and must remain nonnegative through year
    three; a temporary early crossing followed by a loss is not called payback.
    There is no inference about months, later years, taxes, or payment liquidity.
    """
    income = income_case(b, ramp, nominal_growth, nominal_discount)
    initial_cost = _finite_number(initial_cost, "initial_cost")
    annual_costs = _three_numbers(annual_costs, "annual_costs")
    if initial_cost < 0 or any(value < 0 for value in annual_costs):
        raise ValueError("All project cash outflows must be nonnegative")
    r = income["assumptions"]["nominal_discount_fraction"]
    try:
        expense_pv = [value / (1 + r) ** (i + 1)
                      for i, value in enumerate(annual_costs)]
        future_pv = math.fsum(expense_pv)
        max_initial = income["total_expense_pv_ceiling_rub"] - future_pv
        cost_pv = math.fsum([initial_cost, future_pv])
        net_pv = [benefit - cost for benefit, cost in
                  zip(income["pv_by_year_rub"], expense_pv)]
        cumulative = [-initial_cost] + [math.fsum([-initial_cost] + net_pv[:i])
                                        for i in range(1, 4)]
        # Subtract in the same order as the reported initial-budget ceiling so a
        # caller using that ceiling gets exactly zero at the threshold.
        npv = max_initial - initial_cost
        # Use one final NPV expression for the threshold and final cumulative value.
        cumulative[-1] = npv
    except (OverflowError, ZeroDivisionError) as error:
        raise ValueError("Expense inputs exceed the numeric range") from error
    _finite_results(expense_pv + cumulative + [future_pv, max_initial, cost_pv, npv])
    payback = next((year for year in range(4)
                    if all(value >= 0 for value in cumulative[year:])), None)
    return {
        "status": "Conditional on the supplied cash flows; not measured payback",
        "income": income,
        "initial_cash_outflow_rub": initial_cost,
        "annual_cash_outflows_rub": annual_costs,
        "future_expense_pv_rub": future_pv,
        "total_expense_pv_rub": cost_pv,
        "max_initial_outlay_after_future_expenses_rub": max_initial,
        "nonnegative_initial_outlay_feasible": max_initial >= 0,
        "npv_at_year_three_rub": npv,
        "meets_three_year_discounted_threshold_under_assumptions": npv >= 0,
        "cumulative_net_pv_at_t0_and_year_ends_rub": cumulative,
        "sustained_discounted_payback_year_end_within_horizon": payback,
    }


def report():
    return {
        "status": "Illustrative assumptions; not measured ROI or investment advice",
        "timing": "Three years from project start; income at each year end",
        "cash_boundary": "ALL project cash outflows belong in the expense budget; not deducted from gross benefits here",
        "capacity_separate": {
            "support_hours_saved_mature": 40 * .5 * 46 * (4 - .5),
            "new_pm_hours": 230,
            "new_qa_ops_hours": 230,
            "net_hours_mature": 40 * .5 * 46 * (4 - .5) - 230 - 230,
            "net_hours_half_gross_full_new_work": .5 * 3220 - 230 - 230,
            "note": "All inputs except 40 managers are assumptions. Hours do not determine b.",
        },
        "units": "RUB; annual nominal rates as fractions; t=0 is project start",
        "tax_basis": "Illustrative pre-tax benefits and pre-tax discount rate",
        "budget_status": "No expenses supplied; no actual NPV/payback established",
        "cases": {name: income_case(*inputs) for name, inputs in CASES.items()},
        "base_discount_sensitivity": {
            str(r): income_case(1656000, [.5, 1, 1], .06, r)["total_expense_pv_ceiling_rub"]
            for r in [.14, .20, .26]
        },
        "base_gross_benefit_sensitivity": {
            str(b): income_case(b, [.5, 1, 1], .06, .20)["total_expense_pv_ceiling_rub"]
            for b in [0, 828000, 1656000]
        },
        "sensitivity_note": "One input at a time; no probabilities or hourly-to-cash conversion",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: --case base --initial-cost 1000000 --annual-costs 100000 100000 100000. "
               "All amounts in this example are assumptions, not company data.")
    parser.add_argument("--case", choices=CASES, help="Use illustrative inputs for one case")
    parser.add_argument("--benefit", type=float, help="Independent gross mature RUB/year, in year-one prices")
    parser.add_argument("--ramp", type=float, nargs=3, metavar=("U1", "U2", "U3"), help="Three adoption fractions, each 0..1")
    parser.add_argument("--growth", type=float, help="Nominal annual growth fraction, e.g. 0.06")
    parser.add_argument("--discount", type=float, help="Nominal annual discount fraction, e.g. 0.20")
    parser.add_argument("--initial-cost", type=float, help="Initial project cash outflow at t=0, RUB")
    parser.add_argument("--annual-costs", type=float, nargs=3, metavar=("O1", "O2", "O3"), help="All additional project cash outflows at year ends, RUB")
    args = parser.parse_args(argv)
    if all(value is None for value in vars(args).values()):
        result = report()
    else:
        if (args.initial_cost is None) != (args.annual_costs is None):
            parser.error("Provide both --initial-cost and --annual-costs; zero costs are not inferred")
        defaults = CASES[args.case or "base"]
        inputs = tuple(override if override is not None else default for override, default in
                       zip((args.benefit, args.ramp, args.growth, args.discount), defaults))
        try:
            result = {
                "status": "Supplied/illustrative assumptions; not verified company cash flows",
                "timing": "Three years from project start; annual flows at year ends",
                "tax_basis": "User must supply benefits/costs/rate on the same tax basis",
                "income": income_case(*inputs),
                "budget_status": "Not assessed: no expense schedule supplied",
            }
            if args.initial_cost is not None:
                result["budget"] = budget_case(*inputs, args.initial_cost, args.annual_costs)
                result["budget_status"] = "Conditional assessment of the supplied expense schedule"
        except ValueError as error:
            parser.error(str(error))
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
