import pytest

from buyout_toolkit.deal_pipeline import Target
from buyout_toolkit.valuation_model import (
    ValuationAssumptions,
    dcf_valuation,
    ebitda_multiple_valuation,
    value_target,
)


def make_target(**overrides) -> Target:
    defaults = dict(
        target_id="T-VAL",
        company_name="Valuation Test Co LLC",
        sub_sector="Plumbing & Drain Services",
        geography="TX",
        years_in_business=12,
        revenue=12_000_000.0,
        ebitda_margin=0.16,
        revenue_growth_rate=0.06,
        recurring_revenue_pct=0.35,
        customer_concentration_pct=0.12,
        number_of_locations=2,
        owner_age=57,
        succession_situation="Open to Partnership / Growth Capital",
        outreach_status="NDA Signed",
        net_debt=500_000.0,
    )
    defaults.update(overrides)
    return Target(**defaults)


def test_ebitda_multiple_valuation_orders_low_base_high():
    target = make_target()
    result = ebitda_multiple_valuation(target)
    assert result["low"] < result["base"] < result["high"]


def test_dcf_valuation_rejects_growth_at_or_above_discount_rate():
    target = make_target()
    bad_assumptions = ValuationAssumptions(discount_rate=0.05, terminal_growth_rate=0.06)
    with pytest.raises(ValueError):
        dcf_valuation(target, bad_assumptions)


def test_dcf_discount_factors_strictly_decrease_over_time():
    target = make_target()
    dcf = dcf_valuation(target)
    factors = [y.discount_factor for y in dcf["years"]]
    assert factors == sorted(factors, reverse=True)
    assert all(0 < f < 1 for f in factors)


def test_dcf_enterprise_value_equals_pv_of_fcf_plus_pv_terminal_value():
    target = make_target()
    dcf = dcf_valuation(target)
    assert dcf["enterprise_value"] == pytest.approx(
        dcf["pv_explicit_fcf"] + dcf["pv_terminal_value"], rel=1e-6
    )


def test_value_target_blended_ev_range_is_ordered():
    target = make_target()
    result = value_target(target)
    assert result.blended_ev_low <= result.blended_ev_base <= result.blended_ev_high


def test_value_target_equity_value_equals_ev_less_net_debt():
    target = make_target(net_debt=2_000_000.0)
    result = value_target(target)
    assert result.equity_value_base == pytest.approx(result.blended_ev_base - target.net_debt)
    assert result.equity_value_low == pytest.approx(result.blended_ev_low - target.net_debt)
    assert result.equity_value_high == pytest.approx(result.blended_ev_high - target.net_debt)
