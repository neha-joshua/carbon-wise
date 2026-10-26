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
from PIL import UnidentifiedImageError

from user_data_workflow import (
    REQUIRED_FIELDS, analyze_image_pixels, build_optimizer_frame,
    default_column_mapping, load_uploaded_table, map_to_carbonwise,
    validate_mapped_data,
)
from baselines import equal_split_allocation, greedy_cost_effectiveness_allocation
from optimizer import run_nsga2, pareto_front_to_df, pick_balanced_solution
from street_view_insights import formatted_pixel_count, plain_language_reading, valid_percentage


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
        "CarbonWise plan": df["project_id"].astype(str).isin(selected_ids),
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
    st.markdown("### Upload your project file")
    st.write("Use one project per row. Match the columns, review the values, then compare plans.")
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
    if source is not None and st.button("Clear active dataset", key="cw_clear_data"):
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
        st.info("Upload project data or load the practice example to begin. CarbonWise will not compare plans until you map the required fields and start a run.")
        return

    name = st.session_state.get("cw_source_name", "User upload")
    if name.startswith("SYNTHETIC DEMO"):
        st.info("Practice data: every project row and impact value is invented for interface demonstration. Do not present it as Chennai project evidence.")
    else:
        st.success(f"Active dataset: **{name}** · {len(source):,} rows")

    st.markdown("#### Quick file check")
    p1, p2, p3 = st.columns(3)
    p1.metric("Rows × columns", f"{source.shape[0]:,} × {source.shape[1]:,}")
    p2.metric("Duplicate full rows", f"{int(source.duplicated().sum()):,}")
    p3.metric("Cells missing", f"{int(source.isna().sum().sum()):,}")
    profile = pd.DataFrame({"column": source.columns.astype(str), "data type": source.dtypes.astype(str).values,
                            "missing": source.isna().sum().values,
                            "distinct": source.nunique(dropna=True).values})
    with st.expander("Inspect columns and first rows"):
        st.dataframe(profile, hide_index=True, use_container_width=True)
        st.dataframe(source.head(12), hide_index=True, use_container_width=True)

    columns = list(source.columns)
    choices = ["(not mapped)"] + columns
    guesses = default_column_mapping(columns)
    with st.expander("Match file columns to planning fields", expanded=st.session_state.get("cw_working_data") is None):
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
            applied = st.form_submit_button("Use these columns", type="primary")
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
    st.markdown("#### Review and correct the working data")
    st.caption("Edit the planning fields or remove rows you do not want to include. The original uploaded rows remain available in exports.")
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
    st.caption("The community score is scaled from 0–100 within this dataset for comparison; it is not an absolute impact measure. Original values are retained, and missing values are never filled in automatically.")


