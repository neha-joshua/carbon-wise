"""
sensitivity.py

Answers a question any real planner would actually ask: "If our budget goes
up or down, how much does that change what we can achieve?" Runs the
balanced-portfolio selection across a range of budget levels and returns the
resulting carbon/resilience/equity trajectory -- this is the kind of
marginal-value analysis that turns a single-scenario tool into something a
finance department could actually use in a budget negotiation.
"""
import pandas as pd
from optimizer import run_nsga2, pareto_front_to_df, pick_balanced_solution


def run_sensitivity(df: pd.DataFrame, budget_levels: list[float],
                     pop_size=80, n_gen=100, seed=1) -> pd.DataFrame:
    rows = []
    for budget in budget_levels:
        res, problem = run_nsga2(df, budget, pop_size=pop_size, n_gen=n_gen, seed=seed)
        front_df = pareto_front_to_df(res, problem, df)
        balanced = pick_balanced_solution(front_df)
        rows.append({
            "budget_cr": budget,
            "n_projects": int(balanced["n_projects"]),
            "spent_cr": balanced["total_cost_cr"],
            "carbon_score": balanced["carbon_score"],
            "resilience_score": balanced["resilience_score"],
            "equity_score": balanced["equity_score"],
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    from preprocessing import preprocess
    from equity_scoring import compute_equity_score

    df = preprocess()
    df = compute_equity_score(df)

    levels = [20, 35, 50, 75, 100]
    result = run_sensitivity(df, levels)
    print(result.to_string(index=False))

    # marginal value: gain per additional crore between consecutive levels
    result["marginal_carbon_per_cr"] = result["carbon_score"].diff() / result["budget_cr"].diff()
    print("\nMarginal carbon score gained per additional Rs. crore of budget:")
    print(result[["budget_cr", "marginal_carbon_per_cr"]].to_string(index=False))
