import unittest

import numpy as np

from coastal_transport_witness import (
    aligned_node,
    envelope,
    path_to_root,
    routes,
    signed_velocity,
)


class TransportWitnessTests(unittest.TestCase):
    def test_blocked_static_route_remains_blocked_despite_minimax_witness(self):
        floor = np.full((3, 5), 100, np.uint16)
        floor[1, :] = [50, 50, 95, 50, 50]
        seeds = np.zeros_like(floor, bool)
        seeds[1, 0] = True
        static, minimax, spill = routes(floor, seeds, 90)
        self.assertIsNone(path_to_root(9, static))
        self.assertEqual(path_to_root(9, minimax), [9, 8, 7, 6, 5])
        self.assertEqual(spill[9], 95)
        self.assertEqual(floor[1, 2], 95)

    def test_every_branch_gets_an_unchanged_shortest_static_path(self):
        floor = np.full((5, 5), 100, np.uint16)
        floor[2, :] = 50
        floor[1:4, 3] = 50
        seeds = np.zeros_like(floor, bool)
        seeds[2, 0] = True
        static, _, _ = routes(floor, seeds, 90)
        for node in [8, 14, 18]:
            path = path_to_root(node, static)
            self.assertEqual(path[-1], 10)
            self.assertTrue(all(floor.ravel()[n] < 90 for n in path))
        self.assertEqual(path_to_root(8, static), [8, 13, 12, 11, 10])

    def test_signed_horizontal_velocity_follows_native_z_not_y(self):
        parent = np.array([-1, 4, -1, -1, 4, -1])
        self.assertEqual(signed_velocity([2, 999, -3], 1, parent, 3), -3)
        self.assertIsNone(signed_velocity([2, 999, -3], 4, parent, 3))

    def test_unobserved_velocity_is_not_fabricated_from_a_nearby_probe(self):
        self.assertEqual(aligned_node({"x": -8624, "z": -8608}, 1081), 2163)
        self.assertIsNone(aligned_node({"x": -8620, "z": -8608}, 1081))
        self.assertEqual(
            envelope([]), {"count": 0, "min": None, "median": None, "max": None}
        )

    def test_minimax_chooses_lower_sill_even_when_path_is_longer(self):
        floor = np.array([[1, 8, 1], [2, 3, 2]], np.uint16)
        seeds = np.zeros_like(floor, bool)
        seeds[0, 0] = True
        _, minimax, spill = routes(floor, seeds, 5)
        self.assertEqual(path_to_root(2, minimax), [2, 5, 4, 3, 0])
        self.assertEqual(spill[2], 3)


if __name__ == "__main__":
    unittest.main()
