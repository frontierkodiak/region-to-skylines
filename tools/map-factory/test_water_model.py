"""Current runtime parity: real inputs and constructed predicates, no native labels."""

import ast
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np
from capabilities import assess_prepared, prepared_input
from start_model import digest
from test_start_model import N, ROOT, unpack
from water_model import BANK, LOAD, bank_candidate, evaluate_water


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
                    "import {readFileSync} from 'node:fs'; import {evaluateWater} from './water-model.js';"
                    "console.log(JSON.stringify(evaluateWater(JSON.parse(readFileSync(process.argv[1])))))",
                    str(path),
                ],
                cwd=ROOT,
            )
        )


def constructed():
    # South-first channel, descending eastward; flat banks 1m above the surface.
    g, d = np.full((N, N), 95.0), np.zeros((N, N))
    g[538:543, :] = 100 - np.arange(N) / 64
    d[538:543, :] = 2
    return {
        "schema": 1,
        "mode": "export",
        "start_input": {
            "fidelity": "prepared_16m_south_first",
            "tile": 12,
            "terrain_m": g.ravel().tolist(),
            "depth_m": d.ravel().tolist(),
        },
        "water_plan": {
            "samples": {"channel": [[-640, 0, 0], [-320, 0, 0], [0, 0, 0], [320, 0, 0]]}
        },
    }


class WaterTests(unittest.TestCase):
    def same(self, a, b):
        if isinstance(a, dict):
            self.assertEqual(set(a), set(b))
            for k in a:
                self.same(a[k], b[k])
        elif isinstance(a, list):
            self.assertEqual(len(a), len(b))
            for x, y in zip(a, b):
                self.same(x, y)
        elif isinstance(a, float):
            self.assertAlmostEqual(a, b, places=7)
        else:
            self.assertEqual(a, b)

    def parity(self, data):
        result = evaluate_water(data)
        self.same(result, js(data))
        return result

    def test_constructed_witness_and_abstentions(self):
        data = constructed()
        result = self.parity(data)
        self.assertTrue(result["predicted"])
        self.assertEqual(len(result["witness"]["facilities"]), 2)
        self.assertEqual(result["witness"]["load"]["native_units_per_cycle"], 1000)
        self.assertEqual(result["service"], "unknown")
        for change in (
            lambda d: d["start_input"].pop("tile"),
            lambda d: d.pop("water_plan"),
            lambda d: d.update(planner_enabled={"water": False}),
            lambda d: d["start_input"].update(fidelity="coarse"),
            lambda d: d["start_input"].update(terrain_m=[0]),
            lambda d: d["water_plan"]["samples"].update(channel=[[0, 0]]),
            lambda d: d["water_plan"]["samples"].update(
                channel=[[0, 0, 0], [16, 0, 0]]
            ),
            lambda d: d["water_plan"]["samples"]["channel"].reverse(),
        ):
            changed = copy.deepcopy(data)
            change(changed)
            r = self.parity(changed)
            self.assertIsNone(r["predicted"])
            self.assertEqual(r["level"], "unknown")

    def test_real_prepared_and_bindings(self):
        for slug in ("innsbruck", "pittsburgh", "charleston", "asheville", "rio"):
            with self.subTest(slug=slug), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                unpack(slug, folder)
                data = prepared_input(folder)
                result = self.parity(data)
                report = assess_prepared(folder)
                binding = report["capabilities"]["water"]["binding"]
                self.assertEqual(binding["agreement"], "unscored_new_runtime")
                self.assertEqual(
                    binding["witness_sha256"],
                    digest(result["witness"]) if result["witness"] else None,
                )
                self.assertIsNone(binding["artifact_sha256"])
                raw = bytearray((folder / "terrain.u16").read_bytes())
                raw[0] ^= 1
                (folder / "terrain.u16").write_bytes(raw)
                mutated = assess_prepared(folder)["capabilities"]["water"]["binding"]
                self.assertNotEqual(binding["inputs_sha256"], mutated["inputs_sha256"])

    def test_route_depth_drop_and_order_boundaries(self):
        data = constructed()
        # Exact 320m and 1m pass; surface drop strictly above 1/64.
        d = data["start_input"]["depth_m"]
        for i, v in enumerate(d):
            if v:
                d[i] = 1
        self.assertTrue(self.parity(data)["channel_candidate"])
        # All wet surfaces equal => no supported downstream route.
        data["start_input"]["terrain_m"] = [100] * N**2
        self.assertIsNone(self.parity(data)["channel_candidate"])
        # Minimal exact and above-exact drop at a 320m sample separation.
        for drop, expected in ((1 / 64, False), (2 / 64, True)):
            g = [100] * N**2
            g[540 * N + 560] = 100 - drop
            data["start_input"]["terrain_m"] = g
            data["water_plan"]["samples"] = {"a": [[0, 0, 0], [320, 0, 0]]}
            r = self.parity(data)
            self.assertEqual(bool(r["channel_candidate"]), expected)
        data["start_input"]["depth_m"] = [0.999] * N**2
        self.assertIsNone(self.parity(data)["channel_candidate"])

    def test_bank_freeboard_and_snap_boundaries(self):
        g, d = np.full((N, N), 100.0), np.zeros((N, N))
        # Wet vertical strip; dry plateau. Tests actual bank construction.
        d[:, 538:543] = 2
        for freeboard, expected in (
            (0.25, True),
            (8, True),
            (0.249, False),
            (8.001, False),
        ):
            g[:] = 102 + freeboard
            g[:, 538:543] = 100
            self.assertEqual(
                bank_candidate(g, d, [0, 0, 0], 102, 12) is not None, expected
            )
        self.assertEqual(LOAD.shore_snap_radius_m, 50)
        self.assertEqual(BANK.maximum_bank_slope, 0.15)

    def test_bank_slope_and_snap_search_boundaries(self):
        for slope, expected in ((0.15, True), (0.15001, False)):
            g = np.tile((np.arange(N) - 540) * 16 * slope, (N, 1))
            d = np.zeros((N, N))
            d[538:543, :] = 2
            self.assertEqual(
                bank_candidate(g, d, [0, 0, 0], 2, 12) is not None, expected
            )
        # A shallow apron counts as a snap gap, not a continuously deep lateral.
        for shore_x, expected in ((80, True), (96, False)):
            x = (np.arange(N) - 540) * 16
            g = np.tile(np.where(x >= shore_x, 103.0, 100.0), (N, 1))
            d = np.tile(np.where(x <= 32, 2.0, np.where(x < shore_x, 0.5, 0.0)), (N, 1))
            self.assertEqual(
                bank_candidate(g, d, [0, 0, 0], 102, 12) is not None, expected
            )

    def test_archived_route_bank_and_parameters_unchanged(self):
        # Parse only. Never execute the historical predictor/scorer.
        old = ROOT / "tools/map-factory/capability-evidence/pl1078-components"
        active = ast.parse((ROOT / "tools/map-factory/water_model.py").read_text())

        def definition(tree, name):
            node = next(
                n
                for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name
            )
            return ast.dump(node, include_attributes=False)

        surface = ast.parse((old / "surface_intake.py").read_text())
        for name in ("bank_candidate", "Load", "BankParameters"):
            self.assertEqual(definition(active, name), definition(surface, name))


if __name__ == "__main__":
    unittest.main()
