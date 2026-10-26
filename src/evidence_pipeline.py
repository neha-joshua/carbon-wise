"""Build a provenance-preserving, normalized index from the reviewed registers.

Source-specific CSVs remain authoritative. This module never overwrites them; it
creates an analysis index, validation report, duplicate-review queue, and audit.
"""
from __future__ import annotations

import csv
import difflib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "evidence"
INDEX = EVIDENCE / "normalized_evidence_index.csv"
DUPLICATES = EVIDENCE / "duplicate_review.csv"
ISSUES = EVIDENCE / "validation_issues.csv"
AUDIT = EVIDENCE / "audit_summary.json"

INDEX_FIELDS = [
    "evidence_id", "project_id", "associated_evidence_ids", "source_record_id",
    "project_title", "exact_source_title", "agency", "department", "location_as_published",
    "zone_as_published", "division_as_published", "latitude", "longitude",
    "intervention_category", "source_type", "primary_source_url", "secondary_source_url",
    "tender_reference", "publication_date_as_published", "award_date_as_published",
    "financial_year_as_published", "reported_value_original_text", "reported_value_numeric",
    "currency", "value_unit", "source_value_field_heading", "tax_basis_as_published", "value_interpretation",
    "actual_expenditure_as_published",
    "project_status_as_published", "physical_progress_as_published",
    "climate_relevance_evidence", "equity_relevance_evidence", "ghg_value_as_published",
    "ghg_unit", "ghg_boundary_and_method", "reporting_period_as_published",
    "verification_status", "verification_tier", "status_normalized", "limitations", "source_retrieved_at", "extraction_method",
    "source_content_sha256", "duplicate_review_status", "optimization_eligibility", "optimization_exclusion_reason",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in value).split())


def normalize_tender_reference(value: str) -> str:
    return "".join(c for c in normalize_text(value) if c.isalnum())


def _blank(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"nan", "none", "null", "na", "n/a", "not reported", "not stated"} else text


def _base(**values: object) -> dict[str, str]:
    row = {field: "" for field in INDEX_FIELDS}
    row.update({key: _blank(value) for key, value in values.items() if key in row})
    return row


