from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from baselines import equity_aware_greedy_allocation
from equity_auditor import distributive_investment_metrics


class EquityMetricTests(unittest.TestCase):
    def setUp(self):
        self.zones = pd.DataFrame({
            "zone_id": ["Z1", "Z2"],
            "approx_population_2023": [100, 100],
            "vulnerability_index": [0.8, 0.2],
        })
        self.projects = pd.DataFrame({
            "project_id": ["P1", "P2"],
            "zone_id": ["Z1", "Z2"],
            "cost_cr_inr": [1.0, 1.0],
            "carbon_score_raw": [50.0, 100.0],
            "equity_score": [100.0, 10.0],
        })

    def test_metrics_include_zero_investment_zone(self):
        result = distributive_investment_metrics(self.projects, self.zones, ["P1"])
        self.assertAlmostEqual(result["gini_investment_per_resident"], 0.5)
        self.assertAlmostEqual(result["theil_t_investment_per_resident"], 0.69314718056)
        self.assertAlmostEqual(result["atkinson_investment_per_resident"], 0.5)
        self.assertEqual(result["high_vulnerability_investment_share_pct"], 100.0)

    def test_empty_portfolio_has_zero_inequality(self):
        result = distributive_investment_metrics(self.projects, self.zones, [])
        self.assertEqual(result["gini_investment_per_resident"], 0.0)
        self.assertEqual(result["theil_t_investment_per_resident"], 0.0)
        self.assertEqual(result["atkinson_investment_per_resident"], 0.0)

    def test_equity_greedy_respects_budget_and_input_weights(self):
        mask = equity_aware_greedy_allocation(self.projects, 1.0)
        self.assertEqual(int(mask.sum()), 1)
        self.assertEqual(self.projects.loc[mask, "project_id"].tolist(), ["P1"])
        with self.assertRaises(ValueError):
            equity_aware_greedy_allocation(self.projects, 1.0, 0, 0)


if __name__ == "__main__":
    unittest.main()
