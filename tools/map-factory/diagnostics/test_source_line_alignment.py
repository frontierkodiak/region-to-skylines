import json
import unittest

import numpy as np

from source_line_alignment import (
    compare,
    lonlat,
    ordered_vertices,
    quantized_node_candidates,
    world,
)


class SourceLineAlignmentTests(unittest.TestCase):
    def test_coincident_quantized_nodes_keep_distinct_ids_and_serialize(self):
        raw = [
            ({"id": 100, "nodes": [201, 202]}, np.array([[10.1, 10.1], [11.1, 11.1]])),
            ({"id": 101, "nodes": [301, 302]}, np.array([[10.2, 10.2], [11.2, 11.2]])),
        ]
        result = quantized_node_candidates(np.array([10, 10]), raw)
        self.assertEqual({r["node"] for r in result}, {201, 301})
        self.assertEqual(json.loads(json.dumps(result)), result)

    def test_decoder_grid_roundtrip_without_fitting_any_geographic_outcome(self):
        original = np.array([[22369621, 34123125], [22369622, 34123126]], float)
        self.assertTrue(
            np.allclose(world(lonlat(original)), original, atol=1e-5, rtol=0)
        )
        with self.assertRaises(ValueError):
            world([[float("nan"), 0]])

    def test_complete_small_rounding_offset_is_consistent_not_source_identity(self):
        result = compare(
            np.array([[0, 0.1], [10, 0.1]]), np.array([[0, 0], [5, 0], [10, 0]])
        )
        self.assertTrue(result["embeddings"])
        self.assertTrue(
            any(
                e["status"] == "consistent_under_conditional_rounding_model"
                for e in result["embeddings"]
            )
        )
        self.assertNotIn("assigned_source_id", result)

    def test_complete_internal_spur_cannot_be_omitted_by_endpoint_match(self):
        result = compare(
            np.array([[0, 0], [10, 0]]), np.array([[0, 0], [5, 2], [10, 0]])
        )
        self.assertTrue(result["embeddings"])
        self.assertTrue(
            all(
                e["status"] == "incompatible_under_conditional_rounding_model"
                for e in result["embeddings"]
            )
        )

    def test_sampling_margin_is_unknown_not_a_pass_or_refinement_loop(self):
        result = compare(np.array([[0, 0.68], [10, 0.68]]), np.array([[0, 0], [10, 0]]))
        self.assertEqual(
            result["embeddings"][0]["status"], "unresolved_sampling_margin"
        )

    def test_reversed_raw_order_retains_full_ordered_chain(self):
        result = compare(
            np.array([[10, 0], [5, 0], [0, 0]]), np.array([[0, 0], [10, 0]])
        )
        self.assertTrue(result["embeddings"][0]["reverse_raw_order"])
        self.assertTrue(result["embeddings"][0]["monotone_vertex_correspondence"])

    def test_backtracking_is_not_accepted_as_a_simple_ordered_reach(self):
        self.assertFalse(
            ordered_vertices(
                np.array([[0, 0], [8, 0], [2, 0], [10, 0]]), np.array([[0, 0], [10, 0]])
            )
        )

    def test_repeated_geometry_retains_all_embeddings_not_nearest_assignment(self):
        result = compare(
            np.array([[0, 0], [10, 0]]), np.array([[0, 0], [10, 0], [0, 0], [10, 0]])
        )
        self.assertGreater(len(result["embeddings"]), 1)
        self.assertNotIn("selected_embedding", result)
