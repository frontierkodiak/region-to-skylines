"""A changed player, missing attempt or wrong package cannot earn a comparison."""

import json
from pathlib import Path
import tempfile
import unittest

from report_playable_starts import compare


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def attempt(folder, *, status="pass", package="map", player="qualified-player"):
    write(
        folder / "verdict.json",
        {
            "verdict": status,
            "checks": [
                {
                    "name": "first_hour",
                    "status": status,
                    "value": {},
                }
            ],
        },
    )
    write(
        folder / "session-receipt.json",
        {
            "map": {"sha256": package},
            "mod_sha256": player,
        },
    )


class CohortComparison(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.stock, self.before, self.after = [
            self.root / name for name in ("stock", "before", "after")
        ]
        self.cohort = {
            "issue": "test",
            "original": [{"slug": "original"}],
            "fresh": [{"slug": "holdout"}],
            "controls": [
                {"name": name, "sha256": "map"} for name in ("Stock A", "Stock B")
            ],
        }
        for slug in ("stock-a", "stock-b"):
            attempt(self.stock / slug)
        for root in (self.before, self.after):
            write(
                root / "cpu-report.json",
                {
                    "cases": {
                        slug: {"stage": {"crp_sha256": "map"}}
                        for slug in ("original", "holdout")
                    }
                },
            )
            for slug in ("original", "holdout"):
                attempt(root / "native" / slug)

    def result(self):
        return compare(self.cohort, self.stock, self.before, self.after)

    def test_complete_same_player_comparison_is_qualified(self):
        result = self.result()
        self.assertTrue(result["paired_comparison_qualified"])
        self.assertEqual(result["before"]["qualified_pass_rate"], 1)

    def test_missing_holdout_is_unresolved_not_a_failure_or_completed_rate(self):
        (self.after / "native/holdout/verdict.json").unlink()
        result = self.result()
        self.assertFalse(result["paired_comparison_qualified"])
        self.assertEqual(result["after"]["failed"], 0)
        self.assertEqual(result["after"]["unresolved"], 1)
        self.assertIsNone(result["after"]["qualified_pass_rate"])

    def test_stock_failure_withholds_map_attribution_even_when_all_maps_pass(self):
        attempt(self.stock / "stock-b", status="fail")
        result = self.result()
        self.assertFalse(result["stock_policy_qualified"])
        self.assertEqual(result["map_fault_attribution"], "withheld")
        self.assertIsNone(result["before"]["qualified_pass_rate"])

    def test_old_policy_cannot_become_a_qualified_baseline(self):
        attempt(self.before / "native/original", player="old-player")
        result = self.result()
        self.assertTrue(result["stock_policy_qualified"])
        self.assertFalse(result["paired_comparison_qualified"])
        self.assertFalse(result["before"]["same_qualified_player"])
        self.assertIsNone(result["before"]["qualified_pass_rate"])

    def test_wrong_package_cannot_count_as_a_pass(self):
        attempt(self.after / "native/holdout", package="another-square")
        result = self.result()
        self.assertEqual(
            result["cases"]["holdout"]["after"]["status"], "source_mismatch"
        )
        self.assertEqual(result["after"]["passed"], 1)
        self.assertFalse(result["paired_comparison_qualified"])

    def test_one_stock_control_is_insufficient(self):
        self.cohort["controls"].pop()
        self.assertFalse(self.result()["stock_policy_qualified"])

    def test_healthy_opening_cannot_hide_another_failed_native_gate(self):
        path = self.after / "native/holdout/verdict.json"
        verdict = json.loads(path.read_text())
        verdict["verdict"] = "fail"
        verdict["checks"].append({"name": "ground_truth", "status": "fail"})
        write(path, verdict)
        result = self.result()
        self.assertEqual(result["cases"]["holdout"]["after"]["first_hour"], "pass")
        self.assertEqual(result["after"]["failed"], 1)
        self.assertEqual(result["after"]["qualified_pass_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
