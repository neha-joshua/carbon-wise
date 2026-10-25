"""
scenarios.py

The "What-If Scenario Simulator". Rather than re-running NSGA-II three times
with different objective weights (slow, and NSGA-II is weight-free by design),
we run it ONCE to get the full Pareto front, then apply three different
a-posteriori decision rules to the SAME front:

  - Max Carbon:   the front solution with the highest carbon score
  - Max Equity:   the front solution with the highest equity score
  - Balanced:     nearest-to-ideal-point solution (see optimizer.py)

This is methodologically cleaner than re-optimizing per scenario: it proves
all three "scenarios" are honest trade-offs that were already latent in one
consistent Pareto front, not three separately massaged results.
"""
import pandas as pd
from optimizer import pick_balanced_solution


def max_carbon_solution(front_df: pd.DataFrame) -> pd.Series:
    return front_df.loc[front_df["carbon_score"].idxmax()]


def max_equity_solution(front_df: pd.DataFrame) -> pd.Series:
    return front_df.loc[front_df["equity_score"].idxmax()]


def max_resilience_solution(front_df: pd.DataFrame) -> pd.Series:
    return front_df.loc[front_df["resilience_score"].idxmax()]


def build_scenarios(front_df: pd.DataFrame) -> pd.DataFrame:
    scenarios = {
        "Max Carbon": max_carbon_solution(front_df),
        "Max Equity": max_equity_solution(front_df),
        "Max Resilience": max_resilience_solution(front_df),
        "Balanced (Recommended)": pick_balanced_solution(front_df),
    }
    rows = []
    for name, sol in scenarios.items():
        rows.append({
            "scenario": name,
            "n_projects": int(sol["n_projects"]),
            "total_cost_cr": sol["total_cost_cr"],
            "carbon_score": sol["carbon_score"],
            "resilience_score": sol["resilience_score"],
            "equity_score": sol["equity_score"],
            "selected_projects": sol["selected_projects"],
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    from preprocessing import preprocess
    from equity_scoring import compute_equity_score
    from optimizer import run_nsga2, pareto_front_to_df

    df = preprocess()
    df = compute_equity_score(df)
    res, problem = run_nsga2(df, budget_cr=50.0)
    front_df = pareto_front_to_df(res, problem, df)

    scenarios_df = build_scenarios(front_df)
    print(scenarios_df[["scenario", "n_projects", "total_cost_cr",
                         "carbon_score", "resilience_score", "equity_score"]].to_string(index=False))
