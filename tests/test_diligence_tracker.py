import pytest

from buyout_toolkit.deal_pipeline import Target
from buyout_toolkit.diligence_tracker import (
    WORKSTREAMS,
    ChecklistItem,
    compute_readiness,
    generate_diligence_checklist,
)


def make_target(**overrides) -> Target:
    defaults = dict(
        target_id="T-DIL",
        company_name="Diligence Test Co LLC",
        sub_sector="Commercial Landscaping & Grounds Maintenance",
        geography="GA",
        years_in_business=18,
        revenue=11_000_000.0,
        ebitda_margin=0.13,
        revenue_growth_rate=0.05,
        recurring_revenue_pct=0.30,
        customer_concentration_pct=0.20,
        number_of_locations=2,
        owner_age=64,
        succession_situation="Retirement - Family Successor Declined",
        outreach_status="Initial Outreach",
        net_debt=600_000.0,
    )
    defaults.update(overrides)
    return Target(**defaults)


def _item(item_id, workstream="Financial", status="Complete", risk_flag="None"):
    return ChecklistItem(
        item_id=item_id,
        workstream=workstream,
        description="Test item",
        owner="Test Owner",
        status=status,
        risk_flag=risk_flag,
        notes="",
    )


def test_generate_checklist_size_is_in_expected_range():
    target = make_target()
    checklist = generate_diligence_checklist(target)
    assert 20 <= len(checklist) <= 30


def test_generate_checklist_covers_all_four_workstreams():
    target = make_target()
    checklist = generate_diligence_checklist(target)
    observed = {item.workstream for item in checklist}
    assert observed == set(WORKSTREAMS)


def test_readiness_completion_pct_matches_manual_count():
    items = [
        _item("1", status="Complete"),
        _item("2", status="Complete"),
        _item("3", status="In Progress"),
        _item("4", status="Not Started"),
    ]
    rollup = compute_readiness(items)
    assert rollup.total_items == 4
    assert rollup.completion_pct == pytest.approx(50.0)


def test_outstanding_red_flags_excludes_completed_high_risk_items():
    items = [
        _item("1", status="Flagged", risk_flag="High"),
        _item("2", status="Complete", risk_flag="High"),  # closed out, not outstanding
        _item("3", status="In Progress", risk_flag="Low"),
    ]
    rollup = compute_readiness(items)
    ids = {i.item_id for i in rollup.outstanding_red_flags}
    assert ids == {"1"}


def test_readiness_verdict_blocks_on_outstanding_high_risk_flags():
    items = [_item(str(i), status="Complete") for i in range(10)]
    items.append(_item("11", status="Flagged", risk_flag="High"))
    rollup = compute_readiness(items)
    assert rollup.readiness_verdict == "Not Ready - Critical Red Flags Outstanding"


def test_readiness_verdict_ready_for_ic_when_complete_and_clean():
    items = [_item(str(i), status="Complete", risk_flag="None") for i in range(10)]
    rollup = compute_readiness(items)
    assert rollup.readiness_verdict == "Ready for Investment Committee"
    assert rollup.completion_pct == pytest.approx(100.0)


def test_readiness_verdict_ready_with_conditions_for_outstanding_medium_flags():
    items = [_item(str(i), status="Complete", risk_flag="None") for i in range(9)]
    items.append(_item("10", status="In Progress", risk_flag="Medium"))
    rollup = compute_readiness(items)
    assert rollup.readiness_verdict == "Ready with Conditions"


