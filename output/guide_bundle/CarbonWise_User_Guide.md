# CarbonWise: a guide for first-time visitors

You do not need a programming, climate-science, or planning background to follow this guide. It explains what to click, what the results mean, and what they do **not** prove.

## Start with the one-sentence explanation

**CarbonWise helps people compare climate-project ideas, costs, and community priorities, while showing where the information came from and where evidence is missing.**

The website has three separate ways to explore this idea. They use different kinds of information, so do not mix their results together:

| Choose this | What you do | What the information represents |
|---|---|---|
| **Analyze my data** | Upload a project list and compare possible plans | Values in the file you upload. They are not independently checked by CarbonWise. |
| **Try a sample plan** | Practice using the planner | Generated example projects and scores. They are not actual Chennai proposals. |
| **Explore official evidence** | Read source-linked public records | What the supplied project list, GCC report, and public contract records say. A source record is not proof of impact or payment. |

CarbonWise is a research prototype. It is not a Greater Chennai Corporation service, a live monitoring system, or a tool that measures actual climate benefits.

## The easiest way to understand the site

1. Open the public site and leave **Start here** selected.
2. Pick one of the three paths in the table above.
3. If you are new, start with **Try a sample plan**. This is the safest way to click around because the file is an example.
4. Open **Explore official evidence** next to see the difference between a source-backed record and an example used by the planner.
5. Use **Analyze my data** only when you have a project file you understand and are allowed to use.

Use the left-side **Where would you like to start?** menu to move between these areas. If the left menu is hidden, use the small arrow at the upper-left of the page to open it.

## Path 1: Try a sample plan

This path demonstrates how the planner works. It uses 56 generated example projects and 15 GCC zone records. The sample project's name, cost, and benefit values are illustrative; they are not GCC funding proposals or measured outcomes.

### Make a plan

1. Select **Try a sample plan** in the left menu.
2. In **Available budget**, enter the maximum amount the example plan can spend. It is only a practice limit, not a real city budget.
3. Under **How should community need be counted?**, adjust the three sliders if you want to see how priorities affect the example plan:
   - **Community vulnerability** gives more weight to the sample's area vulnerability indicator.
   - **People a project may serve** gives more weight to an estimated share of an area's population.
   - **Infrastructure service gap** gives more weight to the sample's infrastructure-need indicator.
4. Open **Areas** to explore the 15 GCC zones in the sample file. The dots represent zones, not actual project locations. The zone values and coordinates have not been independently checked here.
5. Open **Example projects** to filter and browse the generated project rows.
6. Open **Your sample plan** and select **Build sample plan**.

### Read the result

- **Budget used** tells you how much of the sample budget the selected example projects use.
- **Carbon score**, **Resilience score**, and **Community score** are relative model scores. They are not tonnes of emissions, measured flood protection, or proof of benefits to residents.
- The list under **Projects in this sample plan** shows which generated rows were selected, their example costs, and their relative scores.
- Expand **See comparisons, rationale, and fairness checks** for other ways to select projects, a short explanation of the chosen plan, and more charts.
- The comparison of plans is a search result, not a guarantee that the planner found every possible combination.
- The area distribution check describes where the model placed generated project costs. It does not show who received benefits or prove that the plan is fair in real life.
- The optional five-budget comparison reruns the sample model at different spending limits. It is an exploration of the example data, not a forecast.

### Download sample results

Use **Download full investment decision report (TXT)** for the longer explanation, or **Download portfolio only (CSV)** for the selected rows in a spreadsheet. The download includes notes that the projects and scores are generated examples. Do not present them as real Chennai proposals or results.

## Path 2: Analyze my data

Use this path when you have a CSV or Excel file with one project on each row. The page separates the work into tabs such as **Upload & prepare**, **Street View Insights**, **Compare plans**, **What-if**, and **Review & download**.

### Prepare a project file

1. Choose **Analyze my data** from the starting menu.
2. Under **Upload & prepare**, upload a `.csv`, `.xlsx`, or `.xlsm` file. Or choose **Load synthetic demo** to practice with the included invented sample file.
3. Check the row/column count, missing cells, and duplicates. Open the table preview if you want to inspect the first rows.
4. Match the columns in your file to the required planning fields. The required fields are a project ID, cost, annual carbon benefit, resilience benefit, and equity/community benefit. Project name, category, and zone can also be mapped when your file includes them.
5. Enter a clear cost-unit label, such as “crore INR” or “USD.” Carbon, resilience, and community benefit units should be understood from your source file; CarbonWise does not convert them for you.
6. Choose **Use these columns**, then review the working table. Correct errors or remove rows you do not want to compare.

CarbonWise checks for problems that make a comparison unsafe, including missing required values, duplicate IDs, and invalid costs. It does not fill missing benefit values with guesses. If there are blocking issues, fix the table before continuing.

**Important:** a successful data check means that required fields are present and pass basic checks. It does not confirm that the uploaded figures are true, current, or scientifically valid.

### Compare plans

1. Open **Compare plans**.
2. Set the available budget using the same unit as the costs in your file.
3. Choose how much weight to give the carbon, resilience, and community values. These settings change the ranking; they do not change the values in your file.
4. If useful, set a minimum average community score. This asks the planner to exclude plans below that threshold. The score is scaled within your uploaded dataset, so it is not an absolute measure of community benefit.
5. Select **Generate investment plan**.
6. Read the selected projects, total cost, and alternative plans. The benefit figures come from the file you provided. They are estimates in your file's units, not measured outcomes.

