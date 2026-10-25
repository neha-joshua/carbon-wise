"""
equity_auditor.py

The "Who is being left behind?" feature -- built as a Justice40-style metric
(directly mirroring Paper 7, Pollack et al. 2025, in your literature review):
what SHARE of total investment (Rs.) flows to high-vulnerability zones,
compared against what share it "should" get if investment were proportional
to the population living in zones classified as high-vulnerability.

  target_share      = population of high-vuln zones / total population
  actual_share(method) = Rs. invested in high-vuln zones / total Rs. invested

A method "adequately" serves vulnerable zones when actual_share is close to
or above target_share. This is compared for:
  - Greedy (cost-effectiveness-only, the conventional baseline)
  - CarbonWise (equity-constrained NSGA-II recommendation)
"""
import pandas as pd
import numpy as np

HIGH_VULN_THRESHOLD = 0.70


def investment_share_report(df: pd.DataFrame, wards: pd.DataFrame,
                             funded_ids: list[str]) -> dict:
    high_vuln_zone_ids = wards[wards["vulnerability_index"] >= HIGH_VULN_THRESHOLD]["zone_id"].tolist()

    funded_df = df[df["project_id"].isin(funded_ids)]
    total_invested = funded_df["cost_cr_inr"].sum()
    invested_in_high_vuln = funded_df[funded_df["zone_id"].isin(high_vuln_zone_ids)]["cost_cr_inr"].sum()

    actual_share = 100 * invested_in_high_vuln / total_invested if total_invested > 0 else 0

    total_pop = wards["approx_population_2023"].sum()
    high_vuln_pop = wards[wards["zone_id"].isin(high_vuln_zone_ids)]["approx_population_2023"].sum()
    target_share = 100 * high_vuln_pop / total_pop if total_pop > 0 else 0

    return {
        "total_invested_cr": total_invested,
        "invested_in_high_vuln_cr": invested_in_high_vuln,
        "actual_share_pct": actual_share,
        "target_share_pct": target_share,
        "gap_pct_points": actual_share - target_share,
    }


def audit_report(df: pd.DataFrame, wards: pd.DataFrame,
                  greedy_ids: list[str], carbonwise_ids: list[str]) -> dict:
    before = investment_share_report(df, wards, greedy_ids)
    after = investment_share_report(df, wards, carbonwise_ids)

    return {
        "before": before,
        "after": after,
        "target_share_pct": before["target_share_pct"],  # same for both
        "improvement_pct_points": after["actual_share_pct"] - before["actual_share_pct"],
    }


