"""Coverage cannot disappear or be diluted by a larger healthy feature."""

import copy
import unittest

import numpy as np

from maintained_water_inventory import (
    compile_inventory,
    feature_outcome,
    initial_natural_checks,
)


def coord(x, z):
    a, e2 = 6378137, 0.00669437999014
    return [float(np.rad2deg(x / a)), float(np.rad2deg(z / (a * (1 - e2))))]


def line(start, end, **tags):
    return {"pts": [coord(*start), coord(*end)], **tags}


def body(x0, z0, x1, z1, **tags):
    return {
        "rings": [
            [coord(x0, z0), coord(x1, z0), coord(x1, z1), coord(x0, z1), coord(x0, z0)]
        ],
        **tags,
    }


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.geometry = {
            "sq": {"lon": 0, "lat": 0, "rotation": 0, "scale": 1},
            **{k: [] for k in ("rivers", "streams", "lakes", "riverAreas", "oceans")},
        }
        self.hydro = {
            "sources": [],
            "rivers": [
                {"name": "unnamed waterway", "class": kind}
                for kind in ("river", "stream")
            ],
            "unmodeled_short_surface_reaches": [],
        }

    def compile(self):
        return compile_inventory(self.geometry, self.hydro)

    def test_unmodeled_short_stream_has_source_only_contract(self):
        self.geometry["streams"] = [line((0, 0), (1, 0))]
        self.hydro["unmodeled_short_surface_reaches"] = [
            {"name": "unnamed waterway", "class": "stream"}
        ]
        result = self.compile()
        self.assertFalse(result["coverage_complete"])
        self.assertEqual(result["entries"][0]["status"], "unresolved")
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(len(result["points"]), 2)

    def test_sector_lengths_and_arc_spacing_do_not_exceed_frozen_bounds(self):
        self.geometry["rivers"] = [line((-2000, 0), (2000, 0))]
        result = self.compile()
        contracts = result["entries"][0]["contracts"]
        self.assertEqual(len(contracts), 8)
        for contract in contracts:
            self.assertLessEqual(contract["length_m"], 512)
            delta = np.diff(contract["points_xz"], axis=0)
            self.assertLessEqual(np.linalg.norm(delta, axis=1).max(), 64.000001)

    def test_clip_does_not_connect_reaches_across_outside_square(self):
        self.geometry["rivers"] = [
            {
                "pts": [
                    coord(8600, -100),
                    coord(8700, -100),
                    coord(8700, 100),
                    coord(8600, 100),
                ]
            }
        ]
        result = self.compile()
        contracts = result["entries"][0]["contracts"]
        self.assertEqual(len(contracts), 2)
        self.assertEqual({p[1] for c in contracts for p in c["points_xz"]}, {-100, 100})

    def test_names_and_repeated_fragments_never_merge_denominators(self):
        self.geometry["rivers"] = [
            line((0, 0), (1024, 0), name="same"),
            line((0, 100), (16, 100), name="same"),
        ]
        result = self.compile()
        self.assertEqual([len(e["contracts"]) for e in result["entries"]], [2, 1])

    def test_small_body_is_not_dropped_by_erosion_or_lattice(self):
        self.geometry["lakes"] = [body(2, 2, 3, 3)]
        result = self.compile()
        self.assertTrue(result["coverage_complete"])
        self.assertEqual(len(result["points"]), 1)
        self.assertTrue(result["entries"][0]["contracts"][0]["small_feature_point"])
        self.assertTrue(2 <= result["points"][0]["x"] <= 3)
        self.assertTrue(2 <= result["points"][0]["z"] <= 3)

    def test_large_body_uses_64m_lattice_after_padded_32m_erosion(self):
        self.geometry["oceans"] = [body(-8640, -8640, 8640, 8640)]
        result = self.compile()
        points = result["points"]
        self.assertTrue(points)
        self.assertTrue(all(p["x"] % 64 == p["z"] % 64 == 0 for p in points))
        self.assertTrue(all(max(abs(p["x"]), abs(p["z"])) <= 8608 for p in points))

    def test_holes_are_not_maintained_water(self):
        polygon = body(-256, -256, 256, 256)
        polygon["rings"].extend(body(-128, -128, 128, 128)["rings"])
        self.geometry["lakes"] = [polygon]
        self.assertTrue(
            all(max(abs(p["x"]), abs(p["z"])) > 128 for p in self.compile()["points"])
        )

    def test_only_explicit_intermit_or_underground_excluded(self):
        self.geometry["streams"] = [
            line((0, 0), (32, 0), intermittent=1),
            line((0, 64), (32, 64), intermittent=0),
            line((0, 128), (32, 128)),
            line((0, 192), (32, 192), brunnel="tunnel"),
        ]
        self.assertEqual(
            [e["status"] for e in self.compile()["entries"]],
            ["excluded", "compiled", "compiled", "excluded"],
        )

    def test_source_tag_conflict_and_missing_capture_stay_unresolved(self):
        self.geometry["streams"] = [
            line(
                (0, 0),
                (32, 0),
                intermittent=1,
                sourceFeature={"properties": {"intermittent": 0}},
            )
        ]
        del self.geometry["oceans"]
        result = self.compile()
        self.assertFalse(result["coverage_complete"])
        self.assertEqual(
            [e["status"] for e in result["entries"]], ["unresolved", "unresolved"]
        )

    def test_unknown_authored_water_and_invalid_geometry_are_not_omitted(self):
        self.geometry["streams"] = [{"pts": []}]
        self.hydro["sources"] = [{"class": "mystery"}]
        self.assertFalse(self.compile()["coverage_complete"])
        self.assertEqual(len(self.compile()["entries"]), 2)

    def test_engineered_anchors_are_compiled_without_observed_water(self):
        self.hydro["sources"] = [
            {"class": "reservoir", "position": [16, 0, 32]},
            {"class": "intake", "position": [64, 0, 32]},
        ]
        before = copy.deepcopy(self.hydro)
        result = self.compile()
        self.assertEqual(self.hydro, before)
        self.assertEqual(
            [c["kind"] for e in result["entries"] for c in e["contracts"]],
            ["engineered", "engineered"],
        )

    def test_infeasible_stream_and_missing_authored_support_stay_unresolved(self):
        self.geometry["streams"] = [line((0, 0), (32, 0))]
        self.hydro["rivers"][1]["unforced_infeasible_stream"] = True
        self.assertFalse(self.compile()["coverage_complete"])
        del self.hydro["rivers"]
        self.assertFalse(self.compile()["coverage_complete"])

    def test_authored_control_without_captured_natural_feature_is_unresolved(self):
        self.hydro["sources"] = [{"class": "river", "position": [0, 0, 0]}]
        self.assertFalse(self.compile()["coverage_complete"])

    def test_authored_grid_diagnostic_uses_south_first_64m_circle(self):
        self.geometry["streams"] = [line((0, 1024), (16, 1024))]
        inventory = self.compile()
        water = np.zeros((1081, 1081), dtype=np.uint16)
        water[604, 544] = 7
        result = initial_natural_checks(inventory, water)
        self.assertEqual(result["contracts"][0]["status"], "pass")
        water[604, 544] = 6
        self.assertEqual(
            initial_natural_checks(inventory, water)["contracts"][0]["status"], "fail"
        )
        water[540, 604] = 100
        self.assertEqual(
            initial_natural_checks(inventory, water)["contracts"][0]["status"], "fail"
        )


