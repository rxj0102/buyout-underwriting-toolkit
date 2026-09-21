"""diligence_tracker.py

A structured due diligence tracker spanning the four workstreams typical
of a lower-middle-market buyout: Financial, Legal, Operational, and
Commercial. Each checklist item carries an owner, a status, and a risk
flag. ``compute_readiness`` rolls the checklist up into overall deal
readiness and a list of outstanding red flags for the investment
committee.

Checklist content and statuses are SYNTHETIC / illustrative and generated
with a seeded random number generator for reproducibility.
"""

from __future__ import annotations

import random
import zlib
from dataclasses import dataclass
from typing import Dict, List, Optional

from buyout_toolkit.deal_pipeline import Target

WORKSTREAMS = ["Financial", "Legal", "Operational", "Commercial"]

STATUSES = ["Not Started", "In Progress", "Complete", "Flagged"]
RISK_LEVELS = ["None", "Low", "Medium", "High"]

OWNER_POOL: Dict[str, List[str]] = {
    "Financial": ["Associate - Financial DD", "VP - Finance", "QoE Advisor (external)"],
    "Legal": ["Outside Counsel - M&A", "General Counsel", "Associate - Legal DD"],
    "Operational": ["Operating Partner", "VP - Operations", "Associate - Operational DD"],
    "Commercial": ["Principal - Commercial DD", "Associate - Commercial DD", "Commercial Advisor (external)"],
}

CHECKLIST_TEMPLATE: Dict[str, List[str]] = {
    "Financial": [
        "Quality of earnings (QoE) review",
        "Revenue recognition testing",
        "Net working capital analysis & peg calculation",
        "Customer revenue concentration analysis",
        "Historical financial statement review (3-yr)",
        "Tax compliance and exposure review",
        "EBITDA add-back / normalization review",
        "Monthly financial reporting & systems review",
    ],
    "Legal": [
        "Corporate structure and cap table review",
        "Material contracts review",
        "Litigation and dispute history search",
        "Intellectual property / trademark ownership review",
        "Licensing and regulatory permits review",
        "Employment agreements and non-compete review",
        "Real estate lease review",
        "Environmental liability review",
    ],
    "Operational": [
        "Management team capability assessment",
        "IT systems and field-service software review",
        "Fleet and equipment condition assessment",
        "Safety and compliance (OSHA) review",
        "Insurance coverage adequacy review",
        "Key employee / technician retention risk review",
        "Supply chain and vendor concentration review",
    ],
    "Commercial": [
        "Customer reference calls",
        "Market and competitive positioning analysis",
        "Pricing strategy and discounting analysis",
        "Customer contract terms and renewal review",
        "Sales pipeline and backlog review",
        "Brand and online reputation review",
        "Growth strategy and TAM validation",
    ],
}


@dataclass
class ChecklistItem:
    item_id: str
    workstream: str
    description: str
    owner: str
    status: str
    risk_flag: str
    notes: str


def generate_diligence_checklist(target: Target, seed: int = 100) -> List[ChecklistItem]:
    """Generate a synthetic due diligence checklist (20-30 items across
    the four workstreams) for the given target.
    """
    target_hash = zlib.crc32(target.target_id.encode("utf-8"))
    rng = random.Random(seed + target_hash % 10_000)
    items: List[ChecklistItem] = []
    counter = 1

    status_weights = [15, 30, 45, 10]  # Not Started, In Progress, Complete, Flagged

    for workstream, descriptions in CHECKLIST_TEMPLATE.items():
        for description in descriptions:
            status = rng.choices(STATUSES, weights=status_weights, k=1)[0]

            if status == "Flagged":
                risk_flag = rng.choices(["Medium", "High"], weights=[60, 40], k=1)[0]
            elif status == "Complete":
                risk_flag = rng.choices(RISK_LEVELS, weights=[70, 20, 8, 2], k=1)[0]
            else:
                risk_flag = rng.choices(RISK_LEVELS, weights=[50, 25, 20, 5], k=1)[0]

            owner = rng.choice(OWNER_POOL[workstream])
            notes = _default_note(status, risk_flag)

            items.append(
                ChecklistItem(
                    item_id=f"DD-{counter:03d}",
                    workstream=workstream,
                    description=description,
                    owner=owner,
                    status=status,
                    risk_flag=risk_flag,
                    notes=notes,
                )
            )
            counter += 1

    return items


