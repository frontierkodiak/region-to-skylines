"""A wet grid vertex is not sufficient to preserve its interpolated wet bed."""

import unittest

import numpy as np

from verify_bank_restoration import native_water_ground, require_continuous_floor


class ContinuousFloorTests(unittest.TestCase):
    def test_unchanged_wet_vertex_does_not_authorize_raising_adjacent_bed(self):
        before = np.full((1081, 1081), 6400, dtype=np.uint16)
        after = before.copy()
        water = np.zeros_like(before)
        water[540, 540] = 16
        after[540, 541] += 128
        np.testing.assert_array_equal(before[water > 0], after[water > 0])
        target = 100.25
        self.assertLess(before[540:542, 540:542].mean() / 64, target)
        self.assertGreater(after[540:542, 540:542].mean() / 64, target)
        self.assertEqual(native_water_ground(before, [[8, 8]]), [100.0])
        self.assertEqual(native_water_ground(after, [[8, 8]]), [100.5])
        with self.assertRaisesRegex(ValueError, "Continuous wet-floor"):
            require_continuous_floor(before, after, water)

    def test_distant_dry_excavation_can_still_be_restored(self):
        before = np.full((1081, 1081), 6400, dtype=np.uint16)
        after = before.copy()
        water = np.zeros_like(before)
        water[540, 540] = 64
        after[540, 543] += 128
        require_continuous_floor(before, after, water)


if __name__ == "__main__":
    unittest.main()
