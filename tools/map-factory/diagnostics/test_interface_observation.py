"""Source-complete diagnostic sampling, without hydraulic inference."""

import unittest

import numpy as np

from interface_observation import (
    api_row,
    cohort,
    exact_query_node,
    north_cell,
    projected_points,
    sample_location,
    summarize_heads,
    wet_heads,
)


class InterfaceObservationTests(unittest.TestCase):
    def test_all_corners_and_opposite_row_orders(self):
        for north_rc, xz, native_rc in [
            ([0, 0], [-8640, 8640], [1080, 0]),
            ([1080, 0], [-8640, -8640], [0, 0]),
            ([0, 1080], [8640, 8640], [1080, 1080]),
            ([1080, 1080], [8640, -8640], [0, 1080]),
        ]:
            self.assertEqual(north_cell(north_rc), xz)
            self.assertEqual(sample_location(xz)["native_rc"], native_rc)

    def test_no_clamping_no_hidden_source_movement(self):
        self.assertIsNone(sample_location([8640.01, 0])["native_node"])
        a = sample_location([8, 8])
        self.assertEqual(a["source_xz"], [8, 8])
        self.assertEqual(a["sample_xz"], [0, 0])
        self.assertGreater(a["source_to_sample_m"], 0)
        self.assertIsNone(exact_query_node({"x": 0.002, "z": 0}))

    def test_dry_floor_is_not_observed_surface_and_sum_does_not_wrap(self):
        h = wet_heads(
            np.array([60000, 60, 60], dtype=np.uint16),
            np.array([6000, 0, 1], dtype=np.uint16),
        )
        self.assertEqual(h.tolist(), [66000, -1, 61])
        a = summarize_heads(np.array([-1, -1]), np.array([0, 0]), 5760)
        self.assertIsNone(a["observed_head_q_min"])
        self.assertIsNone(a["wet_heads_all_equal_reference"])

    def test_positive_depth_and_gt_point1m_are_distinct(self):
        a = summarize_heads(
            np.array([5760, 5760, 5759, -1]), np.array([1, 6, 7, 0]), 5760
        )
        self.assertEqual(a["positive_depth_samples"], 3)
        self.assertEqual(a["depth_ge7q_samples"], 1)
        self.assertEqual(a["nonreference_wet_samples"], 1)

    def test_missing_vectors_are_nan_not_zero(self):
        a = api_row({"ground": 1, "surface": 1, "depth": 0, "wet": False})
        self.assertTrue(np.isnan(a[3:6]).all())
        self.assertEqual(a[7], 0)

    def test_all_aliases_sites_and_no_geometry_domains_retained(self):
        clips = {
            "a": {"points_xz": [[0, 0], [16, 0]]},
            "b": {"points_xz": [[0, 0], [16, 0]]},
        }
        b = {
            "complete_source_topology": {
                "clips": clips,
                "literal_source_junctions": [],
            },
            "all_boundary_sites": [],
        }
        for ident, kind, raw, participants in [
            (
                "ep",
                "endpoint",
                {"point_xz": [0, 0], "literal_outside_faces": []},
                ["a"],
            ),
            (
                "line",
                "line",
                {
                    "a_clip": "a",
                    "b_clip": "b",
                    "shared_native_nodes_rc": [[540, 540]],
                    "projected_1um_incidence": [
                        {
                            "kind": "overlap",
                            "endpoints_xz_micro": [[0, 0], [16000000, 0]],
                        }
                    ],
                },
                ["a", "b"],
            ),
            ("body", "body-domain", {}, ["lakes:0"]),
            ("authored", "authored-plan-domain", {}, ["authored:sources:0"]),
        ]:
            b["all_boundary_sites"].append(
                {
                    "id": ident,
                    "kind": kind,
                    "original_source_record": raw,
                    "participants": participants,
                    "original_source_record_sha256": ident,
                    "active_potential_interface_or_endpoint": True,
                }
            )
        j = {
            "contracts": [
                {
                    "entry_id": "lakes:0",
                    "contract": {"id": "lake"},
                    "points": [{"point_xz": [0, 16], "point_f32_xz": [0, 16]}],
                }
            ]
        }
        probes = {
            "points": [
                {"name": "alias0", "x": 0, "z": 0},
                {"name": "alias1", "x": 0, "z": 0},
                {"name": "offgrid", "x": 0.002, "z": 0},
            ]
        }
        c = cohort(b, j, probes)
        self.assertEqual(
            [s["site_id"] for s in c["sites"]], ["ep", "line", "body", "authored"]
        )
        self.assertEqual([q["original_query_index"] for q in c["api_queries"]], [0, 1])
        self.assertEqual(c["sites"][-1]["native_nodes"], [])
        self.assertEqual(len(c["native_nodes"]), 3)
        self.assertEqual(c["new_native_queries"], 0)

    def test_unknown_projection_and_invalid_coordinates_fail_closed(self):
        with self.assertRaises(ValueError):
            projected_points({"kind": "unknown"})
        with self.assertRaises(ValueError):
            sample_location([float("nan"), 0])
        with self.assertRaises(ValueError):
            north_cell([-1, 0])


if __name__ == "__main__":
    unittest.main()
