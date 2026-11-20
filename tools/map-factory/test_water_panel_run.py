"""Check collection boundaries before a long native cohort is launched."""

from pathlib import Path
import tempfile
import unittest

from refresh_water_risk import sha, write
from run_water_panel import validate


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

    def save(self):
        write(self.run / "report.json", self.report)

    def test_a_complete_water_failure_is_still_collected(self):
        write(
            self.run / "verdict.json",
            {"status": "fail", "checks": [{"name": "no_flooding", "status": "fail"}]},
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


if __name__ == "__main__":
    unittest.main()
