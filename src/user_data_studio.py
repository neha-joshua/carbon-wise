"""Streamlit workflow for user data, NSGA-II runs, counterfactuals and field photos."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import zipfile

import pandas as pd
import plotly.express as px
import streamlit as st

from user_data_workflow import (
    REQUIRED_FIELDS, analyze_image_pixels, build_optimizer_frame,
    default_column_mapping, load_uploaded_table, map_to_carbonwise,
    validate_mapped_data,
)
from baselines import equal_split_allocation, greedy_cost_effectiveness_allocation
from optimizer import run_nsga2, pareto_front_to_df, pick_balanced_solution


ROOT = Path(__file__).resolve().parents[1]
SESSION_KEYS = ["cw_source_frame", "cw_source_name", "cw_source_sha256", "cw_mapping",
                "cw_working_data", "cw_cost_unit", "cw_latest_result", "cw_previous_result",
                "cw_confirmed_audits", "cw_last_uploaded_sha", "cw_latest_audit_photo", "cw_audit_images"]


def _run_nsga(df, budget, priorities, equity_floor=None):
    result, problem = run_nsga2(
        df, budget, pop_size=96, n_gen=100, seed=7, equity_floor=equity_floor,
        carbon_col="carbon_reduction_tco2_per_year",
        resilience_col="resilience_benefit_raw", equity_col="equity_score",
        cost_col="cost_cr_inr",
    )
    front = pareto_front_to_df(result, problem, df)
    if front.empty:
        raise ValueError("No feasible portfolio was found. Increase the budget, lower the equity floor, or correct the mapped inputs.")
    balanced = pick_balanced_solution(front, weights=priorities)
    selected_ids = set(balanced["selected_projects"].split(";")) if balanced["selected_projects"] else set()
    # Recheck with unrounded source costs and the configured equity floor.
    selected = df[df["project_id"].astype(str).isin(selected_ids)]
    spent = float(selected["cost_cr_inr"].sum())
    if spent > budget + 1e-7:
        raise RuntimeError("Optimizer returned a portfolio above the configured budget; results were withheld.")
    if equity_floor is not None and not selected.empty and selected["equity_score"].mean() + 1e-7 < equity_floor:
        raise RuntimeError("Optimizer returned a portfolio below the configured equity floor; results were withheld.")
    masks = {
        "CarbonWise · NSGA-II": df["project_id"].astype(str).isin(selected_ids),
        "Equal split baseline": equal_split_allocation(df, budget),
        "Carbon-efficiency baseline": greedy_cost_effectiveness_allocation(df, budget),
    }
    return result, problem, front, balanced, selected_ids, masks


def _portfolio_metrics(df, ids):
    sub = df[df["project_id"].astype(str).isin(set(ids))]
    return {
        "projects": int(len(sub)),
        "cost": float(sub["cost_cr_inr"].sum()),
        "carbon": float(sub["carbon_reduction_tco2_per_year"].sum()),
        "resilience": float(sub["resilience_benefit_raw"].sum()),
        "equity_mean": float(sub["equity_score"].mean()) if len(sub) else 0.0,
        "equity_total": float(sub["equity_score"].sum()),
    }


def _source_rows(source, id_column, selected_ids):
    ids = set(map(str, selected_ids))
    original_ids = source[id_column].astype("string").str.strip()
    return source.loc[original_ids.isin(ids)].copy()


def _source_rows_at_positions(source, positions):
    valid = sorted({int(value) for value in positions if pd.notna(value) and 0 <= int(value) < len(source)})
    return source.iloc[valid].copy()


def _present_mapped_frame(frame, cost_unit):
    display = frame.drop(columns=["_source_row"], errors="ignore").copy()
    display = display.rename(columns={
        "cost_cr_inr": f"cost ({cost_unit})",
        "carbon_reduction_tco2_per_year": "annual carbon benefit (input units)",
        "resilience_benefit_raw": "resilience benefit (input units)",
        "equity_raw": "equity input value",
        "equity_score": "equity comparison score (0-100, dataset-relative)",
        "carbon_score_raw": "carbon baseline comparison score (0-100, dataset-relative)",
        "resilience_score_raw": "resilience baseline comparison score (0-100, dataset-relative)",
    })
    return display


def _reset_active_dataset():
    for key in SESSION_KEYS:
        st.session_state.pop(key, None)
    st.session_state.pop("cw_mapped_editor", None)


def _load_source_into_state(source, source_name, content):
    st.session_state["cw_source_frame"] = source.copy()
    st.session_state["cw_source_name"] = source_name
    st.session_state["cw_source_sha256"] = sha256(content).hexdigest()
    st.session_state["cw_last_uploaded_sha"] = sha256(content).hexdigest()
    st.session_state["cw_working_data"] = None
    st.session_state["cw_mapping"] = None
    st.session_state["cw_latest_result"] = None
    st.session_state["cw_previous_result"] = None
    st.session_state.pop("cw_mapped_editor", None)


def _make_export_packet(source, result):
    selected_ids = result["selected_ids"]
    selected_engine = result["engine_df"][result["engine_df"]["project_id"].astype(str).isin(selected_ids)]
    excluded_engine = result["engine_df"][~result["engine_df"]["project_id"].astype(str).isin(selected_ids)]
    selected_original = _source_rows_at_positions(source, selected_engine["_source_row"])
    selected_original["carbonwise_selected"] = True
    excluded_original = _source_rows_at_positions(source, excluded_engine["_source_row"])
    excluded_original["carbonwise_selected"] = False
    selected_canonical = _present_mapped_frame(selected_engine, result["cost_unit"])
    excluded_canonical = _present_mapped_frame(excluded_engine, result["cost_unit"])
    selected_buf, excluded_buf, selected_canonical_buf, excluded_canonical_buf, pareto_buf, audit_buf = (BytesIO(), BytesIO(), BytesIO(), BytesIO(), BytesIO(), BytesIO())
    selected_original.to_csv(selected_buf, index=False)
    excluded_original.to_csv(excluded_buf, index=False)
    selected_canonical.to_csv(selected_canonical_buf, index=False)
    excluded_canonical.to_csv(excluded_canonical_buf, index=False)
    result["front"].to_csv(pareto_buf, index=False)
    pd.DataFrame(result.get("audit_log", [])).to_csv(audit_buf, index=False)
    meta = {
        "dataset": result["source_name"],
        "source_sha256": result["source_sha256"],
        "mapped_model_input_sha256": result["model_input_sha256"],
        "run_at_utc": result["run_at_utc"],
        "budget": result["budget"],
        "cost_unit_as_entered": result["cost_unit"],
        "objectives": ["annual carbon benefit", "resilience benefit", "normalized equity score"],
        "objective_preferences": result["priorities"],
        "minimum_average_equity_score_0_100": result["equity_floor"],
        "optimizer": "pymoo NSGA-II; 96 individuals x 100 generations; seed 7",
        "selected_portfolio_metrics": result["metrics"],
        "data_basis": "User-supplied values; no missing model field was imputed.",
    }
    packet = BytesIO()
    with zipfile.ZipFile(packet, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("selected_projects.csv", selected_buf.getvalue())
        archive.writestr("excluded_projects.csv", excluded_buf.getvalue())
        archive.writestr("selected_projects_mapped_and_corrected.csv", selected_canonical_buf.getvalue())
        archive.writestr("excluded_projects_mapped_and_corrected.csv", excluded_canonical_buf.getvalue())
        archive.writestr("pareto_front.csv", pareto_buf.getvalue())
        archive.writestr("confirmed_field_audits.csv", audit_buf.getvalue())
        archive.writestr("run_manifest.json", json.dumps(meta, indent=2, ensure_ascii=False))
        for audit in result.get("audit_log", []):
            photo_bytes = st.session_state.get("cw_audit_images", {}).get(audit.get("image_sha256"))
            if photo_bytes:
                suffix = Path(audit.get("image_filename", "photo.jpg")).suffix.lower()
                if suffix not in {".png", ".jpg", ".jpeg"}:
                    suffix = ".jpg"
                archive.writestr(f"field_audit_photos/{audit['image_sha256']}{suffix}", photo_bytes)
    return packet.getvalue()


def _make_audit_packet(audits):
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("confirmed_field_audits.csv", pd.DataFrame(audits).to_csv(index=False))
        for audit in audits:
            photo_bytes = st.session_state.get("cw_audit_images", {}).get(audit.get("image_sha256"))
            if photo_bytes:
                suffix = Path(audit.get("image_filename", "photo.jpg")).suffix.lower()
                if suffix not in {".png", ".jpg", ".jpeg"}:
                    suffix = ".jpg"
                archive.writestr(f"photos/{audit['image_sha256']}{suffix}", photo_bytes)
    return buf.getvalue()


def _data_workspace(source):
    st.markdown("### 1 · Data Workspace")
    st.write("Upload CSV or Excel, inspect its shape and quality, map the five model fields, then correct or delete rows before any optimization.")
    uploader, actions = st.columns([3, 1])
    with uploader:
        uploaded = st.file_uploader("Project data (.csv, .xlsx, .xlsm)", type=["csv", "xlsx", "xlsm"], key="cw_upload_file")
    with actions:
        st.download_button(
            "Download synthetic example CSV",
            pd.read_csv(ROOT / "data/demo/carbonwise_synthetic_demo.csv").to_csv(index=False).encode(),
            "carbonwise_synthetic_demo_template.csv", "text/csv",
            help="This template contains invented example values and is not evidence about actual projects.",
            use_container_width=True,
        )
        if st.button("Load synthetic demo", use_container_width=True, help="Loads a clearly labeled invented sample dataset."):
            raw = (ROOT / "data/demo/carbonwise_synthetic_demo.csv").read_bytes()
            demo = pd.read_csv(BytesIO(raw))
            _load_source_into_state(demo, "SYNTHETIC DEMO — invented sample values", raw)
            st.session_state["cw_cost_unit"] = "crore INR (illustrative)"
            st.rerun()
    if st.button("Clear active dataset", key="cw_clear_data"):
        if uploaded is not None:
            st.session_state["cw_ignored_upload_sha"] = sha256(uploaded.getvalue()).hexdigest()
        _reset_active_dataset()
        st.rerun()

    if uploaded is not None:
        content = uploaded.getvalue()
        upload_hash = sha256(content).hexdigest()
        if upload_hash != st.session_state.get("cw_ignored_upload_sha") and upload_hash != st.session_state.get("cw_last_uploaded_sha"):
            try:
                raw_frame = load_uploaded_table(uploaded.name, content)
                if len(raw_frame) > 500:
                    raise ValueError("Keep uploads to 500 candidate projects or fewer for a responsive NSGA-II demo.")
                _load_source_into_state(raw_frame, uploaded.name, content)
            except Exception as exc:
                st.error(f"Could not read upload: {exc}")
    source = st.session_state.get("cw_source_frame")
    if source is None:
        st.info("Upload project data or load the synthetic demo to begin. Nothing is analyzed until you map fields and run the optimizer.")
        return

    name = st.session_state.get("cw_source_name", "User upload")
    if name.startswith("SYNTHETIC DEMO"):
        st.warning("SYNTHETIC DEMO DATA — all project rows and impact values are invented for interface demonstration. Do not present them as Chennai project evidence.")
    else:
        st.success(f"Active dataset: **{name}** · {len(source):,} rows · SHA-256 `{st.session_state.get('cw_source_sha256','')[:16]}…`")

    st.markdown("#### File profile")
    p1, p2, p3 = st.columns(3)
    p1.metric("Rows × columns", f"{source.shape[0]:,} × {source.shape[1]:,}")
    p2.metric("Duplicate full rows", f"{int(source.duplicated().sum()):,}")
    p3.metric("Cells missing", f"{int(source.isna().sum().sum()):,}")
    profile = pd.DataFrame({"column": source.columns.astype(str), "data type": source.dtypes.astype(str).values,
                            "missing": source.isna().sum().values,
                            "distinct": source.nunique(dropna=True).values})
    st.dataframe(profile, hide_index=True, use_container_width=True)
    st.dataframe(source.head(12), hide_index=True, use_container_width=True)

    columns = list(source.columns)
    choices = ["(not mapped)"] + columns
    guesses = default_column_mapping(columns)
    with st.expander("Map source columns to the CarbonWise model", expanded=st.session_state.get("cw_working_data") is None):
        with st.form("cw_column_mapping"):
            left, middle, right = st.columns(3)
            mapping = {}
            fields = list(REQUIRED_FIELDS.items())
            for i, (field, label) in enumerate(fields):
                col = [left, middle, right][i % 3]
                with col:
                    default = guesses[field]
                    mapping[field] = st.selectbox(label + " (required)", choices,
                        index=choices.index(default) if default in choices else 0, key=f"cw_map_{field}")
            for field, label in [("project_name", "Project name"), ("category", "Category"), ("zone_id", "Ward / zone")]:
                with right:
                    default = guesses[field]
                    mapping[field] = st.selectbox(label + " (optional)", choices,
                        index=choices.index(default) if default in choices else 0, key=f"cw_map_{field}")
            cost_unit = st.text_input("Cost unit label (e.g. crore INR, USD, or points)",
                value=st.session_state.get("cw_cost_unit", "same unit as uploaded cost column"))
            applied = st.form_submit_button("Apply mapping to working dataset", type="primary")
        if applied:
            try:
                mapped = map_to_carbonwise(source, mapping)
                st.session_state["cw_working_data"] = mapped
                st.session_state["cw_mapping"] = mapping
                st.session_state["cw_cost_unit"] = cost_unit.strip() or "same unit as uploaded cost column"
                st.session_state.pop("cw_mapped_editor", None)
            except ValueError as exc:
                st.error(str(exc))

    mapped = st.session_state.get("cw_working_data")
    if mapped is None:
        st.info("Map the required ID, cost, carbon, resilience, and equity fields to create the working dataset.")
        return
    st.markdown("#### Correct or exclude rows")
    st.caption("Edit mapped values in place or use the row controls to remove invalid records. Unmapped source fields remain attached to the original upload for exports.")
    editable_cols = ["project_id", "project_name", "category", "zone_id", "cost_cr_inr",
                     "carbon_reduction_tco2_per_year", "resilience_benefit_raw", "equity_raw"]
    edited = st.data_editor(mapped[editable_cols + ["_source_row"]], key="cw_mapped_editor", num_rows="dynamic",
        use_container_width=True, hide_index=True,
        column_config={"cost_cr_inr": st.column_config.NumberColumn("Cost", format="%.4f"),
            "carbon_reduction_tco2_per_year": st.column_config.NumberColumn("Carbon benefit · input units", format="%.4f"),
            "resilience_benefit_raw": st.column_config.NumberColumn("Resilience benefit · input units", format="%.4f"),
            "equity_raw": st.column_config.NumberColumn("Equity benefit · input units", format="%.4f"),
            "_source_row": None})
    if "_source_row" not in edited:
        edited["_source_row"] = -1
    edited["_source_row"] = pd.to_numeric(edited["_source_row"], errors="coerce").fillna(-1).astype(int)
    st.session_state["cw_working_data"] = edited
    issues = validate_mapped_data(edited)
    if not issues.empty:
        st.error(f"{len(issues):,} blocking data-quality issue(s). Correct the mapped table or delete invalid rows before optimizing.")
        st.dataframe(issues, hide_index=True, use_container_width=True)
    else:
        st.success(f"Validation passed: {len(edited):,} unique project rows with complete numeric model inputs.")
    st.caption("Equity is min–max normalized within this dataset to a 0–100 comparison scale for constraints and portfolio selection. The original mapped value remains available as `equity_raw`. No missing model value is imputed.")


def _visual_audit(source):
    st.markdown("### 2 · Visual Street Audit")
    st.write("Capture or upload a street photo. CarbonWise computes simple color-pixel shares locally, then asks a person to label and confirm the observation.")
    if source is None:
        st.info("Load project data first if you want to associate this observation with one of its wards/zones.")
    shot = st.camera_input("Capture a street observation", key="cw_camera_capture")
    uploaded = st.file_uploader("Or upload a street photo", type=["png", "jpg", "jpeg"], key="cw_audit_photo")
    photo = shot if shot is not None else uploaded
    if photo is None:
        st.caption("Camera requires browser permission and a secure browser context. If it is unavailable, upload a photo instead.")
        return
    photo_bytes = photo.getvalue()
    st.image(photo_bytes, caption="Original user-submitted image", use_container_width=True)
    try:
        image, result = analyze_image_pixels(photo_bytes)
    except Exception as exc:
        st.error(f"Image could not be analyzed ({exc}). You can still record a note without the pixel summary.")
        return
    a, b, c = st.columns(3)
    a.metric("Green-hued pixels", f"{result['green_hued_pixel_share_pct']:.1f}%")
    b.metric("Low-saturation gray pixels", f"{result['low_saturation_gray_pixel_share_pct']:.1f}%")
    c.metric("Analyzed pixels", f"{result['sampled_pixels']:,}")
    st.warning("Color-threshold heuristic only. Green-colored pixels are not verified vegetation; gray pixels are not verified roads or sidewalks. The image does not establish emissions, flooding, safety, population vulnerability, project completion, or causality.")
    if source is None:
        st.info("The image summary is available, but no uploaded project dataset is active to link a ward.")
        return
    mapped = st.session_state.get("cw_working_data")
    if mapped is None or mapped["zone_id"].astype(str).str.strip().replace("<NA>", "").eq("").all():
        st.info("Map a ward/zone column in the Data Workspace to link observations to projects.")
        zones = ["(unlinked)"]
    else:
        zones = ["(unlinked)"] + sorted(mapped["zone_id"].dropna().astype(str).unique().tolist())
    with st.form("cw_confirm_street_audit"):
        category = st.selectbox("Human-entered observation", ["Shade gap visible", "Standing water visible", "Drain obstruction visible", "No issue noted", "Other / needs review"])
        zone = st.selectbox("Associate with ward/zone", zones)
        note = st.text_area("Field note", placeholder="What did you observe? Include date/context if relevant.")
        confirmed = st.checkbox("I reviewed the photo and confirm this is my observation; pixel percentages are descriptive only.")
        saved = st.form_submit_button("Save confirmed observation to this session", type="primary")
    if saved:
        if not confirmed:
            st.error("Confirm the human observation before saving it.")
        else:
            record = {"saved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "observation": category, "zone_id": zone, "note": note,
                **result, "image_sha256": sha256(photo_bytes).hexdigest(),
                "image_filename": Path(getattr(photo, "name", "camera_capture.jpg")).name,
                "status": "user-confirmed observation; independently unverified"}
            st.session_state.setdefault("cw_confirmed_audits", []).append(record)
            st.session_state.setdefault("cw_audit_images", {})[record["image_sha256"]] = photo_bytes
            st.session_state["cw_latest_audit_photo"] = photo_bytes
            st.success("Observation saved in this browser session. It does not alter optimization values unless you later apply a separately configured what-if assumption.")
    audits = st.session_state.get("cw_confirmed_audits", [])
    if audits:
        st.dataframe(pd.DataFrame(audits), use_container_width=True, hide_index=True)
        st.download_button("Download session audit log", pd.DataFrame(audits).to_csv(index=False).encode(), "carbonwise_field_audit.csv", "text/csv")


def _run_optimizer(source):
    st.markdown("### 3 · Investment Optimization")
    mapped = st.session_state.get("cw_working_data")
    if mapped is None:
        st.info("Apply a column mapping in the Data Workspace first.")
        return
    issues = validate_mapped_data(mapped)
    if not issues.empty:
        st.error("Optimization is disabled until the working dataset passes validation. Return to the Data Workspace to correct or remove flagged rows.")
        st.dataframe(issues, use_container_width=True, hide_index=True)
        return
    df = build_optimizer_frame(mapped)
    st.caption(f"Active dataset: **{st.session_state.get('cw_source_name')}** · {len(df):,} mapped candidate rows")
    max_budget = float(df["cost_cr_inr"].sum())
    confirmed = st.session_state.get("cw_confirmed_audits", [])
    usable_audits = [a for a in confirmed if a.get("zone_id") not in (None, "", "(unlinked)")]
    with st.form("cw_optimizer_form"):
        budget = st.number_input(f"Available budget ({st.session_state.get('cw_cost_unit','dataset cost units')})",
            min_value=0.01, max_value=max(max_budget, 0.01), value=max(0.01, max_budget * 0.5),
            step=max(0.01, max_budget / 20), format="%.4f")
        st.markdown("**Portfolio preference when choosing one point from the Pareto frontier**")
        c1, c2, c3 = st.columns(3)
        carbon_weight = c1.slider("Carbon preference", 0.0, 1.0, 0.40, 0.05)
        resilience_weight = c2.slider("Resilience preference", 0.0, 1.0, 0.30, 0.05)
        equity_weight = c3.slider("Equity preference", 0.0, 1.0, 0.30, 0.05)
        require_equity = st.checkbox("Require a minimum average equity score (0–100)")
        floor = st.slider("Minimum portfolio mean equity score", 0, 100, 50, 1, disabled=not require_equity)
        audits = usable_audits
        apply_audit = st.checkbox("Apply an explicit what-if resilience adjustment from a confirmed field audit",
                                  disabled=not audits,
                                  help="This is a user-entered scenario assumption. Image pixel analysis does not calculate it.")
        selected_audit = None
        adjustment = 0
        if audits:
            selected_audit = st.selectbox("Confirmed audit to use", range(len(audits)), format_func=lambda i: f"{audits[i]['observation']} · {audits[i]['zone_id']} · {audits[i]['saved_at_utc']}")
            adjustment = st.slider("User-entered resilience benefit adjustment for matching zone (%)", 0, 50, 10, 1, disabled=not apply_audit)
        submitted = st.form_submit_button("Run uploaded-data NSGA-II", type="primary")
    if not submitted:
        st.caption(f"Active dataset: {st.session_state.get('cw_source_name')} · {len(df)} candidate projects · no run occurs until you press the button.")
        return
    weights = (carbon_weight, resilience_weight, equity_weight)
    if sum(weights) <= 0:
        st.error("Set at least one objective preference above zero.")
        return
    run_df = df.copy()
    applied_audit = None
    if apply_audit and selected_audit is not None:
        applied_audit = audits[selected_audit]
        mask = run_df["zone_id"].astype(str).eq(str(applied_audit["zone_id"]))
        if not mask.any():
            st.error("The confirmed audit ward does not match any candidate project's mapped ward; no adjustment was applied.")
            return
        run_df.loc[mask, "resilience_benefit_raw"] *= (1 + adjustment / 100)
    with st.spinner("Running the existing CarbonWise NSGA-II optimizer on the active uploaded dataset…"):
        try:
            _, _, front, balanced, selected_ids, masks = _run_nsga(
                run_df, budget, weights, floor if require_equity else None)
        except Exception as exc:
            st.error(f"Optimization did not complete: {exc}")
            return
    previous = st.session_state.get("cw_latest_result")
    metrics = _portfolio_metrics(run_df, selected_ids)
    comparison_rows = []
    for label, mask in masks.items():
        ids = set(run_df.loc[mask, "project_id"].astype(str))
        row_metrics = _portfolio_metrics(run_df, ids)
        row_metrics["meets equity floor"] = ("not configured" if not require_equity else
            "yes" if row_metrics["equity_mean"] + 1e-8 >= floor else "no")
        row_metrics["within budget"] = row_metrics["cost"] <= budget + 1e-8
        comparison_rows.append({"Portfolio": label, **row_metrics})
    result = {
        "source_name": st.session_state.get("cw_source_name"),
        "source_sha256": st.session_state.get("cw_source_sha256"),
        "model_input_sha256": sha256(df.to_csv(index=False).encode()).hexdigest(),
        "source_id_column": st.session_state["cw_mapping"]["project_id"],
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "budget": budget, "cost_unit": st.session_state.get("cw_cost_unit", "dataset cost units"),
        "priorities": dict(zip(["carbon", "resilience", "equity"], weights)),
        "equity_floor": floor if require_equity else None,
        "selected_ids": selected_ids, "metrics": metrics, "front": front,
        "balanced": balanced.to_dict(), "masks": masks, "comparison": pd.DataFrame(comparison_rows),
        "engine_df": run_df, "working_df": df, "source_frame": st.session_state["cw_source_frame"],
        "applied_audit": applied_audit, "audit_adjustment_pct": adjustment if apply_audit else 0,
        "audit_log": st.session_state.get("cw_confirmed_audits", []),
    }
    st.session_state["cw_previous_result"] = previous
    st.session_state["cw_latest_result"] = result
    st.success(f"NSGA-II completed: {metrics['projects']} projects selected within the {budget:,.4f} {result['cost_unit']} budget.")
    st.caption(f"Pareto frontier: {len(front)} feasible non-dominated portfolios · 96 population × 100 generations · seed 7. Objective values retain the mapped benefit units. Equity is normalized 0–100 within this dataset.")
    st.dataframe(result["comparison"].round(3), use_container_width=True, hide_index=True)

    fig = px.scatter(front, x="carbon_score", y="resilience_score", color="equity_score",
        size="n_projects", hover_data=["total_cost_cr", "selected_projects"],
        labels={"carbon_score":"Annual carbon benefit sum (input units)",
                "resilience_score":"Resilience benefit sum (input units)",
                "equity_score":"Equity score sum (normalized)", "total_cost_cr":f"Cost ({result['cost_unit']})"},
        title="Feasible Pareto frontier · uploaded dataset")
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("#### Selected projects")
    selected = result["engine_df"][result["engine_df"]["project_id"].astype(str).isin(selected_ids)].copy()
    selected["selection"] = "Selected"
    st.dataframe(_present_mapped_frame(selected, result["cost_unit"]), use_container_width=True, hide_index=True)
    excluded = result["engine_df"][~result["engine_df"]["project_id"].astype(str).isin(selected_ids)].copy()
    excluded["selection"] = "Excluded by chosen portfolio"
    with st.expander(f"Excluded projects ({len(excluded)})"):
        st.dataframe(_present_mapped_frame(excluded, result["cost_unit"]), use_container_width=True, hide_index=True)
    original_selected = _source_rows_at_positions(result["source_frame"], selected["_source_row"])
    st.download_button("Download selected projects (mapped/corrected values)",
        _present_mapped_frame(selected, result["cost_unit"]).to_csv(index=False).encode(),
        "carbonwise_selected_projects_mapped.csv", "text/csv")
    st.download_button("Download original source rows (unchanged)",
        original_selected.to_csv(index=False).encode(), "carbonwise_selected_projects.csv", "text/csv")
    st.download_button("Download Pareto frontier", front.to_csv(index=False).encode(), "carbonwise_pareto_front.csv", "text/csv")
    packet = _make_export_packet(result["source_frame"], result)
    st.download_button("Download complete run packet (.zip)", packet, "carbonwise_optimization_run.zip", "application/zip")


def _digital_twin():
    st.markdown("### 4 · What-If Digital Twin")
    st.write("This is a counterfactual decision simulator over the active uploaded table. It is not a sensor-connected or physical simulation of Chennai.")
    current = st.session_state.get("cw_latest_result")
    previous = st.session_state.get("cw_previous_result")
    if current is None:
        st.info("Run the uploaded-data optimizer first. Change budget, equity floor, objective preferences, or a confirmed-audit assumption, then run again to create a before/after comparison.")
        return
    if previous is None:
        st.info("This is the first run in this session. Change one or more settings in Investment Optimization and run again; the next result will be compared with this one.")
        return
    if current["model_input_sha256"] != previous["model_input_sha256"]:
        st.warning("The mapped project values changed between runs. This compares different input data as well as settings; interpret differences as a data-and-scenario comparison, not an isolated budget effect.")
        before_df = previous["working_df"].set_index("project_id")
        after_df = current["working_df"].set_index("project_id")
        common = before_df.index.intersection(after_df.index)
        changed_rows = []
        fields = ["cost_cr_inr", "carbon_reduction_tco2_per_year", "resilience_benefit_raw", "equity_raw", "category", "zone_id"]
        for project_id in common:
            for field in fields:
                if field in before_df and field in after_df:
                    old, new = before_df.at[project_id, field], after_df.at[project_id, field]
                    if not (pd.isna(old) and pd.isna(new)) and str(old) != str(new):
                        changed_rows.append({"project_id": project_id, "field": field, "before": old, "after": new})
        st.markdown("**Mapped row changes detected**")
        st.dataframe(pd.DataFrame(changed_rows) if changed_rows else pd.DataFrame(columns=["project_id", "field", "before", "after"]), use_container_width=True, hide_index=True)
    else:
        st.caption("Mapped project values are unchanged between runs; differences below come from the displayed scenario settings and optimizer selection.")
    before = previous["metrics"]
    after = current["metrics"]
    added = current["selected_ids"] - previous["selected_ids"]
    removed = previous["selected_ids"] - current["selected_ids"]
    st.markdown(f"**Before:** budget {previous['budget']:,.3f} {previous['cost_unit']} · **After:** {current['budget']:,.3f} {current['cost_unit']}")
    st.markdown(f"**Projects added:** {', '.join(sorted(added)) if added else 'None'}  \n**Projects removed:** {', '.join(sorted(removed)) if removed else 'None'}")
    cols = st.columns(4)
    for col, label, key, fmt in [(cols[0], "Carbon benefit", "carbon", ".2f"),
                                 (cols[1], "Resilience benefit", "resilience", ".2f"),
                                 (cols[2], "Equity mean (0–100)", "equity_mean", ".1f"),
                                 (cols[3], f"Cost ({current['cost_unit']})", "cost", ".2f")]:
        delta = after[key] - before[key]
        col.metric(label, f"{after[key]:{fmt}}", f"{delta:+.{1 if key == 'equity_mean' else 2}f} vs prior run")
    current_frame = current["engine_df"]
    before_frame = previous["engine_df"]
    current_selected = current_frame[current_frame["project_id"].astype(str).isin(current["selected_ids"])]
    prior_selected = before_frame[before_frame["project_id"].astype(str).isin(previous["selected_ids"])]
    slices = []
    for label, group_col in [("Category", "category"), ("Ward / zone", "zone_id")]:
        for frame, run_label in [(prior_selected, "Before"), (current_selected, "After")]:
            if group_col not in frame:
                continue
            part = frame.groupby(group_col, dropna=False)["cost_cr_inr"].sum().reset_index()
            part.columns = ["group", "cost"]
            part["dimension"], part["run"] = label, run_label
            slices.append(part)
    if slices:
        chart_data = pd.concat(slices, ignore_index=True)
        chart_data["cost_unit"] = current["cost_unit"]
        st.markdown("#### Allocation changes by category and ward/zone")
        fig = px.bar(chart_data, x="group", y="cost", color="run", barmode="group", facet_row="dimension",
                     labels={"group":"Category or zone", "cost":f"Cost ({current['cost_unit']})"})
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("#### What changed in the settings?")
    changes = []
    if current["budget"] != previous["budget"]:
        changes.append(f"Budget: {previous['budget']:,.3f} → {current['budget']:,.3f} {current['cost_unit']}")
    for key, label in [("carbon", "Carbon preference"), ("resilience", "Resilience preference"), ("equity", "Equity preference")]:
        if current["priorities"][key] != previous["priorities"][key]:
            changes.append(f"{label}: {previous['priorities'][key]:.0%} → {current['priorities'][key]:.0%}")
    if current["equity_floor"] != previous["equity_floor"]:
        changes.append(f"Minimum mean equity: {previous['equity_floor']} → {current['equity_floor']}")
    if current["audit_adjustment_pct"] != previous["audit_adjustment_pct"]:
        changes.append(f"Confirmed-audit resilience assumption: {previous['audit_adjustment_pct']}% → {current['audit_adjustment_pct']}%")
    st.markdown("**Changed inputs:** " + ("; ".join(changes) if changes else "No configured setting changed; stochastic search seed is held constant."))
    st.json({"before": {"budget": previous["budget"], "priorities": previous["priorities"], "equity_floor": previous["equity_floor"], "audit_adjustment_pct": previous["audit_adjustment_pct"]},
             "after": {"budget": current["budget"], "priorities": current["priorities"], "equity_floor": current["equity_floor"], "audit_adjustment_pct": current["audit_adjustment_pct"]}})
    if current.get("applied_audit"):
        st.caption(f"Current run applied an explicit +{current['audit_adjustment_pct']}% resilience assumption to projects mapped to ward {current['applied_audit']['zone_id']}. This is a user-authored scenario assumption, not a computer-vision measurement.")


def _evidence_explorer(source):
    st.markdown("### 5 · Evidence Explorer and Results")
    st.write("Inspect the active upload and all session-confirmed field audit notes. Official source registers remain in the separate Evidence Room.")
    if source is not None:
        st.success(f"Active input: {st.session_state.get('cw_source_name')} · hash `{st.session_state.get('cw_source_sha256','')}`")
        st.dataframe(source, use_container_width=True, hide_index=True)
        st.download_button("Download original active dataset", source.to_csv(index=False).encode(), "carbonwise_active_input.csv", "text/csv")
    else:
        st.info("No user dataset loaded. Select Evidence Room for the source-backed GCC and CMRL registers.")
    audits = st.session_state.get("cw_confirmed_audits", [])
    if audits:
        st.markdown("#### User-confirmed visual street audit records")
        st.dataframe(pd.DataFrame(audits), use_container_width=True, hide_index=True)
        st.download_button("Download visual audit packet with photos (.zip)", _make_audit_packet(audits), "carbonwise_visual_audit.zip", "application/zip")
    latest = st.session_state.get("cw_latest_result")
    if latest:
        st.markdown("#### Latest optimizer run")
        st.json({"run_at_utc": latest["run_at_utc"], "dataset": latest["source_name"], "budget": latest["budget"], "cost_unit": latest["cost_unit"], "metrics": latest["metrics"], "selected_project_ids": sorted(latest["selected_ids"])})
        st.download_button("Download latest result packet (.zip)", _make_export_packet(latest["source_frame"], latest), "carbonwise_latest_run.zip", "application/zip")


def render():
    st.title("CarbonWise · Decision Studio")
    st.caption("Upload your project records, inspect and map the data, then run multi-objective NSGA-II on those exact rows.")
    st.info("The evidence room remains the source-backed GCC/CMRL workspace. This studio optimizes only the dataset named below. Synthetic sample values are labeled and never substituted silently.")
    tabs = st.tabs(["Data Workspace", "Visual Street Audit", "Investment Optimization", "What-If Digital Twin", "Evidence Explorer & Results"])
    with tabs[0]:
        _data_workspace(st.session_state.get("cw_source_frame"))
    source = st.session_state.get("cw_source_frame")
    with tabs[1]:
        _visual_audit(source)
    with tabs[2]:
        _run_optimizer(source)
    with tabs[3]:
        _digital_twin()
    with tabs[4]:
        _evidence_explorer(source)
