# CarbonWise website walkthrough for a project review

## What the website is

CarbonWise currently contains two distinct workspaces in one local Streamlit website:

1. **Evidence Room · GCC records** — the source-backed evidence interface. It uses the 23 project records from the supplied starter CSV, cross-references them to the official Greater Chennai Corporation (GCC) Climate Budget Report 2025–26, and shows three drainage tender references matched to Asian Development Bank (ADB) award records. It also reproduces five report calculations.
2. **Scenario Lab · synthetic model** — the interactive multi-objective optimization demonstration. Its 56 candidate projects are generated benchmark records. Results are useful to demonstrate the method and interface, but are not real GCC funding recommendations or observed Chennai impacts.

The website runs locally; it is a research prototype, not an official GCC service or a live sensor-connected digital twin.

## How to navigate

Use the **WORKSPACE** selector in the sidebar. The default is Evidence Room. Its tabs are described below.

### Evidence Room · GCC records

#### Overview

- The four headline cards count GCC actions cross-referenced, GCC-published GHG estimates, drainage awards linked, and confirmed actual spend.
- Department bars count source rows. They do not sum budgets, because some starter entries are programme aggregates or can overlap.
- Progress cards reproduce published GCC status: Complete Streets (5 of 11.6 km), Villivakkam Tank (78%), Chinna Nolambur bridge (55%), and deployment/handover of 24 CNG vehicles.
- The 43.1% Complete Streets ratio is calculated as 5 ÷ 11.6. GCC reports the two lengths; the ratio is our arithmetic.
- Drainage cards show contract award records. The award amount is not actual expenditure, and it does not establish completion.

#### GCC project evidence

