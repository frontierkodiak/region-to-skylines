"""Offline saved-grid fixtures; not native acceptance or geometry-mask certification."""

import hashlib
import json
import pathlib
import tempfile
import unittest

import numpy as np

from cs1_harness import mapped_water
from cs1_harness.verdict import GRID_N, MAP_SOAK, adjudicate_flooding, flooding


class MappedWaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.source = self.root / "source"
        self.out = self.root / "run"
        self.source.mkdir()
        (self.out / "grids").mkdir(parents=True)
        self.reference = np.zeros((GRID_N, GRID_N), dtype="<u2")
        self.reference[100:120, 100:120] = 64
        self.saved = self.reference.copy()
        self.saved[100:120, 300:320] = 64
        self.reference.tofile(self.out / "grids/t000-water.u16")
        self.saved.tofile(self.out / "grids/t001-water.u16")
        self.mask = np.zeros((GRID_N, GRID_N), dtype=np.uint8)
        self.mask[100:120, 100:320] = 1
        self.path = self.source / "channel.u8"
        self.mask.tofile(self.path)
        self.spec = self.spec_for(self.path)
        self.probes = self.source / "probes.json"
        self.probes.write_text(json.dumps({"mapped_water": self.spec}))
        self.report = {"first_dump": "t000"}

    @staticmethod
    def spec_for(path):
        return {
            "file": path.name,
            "format": mapped_water.FORMAT,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def freeze(self):
        mapped_water.freeze(self.probes, self.out)
        return {"mapped_water": self.spec}

    def test_channel_extension_excluded_but_distant_flood_still_fails(self):
        meta = self.freeze()
        check = flooding(self.out, self.report, meta, MAP_SOAK)
        self.assertEqual(check["status"], "pass")
        self.assertEqual(check["value"]["worst_km2"], 0)
        self.assertTrue(check["value"]["initial_only_diagnostic"]["would_fail"])
        self.assertEqual(check["value"]["initial_only_diagnostic"]["worst_km2"], 0.1024)
        self.saved[700:720, 700:720] = 64
        self.saved.tofile(self.out / "grids/t001-water.u16")
        check = flooding(self.out, self.report, meta, MAP_SOAK)
        self.assertEqual(check["status"], "fail")
        self.assertEqual(check["value"]["worst_km2"], 0.1024)
        self.assertEqual(check["value"]["failing_grids"][0]["grid"], "t001-water.u16")

    def test_changed_missing_malformed_masks_fail_closed(self):
        meta = self.freeze()
        frozen = self.out / mapped_water.FROZEN_FILE
        for raw in [None, b"changed", bytes(GRID_N * GRID_N)]:
            with self.subTest(raw=None if raw is None else len(raw)):
                if raw is None:
                    frozen.unlink(missing_ok=True)
                else:
                    frozen.write_bytes(raw)
                self.assertEqual(flooding(self.out, self.report, meta, MAP_SOAK)["status"], "fail")
        for raw in [b"short", bytes([2]) * (GRID_N * GRID_N)]:
            frozen.write_bytes(raw)
            bad = {"mapped_water": self.spec_for(frozen)}
            self.assertEqual(flooding(self.out, self.report, bad, MAP_SOAK)["status"], "fail")
        for spec in [None, {}, {**self.spec, "file": "../escape"}, {**self.spec, "format": "north-first"}]:
            with self.subTest(spec=spec):
                self.assertEqual(flooding(self.out, self.report, {"mapped_water": spec}, MAP_SOAK)["status"], "fail")

    def test_no_request_preserves_legacy_and_ignores_unrequested_file(self):
        baseline = flooding(self.out, self.report, {}, MAP_SOAK)
        self.freeze()
        self.assertEqual(flooding(self.out, self.report, {}, MAP_SOAK), baseline)
        self.assertEqual(baseline["status"], "fail")
        self.assertNotIn("initial_only_diagnostic", baseline["value"])

    def test_freeze_exact_bytes_and_source_changes_do_not_affect_run(self):
        meta = self.freeze()
        self.assertEqual((self.out / mapped_water.FROZEN_FILE).read_bytes(), self.path.read_bytes())
        self.path.write_bytes(b"changed upstream")
        self.assertEqual(flooding(self.out, self.report, meta, MAP_SOAK)["status"], "pass")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            mapped_water.freeze(self.probes, self.out)

    def test_supplemental_assessment_preserves_historical_artifacts(self):
        (self.out / "report.json").write_text(json.dumps(self.report))
        (self.out / "probes.json").write_text('{"points": []}\n')
        (self.out / "verdict.json").write_text('{"verdict": "fail"}\n')
        before = {p: p.read_bytes() for p in self.out.rglob("*") if p.is_file()}
        assessment = adjudicate_flooding(self.out, self.path, self.spec)
        self.assertEqual(assessment["assessment"]["status"], "pass")
        self.assertFalse(assessment["native_acceptance"])
        self.assertEqual({p: p.read_bytes() for p in self.out.rglob("*") if p.is_file()}, before)
        self.path.unlink()
        self.assertEqual(adjudicate_flooding(self.out, self.path, self.spec)["assessment"]["status"], "fail")

    def test_distance_and_depth_boundaries_keep_euclidean_definition(self):
        meta = self.freeze()
        saved = self.reference.copy()
        # Nearest mapped cell is [119,319]; a diagonal (6,6) is >128m,
        # while an axis-aligned 8-cell offset is exactly 128m.
        saved[119, 327] = 64
        saved[125, 325] = 32  # exactly .5m is not deeper than .5m
        saved.tofile(self.out / "grids/t001-water.u16")
        thresholds = {**MAP_SOAK, "flood_max_km2": 0}
        self.assertEqual(flooding(self.out, self.report, meta, thresholds)["status"], "pass")
        saved[125, 325] = 33
        saved.tofile(self.out / "grids/t001-water.u16")
        self.assertEqual(flooding(self.out, self.report, meta, thresholds)["status"], "fail")

    def test_dry_initial_reference_keeps_legacy_skip_diagnostic(self):
        np.zeros_like(self.reference).tofile(self.out / "grids/t000-water.u16")
        self.assertEqual(flooding(self.out, self.report, {}, MAP_SOAK)["status"], "skip")
        check = flooding(self.out, self.report, self.freeze(), MAP_SOAK)
        self.assertEqual(check["status"], "pass")
        self.assertEqual(check["value"]["initial_only_diagnostic"]["status"], "skip")
        self.assertFalse(check["value"]["initial_only_diagnostic"]["would_fail"])

    def test_requested_mask_without_saved_evidence_cannot_skip_or_pass(self):
        meta = self.freeze()
        for p in (self.out / "grids").iterdir():
            p.unlink()
        self.assertEqual(flooding(self.out, self.report, meta, MAP_SOAK)["status"], "fail")


if __name__ == "__main__":
    unittest.main()
