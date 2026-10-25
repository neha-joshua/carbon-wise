"""Reproducible, conservative ingestion for the GCC starter and tender leads.

The source CSV is copied into data/raw unchanged. This module writes a dated
derived dataset and keeps unknown, estimated, and reported values distinct.
It deliberately does not adapt these records to the synthetic 15-zone model.
"""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RUN_DATE = date.today().isoformat()
DERIVED = ROOT / "data" / "derived" / RUN_DATE
STARTER = RAW / "projects_real_starter.csv"
TENDERS = ROOT / "data" / "tenders" / "chennai_drainage_tender_packages.csv"
EVIDENCE = ROOT / "data" / "evidence" / "gcc_climate_budget_evidence.csv"

REQUIRED_SOURCE_FIELDS = {
    "project_id", "project_name", "cost_crore_inr", "cost_type",
    "carbon_tco2e_per_year", "carbon_basis", "impact_type",
    "physical_scale", "data_source", "notes",
}
MODEL_READY_FIELDS = ("cost_crore_inr", "carbon_tco2e_per_year", "resilience_benefit")


def _number(value: str) -> float | None:
    value = (value or "").strip().replace(",", "")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _record_type(row: dict[str, str]) -> str:
    text = f"{row['project_name']} {row['cost_type']} {row['physical_scale']}".lower()
    if "programme level" in text or "work packages" in text:
        return "programme"
    return "project_or_aggregate"


def _issue(code: str, severity: str, message: str, record_id: str = "") -> dict[str, str]:
    return {"record_id": record_id, "severity": severity, "code": code, "message": message}


