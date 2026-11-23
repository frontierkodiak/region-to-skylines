import unittest

import numpy as np

from startup_support_bound import aggregate, ownership, point_bound, VIEWS
from stage_contracts import nearby_nodes


class StartupSupportTests(unittest.TestCase):
    def bound(
        self,
        water,
        hard,
        coupling=None,
        foreign=None,
        own=None,
        ambiguous=None,
        known=True,
    ):
        shape = water.shape
        n = water.size
        return point_bound(
            np.arange(n),
            water,
            hard,
            np.zeros(shape, bool) if coupling is None else coupling,
            np.zeros(n, bool) if foreign is None else foreign,
            np.ones(shape, bool) if own is None else own,
            np.zeros(shape, bool) if ambiguous is None else ambiguous,
            known,
        )

    def test_preserved_wet_counts_despite_all_masks(self):
        r = self.bound(np.array([[7]]), np.array([[True]]), known=False)
        self.assertEqual(r["availability"], dict.fromkeys(VIEWS, True))
        r = self.bound(np.array([[6]]), np.array([[True]]))
        self.assertEqual(r["availability"], dict.fromkeys(VIEWS, False))

    def test_coupling_does_not_become_hard_impossibility(self):
        r = self.bound(
            np.array([[0]]), np.array([[False]]), coupling=np.array([[True]])
        )
        self.assertEqual(list(r["availability"].values()), [True, False, False])
        r = self.bound(np.array([[0]]), np.array([[False]]), foreign=np.array([True]))
        self.assertEqual(list(r["availability"].values()), [True, False, False])

    def test_source_overlap_stays_unknown_not_easy_owner(self):
        labels, ambiguous = ownership((1, 2), [(0, [0, 1]), (1, [1])])
        self.assertEqual(labels.tolist(), [[0, 0]])
        self.assertEqual(ambiguous.tolist(), [[False, True]])
        r = self.bound(
            np.array([[0]]), np.array([[False]]), ambiguous=np.array([[True]])
        )
        self.assertEqual(list(r["availability"].values()), [True, True, None])

    def test_missing_target_component_preserves_unknown(self):
        r = self.bound(np.array([[0]]), np.array([[False]]), known=False)
        self.assertEqual(list(r["availability"].values()), [True, None, None])
        r = self.bound(np.array([[0]]), np.array([[True]]), known=False)
        self.assertEqual(list(r["availability"].values()), [False, False, False])

    def test_fraction_handles_unknown_without_false_certificate(self):
        self.assertEqual(
            aggregate([True] * 19 + [False], 0.95)["status"],
            "necessary_support_available",
        )
        self.assertEqual(
            aggregate([True] * 18 + [None, False], 0.95)["status"], "unknown"
        )
        self.assertEqual(
            aggregate([True] * 18 + [False] * 2, 0.95)["status"],
            "conditional_preservation_obstruction",
        )
        self.assertEqual(aggregate([], 0.95)["status"], "unknown")

    def test_exact_circle_and_native_orientation(self):
        nodes = nearby_nodes([0, 8640], (1081, 1081))
        north = (1080 - nodes // 1081) * 1081 + nodes % 1081
        self.assertIn(540, north)
        self.assertIn(544, north)  # exactly 64m
        self.assertNotIn(545, north)
        self.assertTrue(np.all(north // 1081 <= 4))


if __name__ == "__main__":
    unittest.main()
