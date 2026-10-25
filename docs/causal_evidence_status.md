# Causal evidence status and study design

## Finding as of 25 October 2026

The current CarbonWise source pack does **not** contain an independently verified causal estimate showing that a project caused a reduction in flooding, emissions, or harm. This is a finding about the reviewed source materials, not proof that no relevant research exists anywhere.

For the ADB Integrated Urban Flood Management for the Chennai–Kosasthalaiyar Basin Project (49107-009), ADB currently lists the project as active/ongoing and says the intended outcome is expected on completion, targeted for 2027. The project page's “Evaluation Documents” section says none are currently available. ADB's 2021 approval report's 1.9 million exposed residents is a project target, not an observed effect. The GCC Climate Budget 2025–26 describes identifying indicators and establishing a system to monitor and evaluate project impact over future years; it calls this an initial step.

Primary sources:

- [ADB project status, implementation, and evaluation-document listing](https://www.adb.org/projects/49107-009/main)
- [ADB 2021 Report and Recommendation of the President](https://www.adb.org/projects/documents/ind-49107-009-rrp)
- [GCC Climate Budget Report 2025–26](https://www.chennaicorporation.gov.in/gcc/pdf/ClimateBudget2025-2026.pdf)

## What the website evidence does establish

- GCC published the listed project actions, stated costs, physical quantities, and progress in its Climate Budget.
- ADB published contract award records for three drainage packages.
- Five calculations in GCC's report can be reproduced arithmetically from GCC's printed inputs.

These are implementation, procurement, and arithmetic checks. They are not causal attribution. The GCC GHG values are potential/modelled estimates; “5 km complete” or “78% complete” is a delivery statement, not proof of the change in flood risk or emissions caused by the work.

## Causal question to test

For residents and road segments within a verified drainage catchment, what was the effect of the commissioned drainage works on flood depth, duration, inundated area, road closures, or service interruption during comparable rainfall/tide events, relative to what would have happened without the works?

## Minimum data to obtain

1. **Treatment definition:** official package/catchment map, geocoded asset and outfall locations, work-order scope, start date, completion/commissioning date, and operational status by segment. Tender award alone is not treatment.
2. **Outcomes:** geocoded, timestamped flood-depth/duration sensor data or validated satellite/flood-extent observations; road closure and emergency-response logs can supplement but do not replace physical flood outcomes.
3. **Event conditions:** hourly rainfall, tide level, reservoir/canal level, pump operation and relevant drain blockage/maintenance data for each outcome period.
4. **Comparison observations:** comparable catchments or segments not yet treated in the same events and periods, with treatment timing recorded. Catchment spillovers must be mapped; nearby controls may themselves be affected.
5. **Analysis protocol:** pre-specify the outcome, treatment date, comparison group, event window, covariates, missing-data handling, and uncertainty analysis before estimating effects.

## Candidate design

If rollout timing differs across catchments and repeated event-level measurements can be assembled, use a matched difference-in-differences/event-study design with catchment and event/time effects. Check pre-treatment trends, rainfall/tide balance, spillovers, concurrent works, maintenance, and changes in sensor coverage. Report uncertainty intervals and sensitivity to comparison-group selection. If these assumptions or data fail, limit the claim to descriptive before/after measurements. A validated hydraulic model can provide a counterfactual scenario, but its result must be labelled modelled and calibrated against observed flood data; it is not an observed causal estimate.

## Review language

> “We have traceable primary-source evidence of GCC-reported activity and progress, official award records, and reproduced estimate arithmetic. We do not yet have a verified causal estimate of impact. The ADB flood-management project is ongoing and its ADB page currently lists no evaluation document. Our next step is to obtain asset commissioning, geocoded flood outcomes, rainfall/tide, and valid comparison data, then test a pre-specified quasi-experimental design.”
