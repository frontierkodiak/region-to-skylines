"""Behavioral cross-runtime checks; no native game evidence is fabricated."""

import json
import copy
import tempfile
from pathlib import Path
import random
import subprocess
import unittest

import numpy as np

from capabilities import check, prepared_input, stock_band
from integrate_outside_evidence import boundary_probe
from transport_paths import ship_path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = json.loads((ROOT / "capabilities.json").read_text())


def constructed_qualified_ledger():
    """Constructed launch identity for gate tests, never real native evidence."""
    ledger = copy.deepcopy(LEDGER)
    ledger["native_path_certificates"] = copy.deepcopy(
        ledger["evidence_studies"]["outside-v1"]["qualification_candidates"]
    )
    for certificate in ledger["native_path_certificates"]:
        del certificate["blocked_by"]
        context = certificate["native_context"]
        context["runtime_game_sha256"] = "a" * 64
        context["runtime_game_assemblies"] = copy.deepcopy(context["game_assemblies"])
        context["protocol"]["entry"] = "NewGameFromMap"
        context["protocol"]["inverted_traffic"] = False
        certificate["runtime_identity_evidence"] = {
            "file": "tools/map-factory/capability-evidence/runtime-identities/"
            + "a" * 64
            + ".json",
            "sha256": "a" * 64,
        }
    return ledger


QUALIFIED = constructed_qualified_ledger()


def qualification_cases():
    certificate = next(
        c for c in QUALIFIED["native_path_certificates"] if c["capability"] == "ship"
    )
    identity = {
        name: copy.deepcopy(certificate[name])
        for name in ("artifact_sha256", "inputs_sha256", "native_context")
    }
    base = {
        "schema": 1,
        "mode": "export",
        "graph": {
            "nodes": [{"outside": "west"}, {"outside": "east"}],
            "edges": [{"a": 0, "b": 1, "kind": "ship"}],
        },
        "export_identity": identity,
    }
    cases = [base]
    for path, value in (
        (("mode",), "estimate"),
        (("export_identity",), None),
        (("export_identity",), True),
        (("export_identity", "artifact_sha256"), "0" * 64),
        (("export_identity", "inputs_sha256"), {}),
        (("export_identity", "inputs_sha256", "water.u16"), "0" * 64),
        (("export_identity", "native_context"), None),
        (("export_identity", "native_context"), {}),
        (("export_identity", "native_context", "mod_sha256"), "0" * 64),
        (("export_identity", "native_context", "collector_sha256"), "0" * 64),
        (("export_identity", "native_context", "runtime_game_sha256"), None),
        (("export_identity", "native_context", "runtime_game_assemblies"), None),
        (
            (
                "export_identity",
                "native_context",
                "game_assemblies",
                "Assembly-CSharp.dll",
            ),
            "0" * 64,
        ),
        (("export_identity", "native_context", "protocol", "no_workshop"), False),
        (("planner_enabled",), {"ship": False}),
        (("graph",), None),
    ):
        data = copy.deepcopy(base)
        parent = data
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = value
        cases.append(data)
    air = next(
        c for c in QUALIFIED["native_path_certificates"] if c["capability"] == "air"
    )
    data = copy.deepcopy(base)
    data["graph"]["edges"][0]["kind"] = "air"
    data["export_identity"] = {name: copy.deepcopy(air[name]) for name in identity}
    cases.append(data)
    return cases


def narrow_ship_export(planner_report=None):
    """Constructed depth, real offline planner; not native game evidence."""
    ground = np.full((1081, 1081), 100.0)
    depth = np.zeros_like(ground)
    depth[540:544, :] = 8.0  # 64 m, narrower than the model's shore buffer.
    geometry = {"sq": {"lon": 0, "lat": 0, "rotation": 0, "scale": 1}, "seaLevel": 108}
    fragment, _ = ship_path(geometry, ground, depth, 12, 108)
    if fragment is None:
        raise AssertionError(
            "Counterexample no longer exercises an authored ship route"
        )
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        for name, grid in (("terrain.u16", ground), ("water.u16", depth)):
            (np.flipud(grid) * 64).astype("<u2").tofile(folder / name)
        (folder / "hydrology.json").write_text(
            json.dumps({"highways": fragment, "highway_report": planner_report or {}})
        )
        return prepared_input(folder)


