"""Fail-closed tests for the v2 cohort preparation and the v3 readiness gate.

The constructed context below is CONSTRUCTED: its runtime files, graph and
context are synthetic and cannot qualify a native observation.  Every negative
case must be rejected for the stated reason.
"""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

import stock_v2  # noqa: E402  (sets the accepted source paths)

import fixtures  # noqa: E402
import schema  # noqa: E402
import schema_v3  # noqa: E402
import readiness_v3  # noqa: E402
from evidence import ArtifactStore  # noqa: E402
from schema import canonical, consumed_values  # noqa: E402


def put(store: ArtifactStore, data: bytes) -> str:
    hashed = hashlib.sha256(data).hexdigest()
    (store.root / hashed).write_bytes(data)
    return hashed


def put_json(store: ArtifactStore, value) -> str:
    return put(store, canonical(value))


def constructed(store: ArtifactStore):
    native = fixtures.observation("hanami")
    plans = [row["plan"] for row in native["paths"]]
    sources = {
        name: put(store, (stock_v2.ROOT / name).read_bytes())
        for name in schema_v3.SOURCE_KEYS_V3
    }
    source_hash = put_json(store, sources)
    request_hash = put_json(store, plans)
    predictions = {
        p["query_id"]: ("success" if p["kind"] == "positive" else "no_path")
        for p in plans
    }
    protocol = {
        "version": 2,
        "seed": 857,
        "max_length": 100000,
        "entry": "NewGameFromMap",
        "invert_traffic": False,
    }
    snapshot = {}
    for mode, vehicle, category in [
        ("road", "Car", "PassengerCar"),
        ("ship", "Ship", "All"),
        ("air", "Plane", "All"),
    ]:
        snapshot[mode] = [
            {
                "id": 1,
                "start": 1,
                "end": 2,
                "a": [0, 0, 0],
                "b": [1, 0, 0],
                "invert": False,
                "prefab": "CONSTRUCTED",
                "outside": [True, True],
                "lanes": [
                    {
                        "index": 0,
                        "lane_type": "Vehicle",
                        "vehicle": [vehicle],
                        "category": category,
                        "forward": True,
                        "backward": True,
                    }
                ],
            }
        ]
    graph_hash = put_json(store, snapshot)
    coverage = {
        field: put_json(
            store,
            {
                "field": field,
                "graph_sha256": graph_hash,
                "source_sha256": source_hash,
                "values": values,
            },
        )
        for field, values in consumed_values(snapshot, sources, plans, protocol).items()
    }
    frozen = {
        "case_id": "CONSTRUCTED",
        "requests": plans,
        "source_files": sources,
        "predictions": predictions,
        "consumed_fields": coverage,
        "exact_graph_sha256": graph_hash,
        "artifact_sha256": put(store, b"CONSTRUCTED package bytes, not an actual CRP"),
        "source_sha256": source_hash,
        "request_sha256": request_hash,
        "prediction_sha256": put_json(store, predictions),
        "protocol_sha256": put_json(store, protocol),
    }
    files = {
        name: put(store, ("CONSTRUCTED file: " + name).encode())
        for name in (
            "/game/Cities.x64",
            "/game/Cities_Data/Managed/Assembly-CSharp.dll",
            "/game/Cities_Data/Mono/mono.so",
            "/game/Files/Mods/default.dll",
            "/user/Addons/Mods/Cs1Harness/Cs1Harness.dll",
        )
    }
    roots = {
        role: {
            "path": path,
            "files": sorted(p for p in files if p.startswith(path + "/")),
        }
        for role, path in {
            "managed": "/game/Cities_Data/Managed",
            "mono": "/game/Cities_Data/Mono",
            "builtin_mods": "/game/Files/Mods",
            "user_mods": "/user/Addons/Mods",
            "plugin:Cs1Harness": "/user/Addons/Mods/Cs1Harness",
        }.items()
    }
    dll_path = "/user/Addons/Mods/Cs1Harness/Cs1Harness.dll"
    policy = {
        "files": files,
        "roots": roots,
        "plugins": {
            "Cs1Harness": {
                "path": "/user/Addons/Mods/Cs1Harness",
                "enabled": False,
                "builtin": False,
            }
        },
        "assemblies": {
            "Cs1Harness": {
                "path": dll_path,
                "sha256": files[dll_path],
                "mvid": "bec503f1-964f-4198-a393-b138adff4758",
            }
        },
        "excluded_dynamic": ["Anonymously Hosted DynamicMethods Assembly"],
        "source_sha256": source_hash,
        "dll_sha256": files[dll_path],
        "protocol_sha256": frozen["protocol_sha256"],
        "process_roles": ["game", "driver", "collector", "auditor", "monitor"],
        "executable_path": "/game/Cities.x64",
        "dll_path": dll_path,
    }
    phase = {k: copy.deepcopy(v) for k, v in policy.items() if k != "process_roles"}
    phase.update(pid=100, start_ticks=1000, unresolved=[])
    processes = {
        role: {"pid": 100 + i, "start_ticks": 1000 + i, "gone": True}
        for i, role in enumerate(policy["process_roles"])
    }
    observed = {
        k: frozen[k]
        for k in (
            "artifact_sha256",
            "source_sha256",
            "request_sha256",
            "prediction_sha256",
            "protocol_sha256",
            "consumed_fields",
        )
    }
    observed.update(
        completed=True,
        error=None,
        session_id="CONSTRUCTED",
        native_context=native["native_context"],
        opening_graph=graph_hash,
        post_graph=graph_hash,
        runtime={k: copy.deepcopy(phase) for k in ("launch", "pre", "post")},
        owned_processes=processes,
        cleanup=copy.deepcopy(processes),
        paths=[],
    )
    for original in native["paths"]:
        context = dict(native["native_context"], frame=native["native_context"]["frame"] + 1)
        observed["paths"].append(
            {
                "plan": copy.deepcopy(original["plan"]),
                "pre_build_index": original["effective"]["build_index"],
                "pre_graph": graph_hash,
                "post_graph": graph_hash,
                "pre_context": dict(context),
                "post_context": dict(context),
                "effective": copy.deepcopy(original["effective"]),
                "result": copy.deepcopy(original["result"]),
                "error": None,
            }
        )
    return copy.deepcopy(frozen), observed, copy.deepcopy(policy)


