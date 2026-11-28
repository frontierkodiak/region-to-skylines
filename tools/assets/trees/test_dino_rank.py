"""Class-balanced contrast and conservative quartile acceptance."""

import unittest

from rank_dino import contrast


class ContrastTest(unittest.TestCase):
    def test_other_genera_are_equally_weighted(self):
        self.assertAlmostEqual(
            contrast({"Ulmus": 0.7, "Tilia": 0.5, "Gleditsia": 0.3}, "Ulmus"), 0.3
        )

    def test_no_genus_difference_has_no_signal(self):
        self.assertEqual(
            contrast({"Ulmus": 0.5, "Tilia": 0.5, "Gleditsia": 0.5}, "Tilia"), 0
        )
