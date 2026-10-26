import csv
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from src import multicity_catalog as mc


class MultiCityCatalogTests(unittest.TestCase):
    def test_safe_name_prevents_path_components(self):
        self.assertNotIn("/", mc.safe_name("../../private/a.csv"))
        self.assertNotIn("\\", mc.safe_name("..\\private"))

    def test_package_mapping_preserves_unknowns_and_provenance(self):
        row = mc._package_record("Pune", {"id":"x", "title":"Rainfall", "license_title":None},
                                 {"id":"r1", "url":"https://example.org/a.csv", "format":"CSV"})
        self.assertEqual(row["city_query"], "Pune")
        self.assertEqual(row["licence"], "unknown")
        self.assertEqual(row["download_status"], "not_attempted")
        self.assertIn("require human", row["quality_note"])

    def test_ckan_pagination(self):
        calls = []
        pages = [
            {"success":True,"result":{"count":2,"results":[{"id":"1","title":"Test dataset A","resources":[]}] }},
            {"success":True,"result":{"count":2,"results":[{"id":"2","title":"Test dataset B","resources":[]}] }},
        ]
        with patch.object(mc, "_json_get", side_effect=lambda url: calls.append(url) or pages[len(calls)-1]):
            rows = mc.discover_opencity("Test", rows=1)
        self.assertEqual(len(rows), 2)
        self.assertIn("start=1", calls[1])

    def test_csv_and_geojson_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "x.csv"
            p.write_text("a,b\n1,2\n", encoding="utf-8")
            self.assertEqual(mc.validate_resource(p, "csv"), "downloaded_format_sanity_check_passed")
            p = Path(temp) / "x.geojson"
            p.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
            self.assertEqual(mc.validate_resource(p, "geojson"), "downloaded_format_sanity_check_passed")

    def test_report_does_not_claim_model_candidates(self):
        result = mc.build_report([{"city_id":"x","name":"X"}], [], 1)
        self.assertEqual(result["model_ready_candidates"], 0)
        self.assertEqual(result["failed_operations_in_this_run"], 1)

    def test_kml_transformation_retains_source_and_checks_lon_lat(self):
        kml = ET.fromstring('''<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><name>Lake</name><ExtendedData><SchemaData><SimpleData name="OBJECTID">4</SimpleData></SchemaData></ExtendedData><Point><coordinates>80.2,13.1,0</coordinates></Point></Placemark></kml>''')
        record = {"dataset_id":"test-lake", "sha256":"abc123", "title":"Lake layer", "city_query":"Chennai"}
        with tempfile.TemporaryDirectory() as temp, patch.object(mc, "ROOT", Path(temp)):
            output, count, issues = mc.kml_to_geojson(kml, record)
            import json
            layer = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual((count, issues), (1, 0))
        self.assertEqual(layer["features"][0]["geometry"]["coordinates"], [80.2, 13.1])
        self.assertEqual(layer["features"][0]["properties"]["source_sha256"], "abc123")

    def test_changed_download_creates_new_immutable_raw_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "data/raw/catalog_resources"
            meta = root / "data/metadata"
            record = {"dataset_id":"dataset", "resource_id":"r1", "city_query":"X", "title":"T",
                      "resource_url":"https://example.org/r1.csv", "format":"csv"}
            responses = [(b"a\n1\n", "text/csv", 200), (b"a\n2\n", "text/csv", 200)]
            with patch.object(mc, "ROOT", root), patch.object(mc, "RAW", raw), patch.object(mc, "META", meta), \
                 patch.object(mc, "request_bytes", side_effect=responses):
                first = mc.download_resource(dict(record))
                second = mc.download_resource(dict(record))
            first_path, second_path = root / first["local_path"], root / second["local_path"]
            self.assertNotEqual(first_path, second_path)
            self.assertEqual(first_path.read_bytes(), b"a\n1\n")
            self.assertEqual(second_path.read_bytes(), b"a\n2\n")
            self.assertEqual(len((meta / "collection_manifest.jsonl").read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
