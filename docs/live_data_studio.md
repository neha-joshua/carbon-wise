# Live Data Studio

## End-to-end workflow

The app provides five work areas: Data Workspace, Visual Street Audit, Investment Optimization, What-If Digital Twin, and Evidence Explorer & Results. The separate Evidence Room continues to hold the source-backed GCC/CMRL records.

1. Upload a CSV or XLSX/XLSM file (up to 25 MB and 500 project rows; Excel reads the first worksheet), or load the clearly labeled synthetic demo dataset.
2. Inspect rows, columns, types, missing cells, and duplicate rows.
3. Map ID, cost, annual carbon benefit, resilience benefit, and equity/community benefit. Category, project name, and ward/zone are optional.
4. Correct mapped cells or delete invalid rows in the editable table. Duplicate project IDs, blank IDs, nonnumeric fields, nonpositive costs, and negative carbon/resilience benefits block optimization. No model input is imputed.
5. Enter the cost unit label and budget. CarbonWise does not convert cost or benefit units.
6. Run the existing pymoo NSGA-II implementation on the active mapped rows. The three objectives are summed annual carbon benefit, summed resilience benefit, and summed dataset-relative equity score. The selected representative point uses the priority weights, and an optional minimum mean equity score (0–100) is enforced as a constraint.
7. Inspect the Pareto front, chosen and excluded projects, equal-split and carbon-efficiency baselines, and download the selected rows, frontier, or complete ZIP packet. Baselines respect the budget but are separately labeled if they fail an enabled equity floor.
8. Change a setting and run again. The What-If Digital Twin compares the current session's last completed run with the new run, including projects added/removed, objective changes, and budget allocation by category and ward/zone where mapped.

## Input and score interpretation

A model-ready file needs unique project IDs, positive costs, and complete numeric carbon, resilience, and equity fields for every included row. A project is one row. The budget and cost column must use the same unit. Carbon and resilience objectives retain input units. Equity is min–max normalized to 0–100 within the current working dataset; the raw mapped value is preserved in `equity_raw`. Preference weights are applied when selecting a single point from the NSGA-II Pareto frontier; they do not turn the algorithm into a single-objective weighted-sum optimizer. The minimum equity requirement applies to mean normalized equity among selected projects.

NSGA-II uses population 96, 100 generations, and seed 7 in the Live Studio. This is a stochastic evolutionary search. Its frontier is the feasible non-dominated set found in that run, not a proof that every mathematical Pareto solution was found. Selected cost is rechecked against the unrounded mapped costs before display. Equal-split and greedy carbon-efficiency baselines use the same dataset and cost unit.

## Visual Street Audit

Camera capture is provided by Streamlit and requires browser permission; a JPEG/PNG upload is the fallback. Pillow and NumPy compute the share of pixels in selected HSV color ranges. These are **green-hued pixels** and **low-saturation gray pixels**, not vegetation/road segmentation. The interface displays the original image, names the heuristic, and asks the reviewer to enter and confirm an observation.

Confirmed notes, ward association, UTC time, pixel fractions, and image SHA-256 are retained in the current session. In a later optimizer run, the user may explicitly apply a user-entered resilience-benefit percentage adjustment to projects mapped to that ward. This is a what-if assumption; it is never inferred from the photo. The image cannot establish emissions, flood probability, population vulnerability, completion, safety, or causal effect. Photos and uploaded data are handled in the running Streamlit session and are not committed to the repository. Avoid uploading confidential records to a public app.

## Demo dataset and run-through

`data/demo/carbonwise_synthetic_demo.csv` contains 12 invented sample projects. The app labels it synthetic. It is for exercising the interface and optimizer; it is not Chennai evidence and must not be represented as real project records.

1. Choose **Live Studio · your data** and select **Load synthetic demo**.
2. Confirm the mapped fields and validation, then open Investment Optimization and run with a budget.
3. Inspect baselines, selected/excluded projects, and Pareto chart.
4. Change budget or priorities and run again; show the project delta and allocation chart in What-If Digital Twin.
5. In Visual Street Audit, capture a photo if browser camera is available or upload a photo. Review the pixel-share heuristic, manually label and confirm the observation, and optionally use a separately stated resilience scenario assumption on the next run.
6. Download the complete run packet and state that the example rows are synthetic.

For actual recommendations, replace sample data with project-specific, source-traceable estimates; reconcile units and definitions; and validate equity and impact measures with domain experts. Neither this optimizer nor one photo establishes causal impact.
