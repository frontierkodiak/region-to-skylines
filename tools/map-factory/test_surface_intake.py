import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from surface_intake import assess_surface


class SurfaceWitness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ground = np.full((1081, 1081), 55.0, dtype=float)
        self.depth = np.zeros_like(self.ground)
        self.hydro = {
            "start_tile": 12,
            "highways": {"nodes": [], "edges": []},
            "samples": {},
        }

    def write(self):
        for name, a in [("terrain.u16", self.ground), ("water.u16", self.depth)]:
            np.floor(a * 64 + 0.5).clip(0, 65535).astype("<u2").tofile(self.root / name)
        (self.root / "hydrology.json").write_text(json.dumps(self.hydro))

    def channel(self):
        self.ground[539:542, :] = np.linspace(50, 45, 1081)[None, :]
        self.depth[539:542, :] = 4
        self.hydro["samples"] = {"channel": [[x, 0, 0] for x in range(-800, 801, 16)]}

    def hashes(self):
        return {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in self.root.iterdir()
        }

    def test_no_route_is_unknown_not_a_groundwater_substitution(self):
        self.write()
        row = assess_surface(self.root)["capabilities"]["water"]
        self.assertIsNone(row["predicted"])
        self.assertIsNone(row["witness"])

    def test_initial_channel_with_banks_emits_fixed_native_load_not_a_promise(self):
        self.channel()
        self.write()
        before = self.hashes()
        row = assess_surface(self.root)["capabilities"]["water"]
        self.assertTrue(row["predicted"])
        self.assertEqual("likely", row["level"])
        w = row["witness"]
        self.assertEqual(
            ["Water Intake", "Water Outlet"], [f["prefab"] for f in w["facilities"]]
        )
        self.assertEqual([50, 50], [f["shore_snap_radius_m"] for f in w["facilities"]])
        self.assertEqual(1000, w["load"]["native_units_per_cycle"])
        self.assertEqual(60, w["load"]["horizon_game_minutes"])
        self.assertIn("auxiliary", row["limits"][3].lower())
        self.assertEqual(before, self.hashes())

    def test_water_without_dry_banks_cannot_emit_a_placement_witness(self):
        self.channel()
        self.depth[:] = 4
        self.write()
        row = assess_surface(self.root)["capabilities"]["water"]
        self.assertIsNone(row["predicted"])
        self.assertIsNone(row["witness"])

    def test_map_label_cannot_change_physical_capability(self):
        self.channel()
        self.write()
        before = assess_surface(self.root)["capabilities"]["water"]
        self.hydro["map_name"] = "Other arbitrary place"
        self.hydro["map_id"] = "ignored"
        self.write()
        self.assertEqual(before, assess_surface(self.root)["capabilities"]["water"])


if __name__ == "__main__":
    unittest.main()
