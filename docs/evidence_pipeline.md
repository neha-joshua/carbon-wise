# Evidence pipeline and audit

## What is in the evidence system now

The source-specific registers remain separate and are not overwritten by normalization:

| Register | Current source records | Unit and interpretation |
|---|---:|---|
| `data/evidence/gcc_climate_budget_evidence.csv` | 23 | One page-cited Climate Budget crosswalk row per supplied starter ID (R01–R23); this is not a census of GCC works. |
| `data/evidence/cmrl_awarded_tenders.csv` | 97 rows on the 2026-10-26 source retrieval | One exact source table row per CMRL award listing row. Repeated tender numbers remain separate and enter duplicate review. |
| `data/tenders/chennai_drainage_tender_packages.csv` | 3 | Three tender notices matched by exact package title to ADB award entries. The normalized index retains the tender notice and award as separate evidence documents (6 rows). |

The refreshed CMRL count and all other generated counts are written to `data/evidence/audit_summary.json`; do not assume a target count. At the 2026-10-26 collection, the current CMRL static table returned 97 source rows and 96 normalized tender references, including one repeated reference. Those are award-list records, not 97 unique built assets. The page hash and retrieval timestamp are stored per row and in the run log; the source page itself is not archived by this script.

`normalized_evidence_index.csv` is a *document index*. It keeps a GCC report crosswalk row, each CMRL award-list row, each TN tender notice and each ADB award as distinct evidence documents. A project count is deliberately reported as unresolved until a reviewed project crosswalk exists; `distinct_nonblank_project_identifiers` is not a unique project count. GCC starter IDs, tender IDs and CMRL awards identify different units and cannot be added as if they were disjoint projects.

## Repeat a source run

From the repository root:

```bash
python3 src/collect_sources.py
```