def _default_note(status: str, risk_flag: str) -> str:
    if status == "Flagged":
        return f"Escalated to deal team - {risk_flag.lower()} risk pending resolution."
    if status == "Complete" and risk_flag in ("Medium", "High"):
        return f"Reviewed; residual {risk_flag.lower()} risk noted for IC memo."
    if status == "Complete":
        return "Reviewed; no material issues identified."
    if status == "In Progress":
        return "Workstream underway; findings pending."
    return "Not yet started."


@dataclass
class DiligenceRollup:
    total_items: int
    completion_pct: float
    status_counts: Dict[str, int]
    workstream_completion_pct: Dict[str, float]
    outstanding_red_flags: List[ChecklistItem]
    outstanding_medium_flags: List[ChecklistItem]
    readiness_verdict: str


def compute_readiness(items: List[ChecklistItem]) -> DiligenceRollup:
    """Roll up the checklist into overall completion, outstanding risk
    flags, and a deal-readiness verdict for the investment committee.

    An item is considered "outstanding" if its risk flag is Medium or
    High AND it has not been marked Complete (i.e. the risk has not been
    formally closed out, even if reviewed).
    """
    total = len(items)
    status_counts = {status: 0 for status in STATUSES}
    for item in items:
        status_counts[item.status] += 1

    complete = status_counts["Complete"]
    completion_pct = round(complete / total * 100.0, 1) if total else 0.0

    workstream_completion: Dict[str, float] = {}
    for workstream in WORKSTREAMS:
        ws_items = [i for i in items if i.workstream == workstream]
        ws_complete = sum(1 for i in ws_items if i.status == "Complete")
        workstream_completion[workstream] = (
            round(ws_complete / len(ws_items) * 100.0, 1) if ws_items else 0.0
        )

    outstanding_red_flags = [
        i for i in items if i.risk_flag == "High" and i.status != "Complete"
    ]
    outstanding_medium_flags = [
        i for i in items if i.risk_flag == "Medium" and i.status != "Complete"
    ]

    if outstanding_red_flags:
        verdict = "Not Ready - Critical Red Flags Outstanding"
    elif completion_pct < 80.0:
        verdict = "In Progress - Not Yet Ready for IC"
    elif outstanding_medium_flags:
        verdict = "Ready with Conditions"
    else:
        verdict = "Ready for Investment Committee"

    return DiligenceRollup(
        total_items=total,
        completion_pct=completion_pct,
        status_counts=status_counts,
        workstream_completion_pct=workstream_completion,
        outstanding_red_flags=outstanding_red_flags,
        outstanding_medium_flags=outstanding_medium_flags,
        readiness_verdict=verdict,
    )


if __name__ == "__main__":
    from buyout_toolkit.deal_pipeline import generate_pipeline, rank_pipeline

    top = rank_pipeline(generate_pipeline())[0]
    checklist = generate_diligence_checklist(top)
    rollup = compute_readiness(checklist)

    print(f"Diligence tracker for {top.company_name} ({top.target_id})")
    print(f"Items: {rollup.total_items}  Completion: {rollup.completion_pct}%")
    print(f"Status counts: {rollup.status_counts}")
    print(f"By workstream: {rollup.workstream_completion_pct}")
    print(f"Outstanding HIGH risk flags: {len(rollup.outstanding_red_flags)}")
    for f in rollup.outstanding_red_flags:
        print(f"  - [{f.item_id}] {f.description} ({f.workstream}, owner: {f.owner})")
    print(f"Readiness verdict: {rollup.readiness_verdict}")
