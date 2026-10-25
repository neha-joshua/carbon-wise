import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from verify_gcc_calculations import calculation_checks


class GCCCalculationTests(unittest.TestCase):
    def test_published_arithmetic_is_reproduced(self):
        checks = {row["project_id"]: row for row in calculation_checks()}
        self.assertEqual(set(checks), {"R02", "R13", "R16", "R17", "R18"})
        for row in checks.values():
            self.assertAlmostEqual(float(row["recomputed_value"]), float(row["reported_value"]), places=4)
            self.assertIn("not validated", row["status"])

    def test_vehicle_estimates_are_not_observed_outcomes(self):
        checks = calculation_checks()
        for row in checks:
            self.assertIn("potential, modelled", row["unit"])


if __name__ == "__main__":
    unittest.main()
