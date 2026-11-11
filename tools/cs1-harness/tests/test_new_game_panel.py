"""Offline verdict fixtures; synthetic images here are never game evidence."""

import copy
import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from cs1_harness import new_game_panel as panel
from cs1_harness import verdict


class NewGamePanelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = pathlib.Path(self.temp.name)
        self.wanted = {
            "map_name": "Asheville",
            "author": "",
            "buildableArea": 37,
            "resources": {k: 0 for k in panel.RESOURCE_FIELDS},
            "connections": {k: 0 for k in panel.CONNECTION_FIELDS},
        }
        self.wanted["resources"]["maxResourceAmount"] = 100.0
        self.wanted["connections"]["incomingRoads"] = 1
        self.observed = {
            **copy.deepcopy(self.wanted),
            "source": "native NewGamePanel",
            "published": True,
            "imageRef": {"resolved": True, "width": 512, "height": 512},
            "steamPreviewRef": {"resolved": True, "width": 512, "height": 512},
            "snapshot_texture_present": True,
            "author_visible": False,
        }
        self.write("probes.json", {"new_game_panel": self.wanted})
        image = Image.new("RGB", (32, 32), "green")
        image.paste("white", (0, 0, 16, 16))
        image.save(self.out / "new-game-panel.png")
        self.sha = panel.digest(self.out / "new-game-panel.png")
        self.evidence = {"observed": self.observed, "screenshot": "new-game-panel.png", "sha256": self.sha}
        self.write("new-game-panel.json", self.evidence)
        self.review = {
            "sha256": self.sha,
            "reviewer": "offline-fixture-only",
            "notes": "synthetic test only",
            "observed": {
                "map_name": "Asheville",
                "author": "",
                "buildableArea": 37,
                "preview_matches_map": True,
                "resources_match": True,
                "connections_match": True,
                "selected_map_visible": True,
            },
        }
        self.write("new-game-panel-review.json", self.review)

    def write(self, filename, value):
        (self.out / filename).write_text(json.dumps(value))

    def test_complete_review_passes_and_enters_map_verdict(self):
        self.assertEqual(panel.assess(self.out)["status"], "pass")
        self.write("report.json", {})
        self.assertEqual(verdict.judge(self.out, write=False)["checks"][0]["name"], "new_game_panel")

    def test_not_requested_is_skip(self):
        self.write("probes.json", {})
        self.assertEqual(panel.assess(self.out)["status"], "skip")

    def test_missing_capture_fails(self):
        (self.out / "new-game-panel.json").unlink()
        self.assertEqual(panel.assess(self.out)["status"], "fail")

    def test_malformed_evidence_fails_without_crashing_verdict(self):
        for evidence in ([], {"observed": []}, {**self.evidence, "observed": {"imageRef": [1]}}):
            self.write("new-game-panel.json", evidence)
            self.assertEqual(panel.assess(self.out)["status"], "fail")

    def test_unreviewed_capture_fails(self):
        (self.out / "new-game-panel-review.json").unlink()
        self.assertIn("unreviewed", panel.assess(self.out)["detail"])

    def test_each_metadata_group_is_checked(self):
        for field in ("map_name", "author", "buildableArea", "resources", "connections"):
            with self.subTest(field=field):
                observed = copy.deepcopy(self.observed)
                observed[field] = None
                self.write("new-game-panel.json", {**self.evidence, "observed": observed})
                self.assertIn(f"native {field}", panel.assess(self.out)["detail"])

    def test_both_refs_must_resolve(self):
        for field in ("imageRef", "steamPreviewRef"):
            observed = copy.deepcopy(self.observed)
            observed[field] = {"resolved": False}
            self.write("new-game-panel.json", {**self.evidence, "observed": observed})
            self.assertIn(field, panel.assess(self.out)["detail"])

    def test_changed_image_or_review_cannot_pass(self):
        Image.new("RGB", (32, 32), "blue").save(self.out / "new-game-panel.png")
        self.assertIn("changed since capture", panel.assess(self.out)["detail"])
        self.review["sha256"] = "stale"
        self.write("new-game-panel-review.json", self.review)
        self.assertIn("unreviewed", panel.assess(self.out)["detail"])

    def test_incomplete_or_nonfinite_expectations_fail(self):
        for bad in (
            {},
            {**self.wanted, "resources": {"oilAmount": 3}},
            {**self.wanted, "buildableArea": True},
            {**self.wanted, "resources": {**self.wanted["resources"], "maxResourceAmount": float("nan")}},
        ):
            self.write("probes.json", {"new_game_panel": bad})
            self.assertEqual(panel.assess(self.out)["status"], "fail")

    def test_visual_assertions_are_required(self):
        self.review["observed"]["connections_match"] = False
        self.write("new-game-panel-review.json", self.review)
        self.assertIn("connections_match", panel.assess(self.out)["detail"])

    def test_dead_process_fails_before_poll_sleep(self):
        session = SimpleNamespace(alive=Mock(return_value=False))
        with patch.object(panel.time, "sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "process ended"):
                panel.wait_for_capture(session, self.out / "not-written.png")
        sleep.assert_not_called()

    def test_partial_native_file_is_retried_until_complete(self):
        shot = self.out / "new-game-panel.png"
        complete = shot.read_bytes()
        shot.write_bytes(complete[:40])
        session = SimpleNamespace(alive=Mock(return_value=None))
        with patch.object(panel.time, "sleep", side_effect=lambda _: shot.write_bytes(complete)) as sleep:
            self.assertEqual(panel.wait_for_capture(session, shot), self.sha)
        self.assertEqual(sleep.call_count, 1)
        self.assertEqual(session.alive.call_count, 2)

    def test_incomplete_capture_times_out(self):
        session = SimpleNamespace(alive=Mock(return_value=None))
        with patch.object(panel.time, "monotonic", side_effect=[0, 31]):
            with self.assertRaisesRegex(RuntimeError, "complete PNG"):
                panel.wait_for_capture(session, self.out / "not-written.png")

    def test_only_float_denominator_gets_tolerance(self):
        self.observed["resources"]["maxResourceAmount"] += 0.000005
        self.write("new-game-panel.json", self.evidence)
        self.assertEqual(panel.assess(self.out)["status"], "pass")
        self.observed["resources"]["oilAmount"] = 1
        self.write("new-game-panel.json", self.evidence)
        self.assertIn("resources.oilAmount", panel.assess(self.out)["detail"])

    def test_blank_capture_fails_even_with_matching_review_hash(self):
        Image.new("RGB", (32, 32), "black").save(self.out / "new-game-panel.png")
        self.evidence["sha256"] = panel.digest(self.out / "new-game-panel.png")
        self.review["sha256"] = self.evidence["sha256"]
        self.write("new-game-panel.json", self.evidence)
        self.write("new-game-panel-review.json", self.review)
        self.assertIn("blank", panel.assess(self.out)["detail"])


if __name__ == "__main__":
    unittest.main()
