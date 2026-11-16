"""Preserve transient storage, inter-patch routes and signed intake capacity."""

import unittest

import numpy as np

from native_transient import availability, dry_capacity, intake_constraint, ring_release


class TransientTests(unittest.TestCase):
    def test_single_sustained_patch_can_release_outer_ring(self):
        retained = np.zeros((15, 15), bool)
        retained[7, 7] = True
        water = np.zeros_like(retained, dtype=np.uint16)
        water[7, 6:8] = 64
        release, _, _ = ring_release(retained, retained, water)
        self.assertTrue(release[7, 5])

    def test_transient_pool_keeps_its_routes(self):
        retained = np.zeros((15, 15), bool)
        retained[7, 7] = True
        water = np.zeros_like(retained, dtype=np.uint16)
        water[7, 6:8] = 64
        release, transient, _ = ring_release(retained, np.zeros_like(retained), water)
        self.assertFalse(release[7, 5])
        self.assertTrue(transient[7, 5])

    def test_separate_retained_patches_do_not_get_a_dam_between_them(self):
        retained = np.zeros((15, 15), bool)
        retained[7, [5, 9]] = True
        water = retained.astype(np.uint16) * 64
        release, _, bridge = ring_release(retained, retained, water)
        self.assertTrue(bridge[7, 7])
        self.assertFalse(release[7, 7])

    def test_orphan_startup_film_keeps_its_route(self):
        retained = np.zeros((15, 15), bool)
        retained[7, 7] = True
        water = np.zeros_like(retained, dtype=np.uint16)
        water[7, 5] = 64  # Does not touch retained water.
        release, _, _ = ring_release(retained, retained, water)
        self.assertFalse(release[7, 6])

    def test_availability_shift_is_state_independent_including_dry_cells(self):
        old = np.array([[80, 95, 110]])
        new = np.array([[90, 105, 120]])
        mask = np.ones_like(old, bool)
        shift = dry_capacity(old, 100 / 64, mask) - dry_capacity(new, 100 / 64, mask)
        for water in [
            np.array([[0, 0, 0]]),
            np.array([[0, 8, 30]]),
            np.array([[50, 2, 100]]),
        ]:
            self.assertEqual(
                availability(new, water, 100 / 64, mask)
                - availability(old, water, 100 / 64, mask),
                shift,
            )
        self.assertEqual(availability(old, np.zeros_like(old), 100 / 64, mask), -25)

    def test_zero_output_with_actual_withdrawal_keeps_entire_intake(self):
        source = {"type": 1, "input_rate": 100, "output_rate": 0, "target": 100 / 64}
        actual = [{"buffered_water": 10, "flow": 0}]
        floor = np.array([[90, 110]])
        mask = np.ones_like(floor, bool)
        guard, released, _ = intake_constraint(
            source, actual, floor, {"t005": np.array([[0, 1]])}, mask
        )
        self.assertFalse(released)
        np.testing.assert_array_equal(guard, mask)

    def test_inactive_intake_with_above_target_water_keeps_dry_capacity(self):
        source = {"type": 1, "input_rate": 100, "output_rate": 0, "target": 100 / 64}
        floor = np.array([[90, 105]])
        guard, released, above = intake_constraint(
            source,
            [{"buffered_water": 0, "flow": 0}],
            floor,
            {"t005": np.array([[0, 1]])},
            np.ones_like(floor, bool),
        )
        self.assertTrue(released and above)
        np.testing.assert_array_equal(guard, [[True, False]])


if __name__ == "__main__":
    unittest.main()
