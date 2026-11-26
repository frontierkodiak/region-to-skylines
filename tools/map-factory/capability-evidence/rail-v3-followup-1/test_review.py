"""A later exit audit must not erase or freely waive a teardown finding."""

import copy
import unittest

import review


class CleanupReviewTest(unittest.TestCase):
    def test_only_a_recorded_absent_steam_remainder_gets_a_degraded_state(self):
        cleanup = {"game": [], "units_active": [], "steam_instances": ["old-instance"]}
        original = copy.deepcopy(cleanup)
        audit = {
            "reported_steam_remainders": ["old-instance"],
            "reported_steam_remainders_still_present": [],
        }
        self.assertIn("later audit", review.cleanup_state(cleanup, audit))
        self.assertEqual(cleanup, original)
        audit["reported_steam_remainders_still_present"] = ["old-instance"]
        with self.assertRaisesRegex(ValueError, "not proven absent"):
            review.cleanup_state(cleanup, audit)
        audit["reported_steam_remainders_still_present"] = []
        audit["reported_steam_remainders"] = []
        with self.assertRaisesRegex(ValueError, "not proven absent"):
            review.cleanup_state(cleanup, audit)

    def test_game_units_or_missing_facts_are_not_waived(self):
        for cleanup in [
            {"game": [123], "units_active": [], "steam_instances": []},
            {"game": [], "units_active": ["unit"], "steam_instances": []},
            {},
        ]:
            with self.subTest(cleanup=cleanup), self.assertRaises(ValueError):
                review.cleanup_state(cleanup, {})

    def test_real_artifact_retains_finding_and_all_attempts(self):
        proof = review.verify()
        self.assertTrue(proof["stock_gate"])
        self.assertEqual(len(proof["cohort"]), 9)
        self.assertEqual(len(proof["cohort"]["rio"]["attempts"]), 2)
        self.assertEqual(
            proof["cleanup_findings"][0]["raw_cleanup"]["steam_instances"],
            ["3933505219"],
        )


if __name__ == "__main__":
    unittest.main()
