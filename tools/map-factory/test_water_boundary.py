"""Full-core normalized estimate and Unicode witness parity, no native labels."""

import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from capabilities import check
from test_water_model import ROOT, constructed
import test_water_model as water_tests

LEDGER = json.loads((ROOT / "capabilities.json").read_text())


def node(script, data=None):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "input.json"
        path.write_text(json.dumps(data))
        return json.loads(
            subprocess.check_output(
                ["node", "--input-type=module", "-e", script, str(path)], cwd=ROOT
            )
        )


CORE = """
import {readFileSync} from 'node:fs';
import {checkCapabilities} from './capability-model.js';
const data=JSON.parse(readFileSync(process.argv[1]));
console.log(JSON.stringify(checkCapabilities(data,JSON.parse(readFileSync('capabilities.json')))));
"""


def estimate_cases():
    captured = node("""
import {liveShore} from './water-model.js';
const n=1081,g=new Float64Array(n*n).fill(103),d=new Float64Array(n*n);
for(let r=560;r<=564;r++)for(let c=0;c<n;c++){g[r*n+c]=100;d[r*n+c]=2;}
console.log(JSON.stringify({
 valid:liveShore(g,d), coarse:liveShore(g,d,{spacing:64}),
 partial:liveShore([100],[0]), miss:liveShore(g,new Float64Array(n*n))
}));
""")
    valid = captured["valid"]
    cases = [{"schema": 1, "mode": "estimate", "water_opportunity": valid}]
    for level in ("promised", "not_possible_here"):
        claims = copy.deepcopy(valid)
        claims.update(
            level=level,
            predicted=True,
            service="verified",
            quality="clean",
            flow="verified",
            hookup="verified",
            native_agreement="qualified",
            certificate={"valid": True},
            witness={"qualified": True},
        )
        cases.append({"schema": 1, "mode": "estimate", "water_opportunity": claims})
    for opportunity in (
        None,
        {},
        [],
        {"level": "promised", "service": "verified"},
        {**valid, "fidelity": "coarse"},
        {**valid, "model": "unsupported"},
        {**valid, "bank": None},
        {**valid, "wet_point_xz": [0, 0]},
        {**valid, "bank": {**valid["bank"], "water_anchor": [0, 0, 500]}},
        {**valid, "bank": {**valid["bank"], "lateral_min_depth_m": 0.5}},
        {**valid, "bank": {**valid["bank"], "lateral_sample_count": "6"}},
    ):
        cases.append(
            {"schema": 1, "mode": "estimate", "water_opportunity": opportunity}
        )
    cases.append({"schema": 1, "mode": "estimate"})
    cases.append(
        {
            "schema": 1,
            "mode": "estimate",
            "water_opportunity": valid,
            "planner_enabled": {"water": False},
        }
    )
    for key in ("coarse", "partial", "miss"):
        cases.append(
            {"schema": 1, "mode": "estimate", "water_opportunity": captured[key]}
        )
    return cases


class WaterBoundaryTests(unittest.TestCase):
    def test_full_core_estimate_boundary_parity(self):
        for i, data in enumerate(estimate_cases()):
            with self.subTest(case=i):
                py, js = check(data, LEDGER), node(CORE, data)
                water_tests.WaterTests().same(py, js)
                water = py["capabilities"]["water"]
                self.assertEqual(water["level"], "likely" if i < 3 else "unknown")
                for key in ("service", "quality", "flow", "hookup"):
                    self.assertEqual(water[key], "unknown")
                self.assertIsNone(water["predicted"])
                self.assertIsNone(water["witness"])
                self.assertNotIn("certificate", water)
                self.assertTrue(water["native_agreement"].startswith("unscored"))

    def test_unicode_full_prepared_witness_parity(self):
        data = constructed()
        route = data["water_plan"]["samples"]["channel"]
        for names in (
            ("\ue000", "\U00010000"),
            ("a\ue000", "a\U00010000"),
            ("河\ue000", "河\U00010000"),
        ):
            for order in (names, names[::-1]):
                with self.subTest(names=order):
                    data["water_plan"]["samples"] = {name: route for name in order}
                    py, js = check(data, LEDGER), node(CORE, data)
                    water_tests.WaterTests().same(py, js)
                    water = py["capabilities"]["water"]
                    self.assertTrue(water["predicted"])
                    self.assertEqual(
                        water["witness"]["channel_route"]["river"], names[0]
                    )


def write_browser_cases(out):
    out.mkdir(parents=True, exist_ok=True)
    rows = []

    def save(name, data):
        i = len(rows)
        (out / f"{i}.json").write_text(json.dumps(data, separators=(",", ":")))
        rows.append(
            {"case": name, "file": f"{i}.json", "expected": check(data, LEDGER)}
        )

    for i, data in enumerate(estimate_cases()):
        save(f"constructed-estimate-{i}", data)
    data = constructed()
    route = data["water_plan"]["samples"]["channel"]
    for i, names in enumerate(
        (
            ("\ue000", "\U00010000"),
            ("a\ue000", "a\U00010000"),
            ("河\ue000", "河\U00010000"),
        )
    ):
        for order, keys in enumerate((names, names[::-1])):
            data["water_plan"]["samples"] = {key: route for key in keys}
            save(f"constructed-unicode-{i}-{order}", data)
    (out / "cases.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(f"{len(rows)} constructed full-core browser inputs written")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser-out", type=Path)
    args = parser.parse_args()
    if args.browser_out:
        write_browser_cases(args.browser_out)
    else:
        unittest.main(argv=[__file__])
