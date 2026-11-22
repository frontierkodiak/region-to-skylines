import unittest
import numpy as np
from spill_port_topology import elevated_envelope


class SpillTests(unittest.TestCase):
    def run_case(self, floor, initial=None, mapped=None, banks=None):
        return elevated_envelope(
            floor,
            np.zeros_like(floor) if initial is None else initial,
            np.zeros_like(floor, bool) if mapped is None else mapped,
            64,
            np.array([12]),
            8,
            {},
            np.zeros_like(floor, bool) if banks is None else banks,
        )[0]

    def test_sloped_shoulder_is_not_zero_freeboard_failure(self):
        floor = np.full((5, 5), 128, np.int64)
        floor[1:4, 1:4] = 64
        floor[2, 2] = 0
        result = self.run_case(floor)
        self.assertEqual((result["base_nodes"], result["elevated_nodes"]), (1, 9))
        self.assertEqual(result["topology"], "interior_at_elevated_stage")
        self.assertFalse(result["closed_basin_or_stream_admission"])

    def test_low_saddle_opens_interior_domain(self):
        floor = np.full((5, 5), 128, np.int64)
        floor[2, 2] = 0
        floor[2, 0:2] = 80
        result = self.run_case(floor)
        self.assertEqual(result["topology"], "map_edge_open_at_elevated_stage")
        self.assertEqual(len(result["ports"]), 1)
        self.assertIsNone(result["ports"][0]["upstream_supply_port"])

    def test_added_bank_nodes_are_diagnostic_not_retired(self):
        floor = np.full((5, 5), 128, np.int64)
        floor[2, 2] = 0
        floor[2, 3] = 80
        banks = np.zeros_like(floor, bool)
        banks[2, 3] = True
        result = self.run_case(floor, banks=banks)
        self.assertEqual(result["old_source_bank_nodes_in_diagnostic_annulus"], 1)
        self.assertEqual(result["first_original_source_bank_rc"], [2, 3])
        self.assertTrue(banks[2, 3])

    def test_initial_dryness_does_not_select_envelope(self):
        floor = np.full((5, 5), 128, np.int64)
        floor[1:4, 1:4] = 64
        floor[2, 2] = 0
        a = self.run_case(floor)
        b = self.run_case(floor, initial=np.full_like(floor, 32))
        self.assertEqual(a["elevated_nodes_i32_sha256"], b["elevated_nodes_i32_sha256"])
        self.assertEqual(
            (
                a["off_mask_initially_dry_nodes"],
                b["off_mask_already_initialized_nodes"],
            ),
            (9, 9),
        )


if __name__ == "__main__":
    unittest.main()
