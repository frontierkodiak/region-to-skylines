import unittest

import numpy as np

from joint_surface import connected_surface


class JointSurfaceTests(unittest.TestCase):
    def test_a_steep_join_preserves_upstream_relief_and_a_downstream_route(self):
        mask = np.zeros((15, 15), bool)
        mask[:, 6:9] = True
        mask[6:9, :] = True
        preferred = np.full(mask.shape, 90.0)
        preferred[:7] = 240
        surface, report = connected_surface(
            mask, preferred, np.zeros_like(mask), np.zeros_like(mask), 0
        )
        self.assertEqual(report["packed_adverse_downstream_edges"], 0)
        self.assertGreaterEqual(float(surface[:7, 6:9].min()), 240)
        self.assertLess(float(surface[:7, 6:9].max()), 241)
        self.assertLess(float(surface[14, 7]), 91)
        self.assertGreater(report["cascade_tree_edges"], 0)
        self.assertGreater(report["maximum_packed_adjacent_head_jump_m"], 100)
        self.assertTrue(np.isfinite(surface[mask]).all())
        self.assertTrue(np.isnan(surface[~mask]).all())

    def test_steep_mountain_reach_follows_terrain_instead_of_cutting_a_trench(self):
        mask = np.zeros((80, 5), bool)
        mask[:, 2] = True
        preferred = np.broadcast_to(100 + np.arange(80)[:, None] * 8.0, mask.shape)
        surface, report = connected_surface(
            mask, preferred, np.zeros_like(mask), np.zeros_like(mask), 0
        )
        np.testing.assert_array_equal(surface[mask], preferred[mask])
        self.assertEqual(report["cascade_tree_edges"], 79)
        self.assertEqual(report["packed_adverse_downstream_edges"], 0)
        repeated, repeated_report = connected_surface(
            mask, preferred, np.zeros_like(mask), np.zeros_like(mask), 0
        )
        np.testing.assert_array_equal(surface, repeated)
        self.assertEqual(report, repeated_report)

    def test_a_local_low_sample_is_raised_without_lowering_its_upstream_valley(self):
        mask = np.zeros((30, 5), bool)
        mask[:, 2] = True
        preferred = np.broadcast_to(
            100 + np.arange(30)[:, None] * 8.0, mask.shape
        ).copy()
        preferred[15, 2] = 5
        surface, report = connected_surface(
            mask, preferred, np.zeros_like(mask), np.zeros_like(mask), 0
        )
        np.testing.assert_array_equal(surface[16:, 2], preferred[16:, 2])
        self.assertGreater(surface[15, 2], surface[14, 2])
        self.assertEqual(report["packed_adverse_downstream_edges"], 0)

    def test_a_lake_is_one_level_body_not_separate_source_disks(self):
        mask = np.zeros((15, 15), bool)
        mask[:, 7] = True
        lake = np.zeros_like(mask)
        lake[5:10, 4:11] = True
        mask |= lake
        preferred = np.indices(mask.shape)[0] * 4.0 + 80
        surface, report = connected_surface(
            mask, preferred, lake, np.zeros_like(mask), 0
        )
        self.assertEqual(len(np.unique(surface[lake])), 1)
        self.assertEqual(report["level_body_components"], 1)
        self.assertEqual(report["packed_adverse_downstream_edges"], 0)

    def test_a_source_core_can_be_flat_without_flattening_its_apron_or_reach(self):
        mask = np.zeros((30, 7), bool)
        mask[:, 2:5] = True
        core = np.zeros_like(mask)
        core[12:15, 2:5] = True
        preferred = np.broadcast_to(
            100 + np.arange(30)[:, None] * 8.0, mask.shape
        ).copy()
        preferred[12, 2] = 1
        surface, report = connected_surface(
            mask, preferred, core, np.zeros_like(mask), 0
        )
        np.testing.assert_array_equal(surface[core], 204)
        np.testing.assert_array_equal(surface[15:, 2:5], preferred[15:, 2:5])
        self.assertGreater(float(surface[15, 3] - surface[14, 3]), 0)
        self.assertEqual(report["packed_adverse_downstream_edges"], 0)

    def test_ocean_is_pinned_while_its_receiving_channel_is_jointly_fitted(self):
        mask = np.zeros((15, 15), bool)
        mask[:, 7] = True
        ocean = np.zeros_like(mask)
        ocean[:4, :] = True
        mask |= ocean
        surface, report = connected_surface(
            mask, np.full(mask.shape, 70.0), ocean, ocean, 90
        )
        np.testing.assert_array_equal(surface[ocean], 90)
        self.assertGreater(surface[14, 7], 90)
        self.assertEqual(report["outlets"][0]["role"], "sea")

    def test_vertical_headroom_does_not_compress_an_unrelated_lower_reach(self):
        mask = np.zeros((100, 15), bool)
        mask[2:98, 6:9] = True
        preferred = np.full(mask.shape, 1023.0)
        preferred[2:7] = np.arange(5)[:, None] * 100 + 100
        surface, report = connected_surface(
            mask,
            preferred,
            np.zeros_like(mask),
            np.zeros_like(mask),
            0,
        )
        self.assertEqual(report["outlets"][0]["role"], "closed_component")
        self.assertLessEqual(float(surface[mask].max()), 1021)
        self.assertEqual(report["packed_adverse_downstream_edges"], 0)
        np.testing.assert_array_equal(surface[3:7, 6:9], preferred[3:7, 6:9])
        self.assertEqual(surface[2, 6], 100)
        self.assertEqual(report["minimum_vertical_compression_factor"], 1)
        self.assertGreater(report["headroom_limited_tree_edges"], 0)


if __name__ == "__main__":
    unittest.main()
