import unittest

import numpy as np

from waterway_incidence import (
    in_polygon,
    intersections,
    micro,
    minimum_distance,
    segment_incidence,
)


class IncidenceTests(unittest.TestCase):
    def test_nonvertex_crossing_has_exact_rational_projected_witness(self):
        result = segment_incidence([0, 0], [3, 3], [0, 2], [3, 0])
        self.assertEqual(result["xz_micro_rational"], [[6, 5], [6, 5]])
        self.assertEqual(result["kind"], "point")

    def test_overlap_and_singleton_are_not_lost_or_rounded_to_endpoints(self):
        self.assertEqual(
            segment_incidence([0, 0], [10, 0], [3, 0], [8, 0]),
            {"kind": "overlap", "endpoints_xz_micro": [[3, 0], [8, 0]]},
        )
        self.assertEqual(
            segment_incidence([4, 0], [4, 0], [0, 0], [8, 0])["kind"], "point"
        )
        self.assertIsNone(segment_incidence([4, 1], [4, 1], [0, 0], [8, 0]))

    def test_large_coordinates_do_not_overflow_native_integer_products(self):
        q = 8_000_000_000
        result = segment_incidence([-q, -q], [q, q], [-q, q], [q, -q])
        self.assertEqual(result["xz_micro_rational"], [[0, 1], [0, 1]])

    def test_polygon_holes_and_boundaries_remain_distinct(self):
        rings = [
            micro([[0, 0], [10, 0], [10, 10], [0, 10]]),
            micro([[4, 4], [6, 4], [6, 6], [4, 6]]),
        ]
        self.assertEqual(in_polygon(micro([[1, 1]])[0], rings), "inside")
        self.assertEqual(in_polygon(micro([[5, 5]])[0], rings), "outside")
        self.assertEqual(in_polygon(micro([[4, 5]])[0], rings), "boundary")

    def test_all_segment_incidence_and_full_polyline_distance(self):
        a, b = micro([[0, 0], [10, 0]]), micro([[5, -5], [5, 5]])
        hits = intersections(a, b)
        self.assertEqual(hits[0]["xz_m"], [5, 0])
        self.assertAlmostEqual(minimum_distance(a, micro([[0, 3], [10, 3]])), 3)
        with self.assertRaises(ValueError):
            micro(np.array([[float("nan"), 0]]))
