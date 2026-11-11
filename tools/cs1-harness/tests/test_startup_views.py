"""Mocked offline fixtures only: synthetic PNGs are never native game evidence."""

import copy
import itertools
import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from cs1_harness import mapcheck
from cs1_harness import startup_views as views
from cs1_harness import verdict
from cs1_harness.new_game_panel import digest


class StartupViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = pathlib.Path(self.temp.name)
        self.stage = self.out / "stage"
        self.stage.mkdir()
        self.wanted = {
            "opening": {"native_yaw_degrees": 0, "render_heading_degrees": 0},
            "area_zoom": {"native_yaw_degrees": 0, "render_heading_degrees": 0},
            "tolerance_degrees": 1,
        }
        self.initial = {
            "source": views.SOURCE,
            "phase": views.PHASE,
            "frame": 10,
            "camera": {"current_angle_degrees": [0, 60], "render_heading_degrees": 0, "areas_visible": False},
        }
        self.write("probes.json", {"startup_views": self.wanted})
        self.write("startup-world.json", self.initial)
        self.area = False
        self.fake_zoom = False
        self.fail_area_shot = False
        self.session = SimpleNamespace(
            stage=self.stage, alive=Mock(return_value=True), client=SimpleNamespace(call=Mock(side_effect=self.call))
        )
        self.addCleanup(patch.stopall)
        patch("cs1_harness.startup_views.time.sleep").start()

    def write(self, name, data):
        (self.out / name).write_text(json.dumps(data))

    def call(self, op, **kw):
        if op == "stats":
            return {"paused": False}
        if op == "run":
            return {"paused": kw["paused"]}
        if op == "world_observe":
            observation = copy.deepcopy(self.initial)
            observation["camera"]["areas_visible"] = self.area
            observation["camera"]["current_size"] = 10000 if self.fake_zoom else 1000
            return observation
        if op == "area_zoom":
            self.area = kw["enabled"] and not self.fake_zoom
            return {
                "source": "native ToolsModifierControl",
                "areas_visible": self.area,
                "tool": "GameAreaTool" if self.area else "DefaultTool",
            }
        if op == "screenshot":
            if self.fail_area_shot and self.area:
                raise RuntimeError("fixture capture failure")
            image = Image.new("RGB", (32, 32), "green" if not self.area else "blue")
            image.paste("white", (0, 0, 16, 16))
            image.save(kw["path"])
            return {"path": kw["path"], "frame": 10}
        raise AssertionError(f"unallowed op {op}")

    def captured(self):
        evidence = views.capture(self.session, self.out, self.wanted)
        for shot in self.stage.iterdir():
            shot.rename(self.out / shot.name)
        review = {"reviewer": "offline fixture only", "notes": "synthetic, not native evidence"}
        for name in views.VIEWS:
            review[name] = {
                "sha256": evidence["views"][name]["sha256"],
                "view_matches": True,
                "areas_ui_visible": name == "area_zoom",
            }
        self.write("startup-views-review.json", review)
        return evidence

    def test_valid_observations_enter_verdict_and_never_aim_camera(self):
        self.captured()
        self.write("report.json", {})
        row = next(row for row in verdict.judge(self.out, write=False)["checks"] if row["name"] == "startup_views")
        self.assertEqual(row["status"], "pass", row)
        self.assertFalse(self.area)
        calls = self.session.client.call.call_args_list
        self.assertNotIn("camera", [call.args[0] for call in calls])
        self.assertEqual(
            [call.kwargs for call in calls if call.args[0] == "area_zoom"], [{"enabled": True}, {"enabled": False}]
        )
        self.assertEqual(calls[-1].kwargs, {"paused": False})

    def test_driver_invokes_capture_after_startup_world_before_run_or_camera_override(self):
        artifact = self.out / "fixture.crp"
        artifact.touch()
        session = SimpleNamespace(
            client=Mock(),
            install_map=Mock(return_value=artifact),
            launch=Mock(return_value={}),
            cfg=SimpleNamespace(),
            alive=Mock(),
        )
        session.client.call.side_effect = lambda op, **kw: (
            {"maps": [{"path": str(artifact), "map_name": "fixture", "published": True}]}
            if op == "maps"
            else copy.deepcopy(self.initial)
            if op == "world_observe"
            else {}
        )
        session.client.wait.return_value = {"in_game": True, "loading": False}

        def stop_after_capture(*args):
            observed = json.loads((self.out / "startup-world.json").read_text())
            self.assertEqual(observed["phase"], views.PHASE)
            self.assertEqual(
                [call.args[0] for call in session.client.call.call_args_list], ["maps", "new_game", "world_observe"]
            )
            raise RuntimeError("fixture boundary reached")

        driver = mapcheck.MapCheck(session, self.out, [], [], log=lambda line: None)
        self.addCleanup(driver.timeline.close)
        driver.panel_expectations = {"fixture": "panel ordering only"}

        def panel_before_new_game(*args):
            self.assertEqual([call.args[0] for call in session.client.call.call_args_list], ["maps"])

        with (
            patch("cs1_harness.mapcheck.observe.write_context"),
            patch("cs1_harness.mapcheck.startup_views.capture", side_effect=stop_after_capture),
            patch("cs1_harness.mapcheck.new_game_panel.capture", side_effect=panel_before_new_game) as panel,
        ):
            with self.assertRaisesRegex(RuntimeError, "fixture boundary reached"):
                driver.execute(artifact, 1, 1, 1, 1, 1, 1, scenario="test-city")
        panel.assert_called_once()

    def test_main_ground_truth_samples_native_world_in_40_by_40_grid(self):
        session = SimpleNamespace(stage=self.stage, client=Mock())
        session.client.call.side_effect = lambda op, **kw: {
            "samples": [{"terrain": x + 2 * z} for x, z in kw["points"]]
        }
        driver = mapcheck.MapCheck(session, self.out, [], [])
        self.addCleanup(driver.timeline.close)
        driver.world_heights()
        calls = session.client.call.call_args_list
        self.assertEqual([call.args[0] for call in calls], ["water"] * 4)
        data = json.loads((self.stage / "grids" / "t000-terrain-points.json").read_text())
        self.assertIn("TerrainManager.SampleRawHeightSmooth", data["source"])
        self.assertEqual(len(data["points"]), 1600)
        self.assertEqual(data["points"][:2], [[-8424, -8424], [-7992, -8424]])
        self.assertEqual(data["points"][-1], [8424, 8424])
        self.assertEqual(len({p[0] for p in data["points"]}), 40)
        self.assertEqual(len({p[1] for p in data["points"]}), 40)
        self.assertEqual(data["heights"][0], -25272)
        self.assertEqual(data["heights"][-1], 25272)

    def test_wrong_heading_fails_for_each_view_and_readback(self):
        original = self.captured()
        for name in views.VIEWS:
            for field in ("current_angle_degrees", "render_heading_degrees"):
                with self.subTest(view=name, field=field):
                    evidence = copy.deepcopy(original)
                    for sample in evidence["views"][name]["samples"] + [evidence["views"][name]["after"]]:
                        sample["camera"][field] = [90, 60] if field == "current_angle_degrees" else 90
                    self.write("startup-views.json", evidence)
                    self.assertIn("outside explicit tolerance", views.assess(self.out)["detail"])

    def test_fake_max_zoom_without_areas_visible_times_out_and_closes(self):
        self.fake_zoom = True
        with patch("cs1_harness.startup_views.time.monotonic", side_effect=itertools.count()):
            with self.assertRaisesRegex(RuntimeError, "AreasVisible=True"):
                views.capture(self.session, self.out, self.wanted, timeout=4)
        self.assertFalse(self.area)
        evidence = json.loads((self.out / "startup-views.json").read_text())
        self.assertEqual(evidence["close"]["tool"], "DefaultTool")
        self.assertIn("AreasVisible=True", evidence["error"])

    def test_area_screenshot_failure_always_closes_and_records_failure(self):
        self.fail_area_shot = True
        with self.assertRaisesRegex(RuntimeError, "fixture capture failure"):
            views.capture(self.session, self.out, self.wanted)
        self.assertFalse(self.area)
        self.assertEqual(views.assess(self.out)["status"], "fail")
        evidence = json.loads((self.out / "startup-views.json").read_text())
        self.assertFalse(evidence["close"]["areas_visible"])
        self.assertEqual(len(evidence["closed_samples"]), 3)

    def test_cleanup_failure_cannot_pass(self):
        evidence = self.captured()
        evidence["close"]["areas_visible"] = True
        self.write("startup-views.json", evidence)
        self.assertEqual(views.assess(self.out)["status"], "fail")

    def test_max_zoom_fixture_cannot_satisfy_areas_verdict(self):
        evidence = self.captured()
        for sample in evidence["views"]["area_zoom"]["samples"]:
            sample["camera"].update(areas_visible=False, current_size=10000)
        self.write("startup-views.json", evidence)
        self.assertIn("AreasVisible", views.assess(self.out)["detail"])

    def test_wrong_phase_and_altered_initial_identity_fail(self):
        original = self.captured()
        evidence = copy.deepcopy(original)
        evidence["phase"] = "after_camera_override"
        self.write("startup-views.json", evidence)
        self.assertIn("phase", views.assess(self.out)["detail"])
        self.write("startup-views.json", original)
        self.initial["camera"]["current_angle_degrees"][0] = 90
        self.write("startup-world.json", self.initial)
        self.assertIn("identity changed", views.assess(self.out)["detail"])

    def test_pngs_require_visual_review_and_unchanged_hashes(self):
        self.captured()
        review = json.loads((self.out / "startup-views-review.json").read_text())
        (self.out / "startup-views-review.json").unlink()
        self.assertIn("unreviewed", views.assess(self.out)["detail"])
        self.write("startup-views-review.json", review)
        with (self.out / "startup-area_zoom.png").open("ab") as shot:
            shot.write(b"changed")
        self.assertIn("changed since capture", views.assess(self.out)["detail"])

    def test_capture_metadata_and_png_dimensions_must_match(self):
        original = self.captured()
        for key, value in (
            ("screenshot", "other.png"),
            ("size", [64, 64]),
            ("capture", {"path": "other.png", "frame": 10}),
        ):
            evidence = copy.deepcopy(original)
            evidence["views"]["opening"][key] = value
            self.write("startup-views.json", evidence)
            self.assertEqual(views.assess(self.out)["status"], "fail")

    def test_nonfinite_and_unstable_observations_fail(self):
        original = self.captured()
        for angle in (float("nan"), 2):
            evidence = copy.deepcopy(original)
            evidence["views"]["area_zoom"]["samples"][0]["camera"]["render_heading_degrees"] = angle
            self.write("startup-views.json", evidence)
            self.assertEqual(views.assess(self.out)["status"], "fail")

    def test_bad_requests_and_missing_evidence_fail_but_absent_request_skips(self):
        for wanted in (
            {},
            {**self.wanted, "tolerance_degrees": 180},
            {**self.wanted, "opening": {"native_yaw_degrees": 0}},
        ):
            self.write("probes.json", {"startup_views": wanted})
            self.assertEqual(views.assess(self.out)["status"], "fail")
        self.write("probes.json", {"startup_views": self.wanted})
        self.assertEqual(views.assess(self.out)["status"], "fail")
        self.write("probes.json", {})
        self.assertEqual(views.assess(self.out)["status"], "skip")

    def test_wrapped_headings_compare_circularly(self):
        self.captured()
        self.wanted["opening"].update(native_yaw_degrees=360, render_heading_degrees=-360)
        self.write("probes.json", {"startup_views": self.wanted})
        self.assertEqual(views.assess(self.out)["status"], "pass")

    def test_invalid_png_cannot_pass_even_when_rehashed(self):
        evidence = self.captured()
        shot = self.out / "startup-opening.png"
        shot.write_bytes(b"not a PNG")
        evidence["views"]["opening"]["sha256"] = digest(shot)
        self.write("startup-views.json", evidence)
        self.assertEqual(views.assess(self.out)["status"], "fail")


if __name__ == "__main__":
    unittest.main()
