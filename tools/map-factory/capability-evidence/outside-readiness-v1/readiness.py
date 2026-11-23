"""Input/control-only readiness. Never reads experimental labels or enables certs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from protocol import (
    Label,
    ProtocolError,
    Request,
    decide,
    entry,
    exact,
    integer,
    position,
    strict_bool,
)


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Readiness:
    ready_for_measurement: bool
    reasons: tuple[str, ...]
    pre_export_qualification: str = "unknown"
    missing_native_fact: str = (
        "No independently validated native decision law relating "
        "the consumed place/export fields to literal path results; "
        "chord parameter has no native-cost conversion."
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


def coverage(expected: dict, actual: dict, where: str) -> None:
    if not expected or actual != expected:
        raise ProtocolError(f"{where}: incomplete or changed coverage")


def runtime(policy: dict, phases: object) -> None:
    """Compare full file/plugin/assembly sets, not an inventory-present boolean.

    Policy is frozen before controls; file equality is not memory attestation.
    Process coverage includes driver/collector/auditor/monitor outside the game.
    """
    phases = exact(phases, {"launch", "pre", "post"}, "runtime phases")
    if any(value is not True for value in policy["roots"].values()):
        raise ProtocolError("missing required inventory root")
    if set(policy["process_roles"]) != {
        "game",
        "driver",
        "collector",
        "auditor",
        "monitor",
    }:
        raise ProtocolError("incomplete process role policy")
    identity = None
    for phase, raw in phases.items():
        row = exact(
            raw,
            {
                "pid",
                "start_ticks",
                "files",
                "roots",
                "plugins",
                "assemblies",
                "unresolved",
                "excluded_dynamic",
                "source_sha256",
                "dll_sha256",
                "protocol_sha256",
            },
            phase,
        )
        current = (
            integer(row["pid"], 1, 2**31 - 1),
            integer(row["start_ticks"], 1, 2**63 - 1),
        )
        if identity is not None and current != identity:
            raise ProtocolError("runtime PID/start changed")
        identity = current
        for key in ("files", "roots", "plugins", "assemblies"):
            coverage(policy[key], row[key], f"{phase}.{key}")
        if (
            row["unresolved"] != []
            or row["excluded_dynamic"] != policy["excluded_dynamic"]
        ):
            raise ProtocolError("unresolved or undeclared dynamic assembly")
        for key in ("source_sha256", "dll_sha256", "protocol_sha256"):
            if row[key] != policy[key]:
                raise ProtocolError(f"{phase}.{key} differs")


def opening(
    frozen: dict, observed: dict, policy: dict, prior_sessions: set[str]
) -> None:
    """Validate one fresh control opening against pre-label inputs only."""
    if observed.get("error") or strict_bool(observed.get("completed")) is not True:
        raise ProtocolError("control opening failed/incomplete (no replacement)")
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
    if set(frozen["consumed_fields"]) != CONSUMED_COVERAGE:
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
    # Every value in these maps is a literal PID/start identity plus gone state;
    # equality to a nonempty map alone cannot turn a live process into gone.
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
        # New observation requirement: independently sampled build index before
        # CreatePath. Do not use effective.build_index as its own oracle.
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


def check(
    controls: list[dict], observations: dict, policy: dict, prior_sessions: set[str]
) -> Readiness:
    reasons = []
    if not controls:
        reasons.append("no controls frozen")
    if set(observations) != {c["case_id"] for c in controls}:
        reasons.append("control opening set differs; no replacement permitted")
    sessions = set(prior_sessions)
    for control in controls:
        try:
            observed = observations.get(control["case_id"], {})
            opening(control, observed, policy, sessions)
            sessions.add(observed["session_id"])
        except (ProtocolError, KeyError, TypeError, ValueError) as error:
            reasons.append(f"{control['case_id']}: {error}")
    return Readiness(not reasons, tuple(reasons))
