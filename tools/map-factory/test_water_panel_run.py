"""Check collection boundaries before a long native cohort is launched."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from refresh_water_risk import sha, write
from run_water_panel import IncompleteNativeRun, run_panel, validate


class NativeCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.staged, self.run = self.root / "staged", self.root / "run"
        self.staged.mkdir()
        self.run.mkdir()
        (self.run / "grids").mkdir()
        for name in (
            "map.crp",
            "terrain.u16",
            "water.u16",
            "probes.json",
            "mapped-water.u8",
        ):
            (self.staged / name).write_bytes(name.encode())
        self.item = {
            "slug": "any-square",
            "package": "map.crp",
            "files_sha256": {p.name: sha(p) for p in self.staged.iterdir()},
        }
        for name in ("terrain.u16", "water.u16"):
            (self.run / "grids" / ("t000-" + name)).write_bytes(
                (self.staged / name).read_bytes()
            )
        for target, source in (
            ("probes.json", "probes.json"),
            ("mapped-water.u8", "mapped-water.u8"),
            ("reference-water.u16", "water.u16"),
        ):
            (self.run / target).write_bytes((self.staged / source).read_bytes())
        self.report = {
            "game_minutes": 60.1,
            "curve": [{"population": 0}],
            "session": {
                "map": {"sha256": sha(self.staged / "map.crp")},
                "cleanup": {"game": [], "steam_instances": [], "units_active": []},
                "carbon_preflight": {"idle": True},
                "offline_steam": {"fresh_syncs": 1},
            },
        }
        self.save()
        write(self.run / "verdict.json", {"verdict": "pass", "checks": []})
        write(self.run / "harness-source.json", {"commit": "pinned", "dirty": False})

    def save(self):
        write(self.run / "report.json", self.report)

    def test_a_complete_water_failure_is_still_collected(self):
        write(
            self.run / "verdict.json",
            {"verdict": "fail", "checks": [{"name": "no_flooding", "status": "fail"}]},
        )
        self.assertEqual(validate(self.item, self.staged, self.run), self.report)

    def test_short_or_populated_runs_are_not_ground_truth_negatives(self):
        self.report["game_minutes"] = 59.9
        self.save()
        with self.assertRaisesRegex(ValueError, "shorter than sixty"):
            validate(self.item, self.staged, self.run)
        self.report.update(game_minutes=60.1, curve=[{"population": 1}])
        self.save()
        with self.assertRaisesRegex(ValueError, "Populated city"):
            validate(self.item, self.staged, self.run)

    def test_missing_account_or_cleanup_evidence_stops_collection(self):
        for key, replacement, message in (
            ("carbon_preflight", {}, "carbon-idle"),
            ("offline_steam", {}, "offline evidence"),
            ("cleanup", {"game": [123]}, "lifecycle"),
        ):
            with self.subTest(key=key):
                original = self.report["session"][key]
                self.report["session"][key] = replacement
                self.save()
                with self.assertRaisesRegex(ValueError, message):
                    validate(self.item, self.staged, self.run)
                self.report["session"][key] = original

    def test_changed_initial_grid_or_reference_cannot_be_adopted(self):
        for relative in (
            "grids/t000-water.u16",
            "reference-water.u16",
            "mapped-water.u8",
            "probes.json",
        ):
            with self.subTest(path=relative):
                path = self.run / relative
                original = path.read_bytes()
                path.write_bytes(b"changed")
                with self.assertRaises(ValueError):
                    validate(self.item, self.staged, self.run)
                path.write_bytes(original)

    def test_error_or_absent_verdict_is_not_a_complete_observation(self):
        write(self.run / "verdict.json", {"verdict": "error"})
        with self.assertRaises(IncompleteNativeRun):
            validate(self.item, self.staged, self.run)
        (self.run / "verdict.json").unlink()
        with self.assertRaises(IncompleteNativeRun):
            validate(self.item, self.staged, self.run)

    def test_per_run_harness_identity_and_offline_errors_are_enforced(self):
        with self.assertRaisesRegex(ValueError, "Per-run harness"):
            validate(self.item, self.staged, self.run, "wrong")
        self.report["session"]["offline_steam_error"] = "contradictory online state"
        self.save()
        with self.assertRaisesRegex(ValueError, "offline evidence"):
            validate(self.item, self.staged, self.run)

    def fixture_panel(self, name):
        root = self.root / name
        staging, native = root / "staging", root / "native"
        shutil.copytree(self.staged, staging / "any-square")
        write(
            staging / "staging.json", {"squares": [{**self.item, "status": "prepared"}]}
        )
        plan = root / "plan.json"
        write(
            plan,
            {
                "staging_sha256": sha(staging / "staging.json"),
                "harness_source": "pinned",
            },
        )
        checkout = root / "checkout"
        harness = checkout / "tools/cs1-harness"
        (harness / "cs1_harness").mkdir(parents=True)
        (harness / "pyproject.toml").write_text("")
        (harness / "cs1_harness/cli.py").write_text("")
        return staging, native, plan, checkout, harness

    def drive(self, name, outcomes, max_new=None):
        staging, native, plan, checkout, harness = self.fixture_panel(name)
        if max_new is not None:
            manifest = json.loads((staging / "staging.json").read_text())
            manifest["squares"].append(
                {**manifest["squares"][0], "slug": "second-square"}
            )
            shutil.copytree(staging / "any-square", staging / "second-square")
            write(staging / "staging.json", manifest)
            write(
                plan,
                {
                    "staging_sha256": sha(staging / "staging.json"),
                    "harness_source": "pinned",
                },
            )
        calls = []

        def fake_run(command, **kwargs):
            if command[0] == "git":
                return subprocess.CompletedProcess(command, 0)
            self.assertIn("--require-offline", command)
            self.assertEqual(command[command.index("--project") + 1], str(harness))
            output = Path(command[command.index("--out") + 1])
            self.assertFalse((native / "any-square").exists())
            shutil.copytree(self.run, output, dirs_exist_ok=True)
            write(output / "session-receipt.json", self.report["session"])
            outcome = outcomes[len(calls)]
            calls.append(outcome)
            if outcome == "missing":
                (output / "verdict.json").unlink()
            elif outcome == "error":
                write(output / "verdict.json", {"verdict": "error"})
            else:
                write(output / "verdict.json", {"verdict": "fail", "checks": []})
            return subprocess.CompletedProcess(
                command,
                outcome
                if isinstance(outcome, int)
                else 70
                if outcome in {"missing", "error"}
                else 0,
            )

        def fake_git(command, **kwargs):
            return str(checkout) + "\n" if "--show-toplevel" in command else "pinned\n"

        original_alias = Path.symlink_to

        def alias_last(path, target, **kwargs):
            journal = native.parent / "native-driver.jsonl"
            self.assertTrue(journal.is_file())
            receipt = json.loads(journal.read_text().splitlines()[-1])
            self.assertEqual(
                receipt["verdict_sha256"], sha(native / target / "verdict.json")
            )
            return original_alias(path, target, **kwargs)

        with (
            patch("run_water_panel.subprocess.check_output", side_effect=fake_git),
            patch("run_water_panel.subprocess.run", side_effect=fake_run),
            patch.object(Path, "symlink_to", alias_last),
        ):
            if isinstance(outcomes[0], int):
                with self.assertRaisesRegex(RuntimeError, "guard stopped"):
                    run_panel(staging, native, checkout, plan)
                self.assertEqual(len(calls), 1)
                self.assertFalse((native / "any-square").exists())
                self.assertFalse((native.parent / "native-driver.jsonl").exists())
            else:
                run_panel(staging, native, checkout, plan, max_new=max_new)
                self.assertEqual(len(calls), len(outcomes))
                self.assertEqual(
                    (native / "any-square").resolve(),
                    native / f"any-square-attempt-{len(outcomes)}",
                )
                self.assertEqual(
                    len(
                        (native.parent / "native-driver.jsonl").read_text().splitlines()
                    ),
                    1,
                )
        return staging, native, plan, checkout

    def test_tranche_returns_after_a_complete_unit_without_launching_the_next(self):
        _, native, _, _ = self.drive("bounded", ["complete"], max_new=1)
        self.assertFalse((native / "second-square").exists())

    def test_restart_does_not_adopt_an_unreceipted_alias(self):
        staging, native, plan, checkout = self.drive("unreceipted", ["complete"])
        (native.parent / "native-driver.jsonl").unlink()

        def fake_git(command, **kwargs):
            return str(checkout) + "\n" if "--show-toplevel" in command else "pinned\n"

        with (
            patch("run_water_panel.subprocess.check_output", side_effect=fake_git),
            patch(
                "run_water_panel.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "matching collection receipt"):
                run_panel(staging, native, checkout, plan)

    def test_runner_retries_error_and_missing_verdict_but_not_water_failure(self):
        self.drive("error", ["error", "complete"])
        self.drive("missing", ["missing", "complete"])
        self.drive("water-failure", ["complete"])

    def test_runner_never_retries_account_guard_stops(self):
        self.drive("guard75", [75])
        self.drive("guard77", [77])

    def test_unknown_only_slug_cannot_silently_pass(self):
        staging, native, plan, checkout, _ = self.fixture_panel("unknown-only")
        with patch("run_water_panel.subprocess.run") as process:
            with self.assertRaisesRegex(ValueError, "prepared panel square"):
                run_panel(staging, native, checkout, plan, only="typo")
            process.assert_not_called()

    def test_nonpositive_tranche_limit_cannot_silently_pass(self):
        with patch("run_water_panel.subprocess.run") as process:
            with self.assertRaisesRegex(ValueError, "positive"):
                run_panel(self.root, self.root, self.root, self.root, max_new=0)
            process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
