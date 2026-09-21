import pytest

from buyout_toolkit.deal_pipeline import Target
from buyout_toolkit.lbo_model import (
    LboAssumptions,
    build_sources_and_uses,
    default_assumptions,
    irr_from_moic,
    project_schedule,
    run_all_cases,
)


def make_target(**overrides) -> Target:
    defaults = dict(
        target_id="T-LBO",
        company_name="LBO Test Co LLC",
        sub_sector="Residential HVAC Services",
        geography="TX",
        years_in_business=20,
        revenue=18_000_000.0,
        ebitda_margin=0.18,
        revenue_growth_rate=0.07,
        recurring_revenue_pct=0.45,
        customer_concentration_pct=0.15,
        number_of_locations=4,
        owner_age=61,
        succession_situation="Retirement - No Successor Identified",
        outreach_status="Management Meeting",
        net_debt=1_500_000.0,
    )
    defaults.update(overrides)
    return Target(**defaults)


def test_sources_and_uses_balance():
    target = make_target()
    assumptions = default_assumptions(target)
    su = build_sources_and_uses(target, assumptions)
    assert su.total_sources == pytest.approx(su.total_uses)
    assert su.is_balanced


def test_sources_and_uses_raises_when_debt_exceeds_uses():
    target = make_target()
    assumptions = default_assumptions(target)
    over_levered = LboAssumptions(
        **{**assumptions.__dict__, "senior_leverage_x_ebitda": 50.0, "seller_note_pct_of_ev": 0.9}
    )
    with pytest.raises(ValueError):
        build_sources_and_uses(target, over_levered)


def test_debt_balances_never_go_negative_and_are_non_increasing():
    target = make_target()
    assumptions = default_assumptions(target)
    su = build_sources_and_uses(target, assumptions)
    schedule = project_schedule(target, assumptions, su)

    prev_senior = su.senior_debt
    prev_seller = su.seller_note
    for yr in schedule:
        assert yr.senior_debt_end >= 0.0
        assert yr.senior_debt_end <= prev_senior + 1e-6
        prev_senior = yr.senior_debt_end
        prev_seller = yr.seller_note_end
    assert prev_seller >= 0.0


def test_mandatory_amortization_and_sweep_are_consistent_with_balance_roll():
    target = make_target()
    assumptions = default_assumptions(target)
    su = build_sources_and_uses(target, assumptions)
    schedule = project_schedule(target, assumptions, su)

    for yr in schedule:
        expected_end = (
            yr.senior_debt_begin - yr.mandatory_amortization - yr.cash_sweep_senior
        )
        assert yr.senior_debt_end == pytest.approx(expected_end, abs=0.01)


def test_irr_from_moic_matches_compound_growth_formula():
    assert irr_from_moic(2.0, 5) == pytest.approx(2.0 ** (1 / 5) - 1, abs=1e-3)
    assert irr_from_moic(1.0, 5) == pytest.approx(0.0, abs=1e-3)


def test_upside_case_outperforms_base_which_outperforms_downside():
    target = make_target()
    results = run_all_cases(target)
    assert results["upside"].moic > results["base"].moic > results["downside"].moic
    assert results["upside"].irr > results["base"].irr > results["downside"].irr
