import copy
import itertools
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from natural_storage_candidate import write
from natural_water_inventory import compile_natural_inventory
from stream_construction import assess, greatest_profile, preflight, sha, stage
from test_maintained_water_inventory import line
from test_waterway_pieces import geometry


def fixture():
    g = geometry([line((0, 0), (64, 0)), line((32, 32), (32, 0))])
    floor = np.full((1081, 1081), 6400, np.int64)
    floor[540, 540], floor[540, 542], floor[538, 542] = 6404, 6402, 6404
    hydro = {
        "sources": [],
        "rivers": [],
        "unmodeled_short_surface_reaches": [],
        "start_area": {"landing": [-8000, -8000]},
        "node_positions": {},
    }
    return g, hydro, floor, np.zeros_like(floor), {"routes": []}


class StreamGeometryTests(unittest.TestCase):
    def test_dag_solver_matches_exhaustive_feasibility_and_greatest_stages(self):
        rng = np.random.default_rng(42)
        edges = [(0, 1), (0, 2), (1, 3), (2, 3)]
        for _ in range(30):
            lo, hi = rng.integers(0, 4, (2, 4))
            feasible = [
                p
                for p in itertools.product(range(4), repeat=4)
                if all(lo[i] <= p[i] <= hi[i] for i in range(4))
                and all(p[a] >= p[b] for a, b in edges)
            ]
            solved = greatest_profile(lo, hi, edges)
            self.assertEqual(solved["status"] == "feasible", bool(feasible))
            if feasible:
                self.assertTrue(
                    all(
                        all(p[i] <= solved["target_q"][i] for i in range(4))
                        for p in feasible
                    )
                )

    def test_cycles_and_invalid_bounds_are_not_false_infeasibility_certificates(self):
        self.assertEqual(
            greatest_profile(np.array([0, 0]), np.array([3, 3]), [(0, 1), (1, 0)])[
                "status"
            ],
            "unresolved_cycle",
        )
        with self.assertRaises(ValueError):
            greatest_profile(np.array([0.0]), np.array([3.0]), [])

    def test_branch_nodes_preserved_and_proposal_obeys_cut_depth_and_bank_bounds(self):
        g, h, f, w, layout = fixture()
        pieces, plan = assess(g, h, f, w, layout)
        self.assertEqual(len(plan["components"]), 1)
        component = plan["components"][0]
        expected = {
            tuple(n) for r in pieces["rows"] for c in r["clips"] for n in c["nodes_rc"]
        }
        self.assertEqual({tuple(p["node_rc"]) for p in component["proposal"]}, expected)
        self.assertEqual(len(component["source_clips"]), 2)
        self.assertEqual(component["status"], "geometry_proposal_only")
        self.assertEqual(component["native_admission"], "unresolved")
        for p in component["proposal"]:
            node = tuple(p["node_rc"])
            self.assertTrue(0 <= f[node] - p["bed_q"] <= 192)
            self.assertGreaterEqual(p["depth_q"], 64)
            self.assertEqual(p["stage_q"] - p["bed_q"], p["depth_q"])
        self.assertTrue(np.array_equal(w, np.zeros_like(w)))

    def test_protected_graph_remains_refused_and_no_rate_is_invented(self):
        g, h, f, w, layout = fixture()
        h["start_area"]["landing"] = [32, 0]
        _, plan = assess(g, h, f, w, layout)
        c = plan["components"][0]
        self.assertEqual(c["status"], "refused_or_unresolved")
        self.assertGreater(c["guards"]["infrastructure_or_other_water_hits"], 0)
        self.assertEqual(c["supply_outlet_junction_status"], "unresolved")

    def test_equal_endpoints_and_more_than_three_metres_cut_refuse(self):
        g, h, f, w, layout = fixture()
        f[:] = 6400
        _, plan = assess(g, h, f, w, layout)
        self.assertEqual(
            plan["components"][0]["geometry"]["status"], "unresolved_direction_or_bank"
        )
        g, h, f, w, layout = fixture()
        f[540, 542] = 7000
        _, plan = assess(g, h, f, w, layout)
        self.assertEqual(
            plan["components"][0]["geometry"]["status"], "infeasible_bounds"
        )

    def test_missing_protection_evidence_cannot_become_a_pass(self):
        g, h, f, w, layout = fixture()
        del h["start_area"]
        _, plan = assess(g, h, f, w, layout)
        component = plan["components"][0]
        self.assertIsNotNone(component["guards"]["protection_unknown"])
        self.assertEqual(component["status"], "refused_or_unresolved")


class StreamProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / "source"
        cls.source.mkdir()
        g, h, f, w, layout = fixture()
        lake = {"source_features": [], "bodies": []}
        cls.old = compile_natural_inventory(g, h, lake)
        for n, x in [
            ("geometry.json", g),
            ("hydrology.json", h),
            ("natural-plan.json", lake),
            ("inventory.json", cls.old),
            ("layout.json", layout),
            ("probes.json", {"points": cls.old["points"]}),
        ]:
            write(cls.source / n, x)
        np.flipud(f).astype("<u2").tofile(cls.source / "terrain.u16")
        np.flipud(w).astype("<u2").tofile(cls.source / "water.u16")
        np.zeros((1081, 1081), np.uint8).tofile(cls.source / "mapped-water.u8")
        cls.output = cls.root / "protocol"
        stage(cls.source, cls.output, cls.source / "layout.json")

    def test_v3_keeps_all_original_points_and_contracts_and_is_not_a_native_plan(self):
        preflight(self.output)
        new = json.loads((self.output / "inventory.json").read_text())
        self.assertEqual(new["points"], self.old["points"])
        self.assertEqual(
            [e.get("contracts") for e in new["entries"]],
            [e.get("contracts") for e in self.old["entries"]],
        )
        self.assertFalse(new["coverage_complete"])
        self.assertFalse((self.output / "native-plan.json").exists())

    def test_coherently_rebound_inventory_omission_is_rejected(self):
        path, fp = self.output / "inventory.json", self.output / "freeze.json"
        saved, frozen = path.read_bytes(), fp.read_bytes()
        try:
            inv = json.loads(saved)
            inv["entries"].pop(0)
            write(path, inv)
            freeze = copy.deepcopy(json.loads(frozen))
            freeze["files_sha256"]["inventory.json"] = sha(path)
            write(fp, freeze)
            with self.assertRaisesRegex(ValueError, "does not replay"):
                preflight(self.output)
        finally:
            path.write_bytes(saved)
            fp.write_bytes(frozen)
