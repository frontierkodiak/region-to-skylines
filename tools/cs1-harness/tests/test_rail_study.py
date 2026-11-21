"""Observable rail qualification boundaries, independent of native success flags."""

import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from cs1_harness.rail_study import (
    PROTOCOL,
    ROOT,
    classify,
    compatible,
    context_valid,
    controls_valid,
    digest,
    freeze,
    plan,
)


def network():
    def segment(identity, start, end, outside):
        return {
            "id": identity,
            "start": start,
            "end": end,
            "a": [-8640, 0, 0],
            "b": [8640, 0, 0],
            "start_flags": "Created, Outside" if outside == "start" else "Created",
            "end_flags": "Created, Outside" if outside == "end" else "Created",
            "flags": "Created",
            "lanes": [
                {
                    "index": i,
                    "id": identity * 2 + i,
                    "vehicle": "Train",
                    "type": "Vehicle",
                    "category": "PassengerTrain, CargoTrain",
                    "flags": "Created",
                    "direction": direction,
                    "direction_bits": 1 if i == 0 else 2,
                    "forward": i == 0,
                    "backward": i == 1,
                }
                for i, direction in enumerate(["Forward", "Backward"])
            ],
        }

    return {"segments": [segment(1, 1, 2, "start"), segment(2, 2, 3, "end")]}


