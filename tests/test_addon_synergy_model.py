import pytest

from buyout_toolkit.addon_synergy_model import (
    SynergyAssumptions,
    build_platform_co,
    compare_with_without_synergies,
    project_synergies,
)
from buyout_toolkit.deal_pipeline import Target
from buyout_toolkit.lbo_model import default_assumptions, run_lbo_case


def make_target(**overrides) -> Target:
    defaults = dict(
        target_id="T-SYN",
        company_name="Synergy Test Co LLC",
        sub_sector="Pest & Termite Control",
        geography="FL",
        years_in_business=10,
        revenue=9_000_000.0,
        ebitda_margin=0.20,
        revenue_growth_rate=0.09,
        recurring_revenue_pct=0.55,
        customer_concentration_pct=0.08,
        number_of_locations=3,
        owner_age=52,
        succession_situation="Second-Generation Owner - Growth Mode",
        outreach_status="LOI Submitted",
        net_debt=750_000.0,
    )
    defaults.update(overrides)
    return Target(**defaults)


def test_synergies_ramp_to_full_run_rate_by_ramp_year():
    target = make_target()
    lbo_result = run_lbo_case(target, case="base", base_assumptions=default_assumptions(target))
    assumptions = SynergyAssumptions(ramp_years=3, hold_period_years=5)
    schedule = project_synergies(target, lbo_result, assumptions)

    assert schedule[0].ramp_fraction < schedule[1].ramp_fraction < schedule[2].ramp_fraction
    assert schedule[2].ramp_fraction == pytest.approx(1.0)
    assert schedule[4].ramp_fraction == pytest.approx(1.0)


def test_synergy_ebitda_increases_while_ramping():
    target = make_target()
    lbo_result = run_lbo_case(target, case="base", base_assumptions=default_assumptions(target))
    schedule = project_synergies(target, lbo_result, SynergyAssumptions())
    assert schedule[0].total_synergy_ebitda < schedule[1].total_synergy_ebitda < schedule[2].total_synergy_ebitda


def test_synergy_ebitda_is_sum_of_its_three_components():
    target = make_target()
    lbo_result = run_lbo_case(target, case="base", base_assumptions=default_assumptions(target))
    schedule = project_synergies(target, lbo_result, SynergyAssumptions())
    for yr in schedule:
        expected = yr.cross_sell_ebitda + yr.overhead_synergy_ebitda + yr.purchasing_synergy_ebitda
        assert yr.total_synergy_ebitda == pytest.approx(expected, abs=0.05)


def test_combined_case_with_synergies_beats_without():
    target = make_target()
    comparison = compare_with_without_synergies(target)
    assert comparison.with_synergies.moic >= comparison.without_synergies.moic
    assert comparison.with_synergies.irr >= comparison.without_synergies.irr


def test_delta_moic_and_irr_are_internally_consistent():
    target = make_target()
    comparison = compare_with_without_synergies(target)
    assert comparison.delta_moic == pytest.approx(
        comparison.with_synergies.moic - comparison.without_synergies.moic
    )
    assert comparison.delta_irr == pytest.approx(
        comparison.with_synergies.irr - comparison.without_synergies.irr
    )


def test_initial_combined_equity_equals_platform_basis_plus_lbo_equity():
    target = make_target()
    platform = build_platform_co()
    lbo_result = run_lbo_case(target, case="base", base_assumptions=default_assumptions(target))
    comparison = compare_with_without_synergies(target, platform=platform, lbo_result=lbo_result)

    expected = platform.sponsor_equity_basis + lbo_result.initial_equity
    assert comparison.without_synergies.initial_combined_equity == pytest.approx(expected)
    assert comparison.with_synergies.initial_combined_equity == pytest.approx(expected)
