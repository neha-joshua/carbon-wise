"""
preprocessing.py
Loads raw projects.csv + wards.csv, joins them, handles missing values,
and produces a single clean processed dataset used by every downstream
scoring/optimization module.
"""
import pandas as pd
import numpy as np
import os

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")


def load_raw():
    projects = pd.read_csv(os.path.join(RAW_DIR, "projects.csv"))
    wards = pd.read_csv(os.path.join(RAW_DIR, "wards.csv"))
    return projects, wards


def normalize_column(series: pd.Series) -> pd.Series:
    """Min-max normalize a column to [0, 100]."""
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(50.0, index=series.index)
    return 100 * (series - lo) / (hi - lo)


def preprocess() -> pd.DataFrame:
    projects, wards = load_raw()

    # 1. missing-value handling: any numeric NaNs get median-imputed,
    #    any categorical NaNs get "Unknown"
    numeric_cols = projects.select_dtypes(include=[np.number]).columns
    projects[numeric_cols] = projects[numeric_cols].fillna(projects[numeric_cols].median())
    cat_cols = projects.columns.difference(numeric_cols)
    projects[cat_cols] = projects[cat_cols].fillna("Unknown")

    # 2. join ward-level vulnerability context onto each project
    merged = projects.merge(
        wards[["zone_id", "vulnerability_index", "infrastructure_deprivation_index",
               "approx_population_2023"]],
        on="zone_id", how="left"
    )

    # 3. normalize raw metrics to comparable 0-100 scales
    merged["carbon_score_raw"] = normalize_column(merged["carbon_reduction_tco2_per_year"])
    merged["resilience_score_raw"] = normalize_column(merged["resilience_benefit_raw"])
    merged["cost_cr_inr"] = merged["cost_lakhs_inr"] / 100.0  # convert lakhs -> crores for readability

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    out_path = os.path.join(PROCESSED_DIR, "projects_processed.csv")
    merged.to_csv(out_path, index=False)
    print(f"Preprocessed {len(merged)} projects -> {out_path}")
    return merged


if __name__ == "__main__":
    df = preprocess()
    print(df[["project_id", "category", "zone_name", "cost_cr_inr",
              "carbon_score_raw", "resilience_score_raw"]].head(10))
