import unittest

from street_view_insights import formatted_pixel_count, plain_language_reading, valid_percentage


class StreetViewInsightsTests(unittest.TestCase):
    def test_formats_live_image_metrics_without_hardcoded_examples(self):
        result = {
            "green_hued_pixel_share_pct": 18.25,
            "low_saturation_gray_pixel_share_pct": 42.0,
            "sampled_pixels": 137728,
        }
        self.assertEqual(valid_percentage(result, "green_hued_pixel_share_pct"), 18.25)
        self.assertEqual(formatted_pixel_count(result), "137,728")
        reading = plain_language_reading(result)
        self.assertIn("18.2%", reading)
        self.assertIn("42.0%", reading)
        self.assertNotIn("28.1%", reading)

    def test_missing_or_invalid_metrics_are_graceful(self):
        self.assertIsNone(valid_percentage(None, "green_hued_pixel_share_pct"))
        self.assertIsNone(valid_percentage({"green_hued_pixel_share_pct": float("nan")}, "green_hued_pixel_share_pct"))
        self.assertIsNone(valid_percentage({"green_hued_pixel_share_pct": 120}, "green_hued_pixel_share_pct"))
        self.assertIsNone(formatted_pixel_count({"sampled_pixels": 0}))
        self.assertIn("not available", plain_language_reading({"green_hued_pixel_share_pct": 4}))

    def test_neutral_reading_does_not_claim_objects_or_impacts(self):
        reading = plain_language_reading({
            "green_hued_pixel_share_pct": 0,
            "low_saturation_gray_pixel_share_pct": 0,
        })
        self.assertIn("no color cue", reading)
        self.assertNotIn("trees", reading)
        self.assertNotIn("emissions reduction", reading)


if __name__ == "__main__":
    unittest.main()
