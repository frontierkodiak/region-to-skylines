"""Behavioral geometry tests; these do not qualify native water simulation."""

import unittest

import numpy as np
from scipy import ndimage

from reservoir_basin import construct_closed_reservoir


class ReservoirBasinTests(unittest.TestCase):
    def setUp(self):
        self.terrain = np.full((81, 81), 100.0)
        self.water = np.zeros_like(self.terrain)
        self.allowed = np.ones_like(self.terrain, dtype=bool)
        self.protected = np.zeros_like(self.allowed)

    def build(self, preferred=(0, 0)):
        return construct_closed_reservoir(
            self.terrain, self.water, self.allowed, self.protected, preferred
        )

    def test_flat_basin_quantized_closed_and_bounded_without_input_mutation(self):
        self.terrain[:] = 100.007
        before = self.terrain.copy()
        result = self.build()
        self.assertEqual(result.source["position"], [0, 0, 0])
        self.assertEqual(result.source["capacity"], 0.06)
        yy, xx = np.mgrid[:81, :81]
        radius = np.hypot(yy - 40, xx - 40)
        core = radius * 16 <= result.receipt["source_radius_m"]
        ring = (radius >= 6) & (radius < 7)
        self.assertTrue((result.water[core] >= 1).all())
        self.assertTrue((result.terrain[ring] - result.source["target"] >= 0.5).all())
        self.assertTrue((result.terrain <= before).all())
        self.assertLessEqual(float((before - result.terrain).max()), 3)
        np.testing.assert_array_equal(result.terrain[radius >= 6], before[radius >= 6])
        np.testing.assert_array_equal(
            result.water[radius >= 6], self.water[radius >= 6]
        )
        changed = result.terrain != before
        np.testing.assert_array_equal(
            result.terrain[changed] * 64, np.round(result.terrain[changed] * 64)
        )
        self.assertEqual(result.source["target"] * 64 % 1, 0)
        np.testing.assert_array_equal(self.terrain, before)
        self.assertFalse(self.water.any())
        self.assertIn("NOT native verified", result.receipt["qualification"])
        components, _ = ndimage.label(result.water > 0, structure=np.ones((3, 3)))
        self.assertFalse(((components == components[40, 40]) & (radius >= 6)).any())

    def test_diagonal_low_escape_cell_prevents_false_enclosure(self):
        terrain = np.full((13, 13), 100.0)
        terrain[12, 10] = 90  # Offset (6,4) neighbors inside offset (5,3).
        with self.assertRaisesRegex(ValueError, "No feasible enclosed"):
            construct_closed_reservoir(
                terrain,
                np.zeros_like(terrain),
                np.ones_like(terrain, dtype=bool),
                np.zeros_like(terrain, dtype=bool),
                (0, 0),
            )

    def test_native_height_range_and_zero_floor(self):
        self.terrain[:] = 65535 / 64
        result = self.build()
        self.assertLessEqual(float(result.terrain.max()), 65535 / 64)
        self.terrain[:] = 65535 / 64 + 1 / 64
        with self.assertRaisesRegex(ValueError, "native uint16 height range"):
            self.build()
        self.terrain[:] = 1.5
        result = self.build()
        self.assertGreaterEqual(float(result.terrain.min()), 0)
        self.assertGreaterEqual(result.receipt["minimum_source_footprint_depth_m"], 1)

    def test_legacy_sloping_location_relocates_to_flat_patch(self):
        self.terrain[:] = 100 + np.arange(81)[None, :] * 2
        self.terrain[10:31, 10:31] = 140
        result = self.build()
        row, col = result.receipt["center_row_col"]
        self.assertTrue(10 <= row <= 30 and 10 <= col <= 30)
        self.assertGreaterEqual(result.receipt["minimum_rim_freeboard_m"], 0.5)
        self.assertGreater(result.receipt["preferred_distance_m"], 0)

    def test_impossible_slope_refused(self):
        self.terrain[:] = 100 + np.arange(81)[None, :] * 2
        with self.assertRaisesRegex(ValueError, "No feasible enclosed"):
            self.build()

    def test_wet_and_protected_envelopes_excluded_but_preserved(self):
        self.water[40, 40] = 0.001
        self.protected[40, 47] = True
        result = self.build()
        row, col = result.receipt["center_row_col"]
        self.assertGreaterEqual(np.hypot(row - 40, col - 40), 7)
        self.assertGreaterEqual(np.hypot(row - 40, col - 47), 7)
        self.assertEqual(result.water[40, 40], 0.001)
        self.assertEqual(result.terrain[40, 40], 100)
        self.assertEqual(result.terrain[40, 47], 100)

    def test_no_available_unprotected_or_dry_domain_refused(self):
        for blocked in (self.water, self.protected):
            with self.subTest(blocked=blocked.dtype):
                blocked[:] = 1
                with self.assertRaisesRegex(ValueError, "No feasible enclosed"):
                    self.build()
                blocked[:] = 0

    def test_mask_contains_entire_rim_and_deterministic_ties(self):
        self.allowed[:] = False
        self.allowed[25:56, 25:56] = True
        first = self.build((8, 8))
        second = self.build((8, 8))
        self.assertEqual(first.receipt["center_row_col"], [39, 40])
        self.assertEqual(first.receipt, second.receipt)
        np.testing.assert_array_equal(first.terrain, second.terrain)
        np.testing.assert_array_equal(
            first.terrain[~self.allowed], self.terrain[~self.allowed]
        )
        self.allowed[:] = False
        self.allowed[35:46, 35:46] = True
        with self.assertRaisesRegex(ValueError, "No feasible enclosed"):
            self.build()


if __name__ == "__main__":
    unittest.main()
