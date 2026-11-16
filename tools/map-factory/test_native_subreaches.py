"""Dry-only changes must preserve real water interfaces and intake dry floors."""

import unittest

import numpy as np

from native_subreaches import dry_domain, restore, source_radii


class DrySubreachTests(unittest.TestCase):
    def test_nearby_water_does_not_keep_a_dry_subreach_carved(self):
        lines = np.zeros((15, 15), bool)
        lines[7, 2:13] = True
        later = np.zeros_like(lines)
        later[7, 7] = True
        dry, zone, guard = dry_domain(lines, lines, later, np.zeros_like(lines))
        self.assertTrue(dry[7, 10])  # 48 m away: old 64 m piece test hid this.
        self.assertFalse(dry[7, 8])  # Actual flow/interpolation interface wins.
        self.assertFalse(zone[guard].any())

    def test_independent_line_keeps_equal_distance_territory(self):
        eligible = np.zeros((15, 15), bool)
        eligible[7, 5] = True
        lines = eligible.copy()
        lines[7, 9] = True
        _, zone, _ = dry_domain(
            eligible, lines, np.zeros_like(lines), np.zeros_like(lines)
        )
        self.assertFalse(zone[7, 7])
        self.assertTrue(zone[7, 6])

    def test_output_footprint_is_guarded_even_when_intake_is_zero(self):
        guard = source_radii(
            {
                "sources": [
                    {"position": [0, 0, 0], "capacity": 0, "output_capacity": 0.8}
                ]
            }
        )
        self.assertTrue(guard[540, 546])  # 96 m, inside native output radius.
        self.assertFalse(guard[540, 547])  # 112 m, outside it.

    def test_startup_storage_beside_a_later_pool_is_kept(self):
        shape = (1081, 1081)
        terrain = np.full(shape, 6400, np.uint16)
        water = np.zeros(shape, np.uint16)
        water[539:542, 539:542] = [[0, 14, 0], [42, 103, 69], [29, 57, 2]]
        water[540, 560] = 64  # Independent never-rewetted film can still clear.
        later = np.zeros(shape, bool)
        later[540, 540] = True
        empty = np.zeros(shape, bool)
        dry, zone, guard = dry_domain(empty, empty, later, empty)
        banks = np.full(shape, 100.0)
        geometry = {"sq": {"scale": 1}, "fit": {"verticalScale": 1}, "rivers": []}
        _, initial, _, _ = restore(
            terrain,
            water,
            later,
            empty,
            dry,
            zone,
            guard,
            banks,
            banks,
            geometry,
        )
        np.testing.assert_array_equal(
            initial[539:542, 539:542], water[539:542, 539:542]
        )
        self.assertEqual(initial[540, 560], 0)

    def test_dry_intake_cell_is_not_restored_or_drained(self):
        shape = (1081, 1081)
        terrain = np.full(shape, 6400, dtype=np.uint16)
        water = np.zeros(shape, np.uint16)
        # The knife-edge dry intake cell stays below target. A zero output
        # cannot justify removing its physical footprint or changing this bed.
        terrain[540, 540] = 6384
        water[540, 541] = 64
        water[540, 560] = 64
        source = source_radii(
            {
                "sources": [
                    {"position": [0, 0, 0], "capacity": 0.8, "output_capacity": 0}
                ]
            }
        )
        line = np.zeros(shape, bool)
        line[540, 540:563] = True
        later = np.zeros(shape, bool)
        dry, zone, guard = dry_domain(line, line, later, source)
        terrain[540, 560] = 6208  # Old dry incision, outside intake.
        banks = np.full(shape, 100.0)
        geometry = {"sq": {"scale": 1}, "fit": {"verticalScale": 1}, "rivers": []}
        candidate, initial, clear, _ = restore(
            terrain,
            water,
            later,
            source,
            dry,
            zone,
            guard,
            banks,
            banks,
            geometry,
        )
        self.assertEqual(candidate[540, 540], 6384)
        self.assertEqual(initial[540, 541], 64)
        self.assertEqual(candidate[540, 560], 6400)
        self.assertEqual(initial[540, 560], 0)
        self.assertTrue(clear[540, 560])
        self.assertTrue(np.all(candidate >= terrain))


if __name__ == "__main__":
    unittest.main()
