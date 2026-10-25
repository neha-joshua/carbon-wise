"""
digital_twin.py

A lightweight DECISION DIGITAL TWIN layer for CarbonWise.

Honest framing (say this plainly if asked): this is NOT a physics-based
simulation or an IoT-connected twin of Chennai's actual infrastructure. It
is a decision digital twin in the sense used by the digital-twin governance
literature in this project's own review (Qiu et al., 2025) -- a live,
queryable representation of city state (zones + candidate projects) that
can be perturbed with hypothetical future conditions, re-optimized, and
compared against the current baseline. That is a real, well-defined, and
useful capability in its own right; it does not require -- and should not
be oversold as -- a full physical simulation.

Supported perturbations (each represents a plausible planning question):
  - vulnerability_shock(zone_id, delta):    "what if a zone's climate
        vulnerability increases/decreases by `delta`?" (e.g., a flood
        event, or a completed mitigation project elsewhere)
  - cost_shock(category, pct_change):       "what if a project category's
        cost changes (inflation, supply-chain shift, subsidy change)?"
  - population_shock(zone_id, pct_change):  "what if a zone's population
        changes (migration, densification)?"

Budget sensitivity is passed as a different `budget_cr` to `run_scenario`;
it is not stored as a property of CityState. This module is currently a
standalone Python component and is not wired into the Streamlit dashboard.

Each perturbation returns a MODIFIED COPY of the state -- the original
baseline state used elsewhere in the app is never mutated in place, so
the twin can be queried repeatedly from the same starting point.
"""
import copy
import pandas as pd

from preprocessing import preprocess, load_raw
from equity_scoring import compute_equity_score
from optimizer import run_nsga2, pareto_front_to_df, pick_balanced_solution
from equity_auditor import audit_report
from baselines import greedy_cost_effectiveness_allocation


class CityState:
    """A single, queryable snapshot of city state: wards + scored projects."""

    def __init__(self, wards: pd.DataFrame, projects_df: pd.DataFrame, label: str = "baseline"):
        self.wards = wards.copy()
        self.projects_df = projects_df.copy()
        self.label = label

    def clone(self, label: str) -> "CityState":
        return CityState(self.wards, self.projects_df, label=label)

    # --- perturbation operations -------------------------------------
    def vulnerability_shock(self, zone_id: str, delta: float) -> "CityState":
        """Increase (or decrease, with a negative delta) a zone's
        vulnerability_index, clipped to [0, 1]. Re-scores equity for any
        project in that zone since equity_score depends on vulnerability."""
        new = self.clone(f"{self.label} + vuln_shock({zone_id}, {delta:+.2f})")
        mask = new.wards["zone_id"] == zone_id
        if not mask.any():
            raise ValueError(f"Unknown zone_id: {zone_id}")
        new.wards.loc[mask, "vulnerability_index"] = (
            new.wards.loc[mask, "vulnerability_index"] + delta
        ).clip(0, 1)
        new.projects_df = _rescore(new.projects_df, new.wards)
        return new

    def population_shock(self, zone_id: str, pct_change: float) -> "CityState":
        """Change a zone's population by pct_change (e.g. 0.15 = +15%)."""
        new = self.clone(f"{self.label} + pop_shock({zone_id}, {pct_change:+.0%})")
        mask = new.wards["zone_id"] == zone_id
        if not mask.any():
            raise ValueError(f"Unknown zone_id: {zone_id}")
        new.wards.loc[mask, "approx_population_2023"] = (
            new.wards.loc[mask, "approx_population_2023"] * (1 + pct_change)
        ).round().astype(int)
        new.projects_df = _rescore(new.projects_df, new.wards)
        return new

    def cost_shock(self, category: str, pct_change: float) -> "CityState":
        """Change all projects in a category's cost by pct_change."""
        new = self.clone(f"{self.label} + cost_shock({category}, {pct_change:+.0%})")
        mask = new.projects_df["category"] == category
        if not mask.any():
            raise ValueError(f"Unknown category: {category}")
        new.projects_df.loc[mask, "cost_cr_inr"] = (
            new.projects_df.loc[mask, "cost_cr_inr"] * (1 + pct_change)
        ).round(2)
        return new


def _rescore(projects_df: pd.DataFrame, wards: pd.DataFrame) -> pd.DataFrame:
    """Re-join projects to updated ward data and recompute equity inputs
    that depend on vulnerability/population (carbon/resilience scores are
    project-intrinsic and unaffected by ward perturbations)."""
    df = projects_df.drop(columns=["vulnerability_index", "infrastructure_deprivation_index",
                                     "approx_population_2023"], errors="ignore")
    df = df.merge(
        wards[["zone_id", "vulnerability_index", "infrastructure_deprivation_index",
               "approx_population_2023"]],
        on="zone_id", how="left"
    )
    return df


