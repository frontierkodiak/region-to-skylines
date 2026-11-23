import unittest

from field_protection_contract import obligation


class FieldContractTests(unittest.TestCase):
    def test_identity_never_clears_old_refusal(self):
        self.assertEqual(
            obligation("initial_depth", False, ["old_mapped_body_128m"], True),
            "identity_only_old_refusal_not_cleared",
        )
        self.assertEqual(
            obligation("old_control_raw43", True, []),
            "forbidden_existing_control_change",
        )

    def test_terrain_and_water_are_distinct_obligations_not_permission(self):
        mask = ["old_mapped_body_128m"]
        self.assertEqual(
            obligation("terrain", True, mask, True),
            "forbidden_under_retained_terrain_policy",
        )
        self.assertEqual(
            obligation("initial_depth", True, mask, True, True, True),
            "requires_explicit_owned_body_stage_initialization_safety_plan",
        )
        self.assertEqual(
            obligation("initial_depth", True, mask, False),
            "preserve_other_water_requires_explicit_joint_plan",
        )

    def test_buffer_does_not_become_a_water_footprint(self):
        self.assertEqual(
            obligation("initial_depth", True, ["old_mapped_body_128m"], True),
            "no_water_footprint_authority_from_own_body_buffer",
        )

    def test_own_target_does_not_waive_bank_or_infrastructure(self):
        self.assertEqual(
            obligation("initial_depth", True, ["original_stream_bank_union"], True),
            "forbidden_under_retained_untouched_bank_policy",
        )
        self.assertEqual(
            obligation(
                "initial_depth",
                True,
                ["old_mapped_body_128m", "old_corridor_112m"],
                True,
            ),
            "no_water_edit_authority_inferred_from_terrain_mask",
        )
        self.assertEqual(
            obligation("initial_depth", True, [], True, False),
            "requires_target_ownership_before_field_operation",
        )

    def test_no_new_velocity_or_implicit_unknown_field_api(self):
        self.assertEqual(
            obligation("initial_velocity", True, []),
            "preserve_no_new_velocity_operation_declared",
        )
        self.assertIn("undeployed_proposal", obligation("new_control_raw43", True, []))
        with self.assertRaises(ValueError):
            obligation("arbitrary_field", True, [])


if __name__ == "__main__":
    unittest.main()
