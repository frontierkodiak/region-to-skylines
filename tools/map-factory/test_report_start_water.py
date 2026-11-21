"""Do not turn success flags, missing observations or another source into proof."""

import json
from pathlib import Path
import tempfile
import unittest

from report_start_water import literal_paths, observation, report, sha, summarize


class StudyProjection(unittest.TestCase):
    def test_a_changed_prediction_snapshot_is_rejected_before_scoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predictions.json"
            path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "recorded freeze"):
                report(path, Path(tmp), "d" * 64, "c" * 40, "0" * 64)

    def test_midpoint_success_is_not_a_returned_outside_endpoint(self):
        path = {
            "direction": "outbound",
            "success": True,
            "grid_segment": 1,
            "edge_segment": 2,
            "edge_offset": 255,
            "positions": [[1, 0, 128], [2, 1, 128]],
        }
        self.assertEqual(
            0, literal_paths({"complete": True, "paths": [path]})["outbound"]
        )
        path["positions"][-1][2] = 255
        self.assertEqual(
            1, literal_paths({"complete": True, "paths": [path]})["outbound"]
        )

    def test_unscored_positives_and_holdouts_do_not_disappear_into_fitting_rate(self):
        rows = [
            {
                "split": "fitting",
                "capability_id": "start",
                "predicted": True,
                "observed": v,
            }
            for v in (True, False, None)
        ]
        rows.append(
            {
                "split": "held_out",
                "capability_id": "start",
                "predicted": True,
                "observed": False,
            }
        )
        result = summarize(rows)
        self.assertEqual(0.5, result["fitting"]["start"]["positive_witness_agreement"])
        self.assertEqual(1, result["fitting"]["start"]["unscored_positive"])
        self.assertEqual(0, result["held_out"]["start"]["positive_witness_agreement"])

    def entry(self):
        return {
            "slug": "synthetic",
            "split": "fitting",
            "prediction_sha256": "unused",
            "prediction": {
                "square": {"slug": "synthetic"},
                "source_sha": "a" * 40,
                "assessment_source_sha": "b" * 40,
                "artifact_sha256": "e" * 64,
                "capabilities": {
                    "start": {
                        "predicted": True,
                        "witness": {"schema": 1},
                        "witness_sha256": "f" * 64,
                    }
                },
            },
        }

    def test_missing_native_attempt_stays_null_not_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = observation(
                self.entry(),
                "start",
                Path(tmp),
                "a" * 64,
                "d" * 64,
                "c" * 40,
                "2026-11-21T01:00:00+00:00",
            )
        self.assertIsNone(row["observed"])
        self.assertEqual("no_completed_native_attempt", row["unscored_reason"])

    def test_another_collector_or_dll_cannot_supply_a_native_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "native-v2-start/synthetic"
            folder.mkdir(parents=True)
            entry = self.entry()
            (folder / "prediction.json").write_text(json.dumps(entry["prediction"]))
            entry["prediction_sha256"] = sha(folder / "prediction.json")
            raw = {
                "model_sha256": "a" * 64,
                "oracle_dll_sha256": "d" * 64,
                "oracle": "exact_start_witness_v1",
                "artifact_sha256": "e" * 64,
                "prediction_sha256": entry["prediction_sha256"],
                "oracle_source": {"commit": "0" * 40, "dirty": False},
                "observed_start": True,
            }
            for key, value in (
                ("oracle_source", raw["oracle_source"]),
                ("oracle_dll_sha256", "0" * 64),
            ):
                with self.subTest(key=key):
                    changed = {
                        **raw,
                        "oracle_source": {"commit": "c" * 40, "dirty": False},
                        key: value,
                    }
                    (folder / "observation.json").write_text(json.dumps(changed))
                    with self.assertRaisesRegex(ValueError, "identity"):
                        observation(
                            entry,
                            "start",
                            root,
                            "a" * 64,
                            "d" * 64,
                            "c" * 40,
                            "2026-11-21T01:00:00+00:00",
                        )


if __name__ == "__main__":
    unittest.main()
