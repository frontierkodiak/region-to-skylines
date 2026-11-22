import unittest

import numpy as np

from stage_contracts import common_stage, contract_model, escape_field, merge_intervals


class StageTests(unittest.TestCase):
    def test_minimax_finds_saddle_not_nearest_high_bank(self):
        floor = np.full((5, 5), 160, np.int64)
        floor[2, 2], floor[2, 0:2] = 0, 96
        spill, parent = escape_field(floor, 4)
        self.assertEqual(spill[2, 2], 96)
        node, highest = 12, 0
        while True:
            highest = max(highest, int(floor.ravel()[node]))
            other = int(parent.ravel()[node])
            if other == node:
                break
            node = other
        self.assertEqual(highest, 96)

    def test_diagonal_escape_models_kept_separate(self):
        floor = np.full((3, 3), 128, np.int64)
        floor[0, 0], floor[1, 1] = 80, 0
        self.assertEqual(escape_field(floor, 4)[0][1, 1], 128)
        self.assertEqual(escape_field(floor, 8)[0][1, 1], 80)

    def test_ninety_five_percent_is_per_contract_not_pooled(self):
        self.assertTrue(
            common_stage([[(64, 96)]] * 19 + [[]], 0.95)["numeric_fit_only"]
        )
        self.assertFalse(
            common_stage([[(64, 96)]] * 18 + [[], []], 0.95)["numeric_fit_only"]
        )
        self.assertFalse(common_stage([[]], 0.95)["numeric_fit_only"])

    def test_disjoint_cell_support_not_duplicate_point_votes(self):
        model = common_stage([[(1, 4), (2, 6)], [(8, 10)]], 1)
        self.assertFalse(model["numeric_fit_only"])
        self.assertEqual(model["maximum_simultaneous_points"], 1)
        self.assertEqual(merge_intervals([(5, 3), (1, 4), (3, 6)]), [[1, 6]])

    def test_seven_q_natural_depth_and_exact_half_metre_anchor(self):
        floor = np.full((1081, 1081), 6400, np.uint16)
        depth = np.full_like(floor, 7)
        cap = np.full_like(floor, 6464, dtype=np.int32)
        own = np.zeros_like(floor, bool)
        own[540, 540] = True
        natural = {"id": "stream:0", "kind": "natural", "points_xz": [[0, 0]]}
        anchor = {**natural, "kind": "engineered"}
        result = contract_model(natural, floor, depth, cap, own)
        self.assertEqual(
            result["optimistic_any_nearby_raster"]["earliest_common_stage_q"], 6407
        )
        self.assertEqual(
            result["restricted_own_source_raster"][
                "same_stage_with_any_own_1m_source_intervals_q"
            ],
            [[6464, 6464]],
        )
        self.assertEqual(
            contract_model(anchor, floor, depth, cap, own)[
                "optimistic_any_nearby_raster"
            ]["earliest_common_stage_q"],
            6432,
        )

    def test_initial_wetness_never_selects_support_or_intervals(self):
        floor = np.full((1081, 1081), 6400, np.uint16)
        cap = np.full_like(floor, 6406, dtype=np.int32)
        own = np.ones_like(floor, bool)
        contract = {"id": "stream:0", "kind": "natural", "points_xz": [[0, 0]]}
        dry = contract_model(contract, floor, np.zeros_like(floor), cap, own)
        wet = contract_model(contract, floor, np.full_like(floor, 64), cap, own)
        self.assertEqual(
            dry["optimistic_any_nearby_raster"], wet["optimistic_any_nearby_raster"]
        )
        self.assertEqual(dry["initial_wet_points"], 0)
        self.assertEqual(wet["initial_wet_points"], 1)
        self.assertFalse(dry["optimistic_any_nearby_raster"]["numeric_fit_only"])


if __name__ == "__main__":
    unittest.main()
