"""Real retained prepared inputs and explicitly constructed boundary cases."""

import copy
import gzip
import hashlib
import ast
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np
from capabilities import assess_prepared, prepared_input
from start_model import PARAMETERS, dry_centers, evaluate_start

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tools/map-factory/fixtures"
N = 1081


def graph():
    return {
        "nodes": [
            {"xyz": [-8640, 100, -32], "outside": True},
            {"xyz": [-300, 100, -32]},
            {"xyz": [-300, 100, 32]},
            {"xyz": [-8640, 100, 32], "outside": True},
        ],
        "edges": [
            {"a": 0, "b": 1, "kind": "highway"},
            {"a": 2, "b": 3, "kind": "ramp"},
        ],
    }


def constructed():
    return {
        "schema": 1,
        "mode": "export",
        "graph": graph(),
        "start_input": {
            "fidelity": "prepared_16m_south_first",
            "tile": 12,
            "terrain_m": [100] * N**2,
            "depth_m": [0] * N**2,
        },
    }


def unpack(slug, folder):
    for name in ("terrain.u16", "water.u16", "hydrology.json"):
        (folder / name).write_bytes(
            gzip.decompress((FIXTURES / slug / (name + ".gz")).read_bytes())
        )


def js(data):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "input.json"
        path.write_text(json.dumps(data))
        return json.loads(
            subprocess.check_output(
                [
                    "node",
                    "--input-type=module",
                    "-e",
                    "import {readFileSync} from 'node:fs'; import {evaluateStart} from './start-model.js';"
                    "console.log(JSON.stringify(evaluateStart(JSON.parse(readFileSync(process.argv[1])))))",
                    str(path),
                ],
                cwd=ROOT,
            )
        )


