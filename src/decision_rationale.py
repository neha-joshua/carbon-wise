"""
decision_rationale.py

Produces the structured "Why this portfolio?" breakdown: budget constraint,
carbon standing relative to the full Pareto front, equity impact, the
explicit trade-off made, and the leading alternative. Every number here is
pulled directly from already-computed optimizer/front data -- nothing is
invented, nothing requires an LLM.
"""
import pandas as pd


def carbon_percentile(front_df: pd.DataFrame, balanced: pd.Series) -> float:
    """What percentile is the balanced solution's carbon score within the full front?"""
    return 100 * (front_df["carbon_score"] <= balanced["carbon_score"]).mean()


def leading_alternative(front_df: pd.DataFrame, balanced: pd.Series) -> pd.Series:
    """The max-carbon solution on the front, for contrast."""
    return front_df.loc[front_df["carbon_score"].idxmax()]


def build_rationale(front_df: pd.DataFrame, balanced: pd.Series,
                     budget_cr: float, audit: dict) -> list[dict]:
    pct = carbon_percentile(front_df, balanced)
    alt = leading_alternative(front_df, balanced)
    carbon_gap_pct = 100 * (alt["carbon_score"] - balanced["carbon_score"]) / alt["carbon_score"] if alt["carbon_score"] else 0
    equity_gain_pct = 100 * (balanced["equity_score"] - alt["equity_score"]) / alt["equity_score"] if alt["equity_score"] else 0

    return [
        {
            "title": "Budget constraint",
            "detail": f"\u20b9{balanced['total_cost_cr']:.1f} cr of \u20b9{budget_cr:.1f} cr utilised "
                      f"({balanced['total_cost_cr']/budget_cr*100:.0f}%) across {int(balanced['n_projects'])} projects.",
        },
        {
            "title": "Carbon standing",
            "detail": f"Ranks in the top {100-pct:.0f}% of all {len(front_df)} Pareto-optimal portfolios "
                      f"found for this budget on carbon performance alone.",
        },
        {
            "title": "Equity impact",
            "detail": f"Directs {audit['after']['actual_share_pct']:.0f}% of investment toward "
                      f"high-vulnerability zones, against a population-proportional target of "
                      f"{audit['target_share_pct']:.0f}%.",
        },
        {
            "title": "Trade-off made",
            "detail": f"Sacrifices {carbon_gap_pct:.0f}% of the maximum achievable carbon reduction "
                      f"(compared to the max-carbon portfolio) to gain {equity_gain_pct:.0f}% higher equity.",
        },
        {
            "title": "Leading alternative",
            "detail": f"The max-carbon portfolio achieves {alt['carbon_score']:.0f} carbon score "
                      f"but only {alt['equity_score']:.0f} equity score, versus this portfolio's "
                      f"{balanced['equity_score']:.0f}.",
        },
    ]


if __name__ == "__main__":
    from preprocessing import preprocess
    from equity_scoring import compute_equity_score
    from optimizer import run_nsga2, pareto_front_to_df, pick_balanced_solution
    from baselines import greedy_cost_effectiveness_allocation
    from equity_auditor import audit_report

    df = preprocess()
    df = compute_equity_score(df)
    wards = pd.read_csv("../data/raw/wards.csv")
    budget_cr = 50.0

    res, problem = run_nsga2(df, budget_cr)
    front_df = pareto_front_to_df(res, problem, df)
    balanced = pick_balanced_solution(front_df)

    greedy_mask = greedy_cost_effectiveness_allocation(df, budget_cr)
    greedy_ids = df[greedy_mask]["project_id"].tolist()
    cw_ids = balanced["selected_projects"].split(";")
    audit = audit_report(df, wards, greedy_ids, cw_ids)

    rationale = build_rationale(front_df, balanced, budget_cr, audit)
    for point in rationale:
        print(f"\n{point['title']}:")
        print(f"  {point['detail']}")
