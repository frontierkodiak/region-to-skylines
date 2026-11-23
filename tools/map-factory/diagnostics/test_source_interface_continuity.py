"""Observable distinctions between source-graph models and hydraulic claims."""

import unittest

from source_interface_continuity import (
    adjacent,
    induced_counts,
    native_cell,
    path_state,
    source_domain,
    surface_state,
)


class SourceInterfaceContinuityTests(unittest.TestCase):
    def test_source_native_corners_and_no_wrap(self):
        self.assertEqual(native_cell([0, 0]), 1080 * 1081)
        self.assertEqual(native_cell([1080, 1080]), 1080)
        self.assertFalse(adjacent(1080, 1081, 8))
        with self.assertRaises(ValueError):
            native_cell([-1, 0])

    def test_single_shared_cell_is_tautology_not_communication(self):
        self.assertEqual(
            surface_state([5760], [1])["state"], "one_cell_equality_tautology"
        )
        self.assertEqual(
            surface_state([5760, 5760], [1, 1])["state"], "all_wet_equal_q"
        )

    def test_dry_unknown_and_distinct_surfaces_are_separate(self):
        self.assertEqual(surface_state([], [])["state"], "no_support_unknown")
        self.assertIsNone(surface_state([-1], [0])["head_min_q"])
        self.assertEqual(
            surface_state([-1, 6000], [0, 1])["state"], "mixed_dry_and_wet"
        )
        self.assertEqual(surface_state([5760, 5761], [7, 7])["spread_q"], 1)
        with self.assertRaises(ValueError):
            surface_state([80], [0])

    def test_wet_gradient_is_continuous_not_constant_or_flow(self):
        a = path_state([0, 1, 2], [5800, 5799, 5801], [7, 7, 7], 7)
        self.assertTrue(a["complete_digital_path"]["4"])
        self.assertTrue(a["has_increase"] and a["has_decrease"])
        self.assertEqual(a["adjacent_wet_signed_head_delta_q"], [-1, 2])

    def test_dry_gap_and_threshold_not_global_disconnection(self):
        a = path_state([0, 1, 2], [5800, -1, 5801], [7, 0, 7], 1)
        self.assertFalse(a["complete_digital_path"]["8"])
        self.assertEqual(a["adjacent_wet_signed_head_delta_q"], [])
        self.assertTrue(a["not_flow_direction_or_full_square_disconnection"])
        self.assertTrue(path_state([0], [5800], [6], 1)["complete_digital_path"]["8"])
        self.assertFalse(path_state([0], [5800], [6], 7)["complete_digital_path"]["8"])

    def test_diagonal_and_jump_are_not_invented_edges(self):
        a = path_state([0, 1082], [5800, 5800], [7, 7], 1)
        self.assertFalse(a["complete_digital_path"]["4"])
        self.assertTrue(a["complete_digital_path"]["8"])
        b = induced_counts([0, 2], [[0, 1]], [], [[0, 1]], [True, True], 8)
        self.assertEqual(b[0]["wet_induced_components"], 2)

    def test_raster_collision_does_not_join_distinct_source_nodes(self):
        a = induced_counts(
            [0, 1, 1, 2], [[0, 1], [2, 3]], [], [[0, 1, 2, 3]], [True] * 4, 8
        )
        self.assertEqual(a[0]["wet_induced_components"], 2)
        b = induced_counts(
            [0, 1, 1, 2], [[0, 1], [2, 3]], [[1, 2]], [[0, 1, 2, 3]], [True] * 4, 8
        )
        self.assertEqual(b[0]["wet_induced_components"], 1)

    def test_excluded_part_and_unknown_site_remain_in_domain(self):
        t = {
            "clips": {
                "a": {"nodes_rc": [[0, 0]], "source_scope": "perennial_surface"},
                "b": {"nodes_rc": [[2, 0]], "source_scope": "excluded"},
            },
            "eligible_clip_ids": ["a"],
            "nodes": [{"node_rc": [0, 0]}],
            "walks": {"a": [0]},
            "literal_source_junctions": [],
            "components": [[0]],
        }
        d = source_domain(
            {
                "case": "x",
                "complete_source_topology": t,
                "all_boundary_sites": [{"id": "unknown"}],
            }
        )
        self.assertEqual(len(d["clips"]), 2)
        self.assertFalse(d["clips"][1]["eligible"])
        self.assertEqual(d["all_sites"], [{"id": "unknown"}])
        self.assertEqual(len(d["native_cells"]), 2)


if __name__ == "__main__":
    unittest.main()
