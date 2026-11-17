"""Flood diagnostics preserve the original gate and complete trace coverage."""

import unittest

import numpy as np

from cs1_harness.flood_region import close_region, components, flood_mask, storage_budget


class FloodRegionTests(unittest.TestCase):
    def test_original_strict_depth_and_euclidean_distance_boundaries(self):
        ref = np.zeros((1081, 1081), np.uint16)
        ref[500, 500] = 64
        depth = np.zeros_like(ref)
        depth[500, 508] = 100  # Exactly 128m away: not distant flooding.
        depth[500, 509] = 32  # Exactly .5m: not above the depth threshold.
        depth[501, 509] = 33
        mask = flood_mask(depth, ref, np.zeros_like(ref, bool))
        self.assertEqual(np.argwhere(mask).tolist(), [[501, 509]])

    def test_component_order_is_stable_and_diagonals_connect(self):
        mask = np.zeros((1081, 1081), bool)
        mask[1, 1] = mask[2, 2] = mask[10, 10] = True
        self.assertEqual(components(mask), [[(1, 1), (2, 2)], [(10, 10)]])

    def test_source_closure_keeps_complete_footprints_and_fails_on_bounds(self):
        control = {"type": 1, "input": [0, 0, 0], "output": [32, 0, 0], "input_rate": 224, "output_rate": 224}
        nodes, sources = close_region([(540, 540)], [control])
        self.assertEqual(sources, [1])
        self.assertIn([32, 0], nodes)
        self.assertIn([48, 16], nodes)
        with self.assertRaisesRegex(ValueError, "bounds"):
            close_region([(540, 540)], [control], max_nodes=1)

    def test_budget_counts_storage_and_both_source_directions_without_gains_hiding_losses(self):
        def cells(a):
            return [v for depth in a for v in [depth, 0, 0, 0]]

        source = {"id": 7, "pre_cells": cells([13, 5]), "input_cells": cells([11, 5]), "post_cells": cells([16, 6])}
        row = {
            "published": cells([10, 5]),
            "transport": cells([13, 5]),
            "published_end": cells([16, 6]),
            "working_buffer": 0,
            "published_buffer": 0,
            "sources": [source],
        }
        report = storage_budget({"nodes": [[0, 0], [16, 0]]}, [row])
        self.assertTrue(report["closes"])
        self.assertEqual(report["source_input"], 2)
        self.assertEqual(report["source_output"], 6)
        self.assertEqual(report["net_transport_in"], 3)
        self.assertEqual(report["final"], 22)


if __name__ == "__main__":
    unittest.main()
