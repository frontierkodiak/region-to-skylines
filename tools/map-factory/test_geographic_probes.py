"""Acceptance coverage must not inherit the hydraulic model's omissions."""

import copy
import unittest

import numpy as np

from soak import geographic_river_probes


def coord(x, z=0):
    return [float(np.rad2deg(x / 6378137)), float(np.rad2deg(z / 6378137))]


class GeographicProbeTests(unittest.TestCase):
    def geometry(self, rivers):
        return {
            "sq": {"lat": 0, "lon": 0, "rotation": 0, "scale": 1},
            "rivers": rivers,
        }

    def test_short_unmodeled_river_is_probed_without_any_hydraulic_samples(self):
        geometry = self.geometry([{"name": "short", "pts": [coord(-32), coord(32)]}])
        data = {"points": []}
        geographic_river_probes(data, geometry)
        self.assertEqual({p["x"] for p in data["points"]}, {-32, -16, 0, 16, 32})
        self.assertTrue(all(p["required"] for p in data["points"]))
        self.assertTrue(
            all(p["z"] == 0 and "[river]" in p["name"] for p in data["points"])
        )

    def test_explicit_tunnel_gap_is_not_probed_or_reconnected(self):
        geometry = self.geometry(
            [
                {"name": "river", "pts": [coord(-64), coord(-32)]},
                {"name": "river", "pts": [coord(-16), coord(16)], "brunnel": "tunnel"},
                {"name": "river", "pts": [coord(32), coord(64)]},
            ]
        )
        original = copy.deepcopy(geometry)
        data = {"points": []}
        geographic_river_probes(data, geometry)
        self.assertEqual(geometry, original)
        self.assertFalse(any(abs(p["x"]) < 32 for p in data["points"]))
        self.assertTrue(any(p["x"] < 0 for p in data["points"]))
        self.assertTrue(any(p["x"] > 0 for p in data["points"]))

    def test_duplicate_tile_pieces_do_not_reweight_the_same_river_cells(self):
        feature = {"name": "river", "pts": [coord(-32), coord(32)]}
        once, twice = {"points": []}, {"points": []}
        geographic_river_probes(once, self.geometry([feature]))
        geographic_river_probes(twice, self.geometry([feature, copy.deepcopy(feature)]))
        self.assertEqual(once["points"], twice["points"])

    def test_existing_route_samples_are_retained_and_other_river_names_stay_distinct(
        self,
    ):
        route = {"name": "routed [river]:00", "x": 0, "z": 0}
        data = {"points": [route.copy()]}
        geographic_river_probes(
            data,
            self.geometry(
                [
                    {"name": "one", "pts": [coord(0), coord(16)]},
                    {"name": "two", "pts": [coord(0), coord(16)]},
                ]
            ),
        )
        self.assertEqual(data["points"][0], route)
        self.assertEqual(data["geographic_river_probes"]["points"], 4)
        with self.assertRaisesRegex(ValueError, "already present"):
            geographic_river_probes(
                data, self.geometry([{"name": "one", "pts": [coord(0), coord(16)]}])
            )


if __name__ == "__main__":
    unittest.main()
