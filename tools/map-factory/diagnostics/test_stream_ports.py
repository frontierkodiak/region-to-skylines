import json
import unittest

import numpy as np

from stream_ports import ROOT, graph_profile, review_basis
from synthetic_source_response import channel
from waterway_pieces import catalog


class StreamPortRecipeTests(unittest.TestCase):
    def test_results_basis_binds_actual_receipt_schema_issue_and_physical_protocol(
        self,
    ):
        receipt = {
            "status": "pass",
            "review_issue": {"id": "01a1ffaf-049d-7aa3-9e93-21b1c11725fd"},
            "tested_bytes": {
                "protocol_sha256": "0d35d0ba72b36ab7b85a100c118b360d6b74b66163ee346e1f9de2ac93211abc"
            },
        }
        review_basis(receipt)
        receipt["tested_bytes"]["protocol_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "exact independent"):
            review_basis(receipt)

    @classmethod
    def setUpClass(cls):
        cls.layout = json.loads((ROOT / "templates/native-corridors.json").read_text())
        cls.geometry, cls.hydro, cls.floor, cls.water, cls.old = channel(cls.layout)
        cls.clips = [
            c
            for r in catalog(cls.geometry)["rows"]
            if r["field"] == "streams"
            for c in r["clips"]
        ]
        cls.nodes = sorted({tuple(n) for c in cls.clips for n in c["nodes_rc"]})
        local = {n: i for i, n in enumerate(cls.nodes)}
        cls.edges = [
            (local[tuple(a)], local[tuple(b)])
            for c in cls.clips
            for a, b in zip(c["nodes_rc"], c["nodes_rc"][1:])
        ]

    def test_generic_rule_reproduces_the_native_tested_synthetic_geometry_and_ports(
        self,
    ):
        result = graph_profile(
            self.nodes,
            self.edges,
            np.full_like(self.floor, 6400),
            np.zeros_like(self.water),
        )
        self.assertEqual(result["status"], "feasible")
        old = {tuple(p["node_rc"]): p for p in self.old["nodes"]}
        for n, stage, bed in zip(self.nodes, result["target_q"], result["bed_q"]):
            self.assertEqual((stage, bed), (old[n]["stage_q"], old[n]["bed_q"]))
        self.assertEqual(len(result["controls"]), 3)
        self.assertEqual(
            [c["position"][::2] for c in result["controls"]], self.old["port_xz"]
        )
        self.assertEqual(
            [c["intake_rate"] for c in result["controls"]], [128, 128, 128]
        )
        self.assertEqual([c["output_rate"] for c in result["controls"]], [32, 32, 0])
        self.assertEqual(
            [c["target_fixed"] for c in result["controls"]], [6368, 6368, 6336]
        )
        self.assertEqual(
            set(map(tuple, result["full_rim_rc"])), set(map(tuple, self.old["rim_rc"]))
        )

    def test_every_branch_head_and_terminal_has_exactly_one_port_not_each_node(self):
        nodes = [(540, 540), (540, 541), (539, 540), (540, 539), (541, 540)]
        edges = [(1, 0), (2, 0), (0, 3), (0, 4)]
        result = graph_profile(
            nodes,
            edges,
            np.full((1081, 1081), 6400, np.uint16),
            np.zeros((1081, 1081), np.uint16),
        )
        self.assertEqual(result["status"], "feasible")
        self.assertEqual(set(result["heads"]), {1, 2})
        self.assertEqual(set(result["terminals"]), {3, 4})
        self.assertEqual({c["node_index"] for c in result["controls"]}, {1, 2, 3, 4})
        self.assertTrue(
            all(
                c["source_radius_model_m"] < 16
                and c["minimum_static_source_depth_m"] >= 1.5
                for c in result["controls"]
            )
        )

    def test_local_bank_conflict_remains_a_refusal_not_a_deeper_cut(self):
        floor = np.full((1081, 1081), 6400, np.uint16)
        floor[540, 540] = 6800
        result = graph_profile(
            [(540, 540), (540, 541)], [(0, 1)], floor, np.zeros_like(floor)
        )
        self.assertEqual(result["status"], "infeasible_bounds")
        self.assertIsNone(result["controls"])
        self.assertTrue(result["witnesses"])

    def test_cycle_singleton_and_missing_full_bank_stay_unresolved(self):
        floor = np.full((1081, 1081), 6400, np.uint16)
        water = np.zeros_like(floor)
        for nodes, edges, expected in [
            ([(540, 540)], [], "unresolved_isolated_stream"),
            (
                [(540, 540), (540, 541), (541, 540)],
                [(0, 1), (1, 2), (2, 0)],
                "unresolved_cycle",
            ),
            ([(0, 540), (1, 540)], [(0, 1)], "unresolved_exterior_bank"),
        ]:
            result = graph_profile(nodes, edges, floor, water)
            self.assertEqual(result["status"], expected)
            self.assertIsNone(result["controls"])

    def test_existing_depth_is_not_erased_and_skipped_cells_rejected(self):
        floor = np.full((1081, 1081), 6400, np.uint16)
        water = np.zeros_like(floor)
        water[540, 540] = 128
        result = graph_profile([(540, 540), (540, 541)], [(0, 1)], floor, water)
        self.assertEqual(result["status"], "feasible")
        self.assertGreaterEqual(result["target_q"][0] - result["bed_q"][0], 128)
        with self.assertRaisesRegex(ValueError, "skips"):
            graph_profile([(540, 540), (540, 542)], [(0, 1)], floor, water)
