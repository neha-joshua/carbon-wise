from io import BytesIO
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd
from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from user_data_workflow import load_uploaded_table, map_to_carbonwise, validate_mapped_data, build_optimizer_frame, analyze_image_pixels
from optimizer import run_nsga2, pareto_front_to_df, pick_balanced_solution


class UserDataWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.source = pd.DataFrame({
            "code": ["P1", "P2", "P3", "P4"],
            "title": ["A", "B", "C", "D"],
            "programme": ["Road", "Drain", "Green", "Drain"],
            "ward": ["Z1", "Z2", "Z1", "Z2"],
            "budget_crore": [4.0, 4.0, 3.0, 2.0],
            "co2_tonnes": [100.0, 20.0, 60.0, 10.0],
            "resilience": [20.0, 100.0, 60.0, 10.0],
            "equity": [20.0, 100.0, 80.0, 10.0],
        })
        self.mapping = {"project_id":"code", "project_name":"title", "category":"programme",
            "zone_id":"ward", "cost_cr_inr":"budget_crore",
            "carbon_reduction_tco2_per_year":"co2_tonnes", "resilience_benefit_raw":"resilience",
            "equity_raw":"equity"}

    def test_csv_and_excel_upload_readers(self):
        csv_bytes = self.source.to_csv(index=False).encode()
        self.assertEqual(load_uploaded_table("projects.csv", csv_bytes).shape, self.source.shape)
        excel = BytesIO()
        self.source.to_excel(excel, index=False, engine="openpyxl")
        self.assertEqual(load_uploaded_table("projects.xlsx", excel.getvalue()).shape, self.source.shape)

    def test_mapping_and_validation_flag_bad_cost_without_imputation(self):
        mapped = map_to_carbonwise(self.source, self.mapping)
        self.assertTrue(validate_mapped_data(mapped).empty)
        bad = self.source.copy()
        bad["budget_crore"] = bad["budget_crore"].astype(object)
        bad.loc[1, "budget_crore"] = "unknown"
        mapped_bad = map_to_carbonwise(bad, self.mapping)
        issues = validate_mapped_data(mapped_bad)
        self.assertIn("missing_or_invalid_cost_cr_inr", set(issues["issue"]))

    def test_duplicate_id_blocks_optimizer(self):
        source = self.source.copy()
        source.loc[1, "code"] = "P1"
        mapped = map_to_carbonwise(source, self.mapping)
        self.assertEqual(int((validate_mapped_data(mapped)["issue"] == "duplicate_project_id").sum()), 2)

    def test_real_nsga2_run_respects_budget_and_equity_floor(self):
        mapped = map_to_carbonwise(self.source, self.mapping)
        frame = build_optimizer_frame(mapped)
        result, problem = run_nsga2(frame, 6.0, pop_size=48, n_gen=40, seed=4, equity_floor=70.0,
            carbon_col="carbon_reduction_tco2_per_year", resilience_col="resilience_benefit_raw",
            equity_col="equity_score", cost_col="cost_cr_inr")
        front = pareto_front_to_df(result, problem, frame)
        self.assertFalse(front.empty)
        self.assertTrue((front["total_cost_cr"] <= 6.0 + 1e-8).all())
        for ids in front["selected_projects"]:
            chosen = frame[frame["project_id"].isin(ids.split(";"))]
            self.assertGreaterEqual(chosen["equity_score"].mean() + 1e-8, 70.0)
        chosen = pick_balanced_solution(front, (0.3, 0.3, 0.4))["selected_projects"].split(";")
        self.assertLessEqual(frame[frame["project_id"].isin(chosen)]["cost_cr_inr"].sum(), 6.0 + 1e-8)

    def test_infeasible_equity_floor_returns_no_feasible_portfolio(self):
        mapped = map_to_carbonwise(self.source, self.mapping)
        frame = build_optimizer_frame(mapped)
        result, problem = run_nsga2(frame, 2.0, pop_size=40, n_gen=30, seed=9, equity_floor=100.0,
            carbon_col="carbon_reduction_tco2_per_year", resilience_col="resilience_benefit_raw",
            equity_col="equity_score", cost_col="cost_cr_inr")
        self.assertTrue(pareto_front_to_df(result, problem, frame).empty)

    def test_pixel_analysis_is_a_color_share_not_object_recognition(self):
        green_png = BytesIO()
        Image.new("RGB", (8, 8), (0, 255, 0)).save(green_png, format="PNG")
        _, result = analyze_image_pixels(green_png.getvalue())
        self.assertEqual(result["green_hued_pixel_share_pct"], 100.0)
        self.assertIn("not semantic segmentation", result["method"])

    def test_pixel_results_follow_the_current_image_bytes(self):
        green_png, red_png = BytesIO(), BytesIO()
        Image.new("RGB", (8, 8), (0, 255, 0)).save(green_png, format="PNG")
        Image.new("RGB", (8, 8), (255, 0, 0)).save(red_png, format="PNG")
        _, green_result = analyze_image_pixels(green_png.getvalue())
        _, red_result = analyze_image_pixels(red_png.getvalue())
        self.assertEqual(green_result["green_hued_pixel_share_pct"], 100.0)
        self.assertEqual(red_result["green_hued_pixel_share_pct"], 0.0)

    def test_invalid_image_bytes_raise_a_readable_pipeline_error(self):
        with self.assertRaises(UnidentifiedImageError):
            analyze_image_pixels(b"not an image")


if __name__ == "__main__":
    unittest.main()
