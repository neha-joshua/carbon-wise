"""
decision_rationale.py

Builds a rule-based comparison using generated sample-model scores. These
scores and allocation comparisons are not measured real-world impacts.
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
            "title": "Budget used",
            "detail": f"Rs {balanced['total_cost_cr']:.1f} crore of the Rs {budget_cr:.1f} crore sample budget ({balanced['total_cost_cr']/budget_cr*100:.0f}%) across {int(balanced['n_projects'])} generated examples.",
        },
        {
            "title": "Carbon score",
            "detail": f"This plan's sample carbon score is in the top {100-pct:.0f}% of the {len(front_df)} options found for this budget.",
        },
        {
            "title": "Sample cost distribution",
            "detail": f"{audit['after']['actual_share_pct']:.0f}% of sample cost is assigned to zones above the selected threshold; their population-share reference is {audit['target_share_pct']:.0f}%. This does not measure who received benefits.",
        },
        {
            "title": "Trade-off",
            "detail": f"Compared with the highest-carbon-score option found, this plan's carbon score is {carbon_gap_pct:.0f}% lower and its community score is {equity_gain_pct:.0f}% higher.",
        },
        {
            "title": "Highest-carbon-score option",
            "detail": f"It scores {alt['carbon_score']:.0f} for carbon and {alt['equity_score']:.0f} for community, compared with {balanced['equity_score']:.0f} community score for this plan. These are generated, relative scores.",
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
