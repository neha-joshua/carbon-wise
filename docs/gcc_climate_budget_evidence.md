# GCC Climate Budget: project evidence and calculation audit

## Source and method

The source document is the Greater Chennai Corporation (GCC), *Climate Budget Report 2025-26*, available at the GCC official PDF URL below. The PDF is retained in the local project but not stored in this GitHub repository. Its PDF footer page numbers are used in this register. Every starter ID R01-R23 is cross-referenced to the matching activity number and report page in `data/evidence/gcc_climate_budget_evidence.csv`.

The register transcribes GCC-reported cost, status, physical quantity/progress, and annual GHG estimates. A primary report confirms that GCC published the values; it does not make project progress independently audited, costs into expenditure, or model estimates into measured emissions. Free-text site names remain free text; no spatial crosswalk has been inferred.

Official source: <https://www.chennaicorporation.gov.in/gcc/pdf/ClimateBudget2025-2026.pdf>

## Evidence that can be presented now

- GCC's report describes 23 of the source projects/programmes, with activity numbers, budget categories, current status, cost labels and physical delivery information. The report explicitly classifies items as direct quantified actions (DA-Q) or direct unquantified actions (DA-UQ).
- Complete Streets: 11.6 km planned and 5 km reported complete across six neighbourhoods (printed p.45). The 43.1% shown in the dashboard is the transparent arithmetic ratio 5 / 11.6, not a separately measured progress indicator.
- Villivakkam Tank redevelopment: 78% physical progress, planned 50,000 m3 pond over 8.5 acres (printed p.46).
- Chinna Nolambur bridge: 55% complete; GCC describes raising the bridge from 3 m to 6 m (printed pp.49-50).
- GCC reports deployment/operation or handover in 2024-25 for 15 mini trucks, 3 recovery vehicles, and 6 water tankers (printed pp.47-48). These are CNG vehicles, not EVs.
- SWD programme evidence: 236 work packages, ₹5,553.3 crore programme cost, over 1,168 km built, stated 68-72 mm/hour capacity, and expected 50 lakh residents served (printed p.42). These are programme-level claims, not attributes of the three ADB tender packages.
- Pond programme: the detailed project table says 60 ponds and 1,496,916.428 m3 combined storage, expected to benefit over 8 lakh residents (printed p.42).
- Complete Streets, waste, vehicle, lighting and crematorium GHG figures are explicitly estimates in the GCC report, not measured outcome data.

## Reproduced arithmetic

`src/verify_gcc_calculations.py` recalculates five published arithmetic values and writes `results/evidence/gcc_report_calculation_checks.csv`:

| Starter ID | GCC-reported value | Recalculation | What remains an assumption |
|---|---:|---|---|
| R02 windrow compost | 33,555 tCO2e/year | 39,964 - 6,409 | 2 x 50 MT/day, 365 days, 100% utilisation, waste composition |
| R13 LEDs | 250.34 tCO2e/year | 54.57 + 16.37 + 179.40 | 1,610 proposed units, operating hours and grid factor; cost is for a separate 8,083-unit 2023-25 scope |
| R16 CNG mini trucks | 25.974 tCO2e/year | (0.307 - 0.122) x 9,360 km x 15 / 1,000 | Annual distance and diesel replacement counterfactual |
| R17 CNG recovery vehicles | 4.14 tCO2e/year | (0.770 - 0.655) x 12,000 km x 3 / 1,000 | Annual distance and diesel replacement counterfactual |
| R18 CNG water tankers | 9.7344 tCO2e/year | (1.302 - 1.250) x 31,200 km x 6 / 1,000 | Annual distance and diesel replacement counterfactual |

Reproducing the arithmetic validates the formula application only; it does not validate field activity, fuel use, emission factors or realised reductions. R01 and R21 estimates are left as GCC-published estimates because their full input chains have not been independently reproduced in this implementation.

## Scope and consistency flags

- The stormwater entry is one programme-level aggregate across 236 packages and multiple funders. It must not be allocated as a package value or added to child tender values.
- The report's narrative summary says 44 ponds, while its project table specifies 60 pond packages. The register keeps the detailed table value and flags the difference; the report does not explain whether the two counts refer to different scopes/years.
- The report's summary says over 240 km of drains are being constructed, while its detailed programme text says over 1,168 km have been built. Those are different tenses and likely different scopes; do not combine into one progress metric.
- Biomining site-level waste totals (6,652,505 MT at Kodungaiyur and 2,756,810.42 MT at Perungudi) are distinct from the 3,770,546.1 MT FY2025-26 removal plan used for GCC's 4,128,416 tCO2e potential-reduction estimate (printed pp.39-40, 54). GCC explicitly says an on-ground investigation is required to determine exact savings.
- The LED cost is for 8,083 fittings in 2023-25; the 250.34 tCO2e estimate is for 1,610 proposed fittings in FY2025-26. They are not one cost/impact observation.
- Kadapakkam Lake capacity appears as 1.1 to 2.2 cubic metres in GCC text. This unit is preserved as published but requires confirmation from the engineering project document.
- The pedestrian bridges activity reports ₹4.27 crore for two projects while narrating several distinct structures and different progress states. The cost-to-asset crosswalk is not supplied.

## What the evidence does not support

The GCC report is enough to present a source-backed register of project descriptions, budgets, status, quantities and modelled GHG estimates. It is not enough to claim actual expenditure, independently audited progress, observed GHG reductions, project-level resilience outcomes, or a complete equitable investment ranking. Those require work orders/payment statements, measurement reports, validated project-to-zone population crosswalks, and compatible benefit observations.
