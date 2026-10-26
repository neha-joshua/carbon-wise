"""
preprocessing.py
Loads raw projects.csv + zones.csv, joins them, preserves missing numeric
inputs for validation, and produces the processed dataset used by the model.
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
        # A constant observed column gets a neutral score, but unknown inputs
        # must remain unknown so validation can stop the optimizer.
        return pd.Series(50.0, index=series.index).where(series.notna())
    return 100 * (series - lo) / (hi - lo)


def preprocess() -> pd.DataFrame:
    projects, wards = load_raw()

    # Keep missing numeric inputs missing so validation can block an unsafe
    # optimization. A missing benefit is unknown, not a median estimate.
    numeric_cols = projects.select_dtypes(include=[np.number]).columns
    cat_cols = projects.columns.difference(numeric_cols)
    projects[cat_cols] = projects[cat_cols].fillna("Unknown")

    # 2. join GCC zone context onto each sample project
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
