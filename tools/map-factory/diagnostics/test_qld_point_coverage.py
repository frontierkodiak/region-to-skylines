import unittest
import numpy as np
from qld_point_coverage import even_odd


class PointTests(unittest.TestCase):
    def test_disconnected_outer_and_hole_work_in_any_ring_order_orientation(self):
        outer = [[0, 0], [8, 0], [8, 8], [0, 8], [0, 0]]
        hole = [[2, 2], [2, 4], [4, 4], [4, 2], [2, 2]]
        island = [[10, 0], [12, 0], [12, 2], [10, 2], [10, 0]]
        p = np.array([[1, 1], [3, 3], [11, 1], [9, 1]], dtype=float)
        a, b = even_odd(p, [outer, hole, island], 0.001)
        self.assertEqual(a.tolist(), [True, False, True, False])
        self.assertFalse(b.any())
        c, _ = even_odd(p, [island[::-1], hole[::-1], outer[::-1]], 0.001)
        np.testing.assert_array_equal(a, c)

    def test_boundary_unknown_is_not_inside_or_inferred_dry(self):
        a, b = even_odd(
            np.array([[0, 1], [0.0005, 1], [0.01, 1]]),
            [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
            0.001,
        )
        self.assertEqual(a.tolist(), [False, False, True])
        self.assertEqual(b.tolist(), [True, True, False])

    def test_invalid_ring_is_not_silently_omitted(self):
        with self.assertRaises(ValueError):
            even_odd(np.array([[1.0, 1.0]]), [[[0, 0], [2, 0], [2, 2], [0, 2]]], 0.001)


if __name__ == "__main__":
    unittest.main()
