"""Behavioral checks for a frozen, one-shot geographic calibration."""

import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from fit_water_holdout import fit
from score_water_panel import (
    clearance,
    collect,
    rate,
    score,
    scored_prediction,
    summarize,
)
from water_calibration_panel import panel
from stage_water_panel import input_power

ROOT = Path(__file__).resolve().parent


class WaterPanelTests(unittest.TestCase):
    def test_always_warn_is_rejected_before_any_game_labels_exist(self):
        prediction = {
            "status": "warning",
            "risks": {
                "flood": {"level": "not_flagged"},
                "drying": {"level": "flagged"},
            },
        }
        power = input_power(
            [
                {
                    "slug": "one",
                    "status": "prepared",
                    "prediction": prediction,
                    "deployed_prediction": prediction,
                }
            ]
        )
        self.assertEqual(power["drying_disposition"], "rejected_as_discriminator")
        self.assertFalse(power["flood_threshold_change_identifiable"])
        self.assertEqual(power["rule_cleared_squares"], [])
        self.assertFalse(power["uses_native_labels"])

    def test_declined_assessment_is_unscored_not_a_crash_or_clearance(self):
        labels, flags, status = scored_prediction(
            {"status": "declined", "risks": {}}, {"flood": False, "drying": True}, True
        )
        self.assertEqual(labels, {"flood": None, "drying": None})
        self.assertTrue(all(flags.values()))
        self.assertEqual(status, "assessment_declined")

    def test_selection_reproduces_all_30_fixed_nonoverlapping_squares(self):
        selected = panel()
        self.assertEqual(
            selected, json.loads((ROOT / "water-calibration-panel.json").read_text())
        )
        squares = selected["squares"]
        self.assertEqual(len(squares), 30)
        self.assertEqual(len({r["sq"]["slug"] for r in squares}), 30)
        self.assertEqual(sum(r["expected_drying_negative"] for r in squares), 6)
        for i, left in enumerate(squares):
            self.assertLessEqual(
                abs(left["sq"]["lat"] - left["anchor_lat"]), 3000 / 111320
            )
            for right in squares[i + 1 :]:
                lat, lon = left["sq"]["lat"], left["sq"]["lon"]
                distance_km = math.hypot(
                    (lat - right["sq"]["lat"]) * 111.32,
                    (lon - right["sq"]["lon"]) * 111.32 * math.cos(math.radians(lat)),
                )
                self.assertGreater(distance_km, 25)

    def test_old_data_fit_reproduces_frozen_candidate(self):
        rows = json.loads(
            (ROOT / "fixtures/contracts/pl912-water-risk-v1/corpus.json").read_text()
        )
        rows = [r for r in rows if r["complete_60"]]
        model = json.loads((ROOT / "calibration/pl1072-frozen/model.json").read_text())
        self.assertEqual(fit(rows), model["rules"])

    def test_zero_failures_has_a_nonzero_upper_risk_bound(self):
        result = rate(0, 30)
        self.assertEqual(result["rate"], 0)
        self.assertAlmostEqual(result["ci95"][1], 1 - 0.025 ** (1 / 30))
        self.assertIsNone(rate(0, 0)["rate"])
        self.assertIsNone(rate(0, 0)["ci95"])

    def rows(self):
        return [
            {
                "slug": str(i),
                "labels": {"flood": label, "drying": False},
                "flags": {"flood": prediction, "drying": False},
                "product_clear": not prediction,
            }
            for i, (label, prediction) in enumerate(
                (
                    (True, True),
                    (False, True),
                    (False, False),
                    (True, False),
                    (None, False),
                )
            )
        ]

    def test_confusion_and_coverage_do_not_count_unknowns_as_safe(self):
        result = summarize(self.rows(), "flood")
        self.assertEqual([result[k] for k in ("tp", "fp", "tn", "fn")], [1, 1, 1, 1])
        self.assertEqual(result["precision"]["rate"], 0.5)
        self.assertEqual(result["recall"]["rate"], 0.5)
        self.assertEqual(result["unknown_squares"], ["4"])
        self.assertEqual(clearance(self.rows())["cleared_squares"], ["2", "3"])
        self.assertEqual(clearance(self.rows())["absolute_risk_reduction"], 0)

    def test_always_warn_has_no_demonstrated_cleared_risk(self):
        rows = self.rows()
        for row in rows:
            row["flags"]["flood"] = True
        self.assertTrue(summarize(rows, "flood")["identical_to_always_warn"])
        self.assertIsNone(clearance(rows)["cleared_risk"]["rate"])
        self.assertIsNone(clearance(rows)["relative_risk_reduction"])

    def test_no_positive_or_negative_denominators_are_not_perfect_scores(self):
        rows = self.rows()[1:3]
        self.assertIsNone(summarize(rows, "flood")["recall"]["rate"])
        self.assertEqual(summarize(rows, "flood")["specificity"]["rate"], 0.5)
        self.assertIsNone(summarize([], "flood")["precision"]["rate"])

    def test_rescore_and_alternate_result_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            staging = Path(directory)
            output = staging / "holdout-score.json"
            output.write_text("{}")
            with self.assertRaises(FileExistsError):
                score(staging, staging, output, staging, staging)
            with self.assertRaises(ValueError):
                score(staging, staging, staging / "alternate.json", staging, staging)

    def test_model_drift_is_rejected_before_any_native_report_is_read(self):
        with tempfile.TemporaryDirectory() as directory:
            staging = Path(directory)
            freeze_path = ROOT / "calibration/pl1072-frozen"
            freeze = json.loads((freeze_path / "freeze.json").read_text())
            (staging / "freeze.json").write_bytes(
                (freeze_path / "freeze.json").read_bytes()
            )
            original = (freeze_path / "model.json").read_bytes()
            self.assertEqual(
                hashlib.sha256(original).hexdigest(), freeze["model_sha256"]
            )
            (staging / "model.json").write_bytes(original + b" ")
            (staging / "staging.json").write_text(
                json.dumps(
                    {
                        **freeze,
                        "freeze_sha256": hashlib.sha256(
                            (staging / "freeze.json").read_bytes()
                        ).hexdigest(),
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "Frozen model/panel changed"):
                collect(
                    staging, staging, staging, ROOT / "water-calibration-panel.json"
                )


if __name__ == "__main__":
    unittest.main()
