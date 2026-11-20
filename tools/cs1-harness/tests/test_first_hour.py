"""A final healthy snapshot must not hide a failed or unobserved opening."""

import argparse
import copy
import unittest

from cs1_harness.first_hour import assess
from cs1_harness.cli import cmd_run


def opening():
    utilities = [
        {
            "role": role,
            "flags": "Created, Active",
            "problems": "None",
            "connected_segments": 1,
            "requires_electricity": role != "power",
            "electricity_grid_powered": True,
        }
        for role in ("power", "water", "sewage")
    ]
    return {
        "requested_scenario": "first-hour",
        "game_minutes": 60.01,
        "scenario": {"state": "done", "result": {"land": {"samples": 3600, "dry_flat_km2": 1.5}}},
        "scenario_observations": [
            {
                "minute": minute,
                "status": {
                    "state": "done",
                    "utilities": copy.deepcopy(utilities),
                    "growable_problems": {},
                    "traffic": {"scope": "scenario road segments", "vehicles": 10, "moving": 7},
                },
            }
            for minute in range(0, 61, 5)
        ],
    }


def verdict(doc, city=None, panel="pass"):
    if city is None:
        city = [{"name": n, "status": "pass"} for n in ("population_growth", "outside_connection", "utilities")]
    return assess(doc, city, {"name": "new_game_panel", "status": panel})


class FirstHourTest(unittest.TestCase):
    def test_invalid_first_hour_stops_before_any_session_or_output(self):
        for change in ({"game_minutes": 10}, {"sample_every": 10}, {"from_save": "city.crp"}):
            args = dict(scenario="first-hour", game_minutes=60, sample_every=5, from_save=None) | change
            with self.assertRaisesRegex(SystemExit, "first-hour requires a fresh New Game"):
                cmd_run(None, argparse.Namespace(**args))

    def test_observed_complete_opening_passes(self):
        self.assertEqual(verdict(opening())["status"], "pass")

    def test_existing_test_city_does_not_claim_a_first_hour(self):
        doc = opening()
        doc["requested_scenario"] = "test-city"
        self.assertEqual(verdict(doc)["status"], "skip")

    def test_short_run_or_missing_samples_cannot_pass(self):
        for change in ({"game_minutes": 10}, {"scenario_observations": []}):
            doc = opening() | change
            self.assertEqual(verdict(doc)["status"], "fail")

    def test_a_sampling_gap_is_not_observation(self):
        doc = opening()
        del doc["scenario_observations"][5]
        self.assertFalse(verdict(doc)["value"]["checks"]["sample_coverage"])

    def test_recovered_service_failure_still_fails(self):
        for role in ("power", "water", "sewage"):
            doc = opening()
            facility = next(u for u in doc["scenario_observations"][4]["status"]["utilities"] if u["role"] == role)
            facility["problems"] = "Electricity" if role == "power" else "WaterNotConnected"
            self.assertFalse(verdict(doc)["value"]["checks"]["sampled_services"])

    def test_grown_building_failure_is_not_hidden_by_working_plant(self):
        doc = opening()
        doc["scenario_observations"][8]["status"]["growable_problems"] = {"Water, Electricity": 6}
        self.assertFalse(verdict(doc)["value"]["checks"]["sampled_services"])

    def test_energized_wire_or_active_flags_do_not_prove_consumer_cell_power(self):
        doc = opening()
        doc["scenario_observations"][3]["status"]["utilities"][2]["electricity_grid_powered"] = False
        self.assertFalse(verdict(doc)["value"]["checks"]["sampled_services"])

    def test_startup_only_service_warmup_is_allowed(self):
        doc = opening()
        doc["scenario_observations"][0]["status"]["utilities"] = []
        self.assertEqual(verdict(doc)["status"], "pass")

    def test_no_moving_or_unobserved_traffic_cannot_pass(self):
        for observed in (True, False):
            doc = opening()
            for o in doc["scenario_observations"]:
                if observed:
                    o["status"]["traffic"]["moving"] = 0
                else:
                    del o["status"]["traffic"]
            self.assertFalse(verdict(doc)["value"]["checks"]["sampled_traffic_movement"])

    def test_unrelated_highway_traffic_cannot_prove_city_traffic(self):
        doc = opening()
        for o in doc["scenario_observations"]:
            o["status"]["traffic"]["scope"] = "all spawned road vehicles"
        self.assertFalse(verdict(doc)["value"]["checks"]["sampled_traffic_movement"])

    def test_missing_native_panel_or_insufficient_land_fails(self):
        self.assertEqual(verdict(opening(), panel="skip")["status"], "fail")
        doc = opening()
        doc["scenario"]["result"]["land"]["dry_flat_km2"] = 0.01
        self.assertFalse(verdict(doc)["value"]["checks"]["starter_land"])

    def test_growth_or_connection_failure_cannot_be_overridden(self):
        self.assertEqual(verdict(opening(), [])["status"], "fail")
        for name in ("population_growth", "outside_connection", "utilities"):
            self.assertEqual(verdict(opening(), [{"name": name, "status": "fail"}])["status"], "fail")


if __name__ == "__main__":
    unittest.main()
