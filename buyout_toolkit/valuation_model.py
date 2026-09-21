"""valuation_model.py

Standard private-equity valuation for a single acquisition target:
    1. An EBITDA-multiple ("comps") valuation, using a low/base/high
       multiple range appropriate to the target's sub-sector.
    2. A discounted cash flow (DCF) valuation, projecting unlevered free
       cash flow for an explicit forecast period and discounting it (plus
       a terminal value) back at the platform's required return (WACC).
    3. A cross-check that reconciles the two methods into a single
       enterprise value (EV) range and a corresponding equity value range
       (EV less net debt, consistent with a cash-free, debt-free deal
       structure).

All figures are derived from SYNTHETIC target data (see deal_pipeline.py)
and illustrative assumptions. Nothing here is investment advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from buyout_toolkit.deal_pipeline import SUB_SECTORS, Target

# ---------------------------------------------------------------------------
# EBITDA multiple assumptions by sub-sector (low / base / high), reflecting
# typical lower-middle-market multiples paid for essential-services bolt-ons
# in a roll-up strategy circa the mid-2020s. Illustrative only.
# ---------------------------------------------------------------------------
EBITDA_MULTIPLES: Dict[str, Dict[str, float]] = {
    "Residential HVAC Services": {"low": 5.5, "base": 6.5, "high": 7.5},
    "Plumbing & Drain Services": {"low": 5.0, "base": 6.0, "high": 7.0},
    "Pest & Termite Control": {"low": 6.5, "base": 7.5, "high": 8.5},
    "Commercial Landscaping & Grounds Maintenance": {"low": 4.5, "base": 5.5, "high": 6.5},
}


@dataclass
class ValuationAssumptions:
    """Assumptions driving the DCF leg of the valuation."""

    forecast_years: int = 5
    discount_rate: float = 0.13  # WACC / required return
    terminal_growth_rate: float = 0.025
    capex_pct_revenue: float = 0.02
    nwc_pct_revenue_change: float = 0.10  # incremental NWC as % of revenue growth
    tax_rate: float = 0.26
    # EBITDA margin is assumed to hold flat at the target's current margin
    # through the forecast unless overridden.
    margin_fade_to: Optional[float] = None  # optional linear fade target
    revenue_growth_fade_to: float = 0.03  # long-run growth the CAGR fades toward


@dataclass
class DcfYear:
    year: int
    revenue: float
    ebitda: float
    ebit: float
    taxes: float
    nopat: float
    capex: float
    change_in_nwc: float
    unlevered_fcf: float
    discount_factor: float
    pv_fcf: float


@dataclass
class ValuationResult:
    target_id: str
    company_name: str
    ebitda: float
    multiple_ev: Dict[str, float]
    dcf_years: List[DcfYear]
    dcf_terminal_value: float
    dcf_pv_terminal_value: float
    dcf_ev: float
    blended_ev_low: float
    blended_ev_base: float
    blended_ev_high: float
    net_debt: float
    equity_value_low: float
    equity_value_base: float
    equity_value_high: float
    assumptions: ValuationAssumptions = field(default_factory=ValuationAssumptions)


def ebitda_multiple_valuation(target: Target) -> Dict[str, float]:
    """Return {'low', 'base', 'high'} enterprise values from the
    sub-sector's EBITDA multiple range applied to the target's EBITDA.
    """
    multiples = EBITDA_MULTIPLES[target.sub_sector]
    ebitda = target.ebitda
    return {tier: round(ebitda * mult, 2) for tier, mult in multiples.items()}


def _project_dcf_years(target: Target, assumptions: ValuationAssumptions) -> List[DcfYear]:
    years: List[DcfYear] = []
    revenue = target.revenue
    margin = target.ebitda_margin
    growth = target.revenue_growth_rate
    prior_revenue = revenue

    n = assumptions.forecast_years
    margin_start = margin
    margin_end = assumptions.margin_fade_to if assumptions.margin_fade_to is not None else margin

    for yr in range(1, n + 1):
        # Linearly fade growth toward the long-run rate and margin toward
        # its ending value (if provided) over the forecast window.
        weight = yr / n
        yr_growth = growth + (assumptions.revenue_growth_fade_to - growth) * weight
        yr_margin = margin_start + (margin_end - margin_start) * weight

        revenue = prior_revenue * (1 + yr_growth)
        ebitda = revenue * yr_margin
        # Approximate D&A as a small, stable fraction of revenue for a
        # services business (asset-light relative to capex).
        da = revenue * 0.008
        ebit = ebitda - da
        taxes = max(ebit, 0.0) * assumptions.tax_rate
        nopat = ebit - taxes
        capex = revenue * assumptions.capex_pct_revenue
        change_in_nwc = (revenue - prior_revenue) * assumptions.nwc_pct_revenue_change
        unlevered_fcf = nopat + da - capex - change_in_nwc

        discount_factor = 1 / ((1 + assumptions.discount_rate) ** yr)
        pv_fcf = unlevered_fcf * discount_factor

        years.append(
            DcfYear(
                year=yr,
                revenue=round(revenue, 2),
                ebitda=round(ebitda, 2),
                ebit=round(ebit, 2),
                taxes=round(taxes, 2),
                nopat=round(nopat, 2),
                capex=round(capex, 2),
                change_in_nwc=round(change_in_nwc, 2),
                unlevered_fcf=round(unlevered_fcf, 2),
                discount_factor=round(discount_factor, 6),
                pv_fcf=round(pv_fcf, 2),
            )
        )
        prior_revenue = revenue

    return years


def dcf_valuation(
    target: Target, assumptions: Optional[ValuationAssumptions] = None
) -> Dict[str, object]:
    """Run a Gordon-growth terminal-value DCF and return the projected
    years, terminal value, and resulting enterprise value.
    """
    assumptions = assumptions or ValuationAssumptions()
    if assumptions.discount_rate <= assumptions.terminal_growth_rate:
        raise ValueError("discount_rate must exceed terminal_growth_rate")

    years = _project_dcf_years(target, assumptions)
    final_year = years[-1]

    terminal_value = (
        final_year.unlevered_fcf
        * (1 + assumptions.terminal_growth_rate)
        / (assumptions.discount_rate - assumptions.terminal_growth_rate)
    )
    pv_terminal_value = terminal_value * final_year.discount_factor

    pv_explicit_fcf = sum(y.pv_fcf for y in years)
    enterprise_value = pv_explicit_fcf + pv_terminal_value

    return {
        "years": years,
        "terminal_value": round(terminal_value, 2),
        "pv_terminal_value": round(pv_terminal_value, 2),
        "pv_explicit_fcf": round(pv_explicit_fcf, 2),
        "enterprise_value": round(enterprise_value, 2),
    }


def value_target(
    target: Target, assumptions: Optional[ValuationAssumptions] = None
) -> ValuationResult:
    """Produce the full cross-checked valuation (multiple + DCF) for a
    single target, including the reconciled EV range and equity value
    range.
    """
    assumptions = assumptions or ValuationAssumptions()

    multiple_ev = ebitda_multiple_valuation(target)
    dcf = dcf_valuation(target, assumptions)
    dcf_ev = dcf["enterprise_value"]

    # Blend the comps range with the DCF point estimate: widen/verify the
    # comps-implied low/high using the DCF as a sanity cross-check rather
    # than mechanically averaging, consistent with standard PE practice.
    blended_low = min(multiple_ev["low"], dcf_ev * 0.9)
    blended_high = max(multiple_ev["high"], dcf_ev * 1.1)
    blended_base = round((multiple_ev["base"] + dcf_ev) / 2, 2)

    net_debt = target.net_debt
    equity_low = round(blended_low - net_debt, 2)
    equity_base = round(blended_base - net_debt, 2)
    equity_high = round(blended_high - net_debt, 2)

    return ValuationResult(
        target_id=target.target_id,
        company_name=target.company_name,
        ebitda=target.ebitda,
        multiple_ev=multiple_ev,
        dcf_years=dcf["years"],
        dcf_terminal_value=dcf["terminal_value"],
        dcf_pv_terminal_value=dcf["pv_terminal_value"],
        dcf_ev=dcf_ev,
        blended_ev_low=round(blended_low, 2),
        blended_ev_base=blended_base,
        blended_ev_high=round(blended_high, 2),
        net_debt=net_debt,
        equity_value_low=equity_low,
        equity_value_base=equity_base,
        equity_value_high=equity_high,
        assumptions=assumptions,
    )


if __name__ == "__main__":
    from buyout_toolkit.deal_pipeline import generate_pipeline, rank_pipeline

    ranked = rank_pipeline(generate_pipeline())
    top = ranked[0]
    result = value_target(top)
    print(f"Valuation for {result.company_name} ({result.target_id})")
    print(f"EBITDA: ${result.ebitda:,.0f}")
    print(f"Multiple-based EV: {result.multiple_ev}")
    print(f"DCF EV: ${result.dcf_ev:,.0f}")
    print(
        f"Blended EV range: ${result.blended_ev_low:,.0f} - "
        f"${result.blended_ev_base:,.0f} - ${result.blended_ev_high:,.0f}"
    )
    print(
        f"Equity value range: ${result.equity_value_low:,.0f} - "
        f"${result.equity_value_base:,.0f} - ${result.equity_value_high:,.0f}"
    )
