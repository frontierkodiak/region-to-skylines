import unittest

import numpy as np

from natural_basins import construct, validate_final


class NaturalBasinTests(unittest.TestCase):
    def setUp(self):
        self.floor = np.full((31, 31), 100.0)
        self.water = np.zeros_like(self.floor)
        self.mask = np.zeros_like(self.floor, bool)
        self.mask[14:17, 14:17] = True
        self.protected = np.zeros_like(self.mask)

    def build(self):
        return construct(
            self.floor, self.water, {"body": (self.mask, ["lakes:0"])}, self.protected
        )

    def test_passive_body_is_closed_without_new_sources_or_outside_changes(self):
        result = self.build()
        self.assertEqual(result.entries[0]["status"], "constructed")
        self.assertEqual(result.entries[0]["source_controls_added"], 0)
        self.assertTrue(np.all(result.water[self.mask] == 1.5))
        self.assertTrue(
            np.array_equal(self.floor[~self.mask], result.terrain[~self.mask])
        )
        self.assertTrue(
            np.array_equal(self.water[~self.mask], result.water[~self.mask])
        )
        self.assertTrue(
            validate_final(
                self.floor,
                self.water,
                result.terrain,
                result.water,
                result.masks,
                result.entries,
                self.protected,
            )
        )

    def test_small_single_node_feature_is_not_silently_omitted(self):
        self.mask[:] = False
        self.mask[15, 15] = True
        result = self.build()
        self.assertEqual(result.entries[0]["status"], "constructed")
        self.assertEqual(result.entries[0]["static_check"]["body_cells"], 1)

    def test_cut_at_three_metres_passes_and_above_refuses(self):
        self.floor[self.mask] = 101
        self.assertEqual(self.build().entries[0]["status"], "constructed")
        self.floor[self.mask] += 1 / 64
        result = self.build()
        self.assertEqual(result.entries[0]["status"], "refused")
        self.assertTrue(np.array_equal(result.terrain, self.floor))

    def test_diagonal_low_rim_and_protected_rim_refuse(self):
        self.floor[13, 13] = 95
        self.assertEqual(self.build().entries[0]["status"], "refused")
        self.floor[13, 13] = 100
        self.protected[13, 13] = True
        self.assertEqual(self.build().entries[0]["status"], "refused")

    def test_existing_open_water_and_clipped_body_refuse(self):
        self.water[13, 13] = 1
        self.assertEqual(self.build().entries[0]["status"], "refused")
        self.water[:] = 0
        self.mask[0, 0] = True
        self.assertEqual(self.build().entries[0]["status"], "refused")

    def test_existing_initial_water_is_never_removed(self):
        self.water[self.mask] = 2
        self.assertEqual(self.build().entries[0]["status"], "refused")
        self.assertTrue(np.all(self.water[self.mask] == 2))

    def test_late_rim_cut_fill_and_outside_water_are_rejected(self):
        result = self.build()
        for fault in ("rim", "fill", "water"):
            floor, water = result.terrain.copy(), result.water.copy()
            if fault == "rim":
                floor[13, 13] -= 1
            elif fault == "fill":
                floor[15, 15] = self.floor[15, 15] + 1 / 64
            else:
                water[0, 0] = 1 / 64
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                validate_final(
                    self.floor,
                    self.water,
                    floor,
                    water,
                    result.masks,
                    result.entries,
                    self.protected,
                )


if __name__ == "__main__":
    unittest.main()
