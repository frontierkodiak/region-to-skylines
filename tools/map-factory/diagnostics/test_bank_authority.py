import copy
import unittest

from bank_authority import corner_audit, deficits, review_basis, synthetic_check


class BankAuthorityTests(unittest.TestCase):
    def test_actual_review_verdict_schema_and_frozen_source_are_bound(self):
        receipt = {
            "schema": "polli.pl1191-stream-port-recipe-review/1",
            "review_issue": {"id": "01a1ffce-a05d-724a-976c-0365a699c6b4"},
            "claim_recommendation": {"verdict": "pass"},
            "bound_source": {
                "global_freeze": {
                    "sha256": "41d271ce72d0812d8408d6b2bbc4f5531329f500ce4320f3bd4365a8dc00dee7"
                }
            },
        }
        review_basis(receipt)
        receipt["bound_source"]["global_freeze"]["sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "reviewed freeze"):
            review_basis(receipt)

    def test_inside_corner_is_retired_original_bank_not_authorized_channel(self):
        nodes = [[100, 100], [100, 101], [101, 101]]
        original = copy.deepcopy(nodes)
        result = corner_audit(nodes)
        self.assertEqual(result["proposed_added_nodes_rc"], [[101, 100]])
        self.assertEqual(result["proposal_status"], "prohibited_footprint_expansion")
        self.assertEqual(result["retired_untouched_rim_nodes"], 1)
        self.assertIsNone(result["new_channel_or_rim"])
        self.assertEqual(nodes, original)

    def test_straight_reach_has_no_corner_or_changed_rim(self):
        result = corner_audit([(100, c) for c in range(100, 110)])
        self.assertEqual(result["proposal_status"], "no_change")
        self.assertEqual(result["retired_untouched_rim_nodes"], 0)

    def test_diagonal_staircase_does_not_establish_a_lateral_bank(self):
        result = corner_audit([(100, 100), (101, 101)])
        self.assertEqual(len(result["proposed_added_nodes_rc"]), 2)
        self.assertIn("unknown", result["bank_authority"])

    def test_refusal_magnitudes_keep_unknown_distinct_from_feasible_zero(self):
        self.assertIsNone(deficits({"status": "unresolved_cycle"}))
        self.assertEqual(deficits({"status": "feasible"})["max_m"], 0)
        result = deficits(
            {
                "status": "infeasible_bounds",
                "witnesses": [
                    {"lower_potential_q": 100, "greatest_possible_potential_q": 99},
                    {"lower_potential_q": 100, "greatest_possible_potential_q": 36},
                ],
            }
        )
        self.assertEqual(result["max_m"], 1)
        self.assertEqual(result["min_m"], 1 / 64)
        self.assertEqual(result["at_most_0_5m"], 1)

    def test_synthetic_byte_replay_preserves_original_physical_cohort(self):
        result = synthetic_check()
        self.assertTrue(result["original_grid_bytes_exact"])
        self.assertEqual(len(result["original_ports"]), 3)
        self.assertEqual(
            result["reviewer_corner_rule"]["proposal_status"],
            "prohibited_footprint_expansion",
        )
