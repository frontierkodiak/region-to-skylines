"""Role checks retain field identities and the separate legacy comparator."""

import unittest
import numpy as np
from immutable_water_role_profile import role_operation, role_profile, role_requirements


class ExistingWaterRoleTests(unittest.TestCase):
    def test_old_one_metre_pin_stays_exact_and_legacy_check_stays_false(self):
        a = role_profile([100], [64], [64], [300], [], [0])
        self.assertEqual(a["target_q"], [164])
        self.assertEqual(a["bed_q"], [100])
        self.assertEqual(a["depth_q"], [64])
        o = role_operation(
            [1, 1], 100, 64, 100, 164, ["old_control_radius_plus64m"], 64
        )
        self.assertTrue(o["explicit_role_bound_valid"])
        self.assertFalse(o["legacy_96q_design_comparator"])
        self.assertFalse(o["serialized_no_fill_cut3_depth1_5_valid"])
        self.assertEqual(o["changed_fields"], [])
        self.assertNotIn("reference_hydraulic_floor_q", o)
        self.assertIsNone(o["observed_native_floor_q"])

    def test_unprotected_nodes_keep_the96q_minimum(self):
        self.assertEqual(
            role_requirements(np.array([64, 80, 140]), [1]).tolist(), [96, 80, 140]
        )
        a = role_profile([100], [64], [96], [164], [], [])
        self.assertEqual(a["depth_q"], [96])
        self.assertEqual(a["bed_q"], [68])
        o = role_operation([1, 1], 100, 64, 68, 164, [], 96)
        self.assertTrue(o["legacy_96q_design_comparator"])

    def test_sub_one_metre_pin_is_refused_not_repaired_or_called_surface(self):
        for w in [0, 7, 32, 63]:
            a = role_profile([100], [w], [w], [300], [], [0])
            self.assertEqual(
                a["status"], "refused_protected_initial_depth_below_fixed64q"
            )
            self.assertIsNone(a["target_q"])

    def test_protected_existing_one_point_two_five_metres_is_not_raised(self):
        a = role_profile([100], [80], [80], [300], [], [0])
        self.assertEqual(a["depth_q"], [80])
        self.assertEqual(a["bed_q"], [100])

    def test_no_role_or_protection_minimum_bypass(self):
        with self.assertRaises(ValueError):
            role_operation([1, 1], 100, 64, 100, 164, [], 64)
        with self.assertRaises(ValueError):
            role_operation([1, 1], 100, 63, 100, 163, ["bank"], 63)
        o = role_operation([1, 1], 100, 64, 99, 164, ["bank"], 64)
        self.assertFalse(o["explicit_role_bound_valid"])
        self.assertTrue(o["protected_edits"])

    def test_bank_cap_is_not_overridden_by_initialization_pin(self):
        a = role_profile([100], [64], [64], [163], [], [0])
        self.assertEqual(a["status"], "infeasible_bounds")

    def test_conflicting_direction_pins_not_reoriented(self):
        a = role_profile([100, 120], [64, 64], [64, 64], [300, 300], [(0, 1)], [0, 1])
        self.assertEqual(a["status"], "infeasible_bounds")

    def test_cycles_remain_unresolved(self):
        a = role_profile(
            [100, 100], [64, 64], [64, 64], [300, 300], [(0, 1), (1, 0)], [0, 1]
        )
        self.assertEqual(a["status"], "unresolved_cycle")

    def test_target_uint16_does_not_wrap(self):
        a = role_profile([65535], [64], [64], [65535], [], [0])
        self.assertEqual(a["status"], "infeasible_bounds")


if __name__ == "__main__":
    unittest.main()
