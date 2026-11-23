"""Readiness v3: the accepted v2 control gate with the versioned source closure.

Only the source-closure contract differs; every required-fact, graph, context,
build-index, cleanup and control-label rule is the accepted v2 rule.  A ready
result admits this finite measurement.  It never qualifies a prediction for
export and never activates a certificate.
"""

from __future__ import annotations

import schema
import schema_v3
from evidence import ArtifactStore
from protocol import (
    Label,
    exact,
    ProtocolError,
    Request,
    decide,
    entry,
    integer,
    position,
    strict_bool,
)
from readiness import Readiness, coverage, digest, runtime


def opening(frozen, observed, policy, prior_sessions, store):
    if observed.get("error") or strict_bool(observed.get("completed")) is not True:
        raise ProtocolError("control opening failed/incomplete (no replacement)")
    schema_v3.validate_opening(frozen, observed, policy, store)
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
    coverage(frozen["consumed_fields"], observed.get("consumed_fields"), "consumed fields")
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


def check(controls, observations, policy, prior_sessions, store=None):
    reasons = []
    try:
        if type(controls) is not list or not controls:
            raise ProtocolError("no controls frozen (require nonempty list)")
        if type(observations) is not dict:
            raise ProtocolError("observations: require map")
        if type(prior_sessions) is not set or any(
            type(v) is not str or not v for v in prior_sessions
        ):
            raise ProtocolError("prior_sessions: require set of nonempty strings")
        ids = []
        for control in controls:
            if (
                type(control) is not dict
                or type(control.get("case_id")) is not str
                or not control["case_id"]
            ):
                raise ProtocolError("frozen control: missing nonempty case_id")
            ids.append(control["case_id"])
        if len(ids) != len(set(ids)):
            raise ProtocolError("duplicate control opening")
        if set(observations) != set(ids):
            raise ProtocolError("control opening set differs; no replacement permitted")
        if not isinstance(store, ArtifactStore):
            raise ProtocolError(
                "missing retained artifact store; declarations are not evidence"
            )
    except ProtocolError as error:
        return Readiness(False, (str(error),))
    sessions = set(prior_sessions)
    for control in controls:
        try:
            observed = observations[control["case_id"]]
            if type(observed) is not dict:
                raise ProtocolError("observed control: require map")
            opening(control, observed, policy, sessions, store)
            sessions.add(observed["session_id"])
        except (ProtocolError, KeyError, TypeError, ValueError, OverflowError) as error:
            reasons.append(f"{control['case_id']}: {error}")
    return Readiness(not reasons, tuple(reasons))
