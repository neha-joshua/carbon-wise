"""
report.py

Generates a report for the generated sample-project planner. It must clearly
label scores as relative model outputs, not verified or measured impacts.
"""
import pandas as pd
from datetime import date


def generate_report(df: pd.DataFrame, wards: pd.DataFrame, budget_cr: float,
                     balanced: pd.Series, front_df: pd.DataFrame,
                     comparison: pd.DataFrame, audit: dict, rationale: list[dict],
                     equity_weights: tuple[float, float, float]) -> str:
    cw_ids = balanced["selected_projects"].split(";")
    recommended = df[df["project_id"].isin(cw_ids)].copy()

    lines = []
    lines.append("=" * 70)
    lines.append("CARBONWISE - GENERATED SAMPLE PLAN")
    lines.append(f"Generated: {date.today().isoformat()}  |  Pilot city: Chennai")
    lines.append("DATA BASIS: generated demonstration projects; not actual proposals or observed outcomes")
    lines.append("All carbon, resilience, and community values below are relative model scores, not physical impact units.")
    lines.append("=" * 70)

    # --- Executive Summary ---
    lines.append("\n1. EXECUTIVE SUMMARY")
    lines.append("-" * 70)
    lines.append(
        f"With an illustrative budget of Rs {budget_cr:.1f} crore, the sample model selected "
        f"{int(balanced['n_projects'])} of {len(df)} generated examples, using Rs {balanced['total_cost_cr']:.1f} crore "
        f"({balanced['total_cost_cr']/budget_cr*100:.0f}% of this budget). This is one model-selected "
        f"option from {len(front_df)} feasible alternatives found in the search. It is not a city funding recommendation."
    )

    # --- Recommended Portfolio ---
    lines.append("\n2. RECOMMENDED PORTFOLIO")
    lines.append("-" * 70)
    by_category = recommended.groupby("category").agg(
        n=("project_id", "count"), cost=("cost_cr_inr", "sum")
    ).sort_values("cost", ascending=False)
    for cat, row in by_category.iterrows():
        lines.append(f"  {cat}: {int(row['n'])} project(s), \u20b9{row['cost']:.1f} cr")

    # --- Budget Allocation ---
    lines.append("\n3. BUDGET ALLOCATION")
    lines.append("-" * 70)
    lines.append(f"  Total budget:        \u20b9{budget_cr:.1f} cr")
    lines.append(f"  Amount allocated:    \u20b9{balanced['total_cost_cr']:.1f} cr")
    lines.append(f"  Unallocated:         \u20b9{budget_cr - balanced['total_cost_cr']:.1f} cr")
    lines.append(f"  Utilisation:         {balanced['total_cost_cr']/budget_cr*100:.0f}%")

    # --- Impact scores ---
    lines.append("\n4. RELATIVE SAMPLE-MODEL SCORES - NOT MEASURED IMPACTS")
    lines.append("-" * 70)
    lines.append(f"  Carbon score (relative):      {balanced['carbon_score']:.0f}")
    lines.append(f"  Resilience score (relative):  {balanced['resilience_score']:.0f}")
    lines.append(f"  Community score (relative):   {balanced['equity_score']:.0f}")
    lines.append(f"  Community score priorities: vulnerability={equity_weights[0]:.2f}, "
                 f"people served={equity_weights[1]:.2f}, infrastructure need={equity_weights[2]:.2f}")

    # --- Trade-off analysis ---
    lines.append("\n5. TRADE-OFF ANALYSIS")
    lines.append("-" * 70)
    for point in rationale:
        lines.append(f"  {point['title']}: {point['detail']}")

    # --- Baseline comparison ---
    lines.append("\n6. COMPARISON AGAINST CONVENTIONAL METHODS")
    lines.append("-" * 70)
    for _, row in comparison.iterrows():
        lines.append(f"  {row['method']}: carbon={row['carbon_score']:.0f}, "
                     f"resilience={row['resilience_score']:.0f}, equity={row['equity_score']:.0f}")

    # --- Equity audit ---
    lines.append("\n7. SAMPLE COST DISTRIBUTION - NOT A MEASURE OF WHO BENEFITED")
    lines.append("-" * 70)
    lines.append(f"  Population-share reference for selected zones: {audit['target_share_pct']:.0f}%")
    lines.append(f"  Greedy (cost-effectiveness only): {audit['before']['actual_share_pct']:.0f}% "
                 f"(gap {audit['before']['gap_pct_points']:+.0f} pts)")
    lines.append(f"  CarbonWise:                        {audit['after']['actual_share_pct']:.0f}% "
                 f"(gap {audit['after']['gap_pct_points']:+.0f} pts)")

    # --- Alternative Pareto solutions ---
    lines.append("\n8. OTHER OPTIONS FOUND (up to 5, sorted by carbon score)")
    lines.append("-" * 70)
    top5 = front_df.sort_values("carbon_score", ascending=False).head(5)
    for _, row in top5.iterrows():
        lines.append(f"  Option {int(row['solution_id'])}: {int(row['n_projects'])} examples, "
                     f"Rs {row['total_cost_cr']:.1f} crore | carbon score={row['carbon_score']:.0f}, "
                     f"resilience score={row['resilience_score']:.0f}, community score={row['equity_score']:.0f}")

    # --- Zone-level breakdown ---
    lines.append("\n9. ZONE-LEVEL BREAKDOWN (recommended portfolio)")
    lines.append("-" * 70)
    zone_summary = recommended.groupby("zone_name").agg(
        n=("project_id", "count"), cost=("cost_cr_inr", "sum")
    ).sort_values("cost", ascending=False)
    for zone, row in zone_summary.iterrows():
        vuln = wards[wards["zone_name"] == zone]["vulnerability_index"].iloc[0]
        lines.append(f"  {zone} (sample-file vulnerability score={vuln:.2f}): {int(row['n'])} example(s), "
                     f"Rs {row['cost']:.1f} crore")

    # --- Full project list ---
    lines.append("\n10. FULL RECOMMENDED PROJECT LIST")
    lines.append("-" * 70)
    for _, row in recommended.sort_values("cost_cr_inr", ascending=False).iterrows():
        lines.append(f"  [{row['project_id']}] {row['project_name']} "
                     f"- Rs {row['cost_cr_inr']:.1f} crore")

    lines.append("\n" + "=" * 70)
    lines.append("The example projects are generated and are not verified GCC proposals.")
    lines.append("Model scores do not prove emissions reduction, flood protection, equitable benefit, or causation.")
    lines.append("The search returns feasible options; it does not guarantee that every possible plan was found.")
    lines.append("=" * 70)

    return "\n".join(lines)


