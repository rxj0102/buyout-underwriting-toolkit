"""addon_synergy_model.py

Models the acquisition target as an "add-on" (bolt-on) to an existing PE
platform company within the same durable, essential-services roll-up
strategy. Quantifies revenue synergies (cross-selling into the platform's
existing customer base) and cost synergies (corporate overhead
consolidation and purchasing/procurement scale), ramped in over several
years, and compares combined platform-level IRR/MOIC with vs. without
those synergies being realized.

The existing "platform" is SYNTHETIC, representing a regional platform the
sponsor already controls in the same roll-up. All figures here build on
the synthetic target data and LBO structure defined elsewhere in this
package; nothing here constitutes investment advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from buyout_toolkit.deal_pipeline import Target
from buyout_toolkit.lbo_model import LboResult, default_assumptions, run_lbo_case


@dataclass
class PlatformCo:
    """The sponsor's existing platform company that the target will be
    bolted onto. Synthetic figures representative of a regional
    multi-branch essential-services platform a few years into its
    build-out.
    """

    name: str = "Meridian Essential Services Platform"
    revenue: float = 68_000_000.0
    ebitda_margin: float = 0.19
    existing_net_debt: float = 42_000_000.0
    sponsor_equity_basis: float = 55_000_000.0

    @property
    def ebitda(self) -> float:
        return round(self.revenue * self.ebitda_margin, 2)


def build_platform_co() -> PlatformCo:
    """Return the standard synthetic platform used across this project's
    examples and tests.
    """
    return PlatformCo()


@dataclass
class SynergyAssumptions:
    hold_period_years: int = 5
    ramp_years: int = 3  # years to reach full run-rate synergies
    cross_sell_revenue_synergy_pct: float = 0.06  # incremental revenue as % of target revenue at run-rate
    cross_sell_incremental_margin: float = 0.35  # EBITDA flow-through on incremental cross-sell revenue
    overhead_consolidation_pct_of_target_revenue: float = 0.025
    purchasing_scale_pct_of_target_revenue: float = 0.018
    platform_growth_rate: float = 0.05
    platform_debt_amort_pct_per_year: float = 0.12
    platform_exit_multiple_premium: float = 0.5  # turns of extra multiple for combined scale at exit


@dataclass
class SynergyYear:
    year: int
    ramp_fraction: float
    target_revenue: float
    cross_sell_revenue: float
    cross_sell_ebitda: float
    overhead_synergy_ebitda: float
    purchasing_synergy_ebitda: float
    total_synergy_ebitda: float


@dataclass
class CombinedCaseResult:
    realized_synergies: bool
    combined_ebitda_by_year: List[float]
    exit_combined_ebitda: float
    exit_multiple: float
    exit_enterprise_value: float
    exit_net_debt: float
    exit_equity_value: float
    initial_combined_equity: float
    moic: float
    irr: float


@dataclass
class SynergyComparison:
    target_id: str
    company_name: str
    platform_name: str
    synergy_schedule: List[SynergyYear]
    run_rate_annual_synergy_ebitda: float
    without_synergies: CombinedCaseResult
    with_synergies: CombinedCaseResult
    delta_moic: float
    delta_irr: float


def _ramp_fraction(year: int, ramp_years: int) -> float:
    if ramp_years <= 0:
        return 1.0
    return min(year / ramp_years, 1.0)


def project_synergies(
    target: Target,
    lbo_result: LboResult,
    assumptions: Optional[SynergyAssumptions] = None,
) -> List[SynergyYear]:
    """Project the year-by-year revenue and cost synergy dollars, ramping
    linearly to full run-rate over ``assumptions.ramp_years``.

    Target revenue by year is taken from the LBO operating schedule so the
    synergy case stays consistent with the standalone acquisition model.
    """
    assumptions = assumptions or SynergyAssumptions()
    years: List[SynergyYear] = []

    for yr_schedule in lbo_result.schedule[: assumptions.hold_period_years]:
        yr = yr_schedule.year
        ramp = _ramp_fraction(yr, assumptions.ramp_years)
        target_revenue = yr_schedule.revenue

        cross_sell_revenue = target_revenue * assumptions.cross_sell_revenue_synergy_pct * ramp
        cross_sell_ebitda = cross_sell_revenue * assumptions.cross_sell_incremental_margin
        overhead_synergy = (
            target_revenue * assumptions.overhead_consolidation_pct_of_target_revenue * ramp
        )
        purchasing_synergy = (
            target_revenue * assumptions.purchasing_scale_pct_of_target_revenue * ramp
        )
        total = cross_sell_ebitda + overhead_synergy + purchasing_synergy

        years.append(
            SynergyYear(
                year=yr,
                ramp_fraction=round(ramp, 4),
                target_revenue=round(target_revenue, 2),
                cross_sell_revenue=round(cross_sell_revenue, 2),
                cross_sell_ebitda=round(cross_sell_ebitda, 2),
                overhead_synergy_ebitda=round(overhead_synergy, 2),
                purchasing_synergy_ebitda=round(purchasing_synergy, 2),
                total_synergy_ebitda=round(total, 2),
            )
        )

    return years


def _combined_case(
    platform: PlatformCo,
    target: Target,
    lbo_result: LboResult,
    assumptions: SynergyAssumptions,
    synergy_by_year: List[SynergyYear],
    realize_synergies: bool,
) -> CombinedCaseResult:
    platform_revenue = platform.revenue
    platform_debt = platform.existing_net_debt
    platform_original_debt = platform.existing_net_debt

    combined_ebitda_by_year: List[float] = []

    for idx, target_year in enumerate(lbo_result.schedule[: assumptions.hold_period_years]):
        platform_revenue = platform_revenue * (1 + assumptions.platform_growth_rate)
        platform_ebitda = platform_revenue * platform.ebitda_margin

        synergy_ebitda = synergy_by_year[idx].total_synergy_ebitda if realize_synergies else 0.0
        combined_ebitda = platform_ebitda + target_year.ebitda + synergy_ebitda
        combined_ebitda_by_year.append(round(combined_ebitda, 2))

        platform_debt = max(
            platform_debt - platform_original_debt * assumptions.platform_debt_amort_pct_per_year,
            0.0,
        )

    final_target_year = lbo_result.schedule[assumptions.hold_period_years - 1]
    exit_combined_ebitda = combined_ebitda_by_year[-1]
    exit_multiple = lbo_result.exit_multiple + assumptions.platform_exit_multiple_premium
    exit_ev = round(exit_combined_ebitda * exit_multiple, 2)

    exit_net_debt = round(platform_debt + final_target_year.senior_debt_end + final_target_year.seller_note_end, 2)
    exit_equity_value = round(exit_ev - exit_net_debt, 2)

    initial_combined_equity = round(platform.sponsor_equity_basis + lbo_result.initial_equity, 2)
    moic = round(exit_equity_value / initial_combined_equity, 4) if initial_combined_equity > 0 else 0.0
    irr = round(moic ** (1 / assumptions.hold_period_years) - 1, 4) if moic > 0 else -1.0

    return CombinedCaseResult(
        realized_synergies=realize_synergies,
        combined_ebitda_by_year=combined_ebitda_by_year,
        exit_combined_ebitda=exit_combined_ebitda,
        exit_multiple=exit_multiple,
        exit_enterprise_value=exit_ev,
        exit_net_debt=exit_net_debt,
        exit_equity_value=exit_equity_value,
        initial_combined_equity=initial_combined_equity,
        moic=moic,
        irr=irr,
    )


def compare_with_without_synergies(
    target: Target,
    platform: Optional[PlatformCo] = None,
    lbo_result: Optional[LboResult] = None,
    assumptions: Optional[SynergyAssumptions] = None,
) -> SynergyComparison:
    """Run the combined platform + add-on case with and without synergies
    realized, and return both results plus the IRR/MOIC delta.
    """
    platform = platform or build_platform_co()
    assumptions = assumptions or SynergyAssumptions()
    lbo_result = lbo_result or run_lbo_case(target, case="base", base_assumptions=default_assumptions(target))

    synergy_schedule = project_synergies(target, lbo_result, assumptions)
    run_rate = synergy_schedule[-1].total_synergy_ebitda if synergy_schedule else 0.0

    without = _combined_case(platform, target, lbo_result, assumptions, synergy_schedule, realize_synergies=False)
    with_syn = _combined_case(platform, target, lbo_result, assumptions, synergy_schedule, realize_synergies=True)

    return SynergyComparison(
        target_id=target.target_id,
        company_name=target.company_name,
        platform_name=platform.name,
        synergy_schedule=synergy_schedule,
        run_rate_annual_synergy_ebitda=round(run_rate, 2),
        without_synergies=without,
        with_synergies=with_syn,
        delta_moic=round(with_syn.moic - without.moic, 4),
        delta_irr=round(with_syn.irr - without.irr, 4),
    )


if __name__ == "__main__":
    from buyout_toolkit.deal_pipeline import generate_pipeline, rank_pipeline

    top = rank_pipeline(generate_pipeline())[0]
    comparison = compare_with_without_synergies(top)

    print(f"Add-on synergy case for {comparison.company_name} onto {comparison.platform_name}\n")
    print(f"Run-rate annual synergy EBITDA (Year 3+): ${comparison.run_rate_annual_synergy_ebitda:,.0f}\n")
    print(f"Without synergies -> MOIC: {comparison.without_synergies.moic:.2f}x  IRR: {comparison.without_synergies.irr:.1%}")
    print(f"With synergies    -> MOIC: {comparison.with_synergies.moic:.2f}x  IRR: {comparison.with_synergies.irr:.1%}")
    print(f"Delta             -> MOIC: {comparison.delta_moic:+.2f}x  IRR: {comparison.delta_irr:+.1%}")
