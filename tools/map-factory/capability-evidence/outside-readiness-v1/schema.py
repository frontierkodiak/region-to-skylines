"""Version 2 input boundary. Validate required facts before equality checks."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from pathlib import PurePosixPath
from uuid import UUID

from evidence import ArtifactStore
from protocol import (
    ProtocolError,
    Request,
    entry,
    exact,
    integer,
    position,
    strict_bool,
)

CONSUMED_COVERAGE = frozenset(
    {
        "segment_ids",
        "node_ids",
        "endpoint_xyz",
        "segment_invert",
        "lane_index",
        "lane_type",
        "lane_vehicle",
        "lane_category",
        "lane_direction",
        "prefab_catalog",
        "outside_roles",
        "literal_request",
        "rule_constants",
        "reader_helper_closure",
    }
)
ROOTS = frozenset({"managed", "mono", "builtin_mods", "user_mods"})
ROLES = frozenset({"game", "driver", "collector", "auditor", "monitor"})
HASHES = frozenset(
    {
        "artifact_sha256",
        "source_sha256",
        "request_sha256",
        "prediction_sha256",
        "protocol_sha256",
    }
)
FROZEN = HASHES | {
    "case_id",
    "requests",
    "consumed_fields",
    "exact_graph_sha256",
    "source_files",
    "predictions",
}
OBSERVED = HASHES | {
    "completed",
    "error",
    "session_id",
    "native_context",
    "consumed_fields",
    "opening_graph",
    "post_graph",
    "runtime",
    "owned_processes",
    "cleanup",
    "paths",
}
POLICY = {
    "files",
    "roots",
    "plugins",
    "assemblies",
    "excluded_dynamic",
    "source_sha256",
    "dll_sha256",
    "protocol_sha256",
    "process_roles",
    "executable_path",
    "dll_path",
}
PHASE = POLICY - {"process_roles"} | {"pid", "start_ticks", "unresolved"}

# Known helper/producer closure, independent of the caller's source manifest.
# A future collector extension must version this set before measurement.
SOURCE_KEYS = frozenset(
    [
        "tools/map-factory/capability-evidence/outside-query-model-v1/" + name
        for name in ("model.py", "topology.py", "bridge.py")
    ]
    + [
        "tools/map-factory/" + name
        for name in (
            "crp.py",
            "netcodec.py",
            "network_writer.py",
            "template.py",
            "survey/measure_maps.py",
        )
    ]
    + [
        "tools/cs1-harness/mod/" + name
        for name in ("NetworkOps.cs", "Harness.cs", "CityOps.cs", "Json.cs")
    ]
    + [
        "tools/map-factory/capability-evidence/outside-stock-budget-v1/" + name
        for name in (
            "study.py",
            "prior-stock-catalogs.json",
            "build_study.py",
            "build.json",
        )
    ]
    + [
        "tools/map-factory/capability-evidence/outside-readiness-v1/" + name
        for name in ("protocol.py", "readiness.py", "schema.py", "evidence.py")
    ]
)


def text(value: object, where: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ProtocolError(f"{where}: require nonempty string")
    return value


def mapping(value: object, where: str) -> dict:
    if type(value) is not dict or not value:
        raise ProtocolError(f"{where}: require nonempty map")
    for key in value:
        text(key, where + " key")
    return value


def sequence(value: object, where: str, *, empty: bool = False) -> list:
    if type(value) is not list or (not empty and not value):
        raise ProtocolError(
            f"{where}: require {'possibly empty' if empty else 'nonempty'} list"
        )
    return value


def strings(value: object, where: str, *, empty: bool = False) -> list[str]:
    values = sequence(value, where, empty=empty)
    for item in values:
        text(item, where)
    if len(values) != len(set(values)):
        raise ProtocolError(f"{where}: duplicate entries")
    return values


def path_name(value: object, where: str, *, absolute: bool) -> str:
    name = text(value, where)
    p = PurePosixPath(name)
    if p.is_absolute() != absolute or ".." in p.parts or str(p) != name or name == ".":
        raise ProtocolError(
            f"{where}: require normalized {'absolute' if absolute else 'relative'} path"
        )
    return name


def hash_map(value: object, store: ArtifactStore, where: str) -> dict:
    rows = mapping(value, where)
    for name, hashed in rows.items():
        store.read(hashed, f"{where}.{name}")
    return rows


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def bound_json(store: ArtifactStore, hashed: object, value: object, where: str) -> None:
    if store.read(hashed, where) != canonical(value):
        raise ProtocolError(f"{where}: retained JSON bytes differ from declared value")


def process_map(value: object, where: str) -> None:
    rows = exact(value, set(ROLES), where)
    identities = set()
    for role, raw in rows.items():
        row = exact(raw, {"pid", "start_ticks", "gone"}, f"{where}.{role}")
        identity = (
            integer(row["pid"], 1, 2**31 - 1),
            integer(row["start_ticks"], 1, 2**63 - 1),
        )
        if identity in identities:
            raise ProtocolError(f"{where}: reused identity for different process roles")
        identities.add(identity)
        if strict_bool(row["gone"]) is not True:
            raise ProtocolError(f"{where}.{role}: process not gone")


def runtime_inventory(
    raw: object, store: ArtifactStore, where: str, *, phase: bool
) -> None:
    row = exact(raw, PHASE if phase else POLICY, where)
    files = hash_map(row["files"], store, where + ".files")
    for name in files:
        path_name(name, where + ".files key", absolute=True)
    for key in ("source_sha256", "dll_sha256", "protocol_sha256"):
        store.read(row[key], f"{where}.{key}")
    for key in ("executable_path", "dll_path"):
        name = path_name(row[key], where + "." + key, absolute=True)
        if name not in files:
            raise ProtocolError(f"{where}.{key}: absent from file inventory")
    if files[row["dll_path"]] != row["dll_sha256"]:
        raise ProtocolError(f"{where}: DLL hash not bound to actual inventoried file")
    plugins = mapping(row["plugins"], where + ".plugins")
    for name, raw_plugin in plugins.items():
        plugin = exact(
            raw_plugin, {"path", "enabled", "builtin"}, where + ".plugin." + name
        )
        path_name(plugin["path"], where + ".plugin path", absolute=True)
        strict_bool(plugin["enabled"])
        strict_bool(plugin["builtin"])
    if "Cs1Harness" not in plugins:
        raise ProtocolError(f"{where}: missing Cs1Harness plugin")
    roots = exact(
        row["roots"], set(ROOTS) | {"plugin:" + n for n in plugins}, where + ".roots"
    )
    game_root = PurePosixPath(row["executable_path"]).parent
    for role, suffix in {
        "managed": "Cities_Data/Managed",
        "mono": "Cities_Data/Mono",
        "builtin_mods": "Files/Mods",
    }.items():
        expected_path = str(game_root / suffix)
        if type(roots[role]) is not dict or roots[role].get("path") != expected_path:
            raise ProtocolError(
                f"{where}.{role}: missing required game inventory root {expected_path}"
            )
    if (
        type(roots["user_mods"]) is not dict
        or type(roots["user_mods"].get("path")) is not str
        or not roots["user_mods"]["path"].endswith("/Addons/Mods")
        or roots["user_mods"]["path"] == roots["builtin_mods"]["path"]
    ):
        raise ProtocolError(f"{where}: missing independent user Mods root")
    for name, raw_root in roots.items():
        root = exact(raw_root, {"path", "files"}, where + ".root." + name)
        root_path = path_name(root["path"], where + ".root path", absolute=True)
        listed = strings(root["files"], where + ".root files")
        # Derive membership from the full inventory; do not compare two omissions.
        actual = {p for p in files if PurePosixPath(p).is_relative_to(root_path)}
        if set(listed) != actual:
            raise ProtocolError(f"{where}.{name}: root file coverage differs")
        if name.startswith("plugin:") and root_path != plugins[name[7:]]["path"]:
            raise ProtocolError(f"{where}.{name}: plugin root path differs")
    covered = {p for root in roots.values() for p in root["files"]} | {
        row["executable_path"]
    }
    if set(files) != covered:
        raise ProtocolError(f"{where}: file outside declared inventory roots")
    assemblies = mapping(row["assemblies"], where + ".assemblies")
    for name, raw_assembly in assemblies.items():
        assembly = exact(
            raw_assembly, {"path", "sha256", "mvid"}, where + ".assembly." + name
        )
        filename = path_name(assembly["path"], where + ".assembly path", absolute=True)
        store.read(assembly["sha256"], where + ".assembly hash")
        try:
            UUID(text(assembly["mvid"], where + ".assembly MVID"))
        except (ValueError, AttributeError) as error:
            raise ProtocolError(f"{where}: invalid assembly MVID") from error
        if filename not in files or files[filename] != assembly["sha256"]:
            raise ProtocolError(
                f"{where}: assembly not bound to actual inventoried file"
            )
    if (
        "Cs1Harness" not in assemblies
        or assemblies["Cs1Harness"]["path"] != row["dll_path"]
        or not PurePosixPath(row["dll_path"]).is_relative_to(
            plugins["Cs1Harness"]["path"]
        )
    ):
        raise ProtocolError(f"{where}: harness assembly/plugin/DLL chain differs")
    exclusions = strings(
        row["excluded_dynamic"], where + ".excluded_dynamic", empty=True
    )
    if set(exclusions) - {"Anonymously Hosted DynamicMethods Assembly"}:
        raise ProtocolError(f"{where}: unsupported dynamic assembly exclusion")
    if phase:
        integer(row["pid"], 1, 2**31 - 1)
        integer(row["start_ticks"], 1, 2**63 - 1)
        if sequence(row["unresolved"], where + ".unresolved", empty=True):
            raise ProtocolError(f"{where}: unresolved loaded assembly")
    elif set(strings(row["process_roles"], where + ".process_roles")) != ROLES:
        raise ProtocolError(f"{where}: incomplete process role policy")


def graph(store: ArtifactStore, hashed: object, where: str) -> None:
    # Snapshot bytes are kept intact; this checks shape, not native decision law.
    value = store.json(hashed, where)
    exact(value, {"road", "ship", "air"}, where)
    for mode, records in value.items():
        for record in sequence(records, where + "." + mode):
            row = exact(
                record,
                {
                    "id",
                    "start",
                    "end",
                    "a",
                    "b",
                    "invert",
                    "prefab",
                    "outside",
                    "lanes",
                },
                where + ".segment",
            )
            for key in ("id", "start", "end"):
                integer(row[key], 1, 65535)
            for key in ("a", "b"):
                import math

                xyz = sequence(row[key], where + ".xyz")
                if len(xyz) != 3 or any(
                    type(v) not in (int, float) or not math.isfinite(v) for v in xyz
                ):
                    raise ProtocolError(f"{where}: malformed xyz")
            strict_bool(row["invert"])
            text(row["prefab"], where + ".prefab")
            outside = sequence(row["outside"], where + ".outside")
            if len(outside) != 2:
                raise ProtocolError(f"{where}: malformed Outside roles")
            for flag in outside:
                strict_bool(flag)
            for lane in sequence(row["lanes"], where + ".lanes"):
                exact(
                    lane,
                    {
                        "index",
                        "lane_type",
                        "vehicle",
                        "category",
                        "forward",
                        "backward",
                    },
                    where + ".lane",
                )
                integer(lane["index"], 0, 255)
                text(lane["lane_type"], where + ".lane_type")
                strings(lane["vehicle"], where + ".vehicle")
                text(lane["category"], where + ".category")
                strict_bool(lane["forward"])
                strict_bool(lane["backward"])


def request_plan(raw: object, where: str) -> dict:
    plan = exact(raw, {"kind", "max_length", "mode", "query_id", "request"}, where)
    text(plan["query_id"], where + ".query_id")
    if plan["kind"] not in ("positive", "invalid-vehicle") or plan["mode"] not in (
        "road",
        "ship",
        "air",
    ):
        raise ProtocolError(f"{where}: unsupported control kind/mode")
    req = exact(
        plan["request"],
        {"capability", "from", "to", "name", "position_kind"},
        where + ".request",
    )
    if (
        req["capability"] != plan["mode"]
        or req["name"] != "outside-to-outside"
        or req["position_kind"] != "boundary"
    ):
        raise ProtocolError(f"{where}: literal request metadata differs")
    Request(
        plan["mode"], position(req["from"]), position(req["to"]), plan["max_length"], 0
    )
    if plan["max_length"] != 100000:
        raise ProtocolError(f"{where}: control budget differs")
    return plan


def consumed_values(snapshot: dict, sources: dict, plans: list, protocol: dict) -> dict:
    """Derive coverage values from retained graph/input bytes, not hash declarations."""
    result = {
        "segment_ids": {m: [s["id"] for s in rows] for m, rows in snapshot.items()},
        "node_ids": {
            m: [[s["start"], s["end"]] for s in rows] for m, rows in snapshot.items()
        },
        "endpoint_xyz": {
            m: [[s["a"], s["b"]] for s in rows] for m, rows in snapshot.items()
        },
        "segment_invert": {
            m: [s["invert"] for s in rows] for m, rows in snapshot.items()
        },
        "prefab_catalog": {
            m: [s["prefab"] for s in rows] for m, rows in snapshot.items()
        },
        "outside_roles": {
            m: [s["outside"] for s in rows] for m, rows in snapshot.items()
        },
        "literal_request": {"requests": plans},
        "rule_constants": {
            "protocol": protocol,
            "rule": "lane:any_lane:forbidden",
            "chord_parameter": 100000,
        },
        "reader_helper_closure": sources,
    }
    for field, keys in {
        "lane_index": ["index"],
        "lane_type": ["lane_type"],
        "lane_vehicle": ["vehicle"],
        "lane_category": ["category"],
        "lane_direction": ["forward", "backward"],
    }.items():
        result[field] = {
            m: [[{k: lane[k] for k in keys} for lane in s["lanes"]] for s in rows]
            for m, rows in snapshot.items()
        }
    return result


def validate_opening(
    frozen: object, observed: object, policy: object, store: ArtifactStore
) -> None:
    f = exact(frozen, set(FROZEN), "frozen control")
    o = exact(observed, set(OBSERVED), "observed control")
    text(f["case_id"], "case_id")
    text(o["session_id"], "session_id")
    strict_bool(o["completed"])
    if o["error"] is not None:
        text(o["error"], "control error")
    entry(o["native_context"])
    for prefix, row in (("frozen", f), ("observed", o)):
        for key in HASHES:
            store.read(row[key], prefix + "." + key)
        consumed = exact(
            row["consumed_fields"], set(CONSUMED_COVERAGE), prefix + ".consumed_fields"
        )
        for field, hashed in consumed.items():
            evidence = exact(
                store.json(hashed, prefix + ".consumed." + field),
                {"field", "graph_sha256", "source_sha256", "values"},
                "consumed evidence",
            )
            if evidence["field"] != field:
                raise ProtocolError("consumed evidence field differs")
            store.read(evidence["graph_sha256"], "consumed graph")
            store.read(evidence["source_sha256"], "consumed source")
            if (
                evidence["graph_sha256"] != f["exact_graph_sha256"]
                or evidence["source_sha256"] != f["source_sha256"]
            ):
                raise ProtocolError("consumed evidence graph/source differs")
            if type(evidence["values"]) not in (list, dict) or not evidence["values"]:
                raise ProtocolError("consumed evidence values missing")
    exact(f["source_files"], set(SOURCE_KEYS), "required source closure")
    sources = hash_map(f["source_files"], store, "source_files")
    for name in sources:
        path_name(name, "source file", absolute=False)
    bound_json(store, f["source_sha256"], sources, "source manifest")
    here = Path(__file__).resolve().parent
    pinned = json.loads((here / "bindings.json").read_bytes())["sources"]
    for name, hashed in sources.items():
        expected = (
            pinned[name]
            if name in pinned
            else hashlib.sha256((here.parents[3] / name).read_bytes()).hexdigest()
        )
        if hashed != expected:
            raise ProtocolError(
                f"source closure: source differs from versioned file {name}"
            )
    plans = [
        request_plan(v, "frozen request") for v in sequence(f["requests"], "requests")
    ]
    if (
        len(plans) != 6
        or len({v["query_id"] for v in plans}) != 6
        or {(v["mode"], v["kind"]) for v in plans}
        != {
            (m, k)
            for m in ("road", "ship", "air")
            for k in ("positive", "invalid-vehicle")
        }
    ):
        raise ProtocolError(
            "control plan must contain exactly six unique mode/kind requests"
        )
    bound_json(store, f["request_sha256"], plans, "request manifest")
    predictions = exact(f["predictions"], {v["query_id"] for v in plans}, "predictions")
    if any(
        type(v) is not str or v not in ("success", "no_path")
        for v in predictions.values()
    ):
        raise ProtocolError("unsupported prediction value")
    bound_json(store, f["prediction_sha256"], predictions, "prediction manifest")
    protocol = exact(
        store.json(f["protocol_sha256"], "protocol"),
        {"version", "seed", "max_length", "entry", "invert_traffic"},
        "protocol",
    )
    if (
        type(protocol["version"]) is not int
        or protocol["version"] != 2
        or integer(protocol["seed"], 0, 2**32 - 1) != 857
        or type(protocol["max_length"]) is not int
        or protocol["max_length"] != 100000
        or protocol["entry"] != "NewGameFromMap"
        or strict_bool(protocol["invert_traffic"]) is not False
    ):
        raise ProtocolError("protocol constants differ")
    graph(store, f["exact_graph_sha256"], "frozen graph")
    values = consumed_values(
        store.json(f["exact_graph_sha256"], "graph"), sources, plans, protocol
    )
    for row in (f, o):
        for field, hashed in row["consumed_fields"].items():
            actual = store.json(hashed, "consumed " + field)["values"]
            if actual != values[field]:
                raise ProtocolError(
                    f"consumed {field}: values differ from retained inputs"
                )
    graph(store, o["opening_graph"], "opening graph")
    graph(store, o["post_graph"], "post graph")
    runtime_inventory(policy, store, "policy", phase=False)
    phases = exact(o["runtime"], {"launch", "pre", "post"}, "runtime phases")
    for phase, inventory in phases.items():
        runtime_inventory(inventory, store, "runtime." + phase, phase=True)
    process_map(o["owned_processes"], "owned processes")
    process_map(o["cleanup"], "cleanup")
    for raw in sequence(o["paths"], "paths"):
        row = exact(
            raw,
            {
                "plan",
                "pre_build_index",
                "pre_graph",
                "post_graph",
                "pre_context",
                "post_context",
                "effective",
                "result",
                "error",
            },
            "query",
        )
        request_plan(row["plan"], "query plan")
        integer(row["pre_build_index"], 0, 2**32 - 1)
        if row["error"] is not None:
            text(row["error"], "query error")
        for phase in ("pre", "post"):
            entry(row[phase + "_context"])
            graph(store, row[phase + "_graph"], "query " + phase + " graph")