class ConstructedGate(unittest.TestCase):
    def setUp(self):
        self.store = ArtifactStore(Path(self.id().replace(".", "_")))
        self.store.root.mkdir(parents=True, exist_ok=True)
        self.frozen, self.observed, self.policy = constructed(self.store)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.store.root, ignore_errors=True)

    def alt_graph(self):
        value = json.loads(self.store.read(self.frozen["exact_graph_sha256"], "graph"))
        value["road"][0]["prefab"] = "CONSTRUCTED-ALT"
        return put_json(self.store, value)

    def road_index(self):
        return next(
            i
            for i, row in enumerate(self.observed["paths"])
            if row["plan"]["mode"] == "road"
        )

    def check(self, controls=None, observations=None, policy=None, prior=None):
        return readiness_v3.check(
            [self.frozen] if controls is None else controls,
            {"CONSTRUCTED": self.observed} if observations is None else observations,
            self.policy if policy is None else policy,
            set() if prior is None else prior,
            self.store,
        )

    def assertRejected(self, result, fragment):
        self.assertFalse(result.ready_for_measurement)
        self.assertTrue(
            any(fragment in reason for reason in result.reasons),
            f"expected {fragment!r} in {result.reasons}",
        )

    def test_honest_constructed_context_is_ready_for_measurement(self):
        result = self.check()
        self.assertTrue(result.ready_for_measurement, result.reasons)
        self.assertEqual(result.pre_export_qualification, "unknown")

    def test_missing_versioned_collector_source_is_rejected(self):
        broken = copy.deepcopy(self.frozen)
        del broken["source_files"]["tools/map-factory/capability-evidence/outside-readiness-stock-v2/collect_v2.py"]
        self.assertRejected(self.check([broken]), "required source closure")

    def test_extra_source_is_rejected(self):
        broken = copy.deepcopy(self.frozen)
        broken["source_files"]["extra.py"] = broken["source_sha256"]
        self.assertRejected(self.check([broken]), "required source closure")

    def test_shared_omission_of_consumed_field_is_rejected(self):
        frozen = copy.deepcopy(self.frozen)
        observed = copy.deepcopy(self.observed)
        field = sorted(frozen["consumed_fields"])[0]
        del frozen["consumed_fields"][field]
        del observed["consumed_fields"][field]
        self.assertRejected(
            self.check([frozen], {"CONSTRUCTED": observed}), "consumed_fields"
        )

    def test_all_null_consumed_fields_are_rejected(self):
        frozen = copy.deepcopy(self.frozen)
        frozen["consumed_fields"] = {k: None for k in frozen["consumed_fields"]}
        self.assertRejected(self.check([frozen]), "SHA-256")

    def test_string_false_meta_bool_is_accepted(self):
        context = dict(self.observed["native_context"], invert_traffic="False")
        observed = copy.deepcopy(self.observed)
        observed["native_context"] = context
        self.assertTrue(self.check(observations={"CONSTRUCTED": observed}).ready_for_measurement)

    def test_numeric_meta_bool_is_rejected(self):
        context = dict(self.observed["native_context"], invert_traffic=0)
        observed = copy.deepcopy(self.observed)
        observed["native_context"] = context
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "MetaBool")

    def test_missing_transport_ok_is_rejected(self):
        observed = copy.deepcopy(self.observed)
        observed["paths"][0]["effective"].pop("ok")
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "transport status")

    def test_wrong_handle_is_rejected(self):
        observed = copy.deepcopy(self.observed)
        observed["paths"][0]["result"]["id"] += 1
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "handle")

    def test_wrong_endpoint_is_rejected(self):
        observed = copy.deepcopy(self.observed)
        observed["paths"][0]["effective"]["to"] = [9, 0, 255]
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "endpoints")

    def test_wrong_category_is_rejected(self):
        observed = copy.deepcopy(self.observed)
        observed["paths"][self.road_index()]["effective"]["category"] = "All"
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "category")

    def test_wrong_lane_mask_is_rejected(self):
        observed = copy.deepcopy(self.observed)
        observed["paths"][self.road_index()]["effective"]["lane_types"] = "Vehicle, TransportVehicle"
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "lane mask")

    def test_wrong_seed_is_rejected(self):
        observed = copy.deepcopy(self.observed)
        observed["paths"][0]["effective"]["seed"] = 858
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "seed")

    def test_wrong_budget_is_rejected(self):
        observed = copy.deepcopy(self.observed)
        observed["paths"][0]["effective"]["max_length"] = 200000
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "maxLength")

    def test_wrong_independent_build_index_is_rejected(self):
        observed = copy.deepcopy(self.observed)
        observed["paths"][0]["pre_build_index"] += 1
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "build index")

    def test_graph_drift_is_rejected(self):
        observed = copy.deepcopy(self.observed)
        observed["post_graph"] = self.alt_graph()
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "graph identity")

    def test_query_graph_drift_is_rejected(self):
        observed = copy.deepcopy(self.observed)
        observed["paths"][0]["pre_graph"] = self.alt_graph()
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "graph")

    def test_missing_process_role_is_rejected(self):
        observed = copy.deepcopy(self.observed)
        del observed["owned_processes"]["monitor"]
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "exactly")

    def test_live_owned_process_is_rejected(self):
        observed = copy.deepcopy(self.observed)
        observed["cleanup"]["monitor"]["gone"] = False
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "not gone")

    def test_control_label_disagreement_is_rejected(self):
        observed = copy.deepcopy(self.observed)
        index = next(
            i
            for i, row in enumerate(observed["paths"])
            if row["plan"]["kind"] == "positive"
        )
        observed["paths"][index]["result"]["success"] = False
        observed["paths"][index]["result"]["flags"] = 8
        observed["paths"][index]["result"]["positions"] = []
        self.assertRejected(self.check(observations={"CONSTRUCTED": observed}), "control failed")

    def test_reused_prior_session_is_rejected(self):
        result = self.check(prior={"CONSTRUCTED"})
        self.assertRejected(result, "reused session")

    def test_missing_plugin_state_is_rejected(self):
        policy = copy.deepcopy(self.policy)
        policy["plugins"]["Cs1Harness"]["enabled"] = 0
        self.assertRejected(self.check(policy=policy), "boolean")


