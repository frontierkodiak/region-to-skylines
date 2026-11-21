import unittest

import numpy as np

from coastal_wet_connectivity import boundary_connected


class WetConnectivityTests(unittest.TestCase):
    def test_alternate_wet_route_survives_a_dry_shortest_route(self):
        wet = np.array([[1, 1, 1], [1, 0, 1]], bool)
        edge = np.zeros_like(wet)
        edge[1, 0] = True
        self.assertTrue(boundary_connected(wet, edge, 4)[1, 2])

    def test_diagonal_contact_is_not_four_neighbor_connection(self):
        wet = np.eye(3, dtype=bool)
        edge = np.zeros_like(wet)
        edge[0, 0] = True
        self.assertFalse(boundary_connected(wet, edge, 4)[2, 2])
        self.assertTrue(boundary_connected(wet, edge, 8)[2, 2])


if __name__ == "__main__":
    unittest.main()
