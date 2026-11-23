import unittest

import numpy as np

from playable_water import (
    capacity,
    hydrology,
    join_nearby_water,
    section,
    source_walk,
    stage_tree,
)


class PlayableWaterTests(unittest.TestCase):
    def test_channel_has_volume_and_sloping_sides(self):
        result = section(np.array([0, 16, 32, 48, 64]), 32, 8)
        self.assertEqual(result[0], 8)
        self.assertTrue(np.all(np.diff(result) <= 0))
        self.assertGreater(result[2], 1)
        self.assertEqual(result[-1], 0)

    def test_capacity_grows_with_local_catchment_and_is_bounded(self):
        values = [capacity(a, "river") for a in [0, 1, 10, 100, 100000]]
        self.assertEqual(values, sorted(values))
        self.assertGreater(values[0], 0)
        self.assertLessEqual(values[-1], 0.12)
        self.assertLess(capacity(0, "stream"), capacity(0, "river"))

    def test_trunk_and_branch_drain_to_the_same_low_edge(self):
        mask = np.zeros((9, 9), bool)
        mask[:, 4] = True
        mask[4, 4:] = True
        desired = np.full(mask.shape, 100.0)
        desired[0, 4] = 90
        stage, arc, outlets = stage_tree(
            mask, desired, np.zeros_like(mask), np.zeros_like(mask)
        )
        self.assertEqual(len(outlets), 1)
        self.assertEqual(outlets[0]["role"], "map_edge")
        self.assertTrue(np.all(np.isfinite(stage[mask])))
        self.assertGreater(stage[8, 4], stage[0, 4])
        self.assertGreater(arc[4, 8], arc[4, 4])

    def test_closed_captured_water_has_an_explicit_terminal(self):
        mask = np.zeros((7, 7), bool)
        mask[2:5, 2:5] = True
        level = np.full(mask.shape, 20.0)
        stage, _, outlets = stage_tree(mask, level, mask, np.zeros_like(mask))
        self.assertEqual(outlets[0]["role"], "closed_sink")
        np.testing.assert_array_equal(stage[mask], 20)

    def test_crossing_line_is_clipped_without_moving_it_to_a_corner(self):
        walk = source_walk(np.array([[-20.0, 540.0], [1100.0, 540.0]]))
        self.assertEqual(tuple(walk[0]), (540, 0))
        self.assertEqual(tuple(walk[-1]), (540, 1080))
        self.assertTrue(np.all(walk[:, 0] == 540))

    def test_sill_is_deepened_not_propagated_as_a_wall(self):
        mask = np.zeros((9, 9), bool)
        mask[:, 4] = True
        desired = np.full(mask.shape, 100.0)
        desired[0, 4] = 20
        desired[4, 4] = 400
        desired[6, 4] = 50
        stage, _, _ = stage_tree(
            mask, desired, np.zeros_like(mask), np.zeros_like(mask)
        )
        self.assertLess(stage[4, 4], 50)
        self.assertTrue(np.all(np.diff(stage[:, 4]) >= 0))

    def test_short_authored_join_respects_an_underground_gap(self):
        water = np.zeros((1081, 1081), bool)
        water[540, 530:534] = True
        water[540, 538:542] = True
        joined, links = join_nearby_water(water, np.zeros_like(water))
        self.assertEqual(len(links), 1)
        self.assertTrue(joined[540, 530:542].all())
        forbidden = np.zeros_like(water)
        forbidden[:, 535] = True
        blocked, links = join_nearby_water(water, forbidden)
        self.assertFalse(links)
        np.testing.assert_array_equal(blocked, water)

    def test_no_water_never_changes_measured_land(self):
        ground = np.full((1081, 1081), 100.0)
        before = ground.copy()
        geometry = {
            "sq": {"lat": 0, "lon": 0, "scale": 1, "rotation": 0},
            "rivers": [],
            "streams": [],
            "lakes": [],
            "riverAreas": [],
            "oceans": [],
        }
        depth, report = hydrology(ground, ground.copy(), geometry)
        np.testing.assert_array_equal(ground, before)
        self.assertFalse(depth.any())
        self.assertEqual(report["sources"], [])


if __name__ == "__main__":
    unittest.main()
