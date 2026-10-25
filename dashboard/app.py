"""
CarbonWise — Chennai Infrastructure Investment Decision Support
Run with: streamlit run app.py   (from inside the dashboard/ folder)
"""
import sys, os
from pathlib import Path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

pio.templates["carbonwise"] = pio.templates["plotly_white"]
pio.templates["carbonwise"].layout.font = dict(family="Times New Roman, Times, serif", size=13)
pio.templates.default = "carbonwise"
from io import StringIO
from datetime import date

from preprocessing import preprocess
from equity_scoring import compute_equity_score
from optimizer import run_nsga2, pareto_front_to_df, pick_balanced_solution
from baselines import (equal_split_allocation, greedy_cost_effectiveness_allocation,
                        summarize_portfolio)
from scenarios import build_scenarios
from agents import full_council_report
from equity_auditor import audit_report
from report import generate_report
from sensitivity import run_sensitivity
from llm import client as llm_client
from llm.explain import generate_explanation
from data_validation import validate as validate_data
from decision_rationale import build_rationale

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@st.cache_data
def load_evidence_data():
    projects = pd.read_csv(PROJECT_ROOT / "data/raw/projects_real_starter.csv")
    tenders = pd.read_csv(PROJECT_ROOT / "data/tenders/chennai_drainage_tender_packages.csv")
    evidence = pd.read_csv(PROJECT_ROOT / "data/evidence/gcc_climate_budget_evidence.csv", keep_default_na=False)
    checks = pd.read_csv(PROJECT_ROOT / "results/evidence/gcc_report_calculation_checks.csv", keep_default_na=False)
    snapshots = sorted((PROJECT_ROOT / "data/derived").glob("*/validation_issues.csv"))
    issues_path = snapshots[-1] if snapshots else None
    issues = pd.read_csv(issues_path) if issues_path else pd.DataFrame()
    return projects, tenders, issues, evidence, checks


