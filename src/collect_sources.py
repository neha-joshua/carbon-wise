"""Retrieve official evidence source pages and refresh supported registers.

The collector intentionally automates only static, source-labelled tables. GCC
project portals with interactive filters and restricted procurement portals are
logged with a manual-import requirement; they are never represented as scraped.
"""
from __future__ import annotations

import argparse
import difflib
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from io import BytesIO
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from evidence_pipeline import ROOT, normalize_tender_reference, read_csv, write_csv, build

EVIDENCE = ROOT / "data" / "evidence"
COLLECTION = ROOT / "data" / "collection"
CMRL_URL = "https://chennaimetrorail.org/awarded-tenders/"
SOURCE_SPECS = [
    ("gcc_ongoing_projects", "Greater Chennai Corporation", "https://chennaicorporation.gov.in/gcc/citizen-details/location-service/frm_project_search.jsp", "manual_filter_import", "The page requires user-selected zone/division/work type/year; do not treat an empty initial page as zero projects."),
    ("gcc_completed_projects", "Greater Chennai Corporation", "https://chennaicorporation.gov.in/gcc/citizen-details/location-service/frm_works_completed.jsp", "manual_filter_import", "Interactive zone/division/work type/year search; results need documented filter selections and manual review."),
    ("gcc_tender_bulletin", "Greater Chennai Corporation", "https://www.chennaicorporation.gov.in/gcc/tender/", "linked_document_inventory", "Bulletin files are source documents, not one project per bulletin; tender details need extraction and review."),
    ("gcc_climate_budget_2025_26", "Greater Chennai Corporation", "https://www.chennaicorporation.gov.in/gcc/pdf/ClimateBudget2025-2026.pdf", "existing_curated_register", "PDF is the primary source for the retained 23-row crosswalk; do not duplicate those actions."),
    ("gcc_stormwater_department", "Greater Chennai Corporation", "https://chennaicorporation.gov.in/gcc/department/storm-water/", "linked_document_inventory", "Department context page; only item-level details supported by a specific source document enter the register."),
    ("tn_eprocurement", "Tamil Nadu eProcurement", "https://tntenders.gov.in/", "manual_import", "Portal search, login/session and CAPTCHA or document access may constrain automated collection; record source notice URLs and exact IDs manually when needed."),
    ("cmrl_awarded_tenders", "Chennai Metro Rail Limited", CMRL_URL, "static_html_table", "The official page publishes award-list fields. Each row is an award document, not a completed asset."),
    ("cmrl_annual_reports", "Chennai Metro Rail Limited", "https://ta.chennaimetrorail.org/annual-report/", "linked_document_inventory", "The page links annual-report documents; report tables require source/page citations before new project-level rows are added."),
]


class TableAndLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table_depth = 0
        self._current_table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self.links: list[tuple[str, str]] = []
        self._anchor_href = ""
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._current_table = []
        elif tag == "tr" and self._table_depth == 1:
            self._row = []
        elif tag in ("td", "th") and self._table_depth == 1:
            self._cell = []
        elif tag == "a":
            self._anchor_href = attrs_dict.get("href") or ""
            self._anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
        if self._anchor_href:
            self._anchor_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(_clean(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self._current_table.append(self._row)
            self._row = None
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1
            if self._table_depth == 0 and self._current_table is not None:
                self.tables.append(self._current_table)
                self._current_table = None
        elif tag == "a" and self._anchor_href:
            self.links.append((_clean(" ".join(self._anchor_text)), self._anchor_href))
            self._anchor_href = ""
            self._anchor_text = []


def _clean(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def extract_cmrl_annual_reports(html: bytes, retrieved_at: str) -> list[dict[str, str]]:
    """CMRL embeds PDF URLs in DearFlip script config instead of anchor hrefs."""
    text = html.decode("utf-8", "replace")
    pattern = re.compile(
        r'<div[^>]*data-title="(annual-report-[^"]+)"[^>]*>(.*?)</div>\s*'
        r'<script[^>]*>.*?"source"\s*:\s*"([^"\s]+\.pdf)"', re.I | re.S
    )
    rows = []
    for slug, label, href in pattern.findall(text):
        label = _clean(re.sub(r"<[^>]+>", " ", label)) or slug.replace("-", " ")
        href = href.replace(r"\/", "/")
        rows.append({"source_id": "cmrl_annual_reports", "organisation": "Chennai Metro Rail Limited",
                     "document_label_as_published": label, "document_url": urllib.request.urljoin("https://ta.chennaimetrorail.org/annual-report/", href),
                     "primary_source_page": "https://ta.chennaimetrorail.org/annual-report/",
                     "source_retrieved_at": retrieved_at, "document_hash": "",
                     "document_download_status": "not_downloaded", "page_count": "", "extracted_text_chars": "",
                     "review_status": "official report link indexed; report contents not yet extracted into project evidence"})
    return rows


def pdf_text_stats(payload: bytes) -> tuple[int, int]:
    """Return PDF page count and selectable text length without OCR or inference."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf to assess PDF text: pip install pypdf") from exc
    reader = PdfReader(BytesIO(payload))
    return len(reader.pages), sum(len(page.extract_text() or "") for page in reader.pages)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch(url: str, timeout: int = 45) -> tuple[bytes, int]:
    """Fetch with normal TLS verification, using curl's system trust if available."""
    curl = shutil.which("curl")
    if curl:
        result = subprocess.run(
            [curl, "--location", "--silent", "--show-error", "--max-time", str(timeout), "--write-out", "\n__HTTP_STATUS__:%{http_code}", url],
            check=False, capture_output=True,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or f"curl exit {result.returncode}")
        marker = b"\n__HTTP_STATUS__:"
        try:
            payload, raw_status = result.stdout.rsplit(marker, 1)
            status = int(raw_status.strip())
        except (ValueError, IndexError):
            raise RuntimeError("curl did not return an HTTP status")
        if status >= 400:
            raise RuntimeError(f"HTTP {status}")
        return payload, status
    request = urllib.request.Request(url, headers={"User-Agent": "CarbonWiseAcademicEvidenceCollector/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), int(response.status)


def _cmrl_header_map(header: list[str]) -> dict[str, int]:
    normalized = [re.sub(r"[^a-z0-9]+", "", value.casefold()) for value in header]
    aliases = {
        "department": ("department",), "reference": ("tenderno", "tendernumber"),
        "title": ("nameofthework", "workname"), "notice_date": ("nitdate", "noticeinvitingtenderdate"),
        "tender_mode": ("modetypeoftender",),
        "contractor": ("nameofthecontractorconsultant", "contractorconsultant"),
        "value": ("awardedcontractvalueincludinggst", "awardedcontractvalue"),
        "award_date": ("contractawardeddate", "awarddate"),
    }
    mapping: dict[str, int] = {}
    for field, options in aliases.items():
        for option in options:
            needle = re.sub(r"[^a-z0-9]+", "", option.casefold())
            if needle in normalized:
                mapping[field] = normalized.index(needle)
                break
    required = {"department", "reference", "title", "notice_date", "contractor", "value", "award_date"}
    if not required.issubset(mapping):
        raise ValueError(f"CMRL table columns not recognized. Headers were: {header!r}")
    return mapping


def parse_cmrl(html: bytes, retrieved_at: str, content_hash: str) -> list[dict[str, str]]:
    parser = TableAndLinkParser()
    parser.feed(html.decode("utf-8", "replace"))
    for table in parser.tables:
        if not table:
            continue
        try:
            col = _cmrl_header_map(table[0])
        except ValueError:
            continue
        old_rows = read_csv(EVIDENCE / "cmrl_awarded_tenders.csv")
        old_by_ref: dict[str, list[dict[str, str]]] = {}
        for old in old_rows:
            old_by_ref.setdefault(normalize_tender_reference(old.get("tender_reference", "")), []).append(old)
        output = []
        parsed_rows = [cells for cells in table[1:] if len(cells) > max(col.values()) and _clean(cells[col["reference"]]) and _clean(cells[col["title"]])]
        ref_frequency: dict[str, int] = {}
        for cells in parsed_rows:
            key = normalize_tender_reference(cells[col["reference"]])
            ref_frequency[key] = ref_frequency.get(key, 0) + 1
        used_old_ids: set[str] = set()
        for n, cells in enumerate(parsed_rows, start=1):
            if len(cells) <= max(col.values()):
                continue
            values = {name: _clean(cells[idx]) for name, idx in col.items()}
            if not values["reference"] or not values["title"]:
                continue
            ref_key = normalize_tender_reference(values["reference"])
            old_match = None
            candidates = old_by_ref.get(ref_key, [])
            available = [candidate for candidate in candidates if candidate.get("evidence_id", "") not in used_old_ids]
            if len(available) == 1 and ref_frequency.get(ref_key) == 1:
                old_match = available[0]
            elif available:
                scored = [(difflib.SequenceMatcher(None, _clean(c.get("work_title", "")).casefold(), values["title"].casefold()).ratio(), c) for c in available]
                score, candidate = max(scored, key=lambda pair: pair[0])
                if score >= .65:
                    old_match = candidate
            stable_source_key = "|".join((ref_key, values["title"], values["award_date"], values["contractor"], values["value"]))
            evidence_id = old_match.get("evidence_id", "") if old_match else "CMRL-AWARD-" + hashlib.sha256(stable_source_key.encode()).hexdigest()[:12].upper()
            if old_match:
                used_old_ids.add(evidence_id)
            explicit_tax = re.search(r"\([^)]*(?:gst|tax)[^)]*\)", values["value"], flags=re.I)
            tax_basis = explicit_tax.group(0).strip("()") if explicit_tax else ""
            currency = "INR" if re.search(r"(?:₹|\bINR\b|\bRs\.?\s*)", values["value"], flags=re.I) else ""
            unit_match = re.search(r"\b(crores?|cr\.?|lakhs?|lacs?)\b", values["value"], flags=re.I)
            value_unit = unit_match.group(1) if unit_match else ("rupee" if currency else "")
            output.append({
                "evidence_id": evidence_id, "tender_reference": values["reference"],
                "work_title": values["title"], "department_or_agency": "Chennai Metro Rail Limited",
                "department": values["department"], "location_as_published": "",
                "record_type": "Awarded tender / contract listing", "tender_notice_date_as_published": values["notice_date"],
                "tender_mode_as_published": values.get("tender_mode", ""),
                "award_date_as_published": values["award_date"], "contractor": values["contractor"],
                "awarded_value_as_published": values["value"],
                "award_value_field_heading": table[0][col["value"]],
                "currency_as_published": currency, "value_unit_as_published": value_unit,
                "tax_basis_as_published": tax_basis,
                "award_status": "Listed in CMRL awarded-tenders table",
                "climate_relevance": "Not assessed from award listing; title and award are not impact evidence",
                "equity_relevance": "Not assessed from award listing; access outcomes are not reported here",
                "completion_status": "Not stated in award listing", "actual_expenditure": "Not reported",
                "primary_source_url": CMRL_URL,
                "interpretation_note": "Award listing is procurement evidence only; not proof of completion, payment, or climate/equity outcome.",
                "source_retrieved_at": retrieved_at, "extraction_method": "HTML table parser; exact cells retained",
                "source_content_sha256": content_hash, "source_row_number": str(n),
            })
        if output:
            return output
    raise ValueError("No CMRL awarded-tenders table with the expected source headers was found")


def collect(offline: bool = False, source_ids: list[str] | None = None) -> dict[str, object]:
    COLLECTION.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    log_path = COLLECTION / "source_run_log.csv"
    logs: list[dict[str, str]] = []
    documents_path = COLLECTION / "source_documents.csv"
    selected = [spec for spec in SOURCE_SPECS if source_ids is None or spec[0] in source_ids]
    selected_ids = {spec[0] for spec in selected}
    prior_documents = read_csv(documents_path)
    documents: list[dict[str, str]] = prior_documents if offline else [d for d in prior_documents if d.get("source_id") not in selected_ids]
    cmrl_rows: list[dict[str, str]] | None = None
    for source_id, agency, url, method, limitation in selected:
        record = {"run_id": run_id, "source_id": source_id, "organisation": agency, "source_url": url,
                  "retrieved_at_utc": _utc_now(), "http_status": "", "content_sha256": "",
                  "extraction_method": method, "records_extracted": "0", "result": "", "limitation_or_error": limitation}
        if offline:
            record["result"] = "skipped_offline"
            logs.append(record)
            continue
        try:
            payload, http_status = fetch(url, timeout=120 if source_id == "gcc_climate_budget_2025_26" else 45)
            content_hash = hashlib.sha256(payload).hexdigest()
            record.update(http_status=str(http_status), content_sha256=content_hash, result="fetched")
            if source_id == "cmrl_awarded_tenders":
                cmrl_rows = parse_cmrl(payload, record["retrieved_at_utc"], content_hash)
                record.update(extraction_method="HTML table parser; exact cells retained", records_extracted=str(len(cmrl_rows)), result="parsed")
            elif source_id in {"gcc_tender_bulletin", "cmrl_annual_reports", "gcc_stormwater_department"}:
                parser = TableAndLinkParser()
                parser.feed(payload.decode("utf-8", "replace"))
                before_count = len(documents)
                if source_id == "cmrl_annual_reports":
                    documents.extend(extract_cmrl_annual_reports(payload, record["retrieved_at_utc"]))
                else:
                    for label, href in parser.links:
                        text = (label + " " + href).casefold()
                        include = ((source_id == "gcc_tender_bulletin" and ("news bulletin" in label.casefold() or "/tender-bulletin/" in href.casefold()))
                                   or (source_id == "gcc_stormwater_department" and any(word in text for word in ("storm water", "stormwater", "drain"))))
                        if include:
                            documents.append({"source_id": source_id, "organisation": agency, "document_label_as_published": label,
                                              "document_url": urllib.request.urljoin(url, href), "primary_source_page": url,
                                              "source_retrieved_at": record["retrieved_at_utc"], "document_hash": "",
                                              "document_download_status": "not_downloaded", "page_count": "", "extracted_text_chars": "",
                                              "review_status": "document link indexed; contents not yet extracted into project records"})
                # Preserve order while removing duplicate anchors for the same official file.
                unique_docs = []
                seen_urls = set()
                for doc in documents:
                    if doc["source_id"] == source_id and doc["document_url"] in seen_urls:
                        continue
                    if doc["source_id"] == source_id:
                        seen_urls.add(doc["document_url"])
                    unique_docs.append(doc)
                documents = unique_docs
                indexed = len(documents) - before_count
                record["document_links_indexed"] = str(indexed)
                record.update(extraction_method="HTML anchor inventory only; no project row inferred", records_extracted=str(sum(d["source_id"] == source_id for d in documents)))
                if source_id == "gcc_tender_bulletin":
                    record["records_extracted"] = "0"
                    record["limitation_or_error"] = "Weekly bulletin PDF links indexed; contents are not parsed into individual tenders by this run. Review/import notices individually."
                elif source_id == "cmrl_annual_reports":
                    record["records_extracted"] = "0"
                    record["extraction_method"] = "source-specific DearFlip annual-report PDF link parser; report content not parsed"
                    record["limitation_or_error"] = "Annual report links indexed; report contents are not parsed into project evidence by this run."
                else:
                    record["records_extracted"] = "0"
            elif source_id in {"gcc_ongoing_projects", "gcc_completed_projects"}:
                record["extraction_method"] = "page retrieval only; interactive filters not submitted"
                record["result"] = "manual_filter_required"
            elif source_id == "tn_eprocurement":
                record["extraction_method"] = "portal landing page only; no search results assumed"
                record["result"] = "manual_import_required"
            elif source_id == "gcc_climate_budget_2025_26":
                record["extraction_method"] = "PDF availability/hash check; existing curated crosswalk retained"
                record["result"] = "source_available_existing_register_retained"
        except Exception as exc:  # logged per source so one outage never hides other results
            record["result"] = "failed"
            record["limitation_or_error"] = f"{type(exc).__name__}: {exc}"
        logs.append(record)
        time.sleep(.35)

    if cmrl_rows is not None:
        fields = list(cmrl_rows[0]) if cmrl_rows else []
        write_csv(EVIDENCE / "cmrl_awarded_tenders.csv", fields, cmrl_rows)
    run_fields = ["run_id", "source_id", "organisation", "source_url", "retrieved_at_utc", "http_status", "content_sha256", "extraction_method", "records_extracted", "document_links_indexed", "result", "limitation_or_error"]
    history = read_csv(log_path)
    # Correct early pre-release log semantics: these runs counted anchors as
    # records before document-link counts were separated from project rows.
    for old in history:
        if old.get("source_id") == "gcc_tender_bulletin" and old.get("records_extracted") == "262" and not old.get("document_links_indexed"):
            old["records_extracted"] = "0"
            old["document_links_indexed"] = "262"
            old["extraction_method"] = "legacy HTML anchor inventory; no project-row extraction"
            old["limitation_or_error"] = "262 links are weekly bulletin documents, not extracted individual tenders; manual PDF review required."
        if old.get("source_id") == "cmrl_annual_reports" and old.get("records_extracted") == "13" and not old.get("document_links_indexed"):
            old["records_extracted"] = "0"
            old["document_links_indexed"] = "0"
            old["result"] = "superseded_initial_generic_pdf_scan"
            old["extraction_method"] = "legacy generic PDF-link scan; not a source-specific annual report parser"
            old["limitation_or_error"] = "The initial 13-link count included unrelated page PDFs; superseded by the source-specific parser, which identified 12 annual-report links."
    seen_run_sources = {(r.get("run_id", ""), r.get("source_id", "")) for r in history}
    history.extend(r for r in logs if (r["run_id"], r["source_id"]) not in seen_run_sources)
    write_csv(log_path, run_fields, history)
    write_csv(COLLECTION / "source_catalog.csv",
              ["source_id", "organisation", "source_url", "configured_method", "known_limitations"],
              [{"source_id": s[0], "organisation": s[1], "source_url": s[2], "configured_method": s[3], "known_limitations": s[4]} for s in SOURCE_SPECS])
    if not offline:
        write_csv(documents_path,
                  ["source_id", "organisation", "document_label_as_published", "document_url", "primary_source_page", "source_retrieved_at", "document_hash", "document_download_status", "page_count", "extracted_text_chars", "review_status"], documents)
    summary = build()
    return {"run_id": run_id, "sources": logs, "source_document_links_indexed": len(documents), "evidence_audit": summary}


def assess_bulletin_pdfs(limit: int = 1) -> list[dict[str, str]]:
    """Sample recent bulletin PDFs, recording whether text extraction is possible."""
    if limit < 1 or limit > 10:
        raise ValueError("bulletin assessment limit must be between 1 and 10")
    doc_path = COLLECTION / "source_documents.csv"
    docs = read_csv(doc_path)
    candidates = [d for d in docs if d.get("source_id") == "gcc_tender_bulletin"]
    candidates.sort(key=lambda d: d.get("document_label_as_published", ""), reverse=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    assessments: list[dict[str, str]] = []
    log_path = COLLECTION / "source_run_log.csv"
    logs = read_csv(log_path)
    for document in candidates[:limit]:
        retrieved_at = _utc_now()
        row = {"run_id": run_id, "source_id": "gcc_tender_bulletin_pdf_assessment",
               "organisation": "Greater Chennai Corporation", "source_url": document["document_url"],
               "retrieved_at_utc": retrieved_at, "http_status": "", "content_sha256": "",
               "extraction_method": "pypdf selectable-text feasibility check; no OCR or tender parsing",
               "records_extracted": "0", "document_links_indexed": "0", "result": "", "limitation_or_error": ""}
        try:
            payload, status = fetch(document["document_url"], timeout=120)
            digest = hashlib.sha256(payload).hexdigest()
            pages, chars = pdf_text_stats(payload)
            row.update(http_status=str(status), content_sha256=digest)
            if chars == 0:
                row["result"] = "no_selectable_text_ocr_or_manual_review_required"
                row["limitation_or_error"] = f"Downloaded {pages}-page bulletin; pypdf extracted 0 text characters. No tender rows inferred."
                document["review_status"] = f"Downloaded {retrieved_at}; {pages} pages; no selectable text; OCR/manual extraction required; no tender rows created."
            else:
                row["result"] = "selectable_text_available_manual_parser_review_required"
                row["limitation_or_error"] = f"Downloaded {pages}-page bulletin with {chars} text characters; no tender rows inferred by this feasibility check."
                document["review_status"] = f"Downloaded {retrieved_at}; {pages} pages; {chars} selectable text characters; tender extraction/review still required."
            document.update(document_hash=digest, document_download_status=f"HTTP {status}; downloaded for text assessment",
                            page_count=str(pages), extracted_text_chars=str(chars), source_retrieved_at=retrieved_at)
        except Exception as exc:
            row["result"] = "failed"
            row["limitation_or_error"] = f"{type(exc).__name__}: {exc}"
            document["document_download_status"] = row["limitation_or_error"]
        assessments.append(row)
        logs.append(row)
    write_csv(doc_path,
              ["source_id", "organisation", "document_label_as_published", "document_url", "primary_source_page", "source_retrieved_at", "document_hash", "document_download_status", "page_count", "extracted_text_chars", "review_status"], docs)
    log_fields = ["run_id", "source_id", "organisation", "source_url", "retrieved_at_utc", "http_status", "content_sha256", "extraction_method", "records_extracted", "document_links_indexed", "result", "limitation_or_error"]
    write_csv(log_path, log_fields, logs)
    return assessments


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Do not retrieve network sources; rebuild index and audit only.")
    parser.add_argument("--source", action="append", choices=[s[0] for s in SOURCE_SPECS], help="Refresh only this source (repeatable); preserves other source-document inventories.")
    parser.add_argument("--assess-bulletins", type=int, default=0, metavar="N", help="Download up to N latest indexed GCC bulletin PDFs and report whether selectable PDF text is available; never creates tender rows.")
    args = parser.parse_args()
    result = collect(offline=args.offline, source_ids=args.source)
    if args.assess_bulletins:
        result["bulletin_pdf_assessments"] = assess_bulletin_pdfs(args.assess_bulletins)
    print(json.dumps(result, indent=2, ensure_ascii=False))
