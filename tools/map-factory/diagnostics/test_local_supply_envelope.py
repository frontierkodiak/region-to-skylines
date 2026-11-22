import unittest

import numpy as np

from local_supply_envelope import component_envelope


class EnvelopeTests(unittest.TestCase):
    def test_single_safe_footprint_does_not_hide_open_unmapped_domain(self):
        floor = np.full((7, 7), 200, np.int64)
        floor[3, :] = 0
        initial = np.zeros_like(floor)
        initial[3, 3] = 96
        mapped = np.zeros_like(floor, bool)
        mapped[3, 3] = True
        result = component_envelope(floor, initial, mapped, 96, [24], 4)[0]
        self.assertEqual(result["nodes"], 7)
        self.assertEqual(result["initially_dry_unmapped_nodes"], 6)
        self.assertTrue(result["touches_square_boundary"])
        self.assertIn(
            "substage_domain_includes_unmapped_ground", result["geometry_reasons"]
        )

    def test_diagonal_alternative_is_retained(self):
        floor = np.full((5, 5), 200, np.int64)
        floor[2, 2] = floor[1, 1] = floor[0, 0] = 0
        initial = np.full_like(floor, 96)
        mapped = np.ones_like(floor, bool)
        a = component_envelope(floor, initial, mapped, 96, [12], 4)[0]
        b = component_envelope(floor, initial, mapped, 96, [12], 8)[0]
        self.assertEqual((a["nodes"], b["nodes"]), (1, 3))
        self.assertFalse(a["touches_square_boundary"])
        self.assertTrue(b["touches_square_boundary"])

    def test_full_rim_includes_diagonal_bank_and_fixed_half_metre(self):
        floor = np.full((5, 5), 200, np.int64)
        floor[2, 2] = 0
        floor[1, 1] = 127
        result = component_envelope(
            floor, np.zeros_like(floor), np.ones_like(floor, bool), 96, [12], 4
        )[0]
        self.assertEqual(result["full_rim_freeboard_q"], 31)
        self.assertEqual(result["rim_witness_rc"], [1, 1])
        self.assertIn(
            "full_untouched_exterior_half_metre_freeboard_not_met",
            result["geometry_reasons"],
        )

    def test_dry_unmapped_counts_do_not_select_domain(self):
        floor = np.full((5, 5), 200, np.int64)
        floor[2, 1:4] = 0
        a = component_envelope(
            floor, np.zeros_like(floor), np.zeros_like(floor, bool), 96, [12], 4
        )[0]
        b = component_envelope(
            floor, np.full_like(floor, 96), np.zeros_like(floor, bool), 96, [12], 4
        )[0]
        self.assertEqual(a["nodes_i32_sha256"], b["nodes_i32_sha256"])
        self.assertEqual(
            (a["initially_dry_unmapped_nodes"], b["initially_dry_unmapped_nodes"]),
            (3, 0),
        )


if __name__ == "__main__":
    unittest.main()
