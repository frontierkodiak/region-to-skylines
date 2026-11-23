"""Version 4 consumer: unchanged fact checks, distinct validated helper role.

Derived from the pinned schema_v3.validate_opening/readiness_v3.opening. Only
source closure selection changes; no accepted source module is monkeypatched.
"""

from spec import closure_keys
import schema as v1
import schema
from evidence import ArtifactStore
from protocol import (
    ProtocolError,
    exact,
    entry,
    integer,
    position,
    strict_bool,
    Label,
    Request,
    decide,
)
from readiness import coverage, digest, runtime


def validate_consumed(row, f, values, store, prefix):
    for key in v1.HASHES:
        store.read(row[key], prefix + "." + key)
    consumed = exact(
        row["consumed_fields"],
        set(v1.CONSUMED_COVERAGE),
        prefix + ".consumed_fields",
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
    for field, hashed in row["consumed_fields"].items():
        actual = store.json(hashed, "consumed " + field)["values"]
        if actual != values[field]:
            raise ProtocolError(f"consumed {field}: values differ from retained inputs")


def validate_frozen(frozen, store: ArtifactStore, spec):
    """The actual consumer's input-only checks, also run BEFORE queue access."""
    f = exact(frozen, set(v1.FROZEN), "frozen control")
    v1.text(f["case_id"], "case_id")
    # The versioned boundary: the collector closure is required, not optional.
    exact(f["source_files"], set(closure_keys()), "required source closure")
    sources = v1.hash_map(f["source_files"], store, "source_files")
    for name in sources:
        v1.path_name(name, "source file", absolute=False)
    v1.bound_json(store, f["source_sha256"], sources, "source manifest")
    pinned = spec.value["sources"]["readiness_helpers"]["files"]
    for name, hashed in sources.items():
        if hashed != pinned[name]:
            raise ProtocolError(
                f"source closure: source differs from accepted/frozen file {name}"
            )
    plans = [
        v1.request_plan(v, "frozen request")
        for v in v1.sequence(f["requests"], "requests")
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
    v1.bound_json(store, f["request_sha256"], plans, "request manifest")
    predictions = exact(f["predictions"], {v["query_id"] for v in plans}, "predictions")
    if any(
        type(v) is not str or v not in ("success", "no_path")
        for v in predictions.values()
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
    validate_consumed(f, f, values, store, "frozen")
    return f, values


def validate_opening(frozen, observed, policy, store: ArtifactStore, spec) -> None:
    f, values = validate_frozen(frozen, store, spec)
    o = exact(observed, set(v1.OBSERVED), "observed control")
    v1.text(o["session_id"], "session_id")
    strict_bool(o["completed"])
    if o["error"] is not None:
        v1.text(o["error"], "control error")
    entry(o["native_context"])
    validate_consumed(o, f, values, store, "observed")
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


def opening(frozen, observed, policy, prior_sessions, store, spec):
    if observed.get("error") or strict_bool(observed.get("completed")) is not True:
        raise ProtocolError("control opening failed/incomplete (no replacement)")
    validate_opening(frozen, observed, policy, store, spec)
    if (
        type(observed.get("session_id")) is not str
        or not observed["session_id"]
        or observed["session_id"] in prior_sessions
    ):
        raise ProtocolError("missing or reused session identity")
    entry(observed.get("native_context"))
    for key in (
        "artifact_sha256",
        "source_sha256",
        "request_sha256",
        "prediction_sha256",
        "protocol_sha256",
    ):
        if key not in frozen or observed.get(key) != frozen[key]:
            raise ProtocolError(f"{key} not bound to frozen input")
    if set(frozen["consumed_fields"]) != set(schema.CONSUMED_COVERAGE):
        raise ProtocolError("consumed-field coverage key set differs")
    if (
        frozen["request_sha256"] != digest(frozen["requests"])
        or frozen["source_sha256"] != digest(frozen["source_files"])
        or frozen["prediction_sha256"] != digest(frozen["predictions"])
        or not frozen["source_files"]
        or not frozen["predictions"]
    ):
        raise ProtocolError("frozen source/request/prediction hash differs")
    for key in ("source_sha256", "protocol_sha256"):
        if policy[key] != frozen[key]:
            raise ProtocolError("runtime policy differs from freeze")
    coverage(
        frozen["consumed_fields"], observed.get("consumed_fields"), "consumed fields"
    )
    graph = frozen["exact_graph_sha256"]
    if (
        not graph
        or observed.get("opening_graph") != graph
        or observed.get("post_graph") != graph
    ):
        raise ProtocolError("opening/export/post graph identity differs")
    runtime(policy, observed.get("runtime"))
    coverage(observed["owned_processes"], observed.get("cleanup"), "PID/start cleanup")
    for value in observed["cleanup"].values():
        exact(value, {"pid", "start_ticks", "gone"}, "process")
        integer(value["pid"], 1, 2**31 - 1)
        integer(value["start_ticks"], 1, 2**63 - 1)
        if strict_bool(value["gone"]) is not True:
            raise ProtocolError("owned process still alive")
    if set(observed["owned_processes"]) != set(policy["process_roles"]):
        raise ProtocolError("driver/collector/game/auditor/monitor coverage differs")
    game = observed["owned_processes"]["game"]
    launch = observed["runtime"]["launch"]
    if (game["pid"], game["start_ticks"]) != (launch["pid"], launch["start_ticks"]):
        raise ProtocolError("runtime and cleanup game identity differ")
    expected = {r["query_id"]: r for r in frozen["requests"]}
    rows = observed.get("paths")
    if type(rows) is not list or len(rows) != len(expected):
        raise ProtocolError("missing/extra controls")
    seen = set()
    for row in rows:
        plan = row["plan"]
        qid = plan["query_id"]
        if qid in seen or qid not in expected or plan != expected[qid]:
            raise ProtocolError("control request replaced/duplicated")
        seen.add(qid)
        if row.get("error"):
            raise ProtocolError("control query errored")
        for phase in ("pre", "post"):
            if row.get(phase + "_graph") != graph:
                raise ProtocolError("query graph drift")
            context = row[phase + "_context"]
            entry(context)
            if context["frame"] < observed["native_context"]["frame"]:
                raise ProtocolError("stale query context")
        if row["post_context"]["frame"] < row["pre_context"]["frame"]:
            raise ProtocolError("query frame reversed")
        request = Request(
            plan["mode"],
            position(plan["request"]["from"]),
            position(plan["request"]["to"]),
            plan["max_length"],
            integer(row["pre_build_index"], 0, 2**32 - 1),
        )
        decision = decide(row.get("effective"), row.get("result"), request)
        expected_label = {
            "positive": Label.SUCCESS,
            "invalid-vehicle": Label.NO_PATH,
        }.get(plan["kind"])
        if expected_label is None or decision.literal_label != expected_label:
            raise ProtocolError(f"control failed/unknown: {qid}: {decision.reason}")
    for mode in ("road", "ship", "air"):
        kinds = {r["kind"] for r in expected.values() if r["mode"] == mode}
        if kinds != {"positive", "invalid-vehicle"}:
            raise ProtocolError(f"{mode}: incomplete control design")
