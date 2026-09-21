"""deal_pipeline.py

Generates and prioritizes a synthetic acquisition pipeline for a
buy-and-build private equity platform targeting durable, essential-services
businesses (residential HVAC, pest & termite control, commercial
landscaping, and plumbing/drain services).

All targets, names, and financials are SYNTHETIC DATA generated with a
seeded random number generator so results are reproducible. They are not
drawn from or intended to represent any real company.

The module exposes:
    - ``generate_pipeline`` to build a list of ``Target`` records
    - ``score_strategic_fit`` / ``score_financial_quality`` /
      ``score_sourcing_feasibility`` for the three scoring pillars
    - ``compute_priority_score`` to combine the pillars into one score
    - ``rank_pipeline`` to sort and rank the full pipeline
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

# Target sub-sectors for the roll-up platform. Each carries a base
# "strategic fit" weight reflecting how central that trade is to the
# platform's stated thesis (e.g. HVAC and plumbing are core/adjacent
# residential trades with strong cross-sell potential; landscaping is more
# peripheral).
SUB_SECTORS: Dict[str, Dict[str, float]] = {
    "Residential HVAC Services": {"base_fit": 92.0, "margin_floor": 0.12, "margin_ceiling": 0.24},
    "Plumbing & Drain Services": {"base_fit": 85.0, "margin_floor": 0.11, "margin_ceiling": 0.22},
    "Pest & Termite Control": {"base_fit": 74.0, "margin_floor": 0.15, "margin_ceiling": 0.28},
    "Commercial Landscaping & Grounds Maintenance": {"base_fit": 60.0, "margin_floor": 0.08, "margin_ceiling": 0.18},
}

# States where the platform already has a footprint (density bonus).
PLATFORM_FOOTPRINT_STATES = {"TX", "FL", "GA", "NC", "AZ", "TN"}

ALL_STATES = sorted(
    PLATFORM_FOOTPRINT_STATES
    | {"OH", "PA", "IL", "IN", "SC", "AL", "MO", "VA", "CO", "OK", "KY", "NM"}
)

SUCCESSION_SITUATIONS: Dict[str, float] = {
    # situation -> base urgency score (0-100); higher = more likely to
    # transact soon, used as a proxy for near-term deal likelihood.
    "Retirement - No Successor Identified": 95.0,
    "Health or Burnout Driven Exit": 90.0,
    "Retirement - Family Successor Declined": 80.0,
    "Open to Partnership / Growth Capital": 55.0,
    "Second-Generation Owner - Growth Mode": 30.0,
    "Retirement - Family Succession Planned": 15.0,
}

OUTREACH_STATUSES: List[str] = [
    "Not Contacted",
    "Initial Outreach",
    "NDA Signed",
    "Management Meeting",
    "LOI Submitted",
    "Declined",
    "Passed",
]

# Progress credit for each outreach stage, used in sourcing feasibility.
# "Declined" and "Passed" are terminal / negative states.
OUTREACH_PROGRESS: Dict[str, float] = {
    "Not Contacted": 0.0,
    "Initial Outreach": 20.0,
    "NDA Signed": 45.0,
    "Management Meeting": 70.0,
    "LOI Submitted": 90.0,
    "Declined": -30.0,
    "Passed": -50.0,
}

_NAME_PREFIXES = [
    "Summit", "Coastal", "Apex", "Blue Ridge", "Lonestar", "Ironclad", "Redwood",
    "Highland", "Gulf Coast", "Pioneer", "Granite", "Cedar Point", "Silver Oak",
    "Meridian", "Frontline", "Homestead", "Carolina", "Desert Sky", "Riverside",
    "Anchor", "Crossroads", "Bluebonnet", "Heritage", "Palmetto", "Copper Creek",
]

_NAME_SUFFIXES = {
    "Residential HVAC Services": ["Heating & Air", "Comfort Systems", "HVAC Solutions", "Climate Control"],
    "Plumbing & Drain Services": ["Plumbing Co.", "Drain & Rooter", "Plumbing Services", "Pipeworks"],
    "Pest & Termite Control": ["Pest Solutions", "Pest & Termite", "Exterminating", "Pest Control"],
    "Commercial Landscaping & Grounds Maintenance": ["Landscaping", "Grounds Management", "Turf & Tree", "Outdoor Services"],
}

_ENTITY_SUFFIXES = ["LLC", "Inc.", "Group", "Co."]


@dataclass
class Target:
    """A single acquisition target (synthetic)."""

    target_id: str
    company_name: str
    sub_sector: str
    geography: str
    years_in_business: int
    revenue: float
    ebitda_margin: float
    revenue_growth_rate: float
    recurring_revenue_pct: float
    customer_concentration_pct: float
    number_of_locations: int
    owner_age: int
    succession_situation: str
    outreach_status: str
    net_debt: float
    scores: Dict[str, float] = field(default_factory=dict)
    priority_score: Optional[float] = None
    priority_rank: Optional[int] = None

    @property
    def ebitda(self) -> float:
        return round(self.revenue * self.ebitda_margin, 2)


def _random_company_name(rng: random.Random, sub_sector: str) -> str:
    prefix = rng.choice(_NAME_PREFIXES)
    suffix = rng.choice(_NAME_SUFFIXES[sub_sector])
    entity = rng.choice(_ENTITY_SUFFIXES)
    return f"{prefix} {suffix} {entity}"


def generate_pipeline(n: int = 50, seed: int = 42) -> List[Target]:
    """Generate a synthetic pipeline of ``n`` acquisition targets.

    ``n`` should fall within the 40-60 range used across this project's
    documentation and tests, but any positive integer is accepted.
    """
    if n <= 0:
        raise ValueError("n must be a positive integer")

    rng = random.Random(seed)
    sub_sector_names = list(SUB_SECTORS.keys())
    succession_keys = list(SUCCESSION_SITUATIONS.keys())
    targets: List[Target] = []

    for i in range(n):
        sub_sector = rng.choice(sub_sector_names)
        meta = SUB_SECTORS[sub_sector]

        revenue = round(rng.uniform(4_000_000, 42_000_000), -3)
        ebitda_margin = round(rng.uniform(meta["margin_floor"], meta["margin_ceiling"]), 4)
        revenue_growth_rate = round(rng.uniform(-0.03, 0.22), 4)
        recurring_revenue_pct = round(rng.uniform(0.10, 0.75), 4)
        customer_concentration_pct = round(rng.uniform(0.02, 0.55), 4)
        number_of_locations = rng.randint(1, 9)
        owner_age = rng.randint(38, 78)
        years_in_business = rng.randint(5, 55)
        geography = rng.choice(ALL_STATES)

        # Older owners skew toward higher-urgency succession situations.
        if owner_age >= 65:
            situation_pool = succession_keys[:4]
        elif owner_age >= 55:
            situation_pool = succession_keys[:5]
        else:
            situation_pool = succession_keys
        succession_situation = rng.choice(situation_pool)

        outreach_status = rng.choices(
            OUTREACH_STATUSES,
            weights=[35, 25, 15, 10, 5, 5, 5],
            k=1,
        )[0]

        net_debt = round(rng.uniform(-500_000, revenue * ebitda_margin * 1.5), 2)

        target = Target(
            target_id=f"T-{i + 1:03d}",
            company_name=_random_company_name(rng, sub_sector),
            sub_sector=sub_sector,
            geography=geography,
            years_in_business=years_in_business,
            revenue=revenue,
            ebitda_margin=ebitda_margin,
            revenue_growth_rate=revenue_growth_rate,
            recurring_revenue_pct=recurring_revenue_pct,
            customer_concentration_pct=customer_concentration_pct,
            number_of_locations=number_of_locations,
            owner_age=owner_age,
            succession_situation=succession_situation,
            outreach_status=outreach_status,
            net_debt=net_debt,
        )
        targets.append(target)

    return targets


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score_strategic_fit(target: Target) -> float:
    """Score (0-100) how well the target fits the roll-up thesis: core
    trade adjacency, recurring-revenue/cross-sell potential, footprint
    density, and multi-location scalability.
    """
    base_fit = SUB_SECTORS[target.sub_sector]["base_fit"]

    recurring_bonus = target.recurring_revenue_pct * 20.0  # up to +20
    footprint_bonus = 8.0 if target.geography in PLATFORM_FOOTPRINT_STATES else -4.0
    density_bonus = min(target.number_of_locations, 6) * 1.5  # up to +9

    score = base_fit * 0.7 + recurring_bonus + footprint_bonus + density_bonus
    return round(_clamp(score), 2)


def score_financial_quality(target: Target) -> float:
    """Score (0-100) the target's underlying financial quality: margin
    level, growth, customer concentration risk, and a "sweet spot" revenue
    size typical of a fundable bolt-on ($8M-$25M).
    """
    margin_score = _clamp(target.ebitda_margin / 0.28 * 100.0)
    growth_score = _clamp((target.revenue_growth_rate + 0.03) / 0.25 * 100.0)
    concentration_score = _clamp(100.0 - target.customer_concentration_pct * 150.0)

    if 8_000_000 <= target.revenue <= 25_000_000:
        size_score = 100.0
    elif target.revenue < 8_000_000:
        size_score = _clamp(100.0 - (8_000_000 - target.revenue) / 8_000_000 * 60.0)
    else:
        size_score = _clamp(100.0 - (target.revenue - 25_000_000) / 25_000_000 * 60.0)

    score = (
        margin_score * 0.35
        + growth_score * 0.25
        + concentration_score * 0.20
        + size_score * 0.20
    )
    return round(_clamp(score), 2)


def score_sourcing_feasibility(target: Target) -> float:
    """Score (0-100) the near-term likelihood of getting a deal done:
    owner succession urgency (a proxy for willingness to transact) and how
    far outreach has already progressed.
    """
    urgency_score = SUCCESSION_SITUATIONS[target.succession_situation]
    age_bonus = _clamp((target.owner_age - 45) / 30 * 15.0, low=0.0, high=15.0)
    progress_score = _clamp(50.0 + OUTREACH_PROGRESS[target.outreach_status])

    score = urgency_score * 0.55 + progress_score * 0.30 + age_bonus * 0.15
    return round(_clamp(score), 2)


DEFAULT_WEIGHTS: Dict[str, float] = {
    "strategic_fit": 0.35,
    "financial_quality": 0.40,
    "sourcing_feasibility": 0.25,
}


def compute_priority_score(target: Target, weights: Optional[Dict[str, float]] = None) -> float:
    """Combine the three scoring pillars into a single 0-100 priority
    score using weighted average. Also stores the component scores on the
    target's ``scores`` dict as a side effect for downstream inspection.
    """
    weights = weights or DEFAULT_WEIGHTS
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("weights must sum to a positive number")

    strategic = score_strategic_fit(target)
    financial = score_financial_quality(target)
    sourcing = score_sourcing_feasibility(target)

    target.scores = {
        "strategic_fit": strategic,
        "financial_quality": financial,
        "sourcing_feasibility": sourcing,
    }

    weighted_sum = (
        strategic * weights.get("strategic_fit", 0.0)
        + financial * weights.get("financial_quality", 0.0)
        + sourcing * weights.get("sourcing_feasibility", 0.0)
    )
    priority = round(weighted_sum / total_weight, 2)
    target.priority_score = priority
    return priority


def rank_pipeline(
    targets: List[Target], weights: Optional[Dict[str, float]] = None
) -> List[Target]:
    """Score every target and return a new list sorted by descending
    priority score, with ``priority_rank`` (1 = highest priority) set on
    each target.
    """
    for target in targets:
        compute_priority_score(target, weights=weights)

    ranked = sorted(targets, key=lambda t: t.priority_score, reverse=True)
    for idx, target in enumerate(ranked, start=1):
        target.priority_rank = idx
    return ranked


if __name__ == "__main__":
    pipeline = generate_pipeline()
    ranked = rank_pipeline(pipeline)
    print(f"Generated {len(ranked)} synthetic targets across {len(SUB_SECTORS)} sub-sectors.\n")
    print(f"{'Rank':<5}{'ID':<8}{'Company':<34}{'Sub-sector':<32}{'Score':<8}{'Outreach'}")
    for t in ranked[:15]:
        print(
            f"{t.priority_rank:<5}{t.target_id:<8}{t.company_name:<34}"
            f"{t.sub_sector:<32}{t.priority_score:<8}{t.outreach_status}"
        )