If no feasible plan can be generated, check that the budget is high enough, lower any minimum-score requirement, and review the mapped values for errors.

### See what changed with What-if

After generating a first plan, change a budget or priority and generate another plan. The **What-if** area compares the two runs, including projects added or removed and how the settings changed. If the uploaded project values changed too, the comparison will say so; then the difference is due to both the data and the settings.

An optional resilience adjustment can be entered for a manually confirmed field note and a matching project area. This is an assumption chosen by the user. It is not calculated from the photo and is not a measured resilience improvement.

### Review and download

The **Review & download** area lets you save the current input, the selected plan, alternative plans, and a complete run packet. Downloads help you keep a copy because the website's working data and notes are kept in the current browser session and may not be there later.

## Path 3: Street View Insights

In **Analyze my data**, open **Street View Insights**. Upload a PNG/JPG photo or choose the camera option if your browser allows it.

The tool measures the share of pixels with selected colours:

- **Green-coloured areas** may include greenery, but the tool does not identify trees or plants.
- **Grey-coloured areas** may include roads, paths, buildings, and many other surfaces.

The photo alone cannot establish carbon emissions, flooding, safety, neighbourhood vulnerability, or project completion. You can enter your own observation (for example, standing water) and optionally choose an area from your mapped data. CarbonWise does not infer the location from the image. You must confirm your observation yourself.

Saved notes belong to the current session. Download the audit log or packet if you want to keep a copy. Adding a photo or note does not automatically change the project data or plan. A separate, explicit what-if adjustment is needed to change a model input.

## Path 4: Explore official evidence

This area shows records and source links. In this project, the evidence workspace uses 23 rows from the supplied project CSV, links them to items and pages in GCC's 2025–26 Climate Budget, and includes public contract-award records.

Depending on the tab, you can:

- See a high-level overview of the records and selected progress figures reported by GCC.
- Filter and read the GCC project list, including the report page and source link.
- Inspect drainage and other contract-award records and download a CSV.
- Open **Sources & checks** to review source documents, data gaps, and reproduced report calculations.

Read each number with its label. A count of rows is not a count of unique finished projects. A contract award is not proof of payment. A progress figure or emissions estimate printed in a report is what the source reports; it is not automatically an independent measurement. The calculations page checks the arithmetic in selected published estimates, not whether the source assumptions or real-world results are correct.

The evidence records are **not ranked by the sample planner**. The current evidence does not provide a consistent, verified resilience measure, comparable cost basis, and project-to-area/beneficiary link for every record. Ranking these as if they were comparable would require adding assumptions that the sources do not provide.

## What CarbonWise does and does not do

| It does | It does not |
|---|---|
| Lets someone explore project data and compare possible plans under a budget. | Decide or approve a real city budget. |
| Shows source links and some public progress and contract records. | Prove that a contract was paid or a project finished. |
| Checks that required fields are present and that some basic values are valid. | Independently verify every uploaded or published figure. |
| Shows sample-model trade-offs using generated examples. | Measure actual carbon reductions, flood protection, or resident benefits. |
| Estimates image colour shares and lets a person save an observation. | Recognize objects or infer a photo's location or climate impact. |

## Small glossary

- **GCC:** Greater Chennai Corporation, the city body whose climate-budget report is one of the evidence sources.
- **Generated example / sample data:** invented rows used to demonstrate how the planner works. They are not real project records.
- **Source-backed record:** a statement or entry linked to a document or public listing. It tells you what that source says; it does not guarantee that the claim has been independently audited.
- **Annual carbon benefit:** a value in a project file or source that estimates a project's yearly carbon reduction. It is only as reliable as its source and assumptions.
- **Resilience:** in this project, a value meant to represent climate-related protection or service improvement. The meaning and unit must come from the input file; a score is not proof of actual protection.
- **Community/equity score:** a value used to compare how projects might relate to community need. It is not proof that people received a benefit.
- **Baseline:** a simple comparison plan used to give context to another plan. It is still based on the same input data and assumptions.
- **Validation:** basic checks that catch missing or inconsistent input fields. Passing validation does not mean the data are true.
- **What-if:** a comparison of two model runs after changing a setting. It is not a prediction of what will happen in the city.

## A short presentation script

“CarbonWise gives people three ways to explore climate investment planning: they can use their own project file, try a clearly labelled sample plan, or inspect public Chennai records. In the planner, someone can set a budget and compare which projects fit under different priorities. The sample projects are generated examples, and the scores are not measured climate impacts. The evidence page is separate: it links public statements and contract records to their sources and shows where information is still unknown. An award does not prove payment or completion, and a published estimate does not prove a realized reduction. The project demonstrates a transparent comparison workflow; the next step toward real planning is getting comparable project costs, verified locations and beneficiaries, completion/payment records, and measured outcomes.”

## If you get stuck

- **The sample plan looks empty:** open **Your sample plan**, set a budget, and select **Build sample plan**.
- **Your uploaded file will not continue:** check that the required columns are mapped, all required values are present, IDs are unique, and each cost is positive.
- **The result looks like a real recommendation:** check the data path. Results from **Try a sample plan** use generated example projects. Results from **Analyze my data** use your uploaded values.
- **The camera does not open:** browser camera access may be blocked. Choose **Upload a photo** instead; you do not need the camera to use the rest of CarbonWise.
- **You want to keep your work:** download the relevant CSV, report, or ZIP before closing or refreshing the session.

For technical details and the original project method, read the implementation audit and data-provenance notes in the repository. You do not need those files to use the three main website paths.