def render_evidence_room():
    projects, tenders, issues, evidence, checks = load_evidence_data()
    st.markdown("""
    <style>
      .stApp { background: #f4f6f2; }
      [data-testid="stSidebar"] { background: #101c19; }
      [data-testid="stSidebar"] * { color: #eef3e9 !important; }
      .evidence-hero { background: radial-gradient(ellipse at 83% 0%, #315849 0%, #182b25 42%, #101c19 100%);
        border-radius: 24px; padding: 38px 42px 34px; color: #f7f7ef; margin: 4px 0 22px; position: relative; overflow: hidden; }
      .evidence-kicker { color: #c9e86b; font-size: 12px; letter-spacing: 2px; text-transform: uppercase; font-weight: 700; }
      .evidence-title { font-size: clamp(38px, 5vw, 64px); line-height: .99; letter-spacing: -2.4px; font-weight: 750; margin: 16px 0 14px; max-width: 780px; }
      .evidence-copy { color: #d1ddd3; font-size: 17px; max-width: 770px; line-height: 1.5; }
      .evidence-chip { display:inline-block; border: 1px solid #779186; color:#dbe7dc; padding:7px 11px; border-radius:99px; font-size:12px; margin:14px 7px 0 0; }
      .metric-card { background:#fff; border:1px solid #e0e6df; border-radius:16px; padding:20px 22px; min-height:128px; box-shadow:0 5px 18px #172b2010; }
      .metric-label { color:#607167; text-transform:uppercase; font-size:11px; letter-spacing:1.1px; font-weight:700; }
      .metric-value { font-size:39px; letter-spacing:-1.8px; line-height:1.15; font-weight:750; color:#16392d; margin:9px 0 3px; }
      .metric-note { color:#718078; font-size:12px; }
      .section-kicker { color:#79914b; font-size:11px; letter-spacing:1.6px; text-transform:uppercase; font-weight:800; margin: 26px 0 5px; }
      .section-heading { font-size:29px; letter-spacing:-.8px; color:#162b23; font-weight:700; margin:0 0 4px; }
      .status-band { background:#fff8e6; border:1px solid #ead7a7; border-left:5px solid #d7a82f; border-radius:12px; padding:16px 19px; color:#493d22; margin:14px 0 20px; }
      .tender-card { background:#fff; border:1px solid #e2e8e2; border-radius:16px; padding:19px; min-height:206px; box-shadow:0 5px 18px #172b2008; }
      .tender-tag { font-size:10px; text-transform:uppercase; letter-spacing:1.1px; color:#728343; font-weight:800; }
      .tender-package { font-size:23px; letter-spacing:-.5px; color:#19372c; font-weight:700; margin:8px 0; }
      .tender-title { font-size:13px; color:#607067; line-height:1.45; min-height:58px; }
      .tender-value { font-size:20px; font-weight:700; color:#18392e; margin-top:12px; }
      .tender-meta { font-size:11px; color:#78847d; margin-top:4px; }
      div[data-testid="stTabs"] button { font-weight:650; }
      @media (max-width: 700px) {
        .evidence-hero { padding:27px 24px; border-radius:18px; }
        .evidence-title { font-size:38px; letter-spacing:-1.3px; }
        .evidence-copy { font-size:14px; max-width:100%; }
        .evidence-chip { font-size:10px; padding:6px 9px; margin-right:4px; }
        .metric-card { padding:16px 18px; min-height:110px; }
        .metric-value { font-size:34px; }
      }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="evidence-hero">
      <div class="evidence-kicker">Chennai · Evidence room · GCC source records</div>
      <div class="evidence-title">Make every rupee<br>traceable.</div>
      <div class="evidence-copy">A decision-support view of the records you supplied: what GCC reports, what official award data corroborates, and what is still missing before any portfolio can be called decision-ready.</div>
      <span class="evidence-chip">SOURCE-FIRST</span><span class="evidence-chip">15-ZONE CONTEXT</span><span class="evidence-chip">NO INVENTED IMPACTS</span>
    </div>
    """, unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    cards = [
        (k1, "GCC ACTIONS CROSS-REFERENCED", f"{len(evidence)}", "Matched to official Climate Budget items"),
        (k2, "PUBLISHED GHG ESTIMATES", f"{evidence['reported_annual_ghg_reduction_tco2e'].astype(str).str.strip().ne('').sum()}", "GCC-reported modelled figures, not measured outcomes"),
        (k3, "DRAINAGE AWARDS LINKED", f"{len(tenders)}", "Tender notices matched to ADB award entries"),
        (k4, "ACTUAL SPEND CONFIRMED", "0", "Award totals are not expenditure"),
    ]
    for col, label, value, note in cards:
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="status-band"><b>Evidence is now connected to the project ledger.</b> Every starter row is cross-referenced to its numbered GCC Climate Budget action and printed report page. Published quantities, project status and GHG calculations are shown with their scope. The scenario optimizer remains separate because these records do not share one validated carbon, resilience and geographic basis.</div>', unsafe_allow_html=True)

    tab_overview, tab_projects, tab_tenders, tab_checks, tab_method, tab_guide = st.tabs(["Overview", "GCC project evidence", "Drainage awards", "Calculation audit", "Causal evidence & methods", "Presenter guide"])
    with tab_overview:
        st.markdown('<div class="section-kicker">01 / What the evidence can support</div><div class="section-heading">A useful dataset starts with honest boundaries.</div>', unsafe_allow_html=True)
        left, right = st.columns([1.05, .95], gap="large")
        with left:
            dept = projects.groupby("gcc_department").size().sort_values(ascending=True).reset_index(name="records")
            fig = px.bar(dept, x="records", y="gcc_department", orientation="h", text="records", color="records", color_continuous_scale=["#b9cc9a", "#244d3b"])
            fig.update_layout(height=370, margin=dict(l=0,r=10,t=10,b=5), showlegend=False, coloraxis_showscale=False,
                              plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#33483d"),
                              xaxis_title="Starter rows (count)", yaxis_title="", bargap=.28)
            fig.update_traces(textposition="outside", marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Counts only. Costs are not summed because the starter includes programme aggregates and potential overlaps.")
        with right:
            known_carbon = int(projects["carbon_tco2e_per_year"].notna().sum())
            st.markdown('<div class="metric-card" style="min-height:0"><div class="metric-label">HOW TO READ THE RECORDS</div><div class="section-heading" style="font-size:24px;margin-top:10px">The report provides several kinds of evidence.</div><p style="color:#68776e;line-height:1.55">Carbon is populated on {}/{} starter rows. Those are GCC-published estimates or source-labelled calculations, not independently measured emissions. This room makes the published quantities, progress and scope visible alongside the original report pages.</p><hr><p style="color:#68776e;line-height:1.55"><b>Geography:</b> project locations remain source text. The separate 15-zone file is not used to invent project-to-zone assignments. The synthetic optimizer is in a separate workspace.</p></div>'.format(known_carbon, len(projects)), unsafe_allow_html=True)
            if not issues.empty:
                top = issues[issues["severity"].isin(["error", "warning"])].head(5)
                st.markdown("**Highest-priority review flags**")
                for _, issue in top.iterrows():
                    st.markdown(f"- **{issue['record_id']} · {issue['code']}** — {issue['message']}")
        st.markdown('<div class="section-kicker">02 / GCC-published project progress</div><div class="section-heading">Physical progress, reported by GCC.</div>', unsafe_allow_html=True)
        progress_cards = [
            ("COMPLETE STREETS", "5 / 11.6 km", "GCC reports 5 km complete across six neighbourhoods; arithmetic share 43.1% (derived).", "GCC Climate Budget, printed p.45"),
            ("VILLIVAKKAM TANK", "78% complete", "Physical progress stated for the lake redevelopment; report also gives 50,000 m³ planned pond capacity.", "GCC Climate Budget, printed p.46"),
            ("CHINNA NOLAMBUR BRIDGE", "55% complete", "GCC reports the bridge being raised from 3 m to 6 m to improve water flow.", "GCC Climate Budget, printed pp.49-50"),
            ("FLEET DEPLOYMENT", "24 CNG vehicles", "15 mini trucks + 3 recovery vehicles + 6 water tankers reported deployed/handed over in 2024-25.", "GCC Climate Budget, printed pp.47-48"),
        ]
        prog_cols = st.columns(4, gap="medium")
        for col, (label, value, detail, source_note) in zip(prog_cols, progress_cards):
            with col:
                st.markdown(f'<div class="metric-card" style="min-height:175px"><div class="metric-label">{label}</div><div class="metric-value" style="font-size:29px">{value}</div><div class="metric-note" style="line-height:1.45">{detail}<br><br><b>{source_note}</b></div></div>', unsafe_allow_html=True)
        st.caption("These are GCC's published status statements in the 2025-26 Climate Budget report (report PDF issued January 2026), not live project-monitoring data. The 43.1% figure is 5 ÷ 11.6, calculated from GCC's published lengths.")

        st.markdown('<div class="section-kicker">03 / Tender evidence</div><div class="section-heading">Award records, with the unknowns left visible.</div>', unsafe_allow_html=True)
        tender_cols = st.columns(3, gap="medium")
        for col, (_, row) in zip(tender_cols, tenders.iterrows()):
            package = str(row["tender_reference"]).split("/")[-1]
            with col:
                st.markdown(f'''<div class="tender-card"><div class="tender-tag">AWARD RECORD · {row['contract_date']}</div><div class="tender-package">Package {package}</div><div class="tender-title">{row['title']}</div><div class="tender-value">US${row['awarded_contract_value_usd']:,.2f}</div><div class="tender-meta">Total contract · {row['contractor']}<br>Not actual expenditure · quantities and completion unknown</div></div>''', unsafe_allow_html=True)
                st.link_button("Open ADB award source ↗", row["award_source_url"], use_container_width=True)

    with tab_projects:
        st.markdown('<div class="section-kicker">GCC / PRIMARY SOURCE CROSS-REFERENCE</div><div class="section-heading">Project evidence register</div>', unsafe_allow_html=True)
        st.caption("Each row links your starter ID to the GCC Climate Budget's own activity number, status, quantity and printed page. 'GCC reported' means published in GCC's report; it is not third-party verification.")
        dept_options = sorted(projects["gcc_department"].dropna().unique())
        picked = st.multiselect("Filter departments", dept_options, default=dept_options)
        p = evidence.merge(projects, on="project_id", how="left", validate="one_to_one")
        p = p[p["gcc_department"].isin(picked)].copy()
        view_cols = ["project_id", "project_name", "gcc_department", "classification", "official_status", "physical_or_delivery_evidence", "reported_cost_inr_crore", "reported_annual_ghg_reduction_tco2e", "ghg_basis", "printed_report_pages", "primary_source_url", "interpretation_note"]
        display = p[view_cols].rename(columns={"project_id":"Starter ID", "project_name":"Project", "gcc_department":"Department", "classification":"GCC class", "official_status":"GCC-reported status", "physical_or_delivery_evidence":"Published delivery / quantity evidence", "reported_cost_inr_crore":"GCC-reported cost (₹ cr)", "reported_annual_ghg_reduction_tco2e":"GHG estimate (tCO₂e/yr)", "ghg_basis":"GHG method / caveat", "printed_report_pages":"Report pages", "primary_source_url":"Official GCC report", "interpretation_note":"Scope / interpretation"})
        st.dataframe(display, use_container_width=True, hide_index=True, height=560, column_config={"Official GCC report": st.column_config.LinkColumn()})
        st.download_button("Download filtered evidence register (CSV)", p.to_csv(index=False).encode("utf-8"), "carbonwise_gcc_project_evidence.csv", "text/csv")
        with st.expander("Open source notes and original references"):
            st.dataframe(p[["project_id", "data_source", "notes", "primary_source_url", "printed_report_pages"]].fillna("Not stated in starter"), use_container_width=True, hide_index=True)

    with tab_tenders:
        st.markdown('<div class="section-kicker">PROCUREMENT / AWARD EVIDENCE</div><div class="section-heading">Three distinct packages. No inferred costs.</div>', unsafe_allow_html=True)
        tv = tenders[["tender_id", "tender_reference", "title", "published_date", "contract_date", "contractor", "awarded_contract_value_usd", "adb_financed_value_usd", "estimated_tender_value_inr", "actual_expenditure_inr", "physical_quantities", "verification_status", "missing_fields", "source_url", "award_source_url"]].copy()
        tv = tv.rename(columns={"tender_id":"Official tender ID", "tender_reference":"GCC reference", "title":"Official title", "published_date":"Notice date", "contract_date":"Award date", "contractor":"Contractor", "awarded_contract_value_usd":"Contract total (USD)", "adb_financed_value_usd":"ADB share (USD)", "estimated_tender_value_inr":"Tender estimate (₹)", "actual_expenditure_inr":"Actual expenditure (₹)", "physical_quantities":"Quantities", "verification_status":"Status", "missing_fields":"Still missing", "source_url":"TN eProcurement source", "award_source_url":"ADB award source"})
        st.dataframe(tv, use_container_width=True, hide_index=True, height=390, column_config={"TN eProcurement source": st.column_config.LinkColumn(), "ADB award source": st.column_config.LinkColumn()})
        st.markdown('<div class="status-band"><b>Interpretation:</b> ADB lists matching contract awards under Loan 4113. Contract awards and the ADB-financed portion are kept in original USD. Neither amount is treated as GCC actual expenditure. Exact zone, street/chainage, physical quantities and completion are not established by the available records.</div>', unsafe_allow_html=True)
        st.link_button("Open official TN eProcurement portal ↗", tenders.iloc[0]["source_url"], use_container_width=False)
        st.link_button("Open ADB award table ↗", tenders.iloc[0]["award_source_url"], use_container_width=False)
        st.download_button("Download tender evidence table (CSV)", tenders.to_csv(index=False).encode("utf-8"), "carbonwise_drainage_award_evidence.csv", "text/csv")

    with tab_checks:
        st.markdown('<div class="section-kicker">REPRODUCIBILITY / FIVE PUBLISHED FORMULAS</div><div class="section-heading">Can we reproduce the arithmetic?</div>', unsafe_allow_html=True)
        st.markdown("The checks below rerun the arithmetic printed by GCC for five annual GHG estimates. A matching number confirms the arithmetic from the report inputs; it does **not** confirm that the vehicles travelled those distances, lights were installed and operated as assumed, or that these reductions were measured in the field.")
        check_view = checks.rename(columns={"project_id":"Starter ID", "method":"GCC estimate", "formula":"Recalculation", "inputs_and_assumptions":"Inputs and assumptions", "reported_value":"Published result", "recomputed_value":"Reproduced result", "unit":"Unit", "status":"What this check establishes"})
        st.dataframe(check_view, use_container_width=True, hide_index=True, height=390)
        st.caption("All five reproduce within normal floating-point precision. Full source pages: R02 p.55; R13 pp.60–61; R16 pp.56–57; R17 pp.57–58; R18 pp.58–60.")
        st.code("python3 src/verify_gcc_calculations.py", language="bash")

    with tab_method:
        st.markdown('<div class="section-kicker">TRANSPARENCY / CAUSAL EVIDENCE</div><div class="section-heading">What can we prove caused a change?</div>', unsafe_allow_html=True)
        st.markdown("""
        | Evidence class | What this workspace has | How it is shown |
        |---|---|---|
        | Supplied source | 23 GCC starter rows, source labels and notes | Retained as supplied |
        | GCC primary report | Climate Budget action IDs, costs, status, quantities, progress, pages | Confirmed as published by GCC; not independently audited |
        | Derived arithmetic | Five GHG estimate checks and 5 km / 11.6 km progress ratio | Formula and inputs exposed; real-world activity assumptions remain unverified |
        | Official award listing | Three matching ADB award entries | Contract values in USD; not expenditure |
        | Unknown | Actual spend, tender physical quantities, live completion, exact locations | Displayed as unknown |
        | Optimisation inputs | No compatible validated resilience and geographic crosswalk for all records | Real-project ranking is withheld; evidence analysis still runs on source-backed data |

        **Why there is no real-data portfolio ranking yet:** the GCC report supplies real project details and progress, but it does not provide a common project-level resilience score or a validated project-to-zone/population crosswalk for every candidate. A real-data evidence analysis is available now; a ranked multi-objective portfolio would still require assumptions not supplied by the report.

        **Repeat the checks:** from the project root run `python3 src/data_pipeline.py` and `python3 src/verify_gcc_calculations.py`. Dated ingestion outputs are under `data/derived/`; calculation checks are under `results/evidence/`. The original starter remains unchanged; the official GCC report PDF is available from the GCC source link on the evidence page and is kept locally, not in this GitHub repository.
        """)
        st.error("Causal result available now: none. The connected records do not establish that a GCC project caused a reduction in flooding, emissions, or harm. Do not present a causal impact number from this prototype.")
        st.markdown("""
        **Why the causal result is unavailable:** the ADB project page for the Chennai–Kosasthalaiyar flood-management project lists it as ongoing, with completion targeted for 2027, and currently lists no independent evaluation document. Its 1.9 million residents figure is planned exposure reduction, not an observed post-project result. GCC’s Climate Budget says it is establishing indicators and a system to monitor and evaluate impacts over future years.

        **What is verified here:** source publication, project descriptions, stated progress and quantities, award records, and arithmetic reproduction of five report estimates. These answer “what was reported or contracted?” They do not answer “what changed because of the project?”

        **What a defensible causal study needs:** (1) exact project footprint and commissioning date; (2) repeated outcome observations before and after, such as flood depth, duration, inundated area, road closures, or service disruption; (3) rainfall and tide/sewer conditions for each event; (4) comparable untreated locations/events; and (5) a pre-specified design, likely matched difference-in-differences/event study or a hydraulic model validated against observed flood data. Spillovers between drainage catchments must be considered. If these inputs cannot be assembled, report descriptive trends only.

        **Primary-source status:** [ADB project status and evaluation documents](https://www.adb.org/projects/49107-009/main) · [ADB 2021 project design and 1.9m target](https://www.adb.org/projects/documents/ind-49107-009-rrp) · [GCC Climate Budget 2025–26](https://www.chennaicorporation.gov.in/gcc/pdf/ClimateBudget2025-2026.pdf).
        """)
        st.caption("Model boundary: the separate scenario lab is a hypothetical benchmark demonstration using generated candidate projects, not real GCC recommendations or a live digital twin.")

    with tab_guide:
        st.markdown('<div class="section-kicker">A WALKTHROUGH YOU CAN PRESENT</div><div class="section-heading">What each part of CarbonWise does</div>', unsafe_allow_html=True)
        st.markdown("""
        **Start here — Evidence Room · GCC records.** This is the source-backed part of the prototype. It starts from the 23 projects in your supplied CSV and links each row to a GCC Climate Budget activity and printed page.

        **Overview.** Department bars count the supplied rows; they are not budget totals. The progress cards show what GCC reports in the 2025–26 Climate Budget: 5 of 11.6 km for Complete Streets, 78% for Villivakkam Tank, 55% for Chinna Nolambur bridge, and 24 CNG vehicles. These are published status claims, not live monitoring. The 43.1% Complete Streets figure is our division 5 ÷ 11.6.

        **GCC project evidence.** Filter by department, inspect all 23 source-linked project rows, then download the filtered crosswalk. The report page, status, quantity, cost and caveat travel together. Click the official GCC source link to open the report PDF.

        **Drainage awards.** This is a procurement cross-check for three tender packages matched to ADB award listings. The amount is a contract award in USD. The app intentionally shows tender estimate and actual expenditure as unknown; an awarded contract is not proof of payment or completion.

        **Calculation audit.** Five GCC GHG formulas are recalculated from the report's own inputs. You can show both the matching results and each assumption. Say “the arithmetic reproduces,” not “the emissions reduction was independently verified.”

        **Causal evidence & methods.** This tab separates published implementation facts from causal effects, checks the official evaluation status, lists the data needed for an actual impact study, and gives commands to rerun the source pipeline and calculation check.

        **Presenter guide.** This page is the short tour and includes the language to use in a review. A longer speaker script is in `docs/presenter_walkthrough.md`.

        **Scenario Lab · synthetic model.** Select it from the left workspace picker. Here you can change the budget and equity weights, inspect the 15 zone records and 56 generated benchmark projects, then click **Run Optimizer**. Its scores, Pareto frontier, baseline comparisons, scenarios, council statements and equity audit are demonstrations using generated data. They are not actual GCC project recommendations or measured Chennai outcomes. The optional budget sensitivity is also a synthetic-model analysis. Downloaded investment reports inherit that limitation.

        **Best one-sentence description:** “CarbonWise is a prototype with a source-backed GCC evidence register and tender cross-check, plus a separate synthetic multi-objective optimizer demonstrating how carbon, resilience and equity trade-offs could be explored once comparable, verified project inputs are available.”

        **Two-minute review script:** “I began with the 23 project records in the supplied GCC starter file. I matched each one to the Greater Chennai Corporation’s 2025–26 Climate Budget and show the report page, reported status, physical quantities, cost and caveats so a reviewer can trace a claim back to its source. The report gives useful delivery evidence—for example, GCC reports 5 km complete out of 11.6 km of Complete Streets, and 78% progress for Villivakkam Tank. I also reproduced five published GHG calculations directly from the report inputs; that validates arithmetic, not the underlying activity data or realised emissions. Separately, three drainage tender references match ADB award records. Contract values are shown as awards, while actual expenditure and physical completion remain unknown. The optimizer is a separate synthetic demonstration, so I do not present its scores as real Chennai recommendations. The main next evidence needed for a real ranking is project-level payment and completion records, measured outcomes, and a verified location/population crosswalk.”
        """)

# ---------------------------------------------------------------------------
# Page config + restrained, professional styling (no gradients, no emoji soup)
# ---------------------------------------------------------------------------
st.set_page_config(page_title="CarbonWise", layout="wide",
                    initial_sidebar_state="collapsed", page_icon="◆")

app_mode = st.sidebar.radio(
    "WORKSPACE",
    ["Evidence Room · GCC records", "Scenario Lab · synthetic model"],
    index=0,
    help="The evidence room is the default. The optimizer currently runs only on generated benchmark projects.",
)
if app_mode == "Evidence Room · GCC records":
    render_evidence_room()
    st.stop()

INK = "#1A2B22"
FOREST = "#0F4C3A"
MUTED = "#6B7A72"
LINE = "#DDE5E0"
GOLD = "#B8860B"
DANGER = "#9C4141"
CARD_BG = "#FBFCFB"

st.markdown(f"""
<style>
    html, body, .stApp {{
        font-family: "Times New Roman", Times, serif;
    }}
    p, span, li, td, th, label, h1, h2, h3, h4, h5, h6,
    .stMarkdown, .stDataFrame, .stButton button, .stSelectbox div, .stRadio label,
    .stTextInput input, .stNumberInput input, .stSlider label, .stCaption {{
        font-family: "Times New Roman", Times, serif;
    }}
    [data-testid="stIconMaterial"], [class*="Icon"], .material-icons,
    [data-testid="stExpanderToggleIcon"] {{
        font-family: "Material Symbols Rounded", "Material Icons" !important;
    }}
    .main {{ background-color: #FFFFFF; }}
    section[data-testid="stSidebar"] {{ background-color: #F7F9F8; border-right: 1px solid {LINE}; }}

    .cw-title {{ font-size: 26px; font-weight: 700; color: {INK}; margin-bottom: 2px; letter-spacing: -0.3px; }}
    .cw-subtitle {{ font-size: 14px; color: {MUTED}; margin-bottom: 4px; }}
    .cw-rule {{ border: none; border-top: 2px solid {FOREST}; width: 64px; margin: 10px 0 20px 0; }}

    .cw-tile {{
        background: {CARD_BG}; border: 1px solid {LINE}; border-radius: 6px;
        padding: 14px 18px; margin-bottom: 10px;
    }}
    .cw-tile-label {{ font-size: 11px; color: {MUTED}; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px; }}
    .cw-tile-value {{ font-size: 28px; font-weight: 700; color: {INK}; line-height: 1.1; }}
    .cw-tile-context {{ font-size: 12px; color: {MUTED}; margin-top: 2px; }}

    .cw-finding {{
        border-left: 3px solid {FOREST}; background: {CARD_BG}; border-radius: 4px;
        padding: 10px 14px; margin-bottom: 8px; font-size: 14px; color: {INK};
    }}
    .cw-finding b {{ color: {FOREST}; }}

    .cw-callout {{
        background: #FBF7EC; border: 1px solid {GOLD}; border-radius: 6px;
        padding: 14px 18px; margin: 10px 0; font-size: 14px; color: {INK};
    }}
    .cw-source {{ font-size: 11px; color: {MUTED}; font-style: italic; }}

    div.stButton > button[kind="primary"] {{
        background-color: {FOREST}; border-color: {FOREST};
    }}
    div.stButton > button[kind="primary"]:hover {{
        background-color: {INK}; border-color: {INK};
    }}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="cw-title">CarbonWise</div>
<div class="cw-subtitle">Cross-sector infrastructure investment platform — solar, transit, EV charging, drainage, green corridors, flood defenses & building retrofits — unified under equity-aware multi-objective optimisation. Chennai pilot.</div>
<hr class="cw-rule"/>
""", unsafe_allow_html=True)
st.warning(
    "SYNTHETIC SCENARIO LAB: the optimizer below uses generated benchmark-range projects, "
    "not the GCC starter or verified tender packages. The real-data evidence room has 0 "
    "model-ready starter records. Any displayed scores are hypothetical model outputs, "
    "not observed Chennai outcomes or funding recommendations."
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.markdown("**Budget & Priorities**")
budget_cr = st.sidebar.number_input("Available budget (₹ crore)", min_value=5.0,
                                     max_value=500.0, value=50.0, step=5.0)

st.sidebar.markdown("**Equity metric weights**")
w1 = st.sidebar.slider("Vulnerability", 0.0, 1.0, 0.33)
w2 = st.sidebar.slider("Population benefited", 0.0, 1.0, 0.33)
w3 = st.sidebar.slider("Infrastructure deprivation", 0.0, 1.0, 0.34)
total_w = w1 + w2 + w3
w1, w2, w3 = (w1/total_w, w2/total_w, w3/total_w) if total_w else (1/3, 1/3, 1/3)

run_button = st.sidebar.button("Run Optimizer", type="primary", use_container_width=True)
run_sensitivity_btn = st.sidebar.checkbox("Also run budget sensitivity analysis (~10s extra)", value=False)

st.sidebar.markdown("---")
st.sidebar.markdown("**Data sources**")
st.sidebar.caption(
    "Ward vulnerability: Nandhini, Das & Shinde (2025), IIT Kharagpur/NIUA — "
    "TOPSIS composite vulnerability index for Chennai's 15 GCC zones.\n\n"
    "Project cost/impact ranges: MNRE, CEA, CPHEEO, FAME-II published benchmarks."
)

# ---------------------------------------------------------------------------
# Load + score data
# ---------------------------------------------------------------------------
@st.cache_data
def load_data(w1, w2, w3):
    df = preprocess()
    df = compute_equity_score(df, w1=w1, w2=w2, w3=w3)
    # Resolve data from the repository root so the app works both locally and
    # on hosted Streamlit, which starts the entrypoint from the repository root.
    wards = pd.read_csv(PROJECT_ROOT / "data/raw/wards.csv")
    return df, wards

df, wards = load_data(w1, w2, w3)

# ---------------------------------------------------------------------------
# Infrastructure category overview -- makes the cross-sector scope of the
# platform immediately visible, rather than buried in a data table
# ---------------------------------------------------------------------------
st.markdown("**Infrastructure categories evaluated**")
_cat_summary = df.groupby("category").agg(
    n_projects=("project_id", "count"),
    total_cost=("cost_cr_inr", "sum"),
).reset_index().sort_values("total_cost", ascending=False)

_cat_cols = st.columns(4)
for i, (_, row) in enumerate(_cat_summary.iterrows()):
    with _cat_cols[i % 4]:
        st.markdown(f"""
        <div class="cw-tile" style="min-height: 92px;">
            <div class="cw-tile-label" style="font-size:10.5px; line-height:1.3;">{row['category']}</div>
            <div class="cw-tile-value" style="font-size:20px; margin-top:4px;">{int(row['n_projects'])} projects</div>
            <div class="cw-tile-context">\u20b9{row['total_cost']:.0f} cr candidate cost</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

tab_map, tab_data, tab_results = st.tabs(["Zone Profile", "Candidate Projects", "Investment Analysis"])

# ---------------------------------------------------------------------------
# Data validation report (sidebar) -- shown before any optimization runs,
# so the panel sees the system checks its inputs before trusting them
# ---------------------------------------------------------------------------
_validation = validate_data(df, wards)
with st.sidebar.expander(
    f"Data quality: {'Ready' if _validation['status'] == 'READY' else 'Issues found'}",
    expanded=False
):
    st.markdown(f"""
    - Projects loaded: **{_validation['n_projects']}**
    - Chennai zones: **{_validation['n_zones']}**
    - Project categories: **{_validation['n_categories']}**
    - Total candidate cost: **₹{_validation['total_candidate_cost_cr']} cr**
    - Missing values: **{_validation['n_missing_values']}**
    """)
    if _validation["issues"]:
        for issue in _validation["issues"]:
            st.warning(issue)


# ---------------------------------------------------------------------------
# TAB 1: Zone map / profile
# ---------------------------------------------------------------------------
with tab_map:
    col_map, col_detail = st.columns([2, 1])

    with col_map:
        fig_map = px.scatter(
            wards, x="lon", y="lat", size="approx_population_2023",
            color="vulnerability_index", color_continuous_scale="YlOrRd",
            hover_name="zone_name",
            hover_data={"lon": False, "lat": False, "vulnerability_index": ":.2f",
                        "infrastructure_deprivation_index": ":.2f",
                        "approx_population_2023": True},
            size_max=48, height=520,
        )
        fig_map.update_traces(marker=dict(line=dict(width=1.5, color="white")))
        fig_map.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis_title="West \u2192 East", yaxis_title="South \u2192 North",
            plot_bgcolor="#F2F5F3", paper_bgcolor="white",
            coloraxis_colorbar=dict(title="Vulnerability"),
        )
        fig_map.update_yaxes(scaleanchor="x", scaleratio=1)
        for _, row in wards.iterrows():
            fig_map.add_annotation(x=row["lon"], y=row["lat"], text=row["zone_name"],
                                    showarrow=False, yshift=15, font=dict(size=9, color=INK))
        st.plotly_chart(fig_map, use_container_width=True)
        st.caption("Zones positioned by real relative latitude/longitude. Bubble size = population, "
                   "color = vulnerability index.")


    with col_detail:
        st.markdown("**Zone inspector**")
        selected_zone = st.selectbox("Select a zone", wards["zone_name"].tolist(), label_visibility="collapsed")
        zrow = wards[wards["zone_name"] == selected_zone].iloc[0]

        st.markdown(f"""
        <div class="cw-tile"><div class="cw-tile-label">Vulnerability Index</div>
            <div class="cw-tile-value">{zrow['vulnerability_index']:.2f}</div></div>
        <div class="cw-tile"><div class="cw-tile-label">Infrastructure Deprivation</div>
            <div class="cw-tile-value">{zrow['infrastructure_deprivation_index']:.2f}</div></div>
        <div class="cw-tile"><div class="cw-tile-label">Population (2023 est.)</div>
            <div class="cw-tile-value">{zrow['approx_population_2023']:,}</div></div>
        """, unsafe_allow_html=True)

        n_candidate_projects = len(df[df["zone_id"] == zrow["zone_id"]])
        st.markdown(f"**Candidate projects in zone:** {n_candidate_projects}")
        st.markdown(f'<div class="cw-source">Source: {zrow["data_source"]}<br>{zrow["notes"]}</div>',
                     unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# TAB 2: Candidate projects table
# ---------------------------------------------------------------------------
with tab_data:
    fig_cat = go.Figure(go.Bar(
        x=_cat_summary["total_cost"], y=_cat_summary["category"],
        orientation="h", marker_color=FOREST,
        text=_cat_summary["n_projects"].astype(str) + " projects",
        textposition="outside",
    ))
    fig_cat.update_layout(height=280, margin=dict(l=0, r=150, t=10, b=0),
                           xaxis_title="Total candidate cost (\u20b9 crore)",
                           plot_bgcolor="white")
    st.plotly_chart(fig_cat, use_container_width=True)

    st.markdown("**Filter by category**")
    selected_categories = st.multiselect(
        "Category", options=sorted(df["category"].unique()),
        default=sorted(df["category"].unique()), label_visibility="collapsed"
    )

    st.markdown("**Candidate infrastructure projects**")
    filtered_df = df[df["category"].isin(selected_categories)] if selected_categories else df
    st.dataframe(
        filtered_df[["project_id", "project_name", "category", "zone_name",
            "cost_cr_inr", "carbon_score_raw", "resilience_score_raw", "equity_score"]]
        .rename(columns={"cost_cr_inr": "cost_₹cr", "carbon_score_raw": "carbon_score",
                          "resilience_score_raw": "resilience_score"})
        .round(1),
        height=400, use_container_width=True, hide_index=True
    )

# ---------------------------------------------------------------------------
# TAB 3: Investment analysis (optimizer, scenarios, findings, equity audit, sensitivity)
# ---------------------------------------------------------------------------
with tab_results:
    if not run_button:
        st.info("Set your budget and priority weights in the sidebar, then click **Run Optimizer**.")
    else:
        with st.spinner("Solving multi-objective portfolio selection (NSGA-II)..."):
            res, problem = run_nsga2(df, budget_cr)
            front_df = pareto_front_to_df(res, problem, df)
            balanced = pick_balanced_solution(front_df)

            eq_mask = equal_split_allocation(df, budget_cr)
            greedy_mask = greedy_cost_effectiveness_allocation(df, budget_cr)
            cw_ids = balanced["selected_projects"].split(";")
            cw_mask = df["project_id"].isin(cw_ids)

            comparison = pd.DataFrame([
                summarize_portfolio(df, eq_mask, "Equal Split"),
                summarize_portfolio(df, greedy_mask, "Greedy Cost-Effectiveness"),
                summarize_portfolio(df, cw_mask, "CarbonWise"),
            ])
            scenarios_df = build_scenarios(front_df)
            council = full_council_report(comparison, budget_cr)
            greedy_ids = df[greedy_mask]["project_id"].tolist()
            audit = audit_report(df, wards, greedy_ids, cw_ids)

        # --- KPI tiles ---
        c1, c2, c3, c4 = st.columns(4)
        for col, label, val, ctx in [
            (c1, "Carbon Score", f"{balanced['carbon_score']:.0f}", "sum across funded projects"),
            (c2, "Resilience Score", f"{balanced['resilience_score']:.0f}", "sum across funded projects"),
            (c3, "Equity Score", f"{balanced['equity_score']:.0f}", "sum across funded projects"),
            (c4, "Budget Utilised", f"{balanced['total_cost_cr']/budget_cr*100:.0f}%",
             f"₹{balanced['total_cost_cr']:.1f} cr of ₹{budget_cr:.0f} cr"),
        ]:
            col.markdown(f'<div class="cw-tile"><div class="cw-tile-label">{label}</div>'
                          f'<div class="cw-tile-value">{val}</div>'
                          f'<div class="cw-tile-context">{ctx}</div></div>', unsafe_allow_html=True)

        st.markdown("---")

        # --- Why this portfolio: structured decision rationale ---
        st.markdown("#### Why this portfolio?")
        rationale = build_rationale(front_df, balanced, budget_cr, audit)
        for i, point in enumerate(rationale, 1):
            st.markdown(f'<div class="cw-finding"><b>{i}. {point["title"]}.</b> {point["detail"]}</div>',
                         unsafe_allow_html=True)

        st.markdown("---")

        st.markdown("#### Comparison against conventional allocation methods")
        fig_comp = go.Figure()
        for metric, color in zip(["carbon_score", "resilience_score", "equity_score"],
                                   [FOREST, "#3D6B8C", GOLD]):
            fig_comp.add_trace(go.Bar(name=metric.replace("_score", "").title(),
                                       x=comparison["method"], y=comparison[metric], marker_color=color))
        fig_comp.update_layout(barmode="group", height=360, margin=dict(l=0, r=0, t=10, b=0),
                                plot_bgcolor="white", legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_comp, use_container_width=True)

        st.markdown("---")

        # --- Scenario simulator ---
        st.markdown("#### Scenario comparison")
        st.caption("Four trade-off points drawn from the same Pareto front — not independently re-optimized runs.")
        fig_scen = go.Figure()
        for metric, color in zip(["carbon_score", "resilience_score", "equity_score"],
                                   [FOREST, "#3D6B8C", GOLD]):
            fig_scen.add_trace(go.Bar(name=metric.replace("_score", "").title(),
                                       x=scenarios_df["scenario"], y=scenarios_df[metric], marker_color=color))
        fig_scen.update_layout(barmode="group", height=360, margin=dict(l=0, r=0, t=10, b=0),
                                plot_bgcolor="white", legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_scen, use_container_width=True)
        st.dataframe(scenarios_df[["scenario", "n_projects", "total_cost_cr",
                                     "carbon_score", "resilience_score", "equity_score"]].round(1),
                     use_container_width=True, hide_index=True)

        st.markdown("---")

        # --- Findings + Pareto front ---
        col_findings, col_pareto = st.columns([1, 1])
        with col_findings:
            st.markdown("#### Key findings")
            ai_status = "AI explanation: enabled" if llm_client.is_available() else "AI explanation: not configured (using rule-based analysis)"
            st.caption(ai_status)

            context = {
                "budget_cr": budget_cr,
                "carbon_score": round(balanced["carbon_score"], 0),
                "resilience_score": round(balanced["resilience_score"], 0),
                "equity_score": round(balanced["equity_score"], 0),
                "projects_funded": int(balanced["n_projects"]),
                "budget_utilised_pct": round(balanced["total_cost_cr"] / budget_cr * 100, 0),
                "greedy_carbon_score": round(comparison[comparison["method"].str.contains("Greedy")]["carbon_score"].iloc[0], 0),
                "high_vulnerability_investment_share_pct": round(audit["after"]["actual_share_pct"], 0),
            }
            explanation = generate_explanation(context, comparison, budget_cr)
            st.markdown(f'<div class="cw-finding">{explanation["text"]}</div>', unsafe_allow_html=True)
            if explanation["source"] == "llm":
                st.caption("Generated by LLM from verified optimizer output.")
            elif explanation["error"]:
                st.caption(f"Note: {explanation['error']}")

            with st.expander("Per-agent breakdown"):
                for entry in council:
                    label = entry["agent"]
                    st.markdown(f'<div class="cw-finding"><b>{label}.</b> {entry["statement"]}</div>',
                                 unsafe_allow_html=True)

        with col_pareto:
            st.markdown("#### Pareto-optimal trade-off frontier")
            fig_pareto = px.scatter(front_df, x="carbon_score", y="resilience_score",
                                     color="equity_score", color_continuous_scale="Viridis",
                                     hover_data={"n_projects": True, "total_cost_cr": ":.1f",
                                                 "carbon_score": ":.0f", "resilience_score": ":.0f",
                                                 "equity_score": ":.0f"},
                                     height=380)
            fig_pareto.add_trace(go.Scatter(
                x=[balanced["carbon_score"]], y=[balanced["resilience_score"]],
                mode="markers", marker=dict(symbol="star", size=20, color=DANGER,
                                             line=dict(color=INK, width=1)),
                name="Recommended",
                hovertext=f"RECOMMENDED<br>Projects: {int(balanced['n_projects'])}<br>"
                          f"Cost: \u20b9{balanced['total_cost_cr']:.1f} cr<br>"
                          f"Carbon: {balanced['carbon_score']:.0f} | "
                          f"Resilience: {balanced['resilience_score']:.0f} | "
                          f"Equity: {balanced['equity_score']:.0f}",
                hoverinfo="text"))
            fig_pareto.update_layout(margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white")
            st.plotly_chart(fig_pareto, use_container_width=True)
            st.caption(f"{len(front_df)} non-dominated solutions found across {len(df)} candidate projects.")

        st.markdown("---")

        # --- Equity Audit ---
        st.markdown("#### Distributive equity audit")
        st.caption("Share of total investment reaching Chennai's high-vulnerability zones, "
                   "benchmarked against a population-proportional target based on Chennai "
                   "residents living in zones classified as high-vulnerability (Justice40-style metric).")
        col_before, col_after = st.columns(2)
        with col_before:
            st.markdown(f"""
            <div class="cw-tile"><div class="cw-tile-label">Greedy (cost-effectiveness only)</div>
                <div class="cw-tile-value" style="color:{DANGER}">{audit['before']['actual_share_pct']:.0f}%</div>
                <div class="cw-tile-context">of investment to high-vulnerability zones
                (target: {audit['target_share_pct']:.0f}%, gap {audit['before']['gap_pct_points']:.0f} pts)</div>
            </div>""", unsafe_allow_html=True)
        with col_after:
            st.markdown(f"""
            <div class="cw-tile"><div class="cw-tile-label">CarbonWise</div>
                <div class="cw-tile-value" style="color:{FOREST}">{audit['after']['actual_share_pct']:.0f}%</div>
                <div class="cw-tile-context">of investment to high-vulnerability zones
                (target: {audit['target_share_pct']:.0f}%, gap {audit['after']['gap_pct_points']:+.0f} pts)</div>
            </div>""", unsafe_allow_html=True)

        if audit["before"]["gap_pct_points"] < -5:
            st.markdown(f"""
            <div class="cw-callout">
                <b>Distributive shortfall detected.</b> Cost-effectiveness-only allocation directs
                {audit['before']['actual_share_pct']:.0f}% of investment to zones holding
                {audit['target_share_pct']:.0f}% of Chennai's high-vulnerability population — a
                {abs(audit['before']['gap_pct_points']):.0f}-point shortfall, consistent with the
                underinvestment pattern documented empirically in Nandhini et al. (2025).
                CarbonWise's recommended portfolio corrects this to
                {audit['after']['actual_share_pct']:.0f}% ({audit['improvement_pct_points']:+.0f} points)
                by encoding equity as an explicit optimisation objective.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="cw-callout">
                <b>Honest reading of this result.</b> At this budget, both methods currently meet
                or exceed the population-proportional target ({audit['target_share_pct']:.0f}%).
                CarbonWise does not claim to always outperform Greedy on this specific
                investment-share metric — its measured advantage here is in resilience and the
                weighted equity score (above). CarbonWise's contribution is that equity is encoded
                as an explicit, auditable optimisation objective and independently audited on every
                run, rather than assumed.
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # --- Sensitivity analysis (optional, slower) ---
        if run_sensitivity_btn:
            st.markdown("#### Budget sensitivity")
            st.caption("How outcomes and marginal returns change as available budget scales — "
                       "useful for a finance department deciding whether additional budget is worth requesting.")
            with st.spinner("Running optimizer across 5 budget levels (~10-15s)..."):
                levels = sorted(set([max(10, budget_cr * f) for f in [0.4, 0.7, 1.0, 1.5, 2.0]]))
                sens_df = run_sensitivity(df, levels, pop_size=80, n_gen=100)

            fig_sens = go.Figure()
            for metric, color in zip(["carbon_score", "resilience_score", "equity_score"],
                                       [FOREST, "#3D6B8C", GOLD]):
                fig_sens.add_trace(go.Scatter(x=sens_df["budget_cr"], y=sens_df[metric],
                                                mode="lines+markers", name=metric.replace("_score","").title(),
                                                line=dict(color=color, width=2)))
            fig_sens.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white",
                                    xaxis_title="Budget (₹ crore)", yaxis_title="Score",
                                    legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig_sens, use_container_width=True)

            sens_df["marginal_carbon_per_cr"] = sens_df["carbon_score"].diff() / sens_df["budget_cr"].diff()
            st.dataframe(sens_df.round(2), use_container_width=True, hide_index=True)
            st.caption("Marginal carbon score gained per additional ₹1 crore — a declining trend indicates "
                       "diminishing returns on further budget increases.")
            st.markdown("---")

        # --- Recommended portfolio + export ---
        st.markdown("#### Recommended portfolio")
        recommended = df[df["project_id"].isin(cw_ids)][
            ["project_id", "project_name", "category", "zone_name", "cost_cr_inr",
             "carbon_score_raw", "resilience_score_raw", "equity_score"]
        ].round(1)
        st.dataframe(recommended, use_container_width=True, hide_index=True)

        csv_buffer = StringIO()
        recommended.to_csv(csv_buffer, index=False)
        report_header = (
            f"# CarbonWise Investment Brief\n"
            f"# Generated: {date.today().isoformat()}\n"
            f"# Budget: Rs. {budget_cr:.1f} crore | Utilised: Rs. {balanced['total_cost_cr']:.1f} crore "
            f"({balanced['total_cost_cr']/budget_cr*100:.0f}%)\n"
            f"# Carbon score: {balanced['carbon_score']:.0f} | Resilience score: {balanced['resilience_score']:.0f} "
            f"| Equity score: {balanced['equity_score']:.0f}\n"
            f"# Equity weights used: vulnerability={w1:.2f}, population_benefited={w2:.2f}, "
            f"infrastructure_deprivation={w3:.2f}\n\n"
        )

        full_report_text = generate_report(df, wards, budget_cr, balanced, front_df,
                                            comparison, audit, rationale, (w1, w2, w3))

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "Download full investment decision report (TXT)",
                data=full_report_text,
                file_name=f"carbonwise_decision_report_{date.today().isoformat()}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col_dl2:
            st.download_button(
                "Download portfolio only (CSV)",
                data=report_header + csv_buffer.getvalue(),
                file_name=f"carbonwise_portfolio_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
            )
