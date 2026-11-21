"""Fresh preparation must not leave an abandoned pond or waive final earthworks."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from closed_storage_candidate import construct_after_networks, export, validate_package
from reservoir_basin import validate_native_basin


class ClosedStorageCandidateTests(unittest.TestCase):
    def setUp(self):
        self.ground = np.full((1081, 1081), 100.0)
        self.water = np.zeros_like(self.ground)
        self.geometry = {
            "sq": {
                "name": "dry synthetic",
                "slug": "dry-synthetic",
                "lat": 0,
                "lon": 0,
                "scale": 1,
                "rotation": 0,
            },
            "rivers": [],
            "streams": [],
            "lakes": [],
            "oceans": [],
            "riverAreas": [],
            "roads": [],
            "seaLevel": None,
        }
        self.start = {"x": 2, "z": 2, "index": 12, "landing": [0, 0]}
        self.layout, self.network = {"routes": []}, {"node_positions": {}}

    def construct(self):
        return construct_after_networks(
            self.ground,
            self.water,
            self.geometry,
            self.start,
            self.network,
            self.layout,
            [],
        )

    def test_closed_basin_preserves_source_inputs_and_stays_inside_start_tile(self):
        result = self.construct()
        source = result.source
        control = {
            "position": source["position"],
            "target_fixed": int(source["target"] * 64),
            "intake_rate": round(0.06 * 65535),
            "output_rate": round(0.06 * 65535),
        }
        self.assertGreaterEqual(
            validate_native_basin(result.terrain, control)["minimum_rim_freeboard_m"],
            0.5,
        )
        self.assertTrue(all(abs(v) + 112 < 960 for v in source["position"][::2]))
        self.assertFalse(self.water.any())
        self.assertTrue((self.ground == 100).all())

    def test_network_forces_relocation_without_abandoned_legacy_prefill(self):
        self.network["node_positions"] = {"1": [320, 112, -1000], "2": [320, 112, 1000]}
        self.layout["routes"] = [{"nodes": [1, 2]}]
        result = self.construct()
        self.assertGreater(abs(result.source["position"][0] - 320), 208)
        self.assertEqual(result.water[540, 560], 0)
        self.assertEqual(result.terrain[540, 560], 100)

    def test_unmodeled_stream_geometry_is_still_protected(self):
        lon = np.rad2deg(320 / 6378137)
        self.geometry["streams"] = [
            {"name": "unmodeled", "pts": [[lon, -0.01], [lon, 0.01]]}
        ]
        result = self.construct()
        self.assertGreater(abs(result.source["position"][0] - 320), 224)
        self.assertEqual(result.water[540, 560], 0)

    def test_infeasible_protected_tile_is_refused_without_leaking_fallback(self):
        self.ground += np.arange(1081)[None, :] * 0.5
        with self.assertRaisesRegex(ValueError, "No feasible enclosed"):
            self.construct()
        self.assertFalse(self.water.any())

    def files(self, root):
        png, geo, banks = root / "input.png", root / "geometry.json", root / "banks.f32"
        Image.fromarray(
            np.full((1081, 1081), round(100 * 65535 / 1024), dtype=np.uint16)
        ).save(png)
        geo.write_text(json.dumps(self.geometry))
        self.ground.astype("<f4").tofile(banks)
        return png, geo, banks

    def test_full_export_is_bound_but_not_native_qualification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.files(root)
            output = root / "candidate"
            receipt = export(*paths, output)
            self.assertEqual(receipt["status"], "prepared_not_native_qualified")
            self.assertEqual(receipt["stable_water_promise"], "unknown")
            self.assertFalse(
                receipt["preparation"]["water_construction"][
                    "legacy_pond_prefill_added"
                ]
            )
            self.assertEqual(
                len(receipt["final_static_check"]["static_storage_checks"]), 1
            )
            self.assertEqual(validate_package(output), receipt["final_static_check"])
            probes = json.loads((output / "probes.json").read_text())
            self.assertEqual(
                sum(
                    p["name"].startswith("engineered-storage:") and p["required"]
                    for p in probes["points"]
                ),
                1,
            )
            with self.assertRaisesRegex(ValueError, "fresh"):
                export(*paths, output)

    def test_late_admission_earthwork_cannot_keep_prepared_status(self):
        def break_rim(folder, *_):
            hydro = json.loads((folder / "hydrology.json").read_text())
            source = next(s for s in hydro["sources"] if s.get("class") == "reservoir")
            row = round((source["position"][2] + 8640) / 16)
            col = round((source["position"][0] + 8640) / 16) + 6
            terrain = np.fromfile(folder / "terrain.u16", "<u2").reshape(1081, 1081)
            terrain[row, col] = round((source["target"] + 0.25) * 64)
            terrain.tofile(folder / "terrain.u16")
            return {"applied": True, "native_qualified": False}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.files(root)
            with patch("closed_storage_candidate.admit", side_effect=break_rim):
                with self.assertRaisesRegex(ValueError, "freeboard"):
                    export(*paths, root / "candidate")
            self.assertFalse((root / "candidate/generation.json").exists())

    def test_late_fill_cannot_manufacture_a_passing_rim(self):
        def fill_rim(folder, *_):
            hydro = json.loads((folder / "hydrology.json").read_text())
            source = next(s for s in hydro["sources"] if s.get("class") == "reservoir")
            row = round((source["position"][2] + 8640) / 16)
            col = round((source["position"][0] + 8640) / 16) + 6
            terrain = np.fromfile(folder / "terrain.u16", "<u2").reshape(1081, 1081)
            terrain[row, col] += 32
            terrain.tofile(folder / "terrain.u16")
            return {"applied": True, "native_qualified": False}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.files(root)
            with patch("closed_storage_candidate.admit", side_effect=fill_rim):
                with self.assertRaisesRegex(ValueError, "untouched-rim"):
                    export(*paths, root / "candidate")
            self.assertFalse((root / "candidate/generation.json").exists())

    def test_late_prefill_removal_cannot_pass_from_geometry_alone(self):
        def remove_prefill(folder, *_):
            hydro = json.loads((folder / "hydrology.json").read_text())
            source = next(s for s in hydro["sources"] if s.get("class") == "reservoir")
            row = round((source["position"][2] + 8640) / 16)
            col = round((source["position"][0] + 8640) / 16)
            water = np.fromfile(folder / "water.u16", "<u2").reshape(1081, 1081)
            water[row, col] = 0
            water.tofile(folder / "water.u16")
            return {"applied": True, "native_qualified": False}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.files(root)
            with patch("closed_storage_candidate.admit", side_effect=remove_prefill):
                with self.assertRaisesRegex(ValueError, "initial storage"):
                    export(*paths, root / "candidate")
            self.assertFalse((root / "candidate/generation.json").exists())
