import unittest

from coastal_short_study import control_mismatches, groups, metrics


class CoastalShortTests(unittest.TestCase):
    def test_full_group_and_legacy_subset_are_not_merged(self):
        points = [
            {"name": "Main Drain [river] #0"},
            {"name": "Bulimba Creek [stream] #1"},
            {"name": "other"},
        ]
        result = groups(points, [points[0]])
        self.assertEqual(result["all_frozen_probes"], [0, 1, 2])
        self.assertEqual(result["Bulimba Creek"], [1])
        self.assertEqual(result["fixed_historical162"], [0])

    def test_missing_exact_water_does_not_erase_nearby_water_or_velocity(self):
        result = metrics(
            [
                {
                    "wet": False,
                    "depth": 0,
                    "max_depth_within_64m": 0.125,
                    "velocity": [2, 0, 0],
                }
            ],
            {"all": [0]},
        )["all"]
        self.assertEqual(result["native_wet_flag"], 0)
        self.assertEqual(result["nearby_depth_gt_0_1m"], 1)
        self.assertEqual(result["horizontal_velocity_nonzero_api"], 1)

    def test_output_position_change_and_rate_change_are_kept(self):
        expected = [
            {
                "index": 0,
                "type": 1,
                "position": [1, 2, 3],
                "target_fixed": 6400,
                "intake_rate": 0,
                "output_rate": 128,
            }
        ]
        actual = [
            {
                "id": 1,
                "type": 1,
                "input_position": [1, 2, 3],
                "output_position": [1, 2, 3],
                "target_fixed": 6400,
                "input_rate": 0,
                "output_rate": 128,
            }
        ]
        self.assertEqual(control_mismatches(actual, expected), [])
        actual[0]["output_position"][1] = 4
        actual[0]["output_rate"] = 0
        self.assertEqual(
            {p["field"] for p in control_mismatches(actual, expected)},
            {"output_position", "output_rate"},
        )
