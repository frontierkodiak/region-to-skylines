import unittest

from derive_rate_zero_result import count_missed_slots


class ReportingTests(unittest.TestCase):
    def test_all_missed_slot_entries_are_counted_not_added_as_lists(self):
        self.assertEqual(
            count_missed_slots([{"missed_slots": []}, {"missed_slots": [2, 3]}]), 2
        )

    def test_missing_counter_shape_is_not_fabricated_as_zero(self):
        for row in [{}, {"missed_slots": 0}, {"missed_slots": None}]:
            with self.assertRaises(ValueError):
                count_missed_slots([row])


if __name__ == "__main__":
    unittest.main()