Filter the 23 rows by department. Each record links the supplied starter ID and project to its GCC activity, classification, published status, physical quantity/progress, reported cost, GHG estimate (where provided), source page, official PDF, and an interpretation note. Download the filtered CSV if you want to retain or analyze the crosswalk. Open the PDF from the [official GCC site](https://www.chennaicorporation.gov.in/gcc/pdf/ClimateBudget2025-2026.pdf); the file remains in the local project but is not stored in the GitHub repository.

“GCC-reported” means the statement appears in GCC's report. This does not make it an independent audit. The source report itself has scope differences—for example, its summary and detailed table report different pond counts—so the dashboard keeps those caveats visible.

#### Drainage awards

The separate **CMRL award records** tab adds 97 rows from the current Chennai Metro Rail Limited award listing. One tender reference is repeated in two distinct rows and is flagged for review. Treat each row as procurement evidence, not as a separate completed project. The listing does not establish payment, completion, measured carbon reduction, or equity outcomes. The methodology and field definitions are in `docs/cmrl_award_evidence.md`.

The **Evidence index & audit** tab counts source documents separately from projects, withholds the unique-project count until a reviewed cross-source project map exists, and exposes filters, official source links, missing-field coverage, the duplicate-review queue, and source run results. Only evidence rows are shown here; synthetic model inputs remain in the Scenario Lab.

This table brings together three GCC tender references, official tender notice IDs, ADB award dates, contractors and USD award amounts. Tender estimate, actual expenditure, physical quantities and completion remain unknown in the available records. The ADB-financed share and total contract value are separate fields. Neither is converted into a GCC payment.

#### Calculation audit

Five calculations printed in the GCC report are rerun from the report's own numbers: windrow composting, LED lighting, CNG mini trucks, CNG recovery vehicles and CNG tankers. The displayed formulas reproduce the published arithmetic. Operating days, mileage, installation, fuel, counterfactuals and realized impacts are not field-verified. Present these as **reproduced report estimates**, not measured reductions.

#### Causal evidence & methods

This explains which fields are from the supplied file, GCC's report, derived arithmetic, ADB award records, or unknown. It also explains why the source-backed evidence is kept separate from the optimizer: the project records do not share a validated resilience measure, comparable geography, and reconciled cost basis. It states plainly that the current source pack has no verified causal estimate. ADB lists the flood-management project as ongoing and currently has no evaluation document listed. The tab describes the minimum data and a possible matched difference-in-differences/event-study design. See `docs/causal_evidence_status.md` for the full finding and study plan. Running the source pipeline and calculation check from the project root:

```bash
python3 src/data_pipeline.py
python3 src/verify_gcc_calculations.py
```

#### Presenter guide

This is the short in-app tour and two-minute speaking script. It summarizes how to describe the scope correctly.

### Scenario Lab · synthetic model

Choose this workspace in the sidebar to demonstrate the algorithm. Its inputs come from `data/raw/projects.csv` and `data/raw/wards.csv`, not the GCC starter evidence register. In particular, the project generator creates 56 benchmark candidates and the zone file contains 15 zone records. Their provenance/validation limits are described in the README and implementation audit.

- **Budget & priorities:** set a hypothetical budget and adjust the three equity-score weights. The weights are normalized to add to one.
- **Data quality:** expand the sidebar panel to see basic input counts and missing-value checks. A technically clean table does not itself prove that its values describe real projects.
- **Zone Profile:** inspect relative positions and zone vulnerability, deprivation and population fields. Those are context fields from the prototype; no project-to-zone assignment from the GCC evidence register is invented here.
- **Candidate Projects:** filter the generated benchmark candidates and inspect their assigned zone, cost and model scores.
- **Investment Analysis:** click **Run Optimizer** to create a Pareto set and select a balanced point. The page compares that selection with equal-split and greedy baselines, plots objectives, displays trade-off scenarios, provides rule-based council statements and an equity audit, and offers report/CSV downloads. Every output inherits the synthetic-input limitation.
- **Optional budget sensitivity:** the checkbox asks the model to repeat the analysis at alternate budgets; it is not a sensitivity analysis of verified GCC projects.

The UI contains no live municipal feed. The label “digital twin” should be understood as a hypothetical scenario capability unless a live, validated data connection is added.

## Safe statements for a review

- “The GCC Climate Budget lists this status/quantity on the cited printed page.”
- “We reproduced the report's calculation from its printed inputs; the activity assumptions and realized reductions were not independently measured.”
- “ADB lists this award. Actual expenditure and completion are not confirmed in the records currently connected.”
- “The evidence interface is source-backed. The optimizer is a separate synthetic demonstration.”

Avoid claiming verified emissions reductions, actual spending, complete project delivery, a validated zone allocation, or an optimized real-city investment portfolio.

## Two-minute presentation script

“CarbonWise has two deliberately distinct parts. The Evidence Room starts with the 23 project records in the supplied GCC starter file. I matched each row to the Greater Chennai Corporation's 2025–26 Climate Budget and show the published status, quantities, costs, report pages and caveats, so reviewers can trace a claim to its source. For example, the report says 5 km of 11.6 km of Complete Streets are complete, and reports Villivakkam Tank at 78% progress. The first is the source's two lengths; the displayed 43.1% is my division of those values.

“I also reran five GHG estimate calculations from the report. The arithmetic matches, but the inputs—such as annual mileage and operating hours—remain assumptions, so I describe these as reproduced estimates, not measured emissions reductions. In the drainage section, three tender references match ADB award records. Contract awards are not payment records; actual spend and physical completion remain unknown.

“The Scenario Lab demonstrates how the optimizer compares carbon, resilience and equity trade-offs, but it uses 56 generated benchmark candidates. I do not present those scores as real Chennai recommendations. The next step toward a real portfolio is to connect verified project-level payment and completion data, measured outcomes, and an authoritative project-to-zone/population crosswalk. The prototype already provides the evidence trail and reproducible calculation layer on which that next step can build.”

## Q&A: likely reviewer questions

**Are the data real?** The GCC report, starter project rows and referenced tender/ADB records are real source material. Values transcribed from the report are GCC-published claims, not independently audited observations. The Scenario Lab project candidates are synthetic.

**Are the carbon savings proven?** No. Five report calculations are arithmetically reproduced. Their activity factors and realized reductions have not been validated with field monitoring.

**Why isn't the GCC dataset optimized?** The source records do not provide a common verified resilience score, comparable project-level cost scope, and validated project-to-zone beneficiary mapping for all candidates. Ranking them today would require invented or inconsistent assumptions.

**What should be collected next?** Work orders and payment certificates; dated completion and quantity measurements; operational data for emissions; geocoded project footprints; and an approved method to map affected population and resilience benefits to each project.
