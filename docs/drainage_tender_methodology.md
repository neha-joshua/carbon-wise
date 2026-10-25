# Chennai drainage tender collection and splitting

## Scope and distinction

The GCC Climate Budget 2025-26 reports ₹5,553.3 crore and 236 stormwater-drain work packages across schemes. This is a programme-level report, not the cost of one tender and not proof that each of the 236 packages maps to the same procurement programme. The derived tender table therefore keeps the relationship to that budget programme unconfirmed and does not create 236 synthetic rows.

## Official records captured

`data/tenders/chennai_drainage_tender_packages.csv` contains three distinct official TN eProcurement tender IDs: `2020_GCC_184631_1` (Package 28), `2020_GCC_177690_1` (Package 38), and `2020_GCC_177793_1` (Package 43). Official pages expose titles, references, publication dates, and (for Packages 28 and 43) tender value as NA. Historic bid document downloads have expired.

The Asian Development Bank's primary project page lists contract awards under Loan 4113 for all three matching package titles. It reports award dates, contractors, total contract amounts, and ADB-financed portions: Package 28, 1 February 2022, M/s P&C Projects (P) Ltd, US$6,911,749.81 (ADB share US$4,178,677.21); Package 38, 29 January 2022, Sakthi Constructions, US$15,786,158.05 (ADB share US$7,705,235.25); Package 43, 30 January 2022, Sri Sivaram & Co., US$8,078,589.82 (ADB share US$4,864,373.52). Amounts are retained in original USD; none is converted to INR or treated as actual expenditure. The exact package-title match links each award to its tender notice; parent program is ADB project 49107-009 / Loan 4113, distinct from the wider GCC Climate Budget aggregate.

Award values are supported, but actual expenditure, completion status, package-level quantities, street chainage, and exact zone remain unknown. “Kosasthalaiyar basin” comes from each title and is not a zone crosswalk. These are awarded contracts, not evidence of completed works or paid expenditure.

## Repeatable ingestion and duplicate rules

Re-run `python3 src/data_pipeline.py` after editing the reviewed tender CSV. The validation step treats official tender ID as the unique key, flags blank/duplicate IDs, and does not deduplicate by title or street. If an ID occurs more than once, retain source rows for review and resolve the duplicate explicitly; do not merge packages based on similar descriptions.

## Manual retrieval checklist

For each tender ID, retrieve from the TN eProcurement portal or GCC:

1. NIT, technical bid, drawings, BOQ, price bid and all corrigenda.
2. GCC tender evaluation result / Letter of Acceptance / award notice, to cross-check the ADB award record against the tender file.
3. Work order and agreement, including package-level scope, locations, zone/division/unit, streets/chainage, quantities and units.
4. Completion certificate, measurement book/final bill, expenditure and completion date if available.
5. Parent scheme/funding source and evidence linking the package to the Climate Budget's 236-package aggregate.

The official TN eProcurement pages state the historic download window has expired. Current manual retrieval may require portal login or a GCC records request. Until records are obtained, those columns remain blank and none of the entries enters the optimiser.
