import pytest

from buyout_toolkit.deal_pipeline import (
    DEFAULT_WEIGHTS,
    SUB_SECTORS,
    Target,
    compute_priority_score,
    generate_pipeline,
    rank_pipeline,
    score_financial_quality,
    score_sourcing_feasibility,
    score_strategic_fit,
)


def make_target(**overrides) -> Target:
    defaults = dict(
        target_id="T-TEST",
        company_name="Test Co LLC",
        sub_sector="Residential HVAC Services",
        geography="TX",
        years_in_business=15,
        revenue=15_000_000.0,
        ebitda_margin=0.18,
        revenue_growth_rate=0.08,
        recurring_revenue_pct=0.4,
        customer_concentration_pct=0.10,
        number_of_locations=3,
        owner_age=60,
        succession_situation="Retirement - No Successor Identified",
        outreach_status="Initial Outreach",
        net_debt=1_000_000.0,
    )
    defaults.update(overrides)
    return Target(**defaults)


def test_generate_pipeline_default_count_in_expected_range():
    pipeline = generate_pipeline()
    assert 40 <= len(pipeline) <= 60


def test_generate_pipeline_covers_multiple_sub_sectors():
    pipeline = generate_pipeline(n=50, seed=3)
    observed = {t.sub_sector for t in pipeline}
    assert observed.issubset(set(SUB_SECTORS.keys()))
    assert len(observed) >= 3


def test_scores_are_bounded_between_0_and_100():
    pipeline = generate_pipeline(n=50, seed=11)
    for target in pipeline:
        assert 0.0 <= score_strategic_fit(target) <= 100.0
        assert 0.0 <= score_financial_quality(target) <= 100.0
        assert 0.0 <= score_sourcing_feasibility(target) <= 100.0


def test_higher_succession_urgency_increases_sourcing_feasibility():
    urgent = make_target(succession_situation="Retirement - No Successor Identified")
    patient = make_target(succession_situation="Retirement - Family Succession Planned")
    assert score_sourcing_feasibility(urgent) > score_sourcing_feasibility(patient)


def test_compute_priority_score_matches_manual_weighted_average():
    target = make_target()
    priority = compute_priority_score(target)

    strategic = score_strategic_fit(target)
    financial = score_financial_quality(target)
    sourcing = score_sourcing_feasibility(target)
    total_weight = sum(DEFAULT_WEIGHTS.values())
    expected = round(
        (
            strategic * DEFAULT_WEIGHTS["strategic_fit"]
            + financial * DEFAULT_WEIGHTS["financial_quality"]
            + sourcing * DEFAULT_WEIGHTS["sourcing_feasibility"]
        )
        / total_weight,
        2,
    )
    assert priority == pytest.approx(expected)
    assert target.priority_score == pytest.approx(expected)


def test_rank_pipeline_sorts_descending_and_assigns_ranks():
    pipeline = generate_pipeline(n=30, seed=5)
    ranked = rank_pipeline(pipeline)

    scores = [t.priority_score for t in ranked]
    assert scores == sorted(scores, reverse=True)
    assert [t.priority_rank for t in ranked] == list(range(1, len(ranked) + 1))
