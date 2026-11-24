import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from compare_water_references import sampled_surfaces, footprint_retention


class ReferenceComparisonTest(unittest.TestCase):
    def test_complete_footprint_retains_thin_limbs_and_64m_circle(self):
        initial = np.zeros((17, 17), dtype=np.uint16)
        initial[8, 4] = 7
        initial[8, 13] = 7
        current = np.zeros_like(initial)
        current[8, 8] = 7
        result = footprint_retention(initial, [("t005", current)])
        self.assertEqual(result["traces"][0]["fraction"], 0.5)
        self.assertEqual(len(result["components"]), 2)
        self.assertEqual(result["components"][0]["minimum_retained_fraction"], 1)
        self.assertEqual(result["components"][1]["minimum_retained_fraction"], 0)

    def test_no_planned_water_is_unknown_not_a_zero_loss_pass(self):
        initial = np.zeros((17, 17), dtype=np.uint16)
        result = footprint_retention(initial, [("t005", initial)])
        self.assertIsNone(result["traces"][0]["fraction"])
        self.assertEqual(result["components"], [])

    def test_no_surface_from_dry_ground_or_zero_depth_api_flag(self):
        inventory = {
            "entries": [
                {
                    "contracts": [
                        {"kind": "natural", "probe_names": ["a", "b", "c", "d"]}
                    ]
                }
            ]
        }
        first = [
            {"name": "a", "wet": True, "depth": 1, "surface": 100},
            {"name": "b", "wet": False, "depth": 0, "surface": 90},
            {"name": "c", "wet": True, "depth": 0, "surface": 70},
            {"name": "d", "wet": True, "depth": 1, "surface": None},
        ]
        later = [
            {"name": "a", "wet": True, "depth": 2, "surface": 101},
            {"name": "b", "wet": True, "depth": 1, "surface": 95},
            {"name": "c", "wet": False, "depth": 0, "surface": 70},
            {"name": "d", "wet": True, "depth": 1, "surface": None},
        ]
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            folder = Path(directory)
            rows = [
                {"kind": "sample", "label": label, "water": {"samples": values}}
                for label, values in [("t000", first), ("t005", later)]
            ]
            (folder / "timeline.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n"
            )
            result = sampled_surfaces(folder, inventory)
        self.assertEqual(result[0]["wet_heads"], 1)
        self.assertEqual(result[0]["dry"], 2)
        self.assertEqual(result[0]["missing"], 1)
        self.assertEqual(result[1]["wet_heads"], 2)
        self.assertEqual(result[1]["paired_initial_wet_heads"], 1)
        self.assertEqual(result[1]["delta_p10_p50_p90_m"], [1, 1, 1])

    def test_duplicate_alias_does_not_silently_choose_a_surface(self):
        inventory = {
            "entries": [{"contracts": [{"kind": "natural", "probe_names": ["a"]}]}]
        }
        point = {"name": "a", "wet": True, "depth": 1, "surface": 100}
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            folder = Path(directory)
            (folder / "timeline.jsonl").write_text(
                json.dumps(
                    {
                        "kind": "sample",
                        "label": "t000",
                        "water": {"samples": [point, point]},
                    }
                )
                + "\n"
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                sampled_surfaces(folder, inventory)


if __name__ == "__main__":
    unittest.main()