def make_index() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    projects = {r.get("project_id", ""): r for r in read_csv(ROOT / "data/raw/projects_real_starter.csv")}
    for r in read_csv(EVIDENCE / "gcc_climate_budget_evidence.csv"):
        project = projects.get(r.get("project_id", ""), {})
        ghg = r.get("reported_annual_ghg_reduction_tco2e", "")
        row = _base(
            evidence_id=f"GCC-CB-{r['project_id']}", project_id=r["project_id"],
            source_record_id=f"Climate Budget activity {r.get('climate_budget_item', '')}",
            project_title=project.get("project_name", ""), exact_source_title="",
            agency="Greater Chennai Corporation", department=project.get("gcc_department", ""),
            location_as_published=project.get("location", ""), intervention_category=r.get("classification", ""),
            source_type="official_budget_report_crosswalk", primary_source_url=r.get("primary_source_url", ""),
            reported_value_original_text=r.get("reported_cost_inr_crore", ""),
            reported_value_numeric=r.get("reported_cost_inr_crore", ""), currency="INR",
            value_unit="crore", value_interpretation="GCC report value; not actual expenditure",
            project_status_as_published=r.get("official_status", ""),
            physical_progress_as_published=r.get("physical_or_delivery_evidence", ""),
            climate_relevance_evidence=f"GCC classification {r.get('classification', '')}; printed report pages {r.get('printed_report_pages', '')}",
            equity_relevance_evidence="Not established by this register",
            ghg_value_as_published=ghg, ghg_unit="tCO2e/year" if ghg else "",
            ghg_boundary_and_method=r.get("ghg_basis", ""),
            reporting_period_as_published="FY2025-26 where stated in source; see exact row",
            verification_status="official report cross-reference; not independently audited",
            verification_tier="partially_verified_source_claim",
            status_normalized=_normalize_status(r.get("official_status", "")),
            limitations=r.get("interpretation_note", ""), extraction_method="curated page-level crosswalk; see register",
            duplicate_review_status="source register ID retained; cross-source project identity not resolved",
            optimization_eligibility="contextual_evidence_only",
            optimization_exclusion_reason="No common validated cost, GHG outcome, resilience score, equity measure, and project-to-zone crosswalk.",
        )
        rows.append(row)

    for r in read_csv(EVIDENCE / "cmrl_awarded_tenders.csv"):
        row = _base(
            evidence_id=r.get("evidence_id", ""), source_record_id=r.get("tender_reference", ""),
            project_title=r.get("work_title", ""), exact_source_title=r.get("work_title", ""), agency=r.get("department_or_agency", ""),
            department=r.get("department", ""), location_as_published=r.get("location_as_published", ""),
            source_type="official_award_listing", primary_source_url=r.get("primary_source_url", ""),
            tender_reference=r.get("tender_reference", ""),
            publication_date_as_published=r.get("tender_notice_date_as_published", ""),
            award_date_as_published=r.get("award_date_as_published", ""),
            reported_value_original_text=r.get("awarded_value_as_published", ""), currency=r.get("currency_as_published", ""),
            value_unit=r.get("value_unit_as_published", ""), source_value_field_heading=r.get("award_value_field_heading", ""),
            actual_expenditure_as_published=r.get("actual_expenditure", ""),
            tax_basis_as_published=r.get("tax_basis_as_published", ""),
            project_status_as_published=r.get("award_status", ""),
            climate_relevance_evidence=r.get("climate_relevance", ""),
            equity_relevance_evidence=r.get("equity_relevance", ""),
            verification_status="published on CMRL awarded-tenders listing; not completion-verified",
            verification_tier="verified_official_procurement_record_only",
            status_normalized="awarded",
            limitations=r.get("interpretation_note", ""), source_retrieved_at=r.get("source_retrieved_at", ""),
            extraction_method=r.get("extraction_method", "manual transcription; see CMRL register provenance"),
            source_content_sha256=r.get("source_content_sha256", ""),
            duplicate_review_status="tender-reference collisions reviewed separately; no automatic merge",
            optimization_eligibility="contextual_evidence_only",
            optimization_exclusion_reason="Award record lacks verified expenditure, completed asset, project-level GHG outcome, resilience score, equity measure, and zone crosswalk.",
        )
        rows.append(row)

    for r in read_csv(ROOT / "data/tenders/chennai_drainage_tender_packages.csv"):
        pid = f"TN-EPROC-{r.get('tender_id', '')}"
        notice_id, award_id = f"{pid}-NOTICE", f"{pid}-ADB-AWARD"
        limitations = r.get("missing_fields", "") + " " + r.get("notes", "")
        common = {"project_id": pid, "associated_evidence_ids": f"{notice_id}; {award_id}",
                  "tender_reference": r.get("tender_reference", ""),
                  "agency": r.get("department", "Greater Chennai Corporation"),
                  "project_title": r.get("title", ""), "exact_source_title": r.get("title", ""), "intervention_category": "storm-water drain tender (source title)",
                  "location_as_published": r.get("scheme_or_basin", ""),
                  "zone_as_published": r.get("zone", ""), "division_as_published": r.get("division", ""),
                  "verification_tier": "partially_verified_cross_source_match",
                  "limitations": limitations,
                  "verification_status": "TN eProcurement notice and ADB award listing exact-title matched; spend/completion unknown",
                  "duplicate_review_status": "distinct tender package; parent GCC Climate Budget mapping unconfirmed"}
        notice = _base(**common, evidence_id=notice_id, source_record_id=r.get("tender_id", ""),
                       source_type="official_tender_notice", primary_source_url=r.get("source_url", ""),
                       publication_date_as_published=r.get("published_date", ""),
                       project_status_as_published="tendered; later award reported by ADB",
                       status_normalized="tendered", extraction_method="reviewed tender notice fields; exact title retained",
                       optimization_eligibility="contextual_evidence_only",
                       optimization_exclusion_reason="Notice record does not establish paid cost, completed asset, realized GHG outcome, resilience score, equity measure, or verified local geography.")
        award = _base(**common, evidence_id=award_id, source_record_id=r.get("award_source_document_reference", ""),
                      source_type="official_award_record", primary_source_url=r.get("award_source_url", ""),
                      publication_date_as_published=r.get("published_date", ""),
                      award_date_as_published=r.get("contract_date", ""),
                      reported_value_original_text=r.get("awarded_contract_value_usd", ""),
                      reported_value_numeric=r.get("awarded_contract_value_usd", ""), currency="USD",
                      actual_expenditure_as_published=r.get("actual_expenditure_inr", ""),
                      value_unit="USD contract award total", value_interpretation="ADB-listed contract award, not actual expenditure",
                      project_status_as_published="awarded; completion not verified", status_normalized="awarded",
                      extraction_method="ADB award-table cross-reference; original USD retained",
                      optimization_eligibility="contextual_evidence_only",
                      optimization_exclusion_reason="Award amount is not expenditure and no measured outcome, resilience/equity measure, or validated geographic crosswalk is available.")
        rows.extend([notice, award])

    for r in read_csv(EVIDENCE / "manual_import.csv"):
        imported = {field: _blank(r.get(field, "")) for field in INDEX_FIELDS}
        imported["verification_tier"] = imported["verification_tier"] or "pending_manual_verification"
        imported["verification_status"] = imported["verification_status"] or "pending manual review; source not yet checked"
        imported["extraction_method"] = imported["extraction_method"] or "manual import; see docs/evidence_pipeline.md"
        imported["duplicate_review_status"] = imported["duplicate_review_status"] or "pending duplicate and cross-source review"
        imported["optimization_eligibility"] = imported["optimization_eligibility"] or "pending review"
        imported["optimization_exclusion_reason"] = imported["optimization_exclusion_reason"] or "Eligibility requires compatible validated inputs; see docs/evidence_pipeline.md."
        rows.append(imported)
    return rows, list(projects.values())


