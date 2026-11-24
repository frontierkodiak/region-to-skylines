import unittest

import numpy as np

from catchment import priority_flood_drainage


class CatchmentTest(unittest.TestCase):
    def test_depression_routes_over_lowest_spill_without_editing_terrain(self):
        terrain = np.array([[3, 3, 3], [3, 0, 1], [3, 3, 3]], dtype=float)
        before = terrain.copy()
        result = priority_flood_drainage(terrain)
        np.testing.assert_array_equal(terrain, before)
        self.assertEqual(result.filled_elevation[1, 1], 1)
        self.assertEqual(result.parent[1, 1], 5)
        self.assertEqual(result.area[1, 2], 2 * 16**2)

    def test_flat_square_drains_without_cycles_and_conserves_local_area(self):
        result = priority_flood_drainage(np.zeros((7, 7)), spacing=10)
        parents = result.parent.ravel()
        for start in range(len(parents)):
            seen, node = set(), start
            while parents[node] != -1:
                self.assertNotIn(node, seen)
                seen.add(node)
                node = parents[node]
            row, col = divmod(node, 7)
            self.assertTrue(row in (0, 6) or col in (0, 6))
        self.assertEqual(result.area[result.parent == -1].sum(), 49 * 100)

    def test_unknown_terrain_or_spacing_is_not_zero_catchment(self):
        for terrain, spacing in [(np.array([[np.nan]]), 16), (np.zeros((2, 2)), 0)]:
            with self.assertRaises(ValueError):
                priority_flood_drainage(terrain, spacing)


if __name__ == "__main__":
    unittest.main()
