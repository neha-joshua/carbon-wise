"""Data intake, validation, and visual-audit helpers for the interactive workspace."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image


REQUIRED_FIELDS = {
    "project_id": "Project ID",
    "cost_cr_inr": "Cost",
    "carbon_reduction_tco2_per_year": "Annual carbon benefit",
    "resilience_benefit_raw": "Resilience benefit",
    "equity_raw": "Equity / community benefit",
}


def load_uploaded_table(filename: str, content: bytes) -> pd.DataFrame:
    """Read CSV or the first worksheet of an Excel workbook without changing source values."""
    if len(content) > 25 * 1024 * 1024:
        raise ValueError("Files must be 25 MB or smaller for this interactive demo.")
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(BytesIO(content))
        if frame.columns.duplicated().any():
            raise ValueError("This CSV has duplicate column headers. Rename them so each column is unique, then upload again.")
        return frame
    if suffix in {".xlsx", ".xlsm"}:
        frame = pd.read_excel(BytesIO(content), sheet_name=0, engine="openpyxl")
        if frame.columns.duplicated().any():
            raise ValueError("The first worksheet has duplicate column headers. Rename them so each column is unique.")
        return frame
    if suffix == ".xls":
        raise ValueError("Legacy .xls is not supported. Save the workbook as .xlsx and upload it again.")
    raise ValueError("Upload a CSV or Excel workbook (.xlsx/.xlsm).")


def _guess(columns, tokens):
    for column in columns:
        key = str(column).lower().replace("_", " ").replace("-", " ")
        if any(token in key for token in tokens):
            return column
    return "(not mapped)"


def default_column_mapping(columns):
    return {
        "project_id": _guess(columns, ("project id", "record id", "tender id", "project code", "id")),
        "cost_cr_inr": _guess(columns, ("cost", "budget", "amount", "capex")),
        "carbon_reduction_tco2_per_year": _guess(columns, ("carbon", "co2", "ghg", "emission")),
        "resilience_benefit_raw": _guess(columns, ("resilience", "flood", "adaptation")),
        "equity_raw": _guess(columns, ("equity", "vulnerability", "deprivation", "population benefited")),
        "project_name": _guess(columns, ("project name", "name", "title")),
        "category": _guess(columns, ("category", "intervention", "sector", "type")),
        "zone_id": _guess(columns, ("zone id", "ward id", "zone", "ward", "location", "area")),
    }


def map_to_carbonwise(source: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    if source.columns.duplicated().any():
        raise ValueError("Column headers must be unique before mapping.")
    missing = [field for field in REQUIRED_FIELDS if mapping.get(field, "(not mapped)") not in source.columns]
    if missing:
        labels = [REQUIRED_FIELDS[field] for field in missing]
        raise ValueError("Map all five required fields before optimizing: " + ", ".join(labels) + ".")
    core_columns = [mapping[field] for field in REQUIRED_FIELDS]
    if len(set(core_columns)) != len(core_columns):
        raise ValueError("Each required model field must map to a different source column. Review the column mapping.")
    out = pd.DataFrame(index=source.index)
    out["project_id"] = source[mapping["project_id"]].astype("string").str.strip()
    out["cost_cr_inr"] = pd.to_numeric(source[mapping["cost_cr_inr"]], errors="coerce")
    out["carbon_reduction_tco2_per_year"] = pd.to_numeric(source[mapping["carbon_reduction_tco2_per_year"]], errors="coerce")
    out["resilience_benefit_raw"] = pd.to_numeric(source[mapping["resilience_benefit_raw"]], errors="coerce")
    out["equity_raw"] = pd.to_numeric(source[mapping["equity_raw"]], errors="coerce")
    out["project_name"] = (source[mapping["project_name"]].astype("string")
                            if mapping.get("project_name") in source else out["project_id"])
    out["category"] = (source[mapping["category"]].astype("string").fillna("Unclassified")
                       if mapping.get("category") in source else "All projects")
    out["zone_id"] = (source[mapping["zone_id"]].astype("string").fillna("")
                      if mapping.get("zone_id") in source else "")
    out["_source_row"] = source.index.astype(int)
    return out.reset_index(drop=True)


def validate_mapped_data(frame: pd.DataFrame) -> pd.DataFrame:
    """Return row-level blocking issues; no missing numeric value is imputed."""
    issues = []
    frame = frame.reset_index(drop=True)
    if frame.empty:
        return pd.DataFrame([(0, "empty_dataset", "Add at least one project row before optimizing.")],
                            columns=["row", "issue", "message"])
    duplicate_ids = frame["project_id"].astype("string").str.strip().duplicated(keep=False)
    for pos, row in frame.iterrows():
        row_num = pos + 1
        pid = row.get("project_id", "")
        if pd.isna(pid) or not str(pid).strip() or str(pid).strip().lower() == "<na>":
            issues.append((row_num, "blank_project_id", "Project ID is blank."))
        for field, label in [("cost_cr_inr", "Cost"),
                             ("carbon_reduction_tco2_per_year", "Carbon benefit"),
                             ("resilience_benefit_raw", "Resilience benefit"),
                             ("equity_raw", "Equity benefit")]:
            value = pd.to_numeric(pd.Series([row.get(field)]), errors="coerce").iloc[0]
            if pd.isna(value) or not np.isfinite(value):
                issues.append((row_num, f"missing_or_invalid_{field}", f"{label} is missing or not numeric."))
            elif field == "cost_cr_inr" and value <= 0:
                issues.append((row_num, "nonpositive_cost", "Cost must be greater than zero."))
            elif field in {"carbon_reduction_tco2_per_year", "resilience_benefit_raw"} and value < 0:
                issues.append((row_num, f"negative_{field}", f"{label} cannot be negative for this model."))
        if not pd.isna(pid) and str(pid).strip() and str(pid).strip().lower() != "<na>" and duplicate_ids.iloc[pos]:
            issues.append((row_num, "duplicate_project_id", "Project ID is duplicated; edit the ID or remove one row."))
    return pd.DataFrame(issues, columns=["row", "issue", "message"])


def build_optimizer_frame(mapped: pd.DataFrame) -> pd.DataFrame:
    """Derive only relative comparison scores needed by CarbonWise baselines."""
    df = mapped.copy()
    df["project_id"] = df["project_id"].astype(str).str.strip()
    df["cost_cr_inr"] = pd.to_numeric(df["cost_cr_inr"], errors="coerce")
    for col in ["carbon_reduction_tco2_per_year", "resilience_benefit_raw", "equity_raw"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    def scale(series, maximum=100.0):
        lo, hi = series.min(), series.max()
        return pd.Series(maximum / 2, index=series.index) if hi == lo else maximum * (series - lo) / (hi - lo)

    df["carbon_score_raw"] = scale(df["carbon_reduction_tco2_per_year"])
    df["resilience_score_raw"] = scale(df["resilience_benefit_raw"])
    df["equity_score"] = scale(df["equity_raw"])
    return df


def analyze_image_pixels(content: bytes, max_side: int = 512) -> tuple[Image.Image, dict]:
    """Compute coarse color fractions; these are not semantic object classes."""
    image = Image.open(BytesIO(content))
    if image.width * image.height > 30_000_000:
        raise ValueError("Image is larger than the 30-megapixel demo limit.")
    image = image.convert("RGB")
    image.thumbnail((max_side, max_side))
    hsv = np.asarray(image.convert("HSV"), dtype=np.uint8)
    hue, saturation, value = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    green_hued = (hue >= 30) & (hue <= 100) & (saturation >= 50) & (value >= 30)
    gray_neutral = (saturation <= 45) & (value >= 35) & (value <= 205)
    pixels = max(1, hue.size)
    return image, {
        "green_hued_pixel_share_pct": round(float(green_hued.sum() / pixels * 100), 2),
        "low_saturation_gray_pixel_share_pct": round(float(gray_neutral.sum() / pixels * 100), 2),
        "sampled_pixels": int(pixels),
        "method": "HSV color threshold heuristic; not semantic segmentation",
    }
