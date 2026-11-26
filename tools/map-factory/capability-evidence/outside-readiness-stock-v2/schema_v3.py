"""Version 3 input boundary: the accepted v2 checks plus this study's collector.

The accepted module at `outside-readiness-v1` versions its source closure in
`schema.SOURCE_KEYS` and says explicitly that adding a collector requires a
reviewed schema version whose freeze includes that collector.  This module is
that version.  It does not change or import-replace the accepted v2 module.
It re-runs the same required-fact checks and the same equality rules, and the
only contract difference is that `SOURCE_KEYS_V3` also requires the study-local
collector, driver, auditor, build and schema files below.

Everything here is frozen before the first new control request.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import schema as v1
from evidence import ArtifactStore
from protocol import ProtocolError, exact, entry, integer, position, strict_bool

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V1 = HERE.parent / "outside-readiness-v1"

NEW_SOURCES = frozenset(
    "tools/map-factory/capability-evidence/outside-readiness-stock-v2/" + name
    for name in (
        "stock_v2.py",
        "schema_v3.py",
        "readiness_v3.py",
        "check_study.py",
        "build_v2.py",
        "collect_v2.py",
        "run_v2.py",
        "audit_v2.py",
        "bundle_v2.py",
        "evaluate_v2.py",
    )
)
SOURCE_KEYS_V3 = frozenset(v1.SOURCE_KEYS) | NEW_SOURCES


def source_keys():
    return SOURCE_KEYS_V3


def pinned_sources():
    """Accepted hash for an old file, current frozen-tree hash for a new one."""
    pinned = json.loads((V1 / "bindings.json").read_bytes())["sources"]
    result = {}
    for name in SOURCE_KEYS_V3:
        if name in pinned:
            result[name] = pinned[name]
        else:
            path = ROOT / name
            if not path.is_file():
                raise ProtocolError(f"required source closure: missing {name}")
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def validate_opening(frozen, observed, policy, store: ArtifactStore) -> None:
    """Same body as the accepted v2 validator, with the extended source set."""
    f = exact(frozen, set(v1.FROZEN), "frozen control")
    o = exact(observed, set(v1.OBSERVED), "observed control")
    v1.text(f["case_id"], "case_id")
    v1.text(o["session_id"], "session_id")
    strict_bool(o["completed"])
    if o["error"] is not None:
        v1.text(o["error"], "control error")
    entry(o["native_context"])
    for prefix, row in (("frozen", f), ("observed", o)):
        for key in v1.HASHES:
            store.read(row[key], prefix + "." + key)
        consumed = exact(
            row["consumed_fields"], set(v1.CONSUMED_COVERAGE), prefix + ".consumed_fields"
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
    # The versioned boundary: the collector closure is required, not optional.
    exact(f["source_files"], set(SOURCE_KEYS_V3), "required source closure")
    sources = v1.hash_map(f["source_files"], store, "source_files")
    for name in sources:
        v1.path_name(name, "source file", absolute=False)
    v1.bound_json(store, f["source_sha256"], sources, "source manifest")
    pinned = pinned_sources()
    for name, hashed in sources.items():
        if hashed != pinned[name]:
            raise ProtocolError(
                f"source closure: source differs from accepted/frozen file {name}"
            )
    plans = [
        v1.request_plan(v, "frozen request") for v in v1.sequence(f["requests"], "requests")
    ]
    if (
        len(plans) != 6
        or len({v["query_id"] for v in plans}) != 6
        or {(v["mode"], v["kind"]) for v in plans}
        != {(m, k) for m in ("road", "ship", "air") for k in ("positive", "invalid-vehicle")}
    ):
        raise ProtocolError("control plan must contain exactly six unique mode/kind requests")
    v1.bound_json(store, f["request_sha256"], plans, "request manifest")
    predictions = exact(f["predictions"], {v["query_id"] for v in plans}, "predictions")
    if any(
        type(v) is not str or v not in ("success", "no_path") for v in predictions.values()
    ):
        raise ProtocolError("unsupported prediction value")
    v1.bound_json(store, f["prediction_sha256"], predictions, "prediction manifest")
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
    v1.graph(store, f["exact_graph_sha256"], "frozen graph")
    values = v1.consumed_values(
        store.json(f["exact_graph_sha256"], "graph"), sources, plans, protocol
    )
    for row in (f, o):
        for field, hashed in row["consumed_fields"].items():
            actual = store.json(hashed, "consumed " + field)["values"]
            if actual != values[field]:
                raise ProtocolError(f"consumed {field}: values differ from retained inputs")
    v1.graph(store, o["opening_graph"], "opening graph")
    v1.graph(store, o["post_graph"], "post graph")
    v1.runtime_inventory(policy, store, "policy", phase=False)
    phases = exact(o["runtime"], {"launch", "pre", "post"}, "runtime phases")
    for phase, inventory in phases.items():
        v1.runtime_inventory(inventory, store, "runtime." + phase, phase=True)
    v1.process_map(o["owned_processes"], "owned processes")
    v1.process_map(o["cleanup"], "cleanup")
    for raw in v1.sequence(o["paths"], "paths"):
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
        v1.request_plan(row["plan"], "query plan")
        integer(row["pre_build_index"], 0, 2**32 - 1)
        if row["error"] is not None:
            v1.text(row["error"], "query error")
        for phase in ("pre", "post"):
            entry(row[phase + "_context"])
            v1.graph(store, row[phase + "_graph"], "query " + phase + " graph")
