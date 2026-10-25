"""
equity_scoring.py

Implements the CarbonWise equity metric:

    Equity_Score(project) = w1 * Vulnerability_Index(ward)
                           + w2 * Population_Benefited_Ratio(project)
                           + w3 * Infrastructure_Deprivation(ward)

This operationalizes "equity" as an explicit, auditable, per-project score
rather than a vague planning principle -- directly answering the design gap
flagged in Paper 1 (Ahmadi & Ghamisi, 2026) and grounded in the same
vulnerability-index logic used in Paper 7 (Pollack et al., 2025) and the
CDC Social Vulnerability Index methodology.

Weights (w1, w2, w3) default to equal thirds. This is stated explicitly as
a first-pass operational choice, open to sensitivity analysis -- not a
claimed-final formula.
"""
import pandas as pd
import numpy as np


def population_benefited_ratio(df: pd.DataFrame) -> pd.Series:
    """Population served by the project as a share of that ward's population."""
    ratio = df["population_benefited"] / df["approx_population_2023"]
    return ratio.clip(0, 1)


def compute_equity_score(df: pd.DataFrame, w1=1/3, w2=1/3, w3=1/3) -> pd.DataFrame:
    df = df.copy()
    df["pop_benefited_ratio"] = population_benefited_ratio(df)

    # normalize each component to 0-100 before weighting, so weights are
    # comparable regardless of each component's native scale
    def norm(s):
        lo, hi = s.min(), s.max()
        return 100 * (s - lo) / (hi - lo) if hi > lo else pd.Series(50.0, index=s.index)

    vuln_n = norm(df["vulnerability_index"])
    pop_n = norm(df["pop_benefited_ratio"])
    infra_n = norm(df["infrastructure_deprivation_index"])

    df["equity_score"] = w1 * vuln_n + w2 * pop_n + w3 * infra_n
    return df


if __name__ == "__main__":
    from preprocessing import preprocess
    df = preprocess()
    df = compute_equity_score(df)
    print(df[["project_id", "zone_name", "vulnerability_index",
              "pop_benefited_ratio", "equity_score"]].sort_values(
        "equity_score", ascending=False).head(10))
