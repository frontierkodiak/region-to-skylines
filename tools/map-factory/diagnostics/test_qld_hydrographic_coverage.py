import copy
import unittest
import numpy as np
from qld_hydrographic_coverage import coverage, verify_derived_layer


class QldCoverageTests(unittest.TestCase):
    def test_all_occurrences_and_overlapping_classified_bodies_retained(self):
        a = np.zeros((4, 4), dtype=bool)
        a[1, 1] = True
        b = a.copy()
        b[2, 2] = True
        j = coverage(
            [[1, 1], [1, 1], [2, 2], [3, 3]], {"perennial": a, "intermittent": b}
        )
        self.assertEqual(j["walk_occurrences"], 4)
        self.assertEqual(j["covered_occurrences"], 3)
        self.assertEqual(j["per_external_body_occurrence_indices"]["perennial"], [0, 1])
        self.assertEqual(
            j["per_external_body_occurrence_indices"]["intermittent"], [0, 1, 2]
        )
        self.assertIsNone(j["source_piece_identity_or_hydraulic_bank_authority"])

    def test_derived_geometry_change_with_same_ids_is_rejected(self):
        f = {
            "attributes": {"objectid": 1, "perenniality": "Intermittent"},
            "geometry": {"rings": [[[0, 0], [1, 0], [0, 0]]]},
        }
        data = {"objectIds": [1], "objectIdField": "objectid", "features": [f]}
        verify_derived_layer(data, [1], [[f]])
        bad = copy.deepcopy(data)
        bad["features"][0]["geometry"]["rings"][0][1] = [2, 0]
        with self.assertRaises(ValueError):
            verify_derived_layer(bad, [1], [[f]])


if __name__ == "__main__":
    unittest.main()