def load_baseline_state() -> CityState:
    df = preprocess()
    _, wards = load_raw()
    return CityState(wards, df, label="baseline")


def run_scenario(state: CityState, budget_cr: float, w1=0.33, w2=0.33, w3=0.34) -> dict:
    """Run the full CarbonWise pipeline on a given (possibly perturbed)
    city state and return a comparable result summary."""
    df = compute_equity_score(state.projects_df, w1=w1, w2=w2, w3=w3)
    res, problem = run_nsga2(df, budget_cr)
    front_df = pareto_front_to_df(res, problem, df)
    balanced = pick_balanced_solution(front_df)

    greedy_mask = greedy_cost_effectiveness_allocation(df, budget_cr)
    greedy_ids = df[greedy_mask]["project_id"].tolist()
    cw_ids = balanced["selected_projects"].split(";")
    audit = audit_report(df, state.wards, greedy_ids, cw_ids)

    return {
        "label": state.label,
        "n_projects": int(balanced["n_projects"]),
        "total_cost_cr": balanced["total_cost_cr"],
        "carbon_score": balanced["carbon_score"],
        "resilience_score": balanced["resilience_score"],
        "equity_score": balanced["equity_score"],
        "investment_share_pct": audit["after"]["actual_share_pct"],
        "selected_projects": set(cw_ids),
    }


def compare_scenarios(baseline_result: dict, scenario_result: dict) -> dict:
    """Produce a human-readable diff between two scenario runs."""
    added = scenario_result["selected_projects"] - baseline_result["selected_projects"]
    removed = baseline_result["selected_projects"] - scenario_result["selected_projects"]

    def pct_delta(key):
        b, s = baseline_result[key], scenario_result[key]
        return ((s - b) / b * 100) if b else 0.0

    return {
        "carbon_delta_pct": pct_delta("carbon_score"),
        "resilience_delta_pct": pct_delta("resilience_score"),
        "equity_delta_pct": pct_delta("equity_score"),
        "investment_share_delta_pts": scenario_result["investment_share_pct"] - baseline_result["investment_share_pct"],
        "n_projects_added": len(added),
        "n_projects_removed": len(removed),
        "added_project_ids": sorted(added),
        "removed_project_ids": sorted(removed),
    }


if __name__ == "__main__":
    BUDGET_CR = 50.0

    baseline = load_baseline_state()
    baseline_result = run_scenario(baseline, BUDGET_CR)
    print(f"=== BASELINE ===")
    print(f"Carbon={baseline_result['carbon_score']:.0f}  Resilience={baseline_result['resilience_score']:.0f}  "
          f"Equity={baseline_result['equity_score']:.0f}  InvestShare={baseline_result['investment_share_pct']:.0f}%  "
          f"Projects={baseline_result['n_projects']}")

    # Scenario: a flood event sharply raises Sholinganallur's vulnerability
    print(f"\n=== SCENARIO: Sholinganallur vulnerability +0.20 (simulated flood event) ===")
    shocked = baseline.vulnerability_shock("Z15", 0.20)
    shocked_result = run_scenario(shocked, BUDGET_CR)
    print(f"Carbon={shocked_result['carbon_score']:.0f}  Resilience={shocked_result['resilience_score']:.0f}  "
          f"Equity={shocked_result['equity_score']:.0f}  InvestShare={shocked_result['investment_share_pct']:.0f}%  "
          f"Projects={shocked_result['n_projects']}")

    diff = compare_scenarios(baseline_result, shocked_result)
    print(f"\n=== DIFFERENCE ===")
    print(f"Carbon: {diff['carbon_delta_pct']:+.1f}%   Resilience: {diff['resilience_delta_pct']:+.1f}%   "
          f"Equity: {diff['equity_delta_pct']:+.1f}%   InvestShare: {diff['investment_share_delta_pts']:+.1f} pts")
    print(f"Projects added: {diff['n_projects_added']}  removed: {diff['n_projects_removed']}")

    # Scenario: 20% budget cut
    print(f"\n=== SCENARIO: Budget cut to Rs. 35 crore ===")
    cut_result = run_scenario(baseline, 35.0)
    print(f"Carbon={cut_result['carbon_score']:.0f}  Resilience={cut_result['resilience_score']:.0f}  "
          f"Equity={cut_result['equity_score']:.0f}  InvestShare={cut_result['investment_share_pct']:.0f}%  "
          f"Projects={cut_result['n_projects']}")
