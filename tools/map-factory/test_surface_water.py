"""Behavioral fixtures for underground gaps; no native acceptance claim."""

import copy
import unittest

import numpy as np

from prepare import route
from region import hydrology, raster
from surface_water import surface_geometry


class SurfaceWaterTests(unittest.TestCase):
    def test_exact_tunnel_only_not_whole_name_or_intermittent(self):
        pieces = [
            {
                "name": "same river",
                "pts": [[0, 0], [1, 1]],
                "brunnel": tag,
                "intermittent": 1,
            }
            for tag in [None, "bridge", "tunnel"]
        ]
        original = {"rivers": pieces, "streams": []}
        snapshot = copy.deepcopy(original)
        result, receipt = surface_geometry(original)
        self.assertEqual(original, snapshot)
        self.assertEqual(result["rivers"], pieces[:2])
        self.assertEqual(receipt["underground_pieces"], 1)
        repeated, again = surface_geometry(result)
        self.assertEqual(result, repeated)
        self.assertEqual(receipt, again)

    def test_missing_or_conflicting_tunnel_evidence_fails(self):
        with self.assertRaises(ValueError):
            surface_geometry({"undergroundWaterways": [{"brunnel": None}]})
        with self.assertRaises(ValueError):
            surface_geometry(
                {
                    "rivers": [
                        {
                            "brunnel": None,
                            "sourceFeature": {"properties": {"brunnel": "tunnel"}},
                        }
                    ]
                }
            )

    def test_router_does_not_recreate_a_forbidden_gap(self):
        mask = np.zeros((1081, 1081), bool)
        mask[540, 500:580] = True
        blocked = np.zeros_like(mask)
        blocked[:, 538:542] = True
        with self.assertRaisesRegex(ValueError, "disconnected"):
            route(mask, (500, 540), (579, 540), forbidden=blocked)

    def test_surface_legs_stay_separate_and_portal_is_a_drain(self):
        # Equatorial local frame: two visible legs separated by a two-cell
        # underground gap that the old dilation/router would bridge.
        def coord(x):
            return [float(np.rad2deg(x / 6378137)), 0]

        geometry = {
            "sq": {"lat": 0, "lon": 0, "rotation": 0, "scale": 1},
            "rivers": [
                {"name": "river", "pts": [coord(-2000), coord(-16)]},
                {"name": "river", "pts": [coord(16), coord(2000)]},
            ],
            "undergroundWaterways": [
                {
                    "name": "river",
                    "class": "river",
                    "brunnel": "tunnel",
                    "pts": [coord(-16), coord(16)],
                }
            ],
        }
        ground = np.full((1081, 1081), 100.0)
        banks = ground + np.linspace(5, 0, 1081)[None, :]
        before = ground.copy()
        _, report = hydrology(ground, banks, geometry)
        self.assertEqual(len(report["rivers"]), 2)
        self.assertEqual(ground[540, 540], before[540, 540])
        forbidden = raster(geometry["sq"], geometry["undergroundWaterways"])
        for points in report["samples"].values():
            self.assertFalse(
                any(
                    forbidden[round(540 - p[2] / 16), round(540 + p[0] / 16)]
                    and p[0] == 0
                    for p in points
                )
            )
        drains = [
            s
            for s in report["sources"]
            if s.get("underground_portal") == "surface_inlet_to_tunnel"
        ]
        self.assertEqual(len(drains), 1)
        self.assertEqual(drains[0]["output_capacity"], 0)

    def test_infeasible_minor_stream_keeps_probes_but_has_no_perennial_forcing(self):
        def coord(x):
            return [float(np.rad2deg(x / 6378137)), 0]

        geometry = {
            "sq": {"lat": 0, "lon": 0, "rotation": 0, "scale": 1},
            "streams": [
                {
                    "name": "infeasible creek",
                    "class": "stream",
                    "pts": [coord(-2000), coord(2000)],
                }
            ],
        }
        ground = np.full((1081, 1081), 100.0)
        banks = np.full_like(ground, 103.0)
        banks[:, 530:550] = 90
        _, report = hydrology(ground, banks, geometry)
        self.assertTrue(report["rivers"][0]["unforced_infeasible_stream"])
        self.assertTrue(report["samples"])
        self.assertTrue(report["sources"])
        self.assertTrue(all(s["output_capacity"] == 0 for s in report["sources"]))
        self.assertTrue(all(s["capacity"] > 0 for s in report["sources"]))

    def test_bank_limited_river_bounds_prefill_and_source_head_together(self):
        def coord(x):
            return [float(np.rad2deg(x / 6378137)), 0]

        geometry = {
            "sq": {"lat": 0, "lon": 0, "rotation": 0, "scale": 1},
            "rivers": [{"name": "bounded river", "pts": [coord(-2000), coord(2000)]}],
        }
        ground = np.full((1081, 1081), 100.0)
        banks = np.full_like(ground, 103.0)
        banks[:, 530:550] = 101
        depth, report = hydrology(ground, banks, geometry)
        self.assertTrue(any(s.get("bank_limited") for s in report["sources"]))
        self.assertLessEqual(float(depth.max()), 1.0 + 1e-9)
        self.assertGreater(float(depth.max()), 0.5)
        for source in report["sources"]:
            x, _, z = source["position"]
            bed = ground[round(540 - z / 16), round(540 + x / 16)]
            self.assertLessEqual(source["target"] - bed, 1.0 + 1e-9)


if __name__ == "__main__":
    unittest.main()
