import struct
import unittest
from open_interface_operations import (
    field_operation,
    control_record,
    shared_cell_conflicts,
)


class OperationTests(unittest.TestCase):
    def test_contact_is_not_edit_or_admission(self):
        x = field_operation([0, 3], 6400, 6400, 96, 6400, 6496, ["old_control"])
        self.assertEqual(x["protected_contacts"], ["old_control"])
        self.assertEqual(x["protected_edits"], [])
        self.assertFalse(x["old_refusal_cleared"])
        self.assertEqual(x["native_u16le_byte_offset"], 2 * (1080 * 1081 + 3))

    def test_terrain_and_depth_changes_both_protected(self):
        x = field_operation([1080, 0], 6400, 6400, 0, 6304, 6400, ["bank"])
        self.assertEqual(x["changed_fields"], ["terrain", "initial_depth"])
        self.assertEqual(x["protected_edits"], ["bank"])
        self.assertEqual(x["native_u16le_byte_offset"], 0)
        self.assertEqual(
            int.from_bytes(
                bytes.fromhex(x["fields"]["terrain"]["after_u16le_hex"]), "little"
            ),
            6304,
        )

    def test_actual_floor_is_not_serialized_no_fill_authority(self):
        x = field_operation([2, 3], 6400, 6464, 96, 6464, 6560, [])
        self.assertFalse(x["serialized_no_fill_cut3_depth1_5_valid"])
        self.assertIsNone(x["native_floor_after_serialization"])

    def test_depth_retention_and_cut_bound(self):
        self.assertFalse(
            field_operation([2, 3], 6400, 6400, 128, 6300, 6396, [])[
                "serialized_no_fill_cut3_depth1_5_valid"
            ]
        )
        self.assertFalse(
            field_operation([2, 3], 6400, 6400, 0, 6200, 6400, [])[
                "serialized_no_fill_cut3_depth1_5_valid"
            ]
        )
        with self.assertRaises(ValueError):
            field_operation([2, 3], 6400, 6400, 0, 6400, 66000 + 6400, [])

    def test_ports_are_exact_two_position_records_not_node_regulators(self):
        h = control_record([540, 541], 6400, 6496, "head_inlet_proposal")
        t = control_record([540, 541], 6400, 6496, "terminal_outlet_or_intake_proposal")
        raw = bytes.fromhex(h["raw43_hex"])
        self.assertEqual(len(raw), 43)
        a = struct.unpack(">6fHH", raw[:28])
        self.assertEqual(a, (16, 100, 0, 16, 100, 0, 1, 6496))
        self.assertEqual(
            [int.from_bytes(raw[i : i + 3], "big") for i in range(28, 43, 3)],
            [0, 0, 128, 32, 0],
        )
        self.assertEqual(t["output_rate"], 0)
        self.assertFalse(h["deployed"])
        with self.assertRaises(ValueError):
            control_record([0, 0], 1, 97, "per_node_lake")

    def test_shared_cells_do_not_arbitrarily_overwrite_other_piece(self):
        a = field_operation([2, 3], 6400, 6400, 0, 6304, 6400, [])
        b = field_operation([2, 3], 6400, 6400, 0, 6320, 6416, [])
        self.assertFalse(shared_cell_conflicts([("a", [a]), ("b", [a])]))
        self.assertEqual(len(shared_cell_conflicts([("a", [a]), ("b", [b])])), 1)


if __name__ == "__main__":
    unittest.main()
