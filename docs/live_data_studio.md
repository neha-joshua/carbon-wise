# Live Data Studio

## End-to-end workflow

The app provides five work areas: **Upload & prepare**, **Street View Insights**, **Compare plans**, **What-if**, and **Review & download**. The separate Evidence Room continues to hold the source-backed GCC/CMRL records.

1. Upload a CSV or XLSX/XLSM file (up to 25 MB and 500 project rows; Excel reads the first worksheet), or load the clearly labeled synthetic demo dataset.
2. Inspect rows, columns, types, missing cells, and duplicate rows.
3. Map ID, cost, annual carbon benefit, resilience benefit, and equity/community benefit. Category, project name, and ward/zone are optional.
4. Correct mapped cells or delete invalid rows in the editable table. Duplicate project IDs, blank IDs, nonnumeric fields, nonpositive costs, and negative carbon/resilience benefits block plan generation. No model input is imputed.
5. Enter the cost unit label and budget. CarbonWise does not convert cost or benefit units.
6. Select **Generate investment plan** to run the existing pymoo NSGA-II implementation on the active mapped rows. The three objectives are summed annual carbon benefit, summed resilience benefit, and summed dataset-relative community score. The selected representative plan uses the priority weights, and an optional minimum average score (0–100) is enforced as a constraint.
7. Review the selected and excluded projects, alternative feasible plans, and equal-split and carbon-efficiency baselines. Download selected rows, the alternative-plans table, or the complete ZIP packet. Baselines respect the budget but may fail an enabled minimum-score constraint; the comparison shows that status.
8. Change a setting and generate another plan. **What-if** compares the session's previous and current runs, including projects added/removed, result changes, and proposed costs by category and ward/zone where mapped.

## Input and score interpretation

A model-ready file needs unique project IDs, positive costs, and complete numeric carbon, resilience, and equity fields for every included row. A project is one row. The budget and cost column must use the same unit. Carbon and resilience objectives retain input units. Equity is min–max normalized to 0–100 within the current working dataset; the raw mapped value is preserved in `equity_raw`. Preference weights are applied when selecting a single point from the NSGA-II Pareto frontier; they do not turn the algorithm into a single-objective weighted-sum optimizer. The minimum equity requirement applies to mean normalized equity among selected projects.

NSGA-II uses population 96, 100 generations, and seed 7 in the Live Studio. This is a stochastic evolutionary search. Its frontier is the feasible non-dominated set found in that run, not a proof that every mathematical Pareto solution was found. Selected cost is rechecked against the unrounded mapped costs before display. Equal-split and greedy carbon-efficiency baselines use the same dataset and cost unit.

## Street View Insights

Camera capture is provided by Streamlit and requires browser permission; a JPEG/PNG upload is available as an alternative. Images larger than 30 megapixels are rejected. Pillow and NumPy convert the image to RGB, resize it with the aspect ratio preserved so the longest side is at most 512 pixels, then compute HSV pixel shares. The **green-hued** rule is Pillow's hue channel 30–100 on its 0–255 scale (not degrees), saturation ≥50, and value ≥30. The **low-saturation gray** rule is saturation ≤45 and value 35–205. Each percentage uses all pixels in the resized image as its denominator. The classes cannot overlap because their saturation ranges do not overlap. The interface displays the uploaded image and results together; it does not identify objects.

The user must select a ward/zone from the mapped upload to link the note; without an available mapped area it remains unlinked. Confirmed notes, selected ward, UTC time, pixel fractions, and image SHA-256 are retained in the current session. In a later plan run, the user may explicitly apply a user-entered resilience-benefit percentage adjustment to projects mapped to that ward. This is a what-if assumption; it is never inferred from the photo. Lighting, shadows, camera settings, compression, blur, and image quality can change the output. The image cannot establish emissions, flood probability, vegetation coverage, population vulnerability, project completion, safety, or causal effect. Photos and uploaded data are handled in the running Streamlit session and are not committed to the repository. Avoid uploading confidential records to a public app.

## Demo dataset and run-through

`data/demo/carbonwise_synthetic_demo.csv` contains 12 invented sample projects. The app labels it synthetic. It is for exercising the interface and optimizer; it is not Chennai evidence and must not be represented as real project records.

1. Choose **Live Studio · your data** and select **Load synthetic demo**.
2. Confirm the mapped fields and validation, then open **Compare plans**, choose a budget, and select **Generate investment plan**.
3. Inspect the chosen plan, the baseline comparison, and the alternative-plans chart.
4. Change the budget or priorities and generate another plan; show the project changes and cost-allocation chart under **What-if**.
5. In **Street View Insights**, capture or upload a photo. Review the color-share estimates, optionally select one of the mapped project areas, add a human observation, and confirm it. A separately stated resilience assumption can be used in a later plan run.
6. Download the complete run packet and state that the example rows are synthetic.

For actual recommendations, replace sample data with project-specific, source-traceable estimates; reconcile units and definitions; and validate equity and impact measures with domain experts. Neither this optimizer nor one photo establishes causal impact.
