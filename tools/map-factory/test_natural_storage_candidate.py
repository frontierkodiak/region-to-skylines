import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from natural_storage_candidate import export, identity, sha, write
from natural_storage_observation import freeze, preflight
from test_maintained_water_inventory import body


class NaturalCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        source = cls.root / "source"
        source.mkdir()
        Image.fromarray(
            np.full((1081, 1081), round(100 * 65535 / 1024), np.uint16)
        ).save(source / "source-input.png")
        np.full((1081, 1081), 100, "<f4").tofile(source / "source-banks.f32")
        write(
            source / "geometry.json",
            {
                "sq": {
                    "name": "synthetic",
                    "slug": "synthetic",
                    "lat": 0,
                    "lon": 0,
                    "scale": 1,
                    "rotation": 0,
                },
                "rivers": [],
                "streams": [],
                "lakes": [body(3000, 3000, 3016, 3016)],
                "riverAreas": [],
                "oceans": [],
                "roads": [],
                "seaLevel": None,
            },
        )
        cls.folder = cls.root / "candidate"
        cls.generation = export(source, cls.folder)
        protocol = cls.root / "protocol.json"
        write(
            protocol,
            {
                "schema": "polli.closed-storage-native-plan/1",
                "harness_source": "a" * 40,
                "mod_sha256": "b" * 64,
                "thresholds": {"max_unexpected_flood_km2": 0.05},
            },
        )
        # Protocol fixture only, never a synthetic native observation.
        freeze(cls.folder, protocol)

    def test_real_crp_final_geometry_and_new_probe_protocol_preflight(self):
        identity(self.folder)
        plan, inventory = preflight(self.folder)
        self.assertTrue(self.generation["final_static_check"]["natural_bodies"])
        self.assertTrue(
            any(
                c["kind"] == "engineered"
                for e in inventory["entries"]
                if e["id"].startswith("natural-storage:")
                for c in e["contracts"]
            )
        )
        self.assertEqual(plan["thresholds"]["max_unexpected_flood_km2"], 0.05)

    def test_coherent_probe_omission_does_not_remove_a_contract(self):
        files = {
            name: (self.folder / name).read_bytes()
            for name in ("probes.json", "generation.json", "native-plan.json")
        }
        try:
            probes = json.loads(files["probes.json"])
            probes["points"].pop()
            write(self.folder / "probes.json", probes)
            gen = json.loads(files["generation.json"])
            gen["physical_files_sha256"]["probes.json"] = sha(
                self.folder / "probes.json"
            )
            write(self.folder / "generation.json", gen)
            plan = json.loads(files["native-plan.json"])
            plan["generation_sha256"] = sha(self.folder / "generation.json")
            plan["item"]["files_sha256"] = gen["physical_files_sha256"]
            write(self.folder / "native-plan.json", plan)
            with self.assertRaisesRegex(ValueError, "omits an inventory contract"):
                preflight(self.folder)
        finally:
            for name, raw in files.items():
                (self.folder / name).write_bytes(raw)

    def test_changed_constructed_geometry_cannot_reuse_the_plan(self):
        path = self.folder / "natural-plan.json"
        raw = path.read_bytes()
        try:
            plan = json.loads(raw)
            plan["bodies"][0]["target_m"] += 1 / 64
            write(path, plan)
            with self.assertRaisesRegex(ValueError, "Frozen natural candidate changed"):
                preflight(self.folder)
        finally:
            path.write_bytes(raw)


if __name__ == "__main__":
    unittest.main()
