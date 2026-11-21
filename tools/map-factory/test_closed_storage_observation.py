"""Reject stale physical packages, cohorts and validators before a native slot."""

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from closed_storage_candidate import export
from closed_storage_observation import freeze, preflight


class ClosedStorageObservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        png, geo, banks = root / "input.png", root / "geo.json", root / "banks.f32"
        Image.fromarray(
            np.full((1081, 1081), round(100 * 65535 / 1024), dtype=np.uint16)
        ).save(png)
        geo.write_text(
            json.dumps(
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
                    "lakes": [],
                    "oceans": [],
                    "riverAreas": [],
                    "roads": [],
                    "seaLevel": None,
                }
            )
        )
        np.full((1081, 1081), 100, dtype="<f4").tofile(banks)
        self.folder = root / "candidate"
        self.generation = export(png, geo, banks, self.folder)
        # A synthetic protocol fixture, not a native observation or verdict.
        baseline = root / "protocol"
        baseline.mkdir()
        (baseline / "report.json").write_text(
            json.dumps({"game_minutes": 60, "session": {"mod_sha256": "a" * 64}})
        )
        (baseline / "harness-source.json").write_text(
            json.dumps({"dirty": False, "commit": "b" * 40})
        )
        (baseline / "verdict.json").write_text(
            json.dumps({"thresholds": {"max_unexpected_flood_km2": 0.05}})
        )
        self.plan_path = self.folder / "native-plan.json"
        freeze(self.folder, baseline, self.plan_path, "b" * 40, "a" * 64)
        self.plan = json.loads(self.plan_path.read_text())

    def test_frozen_actual_package_and_authored_probes_preflight(self):
        preflight(self.folder, self.plan)
        self.assertEqual(
            self.plan["item"]["files_sha256"]["probes.json"],
            self.generation["physical_files_sha256"]["probes.json"],
        )
        self.assertIn("not matched source-only", self.plan["qualification"])

    def test_changed_actual_package_is_rejected_before_launch(self):
        package = self.folder / self.plan["item"]["package"]
        raw = package.read_bytes()
        package.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        with self.assertRaisesRegex(ValueError, "Frozen candidate input changed"):
            preflight(self.folder, self.plan)

    def test_changed_plan_probe_cohort_is_not_accepted(self):
        self.plan["item"]["files_sha256"]["probes.json"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "probe bindings"):
            preflight(self.folder, self.plan)

    def test_changed_validator_contract_cannot_reuse_plan(self):
        self.plan["validator_sources_sha256"]["maintained_water.py"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "validator changed"):
            preflight(self.folder, self.plan)
