import unittest

from startup_support_ordering import tighten
from startup_support_bound import VIEWS


class SubsetTests(unittest.TestCase):
    def test_full_mask_failure_bounds_restricted_unknown(self):
        source = {
            "contracts": [
                {
                    "contract": {"id": "x", "kind": "natural"},
                    "points": [
                        {"availability": dict(zip(VIEWS, [True, False, None]))},
                        {"availability": dict(zip(VIEWS, [True, True, None]))},
                        {"availability": dict.fromkeys(VIEWS, True)},
                    ],
                }
            ]
        }
        result = tighten(source)
        self.assertIsNone(source["contracts"][0]["points"][0]["availability"][VIEWS[2]])
        values = [p["availability"][VIEWS[2]] for p in result["contracts"][0]["points"]]
        self.assertEqual(values, [False, None, True])
        self.assertEqual(
            result["additive_subset_ordering_correction"][
                "changed_unknown_to_false_points"
            ],
            [["x", 0]],
        )

    def test_null_base_support_not_fabricated(self):
        source = {
            "floor": None,
            "contracts": [
                {
                    "contract": {"id": "x", "kind": "natural"},
                    "points": [{"availability": dict.fromkeys(VIEWS)}],
                }
            ],
        }
        result = tighten(source)
        self.assertIsNone(result["floor"])
        self.assertEqual(result["contracts"][0]["views"][VIEWS[2]]["status"], "unknown")
        self.assertEqual(
            result["additive_subset_ordering_correction"][
                "changed_unknown_to_false_points"
            ],
            [],
        )


if __name__ == "__main__":
    unittest.main()
