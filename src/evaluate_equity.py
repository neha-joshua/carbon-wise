"""Reproducible synthetic-data comparison with independent distribution audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from baselines import (
    equal_split_allocation,
    equity_aware_greedy_allocation,
    greedy_cost_effectiveness_allocation,
)
from equity_auditor import distributive_investment_metrics
from equity_scoring import compute_equity_score
from optimizer import run_nsga2, pareto_front_to_df, pick_balanced_solution
from preprocessing import preprocess, load_raw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "experiments"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evaluate(budget_cr: float = 50.0, seeds: list[int] | None = None,
             pop_size: int = 100, n_gen: int = 150) -> pd.DataFrame:
    if budget_cr <= 0:
        raise ValueError("budget_cr must be positive")
    seeds = seeds or [1, 2, 3, 4, 5]
    projects, zones = load_raw()
    df = compute_equity_score(preprocess())
    source_meta = {
        "dataset_version": "synthetic-projects-seed42-zone-table-unverified-v1",
        "projects_sha256": _sha256(ROOT / "data/raw/projects.csv"),
        "zones_sha256": _sha256(ROOT / "data/raw/wards.csv"),
        "budget_cr": budget_cr,
        "solver": "pymoo.NSGA2",
        "pop_size": pop_size,
        "n_gen": n_gen,
    }

    portfolios: list[dict] = []

    def record(method: str, mask: pd.Series, seed: int | None) -> None:
        selected = df[mask]
        ids = selected["project_id"].tolist()
        spend = float(selected["cost_cr_inr"].sum())
        audit = distributive_investment_metrics(df, zones, ids)
        portfolios.append({
            **source_meta,
            "method": method,
            "seed": seed,
            "n_projects": len(ids),
            "selected_project_ids": ";".join(ids),
            "total_cost_cr": spend,
            "unused_budget_cr": max(0.0, budget_cr - spend),
            "budget_violation_cr": max(0.0, spend - budget_cr),
            "feasible_recalculated": spend <= budget_cr + 1e-8,
            "carbon_modelled_tco2e_per_year": float(selected["carbon_reduction_tco2_per_year"].sum()),
            "carbon_score_normalized_sum": float(selected["carbon_score_raw"].sum()),
            "resilience_index_sum": float(selected["resilience_benefit_raw"].sum()),
            "equity_objective_sum": float(selected["equity_score"].sum()),
            **audit,
        })

    baselines = [
        ("Equal split", equal_split_allocation(df, budget_cr)),
        ("Greedy carbon efficiency", greedy_cost_effectiveness_allocation(df, budget_cr)),
        ("Equity-aware greedy (50/50)", equity_aware_greedy_allocation(df, budget_cr)),
    ]
    for name, mask in baselines:
        record(name, mask, None)

    for seed in seeds:
        result, problem = run_nsga2(df, budget_cr, pop_size=pop_size, n_gen=n_gen, seed=seed)
        if result.X is None or len(result.X) == 0:
            raise RuntimeError(f"NSGA-II returned no feasible portfolio for seed={seed}")
        front = pareto_front_to_df(result, problem, df)
        balanced = pick_balanced_solution(front)
        chosen = set(balanced["selected_projects"].split(";"))
        mask = df["project_id"].isin(chosen)
        record("CarbonWise NSGA-II balanced", mask, seed)

    OUT.mkdir(parents=True, exist_ok=True)
    output = pd.DataFrame(portfolios)
    output.to_csv(OUT / "equity_baseline_comparison.csv", index=False)
    (OUT / "equity_baseline_comparison_metadata.json").write_text(
        json.dumps({**source_meta, "seed_list": seeds,
                    "interpretation": "All portfolios are modelled on generated benchmark projects. Per-resident inequality describes investment allocation intensity, not observed benefits or outcomes."}, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget-cr", type=float, default=50.0)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--pop-size", type=int, default=100)
    parser.add_argument("--n-gen", type=int, default=150)
    args = parser.parse_args()
    comparison = evaluate(args.budget_cr, args.seeds, args.pop_size, args.n_gen)
    cols = ["method", "seed", "total_cost_cr", "carbon_modelled_tco2e_per_year",
            "resilience_index_sum", "gini_investment_per_resident",
            "theil_t_investment_per_resident", "atkinson_investment_per_resident",
            "high_vulnerability_investment_share_pct", "feasible_recalculated"]
    print(comparison[cols].to_string(index=False))
    print(f"Saved {OUT / 'equity_baseline_comparison.csv'}")
