"""CONSTRUCTED byte-backed context. No actual DLL, native observation or cert."""

import copy
import hashlib

from evidence import ArtifactStore
import fixtures
from schema import SOURCE_KEYS, canonical, consumed_values


def put(store: ArtifactStore, data: bytes) -> str:
    hashed = hashlib.sha256(data).hexdigest()
    (store.root / hashed).write_bytes(data)
    return hashed


def put_json(store: ArtifactStore, value: object) -> str:
    return put(store, canonical(value))


def constructed(store: ArtifactStore):
    native = fixtures.observation("hanami")
    plans = [row["plan"] for row in native["paths"]]
    sources = {
        name: put(store, (fixtures.ROOT / name).read_bytes()) for name in SOURCE_KEYS
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
        context = dict(
            native["native_context"], frame=native["native_context"]["frame"] + 1
        )
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
    return copy.deepcopy(frozen), observed, policy