The collector uses ordinary verified HTTPS via `curl` (or Python's verified TLS as a fallback), pauses briefly between the eight configured endpoints, records retrieval time and SHA-256 content hash, and writes `data/collection/source_run_log.csv`. A static HTML table parser refreshes CMRL rows only after finding the expected table headers. If retrieval or parsing fails, the prior CMRL register is preserved and the source failure is logged. It never disables TLS checks.

The collector indexes linked GCC tender-bulletin and CMRL annual-report documents in `data/collection/source_documents.csv`; it does not turn a weekly bulletin or annual report into project rows without item-level extraction. Run `python3 src/collect_sources.py --source gcc_tender_bulletin --assess-bulletins 1` to download the latest indexed bulletin and check whether it has selectable text. This check never parses tenders or uses OCR. The 2026-10-22 bulletin sample is a 28-page PDF with zero selectable text, so OCR/manual extraction is required before reliable notice rows can be added. The GCC ongoing/completed portals require interactive filter selections. A portal landing page fetch does not count as project collection. Tamil Nadu eProcurement search and downloadable tender documents may require a browser session or manual review. Their run-log rows make that outstanding work visible.

To rebuild from already-reviewed files without network access:

```bash
python3 src/collect_sources.py --offline
```

To refresh one or more sources without replacing other source-document link inventories, pass repeatable source IDs, for example `python3 src/collect_sources.py --source cmrl_awarded_tenders --source cmrl_annual_reports`. The index builder writes four reproducible outputs under `data/evidence/`: the normalized index, duplicate-review pairs, validation issues, and an audit summary. It retains all source rows and never resolves a duplicate automatically.

## Manual import

Copy `data/evidence/manual_import_template.csv` to `data/evidence/manual_import.csv` and add one row per evidence document. Keep the source's exact title and date/value strings. Provide a direct primary-source URL, stable evidence ID, extraction method, and limitations. Leave unsupported facts blank. Do not add a synthetic row just to reach a count. Imports default to `pending_manual_verification` until reviewed. Run the offline command to rebuild the index and reports.

When one project has several documents, give each document a separate `evidence_id`, use a reviewed common `project_id` only when the identity is supported, and populate `associated_evidence_ids`. If project identity is uncertain, leave it blank and add a pair to the duplicate-review queue rather than merging.

## Audit results and known limits

`audit_summary.json` contains actual document counts, source/agency/status counts, nonblank field coverage, duplicate counts and validation issue counts. It explicitly withholds the unique-project count. `duplicate_review.csv` includes ambiguous exact normalized tender-reference collisions and cross-source fuzzy title candidates (similarity threshold 0.86); documented notice/award pairs linked by the reviewed drainage crosswalk are retained but are not mislabeled as duplicates. A candidate is a prompt for human review, not proof of duplication. Source URL syntax, required provenance fields, date formats, duplicate IDs, and some status/detail inconsistencies are checked by `evidence_pipeline.py`.

Current key coverage: all 126 indexed rows have an evidence ID, record description, agency, source type, primary URL, status, verification note, and limitation. Exact source wording is present for 103 records; the 23 GCC records instead keep the supplied project title separate from the source activity number because the crosswalk has no verbatim report title column. Only six records have a separately stated location; none has a validated zone, division, or coordinate in the normalized index. Twenty-three records carry delivery/progress text and seven carry a GHG quantity/method from the GCC register. No normalized record reports actual expenditure. Currency is left blank where the official CMRL cell does not state it; amounts are never combined or converted. These figures update on every rebuild.

The GCC Climate Budget register has 23 rows because it was intentionally made as a crosswalk for the 23 rows in the supplied starter file. That does not imply that GCC has only 23 projects. The CMRL award register grows when the official page's static table grows. Its rows establish what CMRL lists as awarded, not payment, delivery, measured emissions, or distributional benefit. Tender award values remain in their source currency and text; unparseable amounts are not numerically coerced.

The evidence count is not a performance measure. The pipeline does not meet the 150–250 planning target by fabrication. GCC source portals with filters, tender-bulletin PDF contents, CMRL annual-report tables, and TN eProcurement records need additional item-level extraction and review. No record becomes eligible for portfolio optimization unless it has compatible, validated cost, climate, resilience, equity, and geographic inputs; the current synthetic scenario lab remains separate.

## Current source access matrix

The current run log is the source of truth for retrieval success and timestamps. On 2026-10-26 12:52 UTC, the GCC Climate Budget PDF returned HTTP 200; its downloaded SHA-256 matched the supplied local report copy byte-for-byte. The collector hashes the PDF in memory but does not commit or store another downloaded copy. It distinguishes evidence rows extracted from document links indexed. The CMRL annual-report PDFs are embedded as DearFlip viewer configuration, so their official report links require a source-specific parser. The current collection found 12 annual-report links. It also indexed weekly GCC tender bulletin PDF links; those PDFs are not automatically parsed into individual tenders. Source methods and limits are:

| Source | Collection method | What counts as a record |
|---|---|---|
| GCC ongoing/completed project portals | Page retrieval; filters not submitted automatically | Only a result row captured with its filter selections and direct source evidence |
| GCC tender bulletin | Linked-document inventory | Tender notice records after item-level review; bulletin PDFs are not project rows |
| GCC Climate Budget 2025–26 | Existing page-cited manual crosswalk | The 23 retained activity/source crosswalk rows |
| GCC storm-water department | Page/link inventory | Department background unless a specific project source is found |
| Tamil Nadu eProcurement | Landing-page check plus manual import route | Individual notice/award documents with official IDs and direct URLs |
| CMRL awarded tenders | Static table parser | One published award row; repeated tender IDs retained |
| CMRL annual reports | Annual-report link inventory | Project/outcome observations only after page- and table-level review |

## Tests

Run:

```bash
python3 -m unittest discover -s tests -v
python3 src/collect_sources.py --offline
```

The tests cover header-driven collection parsing, source and index preservation, ID/date/URL validation, and exact/fuzzy duplicate review. The collector's live network path should be run when preparing an evidence refresh; offline tests do not imply that a website was reachable.