def _visual_audit(source):
    st.markdown("### Add a street photo (optional)")
    st.write("Upload a photo or take one. CarbonWise estimates colour coverage; it does not identify objects or verify project outcomes.")
    photo_source = st.radio("Choose photo source", ["Upload a photo", "Use camera"], horizontal=True, key="cw_photo_source")
    if photo_source == "Use camera":
        photo = st.camera_input("Take a street photo", key="cw_camera_capture")
    else:
        photo = st.file_uploader("Choose a PNG or JPEG photo", type=["png", "jpg", "jpeg"], key="cw_audit_photo")
    if photo is None:
        if photo_source == "Use camera":
            st.info("Allow camera access and capture a photo to continue. You can switch to **Upload a photo** if camera access is unavailable.")
        else:
            st.info("Choose a PNG or JPEG photo above. The photo will be analyzed after you add it.")
        st.caption("Camera access depends on your browser permissions. On a public deployment, the secure site URL supports browser camera access; photo upload remains available.")
        return
    photo_bytes = photo.getvalue()
    try:
        image, result = analyze_image_pixels(photo_bytes)
    except UnidentifiedImageError:
        st.error("This file could not be read as an image. Choose a valid PNG or JPEG photo and try again.")
        st.caption("The uploaded file remains selected. Choose a valid image or replace it to continue.")
        return
    except ValueError as exc:
        st.error(f"This photo could not be analyzed: {exc}")
        st.caption("The uploaded file remains selected. Choose a valid image or replace it to continue.")
        return
    except Exception:
        st.error("Photo analysis did not complete. Try a different PNG or JPEG image.")
        st.caption("The uploaded file remains selected. Choose a valid image or replace it to continue.")
        return

    st.success("Photo uploaded and analyzed")
    image_col, result_col = st.columns([1.05, 1], gap="large")
    with image_col:
        st.image(image, caption="Your uploaded street photo", use_container_width=True)
    with result_col:
        st.markdown("#### Color snapshot")
        green = valid_percentage(result, "green_hued_pixel_share_pct")
        gray = valid_percentage(result, "low_saturation_gray_pixel_share_pct")
        pixels = formatted_pixel_count(result)
        cards = st.columns(2)
        with cards[0]:
            st.metric("Green-coloured areas", f"{green:.1f}%" if green is not None else "Unavailable")
            st.caption("Areas that may contain greenery")
        with cards[1]:
            st.metric("Grey-coloured areas", f"{gray:.1f}%" if gray is not None else "Unavailable")
            st.caption("Possible roads, paths, buildings, or other surfaces")
        st.metric("Image coverage analysed", pixels or "Unavailable")
        st.caption("Pixels scanned to estimate the share of selected colours")

    st.markdown("#### What does this tell us?")
    st.write(plain_language_reading(result))

    with st.expander("About this estimate"):
        st.write("These results are estimates based on image colours. Green-coloured areas may include objects other than plants, while grey-coloured areas may include surfaces other than roads or paths. The image alone cannot establish emissions, flood risk, safety, community vulnerability, or whether a project has been completed.")
    with st.expander("How was this calculated?"):
        st.markdown("""
        CarbonWise converts the image to **HSV (hue, saturation, value)** colour space, then applies two fixed colour rules:

        - **Green-hued:** Pillow hue channel 30–100 on its 0–255 scale (not degrees), saturation at least 50, and brightness/value at least 30.
        - **Low-saturation gray:** saturation at most 45 and brightness/value from 35 to 205.
        - **Percentage denominator:** all pixels in the resized image preview. The image is converted to RGB and scaled down, preserving its aspect ratio, so its longest side is no more than 512 pixels. The scan does not crop the image.
        - **Overlap:** the two current rules cannot overlap because their saturation ranges are separate.

        Shadows, lighting, camera settings, compression, blur, and image quality can change the colour values and therefore the estimates. This is a simple colour-based estimate, not object recognition or a validated environmental measurement.
        """)

    st.markdown("#### Connect this image to a project area")
    st.write("Link this image to a ward or project area to view it alongside the planning data available in CarbonWise.")
    mapped = st.session_state.get("cw_working_data")
    if source is None:
        st.info("No project dataset is active, so there are no project areas to select. Load your data in **Data Workspace**, map its ward/zone column, then return here.")
        zones = []
    elif mapped is None:
        st.info("Your data is uploaded but its columns are not mapped yet. Map a ward/zone column in **Data Workspace** to see the available project areas here.")
        zones = []
    elif "zone_id" not in mapped:
        st.info("The mapped dataset has no ward/zone field. Reopen **Data Workspace** and map a location column, if one is available in your source file.")
        zones = []
    else:
        zones = sorted({str(value).strip() for value in mapped["zone_id"].dropna() if str(value).strip() and str(value).strip().lower() != "<na>"})
        if not zones:
            st.info("No project areas are available in the mapped data. Map a populated ward/zone column in **Data Workspace**. This image will remain unlinked.")

    with st.form("cw_confirm_street_audit"):
        category = st.selectbox("Your observation", ["Shade gap visible", "Standing water visible", "Drain obstruction visible", "No issue noted", "Other / needs review"])
        zone = st.selectbox("Project area (optional)", ["Keep unlinked"] + zones, help="Choose an area explicitly. CarbonWise does not infer a location from the image.")
        note = st.text_area("Field note", placeholder="What did you observe? Add date or context if useful.")
        confirmed = st.checkbox("I reviewed the photo and confirm this observation is mine. The colour estimates are descriptive only.")
        saved = st.form_submit_button("Save observation to this session", type="primary")
    if saved:
        if not confirmed:
            st.error("Confirm the human observation before saving it.")
        else:
            selected_zone = zone if zone != "Keep unlinked" else "(unlinked)"
            record = {"saved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "observation": category, "zone_id": selected_zone, "note": note,
                **result, "image_sha256": sha256(photo_bytes).hexdigest(),
                "image_filename": Path(getattr(photo, "name", "camera_capture.jpg")).name,
                "image_status": "uploaded and analyzed",
                "link_status": "manually linked" if selected_zone != "(unlinked)" else "not linked",
                "status": "user-confirmed observation; independently unverified"}
            st.session_state.setdefault("cw_confirmed_audits", []).append(record)
            st.session_state.setdefault("cw_audit_images", {})[record["image_sha256"]] = photo_bytes
            st.session_state["cw_latest_audit_photo"] = photo_bytes
            if selected_zone != "(unlinked)":
                st.success(f"Observation saved and linked to project area {selected_zone} in this browser session.")
            else:
                st.success("Observation saved without a project-area link. You can associate it manually once a mapped area is available.")
            st.caption("Saving the image note does not change project data or investment results.")
    else:
        st.caption("Status: photo uploaded and analyzed · project-area link will be recorded only if you select one and save.")
    audits = st.session_state.get("cw_confirmed_audits", [])
    if audits:
        with st.expander(f"Saved observations in this session ({len(audits)})"):
            st.dataframe(pd.DataFrame(audits), use_container_width=True, hide_index=True)
            st.download_button("Download session audit log", pd.DataFrame(audits).to_csv(index=False).encode(), "carbonwise_field_audit.csv", "text/csv")


