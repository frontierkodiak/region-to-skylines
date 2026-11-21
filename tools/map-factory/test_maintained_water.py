"""An empty engineered pond cannot hide behind pooled river retention."""

import copy
import unittest

from maintained_water import storage_outcome


class StorageOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.hydro = {"sources": [{"class": "reservoir", "position": [0, 0, 0]}]}
        self.report = {
            "start_frame": 0,
            "frames_per_game_minute": 3600,
            "game_minutes": 60,
        }
        self.samples = [
            {
                "label": f"t{i * 5:03}",
                "stats": {"frame": i * 5 * 3600},
                "water": {
                    "samples": [
                        {"x": 0, "z": 0, "depth": 0.5, "max_depth_within_64m": 2}
                    ]
                },
            }
            for i in range(13)
        ]

    def test_every_engineered_anchor_passes_at_exact_depth_boundary(self):
        result = storage_outcome(self.hydro, self.report, self.samples)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["anchors"][0]["minimum_exact_depth_m"], 0.5)

    def test_pooled_98_percent_and_nearby_water_do_not_rescue_empty_pond(self):
        for row in self.samples:
            row["water"]["samples"].extend(
                {"x": x, "z": 100, "depth": 1} for x in range(49)
            )
        self.samples[1]["water"]["samples"][0]["depth"] = 0
        self.assertGreaterEqual(49 / 50, 0.95)
        result = storage_outcome(self.hydro, self.report, self.samples)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["anchors"][0]["failed_samples"], ["t005"])

    def test_missing_anchor_or_short_observation_is_unknown(self):
        shortened = self.samples[:-1]
        self.assertEqual(
            storage_outcome(self.hydro, self.report, shortened)["status"], "unknown"
        )
        self.samples[5]["water"]["samples"] = []
        self.assertEqual(
            storage_outcome(self.hydro, self.report, self.samples)["status"], "unknown"
        )

    def test_large_gap_or_nonfinite_depth_cannot_pass(self):
        self.samples[-1]["stats"]["frame"] = 70 * 3600
        self.assertEqual(
            storage_outcome(self.hydro, self.report, self.samples)["status"], "unknown"
        )
        self.samples[-1]["stats"]["frame"] = 60 * 3600
        self.samples[3]["water"]["samples"][0]["depth"] = float("nan")
        self.assertEqual(
            storage_outcome(self.hydro, self.report, self.samples)["status"], "unknown"
        )

    def test_known_violation_is_not_hidden_by_missing_samples(self):
        self.samples[0]["water"]["samples"][0]["depth"] = 0
        self.samples[1]["water"]["samples"] = []
        self.assertEqual(
            storage_outcome(self.hydro, self.report, self.samples)["status"], "fail"
        )

    def test_no_engineered_storage_is_not_a_water_qualification(self):
        hydro = copy.deepcopy(self.hydro)
        hydro["sources"][0]["class"] = "river"
        self.assertEqual(
            storage_outcome(hydro, self.report, self.samples)["status"],
            "not_applicable",
        )
