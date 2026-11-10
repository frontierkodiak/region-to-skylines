"""Prevent unbuilt, disconnected and temporarily growing fixtures from passing."""

import unittest

from cs1_harness.verdict import scenario_checks


def report(final=120, reached=2.0, directions=("inbound", "outbound")):
    return {
        "requested_scenario": "test-city",
        "curve": [{"minute": 0, "population": 0}, {"minute": 10, "population": final}],
        "population_observations": [{"minute": reached, "population": 60}],
        "scenario": {
            "state": "done",
            "final": {
                "utilities": [
                    {"role": role, "flags": "Created, Completed, Active", "problems": "None", "connected_segments": 1}
                    for role in ("power", "water", "sewage")
                ]
            },
            "reachability": {
                "complete": True,
                "paths": [
                    {
                        "direction": d,
                        "success": True,
                        "positions": [[1, 0, 128], [100, 0, 255]],
                        "released": True,
                        "grid_segment": 1,
                        "edge_segment": 100,
                        "edge_offset": 255,
                    }
                    for d in directions
                ],
            },
        },
    }


def statuses(doc):
    return {r["name"]: r["status"] for r in scenario_checks(doc)}


class ScenarioVerdictTest(unittest.TestCase):
    def test_empty_map_is_not_a_growth_test(self):
        self.assertEqual(set(statuses({}).values()), {"skip"})

    def test_growth_and_both_native_directions_pass(self):
        self.assertEqual(set(statuses(report()).values()), {"pass"})

    def test_missing_scenario_evidence_fails(self):
        self.assertEqual(set(statuses({"requested_scenario": "test-city"}).values()), {"fail"})

    def test_growth_after_deadline_and_collapsed_city_fail(self):
        for doc in (report(reached=6), report(final=0)):
            with self.subTest(doc=doc):
                self.assertEqual(statuses(doc)["population_growth"], "fail")

    def test_one_way_connection_cannot_pass(self):
        self.assertEqual(statuses(report(directions=("outbound",)))["outside_connection"], "fail")

    def test_summary_booleans_without_native_evidence_cannot_pass(self):
        doc = report(directions=())
        doc["scenario"]["reachability"].update(inbound=True, outbound=True)
        self.assertEqual(statuses(doc)["outside_connection"], "fail")

    def test_path_to_highway_midpoint_is_not_an_exit_proof(self):
        doc = report()
        for path in doc["scenario"]["reachability"]["paths"]:
            path["positions"][-1][2] = 128
        self.assertEqual(statuses(doc)["outside_connection"], "fail")

    def test_population_growth_does_not_excuse_disconnected_water(self):
        doc = report()
        doc["scenario"]["final"]["utilities"][1].update(problems="WaterNotConnected", connected_segments=0)
        self.assertEqual(statuses(doc)["population_growth"], "pass")
        self.assertEqual(statuses(doc)["utilities"], "fail")


if __name__ == "__main__":
    unittest.main()
