import unittest
import numpy as np
from open_face_operations import open_profile, open_bank_clearance


def fixture(clipped=True):
    nodes = [[1, 0], [1, 1]]
    topology = {
        "nodes": [{"node_rc": n, "source_aliases": [["a", *n]]} for n in nodes],
        "clips": {
            "a": {
                "nodes_rc": nodes,
                "points_xz": [[-8640, 8624], [-8624, 8624]],
                "start_clipped": clipped,
                "end_clipped": False,
            }
        },
    }
    component = {
        "graph_node_ids": [0, 1],
        "source_edges": [[0, 1]],
        "conditional_variable_stage_plan": {
            "status": "unresolved_open_port_lateral_or_exterior_bank",
            "target_q": None,
        },
    }
    floor = np.full((4, 4), 6400, dtype=np.int64)
    water = np.zeros_like(floor)
    return topology, component, floor, water


class FaceTests(unittest.TestCase):
    def test_literal_exterior_port_retains_every_in_square_bank(self):
        t, c, f, w = fixture()
        p = open_profile(t, c, f, w)
        self.assertEqual(p["status"], "feasible")
        self.assertEqual(p["in_square_bank_nodes_removed"], 0)
        self.assertIsNone(p["external_stage_and_capacity"])
        self.assertEqual(p["target_q"], [6368, 6368])
        b = open_bank_clearance(t, c, p["target_q"], f, f)
        self.assertTrue(b["serialized_freeboard_half_metre"])
        self.assertTrue(b["per_node"][0]["literal_exterior_open_face_nodes_rc"])

    def test_rounded_unclipped_endpoint_is_not_an_open_face(self):
        t, c, f, w = fixture(False)
        self.assertEqual(
            open_profile(t, c, f, w)["status"],
            "unresolved_exterior_or_lateral_bank_no_literal_port",
        )

    def test_open_port_does_not_remove_low_lateral_bank_bound(self):
        t, c, f, w = fixture()
        f[0, 1] = 6000
        self.assertEqual(open_profile(t, c, f, w)["status"], "infeasible_bounds")

    def test_other_status_not_resolved_again(self):
        t, c, f, w = fixture()
        c["conditional_variable_stage_plan"] = {
            "status": "infeasible_bounds",
            "target_q": None,
        }
        self.assertTrue(open_profile(t, c, f, w)["old_profile_reused_without_resolve"])


if __name__ == "__main__":
    unittest.main()