def identify_duplicates(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    review: list[dict[str, str]] = []
    refs: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        key = normalize_tender_reference(r.get("tender_reference", ""))
        if key:
            refs[key].append(r)
    for key, group in refs.items():
        if len(group) > 1:
            for i, left in enumerate(group):
                for right in group[i + 1:]:
                    if (left.get("project_id") and left.get("project_id") == right.get("project_id")
                            and left.get("associated_evidence_ids") == right.get("associated_evidence_ids")):
                        continue  # a reviewed source crosswalk links these separate documents
                    review.append({"record_a": left["evidence_id"], "record_b": right["evidence_id"],
                                   "match_type": "exact_normalized_tender_reference", "match_score": "1.000",
                                   "review_status": "manual_review_required; records retained", "match_key": key})

    titled = [r for r in rows if normalize_text(r.get("exact_source_title", "") or r.get("project_title", ""))]
    # Compare records across source types only; repeated entries in a single register remain intact.
    for i, left in enumerate(titled):
        left_title = normalize_text(left.get("exact_source_title", "") or left.get("project_title", ""))
        for right in titled[i + 1:]:
            if left.get("source_type") == right.get("source_type"):
                continue
            if left.get("project_id") and left.get("project_id") == right.get("project_id"):
                continue
            right_title = normalize_text(right.get("exact_source_title", "") or right.get("project_title", ""))
            left_packages = set(re.findall(r"\bpackage\s*\d+", left_title))
            right_packages = set(re.findall(r"\bpackage\s*\d+", right_title))
            if left_packages and right_packages and left_packages.isdisjoint(right_packages):
                continue  # explicit package numbers identify different scopes
            score = difflib.SequenceMatcher(a=left_title, b=right_title).ratio()
            if score >= 0.86:
                review.append({"record_a": left["evidence_id"], "record_b": right["evidence_id"],
                               "match_type": "cross_source_fuzzy_title", "match_score": f"{score:.3f}",
                               "review_status": "manual_review_required; records retained", "match_key": left_title[:120]})
    return review


def validate(rows: list[dict[str, str]], projects: list[dict[str, str]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    seen: Counter[str] = Counter(r.get("evidence_id", "") for r in rows)
    for r in rows:
        rid = r.get("evidence_id", "") or "(blank evidence ID)"
        for field in ("evidence_id", "agency", "source_type", "primary_source_url"):
            if not r.get(field, "").strip():
                issues.append({"record_id": rid, "severity": "error", "code": "required_field_blank", "field": field, "detail": "Required field is blank"})
        if not (r.get("project_title", "").strip() or r.get("exact_source_title", "").strip() or r.get("source_record_id", "").strip()):
            issues.append({"record_id": rid, "severity": "error", "code": "record_description_blank", "field": "project_title/exact_source_title/source_record_id", "detail": "At least one record title or source record identifier is required"})
        if seen.get(rid, 0) > 1:
            issues.append({"record_id": rid, "severity": "error", "code": "duplicate_evidence_id", "field": "evidence_id", "detail": "Evidence ID is repeated"})
        for field in ("primary_source_url", "secondary_source_url"):
            value = r.get(field, "")
            if value and (urlparse(value).scheme != "https" or not urlparse(value).netloc):
                issues.append({"record_id": rid, "severity": "error", "code": "invalid_source_url", "field": field, "detail": value})
        for field in ("publication_date_as_published", "award_date_as_published"):
            value = r.get(field, "")
            if value:
                formats = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y")
                if not any(_date_parses(value, fmt) for fmt in formats):
                    issues.append({"record_id": rid, "severity": "warning", "code": "date_requires_manual_review", "field": field, "detail": value})
        if r.get("reported_value_numeric") and not re.search(r"\d", r["reported_value_numeric"]):
            issues.append({"record_id": rid, "severity": "warning", "code": "malformed_numeric_value", "field": "reported_value_numeric", "detail": r["reported_value_numeric"]})
        if r.get("reported_value_numeric") and not r.get("value_unit"):
            issues.append({"record_id": rid, "severity": "warning", "code": "reported_value_unit_missing", "field": "value_unit", "detail": "Numeric value is present but no unit is recorded"})
        if r.get("currency") and not re.fullmatch(r"[A-Z]{3}", r["currency"]):
            issues.append({"record_id": rid, "severity": "error", "code": "malformed_currency_code", "field": "currency", "detail": r["currency"]})
        if r.get("ghg_value_as_published") and not r.get("ghg_unit"):
            issues.append({"record_id": rid, "severity": "error", "code": "ghg_unit_missing", "field": "ghg_unit", "detail": "GHG quantity is present without a unit"})
        if r.get("ghg_unit") and "co2e" not in r["ghg_unit"].casefold():
            issues.append({"record_id": rid, "severity": "warning", "code": "ghg_unit_requires_review", "field": "ghg_unit", "detail": r["ghg_unit"]})
        if r.get("project_status_as_published") and r.get("status_normalized"):
            expected_status = _normalize_status(r["project_status_as_published"])
            exempt_sources = {"official_award_listing"}  # CMRL status is conveyed by the listing itself
            if r.get("source_type") not in exempt_sources and expected_status not in {"not_stated", r["status_normalized"]}:
                issues.append({"record_id": rid, "severity": "warning", "code": "status_normalization_mismatch", "field": "status_normalized", "detail": f"Raw text maps to {expected_status!r}, stored as {r['status_normalized']!r}"})
        if r.get("project_status_as_published", "").casefold() == "completed" and not r.get("physical_progress_as_published"):
            issues.append({"record_id": rid, "severity": "warning", "code": "completed_without_delivery_detail", "field": "project_status_as_published", "detail": "Status is completed but no physical evidence is attached"})
    starter_ids = {r.get("project_id", "") for r in projects}
    gcc_ids = {r.get("project_id", "") for r in rows if r.get("evidence_id", "").startswith("GCC-CB-")}
    for missing in sorted(starter_ids - gcc_ids - {""}):
        issues.append({"record_id": missing, "severity": "error", "code": "gcc_crosswalk_missing_starter_id", "field": "project_id", "detail": "Starter ID is not represented in GCC register"})
    return issues


def audit(rows: list[dict[str, str]], duplicate_rows: list[dict[str, str]], issue_rows: list[dict[str, str]]) -> dict[str, object]:
    coverage = {field: sum(bool(r.get(field, "").strip()) for r in rows) for field in INDEX_FIELDS}
    by_source = Counter(r.get("source_type", "") for r in rows)
    by_agency = Counter(r.get("agency", "") for r in rows)
    by_status = Counter(r.get("project_status_as_published", "") or "Not stated" for r in rows)
    by_location = Counter(r.get("location_as_published", "") or "Not stated" for r in rows)
    tender_refs: dict[str, int] = Counter(normalize_tender_reference(r.get("tender_reference", "")) for r in rows if r.get("tender_reference", "").strip())
    project_sources: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row.get("project_id", "").strip():
            project_sources[row["project_id"]].add(row.get("source_type", ""))
    return {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "evidence_document_records": len(rows),
        "unique_project_count": None,
        "unique_project_count_note": "Not safely estimable: GCC starter IDs, CMRL procurement references, and drainage tender IDs do not share a verified project crosswalk. Blank CMRL project IDs are intentional.",
        "distinct_nonblank_project_identifiers": len({r["project_id"] for r in rows if r.get("project_id", "").strip()}),
        "project_ids_with_multiple_source_types": sum(len(kinds) > 1 for kinds in project_sources.values()),
        "source_counts": dict(sorted(by_source.items())),
        "agency_counts": dict(sorted(by_agency.items())),
        "location_counts": dict(sorted(by_location.items())),
        "status_counts": dict(sorted(by_status.items())),
        "duplicate_review_pairs": len(duplicate_rows),
        "exact_normalized_tender_reference_collision_groups_including_cross_source_links": sum(n > 1 for n in tender_refs.values()),
        "ambiguous_exact_normalized_tender_reference_groups": len({
            r["match_key"] for r in duplicate_rows if r["match_type"] == "exact_normalized_tender_reference"
        }),
        "validation_issue_count": len(issue_rows),
        "validation_issues_by_severity": dict(Counter(r["severity"] for r in issue_rows)),
        "field_coverage_nonblank_records": coverage,
        "limitations": [
            "The GCC evidence register contains one row for each of the 23 IDs in the supplied starter file; it is a curated crosswalk, not a comprehensive scrape of all GCC works.",
            "CMRL award rows are procurement documents, not completed projects or verified climate/equity outcomes.",
            "Cross-source title and tender-reference matches are review flags and are never automatic merges.",
            "A unique project count is withheld until a verified crosswalk links evidence documents to project identities.",
        ],
    }


def _date_parses(value: str, fmt: str) -> bool:
    try:
        datetime.strptime(value.strip(), fmt)
        return True
    except ValueError:
        return False


def _normalize_status(value: str) -> str:
    text = normalize_text(value)
    if "mixed" in text:
        return "mixed_source_status"
    if any(term in text for term in ("proposed", "planning stage", "planned")):
        return "proposed"
    if "ongoing" in text or "progress" in text:
        return "ongoing"
    if any(term in text for term in ("complete", "completed")):
        return "completed"
    if any(term in text for term in ("deployed", "operating", "handed over")):
        return "implemented_or_operating_source_claim"
    if "tendered" in text:
        return "tendered"
    if "award" in text:
        return "awarded"
    if "tender" in text:
        return "tendered"
    return "not_stated"


def build() -> dict[str, object]:
    rows, projects = make_index()
    duplicate_rows = identify_duplicates(rows)
    issue_rows = validate(rows, projects)
    write_csv(INDEX, INDEX_FIELDS, rows)
    write_csv(DUPLICATES, ["record_a", "record_b", "match_type", "match_score", "review_status", "match_key"], duplicate_rows)
    write_csv(ISSUES, ["record_id", "severity", "code", "field", "detail"], issue_rows)
    summary = audit(rows, duplicate_rows, issue_rows)
    AUDIT.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    result = build()
    print(json.dumps(result, indent=2, ensure_ascii=False))
