"""Behavioral checks for scoped plans, contiguous land and honest water labels."""

import copy
import unittest

import numpy as np

from start_capabilities import (
    GRID,
    PARAMETERS,
    digest,
    dry_centers,
    segment_clear,
    start_witness,
    water_witness,
)


def graph():
    xyz = [
        [-8640, 50, -500],
        [200, 50, -200],
        [240, 50, -160],
        [240, 50, -500],
        [8640, 50, -500],
    ]
    return {
        "nodes": [
            {"xyz": p, "outside": ("west" if i == 0 else "east" if i == 4 else None)}
            for i, p in enumerate(xyz)
        ],
        "edges": [
            {"a": a, "b": b, "kind": "ramp", "structure": "ground"}
            for a, b in [(0, 1), (2, 3), (3, 4)]
        ],
    }


class StartCapabilities(unittest.TestCase):
    def setUp(self):
        self.ground = np.full((GRID, GRID), 50.0, dtype=float)
        self.depth = np.zeros((GRID, GRID), dtype=float)
        self.hydro = {"start_tile": 12, "highways": graph()}

    def test_dry_plan_has_ordered_shared_junction_and_no_map_names(self):
        row = start_witness(self.ground, self.depth, self.hydro)
        self.assertTrue(row["predicted"])
        w = row["witness"]
        self.assertEqual(27, len(w["steps"]))
        self.assertEqual(["hook0", "hook1"], [s["from"] for s in w["steps"][24:26]])
        self.assertEqual(["join", "join"], [s["to"] for s in w["steps"][24:26]])
        self.assertEqual(row["witness_sha256"], digest(w))
        self.assertIsNone(row["subchecks"]["native_placement"])
        changed = {**self.hydro, "map_name": "Any name", "map_id": "ignored"}
        self.assertEqual(row, start_witness(self.ground, self.depth, changed))

    def test_road_presence_without_both_directed_outside_paths_is_negative_only_for_plan(
        self,
    ):
        h = copy.deepcopy(self.hydro)
        h["highways"]["nodes"][0]["outside"] = None
        row = start_witness(self.ground, self.depth, h)
        self.assertFalse(row["predicted"])
        self.assertEqual("not_possible_here", row["level"])
        self.assertIn("Current authored", row["scope"])

    def test_missing_graph_is_not_negative(self):
        row = start_witness(self.ground, self.depth, {"start_tile": 12})
        self.assertIsNone(row["predicted"])

    def test_through_roads_without_dangling_stubs_are_not_capability_negatives(self):
        h = copy.deepcopy(self.hydro)
        h["highways"] = {
            "nodes": [
                {"xyz": [x, 50, z], "outside": outside}
                for x, z, outside in [
                    (-8640, -100, "west"),
                    (0, -100, None),
                    (8640, -100, "east"),
                    (8640, 100, "east"),
                    (0, 100, None),
                    (-8640, 100, "west"),
                ]
            ],
            "edges": [
                {"a": a, "b": b, "kind": "highway", "structure": "ground"}
                for a, b in [(0, 1), (1, 2), (3, 4), (4, 5)]
            ],
        }
        row = start_witness(self.ground, self.depth, h)
        self.assertIsNone(row["predicted"])
        self.assertEqual("no_supported_two_stub_witness", row["reason"])

    def test_scattered_dry_samples_do_not_form_a_contiguous_footprint(self):
        self.depth[:] = 2
        self.depth[::2, ::2] = 0
        self.assertEqual([], dry_centers(self.ground, self.depth, graph(), 12))

    def test_fully_wet_search_is_unknown_not_geo_impossible(self):
        self.depth[:] = 2
        row = start_witness(self.ground, self.depth, self.hydro)
        self.assertIsNone(row["predicted"])
        self.assertEqual("unknown", row["level"])

    def test_join_length_slope_and_wet_crossing_are_screened(self):
        self.assertFalse(segment_clear(self.ground, self.depth, [0, 50, 0], [8, 50, 0]))
        self.assertFalse(
            segment_clear(self.ground, self.depth, [0, 50, 0], [96, 80, 0])
        )
        self.assertTrue(segment_clear(self.ground, self.depth, [0, 50, 0], [96, 50, 0]))
        self.depth[540, 543] = 1
        self.assertFalse(
            segment_clear(self.ground, self.depth, [0, 50, 0], [96, 50, 0])
        )

    def test_flat_wet_water_is_not_sustained_freshwater_or_downstream_proof(self):
        self.depth[:] = 2
        self.hydro["samples"] = {"test": [[x, 0, 0] for x in range(-640, 641, 16)]}
        row = water_witness(self.ground, self.depth, self.hydro)
        self.assertIsNone(row["witness"])
        self.assertIsNone(row["predicted"])
        self.assertIsNone(row["subchecks"]["clean_intake"])

    def test_initial_directed_wet_route_is_not_full_water_yes(self):
        self.depth[:] = 2
        self.ground[:] = np.linspace(60, 40, GRID)[None, :]
        self.hydro["samples"] = {"test": [[x, 0, 0] for x in range(-640, 641, 16)]}
        row = water_witness(self.ground, self.depth, self.hydro)
        self.assertIsNotNone(row["witness"])
        self.assertGreaterEqual(
            row["witness"]["along_route_separation_m"], PARAMETERS.sewage_separation_m
        )
        self.assertIsNone(row["predicted"])
        self.assertIsNone(row["subchecks"]["sustained_capacity"])


if __name__ == "__main__":
    unittest.main()
