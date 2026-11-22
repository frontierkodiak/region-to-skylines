import gzip
from pathlib import Path
import tempfile
import unittest

import numpy as np

from initial_water_safety import cover_native, masks, retention


class InitialSafetyTests(unittest.TestCase):
    def test_initial_reference_cannot_clear_new_deep_built_up_water(self):
        before = np.zeros((3, 3), dtype=np.uint16)
        after = before.copy()
        after[1, 1] = 33
        built = np.ones_like(before, bool)
        empty = np.zeros_like(before, bool)
        result = masks(before, after, built, empty, empty)
        self.assertEqual(int(result["new_deep_dated_built_up"].sum()), 1)
        self.assertTrue((after > 6.4)[1, 1])

    def test_delta_retains_absolute_baseline_hazard_and_strict_depth_threshold(self):
        before = np.array([[64, 0, 0]], dtype=np.uint16)
        after = np.array([[64, 32, 33]], dtype=np.uint16)
        empty = np.zeros_like(before, bool)
        result = masks(before, after, ~empty, empty, empty)
        self.assertEqual(int(result["baseline_deep"].sum()), 1)
        self.assertEqual(int(result["candidate_deep"].sum()), 2)
        self.assertEqual(int(result["new_deep"].sum()), 1)

    def test_later_drying_does_not_remove_initial_hazard(self):
        before = np.zeros((3, 3), dtype=np.uint16)
        after = np.full_like(before, 64)
        empty = np.zeros_like(before, bool)
        group = masks(before, after, ~empty, empty, empty)["new_deep"]
        self.assertEqual(retention(group, before)["nearby_wet_within64m"], 0)
        self.assertEqual(int(group.sum()), 9)

    def test_native_cover_orientation_and_last_vertex_are_explicit(self):
        values = np.zeros((1728, 1728), dtype=np.uint8)
        values[0, :] = 10
        values[-1, :] = 50
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "cover.gz"
            p.write_bytes(gzip.compress(values.tobytes()))
            result = cover_native(p, size=3)
        self.assertEqual(result[0, 0], 50)
        self.assertEqual(result[-1, -1], 10)

    def test_shallow_captured_drying_is_not_proof_of_nearby_loss(self):
        initial = np.full((9, 9), 16, dtype=np.uint16)
        later = np.zeros_like(initial)
        later[4, 4] = 64
        group = initial > 0
        metrics = retention(group, later)
        self.assertEqual(metrics["exact_wet"], 1)
        self.assertGreater(metrics["nearby_wet_within64m"], 1)
        self.assertLess(metrics["nearby_wet_within64m"], 81)


if __name__ == "__main__":
    unittest.main()
