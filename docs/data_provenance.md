# GCC starter data provenance and quality

## Source preservation and version

The supplied `projects_real_starter.csv` is copied byte-for-byte to `data/raw/projects_real_starter.csv`. The source has 23 records and 14 columns. Each pipeline run writes a dated derived snapshot into `data/derived/YYYY-MM-DD/`; reruns do not overwrite previous dates. The source is never overwritten.

On 2026-10-25, all 23 IDs were cross-referenced to the official GCC *Climate Budget Report 2025-26*. The source PDF is available from the [official GCC site](https://www.chennaicorporation.gov.in/gcc/pdf/ClimateBudget2025-2026.pdf); it is retained in the local project but not stored in this GitHub repository. Page-level evidence and scope notes are in `data/evidence/gcc_climate_budget_evidence.csv` and `docs/gcc_climate_budget_evidence.md`. The report confirms these data are published by GCC; it does not make every status independently audited or every estimate a measured outcome.

The evidence room separately includes 25 CMRL tender and consultancy awards from CMRL's [official awarded-tenders listing](https://chennaimetrorail.org/awarded-tenders/). These are procurement records with published references, titles, award dates, contractors, and values. They are not a count of 25 completed projects, and they do not establish payments, actual expenditure, GHG savings, or equity outcomes. See `data/evidence/cmrl_awarded_tenders.csv` and `docs/cmrl_award_evidence.md`.

## Meaning of statuses

- `reported_estimate`: the starter labels the cost as estimated and the GCC report calls it an overall project/programme cost; this is not an awarded value or actual expenditure.
- `GCC primary report`: values and status are confirmed as published by GCC, not independently audited by this project.
- `GCC estimate arithmetic reproduced`: selected formulas have been independently recalculated from the report inputs; field assumptions and realized outcomes remain unvalidated.
- `unknown`: the starter does not provide a defensible numeric input.
- `official_tender_notice_and_ADB_award_fields_verified`: the official eProcurement page verifies tender notice fields; ADB's project page lists a matching contract award. It does not verify expenditure or completion.
- `model_ready`: false unless cost, carbon, resilience, geography, and provenance satisfy the current model's stated assumptions. An empty model-ready file is an intentional blocked-ingestion result.

## Record-level findings

- R04 stormwater is a programme record: ₹5,553.3 crore is reported for 236 packages across schemes. Dividing by 236 gives an arithmetic average only; it is not a verified package cost. Do not include this aggregate alongside child tenders.
- R05 ponds is also an aggregate: 60 packages, ₹140.55 crore. It is not a single project cost.
- R01's very large annual methane estimate is now cross-referenced to GCC's CIRIS appendix. GCC uses 37.7 lakh MT as the FY2025-26 removal scope and explicitly labels 41,28,416 tCO2e as a potential estimate requiring on-ground investigation; site total legacy waste and annual removal are different scopes. The starter also mentions a 73.78 lakh figure whose source/page is not supplied, so it remains an unresolved source-note discrepancy, not evidence that the report's 94.09 lakh total and 37.7 lakh annual plan are the same measure.
- R13 LED cost refers to 8,083 fittings supplied over 2023-25, while its carbon estimate refers to 1,610 proposed fittings for 2025-26. They are not a matched cost/impact pair.
- R16-R18 are labelled CNG, not EV. Their calculated avoided-emission values remain estimates until distance, fuel factors, vehicle counts, and comparison basis are checked against sources.
- Most rows have no carbon estimate; all lack a common, measured resilience benefit input. Cost values are programme/project totals as reported, not verified expenditure. Geographic fields are free-text location descriptions rather than validated zone identifiers.

The pipeline retains all 23 input rows and writes reasoned exclusions. It does not impute unknown values or promote an estimate to fact. Source references are now cross-linked to GCC report pages; selected calculation outputs are independently reproduced in `results/evidence/gcc_report_calculation_checks.csv`. Official tender and ADB award information remains separate: the three ADB award values are preserved in USD; actual expenditure is unknown.
