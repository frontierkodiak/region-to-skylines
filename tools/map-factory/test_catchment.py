"""Drainage behavior independent of native-game water simulation."""

import unittest

import numpy as np

from catchment import local_catchment_area, priority_flood_drainage


class CatchmentTests(unittest.TestCase):
    def assert_drainage_forest(self, result, spacing):
        rows, cols = result.area.shape
        parents = result.parent.ravel()
        ranks = np.empty(parents.size, dtype=np.int64)
        np.testing.assert_array_equal(np.sort(result.order), np.arange(parents.size))
        ranks[result.order] = np.arange(parents.size)
        roots = parents == -1
        expected_roots = np.zeros((rows, cols), dtype=bool)
        expected_roots[[0, -1], :] = True
        expected_roots[:, [0, -1]] = True
        np.testing.assert_array_equal(roots.reshape(rows, cols), expected_roots)
        children = np.flatnonzero(~roots)
        self.assertTrue(np.all(ranks[parents[children]] < ranks[children]))
        self.assertTrue(np.all(result.area >= spacing**2))
        self.assertAlmostEqual(
            result.area.ravel()[roots].sum(), parents.size * spacing**2
        )
        for index in children:
            row, col = divmod(int(index), cols)
            pr, pc = divmod(int(parents[index]), cols)
            self.assertLessEqual(max(abs(row - pr), abs(col - pc)), 1)
            self.assertLessEqual(
                result.filled_elevation[pr, pc], result.filled_elevation[row, col]
            )
        # An independent subtree count verifies accumulation, not only root sum.
        counts = np.ones(parents.size)
        for index in range(parents.size):
            parent = parents[index]
            while parent != -1:
                counts[parent] += 1
                parent = parents[parent]
        np.testing.assert_array_equal(result.area.ravel(), counts * spacing**2)

    def test_monotone_plane_preserves_surface_and_conserves_boundary_area(self):
        ground = np.add.outer(np.arange(8.0), np.arange(11.0))
        original = ground.copy()
        result = priority_flood_drainage(ground, spacing=3)
        self.assert_drainage_forest(result, 3)
        np.testing.assert_array_equal(result.filled_elevation, original)
        np.testing.assert_array_equal(ground, original)
        self.assertGreater(result.area.max(), 9)
        np.testing.assert_array_equal(local_catchment_area(ground, 3), result.area)

    def test_closed_depression_fills_to_spill_and_drains_without_terrain_edit(self):
        ground = np.full((7, 7), 10.0)
        ground[1:-1, 1:-1] = 1
        ground[0, 3] = 4
        original = ground.copy()
        ground.flags.writeable = False
        result = priority_flood_drainage(ground)
        self.assert_drainage_forest(result, 16)
        np.testing.assert_array_equal(result.filled_elevation[1:-1, 1:-1], 4)
        self.assertEqual(result.area[0, 3], 26 * 256)
        np.testing.assert_array_equal(ground, original)
        self.assertFalse(np.shares_memory(result.filled_elevation, ground))

    def test_flat_grid_is_deterministic_and_acyclic(self):
        ground = np.zeros((13, 9))
        first = priority_flood_drainage(ground, 2)
        second = priority_flood_drainage(ground, 2)
        self.assert_drainage_forest(first, 2)
        for name in ("area", "filled_elevation", "parent", "order"):
            np.testing.assert_array_equal(getattr(first, name), getattr(second, name))

    def test_single_row_column_and_cell_are_all_outlets(self):
        for shape in ((1, 7), (6, 1), (1, 1)):
            with self.subTest(shape=shape):
                result = priority_flood_drainage(np.ones(shape), 2)
                self.assert_drainage_forest(result, 2)
                np.testing.assert_array_equal(result.area, 4)

    def test_invalid_grids_are_rejected(self):
        for ground in (
            [],
            [1, 2],
            np.zeros((2, 0)),
            np.zeros((2, 2, 2)),
            [[0, np.nan]],
            [[0, np.inf]],
            [[1j]],
            [["bad"]],
        ):
            with self.subTest(ground=ground), self.assertRaises(ValueError):
                local_catchment_area(ground)

    def test_invalid_spacing_is_rejected(self):
        for spacing in (0, -16, np.nan, np.inf, -np.inf, 1e300, None, "bad"):
            with self.subTest(spacing=spacing), self.assertRaises(ValueError):
                local_catchment_area(np.zeros((3, 3)), spacing)


if __name__ == "__main__":
    unittest.main()
