"""Immutable field constraints belong inside the construction solve."""

import unittest
from immutable_initialization_profile import pinned_profile
from open_interface_authority import cell_consistency


class ImmutableProfileTests(unittest.TestCase):
    def test_pin_can_preserve_fields_that_greatest_unpinned_profile_would_edit(self):
        a = pinned_profile([100, 100], [96, 96], [196, 196], [240, 240], [(0, 1)], [0])
        self.assertEqual(a["status"], "feasible")
        self.assertEqual(a["target_q"], [196, 196])
        self.assertEqual(a["bed_q"], [100, 100])
        self.assertEqual(a["depth_q"], [96, 96])

    def test_protected_dry_source_node_is_not_silently_filled_or_depth_relaxed(self):
        a = pinned_profile([100], [0], [96], [250], [], [0])
        self.assertEqual(a["status"], "refused_protected_initial_depth_below_design96q")
        self.assertIsNone(a["target_q"])
        self.assertEqual(a["witnesses"][0]["initial_depth_q"], 0)

    def test_protected_deeper_initial_water_preserved_exactly(self):
        a = pinned_profile([100], [140], [140], [300], [], [0])
        self.assertEqual(a["target_q"], [240])
        self.assertEqual(a["bed_q"], [100])
        self.assertEqual(a["depth_q"], [140])

    def test_conflicting_pin_direction_is_refused_not_reoriented(self):
        a = pinned_profile(
            [100, 120], [96, 96], [196, 216], [300, 300], [(0, 1)], [0, 1]
        )
        self.assertEqual(a["status"], "infeasible_bounds")

    def test_original_bank_cap_is_not_overridden_by_pin(self):
        a = pinned_profile([100], [96], [196], [195], [], [0])
        self.assertEqual(a["status"], "infeasible_bounds")

    def test_cycle_remains_unknown_even_with_consistent_pins(self):
        a = pinned_profile(
            [100, 100], [96, 96], [196, 196], [250, 250], [(0, 1), (1, 0)], [0]
        )
        self.assertEqual(a["status"], "unresolved_cycle")

    def test_native_target_range_does_not_wrap(self):
        a = pinned_profile([65535], [96], [96], [65535], [], [0])
        self.assertEqual(a["status"], "infeasible_bounds")

    def test_unprotected_cut_and_duplicate_cell_conflict_stay_guarded(self):
        a = pinned_profile([300], [0], [204], [204], [], [])
        self.assertEqual(a["bed_q"], [108])
        self.assertEqual(a["depth_q"], [96])
        self.assertFalse(
            cell_consistency([[1, 1], [1, 1]], [204, 205], [108, 109])["single_valued"]
        )


if __name__ == "__main__":
    unittest.main()
