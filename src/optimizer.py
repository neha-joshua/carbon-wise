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
    def __init__(self, df: pd.DataFrame, budget_cr: float, equity_floor=None,
                 carbon_col="carbon_score_raw", resilience_col="resilience_score_raw",
                 equity_col="equity_score", cost_col="cost_cr_inr"):
        self.df = df.reset_index(drop=True)
        self.n = len(df)
        self.budget = budget_cr
        self.cost = df[cost_col].to_numpy(dtype=float)
        self.carbon = df[carbon_col].to_numpy(dtype=float)
        self.resilience = df[resilience_col].to_numpy(dtype=float)
        self.equity = df[equity_col].to_numpy(dtype=float)
        self.equity_floor = equity_floor

        super().__init__(
            n_var=self.n,
            n_obj=3,
            n_constr=2 if equity_floor is not None else 1,
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
        if self.equity_floor is None:
            out["G"] = [g1]
        else:
            mean_equity = float(np.mean(self.equity[x])) if np.any(x) else 0.0
            out["G"] = [g1, self.equity_floor - mean_equity]


def run_nsga2(df: pd.DataFrame, budget_cr: float, pop_size=100, n_gen=150, seed=1,
              equity_floor=None, carbon_col="carbon_score_raw",
              resilience_col="resilience_score_raw", equity_col="equity_score",
              cost_col="cost_cr_inr"):
    if df.empty:
        raise ValueError("At least one project is required")
    if not np.isfinite(budget_cr) or budget_cr <= 0:
        raise ValueError("Budget must be a positive finite number")
    required = {carbon_col, resilience_col, equity_col, cost_col, "project_id"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing optimizer columns: {sorted(missing)}")
    values = df[[carbon_col, resilience_col, equity_col, cost_col]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Optimizer inputs must be complete finite numbers")
    if (df[cost_col] <= 0).any():
        raise ValueError("All project costs must be positive")
    if df["project_id"].duplicated().any():
        raise ValueError("Project IDs must be unique before optimization")
    if equity_floor is not None and not 0 <= equity_floor <= 100:
        raise ValueError("Minimum average equity score must be between 0 and 100")

    problem = InfrastructurePortfolioProblem(df, budget_cr, equity_floor,
        carbon_col, resilience_col, equity_col, cost_col)

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
    if res.X is None or res.F is None:
        return pd.DataFrame(columns=["solution_id", "n_projects", "total_cost_cr", "carbon_score", "resilience_score", "equity_score", "selected_projects"])
    for i, (x, f) in enumerate(zip(res.X, res.F)):
        x = np.asarray(x, dtype=bool)
        cost_ok = problem.cost[x].sum() <= problem.budget + 1e-8
        if problem.equity_floor is None:
            equity_ok = True
        else:
            mean_equity = float(np.mean(problem.equity[x])) if np.any(x) else 0.0
            equity_ok = mean_equity + 1e-8 >= problem.equity_floor
        if not (cost_ok and equity_ok):
            continue
        selected = df.loc[x, "project_id"].tolist()
        rows.append({
            "solution_id": i,
            "n_projects": int(x.sum()),
            "total_cost_cr": round(problem.cost[x].sum(), 6),
            "carbon_score": round(-f[0], 1),
            "resilience_score": round(-f[1], 1),
            "equity_score": round(-f[2], 1),
            "selected_projects": ";".join(selected),
        })
    return pd.DataFrame(rows).sort_values("carbon_score", ascending=False) if rows else pd.DataFrame(columns=["solution_id", "n_projects", "total_cost_cr", "carbon_score", "resilience_score", "equity_score", "selected_projects"])


def pick_balanced_solution(front_df: pd.DataFrame, weights=(1/3, 1/3, 1/3)) -> pd.Series:
    """
    Pick one representative 'balanced' portfolio from the Pareto front using
    a simple normalized-distance-to-ideal-point method (a standard, defensible
    a-posteriori decision rule -- not an ad hoc pick).
    """
    if front_df.empty:
        raise ValueError("No budget-feasible portfolio was found")
    norm = front_df[["carbon_score", "resilience_score", "equity_score"]].copy()
    for col in norm.columns:
        lo, hi = norm[col].min(), norm[col].max()
        norm[col] = (norm[col] - lo) / (hi - lo) if hi > lo else 0.5
    # distance to ideal point (1,1,1) -- lower is better
    w = np.asarray(weights, dtype=float)
    if w.shape != (3,) or not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
        raise ValueError("Portfolio preference weights must be three non-negative values with a positive sum")
    w /= w.sum()
    dist = np.sqrt((((norm - 1) ** 2) * w).sum(axis=1))
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