if __name__ == "__main__":
    from preprocessing import preprocess
    from equity_scoring import compute_equity_score
    from optimizer import run_nsga2, pareto_front_to_df, pick_balanced_solution
    from baselines import (equal_split_allocation, greedy_cost_effectiveness_allocation,
                            summarize_portfolio)
    from equity_auditor import audit_report
    from decision_rationale import build_rationale

    df = preprocess()
    df = compute_equity_score(df)
    wards = pd.read_csv("../data/raw/wards.csv")
    budget_cr = 50.0

    res, problem = run_nsga2(df, budget_cr)
    front_df = pareto_front_to_df(res, problem, df)
    balanced = pick_balanced_solution(front_df)

    eq_mask = equal_split_allocation(df, budget_cr)
    greedy_mask = greedy_cost_effectiveness_allocation(df, budget_cr)
    cw_ids = balanced["selected_projects"].split(";")
    cw_mask = df["project_id"].isin(cw_ids)
    comparison = pd.DataFrame([
        summarize_portfolio(df, eq_mask, "Equal Split"),
        summarize_portfolio(df, greedy_mask, "Greedy Cost-Effectiveness"),
        summarize_portfolio(df, cw_mask, "CarbonWise"),
    ])
    greedy_ids = df[greedy_mask]["project_id"].tolist()
    audit = audit_report(df, wards, greedy_ids, cw_ids)
    rationale = build_rationale(front_df, balanced, budget_cr, audit)

    report = generate_report(df, wards, budget_cr, balanced, front_df,
                              comparison, audit, rationale, (0.33, 0.33, 0.34))
    print(report)

    with open("../results/portfolios/investment_decision_report.txt", "w") as f:
        f.write(report)
    print("\n\nSaved -> results/portfolios/investment_decision_report.txt")
