"""Auditable discovery and bounded downloads for public urban-data catalogues.

Catalogue discovery is not proof that a resource is city-relevant or reusable.
Only a successful, validated download is recorded as retrieved. No auth bypass.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import re
import xml.etree.ElementTree as ET
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
META = ROOT / "data" / "metadata"
RAW = ROOT / "data" / "raw" / "catalog_resources"
MAX_BYTES = 50 * 1024 * 1024
USER_AGENT = "CarbonWiseResearchCollector/1.0 (academic; contact via repository)"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")[:120]
    return name or "resource"


def request_bytes(url: str, timeout: int = 30, retries: int = 2, max_bytes: int = MAX_BYTES) -> tuple[bytes, str, int]:
    """GET a bounded response with retry/backoff; return bytes, content type, status."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Only absolute HTTPS URLs are accepted")
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/csv, */*"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status = int(response.status)
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > max_bytes:
                    raise ValueError(f"Response exceeds {max_bytes} byte limit")
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise ValueError(f"Response exceeds {max_bytes} byte limit")
                if not data:
                    raise ValueError("Empty response")
                return data, content_type, status
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            # Some managed Python installs lack the system root CA bundle while
            # curl is correctly configured to use it. Retry through curl with
            # normal TLS verification; never disable certificate checks.
            if isinstance(exc, urllib.error.URLError) and "CERTIFICATE_VERIFY_FAILED" in str(exc.reason):
                curl = shutil.which("curl")
                if curl:
                    command = [curl, "--location", "--fail", "--silent", "--show-error",
                               "--max-time", str(timeout), "--max-filesize", str(max_bytes),
                               "--write-out", "\n__CW_META__:%{http_code}|%{content_type}", url]
                    result = subprocess.run(command, capture_output=True, check=False)
                    if result.returncode == 0:
                        marker = b"\n__CW_META__:<"
                        raw, sep, tail = result.stdout.rpartition(b"\n__CW_META__:")
                        if sep:
                            try:
                                status_raw, type_raw = tail.decode("utf-8", "replace").split("|", 1)
                                if len(raw) <= max_bytes and raw:
                                    return raw, type_raw.strip(), int(status_raw)
                            except ValueError:
                                pass
                    elif attempt == retries:
                        last_error = RuntimeError(result.stderr.decode("utf-8", "replace").strip() or f"curl exit {result.returncode}")
            if attempt < retries:
                time.sleep(0.4 * (2 ** attempt))
    raise RuntimeError(f"Request failed after {retries + 1} attempts: {last_error}")


def _json_get(url: str) -> dict[str, Any]:
    payload, _, _ = request_bytes(url, max_bytes=8 * 1024 * 1024)
    result = json.loads(payload.decode("utf-8-sig"))
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


def discover_opencity(city: str, rows: int = 100) -> list[dict[str, str]]:
    """Search public OpenCity CKAN catalogue using page offsets."""
    if not 1 <= rows <= 500:
        raise ValueError("rows must be between 1 and 500")
    base = "https://data.opencity.in/api/3/action/package_search"
    found: dict[str, dict[str, str]] = {}
    aliases = {"Bengaluru": ("Bengaluru", "Bangalore"), "Kolkata": ("Kolkata", "Calcutta")}
    search_terms = aliases.get(city, (city,))
    for search_term in search_terms:
        start = 0
        while True:
            query = urllib.parse.urlencode({"q": search_term, "rows": rows, "start": start})
            response = _json_get(f"{base}?{query}")
            if response.get("success") is not True:
                raise ValueError("OpenCity CKAN returned success=false")
            result = response.get("result") or {}
            packages = result.get("results") or []
            for package in packages:
                if not _mentions_city(package, city):
                    continue
                resources = package.get("resources") or []
                if not resources:
                    record = _package_record(city, package, {})
                    found[record["dataset_id"]] = record
                for resource in resources:
                    record = _package_record(city, package, resource)
                    found[record["dataset_id"]] = record
            total = int(result.get("count") or len(packages))
            start += len(packages)
            if not packages or start >= total:
                break
            time.sleep(0.2)
    return list(found.values())


def _mentions_city(package: dict[str, Any], city: str) -> bool:
    aliases = {"Bengaluru": ("bengaluru", "bangalore"), "Kolkata": ("kolkata", "calcutta")}
    terms = aliases.get(city, (city.casefold(),))
    # Descriptions can mention cities in broad or nationwide text; require an
    # explicit mention in dataset identity, source page, organization or tags.
    searchable = " ".join(str(package.get(k) or "") for k in ("title", "name", "url", "organization"))
    searchable += " " + " ".join(str(x) for x in package.get("tags", []))
    searchable += " " + " ".join(str(x.get("value") or "") for x in package.get("extras", []) if isinstance(x, dict))
    return any(term in searchable.casefold() for term in terms)


def _package_record(city: str, package: dict[str, Any], resource: dict[str, Any]) -> dict[str, str]:
    title = str(package.get("title") or package.get("name") or "Unknown title")
    resource_id = str(resource.get("id") or "")
    dataset_id = str(package.get("id") or package.get("name") or "")
    stable = hashlib.sha256(f"opencity|{dataset_id}|{resource_id}".encode()).hexdigest()[:16]
    return {
        "dataset_id": f"opencity_{stable}", "city_query": city, "title": title,
        "publisher": str((package.get("organization") or {}).get("title") or (package.get("organization") or {}).get("name") or "OpenCity catalogue; original publisher unknown"),
        "source_id": "opencity_ckan", "dataset_page": f"https://data.opencity.in/dataset/{package.get('name','')}",
        "resource_url": str(resource.get("url") or ""), "resource_id": resource_id,
        "format": str(resource.get("format") or "unknown"), "licence": str(package.get("license_title") or "unknown"),
        "licence_url": str(package.get("license_url") or ""), "published": str(package.get("metadata_created") or ""),
        "modified": str(package.get("metadata_modified") or ""), "description": re.sub(r"\s+", " ", str(package.get("notes") or ""))[:1200],
        "geo_coverage": "unknown; city query is a catalogue search, not validated spatial coverage",
        "temporal_coverage": "unknown", "discovery_status": "catalogue_metadata_discovered",
        "download_status": "not_attempted", "retrieved_at_utc": "", "sha256": "", "size_bytes": "",
        "local_path": "", "validation_status": "not_validated", "quality_note": "Dataset relevance, licence, geography and dates require human/resource-level review.",
    }


def validate_resource(path: Path, fmt: str, content_type: str = "") -> str:
    if path.stat().st_size == 0:
        raise ValueError("Downloaded resource is empty")
    extension = path.suffix.lower()
    fmt = (fmt or "").lower().strip()
    if extension == ".zip" or fmt in {"zip", "shapefile", "kmz"}:
        if not zipfile.is_zipfile(path):
            raise ValueError("File is labelled ZIP/KMZ but is not a valid ZIP container")
        if fmt == "shapefile":
            names = {Path(name).suffix.casefold() for name in zipfile.ZipFile(path).namelist()}
            if not {".shp", ".shx", ".dbf"}.issubset(names):
                raise ValueError("Zipped shapefile must include .shp, .shx and .dbf components")
    elif extension == ".kml" or fmt == "kml":
        root = ET.parse(path).getroot()
        if root.tag.split("}")[-1] not in {"kml", "Document", "Folder"}:
            raise ValueError("KML XML root is not recognized")
    elif fmt == "xlsx" or extension == ".xlsx":
        from openpyxl import load_workbook
        workbook = load_workbook(path, read_only=True, data_only=True)
        if not workbook.sheetnames:
            raise ValueError("Excel workbook contains no sheets")
        workbook.close()
    elif fmt == "pdf" or extension == ".pdf":
        if not path.read_bytes().startswith(b"%PDF-"):
            raise ValueError("PDF signature is missing")
        from pypdf import PdfReader
        PdfReader(path, strict=False)
    elif extension in {".json", ".geojson"} or fmt in {"json", "geojson"}:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object or GeoJSON FeatureCollection")
        if fmt == "geojson" and data.get("type") not in {"FeatureCollection", "Feature", "GeometryCollection"}:
            raise ValueError("JSON is not a recognized GeoJSON object")
    elif extension in {".csv", ".tsv"} or fmt in {"csv", "tsv"}:
        delimiter = "\t" if fmt == "tsv" or extension == ".tsv" else ","
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, delimiter=delimiter)
            header = next(reader, None)
            if not header or not any(str(c).strip() for c in header):
                raise ValueError("CSV/TSV has no usable header row")
    elif fmt == "xls" or extension == ".xls":
        # Legacy XLS is retained with signature check; optional parsing is not
        # attempted unless xlrd is installed in the user's environment.
        if not path.read_bytes().startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
            raise ValueError("Legacy XLS OLE signature is missing")
        return "downloaded_legacy_excel_signature_checked"
    else:
        return "downloaded_unparsed_format"
    return "downloaded_format_sanity_check_passed"


def download_resource(record: dict[str, str], max_bytes: int = MAX_BYTES) -> dict[str, str]:
    url = record.get("resource_url", "")
    if not url:
        record.update(download_status="skipped_no_resource_url", validation_status="not_validated")
        return record
    try:
        payload, content_type, status = request_bytes(url, max_bytes=max_bytes)
        basename = Path(urllib.parse.urlparse(url).path).name
        suffix = Path(basename).suffix[:12]
        fmt = record.get("format", "").lower()
        if not suffix:
            suffix = mimetypes.guess_extension(content_type) or ({"csv":".csv", "geojson":".geojson", "json":".json", "xlsx":".xlsx"}.get(fmt, ".bin"))
        RAW.mkdir(parents=True, exist_ok=True)
        suffix = suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,10}", suffix) else ".bin"
        stem = safe_name(record.get("resource_id") or record["dataset_id"])
        path = RAW / f"{stem}{suffix.lower()}"
        digest = hashlib.sha256(payload).hexdigest()
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
            status_text = "skipped_identical_hash"
        else:
            # Keep changed source bytes side by side; the prior raw snapshot is
            # immutable and remains addressable by its old manifest entry.
            if path.exists():
                path = RAW / f"{stem}_{digest[:12]}{suffix.lower()}"
                if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                    status_text = "skipped_identical_hash"
                else:
                    path.write_bytes(payload)
                    status_text = f"downloaded_http_{status}"
            else:
                path.write_bytes(payload)
                status_text = f"downloaded_http_{status}"
        record.update(download_status=status_text, retrieved_at_utc=now_utc(), sha256=digest,
                      size_bytes=str(len(payload)), local_path=str(path.relative_to(ROOT)),
                      validation_status=validate_resource(path, fmt, content_type))
    except Exception as exc:
        record.update(download_status=f"failed:{type(exc).__name__}:{exc}"[:300], validation_status="failed")
    _append_manifest(record)
    return record


def _append_manifest(record: dict[str, str]) -> None:
    manifest = META / "collection_manifest.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    entry = {"dataset_id":record.get("dataset_id"), "resource_id":record.get("resource_id"),
             "city_query":record.get("city_query"), "source_page":record.get("dataset_page"),
             "resource_url":record.get("resource_url"), "retrieved_at_utc":record.get("retrieved_at_utc") or now_utc(),
             "download_status":record.get("download_status"), "http_hash_sha256":record.get("sha256"),
             "size_bytes":record.get("size_bytes"), "local_path":record.get("local_path"),
             "validation_status":record.get("validation_status")}
    with manifest.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def _read_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def run(cities: list[str] | None = None, download: bool = False, max_resources: int = 0, rows: int = 100) -> dict[str, Any]:
    cities_cfg = _read_json(CONFIG / "cities.json", {"cities": []})["cities"]
    selected = [c for c in cities_cfg if not cities or c["city_id"] in cities]
    if cities and len(selected) != len(set(cities)):
        valid = {c["city_id"] for c in cities_cfg}
        unknown = sorted(set(cities) - valid)
        if unknown:
            raise ValueError(f"Unknown city IDs: {unknown}")
    META.mkdir(parents=True, exist_ok=True)
    existing_path = META / "dataset_inventory.csv"
    existing: dict[str, dict[str, str]] = {}
    if existing_path.exists():
        with existing_path.open(encoding="utf-8-sig", newline="") as f:
            existing = {r["dataset_id"]: r for r in csv.DictReader(f)}
    prior_inventory = dict(existing)
    selected_names = {c["name"] for c in selected}
    existing = {key:value for key,value in existing.items() if value.get("city_query") not in selected_names}
    attempted, failures = 0, 0
    for city_index, city in enumerate(selected):
        try:
            records = discover_opencity(city["name"], rows=rows)
        except Exception as exc:
            records = [{"dataset_id": f"opencity_search_{city['city_id']}", "city_query": city["name"],
                        "title": "OpenCity search attempt", "publisher": "OpenCity", "source_id": "opencity_ckan",
                        "dataset_page": "https://data.opencity.in/", "resource_url": "", "resource_id": "",
                        "format": "", "licence": "unknown", "licence_url": "", "published": "", "modified": "",
                        "description": "", "geo_coverage": "unknown", "temporal_coverage": "unknown",
                        "discovery_status": "search_failed", "download_status": "not_attempted", "retrieved_at_utc": "",
                        "sha256": "", "size_bytes": "", "local_path": "", "validation_status": "not_validated",
                        "quality_note": f"{type(exc).__name__}: {exc}"[:300]}]
        if max_resources > 0 and download:
            quota = max_resources // len(selected) + int(city_index < (max_resources % len(selected)))
        else:
            quota = max_resources
        attempted_for_city = 0
        # Prefer structured, parseable formats for the small opt-in demo run.
        if download:
            rank = {"csv":0,"geojson":1,"json":2,"tsv":3,"xlsx":4,"xls":5,"kml":6,"kmz":7,"zip":8}
            records.sort(key=lambda r: (rank.get(r.get("format", "").lower(), 20), r.get("title", "").casefold()))
        for record in records:
            old = prior_inventory.get(record["dataset_id"], {})
            # Retain prior successful provenance unless a new download is requested.
            for key in ("download_status", "retrieved_at_utc", "sha256", "size_bytes", "local_path", "validation_status"):
                if old.get(key) and not download:
                    record[key] = old[key]
            if record["discovery_status"] == "search_failed":
                failures += 1
            elif download and record.get("resource_url") and (quota <= 0 or attempted_for_city < quota):
                download_resource(record)
                attempted += 1
                attempted_for_city += 1
                failures += int(record["download_status"].startswith("failed:"))
            existing[record["dataset_id"]] = record
    fields = ["dataset_id","city_query","title","publisher","source_id","dataset_page","resource_url","resource_id","format","licence","licence_url","published","modified","description","geo_coverage","temporal_coverage","discovery_status","download_status","retrieved_at_utc","sha256","size_bytes","local_path","validation_status","quality_note"]
    records = list(existing.values())
    with existing_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(records)
    # Coverage artifacts always describe all target cities; this run's scope
    # is recorded separately so a subset refresh cannot erase other cities.
    summary = build_report(cities_cfg, records, failures)
    summary["cities_refreshed_this_run"] = [c["city_id"] for c in selected]
    _write_coverage_artifacts(cities_cfg, records, summary)
    (META / "collection_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _write_coverage_artifacts(cities: list[dict[str, str]], records: list[dict[str, str]], summary: dict[str, Any]) -> None:
    """Persist configured source leads and actual catalogue coverage separately."""
    catalogue = _read_json(CONFIG / "source_catalog.json", {"catalogues": []})["catalogues"]
    source_rows = [{"source_id":s["source_id"], "organisation":s["organisation"], "source_url":s["base_url"],
                    "integration_kind":s["kind"], "access_or_licence_note":s["licence_note"],
                    "verification_status":"public_catalogue_api_queried; individual_resource_terms_require_review" if s["source_id"] == "opencity_ckan" else "configured_lead_not_yet_verified"} for s in catalogue]
    for city in cities:
        source_rows.append({"source_id":f"municipal_{city['city_id']}", "organisation":city["name"],
                            "source_url":city["municipal_home"], "integration_kind":"official_municipal_homepage",
                            "access_or_licence_note":"Relevant datasets and reuse terms must be identified on a per-resource basis.",
                            "verification_status":"official_homepage_configured_not_dataset_verified"})
    _write_csv(META / "source_registry.csv", list(source_rows[0]), source_rows)
    city_lookup = {r["city_id"]:r for r in summary["city_coverage"]}
    matrix = []
    for city in cities:
        row = city_lookup[city["city_id"]]
        matrix.append({"city_id":city["city_id"], "city":city["name"], "source_id":"opencity_ckan",
                       "source_status":row["coverage_status"], "catalogue_resource_rows":row["catalogue_resource_rows"],
                       "verified_spatial_coverage":"unknown", "temporal_coverage":"unknown", "licence_review":"required"})
        for source in catalogue:
            if source["source_id"] == "opencity_ckan":
                continue
            matrix.append({"city_id":city["city_id"], "city":city["name"], "source_id":source["source_id"],
                           "source_status":"configured_not_yet_discovered_or_retrieved", "catalogue_resource_rows":0,
                           "verified_spatial_coverage":"unknown", "temporal_coverage":"unknown", "licence_review":"required"})
    _write_csv(META / "city_dataset_coverage.csv", list(matrix[0]), matrix)
    _ensure_manifest(records)
    validations = audit_downloaded_resources(records)
    validation_fields = ["dataset_id","city_query","title","format","local_path","sha256_expected","sha256_actual","integrity_check","raw_data_rows","columns","missing_cells","duplicate_rows","contains_climate_measurement_field","geo_feature_count","derived_geojson_path","page_count","extracted_text_chars","quality_status","quality_note"]
    _write_csv(META / "resource_validation_report.csv", validation_fields, validations)
    summary["downloaded_resources_audited"] = len(validations)
    summary["raw_data_rows_in_downloaded_csvs"] = sum(int(r.get("raw_data_rows") or 0) for r in validations)
    summary["missing_csv_cells"] = sum(int(r.get("missing_cells") or 0) for r in validations)
    summary["duplicate_csv_rows"] = sum(int(r.get("duplicate_rows") or 0) for r in validations)
    summary["downloaded_climate_time_series_rows"] = sum(int(r.get("raw_data_rows") or 0) for r in validations if r.get("contains_climate_measurement_field") == "true")
    summary["geographic_features_collected"] = sum(int(r.get("geo_feature_count") or 0) for r in validations)
    summary["files_not_attempted"] = sum(r.get("download_status") == "not_attempted" for r in records)
    summary["failed_download_records_retained"] = sum(r.get("download_status", "").startswith("failed:") for r in records)
    summary["source_catalogues_configured"] = len(catalogue)
    summary["source_catalogues_actually_queried"] = 1 if any(r.get("source_id") == "opencity_ckan" for r in records) else 0
    summary["cities_with_successfully_downloaded_files"] = sum(any(r.get("city_query") == city["name"] and r.get("local_path") for r in records) for city in cities)
    summary["city_project_or_procurement_records_extracted"] = 0
    ready_dir = ROOT / "data" / "model_ready"
    ready_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(ready_dir / "multicity_candidates.csv",
               ["candidate_id","city_id","source_dataset_id","cost_inr","expected_carbon_tco2e_per_year","resilience_metric","geographic_id","evidence_class","eligibility_status","exclusion_reason"], [])
    report_dir = ROOT / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    md = ["# CarbonWise multi-city catalogue collection report", "", f"Generated UTC: {summary['generated_at_utc']}", "",
          "> This report describes catalogue search metadata, not a validated multi-city analytical dataset.", "",
          "## Measured run totals", "", f"- Target cities: {summary['city_count_targeted']}",
          f"- Cities with city-named catalogue metadata: {summary['cities_with_catalogue_items']}",
          f"- Cities with a downloaded original file: {summary['cities_with_successfully_downloaded_files']}",
          f"- Source catalogues queried: {summary['source_catalogues_actually_queried']} of {summary['source_catalogues_configured']} configured",
          f"- Unique dataset packages: {summary['unique_dataset_packages']}",
          f"- Resource rows (a dataset may expose multiple files): {summary['catalogue_records_retained']}",
          f"- Rows with a resource URL: {summary['resource_records_with_download_url']}",
          f"- Successful or hash-identical downloads: {summary['successful_downloads']}",
          f"- Downloaded resources content-audited: {summary['downloaded_resources_audited']}",
          f"- Raw CSV rows (not pooled across incompatible schemas): {summary['raw_data_rows_in_downloaded_csvs']}",
          f"- CSV missing cells: {summary['missing_csv_cells']}; duplicate rows: {summary['duplicate_csv_rows']}",
          f"- Downloaded CSV climate time-series rows detected by field names: {summary['downloaded_climate_time_series_rows']}",
          f"- KML geographic features inventoried and converted: {summary['geographic_features_collected']}",
          f"- Project/procurement rows extracted by this collector: {summary['city_project_or_procurement_records_extracted']}",
          f"- Resource downloads not attempted: {summary['files_not_attempted']}; retained download failures: {summary['failed_download_records_retained']}",
          f"- Downloaded/verified bytes represented in inventory: {summary['raw_bytes_downloaded_or_verified']}",
          f"- Model-ready investment candidates: {summary['model_ready_candidates']}", "", "## City search results", "",
          "| City | Unique packages | Resource rows | Downloaded | Basic-format valid | Status |", "|---|---:|---:|---:|---:|---|"]
    for c in summary["city_coverage"]:
        md.append(f"| {c['city']} | {c['unique_dataset_packages']} | {c['catalogue_resource_rows']} | {c['successful_downloads']} | {c['usable_downloads']} | {c['coverage_status']} |")
    md += ["", "## Interpretation and gaps", ""] + [f"- {warning}" for warning in summary["warnings"]]
    md += ["", "No OpenCity search result was promoted to model-ready because catalogue metadata does not establish compatible investment costs, measured outcomes, verified project geography, or comparable evidence. Resource-level license, dates, spatial coverage, schema and content still need quality review.",
           "", "The detailed registry is `data/metadata/dataset_inventory.csv`; configured source leads are `data/metadata/source_registry.csv`; the city-by-source matrix is `data/metadata/city_dataset_coverage.csv`. Downloaded originals, if any, are retained under `data/raw/catalog_resources/` and are indexed by SHA-256 in the inventory.", ""]
    (report_dir / "multicity_collection_report.md").write_text("\n".join(md), encoding="utf-8")


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def _ensure_manifest(records: list[dict[str, str]]) -> None:
    """Backfill first-seen retrievals into the append-only manifest."""
    manifest = META / "collection_manifest.jsonl"
    seen: set[tuple[str, str]] = set()
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
                seen.add((str(item.get("http_hash_sha256") or ""), str(item.get("local_path") or "")))
            except json.JSONDecodeError:
                continue
    for record in records:
        if not record.get("local_path") and not record.get("download_status", "").startswith("failed:"):
            continue
        key = (record.get("sha256", ""), record.get("local_path", ""))
        if key in seen:
            continue
        _append_manifest(record)
        seen.add(key)


def audit_downloaded_resources(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """Record hashes and basic row/feature counts without asserting suitability."""
    output = []
    for record in records:
        relative = record.get("local_path", "")
        if not relative:
            continue
        path = ROOT / relative
        item = {"dataset_id":record.get("dataset_id", ""), "city_query":record.get("city_query", ""),
                "title":record.get("title", ""), "format":record.get("format", ""), "local_path":relative,
                "sha256_expected":record.get("sha256", ""), "sha256_actual":"", "integrity_check":"failed",
                "raw_data_rows":"", "columns":"", "missing_cells":"", "duplicate_rows":"", "contains_climate_measurement_field":"false",
                "geo_feature_count":"", "page_count":"", "extracted_text_chars":"", "quality_status":"not_parsed", "quality_note":""}
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            item.update(sha256_actual=digest, integrity_check="pass" if digest == record.get("sha256") else "mismatch")
            fmt = (record.get("format") or path.suffix.lstrip(".")).casefold()
            if fmt in {"csv", "tsv"}:
                delimiter = "\t" if fmt == "tsv" else ","
                with path.open(encoding="utf-8-sig", newline="") as stream:
                    rows = list(csv.reader(stream, delimiter=delimiter))
                header = rows[0] if rows else []
                data = rows[1:] if rows else []
                climate_field = any(any(term in str(field).casefold() for term in ("rainfall", "precipitation", "temperature", "tmax", "tmin", "heat index")) for field in header)
                item.update(raw_data_rows=str(len(data)), columns=json.dumps(header, ensure_ascii=False),
                            missing_cells=str(sum(not cell.strip() for row in data for cell in row)),
                            duplicate_rows=str(len(data) - len({tuple(row) for row in data})),
                            contains_climate_measurement_field=str(climate_field).lower(),
                            quality_status="basic_csv_inventory_complete" if header else "empty_or_header_missing",
                            quality_note="Counts only; domain/schema suitability and semantic correctness are not assessed.")
            elif fmt in {"kml", "kmz"}:
                if fmt == "kmz":
                    with zipfile.ZipFile(path) as archive:
                        member = next((name for name in archive.namelist() if name.lower().endswith(".kml")), None)
                        if not member:
                            raise ValueError("KMZ has no KML member")
                        root = ET.fromstring(archive.read(member))
                else:
                    root = ET.parse(path).getroot()
                geojson_path, count, geometry_issues = kml_to_geojson(root, record)
                item.update(geo_feature_count=str(count), quality_status="kml_to_geojson_with_coordinate_checks",
                            quality_note=f"KML coordinates transformed per KML lon,lat order; geometry validity and city-boundary containment not assessed. Coordinate issues: {geometry_issues}.",
                            derived_geojson_path=str(geojson_path.relative_to(ROOT)))
            elif fmt in {"geojson", "json"}:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                if data.get("type") == "FeatureCollection":
                    item.update(geo_feature_count=str(len(data.get("features", []))), quality_status="basic_geojson_inventory_complete",
                                quality_note="Feature count only; CRS and geometry validity are not fully assessed.")
                else:
                    item.update(quality_status="basic_json_syntax_valid", quality_note="JSON structure is retained; schema is not assessed.")
            elif fmt == "pdf":
                from pypdf import PdfReader
                reader = PdfReader(path, strict=False)
                item.update(page_count=str(len(reader.pages)), extracted_text_chars=str(sum(len(page.extract_text() or "") for page in reader.pages)),
                            quality_status="pdf_integrity_and_text_inventory_complete", quality_note="No OCR or project/tender extraction performed.")
            elif fmt == "xlsx":
                from openpyxl import load_workbook
                workbook = load_workbook(path, read_only=True, data_only=True)
                sheet = workbook[workbook.sheetnames[0]]
                item.update(raw_data_rows=str(max(sheet.max_row - 1, 0)), columns=json.dumps([str(c.value or "") for c in next(sheet.iter_rows(max_row=1))], ensure_ascii=False),
                            quality_status="excel_first_sheet_dimensions_inventoried", quality_note="Only first-sheet dimensions/header recorded; cell semantics not assessed.")
                workbook.close()
            else:
                item.update(quality_status="integrity_hash_checked_only", quality_note="Format-specific parser is not implemented.")
        except Exception as exc:
            item.update(quality_status="failed", quality_note=f"{type(exc).__name__}: {exc}"[:300])
        output.append(item)
    return output


def _coordinates(text: str) -> list[list[float]]:
    coords = []
    for token in text.split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        lon, lat = float(parts[0]), float(parts[1])
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError(f"Coordinate outside longitude/latitude bounds: {lon},{lat}")
        coords.append([lon, lat])
    return coords


def kml_to_geojson(root: ET.Element, record: dict[str, str]) -> tuple[Path, int, int]:
    """Convert source KML geometry to GeoJSON while retaining source properties."""
    features = []
    issues = 0
    for placemark in (node for node in root.iter() if node.tag.split("}")[-1] == "Placemark"):
        props: dict[str, Any] = {"source_dataset_id":record.get("dataset_id", ""), "source_sha256":record.get("sha256", ""),
                                 "evidence_class":"official_record", "source_title":record.get("title", "")}
        for child in placemark.iter():
            tag = child.tag.split("}")[-1]
            if tag == "name" and child.text:
                props["name"] = child.text.strip()
            elif tag == "SimpleData" and child.attrib.get("name"):
                props[child.attrib["name"]] = (child.text or "").strip()
        geometries = []
        for node in placemark.iter():
            tag = node.tag.split("}")[-1]
            if tag == "Point":
                c = node.find(".//{*}coordinates")
                if c is not None and c.text:
                    coords = _coordinates(c.text)
                    if coords: geometries.append({"type":"Point", "coordinates":coords[0]})
            elif tag == "LineString":
                c = node.find(".//{*}coordinates")
                if c is not None and c.text:
                    coords = _coordinates(c.text)
                    if len(coords) >= 2: geometries.append({"type":"LineString", "coordinates":coords})
            elif tag == "Polygon":
                rings = []
                for c in node.findall(".//{*}LinearRing/{*}coordinates"):
                    if c.text:
                        coords = _coordinates(c.text)
                        if len(coords) >= 4:
                            if coords[0] != coords[-1]:
                                coords.append(coords[0])
                            rings.append(coords)
                if rings: geometries.append({"type":"Polygon", "coordinates":rings})
        if not geometries:
            issues += 1
            continue
        geom = geometries[0] if len(geometries) == 1 else {"type":"GeometryCollection", "geometries":geometries}
        features.append({"type":"Feature", "geometry":geom, "properties":props})
    output = ROOT / "data" / "geospatial" / f"opencity_{safe_name(record.get('city_query','unknown').lower())}_{safe_name(record.get('dataset_id','resource'))}.geojson"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"type":"FeatureCollection", "name":record.get("title", ""),
               "crs":{"type":"name", "properties":{"name":"urn:ogc:def:crs:OGC:1.3:CRS84"}},
               "features":features}
    output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return output, len(features), issues


def report_existing() -> dict[str, Any]:
    """Regenerate coverage/report artifacts from the saved inventory, no network."""
    cities = _read_json(CONFIG / "cities.json", {"cities": []})["cities"]
    path = META / "dataset_inventory.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        records = list(csv.DictReader(f))
    summary = build_report(cities, records, failures=0)
    summary["cities_refreshed_this_run"] = []
    _write_coverage_artifacts(cities, records, summary)
    (META / "collection_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def build_report(cities: list[dict[str, str]], records: list[dict[str, str]], failures: int = 0) -> dict[str, Any]:
    city_rows = []
    for city in cities:
        subset = [r for r in records if r.get("city_query", "").casefold() == city["name"].casefold()]
        verified_metadata = [r for r in subset if r.get("discovery_status") != "search_failed"]
        city_rows.append({"city_id":city["city_id"], "city":city["name"], "catalogue_resource_rows":len(verified_metadata),
                          "unique_dataset_packages":len({r.get("dataset_page", "") for r in verified_metadata if r.get("dataset_page")}),
                          "successful_downloads":sum(r.get("download_status", "").startswith(("downloaded_http_", "skipped_identical_hash")) for r in subset),
                          "usable_downloads":sum(r.get("validation_status", "").endswith("passed") for r in subset),
                          "verified_model_ready_records":0,
                          "coverage_status":"city_name_in_dataset_identity; geography, time and licence require validation" if verified_metadata else "no_city_named_catalogue_metadata_or_search_failed"})
    return {"generated_at_utc":now_utc(), "city_count_targeted":len(cities), "cities_with_catalogue_items":sum(x["catalogue_resource_rows"]>0 and x["coverage_status"].startswith("city_name") for x in city_rows),
            "catalogue_records_retained":len(records), "resource_records_with_download_url":sum(bool(r.get("resource_url")) for r in records),
            "unique_dataset_packages":len({r.get("dataset_page", "") for r in records if r.get("dataset_page") and r.get("discovery_status") != "search_failed"}),
            "successful_downloads":sum(r.get("download_status", "").startswith(("downloaded_http_", "skipped_identical_hash")) for r in records),
            "failed_operations_in_this_run":failures, "raw_bytes_downloaded_or_verified":sum(int(r.get("size_bytes") or 0) for r in records if r.get("local_path")),
            "model_ready_candidates":0, "model_ready_explanation":"The discovered catalogue metadata has not been reviewed for comparable, location-linked cost and outcome evidence. No records promoted.",
            "city_coverage":city_rows, "warnings":["Catalogue search hits are leads, not verified city coverage.","OpenCity city query does not guarantee geographic containment.","Licence, date range, data quality and relevance require per-resource review.","Other catalogues remain configured discovery leads until a documented, permitted integration is run."]}


def cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", action="append", help="City ID; repeatable. Defaults to all eight.")
    parser.add_argument("--download", action="store_true", help="Download discovered public resources after size/type checks.")
    parser.add_argument("--max-resources", type=int, default=0, help="Maximum resources to attempt; 0 means no explicit count cap.")
    parser.add_argument("--rows", type=int, default=100, help="CKAN page size (1-500).")
    parser.add_argument("--report-only", action="store_true", help="Rebuild summary/coverage artifacts from saved metadata without network access.")
    args = parser.parse_args()
    if args.max_resources < 0:
        parser.error("--max-resources cannot be negative")
    summary = report_existing() if args.report_only else run(args.city, args.download, args.max_resources, args.rows)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    cli()
