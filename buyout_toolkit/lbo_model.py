"""lbo_model.py

A simplified leveraged buyout (LBO) model for a single acquisition target:
a sources & uses table, a 5-year operating and debt-paydown schedule, and
an exit at a terminal EBITDA multiple producing platform-level IRR and
MOIC. Base, upside, and downside operating cases are supported.

Financing structure modeled:
    - Senior debt: amortizing term loan (mandatory amortization + a
      100% cash-flow sweep of any remaining free cash flow).
    - Seller note: subordinated seller financing, PIK-accruing until the
      senior debt is fully repaid, then swept.
    - Sponsor equity: the balancing "plug" in the sources & uses table.

All figures are derived from SYNTHETIC target data and illustrative deal
assumptions; nothing here constitutes investment advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional

from buyout_toolkit.deal_pipeline import Target
from buyout_toolkit.valuation_model import EBITDA_MULTIPLES


@dataclass
class LboAssumptions:
    entry_multiple: float
    hold_period_years: int = 5
    senior_leverage_x_ebitda: float = 3.5
    senior_interest_rate: float = 0.095
    senior_mandatory_amort_pct: float = 0.07  # % of original principal per year
    seller_note_pct_of_ev: float = 0.10
    seller_note_rate: float = 0.08  # PIK accrual rate
    transaction_fee_pct: float = 0.02
    revenue_growth_rate: float = 0.06
    ebitda_margin: Optional[float] = None  # defaults to target's own margin
    margin_expansion_bps_per_year: float = 0.0
    capex_pct_revenue: float = 0.015
    nwc_pct_revenue_change: float = 0.08
    cash_tax_rate: float = 0.26
    da_pct_revenue: float = 0.006
    cash_sweep_pct: float = 1.0  # % of post-amortization FCF swept to debt
    exit_multiple: Optional[float] = None  # defaults to entry_multiple


@dataclass
class YearSchedule:
    year: int
    revenue: float
    ebitda: float
    senior_debt_begin: float
    seller_note_begin: float
    cash_interest_senior: float
    seller_note_pik_accrual: float
    da: float
    ebit: float
    cash_taxes: float
    capex: float
    change_in_nwc: float
    free_cash_flow_pre_debt_service: float
    mandatory_amortization: float
    cash_sweep_senior: float
    cash_sweep_seller_note: float
    senior_debt_end: float
    seller_note_end: float


@dataclass
class SourcesUses:
    purchase_enterprise_value: float
    transaction_fees: float
    total_uses: float
    senior_debt: float
    seller_note: float
    sponsor_equity: float
    total_sources: float

    @property
    def is_balanced(self) -> bool:
        return abs(self.total_sources - self.total_uses) < 0.01


@dataclass
class LboResult:
    case: str
    target_id: str
    company_name: str
    sources_uses: SourcesUses
    schedule: List[YearSchedule]
    exit_ebitda: float
    exit_multiple: float
    exit_enterprise_value: float
    exit_net_debt: float
    exit_equity_value: float
    initial_equity: float
    moic: float
    irr: float
    assumptions: LboAssumptions


CASE_OVERRIDES: Dict[str, Dict[str, float]] = {
    "base": {},
    "upside": {
        "revenue_growth_rate_delta": 0.03,
        "margin_expansion_bps_per_year": 0.004,
        "exit_multiple_delta": 0.5,
    },
    "downside": {
        "revenue_growth_rate_delta": -0.05,
        "margin_expansion_bps_per_year": -0.006,
        "exit_multiple_delta": -0.75,
    },
}


def default_assumptions(target: Target) -> LboAssumptions:
    """Build a reasonable base-case assumption set for ``target`` using
    the sub-sector's base EBITDA multiple as both entry and exit.
    """
    base_multiple = EBITDA_MULTIPLES[target.sub_sector]["base"]
    return LboAssumptions(
        entry_multiple=base_multiple,
        revenue_growth_rate=max(target.revenue_growth_rate, 0.02),
        ebitda_margin=target.ebitda_margin,
        exit_multiple=base_multiple,
    )


def apply_case(assumptions: LboAssumptions, case: str) -> LboAssumptions:
    """Return a new ``LboAssumptions`` with the named case's deltas
    applied to the base assumptions. ``case`` must be one of
    'base', 'upside', 'downside'.
    """
    if case not in CASE_OVERRIDES:
        raise ValueError(f"Unknown case '{case}'; expected one of {list(CASE_OVERRIDES)}")

    overrides = CASE_OVERRIDES[case]
    exit_multiple = assumptions.exit_multiple if assumptions.exit_multiple is not None else assumptions.entry_multiple

    return replace(
        assumptions,
        revenue_growth_rate=assumptions.revenue_growth_rate
        + overrides.get("revenue_growth_rate_delta", 0.0),
        margin_expansion_bps_per_year=assumptions.margin_expansion_bps_per_year
        + overrides.get("margin_expansion_bps_per_year", 0.0),
        exit_multiple=max(exit_multiple + overrides.get("exit_multiple_delta", 0.0), 1.0),
    )


def build_sources_and_uses(target: Target, assumptions: LboAssumptions) -> SourcesUses:
    """Construct the sources & uses table for the acquisition. Assumes a
    cash-free, debt-free transaction: uses equal the purchase EV plus
    transaction fees; sources are senior debt + seller note + sponsor
    equity (the plug), which must balance to total uses by construction.
    """
    purchase_ev = round(target.ebitda * assumptions.entry_multiple, 2)
    fees = round(purchase_ev * assumptions.transaction_fee_pct, 2)
    total_uses = round(purchase_ev + fees, 2)

    senior_debt = round(target.ebitda * assumptions.senior_leverage_x_ebitda, 2)
    seller_note = round(purchase_ev * assumptions.seller_note_pct_of_ev, 2)
    sponsor_equity = round(total_uses - senior_debt - seller_note, 2)

    if sponsor_equity < 0:
        raise ValueError(
            "Debt financing exceeds total uses; reduce leverage or seller note assumptions."
        )

    total_sources = round(senior_debt + seller_note + sponsor_equity, 2)

    return SourcesUses(
        purchase_enterprise_value=purchase_ev,
        transaction_fees=fees,
        total_uses=total_uses,
        senior_debt=senior_debt,
        seller_note=seller_note,
        sponsor_equity=sponsor_equity,
        total_sources=total_sources,
    )


def project_schedule(
    target: Target, assumptions: LboAssumptions, sources_uses: SourcesUses
) -> List[YearSchedule]:
    """Project the operating and debt-paydown schedule over the hold
    period. Free cash flow after mandatory amortization is swept, first
    to the senior debt and then (once senior is fully repaid) to the
    seller note.
    """
    schedule: List[YearSchedule] = []

    revenue = target.revenue
    margin = assumptions.ebitda_margin if assumptions.ebitda_margin is not None else target.ebitda_margin
    senior_balance = sources_uses.senior_debt
    seller_balance = sources_uses.seller_note
    original_senior_principal = sources_uses.senior_debt
    mandatory_amort = original_senior_principal * assumptions.senior_mandatory_amort_pct

    for yr in range(1, assumptions.hold_period_years + 1):
        revenue = revenue * (1 + assumptions.revenue_growth_rate)
        margin = margin + assumptions.margin_expansion_bps_per_year
        ebitda = revenue * margin

        senior_begin = senior_balance
        seller_begin = seller_balance

        cash_interest_senior = senior_begin * assumptions.senior_interest_rate
        seller_pik_accrual = seller_begin * assumptions.seller_note_rate

        da = revenue * assumptions.da_pct_revenue
        ebit = ebitda - da - cash_interest_senior
        cash_taxes = max(ebit, 0.0) * assumptions.cash_tax_rate
        capex = revenue * assumptions.capex_pct_revenue
        change_in_nwc = revenue * assumptions.revenue_growth_rate * assumptions.nwc_pct_revenue_change

        fcf_pre_debt_service = (
            ebitda - cash_interest_senior - cash_taxes - capex - change_in_nwc
        )

        actual_mandatory_amort = min(mandatory_amort, senior_begin)
        fcf_after_mandatory = max(fcf_pre_debt_service - actual_mandatory_amort, 0.0)

        senior_after_mandatory = senior_begin - actual_mandatory_amort
        sweep_amount = fcf_after_mandatory * assumptions.cash_sweep_pct

        sweep_to_senior = min(sweep_amount, senior_after_mandatory)
        remaining_sweep = sweep_amount - sweep_to_senior

        seller_end_before_sweep = seller_begin + seller_pik_accrual
        sweep_to_seller = min(remaining_sweep, seller_end_before_sweep)

        senior_end = senior_after_mandatory - sweep_to_senior
        seller_end = seller_end_before_sweep - sweep_to_seller

        schedule.append(
            YearSchedule(
                year=yr,
                revenue=round(revenue, 2),
                ebitda=round(ebitda, 2),
                senior_debt_begin=round(senior_begin, 2),
                seller_note_begin=round(seller_begin, 2),
                cash_interest_senior=round(cash_interest_senior, 2),
                seller_note_pik_accrual=round(seller_pik_accrual, 2),
                da=round(da, 2),
                ebit=round(ebit, 2),
                cash_taxes=round(cash_taxes, 2),
                capex=round(capex, 2),
                change_in_nwc=round(change_in_nwc, 2),
                free_cash_flow_pre_debt_service=round(fcf_pre_debt_service, 2),
                mandatory_amortization=round(actual_mandatory_amort, 2),
                cash_sweep_senior=round(sweep_to_senior, 2),
                cash_sweep_seller_note=round(sweep_to_seller, 2),
                senior_debt_end=round(senior_end, 2),
                seller_note_end=round(seller_end, 2),
            )
        )

        senior_balance = senior_end
        seller_balance = seller_end

    return schedule


def irr_from_moic(moic: float, years: int) -> float:
    """Annualized IRR implied by a single-period MOIC over ``years``."""
    if moic <= 0:
        raise ValueError("moic must be positive")
    return round(moic ** (1 / years) - 1, 4)


def run_lbo_case(
    target: Target, case: str = "base", base_assumptions: Optional[LboAssumptions] = None
) -> LboResult:
    """Run the full LBO (sources & uses, schedule, exit) for the given
    case ('base', 'upside', or 'downside').
    """
    base_assumptions = base_assumptions or default_assumptions(target)
    assumptions = apply_case(base_assumptions, case)

    sources_uses = build_sources_and_uses(target, assumptions)
    schedule = project_schedule(target, assumptions, sources_uses)
    final_year = schedule[-1]

    exit_multiple = assumptions.exit_multiple if assumptions.exit_multiple is not None else assumptions.entry_multiple
    exit_ev = round(final_year.ebitda * exit_multiple, 2)
    exit_net_debt = round(final_year.senior_debt_end + final_year.seller_note_end, 2)
    exit_equity = round(exit_ev - exit_net_debt, 2)

    initial_equity = sources_uses.sponsor_equity
    moic = round(exit_equity / initial_equity, 4) if initial_equity > 0 else 0.0
    irr = irr_from_moic(moic, assumptions.hold_period_years) if moic > 0 else -1.0

    return LboResult(
        case=case,
        target_id=target.target_id,
        company_name=target.company_name,
        sources_uses=sources_uses,
        schedule=schedule,
        exit_ebitda=final_year.ebitda,
        exit_multiple=exit_multiple,
        exit_enterprise_value=exit_ev,
        exit_net_debt=exit_net_debt,
        exit_equity_value=exit_equity,
        initial_equity=initial_equity,
        moic=moic,
        irr=irr,
        assumptions=assumptions,
    )


def run_all_cases(
    target: Target, base_assumptions: Optional[LboAssumptions] = None
) -> Dict[str, LboResult]:
    """Convenience helper: run base, upside, and downside cases and
    return them keyed by case name.
    """
    base_assumptions = base_assumptions or default_assumptions(target)
    return {
        case: run_lbo_case(target, case=case, base_assumptions=base_assumptions)
        for case in CASE_OVERRIDES
    }


if __name__ == "__main__":
    from buyout_toolkit.deal_pipeline import generate_pipeline, rank_pipeline

    top = rank_pipeline(generate_pipeline())[0]
    results = run_all_cases(top)

    print(f"LBO summary for {top.company_name} ({top.target_id})\n")
    su = results["base"].sources_uses
    print("Sources & Uses (base case):")
    print(f"  Purchase EV:      ${su.purchase_enterprise_value:,.0f}")
    print(f"  Transaction fees: ${su.transaction_fees:,.0f}")
    print(f"  Total uses:       ${su.total_uses:,.0f}")
    print(f"  Senior debt:      ${su.senior_debt:,.0f}")
    print(f"  Seller note:      ${su.seller_note:,.0f}")
    print(f"  Sponsor equity:   ${su.sponsor_equity:,.0f}")
    print(f"  Total sources:    ${su.total_sources:,.0f} (balanced={su.is_balanced})\n")

    for case, result in results.items():
        print(f"{case.title():<10} MOIC: {result.moic:.2f}x   IRR: {result.irr:.1%}")
