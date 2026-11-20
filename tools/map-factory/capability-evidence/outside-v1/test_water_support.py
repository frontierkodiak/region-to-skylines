"""The bound must describe a connected edge path, not isolated deep pools."""

import unittest

import numpy as np

from water_support import edge_pairs, support


class WaterSupportTest(unittest.TestCase):
    def test_shallow_bottleneck_limits_deep_river(self):
        depth = np.zeros((1081, 1081), dtype=np.uint16)
        depth[:, 530:550] = 8 * 64
        depth[500:504, 530:550] = 4 * 64
        result = support(depth, 1)
        self.assertEqual(result["maximum_bottleneck_depth_m"], 4)
        self.assertEqual(result["deep_6m_edge_pairs"], [])
        self.assertIn(["south", "north"], edge_pairs(depth, 4 * 64, 16))

    def test_isolated_deep_pool_is_not_edge_support(self):
        depth = np.zeros((1081, 1081), dtype=np.uint16)
        depth[100:900, 100:900] = 10 * 64
        self.assertEqual(support(depth, 1)["maximum_bottleneck_depth_m"], 0)


if __name__ == "__main__":
    unittest.main()
