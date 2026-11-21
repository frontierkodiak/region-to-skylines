"""Keep the construction holdout separate from every named development square."""

import hashlib
import json
from pathlib import Path
import unittest

from stable_water_panel import panel, separation

ROOT = Path(__file__).resolve().parent


class StableWaterPanelTests(unittest.TestCase):
    def test_frozen_selection_and_geographic_separation(self):
        path = ROOT / "stable-water-panel.json"
        freeze = json.loads(
            (ROOT / "calibration/pl1191-construction-v1/freeze.json").read_text()
        )
        self.assertEqual(panel(), json.loads(path.read_text()))
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(), freeze["panel_sha256"]
        )
        self.assertEqual(len(freeze["excluded_squares"]), 39)
        self.assertGreaterEqual(separation(panel(), freeze["excluded_squares"]), 100)

    def test_a_development_square_cannot_be_reused_as_holdout(self):
        selected = panel()
        with self.assertRaisesRegex(ValueError, "Insufficient separation"):
            separation(selected, selected["squares"][:1])


if __name__ == "__main__":
    unittest.main()
