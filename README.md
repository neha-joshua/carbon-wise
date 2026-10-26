# CarbonWise

CarbonWise is a Streamlit research prototype for exploring climate investment planning in Chennai. It offers three clear starting points:

- **Analyze my data:** upload a project CSV or Excel file, map its columns, review input checks, set a budget, compare plans, and download the results.
- **Try a sample plan:** explore the planning workflow with generated example projects.
- **Explore official evidence:** browse source-linked GCC climate-budget records and contract-award evidence.

CarbonWise is not an official GCC service, live monitoring system, or digital twin. It does not prove real-world project impact.

## Evidence and sample data are different

The evidence workspace starts with 23 project records from the supplied CSV and links them to the GCC Climate Budget 2025–26. It also shows public procurement records. These support claims about what a source published or listed; award records do not establish payment or completion, and published estimates are not measured outcomes.

The sample planner uses 56 generated project examples and 15 GCC zone context records. Its carbon, resilience, and community values are relative model scores, not tonnes of emissions, measured protection, or verified community benefits. The zone context values have not been independently validated in this implementation. The sample planner does not produce real GCC funding recommendations.

For uploaded data, CarbonWise uses the values the user provides. Required missing values, non-finite values, duplicate IDs, and invalid costs are flagged; missing benefits are not silently imputed. A plan is still an estimate based on the uploaded fields, not an observed outcome.

## Run the app

```bash
pip install -r requirements.txt
streamlit run dashboard/app.py
```

Open the local URL printed by Streamlit. For hosted use, this repository is configured for Streamlit Community Cloud. See [deployment instructions](docs/deploy_streamlit_cloud.md).

## A short demo

1. Open **Try a sample plan**.
2. Set the budget and, if desired, adjust the community-need priorities.
3. Inspect **Areas** and **Example projects**.
4. Choose **Build sample plan**.
5. Review the plan, comparisons, and caveats. Download the report or CSV if useful.

To demonstrate a user-provided file, open **Analyze my data**, load the included generated demo file or upload your own, confirm the column mapping and validation results, then set a budget and generate a plan.

For a full click-by-click explanation and presentation script, see [the CarbonWise user guide](docs/presenter_walkthrough.md). For the upload workflow and image-analysis limits, see [Live Studio documentation](docs/live_data_studio.md).

## Tests

```bash
python -m unittest discover -s tests -v
```

## Project layout

```text
dashboard/app.py       Streamlit website and navigation
src/                   Evidence, validation, scoring, optimization, and reporting
data/                  Supplied evidence, generated examples, and source registers
docs/                  Method, deployment, and presenter guidance
tests/                 Automated checks
```

See [the implementation audit](docs/implementation_audit.md) and [data provenance notes](docs/data_provenance.md) before making claims about real-world impact.
