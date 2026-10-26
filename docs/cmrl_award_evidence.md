# Chennai Metro Rail Limited award evidence

## What this register contains

`data/evidence/cmrl_awarded_tenders.csv` records 97 rows from the Chennai Metro Rail Limited (CMRL) [official awarded-tenders listing](https://chennaimetrorail.org/awarded-tenders/) retrieved on 2026-10-26. The source table has 96 normalized tender references because `CMRL/PHASE-11/SYS/ASA11/2023` appears twice with different award details. Both rows are retained and flagged for review. Each row preserves exact work-title wording, published department, tender number, notice date, mode/type, contractor, award-value string, date, source URL, collection timestamp, and source-page SHA-256. The original award-value column heading is retained separately from row-level tax wording.

A later refresh attempt at 2026-10-26 12:54 UTC timed out before receiving the page body. The last successful source response (12:50 UTC) and its 97 parsed rows were preserved; both attempts remain visible in `data/collection/source_run_log.csv`.

The rows are procurement evidence records. They are not 97 independently verified completed projects. Some refer to design, feasibility, audit, or DPR services; others describe construction, equipment, systems, and support services. Different packages may belong to the same larger metro programme. Do not sum the contract values into a project budget or count each package as a separate completed project. Location, climate relevance, and equity outcomes are not independently parsed from these titles.

## What the source does and does not establish

- **Supported by the page:** CMRL publishes a matching tender reference, work description, contractor, award value, and award date for these entries.
- **Not established by this source:** payment or actual expenditure, physical completion, operating performance, project-level emissions reductions, population served, or distributional equity outcomes.
- **Climate and equity:** the source listing does not provide GHG calculations or measured access/equity outcomes. These fields are marked as not stated; no benefits are imputed from the work descriptions.
- **Amounts:** retain the value exactly as published. The page heading mentions GST while some row strings explicitly qualify GST; both the source heading and exact row text are retained. Values are not normalized or summed.
- **Dates:** retain the date text in the source's displayed format rather than infer a different locale.

This register complements the 23-row GCC Climate Budget crosswalk and the separate three-package drainage award cross-check. It does not modify or replace the supplied GCC starter CSV. In the normalized index the rows remain contextual procurement evidence and are not eligible for project portfolio optimization.

## How to reproduce the register

From the repository root, run `python3 src/collect_sources.py`. The collector retrieves the official page with verified HTTPS, checks for the expected table headers, preserves exact text, records a timestamp and SHA-256 page hash, and replaces the current table snapshot only if parsing succeeds. The hash permits later integrity comparison, but it is not an archived copy of the live page. To rebuild only the index and validation outputs, run `python3 src/collect_sources.py --offline`.
