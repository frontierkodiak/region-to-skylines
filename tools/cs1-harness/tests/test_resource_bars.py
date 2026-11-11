"""Offline synthetic bar readbacks/PNGs, never evidence of native rendering."""

import copy
import itertools
import json
import math
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from cs1_harness import new_game_panel as panel
from cs1_harness.client import HarnessError


class ResourceBarTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = pathlib.Path(self.temp.name)
        self.stage = self.out / "stage"
        self.stage.mkdir()
        self.wanted = {
            "map_name": "offline synthetic map",
            "author": "",
            "buildableArea": 73,
            "resources": {
                "maxResourceAmount": 20631704.0,
                "oreAmount": 1086916,
                "oilAmount": 570000,
                "forestAmount": 4128000,
                "fertileLandAmount": 700000,
                "waterAmount": 538600,
            },
            "connections": {key: 0 for key in panel.CONNECTION_FIELDS},
            "require_resource_bars": True,
        }
        image = Image.new("RGB", (32, 32), "green")
        image.paste("white", (0, 0, 16, 16))
        image.save(self.out / "new-game-panel.png")
        self.png = (self.out / "new-game-panel.png").read_bytes()
        self.evidence = {
            "observed": self.observation(13),
            "screenshot": "new-game-panel.png",
            "sha256": panel.digest(self.out / "new-game-panel.png"),
            "resource_bar_settlement": {
                "schema": 1,
                "samples": [self.observation(i) for i in [10, 11, 12]],
                "after": self.observation(14),
            },
        }
        self.write("probes.json", {"new_game_panel": self.wanted})
        self.write("new-game-panel.json", self.evidence)
        self.write(
            "new-game-panel-review.json",
            {
                "sha256": self.evidence["sha256"],
                "reviewer": "offline fixture",
                "notes": "synthetic test only",
                "observed": {
                    "map_name": self.wanted["map_name"],
                    "author": "",
                    "buildableArea": 73,
                    "preview_matches_map": True,
                    "resources_match": True,
                    "connections_match": True,
                    "selected_map_visible": True,
                },
            },
        )

    def write(self, name, value):
        (self.out / name).write_text(json.dumps(value))

    def observation(self, frame):
        resources = copy.deepcopy(self.wanted["resources"])
        bars = {}
        for name, (field, component) in panel.BAR_FIELDS.items():
            amount, denominator, exponent = resources[field], resources["maxResourceAmount"], 0.3
            target = math.pow(amount / denominator, exponent)
            bars[name] = {
                "component": component,
                "amount": amount,
                "denominator": denominator,
                "exponent": exponent,
                "value": target,
                "normalized_target": target,
                "target_value": target,
                "min_value": 0,
                "max_value": 1,
                "visible": True,
                "animating": False,
                "no_resource_visible": amount == 0,
                "expected_no_resource": amount == 0,
            }
        return {
            "source": "native NewGamePanel",
            "path": "/offline/map.crp",
            "selected_index": 3,
            **copy.deepcopy(self.wanted),
            "published": True,
            "snapshot_texture_present": True,
            "author_visible": False,
            "imageRef": {"resolved": True, "width": 400, "height": 224},
            "steamPreviewRef": {"resolved": True, "width": 1800, "height": 1008},
            "resource_bars": {
                "schema": 1,
                "source": panel.BAR_SOURCE,
                "frame": frame,
                "realtime": frame * 0.25,
                "bars": bars,
            },
        }

    def test_stable_actual_readbacks_and_review_pass(self):
        row = panel.assess(self.out)
        self.assertEqual(row["status"], "pass", row)
        self.assertTrue(row["value"]["resource_bars_verified"])

    def test_metadata_correct_but_ore_zero_cannot_pass(self):
        for sample in self.evidence["resource_bar_settlement"]["samples"]:
            sample["resource_bars"]["bars"]["ore"]["value"] = 0
        self.write("new-game-panel.json", self.evidence)
        self.assertEqual(panel.assess(self.out)["status"], "fail")
        self.assertEqual(self.evidence["observed"]["resources"]["oreAmount"], 1086916)

    def test_wrong_native_target_nonfinite_and_missing_control_fail(self):
        for defect in ["target", "nonfinite", "missing"]:
            evidence = copy.deepcopy(self.evidence)
            bars = evidence["observed"]["resource_bars"]["bars"]
            if defect == "target":
                bars["ore"]["normalized_target"] = 0
            elif defect == "nonfinite":
                bars["ore"]["value"] = float("nan")
            else:
                del bars["ore"]
            self.write("new-game-panel.json", evidence)
            self.assertEqual(panel.assess(self.out)["status"], "fail")

    def test_icon_mismatch_and_active_animation_fail(self):
        for field in ["no_resource_visible", "expected_no_resource", "animating"]:
            evidence = copy.deepcopy(self.evidence)
            evidence["observed"]["resource_bars"]["bars"]["ore"][field] = True
            self.write("new-game-panel.json", evidence)
            self.assertEqual(panel.assess(self.out)["status"], "fail")

    def test_duplicate_frames_and_unstable_values_fail(self):
        for defect in ["frame", "value"]:
            evidence = copy.deepcopy(self.evidence)
            samples = evidence["resource_bar_settlement"]["samples"]
            if defect == "frame":
                samples[1]["resource_bars"]["frame"] = samples[0]["resource_bars"]["frame"]
            else:
                samples[1]["resource_bars"]["bars"]["ore"]["value"] += 0.00005
            self.write("new-game-panel.json", evidence)
            self.assertEqual(panel.assess(self.out)["status"], "fail")

    def test_post_capture_bar_drop_and_wrong_selection_fail(self):
        for defect in ["value", "selection"]:
            evidence = copy.deepcopy(self.evidence)
            after = evidence["resource_bar_settlement"]["after"]
            if defect == "value":
                after["resource_bars"]["bars"]["ore"]["value"] = 0
            else:
                after["selected_index"] = 4
            self.write("new-game-panel.json", evidence)
            self.assertEqual(panel.assess(self.out)["status"], "fail")

    def test_legacy_evidence_is_not_silently_upgraded(self):
        del self.evidence["resource_bar_settlement"]
        del self.evidence["observed"]["resource_bars"]
        self.write("new-game-panel.json", self.evidence)
        self.assertEqual(panel.assess(self.out)["status"], "fail")
        del self.wanted["require_resource_bars"]
        self.write("probes.json", {"new_game_panel": self.wanted})
        row = panel.assess(self.out)
        self.assertEqual(row["status"], "pass", row)
        self.assertFalse(row["value"]["resource_bars_verified"])

    def test_request_flag_must_be_bool(self):
        with self.assertRaisesRegex(ValueError, "boolean"):
            panel.expectations({**self.wanted, "require_resource_bars": 1})

    def test_zero_resources_use_zero_target_and_visible_no_resource_icon(self):
        self.wanted["resources"]["oilAmount"] = 0
        self.write("probes.json", {"new_game_panel": self.wanted})
        self.evidence["observed"] = self.observation(13)
        self.evidence["resource_bar_settlement"].update(
            samples=[self.observation(i) for i in [10, 11, 12]], after=self.observation(14)
        )
        self.write("new-game-panel.json", self.evidence)
        self.assertEqual(panel.assess(self.out)["status"], "pass")

    def test_manual_visual_review_still_required_after_correct_bar_measurements(self):
        (self.out / "new-game-panel-review.json").unlink()
        self.assertIn("unreviewed", panel.assess(self.out)["detail"])

    def fake_session(self, stuck=False):
        frame = itertools.count(20)

        def call(op, **kw):
            self.assertEqual(op, "new_game_panel")
            if kw.get("close"):
                return {"closed": True}
            observed = self.observation(next(frame))
            if stuck:
                observed["resource_bars"]["bars"]["ore"]["value"] = 0
            if "screenshot" in kw:
                pathlib.Path(kw["screenshot"]).write_bytes(self.png)
            return observed

        return SimpleNamespace(
            client=SimpleNamespace(call=Mock(side_effect=call)), stage=self.stage, alive=Mock(return_value=None)
        )

    def test_capture_polls_readonly_then_captures_and_closes(self):
        session = self.fake_session()
        with patch.object(panel.time, "sleep") as sleep:
            panel.capture(session, self.out, "/offline/map.crp", self.wanted)
        calls = session.client.call.call_args_list
        self.assertEqual(sum(c.kwargs.get("select", False) for c in calls), 1)
        self.assertTrue(all("select" not in c.kwargs for c in calls if c.kwargs.get("bars_only")))
        self.assertTrue(calls[-1].kwargs["close"])
        self.assertEqual(sleep.call_count, 2)
        evidence = json.loads((self.out / "new-game-panel.json").read_text())
        panel.check_bar_settlement(evidence)

    def test_animation_timeout_records_zero_ore_and_closes_without_screenshot(self):
        session = self.fake_session(stuck=True)
        with patch.object(panel.time, "sleep"), patch.object(panel.time, "monotonic", side_effect=itertools.count()):
            with self.assertRaisesRegex(HarnessError, "ore bar value 0"):
                panel.capture(session, self.out, "/offline/map.crp", self.wanted, bar_timeout=3)
        calls = session.client.call.call_args_list
        self.assertTrue(calls[-1].kwargs["close"])
        self.assertFalse(any("screenshot" in c.kwargs for c in calls))
        evidence = json.loads((self.out / "new-game-panel.json").read_text())
        self.assertEqual(evidence["resource_bar_settlement"]["last"]["resource_bars"]["bars"]["ore"]["value"], 0)

    def test_dead_game_fails_before_readonly_poll(self):
        session = self.fake_session()
        session.alive.return_value = False
        with self.assertRaisesRegex(HarnessError, "process ended"):
            panel.wait_for_bars(session, "/offline/map.crp", {})
        session.client.call.assert_not_called()

    def test_selection_waits_only_for_explicit_native_pending(self):
        session = self.fake_session()
        observed = self.observation(19)
        session.client.call.side_effect = [
            {"pending": True, "phase": "opening native New Game modal"},
            {"pending": True, "phase": "opening native New Game Maps tab"},
            observed,
        ]
        evidence = {}
        with patch.object(panel.time, "sleep") as sleep:
            self.assertEqual(panel.select_map(session, "/offline/map.crp", evidence), observed)
        self.assertEqual(len(evidence["selection_attempts"]), 3)
        self.assertEqual(sleep.call_count, 2)

    def test_selection_pending_times_out_and_other_errors_are_not_retried(self):
        session = self.fake_session()
        session.client.call.side_effect = None
        session.client.call.return_value = {"pending": True, "phase": "opening"}
        with patch.object(panel.time, "sleep"), patch.object(panel.time, "monotonic", side_effect=itertools.count()):
            with self.assertRaisesRegex(HarnessError, "selection timed out"):
                panel.select_map(session, "/offline/map.crp", {}, timeout=2)
        session.client.call.reset_mock(side_effect=True)
        session.client.call.side_effect = HarnessError("map absent")
        with self.assertRaisesRegex(HarnessError, "map absent"):
            panel.select_map(session, "/offline/map.crp", {})
        self.assertEqual(session.client.call.call_count, 1)


if __name__ == "__main__":
    unittest.main()
