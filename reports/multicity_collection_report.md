# CarbonWise multi-city catalogue collection report

Generated UTC: 2026-10-26T20:22:41Z

> This report describes catalogue search metadata, not a validated multi-city analytical dataset.

## Measured run totals

- Target cities: 8
- Cities with city-named catalogue metadata: 8
- Cities with a downloaded original file: 6
- Source catalogues queried: 1 of 9 configured
- Unique dataset packages: 764
- Resource rows (a dataset may expose multiple files): 6122
- Rows with a resource URL: 6099
- Successful or hash-identical downloads: 14
- Downloaded resources content-audited: 14
- Raw CSV rows (not pooled across incompatible schemas): 1001
- CSV missing cells: 776; duplicate rows: 0
- Downloaded CSV climate time-series rows detected by field names: 0
- KML geographic features inventoried and converted: 4772
- Project/procurement rows extracted by this collector: 0
- Resource downloads not attempted: 6106; retained download failures: 2
- Downloaded/verified bytes represented in inventory: 7897111
- Model-ready investment candidates: 0

## City search results

| City | Unique packages | Resource rows | Downloaded | Basic-format valid | Status |
|---|---:|---:|---:|---:|---|
| Chennai | 110 | 891 | 9 | 3 | city_name_in_dataset_identity; geography, time and licence require validation |
| Mumbai | 55 | 571 | 1 | 1 | city_name_in_dataset_identity; geography, time and licence require validation |
| Bengaluru | 415 | 3298 | 0 | 0 | city_name_in_dataset_identity; geography, time and licence require validation |
| Delhi | 48 | 444 | 1 | 1 | city_name_in_dataset_identity; geography, time and licence require validation |
| Hyderabad | 48 | 317 | 0 | 0 | city_name_in_dataset_identity; geography, time and licence require validation |
| Kolkata | 28 | 249 | 1 | 1 | city_name_in_dataset_identity; geography, time and licence require validation |
| Pune | 56 | 294 | 1 | 1 | city_name_in_dataset_identity; geography, time and licence require validation |
| Ahmedabad | 4 | 58 | 1 | 1 | city_name_in_dataset_identity; geography, time and licence require validation |

## Interpretation and gaps

- Catalogue search hits are leads, not verified city coverage.
- OpenCity city query does not guarantee geographic containment.
- Licence, date range, data quality and relevance require per-resource review.
- Other catalogues remain configured discovery leads until a documented, permitted integration is run.

No OpenCity search result was promoted to model-ready because catalogue metadata does not establish compatible investment costs, measured outcomes, verified project geography, or comparable evidence. Resource-level license, dates, spatial coverage, schema and content still need quality review.

The detailed registry is `data/metadata/dataset_inventory.csv`; configured source leads are `data/metadata/source_registry.csv`; the city-by-source matrix is `data/metadata/city_dataset_coverage.csv`. Downloaded originals, if any, are retained under `data/raw/catalog_resources/` and are indexed by SHA-256 in the inventory.
