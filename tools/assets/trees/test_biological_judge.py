"""Fail closed on missing anchors and reject distant fitness after failed calibration."""

import unittest
from pathlib import Path
import json
import subprocess
import sys
import tempfile

from biological_judge import GENERA, VIEWS, calibration, preflight


class AnchorGateTests(unittest.TestCase):
    def test_cli_failure_writes_blocked_receipt_without_loading_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "anchors.json"
            manifest.write_text('{"anchors": []}')
            output = root / "result.json"
            run = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("biological_judge.py")),
                    str(manifest),
                    str(output),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 2, run.stderr)
            result = json.loads(output.read_text())
            self.assertTrue(result["blocked"])
            self.assertEqual(len(result["errors"]), 3)
            self.assertFalse(result["optimisation_started"])

    def test_absent_anchors_do_not_open_gate(self):
        errors, inputs = preflight({"anchors": []}, Path("."))
        self.assertEqual(len(errors), 3)
        self.assertEqual(inputs, [])

    def test_one_gameplay_failure_disables_distant_fitness(self):
        rows = [
            {"genus": g, "view": v, "predicted_genus": g} for g in GENERA for v in VIEWS
        ]
        next(r for r in rows if r["genus"] == "Tilia" and r["view"] == "gameplay")[
            "predicted_genus"
        ] = "Ulmus"
        self.assertEqual(calibration(rows)["bioclip_allowed_views"], ["close"])

    def test_close_failure_disables_bioclip(self):
        rows = [
            {"genus": g, "view": v, "predicted_genus": g} for g in GENERA for v in VIEWS
        ]
        rows[0]["predicted_genus"] = "Ulmus"
        self.assertEqual(calibration(rows)["bioclip_allowed_views"], [])

    def test_incomplete_screen_cannot_pass(self):
        with self.assertRaises(ValueError):
            calibration([])


if __name__ == "__main__":
    unittest.main()
