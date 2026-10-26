# Multi-city catalogue collection

CarbonWise targets Chennai, Mumbai, Bengaluru, Delhi, Hyderabad, Kolkata, Pune and Ahmedabad. The current collector performs paginated metadata discovery through the public OpenCity CKAN API. Other national, municipal, climate and geospatial portals are recorded as configured leads; their datasets are not reported as retrieved until a specific supported integration has actually run.

## Run it

From the repository root:

```bash
python src/multicity_catalog.py
```

This refreshes OpenCity metadata only. To limit the run, repeat a city ID:

```bash
python src/multicity_catalog.py --city chennai --city mumbai
```

The summary still reports all target cities from the saved inventory. Rebuild reports without contacting sources with `python src/multicity_catalog.py --report-only`.

Downloads are opt-in. Start with a small cap after reviewing the catalogue:

```bash
python src/multicity_catalog.py --city chennai --download --max-resources 3
```

The collector accepts HTTPS only, uses verified TLS, retries transient failures, limits each response to 50 MiB by default, computes SHA-256, preserves changed raw versions, and performs basic CSV/TSV/JSON/GeoJSON/Excel/KML/KMZ/ZIP/PDF checks. It does not bypass login, CAPTCHA, paywalls or other access controls. `--max-resources` bounds download attempts; it does not guarantee that a source is suitable for use.

## Outputs

- `data/metadata/dataset_inventory.csv`: resource-level search metadata, source URL, licence fields (unknown when not supplied), retrieval state, hash and local path.
- `data/metadata/source_registry.csv`: portal and official municipal homepage leads, clearly distinguished from verified dataset integrations.
- `data/metadata/city_dataset_coverage.csv`: city-by-source status matrix.
- `data/metadata/resource_validation_report.csv`: downloaded file hashes, CSV row/null/duplicate counts, and basic KML feature counts.
- `data/metadata/collection_manifest.jsonl`: append-only retrieval/download history, including old hashes when a source file changes.
- `data/metadata/collection_summary.json`: computed run totals.
- `data/model_ready/multicity_candidates.csv`: header-only unless future eligibility checks support actual candidates.
- `data/raw/catalog_resources/`: downloaded original bytes, indexed by SHA-256.
- `data/geospatial/`: derived GeoJSON conversions of source KML, carrying source dataset IDs and hashes.
- `reports/multicity_collection_report.md`: human-readable totals and limitations.

Catalogue entries are discovery leads. A title containing a city name is not proof that the data geography matches the municipal boundary. Validate each resource's licence, coordinates or geography, reference period, schema and quality before analytical use. A downloaded file passing a format sanity check is not necessarily accurate, complete or reusable. Unknowns are retained as unknown; nothing is imputed into candidate investment outcomes.

## Current analytical boundary

The existing Chennai evidence and generated sample planner remain separate. No cross-city optimizer is populated from catalogue metadata. A real investment candidate needs traceable cost, supported climate or service outcome, location crosswalk and comparable units. Keep procurement awards distinct from completion and expenditure; keep budget allocations distinct from realised outcomes; keep IMD's access-managed historical data distinct from public, freely downloadable resources.

## Reproducibility and tests

The collector uses Python standard-library modules. Its tests mock API responses and validate pagination, metadata retention, file checks and conservative model eligibility:

```bash
python -m unittest discover -s tests -v
```

No tests call live services. Run the collector separately when refreshing current catalogue metadata.
