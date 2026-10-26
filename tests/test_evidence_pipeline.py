import csv
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from collect_sources import parse_cmrl, pdf_text_stats
from evidence_pipeline import INDEX_FIELDS, _normalize_status, identify_duplicates, normalize_tender_reference, validate


class EvidencePipelineTests(unittest.TestCase):
    def test_live_saved_page_parser_preserves_source_rows_and_repeated_ids(self):
        source = b"""<table><tr><th>Department</th><th>Tender No</th><th>Name of the Work</th><th>NIT Date</th><th>Mode &amp; Type of Tender</th><th>Name of the Contractor / Consultant</th><th>Awarded Contract Value Including GST</th><th>Contract Awarded Date</th></tr>
        <tr><td>Civil</td><td>CMRL/TEST-1/2025</td><td>Drain improvement, phase &amp; pump</td><td>01/02/2025</td><td>Open tender</td><td>Contractor A</td><td>Rs. 5 Cr</td><td>03/04/2025</td></tr>
        <tr><td>Civil</td><td>CMRL/TEST-1/2025</td><td>Drain improvement, phase &amp; pump</td><td>01/02/2025</td><td>Open tender</td><td>Contractor B</td><td>Rs. 6 Cr</td><td>04/04/2025</td></tr></table>"""
        rows = parse_cmrl(source, "2026-10-26T00:00:00Z", hashlib.sha256(source).hexdigest())
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r["evidence_id"] for r in rows}), 2)
        self.assertEqual(rows[0]["work_title"], "Drain improvement, phase & pump")
        self.assertEqual(rows[1]["contractor"], "Contractor B")
        self.assertTrue(all(r["source_content_sha256"] == hashlib.sha256(source).hexdigest() for r in rows))

    def test_pdf_feasibility_check_does_not_invent_text_for_scanned_page(self):
        from pypdf import PdfWriter
        import io
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        output = io.BytesIO()
        writer.write(output)
        self.assertEqual(pdf_text_stats(output.getvalue()), (1, 0))

    def test_tender_reference_normalization_is_unicode_and_punctuation_safe(self):
        self.assertEqual(normalize_tender_reference("CMRL/PHASE–II/SYS 01/2024"), "cmrlphaseiisys012024")

    def test_status_normalization_preserves_ongoing_work_with_partial_completion(self):
        self.assertEqual(_normalize_status("Ongoing; 78% physical progress reported"), "ongoing")
        self.assertEqual(_normalize_status("Planning stage (Mayor announcement)"), "proposed")
        self.assertEqual(_normalize_status("Mixed status: one work open, another 43% complete"), "mixed_source_status")

    def test_duplicate_reference_is_flagged_not_merged_and_fuzzy_pairs_retained(self):
        rows = [
            {"evidence_id": "A", "source_type": "notice", "tender_reference": "GCC/1", "exact_source_title": "Construction of storm drain package 1"},
            {"evidence_id": "B", "source_type": "award", "tender_reference": "GCC 1", "exact_source_title": "Construction of storm drain package 1"},
        ]
        findings = identify_duplicates(rows)
        self.assertTrue(any(r["match_type"] == "exact_normalized_tender_reference" for r in findings))
        self.assertTrue(any(r["match_type"] == "cross_source_fuzzy_title" for r in findings))
        self.assertEqual(len(rows), 2)

    def test_distinct_explicit_package_numbers_do_not_become_fuzzy_duplicates(self):
        rows = [
            {"evidence_id": "A", "source_type": "notice", "tender_reference": "GCC/28", "exact_source_title": "Construction of integrated drain Package 28 in basin"},
            {"evidence_id": "B", "source_type": "award", "tender_reference": "GCC/43", "exact_source_title": "Construction of integrated drain Package 43 in basin"},
        ]
        findings = identify_duplicates(rows)
        self.assertEqual(findings, [])

    def test_validator_flags_missing_provenance_and_bad_dates_without_dropping_rows(self):
        row = {field: "" for field in INDEX_FIELDS}
        row.update(evidence_id="X", exact_source_title="Example", agency="GCC", source_type="report",
                   primary_source_url="http://bad.example/", publication_date_as_published="31/31/2025")
        issues = validate([row], [])
        self.assertIn("invalid_source_url", {r["code"] for r in issues})
        self.assertIn("date_requires_manual_review", {r["code"] for r in issues})
        self.assertEqual(row["evidence_id"], "X")


if __name__ == "__main__":
    unittest.main()
