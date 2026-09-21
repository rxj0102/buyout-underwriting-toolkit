"""investment_memo.py

Assembles a structured Investment Committee (IC) memo for a single
acquisition target by pulling every figure directly from the other
modules in this package: deal_pipeline (thesis/scoring), valuation_model
(valuation), lbo_model (returns), addon_synergy_model (synergy case), and
diligence_tracker (diligence status). No figures are re-derived or
hard-coded here.

The memo is SYNTHETIC and for demonstration purposes only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from buyout_toolkit.addon_synergy_model import (
    PlatformCo,
    SynergyComparison,
    build_platform_co,
    compare_with_without_synergies,
)
from buyout_toolkit.deal_pipeline import (
    Target,
    compute_priority_score,
    generate_pipeline,
    rank_pipeline,
)
from buyout_toolkit.diligence_tracker import (
    ChecklistItem,
    DiligenceRollup,
    compute_readiness,
    generate_diligence_checklist,
)
from buyout_toolkit.lbo_model import LboResult, default_assumptions, run_all_cases
from buyout_toolkit.valuation_model import ValuationResult, value_target

IRR_HURDLE = 0.20
MOIC_HURDLE = 2.5


@dataclass
class InvestmentMemo:
    target: Target
    thesis: str
    financial_profile: Dict[str, object]
    valuation: ValuationResult
    lbo_cases: Dict[str, LboResult]
    synergy_comparison: SynergyComparison
    diligence_rollup: DiligenceRollup
    key_risks: List[str]
    recommendation: str
    recommendation_rationale: str


def _build_thesis(target: Target) -> str:
    return (
        f"{target.company_name} is a {target.years_in_business}-year-old "
        f"{target.sub_sector.lower()} operator based in {target.geography} generating "
        f"${target.revenue:,.0f} of revenue at a {target.ebitda_margin:.1%} EBITDA margin. "
        f"The company scores {target.priority_score}/100 on the platform's proprietary "
        "prioritization framework, reflecting strong strategic fit with the firm's "
        "buy-and-build thesis in durable, essential-services trades, solid underlying "
        "financial quality, and a favorable near-term sourcing/succession dynamic "
        f"(\"{target.succession_situation}\"). The proposed transaction would be executed "
        "as a bolt-on acquisition to the firm's existing regional platform, unlocking cross-sell, "
        "overhead consolidation, and purchasing-scale synergies on top of standalone returns."
    )


def _build_financial_profile(target: Target) -> Dict[str, object]:
    return {
        "revenue": target.revenue,
        "ebitda": target.ebitda,
        "ebitda_margin": target.ebitda_margin,
        "revenue_growth_rate": target.revenue_growth_rate,
        "recurring_revenue_pct": target.recurring_revenue_pct,
        "customer_concentration_pct": target.customer_concentration_pct,
        "number_of_locations": target.number_of_locations,
        "net_debt": target.net_debt,
        "priority_score": target.priority_score,
        "score_breakdown": dict(target.scores),
    }


def _identify_key_risks(target: Target, diligence_rollup: DiligenceRollup) -> List[str]:
    risks: List[str] = []

    if target.customer_concentration_pct > 0.25:
        risks.append(
            f"Customer concentration risk: top customers represent "
            f"{target.customer_concentration_pct:.1%} of revenue."
        )
    if target.recurring_revenue_pct < 0.30:
        risks.append(
            f"Limited recurring revenue base ({target.recurring_revenue_pct:.1%} of revenue), "
            "increasing sensitivity to demand cyclicality."
        )
    if target.revenue_growth_rate < 0.0:
        risks.append(
            f"Recent revenue decline ({target.revenue_growth_rate:.1%} growth), requiring "
            "diligence on the root cause before underwriting a recovery."
        )
    if "No Successor" in target.succession_situation or "Burnout" in target.succession_situation:
        risks.append(
            "Key-person / owner-dependency risk given the seller's succession situation "
            f"(\"{target.succession_situation}\"); a transition services agreement is recommended."
        )

    for item in diligence_rollup.outstanding_red_flags:
        risks.append(f"[{item.workstream}] {item.description} - unresolved HIGH risk flag ({item.item_id}).")
    for item in diligence_rollup.outstanding_medium_flags:
        risks.append(f"[{item.workstream}] {item.description} - unresolved MEDIUM risk flag ({item.item_id}).")

    if not risks:
        risks.append("No material red or medium risk flags identified to date.")

    return risks


def _recommend(
    lbo_cases: Dict[str, LboResult],
    diligence_rollup: DiligenceRollup,
) -> (str, str):
    base = lbo_cases["base"]
    downside = lbo_cases["downside"]

    meets_return_hurdles = base.irr >= IRR_HURDLE and base.moic >= MOIC_HURDLE
    downside_acceptable = downside.irr >= 0.0

    if diligence_rollup.outstanding_red_flags:
        return (
            "Do Not Proceed - Pending Red Flag Resolution",
            "One or more unresolved HIGH risk diligence flags must be cleared before this "
            "deal can be brought back to the Investment Committee.",
        )

    if meets_return_hurdles and downside_acceptable and diligence_rollup.completion_pct >= 80.0:
        return (
            "Recommend Proceeding to LOI / Final IC Approval",
            f"Base case underwrites to a {base.irr:.1%} IRR / {base.moic:.2f}x MOIC, above the "
            f"{IRR_HURDLE:.0%} IRR and {MOIC_HURDLE:.1f}x MOIC hurdles, with a downside case that "
            "remains capital-protective and diligence substantially complete.",
        )

    if meets_return_hurdles and diligence_rollup.completion_pct < 80.0:
        return (
            "Conditional Approval - Complete Diligence Before Signing",
            f"Returns underwrite above hurdle ({base.irr:.1%} IRR / {base.moic:.2f}x MOIC) but "
            f"diligence is only {diligence_rollup.completion_pct}% complete; recommend advancing "
            "to LOI in parallel with completing outstanding workstreams.",
        )

    return (
        "Do Not Proceed at Current Terms",
        f"Base case returns ({base.irr:.1%} IRR / {base.moic:.2f}x MOIC) do not clear the firm's "
        f"{IRR_HURDLE:.0%} IRR / {MOIC_HURDLE:.1f}x MOIC underwriting hurdles; recommend "
        "re-trading price/structure or passing.",
    )


def build_investment_memo(
    target: Target,
    platform: Optional[PlatformCo] = None,
    diligence_seed: int = 100,
) -> InvestmentMemo:
    """Build the full IC memo for ``target``, pulling every figure from
    the pipeline, valuation, LBO, synergy, and diligence modules.
    """
    if target.priority_score is None:
        compute_priority_score(target)

    valuation = value_target(target)
    lbo_cases = run_all_cases(target, base_assumptions=default_assumptions(target))
    synergy_comparison = compare_with_without_synergies(
        target, platform=platform, lbo_result=lbo_cases["base"]
    )
    checklist = generate_diligence_checklist(target, seed=diligence_seed)
    diligence_rollup = compute_readiness(checklist)

    thesis = _build_thesis(target)
    financial_profile = _build_financial_profile(target)
    key_risks = _identify_key_risks(target, diligence_rollup)
    recommendation, rationale = _recommend(lbo_cases, diligence_rollup)

    return InvestmentMemo(
        target=target,
        thesis=thesis,
        financial_profile=financial_profile,
        valuation=valuation,
        lbo_cases=lbo_cases,
        synergy_comparison=synergy_comparison,
        diligence_rollup=diligence_rollup,
        key_risks=key_risks,
        recommendation=recommendation,
        recommendation_rationale=rationale,
    )


def render_memo_markdown(memo: InvestmentMemo) -> str:
    """Render the memo as a Markdown document."""
    t = memo.target
    v = memo.valuation
    base = memo.lbo_cases["base"]
    upside = memo.lbo_cases["upside"]
    downside = memo.lbo_cases["downside"]
    su = base.sources_uses
    sc = memo.synergy_comparison
    dr = memo.diligence_rollup

    lines: List[str] = []
    lines.append(f"# Investment Committee Memo: {t.company_name}")
    lines.append(f"**Target ID:** {t.target_id}  |  **Sub-sector:** {t.sub_sector}  |  **Geography:** {t.geography}")
    lines.append("")
    lines.append("## 1. Investment Thesis")
    lines.append(memo.thesis)
    lines.append("")
    lines.append("## 2. Financial Profile")
    lines.append(f"- Revenue: ${t.revenue:,.0f}")
    lines.append(f"- EBITDA: ${t.ebitda:,.0f} ({t.ebitda_margin:.1%} margin)")
    lines.append(f"- Revenue growth rate: {t.revenue_growth_rate:.1%}")
    lines.append(f"- Recurring revenue: {t.recurring_revenue_pct:.1%} of revenue")
    lines.append(f"- Customer concentration: {t.customer_concentration_pct:.1%}")
    lines.append(f"- Locations: {t.number_of_locations}")
    lines.append(f"- Net debt: ${t.net_debt:,.0f}")
    lines.append(f"- Priority score: {t.priority_score}/100 {t.scores}")
    lines.append("")
    lines.append("## 3. Valuation Summary")
    lines.append(f"- EBITDA-multiple EV range: ${v.multiple_ev['low']:,.0f} - ${v.multiple_ev['high']:,.0f}")
    lines.append(f"- DCF-implied EV: ${v.dcf_ev:,.0f}")
    lines.append(
        f"- Blended EV range: ${v.blended_ev_low:,.0f} (low) / ${v.blended_ev_base:,.0f} (base) / "
        f"${v.blended_ev_high:,.0f} (high)"
    )
    lines.append(
        f"- Implied equity value range: ${v.equity_value_low:,.0f} - ${v.equity_value_base:,.0f} - "
        f"${v.equity_value_high:,.0f}"
    )
    lines.append("")
    lines.append("## 4. Proposed Offer Terms & Structure")
    lines.append(f"- Purchase enterprise value (base case, {base.assumptions.entry_multiple:.1f}x EBITDA): ${su.purchase_enterprise_value:,.0f}")
    lines.append(f"- Transaction fees: ${su.transaction_fees:,.0f}")
    lines.append(f"- Total uses: ${su.total_uses:,.0f}")
    lines.append(f"- Senior debt: ${su.senior_debt:,.0f}")
    lines.append(f"- Seller note: ${su.seller_note:,.0f}")
    lines.append(f"- Sponsor equity check: ${su.sponsor_equity:,.0f}")
    lines.append(f"- Sources & uses balanced: {su.is_balanced}")
    lines.append("")
    lines.append("### Standalone Returns by Case")
    lines.append("| Case | MOIC | IRR |")
    lines.append("|---|---|---|")
    lines.append(f"| Downside | {downside.moic:.2f}x | {downside.irr:.1%} |")
    lines.append(f"| Base | {base.moic:.2f}x | {base.irr:.1%} |")
    lines.append(f"| Upside | {upside.moic:.2f}x | {upside.irr:.1%} |")
    lines.append("")
    lines.append("### Add-On Synergy Case")
    lines.append(f"- Platform: {sc.platform_name}")
    lines.append(f"- Run-rate annual synergy EBITDA: ${sc.run_rate_annual_synergy_ebitda:,.0f}")
    lines.append(
        f"- Combined platform MOIC/IRR without synergies: {sc.without_synergies.moic:.2f}x / "
        f"{sc.without_synergies.irr:.1%}"
    )
    lines.append(
        f"- Combined platform MOIC/IRR with synergies: {sc.with_synergies.moic:.2f}x / "
        f"{sc.with_synergies.irr:.1%}"
    )
    lines.append(f"- Delta from synergies: {sc.delta_moic:+.2f}x MOIC / {sc.delta_irr:+.1%} IRR")
    lines.append("")
    lines.append("## 5. Key Risks")
    for risk in memo.key_risks:
        lines.append(f"- {risk}")
    lines.append("")
    lines.append("## 6. Diligence Status")
    lines.append(f"- Overall completion: {dr.completion_pct}% ({dr.total_items} items)")
    lines.append(f"- Status counts: {dr.status_counts}")
    lines.append(f"- Workstream completion: {dr.workstream_completion_pct}")
    lines.append(f"- Outstanding HIGH risk flags: {len(dr.outstanding_red_flags)}")
    lines.append(f"- Outstanding MEDIUM risk flags: {len(dr.outstanding_medium_flags)}")
    lines.append(f"- Readiness verdict: **{dr.readiness_verdict}**")
    lines.append("")
    lines.append("## 7. Recommendation")
    lines.append(f"**{memo.recommendation}**")
    lines.append("")
    lines.append(memo.recommendation_rationale)
    lines.append("")
    lines.append("---")
    lines.append("*All figures above are synthetic and generated for demonstration purposes only.*")

    return "\n".join(lines)


if __name__ == "__main__":
    ranked = rank_pipeline(generate_pipeline())
    top = ranked[0]
    memo = build_investment_memo(top)
    print(render_memo_markdown(memo))
