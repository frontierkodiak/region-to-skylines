import copy
import unittest

from coastal_rate_zero_study import missed_slot_count, rate_only_change


class RateZeroTests(unittest.TestCase):
    def test_future_protocol_reporting_counts_actual_missed_slot_entries(self):
        self.assertEqual(
            missed_slot_count([{"missed_slots": []}, {"missed_slots": [2, 3]}]), 2
        )

    def test_future_protocol_reporting_keeps_wrong_counter_shape_unknown(self):
        with self.assertRaises(ValueError):
            missed_slot_count([{"missed_slots": 0}])

    def test_only_outputs_change_and_original_targets_positions_are_retained(self):
        before = [
            {
                "index": i,
                "intake_rate": 0,
                "output_rate": 10,
                "target_fixed": 5760,
                "position": [i, 90, 0],
            }
            for i in range(167)
        ]
        after = [dict(s, output_rate=0) for s in before]
        rate_only_change(before, after)
        after = copy.deepcopy(after)
        after[0]["target_fixed"] += 1
        with self.assertRaisesRegex(ValueError, "Only all167"):
            rate_only_change(before, after)

    def test_nonzero_intake_or_missing_source_cannot_be_called_rates_zero(self):
        before = [{"index": i, "intake_rate": 0, "output_rate": 10} for i in range(167)]
        after = [dict(s, output_rate=0) for s in before]
        with self.assertRaisesRegex(ValueError, "All167"):
            rate_only_change(before, after[:-1])
        before[0]["intake_rate"] = 1
        with self.assertRaisesRegex(ValueError, "Only all167"):
            rate_only_change(before, after)


if __name__ == "__main__":
    unittest.main()