def _run_optimizer(source):
    st.markdown("### Compare investment plans")
    mapped = st.session_state.get("cw_working_data")
    if mapped is None:
        st.info("Prepare your file in **Upload and prepare data** first.")
        return
    issues = validate_mapped_data(mapped)
    if not issues.empty:
        st.error("Plan comparison is paused until the working data passes its checks. Return to **Upload and prepare data** to correct or remove flagged rows.")
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
        st.markdown("**Choose what matters most**")
        st.caption("These settings rank the plans your data supports. They do not change the values in your file.")
        c1, c2, c3 = st.columns(3)
        carbon_weight = c1.slider("Carbon benefit", 0.0, 1.0, 0.40, 0.05)
        resilience_weight = c2.slider("Resilience benefit", 0.0, 1.0, 0.30, 0.05)
        equity_weight = c3.slider("Community score", 0.0, 1.0, 0.30, 0.05)
        audits = usable_audits
        with st.expander("Optional constraints and field-audit scenario"):
            require_equity = st.checkbox("Set a minimum average community score")
            floor = st.slider("Minimum score (0–100 within this dataset)", 0, 100, 50, 1, disabled=not require_equity)
            apply_audit = st.checkbox("Apply a user-entered resilience adjustment from a confirmed field note",
                                      disabled=not audits,
                                      help="This scenario value is entered by you; image colours do not calculate it.")
            selected_audit = None
            adjustment = 0
            if audits:
                selected_audit = st.selectbox("Field note", range(len(audits)), format_func=lambda i: f"{audits[i]['observation']} · {audits[i]['zone_id']} · {audits[i]['saved_at_utc']}")
                adjustment = st.slider("Resilience adjustment for matching area (%)", 0, 50, 10, 1, disabled=not apply_audit)
        submitted = st.form_submit_button("Generate investment plan", type="primary")
    if not submitted:
        st.caption(f"Active dataset: {st.session_state.get('cw_source_name')} · {len(df)} project rows · no plan is generated until you select the button.")
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
    with st.spinner("Comparing feasible plans from the active dataset…"):
        try:
            _, _, front, balanced, selected_ids, masks = _run_nsga(
                run_df, budget, weights, floor if require_equity else None)
        except Exception as exc:
            st.error(f"CarbonWise could not generate a plan: {exc}")
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
    st.success(f"Plan generated: {metrics['projects']} projects fit within the {budget:,.4f} {result['cost_unit']} budget.")
    st.caption("Benefits in this result come from the values and units in your file. The community score is scaled within the active dataset.")
    comparison_display = result["comparison"].rename(columns={
        "projects": "Projects selected", "cost": f"Total cost ({result['cost_unit']})",
        "carbon": "Carbon benefit (input units)", "resilience": "Resilience benefit (input units)",
        "equity_mean": "Average community score (0–100)", "equity_total": "Community score total",
        "meets equity floor": "Meets score minimum", "within budget": "Within budget",
    })
    st.dataframe(comparison_display.round(3), use_container_width=True, hide_index=True)
    st.markdown("#### What this plan means")
    st.write(f"The selected plan includes **{metrics['projects']} projects** at a total cost of **{metrics['cost']:,.3f} {result['cost_unit']}**. Its projected benefits are sums of the mapped values in your file; they are estimates supplied by you, not measured outcomes.")

    fig = px.scatter(front, x="carbon_score", y="resilience_score", color="equity_score",
        size="n_projects", hover_data=["total_cost_cr", "selected_projects"],
        labels={"carbon_score":"Annual carbon benefit sum (input units)",
                "resilience_score":"Resilience benefit sum (input units)",
                "equity_score":"Community score total (dataset-relative)", "total_cost_cr":f"Cost ({result['cost_unit']})"},
        title="Feasible plans with different benefit trade-offs")
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("How the plans were generated"):
        floor_text = f" and minimum average community score of {floor}" if require_equity else ""
        st.write(f"CarbonWise used the existing NSGA-II search on {len(df):,} validated rows, with a population of 96, 100 generations, and a fixed seed of 7. It filtered plans against your budget{floor_text}. The plotted points are feasible model alternatives, not forecasts or verified impacts.")
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
    st.download_button("Download alternative plans table", front.to_csv(index=False).encode(), "carbonwise_alternative_plans.csv", "text/csv")
    packet = _make_export_packet(result["source_frame"], result)
    st.download_button("Download complete run packet (.zip)", packet, "carbonwise_optimization_run.zip", "application/zip")


