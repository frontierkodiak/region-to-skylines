import copy
import unittest

from coastal_dense_study import augment, readback_metrics


class DenseStudyTests(unittest.TestCase):
    def test_original_objects_metadata_and_required_flags_stay_unchanged(self):
        original = {
            "reference_water": "water.u16",
            "points": [
                {
                    "name": "original",
                    "x": -8640,
                    "z": -8640,
                    "required": True,
                    "custom": [1, 2],
                }
            ],
        }
        before = copy.deepcopy(original)
        new, indices = augment(original, [0, 1])
        self.assertEqual(original, before)
        self.assertEqual(new["points"][:1], original["points"])
        self.assertEqual(indices, [0, 1])
        self.assertFalse(new["points"][1]["required"])
        self.assertEqual(new["reference_water"], "water.u16")

    def test_nearby_nongrid_query_does_not_fill_a_dense_measurement_gap(self):
        original = {"points": [{"name": "offgrid", "x": -8638, "z": -8640}]}
        new, indices = augment(original, [0])
        self.assertEqual(indices, [1])
        self.assertEqual(new["points"][1]["x"], -8640)

    def test_missing_velocity_is_retained_as_unknown_not_zero_or_pass(self):
        result = readback_metrics([{"name": "a", "wet": True}], {"group": [0]}, True)
        self.assertEqual(result["status"], "unknown; raw readback failure retained")
        self.assertNotIn("group", result)

    def test_reserved_name_collision_is_refused_without_relabeling_original(self):
        original = {
            "points": [{"name": "dense-source-interface-v1:0,0", "x": 1, "z": 1}]
        }
        with self.assertRaisesRegex(ValueError, "collision"):
            augment(original, [0])


if __name__ == "__main__":
    unittest.main()
