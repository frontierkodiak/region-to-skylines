"""Behavioral fixtures for underground gaps; no native acceptance claim."""

import copy
import unittest

import numpy as np

from prepare import route
from region import hydrology, limit_source_footprints, raster
from surface_water import surface_geometry


class SurfaceWaterTests(unittest.TestCase):
    @staticmethod
    def short_geometry(legs, kind="river"):
        def coord(x):
            return [float(np.rad2deg(x / 6378137)), 0]

        return {
            "sq": {"lat": 0, "lon": 0, "rotation": 0, "scale": 1},
            "rivers" if kind == "river" else "streams": [
                {"name": "short reach", "class": kind, "pts": [coord(a), coord(b)]}
                for a, b in legs
            ],
        }

    def test_short_visible_legs_are_wet_without_recreating_tunnel(self):
        geometry = self.short_geometry([(-320, -16), (16, 320)])
        tunnel = self.short_geometry([(-16, 16)])["rivers"][0]
        geometry["undergroundWaterways"] = [{**tunnel, "brunnel": "tunnel"}]
        ground = np.full((1081, 1081), 100.0)
        banks = ground + np.linspace(5, 3, 1081)[None, :]
        original = ground.copy()
        depth, report = hydrology(ground, banks, geometry)
        self.assertEqual(len(report["rivers"]), 2)
        self.assertTrue(all(r["length_m"] < 720 for r in report["rivers"]))
        self.assertTrue(all(r["short_surface_river"] for r in report["rivers"]))
        for points in report["samples"].values():
            for x, _, z in points:
                self.assertGreater(depth[round(540 - z / 16), round(540 + x / 16)], 0.1)
        self.assertEqual(depth[540, 540], 0)
        self.assertEqual(ground[540, 540], original[540, 540])
        self.assertLessEqual(float(depth.max()), 1.0 + 1e-9)
        self.assertLessEqual(float((original - ground).max()), 3.0 + 1e-9)
        limit_source_footprints(ground, depth, banks, geometry, report)
        drains = [
            s
            for s in report["sources"]
            if s.get("underground_portal") == "surface_inlet_to_tunnel"
        ]
        self.assertEqual(len(drains), 1)
        self.assertEqual(drains[0]["output_capacity"], 0)
        self.assertTrue(any(s["output_capacity"] > 0 for s in report["sources"]))

    def test_two_vertex_river_controls_keep_flow_order_and_do_not_duplicate(self):
        geometry = self.short_geometry([(0, 16.1)])
        ground = np.full((1081, 1081), 100.0)
        banks = ground + np.linspace(5, 3, 1081)[None, :]
        depth, report = hydrology(ground, banks, geometry)
        self.assertEqual(len(report["rivers"]), 1)
        controls = {s["role"]: s for s in report["sources"]}
        self.assertEqual(set(controls), {"upstream", "downstream"})
        self.assertLess(
            controls["upstream"]["position"][0], controls["downstream"]["position"][0]
        )
        self.assertGreater(depth[540, 540], 0.1)
        self.assertGreater(depth[540, 541], 0.1)
        self.assertLessEqual(float(depth.max()), 1.0 + 1e-9)

    def test_short_minor_stream_still_omitted_but_coverage_is_disclosed(self):
        geometry = self.short_geometry([(0, 320)], kind="stream")
        ground = np.full((1081, 1081), 100.0)
        _, report = hydrology(ground, ground + 3, geometry)
        self.assertEqual(report["rivers"], [])
        self.assertEqual(report["sources"], [])
        self.assertIn(
            "45-vertex", report["unmodeled_short_surface_reaches"][0]["reason"]
        )
        self.assertEqual(len(report["mapped_waterway_coverage"]), 1)

    def test_one_cell_river_is_an_explicit_resolution_omission(self):
        geometry = self.short_geometry([(0.1, 0.2)])
        ground = np.full((1081, 1081), 100.0)
        depth, report = hydrology(ground, ground + 3, geometry)
        self.assertEqual(report["sources"], [])
        self.assertEqual(
            report["unmodeled_short_surface_reaches"][0]["mapped_vertices"], 1
        )
        self.assertIn(
            "native two-vertex", report["unmodeled_short_surface_reaches"][0]["reason"]
        )
        self.assertEqual(float(depth[540, 540]), 0.25)
        self.assertEqual(report["geographic_river_prefill"]["film_added_cells"], 1)
        self.assertEqual(report["geographic_river_prefill"]["unseeded_cells"], 0)

    def test_geographic_film_does_not_raise_high_ground_or_hide_dry_cells(self):
        geometry = self.short_geometry([(0.1, 0.2)])
        ground = np.full((1081, 1081), 100.0)
        original = ground.copy()
        depth, report = hydrology(ground, ground - 1, geometry)
        np.testing.assert_array_equal(ground, original)
        self.assertEqual(float(depth.max()), 0.0)
        prefill = report["geographic_river_prefill"]
        self.assertEqual(prefill["unseeded_cells"], 1)
        self.assertEqual(prefill["insufficient_bank_clearance_cells"], 1)
        self.assertEqual(prefill["unseeded_world_positions"], [[0, 0, 0]])

    def test_startup_film_covers_disconnected_source_islands_without_route_samples(
        self,
    ):
        geometry = self.short_geometry([(0.1, 0.2), (128.1, 128.2)])
        ground = np.full((1081, 1081), 100.0)
        depth, report = hydrology(ground, ground + 3, geometry)
        self.assertFalse(report["samples"])
        self.assertFalse(report["sources"])
        self.assertEqual(float(depth[540, 540]), 0.25)
        self.assertEqual(float(depth[540, 548]), 0.25)
        self.assertEqual(int(np.count_nonzero(depth)), 2)
        self.assertEqual(report["geographic_river_prefill"]["mapped_cells"], 2)
        self.assertEqual(report["geographic_river_prefill"]["film_added_cells"], 2)

    def test_short_coastal_reach_does_not_lower_the_ocean_stage(self):
        geometry = self.short_geometry([(0, 320)]) | {"seaLevel": 110.0}
        ground = np.full((1081, 1081), 100.0)
        depth, report = hydrology(ground, ground + 3, geometry)
        self.assertEqual(report["sources"], [])
        self.assertEqual(float(depth[540, 540]), 10.0)
        self.assertEqual(float(depth[540, 560]), 10.0)

    def test_short_source_head_stays_shallow_after_corridor_lowering(self):
        geometry = self.short_geometry([(0, 320)])
        ground = np.full((1081, 1081), 100.0)
        banks = ground + 3
        depth, report = hydrology(ground, banks, geometry)
        for source in report["sources"]:
            x, _, z = source["position"]
            ground[round(540 - z / 16), round(540 + x / 16)] -= 3
        limit_source_footprints(ground, depth, banks, geometry, report)
        for source in report["sources"]:
            x, _, z = source["position"]
            self.assertLessEqual(
                source["target"] - ground[round(540 - z / 16), round(540 + x / 16)], 1.0
            )

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

    def test_bed_crest_receives_shallow_supply_without_deepening_the_barrier(self):
        def coord(x):
            return [float(np.rad2deg(x / 6378137)), 0]

        geometry = {
            "sq": {"lat": 0, "lon": 0, "rotation": 0, "scale": 1},
            "rivers": [
                {"name": "obstructed river", "pts": [coord(-2000), coord(2000)]}
            ],
        }
        ground = np.broadcast_to(
            100 + 5 * np.exp(-(((np.arange(1081) - 540) / 8) ** 2)),
            (1081, 1081),
        ).copy()
        banks = ground + 3
        original = ground.copy()
        _, report = hydrology(ground, banks, geometry)
        crests = [s for s in report["sources"] if s["role"] == "bed_crest"]
        self.assertTrue(crests)
        self.assertLessEqual(float((original - ground).max()), 3.0 + 1e-9)
        self.assertTrue(any(abs(s["position"][0]) <= 32 for s in crests))
        for source in crests:
            x, _, z = source["position"]
            bed = ground[round(540 - z / 16), round(540 + x / 16)]
            self.assertGreater(source["target"] - bed, 0.1)
            self.assertLessEqual(source["target"] - bed, 1.0 + 1e-9)


if __name__ == "__main__":
    unittest.main()