class OutcomeTests(unittest.TestCase):
    compile = InventoryTests.compile

    def setUp(self):
        InventoryTests.setUp(self)
        self.geometry["streams"] = [line((0, 0), (32, 0))]
        self.hydro["sources"] = [{"class": "reservoir", "position": [100, 0, 0]}]
        self.inventory = self.compile()
        self.report = {
            "start_frame": 100,
            "frames_per_game_minute": 100,
            "game_minutes": 60,
        }
        self.samples = [
            {
                "label": f"t{i * 5:03}",
                "stats": {"frame": 100 + i * 500},
                "water": {
                    "samples": [
                        {
                            "name": p["name"],
                            "x": p["x"],
                            "z": p["z"],
                            "depth": 0.5,
                            "max_depth_within_64m": 0.1001,
                        }
                        for p in self.inventory["points"]
                    ]
                },
            }
            for i in range(13)
        ]

    def evaluate(self):
        return feature_outcome(self.inventory, self.report, self.samples)

    def test_initialization_failure_is_not_hidden_by_later_recovery(self):
        self.samples[0]["water"]["samples"][0]["max_depth_within_64m"] = 0.1
        self.assertEqual(self.evaluate()["status"], "fail")

    def test_natural_strict_depth_and_engineered_inclusive_boundary(self):
        self.assertEqual(self.evaluate()["status"], "pass")
        self.samples[5]["water"]["samples"][-1]["depth"] = 0.499
        self.assertEqual(self.evaluate()["status"], "fail")

    def test_unresolved_coverage_and_missing_observations_cannot_pass(self):
        self.inventory["coverage_complete"] = False
        self.assertEqual(self.evaluate()["status"], "unknown")
        self.inventory["coverage_complete"] = True
        self.samples[0]["water"]["samples"] = []
        self.assertEqual(self.evaluate()["status"], "unknown")

    def test_missing_evidence_does_not_hide_a_known_failure(self):
        self.samples[0]["water"]["samples"][0]["max_depth_within_64m"] = 0
        self.samples[1]["water"]["samples"] = []
        self.assertEqual(self.evaluate()["status"], "fail")

    def test_short_gapped_or_duplicate_time_series_is_unknown(self):
        original = copy.deepcopy(self.samples)
        for fault in ("short", "gap", "label", "frame"):
            self.samples = copy.deepcopy(original)
            if fault == "short":
                self.samples.pop()
            elif fault == "gap":
                self.samples[-1]["stats"]["frame"] += 200
            elif fault == "label":
                self.samples[1]["label"] = self.samples[0]["label"]
            else:
                self.samples[1]["stats"]["frame"] = self.samples[0]["stats"]["frame"]
            with self.subTest(fault=fault):
                self.assertEqual(self.evaluate()["status"], "unknown")

    def test_nonfinite_or_duplicate_conflicting_readback_is_not_pass(self):
        self.samples[1]["water"]["samples"][0]["max_depth_within_64m"] = float("nan")
        self.assertEqual(self.evaluate()["status"], "unknown")

    def test_nonfinite_native_position_cannot_match_a_named_probe(self):
        self.samples[0]["water"]["samples"][0]["x"] = float("nan")
        self.assertEqual(self.evaluate()["status"], "unknown")

    def test_failed_small_feature_cannot_pool_with_healthy_body(self):
        self.geometry["lakes"] = [body(1024, 1024, 2048, 2048)]
        self.inventory = self.compile()
        for row in self.samples:
            row["water"]["samples"] = [
                {
                    "name": p["name"],
                    "x": p["x"],
                    "z": p["z"],
                    "depth": 1,
                    "max_depth_within_64m": 1,
                }
                for p in self.inventory["points"]
            ]
        self.samples[0]["water"]["samples"][0]["max_depth_within_64m"] = 0
        self.assertEqual(self.evaluate()["status"], "fail")

    def test_float32_native_coordinates_match_named_planned_probes(self):
        contract = self.inventory["entries"][0]["contracts"][0]
        contract["points_xz"][0][0] = 8123.456789
        for row in self.samples:
            row["water"]["samples"][0]["x"] = 8123.456789
        for row in self.samples:
            for p in row["water"]["samples"]:
                p["x"] = float(np.float32(p["x"]))
                p["z"] = float(np.float32(p["z"]))
        self.assertEqual(self.evaluate()["status"], "pass")
        self.samples[0]["water"]["samples"][0]["x"] += 1
        self.assertEqual(self.evaluate()["status"], "unknown")

    def test_exact_95_percent_is_per_sector_and_missing_is_unknown(self):
        contract = self.inventory["entries"][0]["contracts"][0]
        contract["points_xz"] = [[x, 0] for x in range(20)]
        contract["probe_names"] = [f"test:{x}" for x in range(20)]
        for row in self.samples:
            row["water"]["samples"] = [
                {
                    "name": f"test:{x}",
                    "x": x,
                    "z": 0,
                    "max_depth_within_64m": 0 if x == 19 else 1,
                }
                for x in range(20)
            ] + [row["water"]["samples"][-1]]
        self.assertEqual(self.evaluate()["status"], "pass")
        self.samples[0]["water"]["samples"][18]["max_depth_within_64m"] = 0
        self.assertEqual(self.evaluate()["status"], "fail")
        self.samples[0]["water"]["samples"].pop(18)
        self.assertEqual(self.evaluate()["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
