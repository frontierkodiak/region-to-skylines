"""Probe selection must not turn disconnected markers into a route."""

import unittest

from cs1_harness.connections import outside_pair, outside_requests


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
    def test_all_outside_pairs_are_candidates_not_reachability_claims(self):
        networks = {
            "segments": [
                segment(1, 1, 2, -100, 0, outside_start=True),
                segment(2, 2, 3, 0, 100, outside_end=True),
                segment(3, 4, 5, 900, 1000, outside_end=True),
            ]
        }
        self.assertEqual(len(outside_requests(networks, "ship", "Ship")), 12)
        self.assertIsNone(outside_pair(networks, "Plane"))

    def test_midpoint_controls_keep_segments_lanes_and_direction_fixed(self):
        networks = {
            "segments": [
                segment(1, 1, 2, -100, 0, outside_start=True),
                segment(2, 2, 3, 0, 100, outside_end=True),
            ]
        }
        requests = outside_requests(networks, "ship", "Ship")
        boundary = [request for request in requests if request["position_kind"] == "boundary"]
        midpoint = [request for request in requests if request["position_kind"] == "midpoint"]
        self.assertEqual(len(boundary), 2)
        self.assertEqual(len(midpoint), 2)
        for original, control in zip(boundary, midpoint):
            self.assertEqual(original["direction"], control["direction"])
            self.assertEqual(original["from"][:2], control["from"][:2])
            self.assertEqual(original["to"][:2], control["to"][:2])
            self.assertEqual([control["from"][2], control["to"][2]], [128, 128])
        self.assertEqual(networks["segments"][0]["a"], [-100, 0, 0])

    def test_road_requires_opposite_roles(self):
        a = segment(1, 1, 2, -100, 0, outside_start=True, vehicle="Car")
        b = segment(2, 2, 3, 0, 100, outside_end=True, vehicle="Car")
        a["start_flags"] += ", OneWayOut"
        b["end_flags"] += ", OneWayOut"
        self.assertEqual(outside_requests({"segments": [a, b]}, "road", "Car"), [])
        b["end_flags"] = "Created, Outside, OneWayIn"
        requests = outside_requests({"segments": [a, b]}, "road", "Car")
        self.assertEqual(len(requests), 4)
        self.assertEqual(requests[0]["endpoint_roles"], [["OneWayOut"], ["OneWayIn"]])

    def test_one_outside_node_is_not_a_pair(self):
        self.assertIsNone(outside_pair({"segments": [segment(1, 1, 2, 0, 100, outside_end=True)]}, "Ship"))

    def test_vehicle_matching_is_not_a_substring(self):
        net = {"segments": [segment(1, 1, 2, 0, 100, outside_start=True, outside_end=True, vehicle="CableCar")]}
        self.assertIsNone(outside_pair(net, "Car"))


if __name__ == "__main__":
    unittest.main()