def distributive_investment_metrics(
    df: pd.DataFrame,
    zones: pd.DataFrame,
    funded_ids: list[str],
    atkinson_epsilon: float = 0.5,
) -> dict:
    """Compute independent across-zone inequality metrics on investment/person.

    Every zone in ``zones`` is included, including zones with zero investment.
    Metrics describe modelled allocation intensity (INR crore per resident),
    not project benefits, service coverage, or observed outcomes.
    """
    required_projects = {"project_id", "zone_id", "cost_cr_inr"}
    required_zones = {"zone_id", "approx_population_2023", "vulnerability_index"}
    if required_projects - set(df.columns):
        raise ValueError(f"Project data missing: {sorted(required_projects - set(df.columns))}")
    if required_zones - set(zones.columns):
        raise ValueError(f"Zone data missing: {sorted(required_zones - set(zones.columns))}")
    if not 0 < atkinson_epsilon < 1:
        raise ValueError("atkinson_epsilon must be between 0 and 1")
    if df["project_id"].duplicated().any() or zones["zone_id"].duplicated().any():
        raise ValueError("project_id and zone_id values must be unique")
    if zones["approx_population_2023"].isna().any() or (zones["approx_population_2023"] <= 0).any():
        raise ValueError("Every zone must have a known positive population denominator")
    if df[["zone_id", "cost_cr_inr"]].isna().any().any() or (df["cost_cr_inr"] < 0).any():
        raise ValueError("Project zones and costs must be present and non-negative")

    selected_set = set(funded_ids)
    unknown_ids = selected_set - set(df["project_id"])
    if unknown_ids:
        raise ValueError(f"Unknown funded project IDs: {sorted(unknown_ids)}")
    selected = df[df["project_id"].isin(selected_set)]
    zone_investment = selected.groupby("zone_id")["cost_cr_inr"].sum()
    zone_table = zones[["zone_id", "approx_population_2023", "vulnerability_index"]].copy()
    zone_table["investment_cr"] = zone_table["zone_id"].map(zone_investment).fillna(0.0)
    intensity = (zone_table["investment_cr"] / zone_table["approx_population_2023"]).to_numpy(dtype=float)
    mean_intensity = float(intensity.mean()) if intensity.size else 0.0
    if mean_intensity == 0:
        gini = theil = atkinson = 0.0
    else:
        gini = float(np.abs(intensity[:, None] - intensity[None, :]).sum() / (2 * len(intensity) ** 2 * mean_intensity))
        positive = intensity > 0
        ratios = intensity[positive] / mean_intensity
        theil = float(np.sum(ratios * np.log(ratios)) / len(intensity)) if positive.any() else 0.0
        equally_distributed = float(np.mean(intensity ** (1 - atkinson_epsilon)) ** (1 / (1 - atkinson_epsilon)))
        atkinson = float(1 - equally_distributed / mean_intensity)

    high_ids = set(zone_table.loc[zone_table["vulnerability_index"] >= HIGH_VULN_THRESHOLD, "zone_id"])
    total_investment = float(zone_table["investment_cr"].sum())
    high_investment = float(zone_table.loc[zone_table["zone_id"].isin(high_ids), "investment_cr"].sum())
    return {
        "unit_of_analysis": f"{len(zone_table)} GCC zone records; all zones included",
        "measure": "modelled investment intensity per resident",
        "unit": "INR crore per resident",
        "atkinson_epsilon": atkinson_epsilon,
        "gini_investment_per_resident": gini,
        "theil_t_investment_per_resident": theil,
        "atkinson_investment_per_resident": atkinson,
        "investment_cr": total_investment,
        "high_vulnerability_investment_share_pct": 100 * high_investment / total_investment if total_investment else 0.0,
        "data_basis": "Generated benchmark project costs and existing zone population/vulnerability fields; not observed expenditure or benefits",
        "denominator_note": "Approximate 2023 zone population supplied in wards.csv; its provenance is not independently validated in this project",
        "missing_treatment": "Raises an error if population denominators or project allocation fields are missing; zero-investment zones are retained",
    }


if __name__ == "__main__":
    from preprocessing import preprocess
    from equity_scoring import compute_equity_score
    from optimizer import run_nsga2, pareto_front_to_df, pick_balanced_solution
    from baselines import greedy_cost_effectiveness_allocation

    df = preprocess()
    df = compute_equity_score(df)
    wards = pd.read_csv("../data/raw/wards.csv")

    BUDGET_CR = 50.0
    greedy_mask = greedy_cost_effectiveness_allocation(df, BUDGET_CR)
    greedy_ids = df[greedy_mask]["project_id"].tolist()

    res, problem = run_nsga2(df, BUDGET_CR)
    front_df = pareto_front_to_df(res, problem, df)
    balanced = pick_balanced_solution(front_df)
    cw_ids = balanced["selected_projects"].split(";")

    report = audit_report(df, wards, greedy_ids, cw_ids)
    print(f"Target share (high-vuln zones' population share of Chennai): {report['target_share_pct']:.0f}%")
    print(f"\nBEFORE (Greedy, cost-effectiveness only):")
    print(f"  Investment share to high-vuln zones: {report['before']['actual_share_pct']:.0f}% "
          f"(gap: {report['before']['gap_pct_points']:+.0f} pts vs target)")
    print(f"\nAFTER (CarbonWise):")
    print(f"  Investment share to high-vuln zones: {report['after']['actual_share_pct']:.0f}% "
          f"(gap: {report['after']['gap_pct_points']:+.0f} pts vs target)")
    print(f"\nImprovement: {report['improvement_pct_points']:+.0f} percentage points")

