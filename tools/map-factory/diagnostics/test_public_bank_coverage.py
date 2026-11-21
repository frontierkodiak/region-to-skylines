import unittest

import numpy as np

from public_bank_coverage import coverage, polygon, rings


def points(coords):
    return [{"lon": x, "lat": y} for x, y in coords]


class PublicPolygonTests(unittest.TestCase):
    def test_literal_reversed_parts_form_ring_but_proximity_does_not(self):
        result = rings(
            [points([(0, 0), (2, 0)]), points([(0, 0), (0, 2), (2, 2), (2, 0)])]
        )
        self.assertEqual(len(result), 1)
        with self.assertRaisesRegex(ValueError, "Unclosed"):
            rings(
                [
                    points([(0, 0), (2, 0)]),
                    points([(0, 0), (0, 2), (2, 2), (2.00001, 0)]),
                ]
            )

    def test_holes_and_boundary_uncertainty_are_not_interior_evidence(self):
        outer = [np.array([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])]
        inner = [np.array([(4, 4), (6, 4), (6, 6), (4, 6), (4, 4)])]
        hit, boundary = coverage(
            np.array([(2, 2), (5, 5), (4, 5), (10.0005, 5), (11, 11)]), outer, inner
        )
        self.assertEqual(hit.tolist(), [True, False, False, False, False])
        self.assertEqual(boundary.tolist(), [False, False, True, True, False])

    def test_unclosed_way_and_unsupported_relation_stay_unresolved(self):
        with self.assertRaisesRegex(ValueError, "not a closed"):
            polygon(
                {"type": "way", "nodes": [1, 2], "geometry": points([(0, 0), (1, 1)])}
            )
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            polygon({"type": "relation", "tags": {"type": "waterway"}})
