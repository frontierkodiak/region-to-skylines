"""Behavioral checks for the offline attribution tool, with no network/game."""

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

try:
    from audit_place_terrain import audit, native_units, stage_metrics
except ImportError as exc:  # polli-place-model 0.3 lives in the workbench, not in this repo
    raise unittest.SkipTest(f"needs polli-place-model 0.3: {exc}")


class AttributionTests(unittest.TestCase):
    def setUp(self):
        rows, cols = np.mgrid[:1081, :1081] / 1080
        self.source = 50 + 200 * rows**2 + 100 * cols**3 + 40 * rows * cols
        self.reference = np.flipud(self.source)[::4, ::4]
        self.fit = {"base": 0, "verticalScale": 1}

    def test_asymmetric_source_and_north_south_flip_are_distinguished(self):
        correct = stage_metrics(self.source, self.reference, self.source, self.fit)
        flipped = stage_metrics(
            np.flipud(self.source), self.reference, self.source, self.fit
        )
        self.assertEqual(correct["correlation"]["as is"], 1)
        self.assertEqual(
            correct["error_vs_canonical_dem_source_metres"]["maximum_abs"], 0
        )
        self.assertLess(flipped["correlation"]["as is"], 0)
        self.assertEqual(flipped["correlation"]["mirrored north-south"], 1)

    def test_source_reference_failure_is_not_an_exporter_error(self):
        reference = np.cos(np.mgrid[:271, :271][1])
        result = stage_metrics(self.source, reference, self.source, self.fit)
        self.assertLess(result["correlation"]["as is"], 0.9)
        self.assertEqual(
            result["error_vs_canonical_dem_source_metres"]["maximum_abs"], 0
        )

    def test_clockwise_label_uses_the_frozen_north_up_convention(self):
        result = stage_metrics(
            np.rot90(self.source, -1), self.reference, self.source, self.fit
        )
        self.assertEqual(result["correlation"]["rotated 90° clockwise"], 1)
        self.assertLess(result["correlation"]["rotated 90° counter-clockwise"], 0)

    def test_native_quantization_is_bounded_and_matches_writer(self):
        result = stage_metrics(self.source, self.reference, self.source, self.fit)
        self.assertLessEqual(
            result["native_quantization_maximum_abs_game_metres"], 1 / 128
        )
        self.assertEqual(
            native_units(np.array([[1.0, 1 + 1 / 128], [2, 3]])).tolist(),
            [[128, 192], [64, 65]],
        )

    def test_mismatched_manifest_is_rejected_before_reading_other_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "place.json").write_text(json.dumps({"schema": "polli.place/0"}))
            (root / "geometry.json").write_text(
                json.dumps({"placeInput": {"manifest_sha256": "wrong"}})
            )
            with self.assertRaisesRegex(ValueError, "manifest differs"):
                audit(root, root, root, root / "output")
            self.assertFalse((root / "output").exists())

    def test_changed_source_bytes_are_rejected_before_sampling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "place.json").write_text(
                json.dumps(
                    {"layers": {"terrain": {"path": "terrain.arrow", "sha256": "old"}}}
                )
            )
            from audit_place_terrain import sha256

            (root / "geometry.json").write_text(
                json.dumps(
                    {"placeInput": {"manifest_sha256": sha256(root / "place.json")}}
                )
            )
            (root / "terrain.arrow").write_bytes(b"changed source")
            with self.assertRaisesRegex(ValueError, "terrain differs"):
                audit(root, root, root, root / "output")
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
