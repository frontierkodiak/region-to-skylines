"""Behavioral cross-runtime checks; no native game evidence is fabricated."""

import json
import tempfile
from pathlib import Path
import random
import subprocess
import unittest

import numpy as np

from capabilities import check, prepared_input, stock_band
from transport_paths import ship_path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = json.loads((ROOT / "capabilities.json").read_text())


def narrow_ship_export():
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
        (folder / "hydrology.json").write_text(json.dumps({"highways": fragment}))
        return prepared_input(folder)


class CapabilityParity(unittest.TestCase):
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
        javascript = """
          import {readFileSync} from 'node:fs';
          import {checkCapabilities} from './capability-model.js';
          const ledger = JSON.parse(readFileSync('capabilities.json'));
          const cases = JSON.parse(readFileSync(0, 'utf8'));
          process.stdout.write(JSON.stringify(cases.map((input) => checkCapabilities(input, ledger))));
        """
        result = subprocess.run(
            ["node", "--input-type=module", "-e", javascript],
            cwd=ROOT,
            input=json.dumps(inputs),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(
            json.loads(result.stdout), [check(data, LEDGER) for data in inputs]
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


if __name__ == "__main__":
    unittest.main()