class StartTests(unittest.TestCase):
    def assert_same(self, a, b):
        if isinstance(a, dict):
            self.assertEqual(set(a), set(b))
            for key in a:
                self.assert_same(a[key], b[key])
        elif isinstance(a, list):
            self.assertEqual(len(a), len(b))
            for x, y in zip(a, b):
                self.assert_same(x, y)
        elif isinstance(a, float):
            self.assertAlmostEqual(a, b, places=7)
        else:
            self.assertEqual(a, b)

    def test_constructed_directed_plan_and_boundaries(self):
        data = constructed()
        result = evaluate_start(data)
        self.assertTrue(result["predicted"])
        self.assertEqual(len(result["witness"]["steps"]), 27)
        self.assert_same(result, js(data))
        for mutate in (
            lambda d: d["graph"]["edges"].pop(),
            lambda d: d.pop("graph"),
            lambda d: d["start_input"].pop("tile"),
            lambda d: d.update(planner_enabled={"start": False}),
            lambda d: d["start_input"].update(depth_m=[1] * N**2),
            lambda d: d["start_input"].update(terrain_m=[100] * (N**2 - 1)),
            lambda d: d["start_input"].update(fidelity="coarse"),
        ):
            changed = copy.deepcopy(data)
            mutate(changed)
            expected = evaluate_start(changed)
            self.assertNotEqual(expected.get("predicted"), True)
            self.assert_same(expected, js(changed))

    def test_retained_real_inputs_frozen_algorithm_and_browser(self):
        for slug in ("innsbruck", "pittsburgh", "charleston", "asheville", "rio"):
            with self.subTest(slug=slug), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                unpack(slug, folder)
                data = prepared_input(folder)
                result = evaluate_start(data)
                self.assert_same(result, js(data))
                report = assess_prepared(folder)
                binding = report["capabilities"]["start"]["binding"]
                self.assertEqual(binding["agreement"], "unscored_new_runtime")
                self.assertEqual(
                    binding["inputs_sha256"]["terrain.u16"],
                    hashlib.sha256((folder / "terrain.u16").read_bytes()).hexdigest(),
                )
                if result.get("witness"):
                    changed = copy.deepcopy(result["witness"])
                    changed["points"]["join"][0] += 1
                    from start_model import digest

                    self.assertNotEqual(digest(changed), binding["witness_sha256"])
                raw = bytearray((folder / "terrain.u16").read_bytes())
                raw[0] ^= 1
                (folder / "terrain.u16").write_bytes(raw)
                mutated = assess_prepared(folder)["capabilities"]["start"]["binding"]
                self.assertNotEqual(binding["inputs_sha256"], mutated["inputs_sha256"])

    def test_live_footprint_real_grids_uses_same_predicates_without_graph(self):
        for slug in ("innsbruck", "pittsburgh", "charleston", "asheville", "rio"):
            with self.subTest(slug=slug), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                unpack(slug, folder)
                arrays = [
                    np.fromfile(folder / name, dtype="<u2").reshape(N, N).astype(float)
                    / 64
                    for name in ("terrain.u16", "water.u16")
                ]
                centers = dry_centers(*arrays, {"nodes": [], "edges": []}, 12)
                path = folder / "north.json"
                path.write_text(
                    json.dumps([np.flipud(a).ravel().tolist() for a in arrays])
                )
                result = json.loads(
                    subprocess.check_output(
                        [
                            "node",
                            "--input-type=module",
                            "-e",
                            "import {readFileSync} from 'node:fs'; import {liveFootprint} from './start-model.js'; console.log(JSON.stringify(liveFootprint(...JSON.parse(readFileSync(process.argv[1])))))",
                            str(path),
                        ],
                        cwd=ROOT,
                    )
                )
                self.assertEqual(result["candidates"], len(centers))
                self.assertEqual(result["center_xz"], centers[0] if centers else None)
                self.assertEqual(result["hookup"], "unknown")
                self.assertEqual(result["level"], "unknown")

    def test_frozen_geometry_functions_are_preserved_without_running_archived_predictor(
        self,
    ):
        original = ast.parse(
            (
                ROOT
                / "tools/map-factory/capability-evidence/pl1078-components/start_capabilities.py"
            ).read_text()
        )
        active = ast.parse((ROOT / "tools/map-factory/start_model.py").read_text())
        names = {
            "sample",
            "position",
            "edge_curve",
            "outward_heading",
            "link_clearance",
            "road_mask",
            "dry_centers",
            "segment_clear",
        }

        def functions(tree):
            return {
                n.name: ast.dump(n, include_attributes=False)
                for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name in names
            }

        self.assertEqual(functions(original), functions(active))

    def test_footprint_thresholds_extent_and_orientation(self):
        ground, depth = np.full((N, N), 100.0), np.full((N, N), PARAMETERS.max_depth_m)
        empty = {"nodes": [], "edges": []}
        centers = dry_centers(ground, depth, empty, 12)
        self.assertEqual(len(centers), 529)
        depth[500:581, 500:581] = PARAMETERS.max_depth_m + 1e-9
        self.assertLess(len(dry_centers(ground, depth, empty, 12)), len(centers))
        # Exactly 8 m relief across the 384 m footprint passes; a small excess fails.
        for delta, expected in ((8, True), (8.0001, False)):
            ramp = np.tile(np.arange(N) * 16 * delta / 384, (N, 1))
            self.assertEqual(
                bool(dry_centers(ramp, np.zeros_like(depth), empty, 12)), expected
            )
        # Local equality: segment grade 15 percent is accepted; above is rejected.
        from start_model import segment_clear

        self.assertTrue(
            segment_clear(ground, np.zeros_like(depth), [0, 0, 0], [100, 15, 0])
        )
        self.assertFalse(
            segment_clear(ground, np.zeros_like(depth), [0, 0, 0], [100, 15.001, 0])
        )
        depth[:] = 1
        self.assertEqual(dry_centers(ground, depth, empty, 12), [])


if __name__ == "__main__":
    unittest.main()
