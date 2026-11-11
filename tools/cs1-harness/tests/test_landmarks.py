"""Synthetic offline fixtures only; these do not certify any actual map orientation."""

import copy
import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from cs1_harness import landmarks, verdict


class LandmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = pathlib.Path(self.temp.name)
        self.wanted = {
            "reference": "synthetic fixture, not geographic evidence",
            "points": [
                {"name": "ridge", "x": 103.125, "z": -500.75, "expected_height_m": 612, "tolerance_m": 12},
                {"name": "river", "x": -1000, "z": 2048, "expected_height_m": 101, "tolerance_m": 12},
            ],
        }
        self.observed = {
            "source": landmarks.SOURCE,
            "phase": "startup_before_harness_camera_overrides",
            "camera": {"current_angle_degrees": [-28, 20], "areas_visible": False},
            "points": [
                {k: p[k] for k in ("name", "x", "z")} | {"height_m": p["expected_height_m"] - 1.8}
                for p in self.wanted["points"]
            ],
        }
        self.write("probes.json", {"landmarks": self.wanted})
        self.write("startup-world.json", self.observed)

    def write(self, name, data):
        (self.out / name).write_text(json.dumps(data))

    def test_height_matches_and_camera_receipt_enters_verdict(self):
        self.write("report.json", {})
        row = verdict.judge(self.out, write=False)["checks"][1]
        self.assertEqual(row["name"], "terrain_landmarks")
        self.assertEqual(row["status"], "pass")
        self.assertEqual(row["value"]["startup_camera"]["current_angle_degrees"], [-28, 20])

    def test_transposed_point_heights_fail(self):
        points = self.observed["points"]
        points[0]["height_m"], points[1]["height_m"] = points[1]["height_m"], points[0]["height_m"]
        self.write("startup-world.json", self.observed)
        self.assertEqual(landmarks.assess(self.out)["status"], "fail")
        self.assertIn("ridge, river", landmarks.assess(self.out)["detail"])

    def test_native_point_identity_cannot_be_substituted(self):
        self.observed["points"].reverse()
        self.write("startup-world.json", self.observed)
        self.assertIn("identity/coordinates", landmarks.assess(self.out)["detail"])

    def test_missing_native_evidence_fails(self):
        (self.out / "startup-world.json").unlink()
        self.assertEqual(landmarks.assess(self.out)["status"], "fail")

    def test_not_requested_skips(self):
        self.write("probes.json", {})
        self.assertEqual(landmarks.assess(self.out)["status"], "skip")

    def test_post_override_or_area_zoom_cannot_certify_startup(self):
        for change in ({"phase": "after"}, {"camera": {"current_angle_degrees": [90, 60], "areas_visible": True}}):
            self.write("startup-world.json", {**self.observed, **change})
            self.assertEqual(landmarks.assess(self.out)["status"], "fail")

    def test_incomplete_or_nondistinguishing_requests_fail(self):
        same_height = copy.deepcopy(self.wanted)
        same_height["points"][1]["expected_height_m"] = 612
        for bad in ({}, {**self.wanted, "points": self.wanted["points"][:1]}, same_height):
            self.write("probes.json", {"landmarks": bad})
            self.assertEqual(landmarks.assess(self.out)["status"], "fail")

    def test_nonfinite_height_and_camera_fail(self):
        bad = copy.deepcopy(self.observed)
        bad["points"][0]["height_m"] = float("nan")
        self.write("startup-world.json", bad)
        self.assertEqual(landmarks.assess(self.out)["status"], "fail")
        bad = copy.deepcopy(self.observed)
        bad["camera"]["current_angle_degrees"] = [float("inf"), 20]
        self.write("startup-world.json", bad)
        self.assertEqual(landmarks.assess(self.out)["status"], "fail")

    def test_capture_only_requests_readonly_world_observations(self):
        client = SimpleNamespace(call=Mock(return_value=copy.deepcopy(self.observed)))
        actual = landmarks.capture(SimpleNamespace(client=client), self.out, self.wanted)
        client.call.assert_called_once_with(
            "world_observe", points=[{k: p[k] for k in ("name", "x", "z")} for p in self.wanted["points"]]
        )
        self.assertEqual(actual["phase"], "startup_before_harness_camera_overrides")
        self.assertEqual(json.loads((self.out / "startup-world.json").read_text()), actual)


if __name__ == "__main__":
    unittest.main()