class RailStudyTest(unittest.TestCase):
    def test_directed_reciprocals_use_different_lanes_and_literal_offsets(self):
        frozen = plan(network())
        boundary = [r for r in frozen["requests"] if not r["diagnostic"]]
        self.assertEqual([(r["from"], r["to"]) for r in boundary], [([1, 0, 0], [2, 0, 255]), ([2, 1, 255], [1, 1, 0])])
        self.assertEqual(frozen["candidate_boundary_count"], 2)
        diagnostic = frozen["requests"][-1]
        self.assertEqual(diagnostic["from"], [2, 0, 255])
        end = frozen["endpoints"][1]
        self.assertFalse(compatible(end, end["lanes"][0], source=True))

    def test_segment_invert_changes_lane_eligibility_not_boundary_offset(self):
        net = network()
        net["segments"][0]["flags"] += ", Invert"
        boundary = [r for r in plan(net)["requests"] if not r["diagnostic"]]
        self.assertEqual(boundary[0]["from"], [1, 1, 0])
        self.assertEqual(boundary[1]["to"], [1, 0, 0])

    def test_avoid_direction_alias_does_not_drop_native_direction_bits(self):
        net = network()
        for segment in net["segments"]:
            for lane in segment["lanes"]:
                lane["direction"] = "Avoid" + lane["direction"]
        boundary = [row for row in plan(net)["requests"] if not row["diagnostic"]]
        self.assertEqual(len(boundary), 2)

    def test_no_lane_or_incomplete_inventory_does_not_guess(self):
        net = network()
        net["segments"][0]["lanes"] = []
        self.assertEqual(plan(net)["requests"], [])
        net = network()
        del net["segments"][0]["lanes"][0]["direction"]
        with self.assertRaisesRegex(ValueError, "inventory"):
            plan(net)

    def test_endpoint_mismatch_and_midpoint_are_not_literal_success(self):
        request = plan(network())["requests"][0]
        row = {
            "request": request,
            "result": {
                "complete": True,
                "released": True,
                "success": True,
                "positions": [request["from"], request["to"]],
            },
        }
        self.assertEqual(classify(row), "exact_path_success")
        row["result"]["positions"][-1] = [2, 0, 128]
        self.assertEqual(classify(row), "returned_endpoint_mismatch")
        row["result"]["success"] = False
        self.assertEqual(classify(row), "selected_query_failure")
        row["result"]["released"] = False
        self.assertEqual(classify(row), "Unknown")

    def test_missing_or_different_runtime_fails_closed(self):
        self.assertFalse(context_valid({}))
        build = {"game_executable_sha256": "exe", "game_assemblies": {"game.dll": "game"}, "dll_sha256": "mod"}
        identity = {
            "host_pid": 7,
            "process_start_ticks": "8",
            "observed_at": "today",
            "build_matches": True,
            "executable": {"sha256": "exe"},
            "excluded_dynamic_assemblies": ["dynamic"],
            "assemblies": [{"path": "/game.dll", "sha256": "game"}, {"path": "/Cs1Harness.dll", "sha256": "mod"}],
            "status": {
                "plugins": [{"name": "harness", "enabled": True}],
                "errors": [],
                "error_count": 0,
                "enabled_mod_count": 1,
            },
        }
        obs = {
            "launch_runtime_identity": identity,
            "runtime_identity": copy.deepcopy(identity),
            "build_receipt": build,
            "native_context": {
                "update_mode": "NewGameFromMap",
                "invert_traffic": "False",
                "no_workshop": True,
                "mods_enabled": True,
            },
        }
        self.assertTrue(context_valid(obs))
        obs["runtime_identity"]["process_start_ticks"] = "9"
        self.assertFalse(context_valid(obs))
        obs["runtime_identity"] = copy.deepcopy(identity)
        obs["runtime_identity"]["unresolved_loaded_assemblies"] = ["missing"]
        self.assertFalse(context_valid(obs))

    def test_no_positive_stock_control_forbids_cohort_and_freeze_is_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            study = Path(directory)
            freeze(study / "selection.json", {"controls": [{"slug": "stock-1"}]})
            self.assertFalse(controls_valid(study))
            with self.assertRaises(FileExistsError):
                freeze(study / "selection.json", {})

    def test_completed_control_failures_and_endpoint_mismatches_cannot_unlock_cohort(self):
        # Real retained context; synthetic networks/results below are unit data,
        # not new native witnesses. Exercise the complete qualification boundary.
        raw = ROOT / "tools/map-factory/capability-evidence/rail-v1/raw/stock-1/observation.json.gz"
        template = json.loads(gzip.decompress(raw.read_bytes()))
        with tempfile.TemporaryDirectory() as directory:
            study = Path(directory)
            freeze(
                study / "selection.json",
                {
                    "build_receipt": template["build_receipt"],
                    "controls": [
                        {"slug": slug, "artifact_sha256": template["artifact_sha256"]}
                        for slug in ["stock-1", "stock-2"]
                    ],
                },
            )
            for slug in ["stock-1", "stock-2"]:
                out = study / "raw" / slug
                freeze(out / "networks.json", network())
                planned = plan(network())
                observation = copy.deepcopy(template)
                observation["paths"] = [
                    {
                        "request": r,
                        "submitted_at": "2026-11-21T01:00:00Z",
                        "result": {"complete": True, "released": True, "success": False, "positions": []},
                    }
                    for r in planned["requests"]
                ]
                observation["query_freeze_sha256"] = freeze(
                    out / "query-freeze.json",
                    {
                        "selection_sha256": digest(study / "selection.json"),
                        "frozen_at": "2026-11-21T00:00:00Z",
                        "plan": planned,
                        "networks_sha256": digest(out / "networks.json"),
                        "protocol": PROTOCOL,
                        "artifact_sha256": observation["artifact_sha256"],
                        "runtime_identity": observation["runtime_identity"],
                    },
                )
                freeze(out / "observation.json", observation)
            self.assertFalse(controls_valid(study))
            path = study / "raw/stock-1/observation.json"
            observation = json.loads(path.read_text())
            row = observation["paths"][0]
            row["result"].update(success=True, positions=[row["request"]["from"], row["request"]["to"]])
            path.write_text(json.dumps(observation))
            self.assertTrue(controls_valid(study))
            row["result"]["positions"][-1] = [2, 0, 128]
            path.write_text(json.dumps(observation))
            self.assertFalse(controls_valid(study))


if __name__ == "__main__":
    unittest.main()
