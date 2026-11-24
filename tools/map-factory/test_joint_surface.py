import unittest

import numpy as np

from joint_surface import connected_surface


class JointSurfaceTests(unittest.TestCase):
    def test_touching_reaches_do_not_keep_independent_incompatible_heads(self):
        mask = np.zeros((15, 15), bool)
        mask[:, 6:9] = True
        mask[6:9, :] = True
        preferred = np.full(mask.shape, 90.0)
        preferred[:7] = 240
        surface, report = connected_surface(
            mask, preferred, np.zeros_like(mask), np.zeros_like(mask), 0
        )
        self.assertEqual(report["packed_adverse_downstream_edges"], 0)
        self.assertLessEqual(report["maximum_packed_adjacent_head_jump_m"], 0.5)
        self.assertTrue(np.isfinite(surface[mask]).all())
        self.assertTrue(np.isnan(surface[~mask]).all())

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

    def test_closed_water_is_named_and_vertical_fit_does_not_make_a_seam(self):
        mask = np.zeros((15, 15), bool)
        mask[2:13, 6:9] = True
        surface, report = connected_surface(
            mask,
            np.full(mask.shape, 1023.0),
            np.zeros_like(mask),
            np.zeros_like(mask),
            0,
        )
        self.assertEqual(report["outlets"][0]["role"], "closed_component")
        self.assertLessEqual(float(surface[mask].max()), 1021)
        self.assertEqual(report["packed_adverse_downstream_edges"], 0)
        self.assertLessEqual(report["maximum_packed_adjacent_head_jump_m"], 0.5)


if __name__ == "__main__":
    unittest.main()
