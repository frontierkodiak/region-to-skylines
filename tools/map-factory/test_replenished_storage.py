import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from natural_storage_candidate import export as passive_export, write
from replenished_storage import controls, export, freeze, identity, preflight, sha
from test_maintained_water_inventory import body
from water_diagnostics import decode_water
from crp import read_package


class ReplenishedStorageTests(unittest.TestCase):
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
        cls.parent = cls.root / "passive"
        passive_export(source, cls.parent)
        cls.folder = cls.root / "regulated"
        cls.generation = export(cls.parent, cls.folder)
        protocol = cls.root / "runtime.json"
        write(
            protocol,
            {
                "schema": "polli.closed-storage-native-plan/1",
                "harness_source": "a" * 40,
                "mod_sha256": "b" * 64,
                "thresholds": {"max_unexpected_flood_km2": 0.05},
            },
        )
        freeze(cls.folder, protocol)

    def test_real_package_retains_existing_controls_grids_and_complete_cohort(self):
        generation = identity(self.folder)
        preflight(self.folder)
        old = json.loads((self.parent / "hydrology.json").read_text())
        new = json.loads((self.folder / "hydrology.json").read_text())
        self.assertEqual(new["sources"][: len(old["sources"])], old["sources"])
        rule = json.loads((self.folder / "regulation.json").read_text())
        self.assertTrue(rule["sources"])
        self.assertEqual(
            rule["sum_encoded_rates_per_direction"], 128 * len(rule["sources"])
        )
        decoded = decode_water(
            next(
                a["payload"]
                for a in read_package(
                    (self.folder / generation["package"]).read_bytes()
                )[1]
                if a["kind"] == 52
            )
        )
        self.assertEqual(
            decoded["depth"].astype("<u2").tobytes(),
            (self.parent / "water.u16").read_bytes(),
        )
        self.assertTrue(
            all(
                s["intake_rate"] == s["output_rate"] == 128
                for s in decoded["sources"][len(old["sources"]) :]
            )
        )
        self.assertEqual(
            json.loads((self.parent / "probes.json").read_text())["points"],
            json.loads((self.folder / "probes.json").read_text())["points"],
        )

    def test_coherently_rebound_cohort_omission_is_rejected(self):
        names = ["probes.json", "generation.json", "native-plan.json"]
        saved = {n: (self.folder / n).read_bytes() for n in names}
        try:
            probes = json.loads(saved["probes.json"])
            probes["points"].pop()
            write(self.folder / "probes.json", probes)
            generation = json.loads(saved["generation.json"])
            generation["physical_files_sha256"]["probes.json"] = sha(
                self.folder / "probes.json"
            )
            write(self.folder / "generation.json", generation)
            plan = json.loads(saved["native-plan.json"])
            plan["generation_sha256"] = sha(self.folder / "generation.json")
            plan["item"]["files_sha256"] = generation["physical_files_sha256"]
            write(self.folder / "native-plan.json", plan)
            with self.assertRaisesRegex(ValueError, "Matched probe cohort"):
                preflight(self.folder)
        finally:
            for name, data in saved.items():
                (self.folder / name).write_bytes(data)

    def test_rate_that_reaches_neighbouring_rim_is_not_admitted(self):
        geometry = json.loads((self.parent / "geometry.json").read_text())
        construction = json.loads((self.parent / "natural-plan.json").read_text())
        with (
            patch("replenished_storage.RATE", 225),
            self.assertRaisesRegex(ValueError, "footprint"),
        ):
            controls(geometry, construction, np.full((1081, 1081), 100.0))

    def test_terrain_drift_even_with_rebound_hash_is_rejected(self):
        path = self.folder / "terrain.u16"
        saved = path.read_bytes()
        gen_path = self.folder / "generation.json"
        original_generation = gen_path.read_bytes()
        try:
            values = np.frombuffer(saved, "<u2").copy()
            values[0] -= 1
            values.tofile(path)
            generation = copy.deepcopy(self.generation)
            generation["physical_files_sha256"]["terrain.u16"] = sha(path)
            write(gen_path, generation)
            with self.assertRaisesRegex(ValueError, "Source-only intervention"):
                identity(self.folder)
        finally:
            path.write_bytes(saved)
            gen_path.write_bytes(original_generation)


if __name__ == "__main__":
    unittest.main()