class CapabilityParity(unittest.TestCase):
    def test_midpoints_and_unreached_endpoints_are_not_boundary_witnesses(self):
        segments = {
            1: {
                "id": 1,
                "start": 10,
                "end": 11,
                "start_flags": "Created, Outside",
                "end_flags": "Created",
            },
            2: {
                "id": 2,
                "start": 12,
                "end": 13,
                "start_flags": "Created",
                "end_flags": "Created, Outside",
            },
        }
        path = {
            "request": {
                "name": "outside-to-outside",
                "from": [1, 0, 0],
                "to": [2, 0, 255],
            },
            "result": {"success": True, "positions": [[1, 0, 0], [2, 0, 255]]},
        }
        self.assertTrue(boundary_probe(path, segments))
        midpoint = copy.deepcopy(path)
        midpoint["request"]["from"][2] = 128
        midpoint["result"]["positions"][0][2] = 128
        self.assertFalse(boundary_probe(midpoint, segments))
        unreached = copy.deepcopy(path)
        unreached["result"]["positions"][-1][2] = 128
        self.assertFalse(boundary_probe(unreached, segments))
        named = copy.deepcopy(path)
        named["request"]["name"] = "named-midpoint-probe"
        self.assertFalse(boundary_probe(named, segments))
        within = copy.deepcopy(path)
        within["request"]["to"][0] = 1
        self.assertFalse(boundary_probe(within, segments))

    def test_seeded_grids_and_directed_graphs_match_javascript(self):
        rng = random.Random(1119)
        inputs = []
        for iteration in range(40):
            size = 17
            depth = [
                8 if rng.random() < iteration / 39 else 0 for _ in range(size * size)
            ]
            graph = {
                "nodes": [
                    {"outside": "west" if i == 0 else "east" if i == 7 else None}
                    for i in range(8)
                ],
                "edges": [
                    {
                        "a": rng.randrange(8),
                        "b": rng.randrange(8),
                        "kind": rng.choice(["rail", "ship", "air", "highway", "ramp"]),
                    }
                    for _ in range(15)
                ],
            }
            inputs.append(
                {
                    "schema": 1,
                    "mode": "export" if iteration % 2 else "estimate",
                    "grid": {"size": size, "spacing_m": 1080, "depth_m": depth},
                    "graph": graph,
                    "buildable_fraction": iteration / 39,
                }
            )
        inputs.extend(
            [
                {
                    "schema": 1,
                    "mode": "estimate",
                    "transport": {"road": True, "air": False},
                },
                {"schema": 1, "mode": "export"},
            ]
        )
        inputs.append(narrow_ship_export())
        for mode in ("export", "estimate"):
            for depth in (0, 8):
                inputs.append(
                    {
                        "schema": 1,
                        "mode": mode,
                        "planner_enabled": {"ship": False, "air": False},
                        "graph": {"nodes": [], "edges": []},
                        "grid": {
                            "size": 17,
                            "spacing_m": 1080,
                            "depth_m": [depth] * 289,
                        },
                    }
                )
        inputs.extend(qualification_cases())
        javascript = """
          import {readFileSync} from 'node:fs';
          import {checkCapabilities} from './capability-model.js';
          const {ledger,cases} = JSON.parse(readFileSync(0, 'utf8'));
          process.stdout.write(JSON.stringify(cases.map((input) => checkCapabilities(input, ledger))));
        """
        result = subprocess.run(
            ["node", "--input-type=module", "-e", javascript],
            cwd=ROOT,
            input=json.dumps({"ledger": QUALIFIED, "cases": inputs}),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(
            json.loads(result.stdout), [check(data, QUALIFIED) for data in inputs]
        )

    def test_real_offline_ship_planner_is_not_vetoed_by_coarse_corridor(self):
        ship = check(narrow_ship_export(), LEDGER)["capabilities"]["ship"]
        self.assertTrue(ship["authored_route"]["candidate"])
        self.assertFalse(ship["witness"]["candidate"])
        self.assertEqual(ship["level"], "likely")
        self.assertEqual(ship["reason"], "authored_ship_route_corridor_unconfirmed")

    def test_stock_band_boundaries(self):
        metric = {"p25": 1, "p75": 3}
        self.assertEqual(
            [stock_band(v, metric) for v in (0, 1, 2, 3, 4, None)],
            [
                "below_p25",
                "typical",
                "typical",
                "typical",
                "above_p75",
                "not_comparable",
            ],
        )

    def test_only_explicit_exact_native_context_qualifies_sampled_paths(self):
        cases = qualification_cases()
        self.assertEqual(
            check(cases[0], QUALIFIED)["capabilities"]["ship"]["level"], "promised"
        )
        self.assertEqual(
            check(cases[-1], QUALIFIED)["capabilities"]["air"]["level"], "promised"
        )
        for data in cases[1:-1]:
            self.assertNotEqual(
                check(data, QUALIFIED)["capabilities"]["ship"]["level"], "promised"
            )
        self.assertNotEqual(
            check(cases[0], LEDGER)["capabilities"]["ship"]["level"], "promised"
        )

    def test_prepared_opt_out_is_unknown_not_a_negative(self):
        data = narrow_ship_export({"ship": "off", "air": "off"})
        self.assertEqual(data["planner_enabled"], {"ship": False, "air": False})
        for graph in (data["graph"], {"nodes": [], "edges": []}):
            data["graph"] = graph
            report = check(data, LEDGER)["capabilities"]
            for key in ("ship", "air"):
                self.assertEqual(
                    report[key], {"level": "unknown", "reason": "planner_disabled"}
                )
        del data["planner_enabled"]
        self.assertEqual(
            check(data, LEDGER)["capabilities"]["ship"]["level"], "not_possible_here"
        )


if __name__ == "__main__":
    unittest.main()
