import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cs1_harness import registry


class RegistryValueTests(unittest.TestCase):
    def test_scalar_failed_checks_register_without_overwriting_the_verdict(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            out = root / "run"
            out.mkdir()
            verdict = {
                "verdict": "fail",
                "failed": ["no_flooding"],
                "checks": [
                    {"name": "no_flooding", "status": "fail", "value": 73},
                    {"name": "probes_wet_end", "status": "skip", "value": 0},
                ],
            }
            (out / "verdict.json").write_text(json.dumps(verdict))
            before = (out / "verdict.json").read_bytes()
            with patch.object(registry, "REGISTRY", root / "index.jsonl"):
                row = registry.add(out)
                saved = json.loads((root / "index.jsonl").read_text())
            self.assertEqual(row["verdict"], "fail")
            self.assertEqual(saved["failed"], ["no_flooding"])
            self.assertIsNone(row["metrics"]["flood_km2"])
            self.assertIsNone(row["metrics"]["probes_required"])
            self.assertEqual((out / "verdict.json").read_bytes(), before)

    def test_structured_metrics_are_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            out = Path(name)
            (out / "verdict.json").write_text(
                json.dumps(
                    {
                        "verdict": "fail",
                        "checks": [
                            {"name": "no_flooding", "value": {"worst_km2": 0.07}},
                            {"name": "probes_wet_end", "value": {"wet": 4, "required": 5}},
                        ],
                    }
                )
            )
            row = registry.entry(out)
            self.assertEqual(row["metrics"]["flood_km2"], 0.07)
            self.assertEqual(row["metrics"]["probes_wet_end"], 4)
            self.assertEqual(row["metrics"]["probes_required"], 5)