def run() -> dict:
    if not STARTER.exists():
        raise FileNotFoundError(f"Missing unchanged source copy: {STARTER}")
    DERIVED.mkdir(parents=True, exist_ok=True)
    with STARTER.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        missing_schema = sorted(REQUIRED_SOURCE_FIELDS - set(fields))
        if missing_schema:
            raise ValueError(f"Starter schema is missing required fields: {missing_schema}")
        source_rows = list(reader)

    if not EVIDENCE.exists():
        raise FileNotFoundError(f"Missing official-source evidence register: {EVIDENCE}")
    with EVIDENCE.open(encoding="utf-8-sig", newline="") as stream:
        evidence_rows = list(csv.DictReader(stream))
    evidence_by_id = {row["project_id"]: row for row in evidence_rows}
    if len(evidence_by_id) != len(evidence_rows):
        raise ValueError("GCC evidence register has duplicate project_id values")
    if set(evidence_by_id) != {row.get("project_id", "").strip() for row in source_rows}:
        raise ValueError("GCC evidence register IDs must exactly match the unchanged starter IDs")

    cleaned: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    issues: list[dict[str, str]] = []
    seen: set[str] = set()
    for source in source_rows:
        row = {key: (value or "").strip() for key, value in source.items()}
        rid = row["project_id"]
        evidence = evidence_by_id[rid]
        row.update({f"official_{key}": value for key, value in evidence.items() if key != "project_id"})
        row["official_evidence_status"] = "primary_source_confirmed_as_published_not_independently_audited"
        row["record_type"] = _record_type(row)
        row["cost_value"] = str(_number(row["cost_crore_inr"]) or "")
        row["cost_unit"] = "INR crore"
        row["cost_status"] = "reported_estimate" if row["cost_value"] else "unknown"
        row["carbon_value"] = str(_number(row["carbon_tco2e_per_year"]) or "")
        row["carbon_unit"] = "tCO2e/year (as labelled in source; basis not independently reconciled)"
        impact = row["impact_type"].lower()
        if not row["carbon_value"] or "unknown" in impact:
            row["carbon_status"] = "unknown"
        elif "recomputed" in evidence.get("ghg_basis", "").lower():
            row["carbon_status"] = "gcc_estimate_arithmetic_reproduced_assumptions_unvalidated"
        else:
            row["carbon_status"] = "gcc_primary_report_estimate_not_observed_outcome"
        row["resilience_value"] = ""
        row["resilience_status"] = "unknown"
        row["geographic_resolution"] = "location text only; zone/ward identifier not supplied"
        row["source_verification_status"] = "cross_referenced_to_official_gcc_climate_budget_not_independently_audited"
        row["model_eligible"] = "false"
        row["model_exclusion_reason"] = "; ".join([
            "no compatible GCC zone identifier/crosswalk",
            "no resilience benefit input",
            "cost is reported estimate, not reconciled package/award/expenditure value",
            "resilience benefit is not quantified on a compatible project-level basis",
            "reported impact estimates are not observed outcomes and retain source assumptions/scope",
        ])
        if not rid:
            issues.append(_issue("missing_project_id", "error", "project_id is blank"))
        elif rid in seen:
            issues.append(_issue("duplicate_project_id", "error", "Duplicate project_id; row retained for review", rid))
        seen.add(rid)
        if row["record_type"] == "programme":
            issues.append(_issue("programme_not_package", "warning", "Programme aggregate must not be treated as an individual funded project", rid))
        if rid == "R01":
            issues.append(_issue("large_caveated_ghg_estimate", "warning", "GCC Climate Budget p.54 gives a 41,28,416 tCO2e FY2025-26 potential-reduction estimate and says exact savings require detailed on-ground investigation; do not present as measured savings", rid))
        if rid == "R04":
            issues.append(_issue("programme_cost_not_package_cost", "warning", "₹5,553.3 crore is reported for 236 packages across schemes; not an individual tender cost", rid))
        if rid == "R13":
            issues.append(_issue("cost_and_carbon_scope_differ", "warning", "GCC Climate Budget pp.46,60-61: ₹8.19 crore refers to 8,083 fittings in 2023-25; 250.34 tCO2e/year is calculated for 1,610 proposed FY2025-26 fittings. Keep both facts; do not calculate cost-effectiveness across scopes", rid))
        if "cng" in row["project_name"].lower():
            issues.append(_issue("fuel_type_check", "warning", "Keep as CNG vehicles; do not recode as EVs. Estimated avoided emissions need validation", rid))
        if not row["carbon_value"]:
            issues.append(_issue("unknown_carbon", "warning", "Carbon impact is not quantified in starter record", rid))
        cleaned.append(row)
        excluded.append({"project_id": rid, "project_name": row["project_name"], "reason": row["model_exclusion_reason"]})

    evidence_fields = [f"official_{field}" for field in evidence_rows[0] if field != "project_id"] + ["official_evidence_status"]
    clean_fields = fields + evidence_fields + [
        "record_type", "cost_value", "cost_unit", "cost_status", "carbon_value",
        "carbon_unit", "carbon_status", "resilience_value", "resilience_status",
        "geographic_resolution", "source_verification_status", "model_eligible",
        "model_exclusion_reason",
    ]
    _write_csv(DERIVED / "cleaned_enriched_records.csv", clean_fields, cleaned)
    # Header-only output is an intentional safeguard: none of these records
    # meet the present optimiser's documented assumptions.
    model_fields = ["project_id", "project_name", "zone_id", "cost_cr_inr", "carbon_reduction_tco2_per_year", "resilience_benefit", "population_benefited", "dataset_version", "provenance_status"]
    _write_csv(DERIVED / "model_ready_records.csv", model_fields, [])
    _write_csv(DERIVED / "excluded_records.csv", ["project_id", "project_name", "reason"], excluded)
    _write_csv(DERIVED / "validation_issues.csv", ["record_id", "severity", "code", "message"], issues)

    tender_rows = []
    if TENDERS.exists():
        with TENDERS.open(encoding="utf-8-sig", newline="") as stream:
            tr = csv.DictReader(stream)
            tender_rows = list(tr)
        ids = [r.get("tender_id", "").strip() for r in tender_rows]
        for i, tid in enumerate(ids):
            if not tid:
                issues.append(_issue("missing_tender_id", "error", "Tender row has no official tender ID"))
            elif ids.count(tid) > 1 and ids.index(tid) == i:
                issues.append(_issue("duplicate_tender_id", "error", "Official tender ID occurs more than once", tid))
    _write_csv(DERIVED / "validation_issues.csv", ["record_id", "severity", "code", "message"], issues)
    summary = {
        "dataset_version": f"gcc-starter-derived-{RUN_DATE}-v3",
        "generated_on": date.today().isoformat(),
        "source_file": "data/raw/projects_real_starter.csv",
        "source_row_count": len(source_rows),
        "cleaned_row_count": len(cleaned),
        "rows_cross_referenced_to_official_gcc_climate_budget": len(evidence_by_id),
        "programme_row_count": sum(r["record_type"] == "programme" for r in cleaned),
        "model_ready_row_count": 0,
        "excluded_row_count": len(excluded),
        "tender_lead_count": len(tender_rows),
        "tenders_with_official_ids": sum(bool(r.get("tender_id", "").strip()) for r in tender_rows),
        "tender_estimated_value_records": sum(bool(r.get("estimated_tender_value_inr", "").strip()) for r in tender_rows),
        "tender_award_value_records": sum(bool(r.get("awarded_contract_value_usd", "").strip()) for r in tender_rows),
        "tender_actual_expenditure_records": sum(bool(r.get("actual_expenditure_inr", "").strip()) for r in tender_rows),
        "warning_count": sum(i["severity"] == "warning" for i in issues),
        "error_count": sum(i["severity"] == "error" for i in issues),
        "status": "source_evidence_enriched; GCC-reported facts/progress available; model ingestion still requires compatible validated cost, impact, resilience, and geographic inputs",
    }
    (DERIVED / "provenance_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
