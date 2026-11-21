"""Qualification retains missing-input declines and the landed warning reasons."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from qualify_connections import frozen_inputs, screen, sha


class FrozenInputs(unittest.TestCase):
    def test_reuse_does_not_recapture_or_change_the_original_cohort(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline, candidate = root / "original", root / "candidate"
            source = baseline / "inputs" / "square"
            source.mkdir(parents=True)
            cohort = {"fixtures": ["square"], "fresh": []}
            raw = json.dumps(cohort).encode()
            (baseline / "cohort.json").write_bytes(raw)
            (source / "geometry.json").write_bytes(b"exact frozen input")
            report = {
                "selection": cohort,
                "cases": {
                    "square": {
                        "status": "exported",
                        "inputs_sha256": {
                            "geometry.json": sha(source / "geometry.json")
                        },
                    }
                },
            }
            (baseline / "cpu-report.json").write_text(json.dumps(report))
            frozen_inputs(baseline, candidate)
            self.assertEqual((candidate / "cohort.json").read_bytes(), raw)
            target = candidate / "inputs/square/geometry.json"
            self.assertEqual(
                target.read_bytes(), (source / "geometry.json").read_bytes()
            )
            target.write_bytes(b"changed square")
            with self.assertRaisesRegex(ValueError, "differs from frozen baseline"):
                frozen_inputs(baseline, candidate)
            self.assertEqual(
                (source / "geometry.json").read_bytes(), b"exact frozen input"
            )
            target.write_bytes(b"exact frozen input")
            (source / "geometry.json").write_bytes(b"changed baseline")
            with self.assertRaisesRegex(ValueError, "baseline input bytes changed"):
                frozen_inputs(baseline, candidate)

    def test_original_output_cannot_be_used_as_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            with self.assertRaisesRegex(
                ValueError, "differ from the preserved baseline"
            ):
                frozen_inputs(path, path)


class Screen(unittest.TestCase):
    def test_missing_preparation_is_declined_not_a_clear_square(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            risk = screen(folder)
            self.assertEqual(risk["status"], "declined")
            self.assertFalse(risk["native_tested"])
            self.assertEqual(json.loads((folder / "water-risk.json").read_text()), risk)
            self.assertEqual(
                set(risk["tool_sha256"]), {"water_risk.py", "water-risk-model.json"}
            )

    def test_screen_preserves_unmodified_landed_assessment_and_grid_bindings(self):
        from water_risk import assess

        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            terrain = np.full((1081, 1081), 6400, dtype="<u2")
            water = np.zeros_like(terrain)
            water[540, 100:900] = (
                8  # Present, narrow 12.5 cm film, not an omitted stream.
            )
            hydro = {"sea_level_m": 0, "sources": []}
            terrain.tofile(folder / "terrain.u16")
            water.tofile(folder / "water.u16")
            (folder / "hydrology.json").write_text(json.dumps(hydro))
            expected = assess(terrain, water, hydro)
            risk = screen(folder)
            for key, value in expected.items():
                self.assertEqual(risk[key], value)
            self.assertEqual(risk["risks"]["drying"]["level"], "flagged")
            self.assertTrue(risk["risks"]["drying"]["reasons"])
            self.assertEqual(
                set(risk["inputs_sha256"]),
                {"terrain.u16", "water.u16", "hydrology.json"},
            )


if __name__ == "__main__":
    unittest.main()
