from buyout_toolkit.deal_pipeline import Target, generate_pipeline, rank_pipeline
from buyout_toolkit.investment_memo import build_investment_memo, render_memo_markdown


def make_target(**overrides) -> Target:
    defaults = dict(
        target_id="T-MEMO",
        company_name="Memo Test Co LLC",
        sub_sector="Residential HVAC Services",
        geography="TX",
        years_in_business=22,
        revenue=16_500_000.0,
        ebitda_margin=0.19,
        revenue_growth_rate=0.08,
        recurring_revenue_pct=0.5,
        customer_concentration_pct=0.10,
        number_of_locations=5,
        owner_age=67,
        succession_situation="Retirement - No Successor Identified",
        outreach_status="LOI Submitted",
        net_debt=1_200_000.0,
    )
    defaults.update(overrides)
    return Target(**defaults)


def test_memo_pulls_figures_directly_from_underlying_modules():
    target = make_target()
    memo = build_investment_memo(target)

    assert memo.financial_profile["revenue"] == target.revenue
    assert memo.financial_profile["ebitda"] == target.ebitda
    assert memo.valuation.target_id == target.target_id
    assert memo.lbo_cases["base"].target_id == target.target_id
    assert memo.synergy_comparison.target_id == target.target_id
    assert memo.diligence_rollup.total_items > 0


def test_memo_recommendation_is_one_of_the_defined_outcomes():
    target = make_target()
    memo = build_investment_memo(target)
    assert memo.recommendation in {
        "Recommend Proceeding to LOI / Final IC Approval",
        "Conditional Approval - Complete Diligence Before Signing",
        "Do Not Proceed at Current Terms",
        "Do Not Proceed - Pending Red Flag Resolution",
    }


def test_render_memo_markdown_contains_key_sections():
    target = make_target()
    memo = build_investment_memo(target)
    markdown = render_memo_markdown(memo)

    assert target.company_name in markdown
    assert "Investment Thesis" in markdown
    assert "Valuation Summary" in markdown
    assert "Proposed Offer Terms" in markdown
    assert "Key Risks" in markdown
    assert "Diligence Status" in markdown
    assert "Recommendation" in markdown
    assert memo.recommendation in markdown


def test_build_investment_memo_works_across_full_pipeline():
    pipeline = rank_pipeline(generate_pipeline(n=40, seed=21))
    for target in pipeline[:5]:
        memo = build_investment_memo(target)
        assert memo.recommendation
        markdown = render_memo_markdown(memo)
        assert len(markdown) > 0
