import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import data_pipeline


class DataPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = data_pipeline.run()

    def test_source_row_count_and_empty_model_ready(self):
        self.assertEqual(self.summary["source_row_count"], 23)
        self.assertEqual(self.summary["model_ready_row_count"], 0)
        with (data_pipeline.DERIVED / "model_ready_records.csv").open(newline="", encoding="utf-8") as f:
            self.assertEqual(list(csv.DictReader(f)), [])

    def test_programmes_and_high_risk_records_flagged(self):
        with (data_pipeline.DERIVED / "validation_issues.csv").open(newline="", encoding="utf-8") as f:
            issues = list(csv.DictReader(f))
        pairs = {(row["record_id"], row["code"]) for row in issues}
        self.assertIn(("R04", "programme_not_package"), pairs)
        self.assertIn(("R04", "programme_cost_not_package_cost"), pairs)
        self.assertIn(("R01", "large_caveated_ghg_estimate"), pairs)
        self.assertIn(("R13", "cost_and_carbon_scope_differ"), pairs)

    def test_all_starter_rows_have_official_report_cross_reference(self):
        with (data_pipeline.DERIVED / "cleaned_enriched_records.csv").open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 23)
        self.assertTrue(all(row["official_evidence_status"].startswith("primary_source_confirmed") for row in rows))
        self.assertTrue(all(row["official_printed_report_pages"] for row in rows))
        self.assertEqual(self.summary["rows_cross_referenced_to_official_gcc_climate_budget"], 23)

    def test_tenders_use_unique_ids_and_only_source_supported_awards(self):
        with (ROOT / "data/tenders/chennai_drainage_tender_packages.csv").open(newline="", encoding="utf-8") as f:
            tenders = list(csv.DictReader(f))
        ids = [row["tender_id"] for row in tenders]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 3)
        for row in tenders:
            self.assertEqual(row["awarded_contract_value_inr"], "")
            self.assertEqual(row["actual_expenditure_inr"], "")
            self.assertTrue(row["awarded_contract_value_usd"])
            self.assertTrue(row["contractor"])
            self.assertTrue(row["award_source_url"].startswith("https://www.adb.org/"))
            self.assertEqual(row["verification_status"], "official_tender_notice_and_ADB_award_fields_verified")
        self.assertEqual(self.summary["tender_award_value_records"], 3)
        self.assertEqual(self.summary["tender_actual_expenditure_records"], 0)


if __name__ == "__main__":
    unittest.main()
