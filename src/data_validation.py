"""Check model inputs for completeness and basic integrity before comparison."""
import pandas as pd
import numpy as np


def validate(df: pd.DataFrame, zones: pd.DataFrame) -> dict:
    issues = []

    n_projects = len(df)
    n_zones = len(zones)
    n_categories = df["category"].nunique()
    total_cost = df["cost_cr_inr"].sum()

    core_numeric = ["cost_cr_inr", "carbon_reduction_tco2_per_year",
                    "resilience_benefit_raw", "population_benefited"]
    missing_counts = df[core_numeric].isna().sum()
    n_missing = int(missing_counts.sum())
    if n_missing > 0:
        issues.append(f"{n_missing} missing values found in required numeric fields; missing values are not filled in")

    non_finite = int(np.isinf(df[core_numeric].to_numpy(dtype=float)).sum())
    if non_finite:
        issues.append(f"{non_finite} infinite values found in required numeric fields")

    n_nonpositive_cost = int((df["cost_cr_inr"] <= 0).sum())
    if n_nonpositive_cost > 0:
        issues.append(f"{n_nonpositive_cost} projects have zero or negative cost")

    orphaned = df[~df["zone_id"].isin(zones["zone_id"])]
    n_orphaned = len(orphaned)
    if n_orphaned > 0:
        issues.append(f"{n_orphaned} projects reference a zone_id not present in the zone file")

    n_duplicate_ids = int(df["project_id"].duplicated().sum())
    if n_duplicate_ids > 0:
        issues.append(f"{n_duplicate_ids} duplicate project_id values found")

    n_negative_carbon = int((df["carbon_reduction_tco2_per_year"] < 0).sum())
    if n_negative_carbon > 0:
        issues.append(f"{n_negative_carbon} projects have negative carbon reduction")

    n_negative_resilience = int((df["resilience_benefit_raw"] < 0).sum())
    if n_negative_resilience > 0:
        issues.append(f"{n_negative_resilience} projects have negative resilience benefit")

    merged_pop = df.merge(zones[["zone_id", "approx_population_2023"]], on="zone_id",
                           how="left", suffixes=("", "_zone"))
    n_pop_exceeds_ward = int((merged_pop["population_benefited"] >
                               merged_pop["approx_population_2023"]).sum())
    if n_pop_exceeds_ward > 0:
        issues.append(f"{n_pop_exceeds_ward} projects claim population_benefited exceeding their zone's total population")

    status = "READY" if not issues else "ISSUES FOUND"

    return {
        "status": status,
        "n_projects": n_projects,
        "n_zones": n_zones,
        "n_categories": n_categories,
        "total_candidate_cost_cr": round(total_cost, 1),
        "n_missing_values": n_missing,
        "issues": issues,
    }


def print_report(report: dict) -> None:
    print("DATA QUALITY REPORT")
    print(f"  Projects loaded:       {report['n_projects']}")
    print(f"  GCC zones:             {report['n_zones']}")
    print(f"  Project categories:    {report['n_categories']}")
    print(f"  Total candidate cost:  \u20b9{report['total_candidate_cost_cr']} cr")
    print(f"  Missing values:        {report['n_missing_values']}")
    if report["issues"]:
        print("  Issues:")
        for issue in report["issues"]:
            print(f"    - {issue}")
    print(f"  Status: {'READY TO COMPARE' if report['status'] == 'READY' else report['status']}")


if __name__ == "__main__":
    from preprocessing import preprocess
    df = preprocess()
    zones = pd.read_csv("../data/raw/wards.csv")
    report = validate(df, zones)
    print_report(report)
