import unittest

import numpy as np

from open_interface_authority import (
    cell_consistency,
    literal_faces,
    open_bank_witness,
    require_single_valued_cells,
)


class InterfaceTests(unittest.TestCase):
    def test_distinct_graph_nodes_cannot_write_different_values_to_same_cell(self):
        with self.assertRaises(ValueError):
            require_single_valued_cells([[2, 3], [2, 3]], [64, 65], [0, 0])
        with self.assertRaises(ValueError):
            require_single_valued_cells([[2, 3], [2, 3]], [64, 64], [0, 1])

    def test_equal_values_still_do_not_materialize_or_approve_junction(self):
        result = require_single_valued_cells([[2, 3], [2, 3]], [64, 64], [0, 0])
        self.assertTrue(result["single_valued"])
        self.assertFalse(result["materialized"])
        self.assertEqual(len(result["repeated_cells"]), 1)

    def test_complete_potential_arrays_required(self):
        with self.assertRaises(ValueError):
            cell_consistency([[1, 2]], [64], [])

    def test_only_literal_clipped_face_not_nearby_or_unclipped_endpoint(self):
        clip = {
            "start_clipped": True,
            "end_clipped": False,
            "points_xz": [[-8640, 80], [8640, 80]],
        }
        self.assertEqual(literal_faces(clip, "start"), ["west"])
        self.assertEqual(literal_faces(clip, "end"), [])
        clip["points_xz"][0] = [-8639.9, 80]
        self.assertEqual(literal_faces(clip, "start"), [])

    def test_open_face_partitions_bank_without_removing_in_square_lateral_nodes(self):
        floor = np.full((5, 5), 6400, np.int64)
        own = {(0, 2), (1, 2)}
        result = open_bank_witness((0, 2), own, floor, {"north"})
        self.assertEqual(len(result["literal_exterior_open_face_nodes_rc"]), 3)
        self.assertEqual(result["unknown_exterior_lateral_bank_nodes_rc"], [])
        self.assertEqual(result["in_square_bank_nodes_removed"], 0)
        self.assertEqual(result["conditional_in_square_lateral_stage_cap_q"], 6368)
        self.assertFalse(result["admission"])
        self.assertIsNone(result["external_boundary_stage_and_capacity"])

    def test_missing_face_keeps_every_exterior_node_unknown(self):
        floor = np.full((5, 5), 6400, np.int64)
        result = open_bank_witness((0, 2), {(0, 2)}, floor, set())
        self.assertEqual(len(result["unknown_exterior_lateral_bank_nodes_rc"]), 3)
        self.assertEqual(result["literal_exterior_open_face_nodes_rc"], [])

    def test_corner_requires_all_violated_faces_not_either_face(self):
        floor = np.full((5, 5), 6400, np.int64)
        result = open_bank_witness((0, 0), {(0, 0)}, floor, {"north"})
        self.assertIn([-1, -1], result["unknown_exterior_lateral_bank_nodes_rc"])
        self.assertIn([-1, 0], result["literal_exterior_open_face_nodes_rc"])
        both = open_bank_witness((0, 0), {(0, 0)}, floor, {"north", "west"})
        self.assertEqual(both["unknown_exterior_lateral_bank_nodes_rc"], [])


if __name__ == "__main__":
    unittest.main()
