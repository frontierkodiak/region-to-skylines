import unittest
from qld_hydrographic_capture import complete_ids


class QldCaptureTests(unittest.TestCase):
    def test_lowercase_declared_id_retains_attributes_without_case_rewrite(self):
        features = [
            {"attributes": {"objectid": 2, "perenniality": "Unknown"}},
            {"attributes": {"objectid": 1, "function": "Drain"}},
        ]
        complete_ids([1, 2], features, "objectid")
        self.assertEqual(features[0]["attributes"]["perenniality"], "Unknown")
        self.assertNotIn("OBJECTID", features[0]["attributes"])

    def test_missing_duplicate_extra_noninteger_are_refused_not_repaired(self):
        for ids in [[1], [1, 1], [1, 3], [1, 2, 3], [1, True]]:
            with self.assertRaises(ValueError):
                complete_ids(
                    [1, 2], [{"attributes": {"objectid": n}} for n in ids], "objectid"
                )
        complete_ids([], [], "objectid")


if __name__ == "__main__":
    unittest.main()
