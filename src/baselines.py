"""
baselines.py

Two conventional allocation methods CarbonWise is benchmarked against:

1. Equal-Split: distribute the budget evenly across project categories,
   funding as many projects as fit within each category's share.
2. Greedy Cost-Effectiveness: rank all projects by carbon-reduction-per-rupee
   and fund top-ranked projects until the budget is exhausted (the
   conventional single-objective approach most municipal tools default to).

Both are scored on the SAME three metrics as CarbonWise (carbon, resilience,
equity) so the comparison is apples-to-apples, even though neither baseline
optimizes for resilience or equity directly -- that asymmetry IS the point
of the comparison.
"""
import pandas as pd
import numpy as np


def equal_split_allocation(df: pd.DataFrame, budget_cr: float) -> pd.Series:
    categories = df["category"].unique()
    per_category_budget = budget_cr / len(categories)
    selected_ids = []

    for cat in categories:
        cat_df = df[df["category"] == cat].sample(frac=1, random_state=42)  # shuffle within category
        spent = 0.0
        for _, row in cat_df.iterrows():
            if spent + row["cost_cr_inr"] <= per_category_budget:
                selected_ids.append(row["project_id"])
                spent += row["cost_cr_inr"]

    return df["project_id"].isin(selected_ids)


def greedy_cost_effectiveness_allocation(df: pd.DataFrame, budget_cr: float) -> pd.Series:
    df = df.copy()
    df["carbon_per_cr"] = df["carbon_score_raw"] / df["cost_cr_inr"]
    ranked = df.sort_values("carbon_per_cr", ascending=False)

    selected_ids = []
    spent = 0.0
    for _, row in ranked.iterrows():
        if spent + row["cost_cr_inr"] <= budget_cr:
            selected_ids.append(row["project_id"])
            spent += row["cost_cr_inr"]

    return df["project_id"].isin(selected_ids)


def equity_aware_greedy_allocation(
    df: pd.DataFrame,
    budget_cr: float,
    carbon_weight: float = 0.5,
    equity_weight: float = 0.5,
) -> pd.Series:
    """Greedy benchmark balancing cost efficiency and the project's equity score.

    Both per-crore signals are min-max scaled across the same candidate set,
    then combined with declared weights. Projects are considered in descending
    score order and selected only when they fit the same total budget. This is
    a heuristic comparator, not a claim that the weights are normative.
    """
    if budget_cr < 0:
        raise ValueError("budget_cr must be non-negative")
    if carbon_weight < 0 or equity_weight < 0 or carbon_weight + equity_weight <= 0:
        raise ValueError("weights must be non-negative and at least one must be positive")
    required = {"project_id", "cost_cr_inr", "carbon_score_raw", "equity_score"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if df["project_id"].duplicated().any():
        raise ValueError("project_id must be unique")
    if df[list(required - {"project_id"})].isna().any().any():
        raise ValueError("Greedy input scores and costs must not be missing")
    if (df["cost_cr_inr"] <= 0).any():
        raise ValueError("All project costs must be positive")

    work = df.copy()
    work["carbon_efficiency"] = work["carbon_score_raw"] / work["cost_cr_inr"]
    work["equity_efficiency"] = work["equity_score"] / work["cost_cr_inr"]

    def scale(values: pd.Series) -> pd.Series:
        lo, hi = values.min(), values.max()
        return (values - lo) / (hi - lo) if hi > lo else pd.Series(0.5, index=values.index)

    weight_total = carbon_weight + equity_weight
    work["combined_priority"] = (
        carbon_weight / weight_total * scale(work["carbon_efficiency"])
        + equity_weight / weight_total * scale(work["equity_efficiency"])
    )
    ranked = work.sort_values(
        ["combined_priority", "project_id"], ascending=[False, True], kind="mergesort"
    )
    selected_ids: list[str] = []
    spent = 0.0
    for _, row in ranked.iterrows():
        if spent + row["cost_cr_inr"] <= budget_cr + 1e-12:
            selected_ids.append(row["project_id"])
            spent += row["cost_cr_inr"]
    return df["project_id"].isin(selected_ids)


def summarize_portfolio(df: pd.DataFrame, mask: pd.Series, method_name: str) -> dict:
    sub = df[mask]
    return {
        "method": method_name,
        "n_projects": int(mask.sum()),
        "total_cost_cr": round(sub["cost_cr_inr"].sum(), 1),
        "carbon_score": round(sub["carbon_score_raw"].sum(), 1),
        "resilience_score": round(sub["resilience_score_raw"].sum(), 1),
        "equity_score": round(sub["equity_score"].sum(), 1),
    }


if __name__ == "__main__":
    from preprocessing import preprocess
    from equity_scoring import compute_equity_score
    from optimizer import run_nsga2, pareto_front_to_df, pick_balanced_solution

    df = preprocess()
    df = compute_equity_score(df)
    BUDGET_CR = 50.0

    eq_mask = equal_split_allocation(df, BUDGET_CR)
    greedy_mask = greedy_cost_effectiveness_allocation(df, BUDGET_CR)

    res, problem = run_nsga2(df, BUDGET_CR)
    front_df = pareto_front_to_df(res, problem, df)
    balanced = pick_balanced_solution(front_df)
    cw_ids = balanced["selected_projects"].split(";")
    cw_mask = df["project_id"].isin(cw_ids)

    results = [
        summarize_portfolio(df, eq_mask, "Equal Split"),
        summarize_portfolio(df, greedy_mask, "Greedy Cost-Effectiveness"),
        summarize_portfolio(df, cw_mask, "CarbonWise (NSGA-II)"),
    ]
    comparison = pd.DataFrame(results)
    print("\n=== BASELINE COMPARISON (Budget = Rs.", BUDGET_CR, "crore) ===")
    print(comparison.to_string(index=False))

    comparison.to_csv("../results/portfolios/baseline_comparison.csv", index=False)
    print("\nSaved -> results/portfolios/baseline_comparison.csv")
