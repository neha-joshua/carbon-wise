import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import preprocessing
from data_validation import validate


class PreprocessingValidationTests(unittest.TestCase):
    def test_preprocess_preserves_missing_numeric_inputs(self):
        projects = pd.DataFrame({
            "project_id": ["P1", "P2"],
            "project_name": ["One", "Two"],
            "category": ["Drainage", "Drainage"],
            "zone_id": ["Z1", "Z1"],
            "cost_lakhs_inr": [100.0, 200.0],
            "carbon_reduction_tco2_per_year": [10.0, np.nan],
            "resilience_benefit_raw": [5.0, 8.0],
            "population_benefited": [10, 20],
        })
        zones = pd.DataFrame({
            "zone_id": ["Z1"],
            "vulnerability_index": [0.5],
            "infrastructure_deprivation_index": [0.5],
            "approx_population_2023": [100],
        })
        with patch.object(preprocessing, "load_raw", return_value=(projects, zones)), \
             patch.object(preprocessing.os, "makedirs"), \
             patch.object(pd.DataFrame, "to_csv"):
            result = preprocessing.preprocess()
        self.assertTrue(pd.isna(result.loc[1, "carbon_reduction_tco2_per_year"]))
        self.assertTrue(pd.isna(result.loc[1, "carbon_score_raw"]))

    def test_validation_blocks_missing_and_nonfinite_model_values(self):
        frame = pd.DataFrame({
            "project_id": ["P1", "P2"], "category": ["A", "A"],
            "zone_id": ["Z1", "Z1"], "cost_cr_inr": [1.0, 2.0],
            "carbon_reduction_tco2_per_year": [1.0, np.nan],
            "resilience_benefit_raw": [1.0, np.inf],
            "population_benefited": [10, 20],
        })
        zones = pd.DataFrame({
            "zone_id": ["Z1"], "approx_population_2023": [100],
            "vulnerability_index": [0.5],
        })
        result = validate(frame, zones)
        self.assertEqual(result["status"], "ISSUES FOUND")
        self.assertTrue(any("missing values" in issue for issue in result["issues"]))
        self.assertTrue(any("infinite values" in issue for issue in result["issues"]))

    def test_validation_rejects_zero_cost(self):
        frame = pd.DataFrame({
            "project_id": ["P1"], "category": ["A"], "zone_id": ["Z1"],
            "cost_cr_inr": [0.0], "carbon_reduction_tco2_per_year": [1.0],
            "resilience_benefit_raw": [1.0], "population_benefited": [10],
        })
        zones = pd.DataFrame({
            "zone_id": ["Z1"], "approx_population_2023": [100],
            "vulnerability_index": [0.5],
        })
        result = validate(frame, zones)
        self.assertTrue(any("zero or negative cost" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
