"""Reproduce illustrative income ceilings. No model, network or company data."""
import json

def income_case(b, ramp, nominal_growth, nominal_discount):
    """b is an independent assumed gross annual monetary benefit, not hours."""
    if len(ramp) != 3 or b < 0 or nominal_discount <= -1:
        raise ValueError("Need a nonnegative benefit, three years, and r > -1")
    gross = [b * u * (1 + nominal_growth) ** t for t, u in enumerate(ramp)]
    pv = [value / (1 + nominal_discount) ** (t + 1)
          for t, value in enumerate(gross)]
    return {
        "gross_benefit_by_year_rub": gross,
        "pv_by_year_rub": pv,
        "simple_total_expense_ceiling_rub": sum(gross),
        "total_expense_pv_ceiling_rub": sum(pv),
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
        "cases": {
            "cautious": income_case(230000, [.25, .75, 1], .04, .26),
            "base": income_case(1656000, [.5, 1, 1], .06, .20),
            "favorable": income_case(4830000, [.75, 1, 1], .08, .14),
            "no_verified_cash": income_case(0, [.5, 1, 1], .06, .20),
        },
        "base_discount_sensitivity": {
            str(r): income_case(1656000, [.5, 1, 1], .06, r)["total_expense_pv_ceiling_rub"]
            for r in [.14, .20, .26]
        },
    }

if __name__ == "__main__":
    print(json.dumps(report(), indent=2, ensure_ascii=False))
