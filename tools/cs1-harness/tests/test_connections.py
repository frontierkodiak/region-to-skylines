"""Probe selection must not turn disconnected markers into a route."""

import unittest

from cs1_harness.connections import outside_pair


def segment(identity, start, end, a, b, *, outside_start=False, outside_end=False, vehicle="Ship"):
    return {
        "id": identity,
        "start": start,
        "end": end,
        "a": [a, 0, 0],
        "b": [b, 0, 0],
        "start_flags": "Created, Outside" if outside_start else "Created",
        "end_flags": "Created, Outside" if outside_end else "Created",
        "lanes": [{"index": 0, "vehicle": vehicle}],
    }


class OutsidePairTest(unittest.TestCase):
    def test_connected_outside_endpoints_not_isolated_distant_marker(self):
        networks = {
            "segments": [
                segment(1, 1, 2, -100, 0, outside_start=True),
                segment(2, 2, 3, 0, 100, outside_end=True),
                segment(3, 4, 5, 900, 1000, outside_end=True),
            ]
        }
        self.assertEqual(outside_pair(networks, "Ship"), [[1, 0, 0], [2, 0, 255]])
        self.assertIsNone(outside_pair(networks, "Plane"))

    def test_one_outside_node_is_not_a_pair(self):
        self.assertIsNone(outside_pair({"segments": [segment(1, 1, 2, 0, 100, outside_end=True)]}, "Ship"))

    def test_vehicle_matching_is_not_a_substring(self):
        net = {"segments": [segment(1, 1, 2, 0, 100, outside_start=True, outside_end=True, vehicle="CableCar")]}
        self.assertIsNone(outside_pair(net, "Car"))


if __name__ == "__main__":
    unittest.main()