def _digital_twin():
    st.markdown("### Compare two runs")
    st.write("See how the selected plan changes when you change the budget, priorities, or an explicit scenario assumption. This is not a live city model.")
    current = st.session_state.get("cw_latest_result")
    previous = st.session_state.get("cw_previous_result")
    if current is None:
        st.info("Generate an investment plan first. Then change a budget, priority, or confirmed-audit assumption and generate another plan to see the comparison.")
        return
    if previous is None:
        st.info("This is the first plan in this session. Change a setting under **Compare investment plans** and generate another plan to compare it with this one.")
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
        st.markdown("#### How proposed costs shift by project type and area")
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
    st.markdown("### Review and download")
    st.write("Your upload and saved notes stay in this browser session. Download any run files you need to keep.")
    if source is not None:
        st.success(f"Active input: {st.session_state.get('cw_source_name')}")
        st.dataframe(source, use_container_width=True, hide_index=True)
        st.download_button("Download original active dataset", source.to_csv(index=False).encode(), "carbonwise_active_input.csv", "text/csv")
    else:
        st.info("No user dataset loaded. Select Evidence Room for the source-backed GCC and CMRL registers.")
    audits = st.session_state.get("cw_confirmed_audits", [])
    if audits:
        st.markdown("#### Your saved Street View observations")
        st.dataframe(pd.DataFrame(audits), use_container_width=True, hide_index=True)
        st.download_button("Download visual audit packet with photos (.zip)", _make_audit_packet(audits), "carbonwise_visual_audit.zip", "application/zip")
    latest = st.session_state.get("cw_latest_result")
    if latest:
        st.markdown("#### Latest optimizer run")
        st.json({"run_at_utc": latest["run_at_utc"], "dataset": latest["source_name"], "budget": latest["budget"], "cost_unit": latest["cost_unit"], "metrics": latest["metrics"], "selected_project_ids": sorted(latest["selected_ids"])})
        st.download_button("Download latest result packet (.zip)", _make_export_packet(latest["source_frame"], latest), "carbonwise_latest_run.zip", "application/zip")


def render():
    st.title("Analyze your project data")
    st.caption("Upload a file to compare possible project plans. Results use the values you provide and are not measured outcomes.")
    st.info("Start with **Upload data**, map and review the required fields, then choose **Compare plans**. The sample file contains invented values. For published city records, choose **Explore official evidence** in the sidebar.")
    tabs = st.tabs(["Upload data", "Street photo", "Compare plans", "Compare runs", "Downloads"])
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