class PreparationBoundaries(unittest.TestCase):
    def test_mvid_parser_matches_known_game_bytes(self):
        base = Path("/peach/Games/SteamLibrary/steamapps/common/Cities_Skylines")
        cases = {
            base / "Files/Mods/UnlockAll/UnlockAll.dll": "e629942e-a063-4292-b233-2911e326d70b",
            base / "Files/Mods/UnlimitedSoil/UnlimitedSoil.dll": "b03f610f-ee01-4732-b3be-b005cdd35ef7",
        }
        import build_v2

        for path, expected in cases.items():
            if path.exists():
                self.assertEqual(build_v2.module_version_id(path), expected)

    def test_exclusion_table_is_content_keyed_and_binds_sources(self):
        table = stock_v2.exclusion_table()
        self.assertTrue(table)
        for row in table.values():
            self.assertTrue(row["categories"])
            self.assertTrue(row["sources"])
        stock, geographic, old_freeze = stock_v2.exclusion_sources()
        self.assertEqual(len(geographic), 9)
        self.assertEqual(len(stock["selected"]), 10)
        self.assertEqual(len(stock["controls"]), 2)
        for record in old_freeze["selected"]:
            self.assertIn(record["sha256"], table)

    def test_selection_fails_closed_when_cells_are_missing(self):
        rows = []
        covered = ["road:success", "road:no_path", "ship:success"]
        for index in range(3):
            rows.append(
                {
                    "sha256": f"{index:064x}",
                    "locator": f"/x/{index}.crp",
                    "exclusion": None,
                    "supported": True,
                    "cells": {
                        f"{m}:{c}": int(f"{m}:{c}" == covered[index])
                        for m in ("road", "ship", "air")
                        for c in ("success", "no_path")
                    },
                }
            )
        selection = stock_v2.select(rows)
        self.assertEqual(len(selection["selected"]), 3)
        self.assertIn("air:no_path", selection["missing_cells"])

    def test_selection_prefers_one_package_covering_six_cells(self):
        cells = {f"{m}:{c}": 1 for m in ("road", "ship", "air") for c in ("success", "no_path")}
        rows = [
            {"sha256": "0" * 63 + "1", "locator": "/a.crp", "exclusion": None, "supported": True, "cells": cells},
            {"sha256": "0" * 63 + "2", "locator": "/b.crp", "exclusion": None, "supported": True, "cells": cells},
        ]
        selection = stock_v2.select(rows)
        self.assertEqual(len(selection["selected"]), 1)
        self.assertEqual(selection["selected"][0]["locator"], "/a.crp")


if __name__ == "__main__":
    unittest.main()
