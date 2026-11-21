import unittest

import numpy as np

from coastal_corridor_profiles import path_summary


class ProfileTests(unittest.TestCase):
    def test_dry_bed_difference_does_not_become_water_surface_gradient(self):
        row = path_summary(
            np.array([64, 128, 640]),
            np.array([64, 64, 0]),
            np.array([-2.0, np.nan, np.nan]),
        )
        self.assertEqual(row["wet_pairs"], 1)
        self.assertEqual(row["maximum_wet_pair_head_rise_toward_edge_m"], 1)
        self.assertEqual(row["velocity_times_head_difference_negative"], 1)

    def test_missing_velocity_and_dry_pairs_remain_unknown(self):
        row = path_summary(
            np.array([64, 128]), np.array([0, 0]), np.array([np.nan, np.nan])
        )
        self.assertIsNone(row["maximum_wet_pair_head_rise_toward_edge_m"])
        self.assertEqual(row["API_velocity_nodes"], 0)
        self.assertEqual(row["wet_pairs_with_velocity"], 0)


if __name__ == "__main__":
    unittest.main()
