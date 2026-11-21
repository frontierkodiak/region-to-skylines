import unittest

import numpy as np

from prepare_surface_controls import control_banks


class ReferenceGeometry(unittest.TestCase):
    def test_same_component_separated_reference_is_deterministic(self):
        ground = np.full((1081, 1081), 55.0)
        depth = np.zeros_like(ground)
        ground[:, 530:550] = 50
        depth[:, 530:550] = 4
        first = control_banks(ground, depth, 12)
        second = control_banks(ground, depth, 12)
        self.assertEqual(first, second)
        self.assertEqual(2, len(first))
        self.assertGreaterEqual(
            np.linalg.norm(np.asarray(first[0][:2]) - first[1][:2]) * 16, 640
        )

    def test_no_water_is_unscored_reference_not_fabricated(self):
        ground = np.full((1081, 1081), 55.0)
        self.assertEqual([], control_banks(ground, np.zeros_like(ground), 12))

    def test_disconnected_small_ponds_cannot_be_a_same_body_reference(self):
        ground = np.full((1081, 1081), 55.0)
        depth = np.zeros_like(ground)
        for c in (510, 560):
            ground[530:540, c : c + 10] = 50
            depth[530:540, c : c + 10] = 4
        self.assertLess(len(control_banks(ground, depth, 12)), 2)


if __name__ == "__main__":
    unittest.main()
