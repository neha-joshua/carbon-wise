"""
optimizer.py

The core CarbonWise decision engine. Formulates infrastructure portfolio
selection as a multi-objective binary knapsack problem and solves it with
NSGA-II (via pymoo), producing a Pareto front of budget-feasible portfolios
that trade off carbon reduction, resilience, and equity.

Decision variable: x_i in {0, 1} for each project i (fund / don't fund)
Objectives (all maximized -> pymoo minimizes, so we negate):
    f1 = -sum(carbon_score_i * x_i)
    f2 = -sum(resilience_score_i * x_i)
    f3 = -sum(equity_score_i * x_i)
Constraint:
    sum(cost_i * x_i) <= BUDGET
"""
import numpy as np
import pandas as pd
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.pntx import TwoPointCrossover
from pymoo.operators.mutation.bitflip import BitflipMutation
from pymoo.operators.sampling.rnd import BinaryRandomSampling
from pymoo.optimize import minimize

from preprocessing import preprocess
from equity_scoring import compute_equity_score


class InfrastructurePortfolioProblem(ElementwiseProblem):
    def __init__(self, df: pd.DataFrame, budget_cr: float):
        self.df = df.reset_index(drop=True)
        self.n = len(df)
        self.budget = budget_cr
        self.cost = df["cost_cr_inr"].values
        self.carbon = df["carbon_score_raw"].values
        self.resilience = df["resilience_score_raw"].values
        self.equity = df["equity_score"].values

        super().__init__(
            n_var=self.n,
            n_obj=3,
            n_constr=1,
            xl=0, xu=1,
            vtype=bool,
        )

    def _evaluate(self, x, out, *args, **kwargs):
        x = np.asarray(x, dtype=bool)
        total_cost = np.sum(self.cost[x])

        f1 = -np.sum(self.carbon[x])
        f2 = -np.sum(self.resilience[x])
        f3 = -np.sum(self.equity[x])

        g1 = total_cost - self.budget  # must be <= 0

        out["F"] = [f1, f2, f3]
        out["G"] = [g1]


def run_nsga2(df: pd.DataFrame, budget_cr: float, pop_size=100, n_gen=150, seed=1):
    problem = InfrastructurePortfolioProblem(df, budget_cr)

    algorithm = NSGA2(
        pop_size=pop_size,
        sampling=BinaryRandomSampling(),
        crossover=TwoPointCrossover(),
        mutation=BitflipMutation(),
        eliminate_duplicates=True,
    )

    res = minimize(problem, algorithm, ("n_gen", n_gen), seed=seed, verbose=False)
    return res, problem


def pareto_front_to_df(res, problem, df: pd.DataFrame) -> pd.DataFrame:
    """Convert the Pareto front solutions into a readable summary table."""
    rows = []
    for i, (x, f) in enumerate(zip(res.X, res.F)):
        x = np.asarray(x, dtype=bool)
        selected = df.loc[x, "project_id"].tolist()
        rows.append({
            "solution_id": i,
            "n_projects": int(x.sum()),
            "total_cost_cr": round(problem.cost[x].sum(), 1),
            "carbon_score": round(-f[0], 1),
            "resilience_score": round(-f[1], 1),
            "equity_score": round(-f[2], 1),
            "selected_projects": ";".join(selected),
        })
    return pd.DataFrame(rows).sort_values("carbon_score", ascending=False)


def pick_balanced_solution(front_df: pd.DataFrame) -> pd.Series:
    """
    Pick one representative 'balanced' portfolio from the Pareto front using
    a simple normalized-distance-to-ideal-point method (a standard, defensible
    a-posteriori decision rule -- not an ad hoc pick).
    """
    norm = front_df[["carbon_score", "resilience_score", "equity_score"]].copy()
    for col in norm.columns:
        lo, hi = norm[col].min(), norm[col].max()
        norm[col] = (norm[col] - lo) / (hi - lo) if hi > lo else 0.5
    # distance to ideal point (1,1,1) -- lower is better
    dist = np.sqrt(((norm - 1) ** 2).sum(axis=1))
    best_idx = dist.idxmin()
    return front_df.loc[best_idx]


if __name__ == "__main__":
    df = preprocess()
    df = compute_equity_score(df)

    BUDGET_CR = 50.0  # example: Rs. 50 crore available budget
    print(f"Running NSGA-II with budget = Rs. {BUDGET_CR} crore, {len(df)} candidate projects...")

    res, problem = run_nsga2(df, BUDGET_CR)
    front_df = pareto_front_to_df(res, problem, df)

    print(f"\nPareto front has {len(front_df)} non-dominated solutions.")
    print(front_df[["solution_id", "n_projects", "total_cost_cr",
                     "carbon_score", "resilience_score", "equity_score"]].head(10).to_string())

    balanced = pick_balanced_solution(front_df)
    print("\n--- Recommended balanced portfolio ---")
    print(balanced[["n_projects", "total_cost_cr", "carbon_score",
                     "resilience_score", "equity_score"]])
    print("Projects:", balanced["selected_projects"])
