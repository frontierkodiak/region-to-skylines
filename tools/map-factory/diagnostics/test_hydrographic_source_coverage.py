import unittest
import numpy as np
from hydrographic_source_coverage import coverage, verify_derived_layer


class CoverageTests(unittest.TestCase):
    def test_modified_derived_geometry_with_same_ids_is_rejected(self):
        original = {
            "attributes": {"OBJECTID": 1},
            "geometry": {"rings": [[[0, 0], [1, 0], [0, 1]]]},
        }
        changed = {
            "attributes": {"OBJECTID": 1},
            "geometry": {"rings": [[[0, 0], [9, 0], [0, 1]]]},
        }
        with self.assertRaises(ValueError):
            verify_derived_layer(
                {"objectIds": [1], "features": [changed]}, [1], [[original]]
            )
        verify_derived_layer(
            {"objectIds": [1], "features": [original]}, [1], [[original]]
        )

    def test_all_bodies_and_repeated_source_occurrences_retained_not_pooled(self):
        a = np.zeros((5, 5), bool)
        a[2, 2] = True
        b = np.zeros_like(a)
        result = coverage([[2, 2], [3, 3], [2, 2]], {"a": a, "empty": b})
        self.assertEqual(result["walk_occurrences"], 3)
        self.assertEqual(result["unique_nodes"], 2)
        self.assertEqual(result["covered_occurrences"], 2)
        self.assertEqual(
            result["per_external_body_occurrence_indices"], {"a": [0, 2], "empty": []}
        )
        self.assertIsNone(result["source_piece_identity_or_hydraulic_bank_authority"])

    def test_multiple_covering_polygons_stay_ambiguous_not_one_selected_match(self):
        a = np.ones((5, 5), bool)
        result = coverage([[2, 2]], {"a": a, "b": a.copy()})
        self.assertEqual(
            result["per_external_body_occurrence_indices"], {"a": [0], "b": [0]}
        )
        self.assertEqual(result["covered_occurrences"], 1)


if __name__ == "__main__":
    unittest.main()
