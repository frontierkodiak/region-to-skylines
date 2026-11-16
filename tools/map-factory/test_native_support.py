"""Sampling support must retain empty-corner water, not immortalize thin film."""

import unittest

import numpy as np

from native_support import interpolation_support, sample_water


class NativeSupportTests(unittest.TestCase):
    def test_subthreshold_film_on_level_ground_has_no_qualified_patch(self):
        ground = np.full((4, 4), 6400, dtype=np.uint16)
        self.assertFalse(interpolation_support(ground, np.full_like(ground, 6)).any())
        self.assertTrue(interpolation_support(ground, np.full_like(ground, 7)).all())

    def test_empty_lower_corner_can_still_sample_water(self):
        ground = np.full((1081, 1081), 6400, dtype=np.uint16)
        ground[540, 541] = 6300
        depth = np.zeros_like(ground)
        depth[540, 540] = 1
        support = interpolation_support(ground, depth)
        self.assertTrue(support[540, 541])
        _, surface, wet = sample_water(ground, depth, [[8, 0]])
        self.assertTrue(wet[0])
        self.assertEqual(surface[0], 6401 / 64)

    def test_no_occupied_corner_cannot_create_water(self):
        ground = np.full((1081, 1081), 6400, dtype=np.uint16)
        depth = np.zeros_like(ground)
        _, surface, wet = sample_water(ground, depth, [[0, 0], [2, 3]])
        self.assertFalse(wet.any())
        self.assertFalse(surface.any())
        self.assertFalse(interpolation_support(ground, depth).any())

    def test_clamped_boundary_has_its_own_minimum_surface(self):
        ground = np.full((1081, 1081), 6400, dtype=np.uint16)
        depth = np.zeros_like(ground)
        ground[540, 0] = 6300
        depth[541, 0] = 1
        ground[540, 1] = 6200
        depth[540, 1] = 1
        self.assertTrue(interpolation_support(ground, depth)[540, 0])
        _, _, wet = sample_water(ground, depth, [[-8641, 8]])
        self.assertTrue(wet[0])


if __name__ == "__main__":
    unittest.main()
