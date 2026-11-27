"""Quartile gate behaviour, including ties at the acceptance boundary."""

import unittest

from rank_native import conservative_rank


class RankingTest(unittest.TestCase):
    def test_top_quarter_boundary(self):
        self.assertEqual(conservative_rank(0.5, [0.8, 0.7, 0.6] + [0.1] * 12), 4)
        self.assertEqual(conservative_rank(0.5, [0.8, 0.7, 0.6, 0.55] + [0.1] * 11), 5)

    def test_ties_are_not_broken_by_input_order(self):
        self.assertEqual(conservative_rank(0.5, [0.5] * 15), 16)
        self.assertEqual(
            conservative_rank(0.5, [0.6, 0.5, 0.1]),
            conservative_rank(0.5, [0.1, 0.5, 0.6]),
        )
