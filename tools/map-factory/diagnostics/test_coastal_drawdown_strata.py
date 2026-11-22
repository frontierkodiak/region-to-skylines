import unittest

import numpy as np

from coastal_drawdown_strata import (
    classes,
    interval_metrics,
    near_far_comparison,
    quantiles,
)


class DrawdownTests(unittest.TestCase):
    def test_every_vertex_has_one_stratum_including_empty_or_dry_domains(self):
        floor = np.array([[0.0, 8, 10], [12, 20, 90]])
        distance = np.array([[0, 128, 512], [2048, 3000, 0]])
        ids = classes(distance, distance, floor, np.zeros_like(floor, bool), 10)
        self.assertEqual(ids.size, sum(np.count_nonzero(ids == i) for i in range(128)))
        self.assertEqual(ids[0, 1] % 4, 1)
        self.assertEqual(ids[0, 2] % 4, 2)
        self.assertEqual(ids[1, 0] % 4, 3)

    def test_drying_is_retained_as_storage_change_not_zero_surface_slope(self):
        initial = np.array([[64, 64]], dtype=np.uint16)
        final = np.array([[0, 32]], dtype=np.uint16)
        result = interval_metrics(np.ones_like(initial, bool), initial, final, 1)
        self.assertEqual(result["all_vertices"], 2)
        self.assertEqual(result["paired_wet_head_change_m_per_game_min"]["count"], 1)
        self.assertEqual(result["unobserved_paired_head_vertices"], 1)
        self.assertEqual(result["net_depth_change_q"], -96)

    def test_missing_common_support_is_unknown_not_zero_causal_effect(self):
        result = near_far_comparison({"all_vertices": 0}, {"all_vertices": 20})
        self.assertIsNone(result["median_difference_m_per_game_min"])

    def test_empty_strata_keep_null_quantiles(self):
        self.assertEqual(quantiles([])["count"], 0)
        self.assertIsNone(quantiles([])["median"])


if __name__ == "__main__":
    unittest.main()
