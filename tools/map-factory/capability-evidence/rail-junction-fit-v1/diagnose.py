"""Explain the frozen rules' remaining errors mechanically, after the freeze.

This script reads labels, so it runs after `freeze.py` and is not part of the
prediction path. Its job is the question a score cannot answer: at which node,
and with which angle, does a rule disagree with the game?

What it reports:

* for the frozen reference rule's false negative, the **native path
  transitions** from the observed successful path and the first transition the
  rule rejects, as an outcome diagnostic only;
* for its false positives, the **model witness path** it predicted, each
  transition's chord and tangent turn, and whether that exact transition was
  ever traversed in a native successful path of the same opening;
* the **old greedy choice beside the export geometry** at each involved node:
  every incident Train segment pair's chord and tangent turn, and the disjoint
  pairing the continuation rule derives from each measure;
* an input-only geometry section: how often chord and tangent continuation
  pairings differ, on all 11 packages, computed from topology alone.

Successful segment ids appear here as diagnostics only. They are never a
predictive input, a lookup exception or a place rule; `predictions.json` and
`evaluation.json` are already frozen before this file reads them.

Run:  .venv/bin/python capability-evidence/rail-junction-fit-v1/diagnose.py
"""

from __future__ import annotations

import argparse
import datetime
import heapq
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[1]), str(HERE)]

import binding  # noqa: E402
import export_topology as exports  # noqa: E402
import junction_model as jm  # noqa: E402
import model  # noqa: E402
import topology  # noqa: E402

FREEZE = "rail-junction-fit-v1"
PROTOCOL = HERE / "protocol.json"
FEATURES = HERE / "features.json"
PREDICTIONS = HERE / "predictions.json"
EVALUATION = HERE / "evaluation.json"
DIAGNOSTICS = HERE / "diagnostics.json"
REFERENCE = jm.PRIMARY_REFERENCE
CORRESPONDENCE = jm.PRIMARY_EQUIVALENT


# ------------------------------------------------------------------- witness


def _search(segments, incident, partners, request, pairing, max_length):
    """`model._reach`, with predecessors kept so a success can be shown."""
    source, source_lane = model._lookup(segments, request, "from")
    target, target_lane = model._lookup(segments, request, "to")
    start = model.endpoint_node(source, request["from"][2])
    finish = model.endpoint_node(target, request["to"][2])
    if not model.can_travel(source, source_lane, start):
        return None, "source_lane_cannot_leave_node"
    if not model.can_travel(target, target_lane, model.other_node(target, finish)):
        return None, "target_lane_cannot_reach_node"
    first = (source["id"], source_lane["index"], model.other_node(source, start), True)
    opening = model.chord(source)
    if opening > max_length:
        return None, "path_lower_bound_exceeds_max_length"
    goal = (target["id"], target_lane["index"], finish, True)
    best = {first: opening}
    previous = {first: None}
    queue = [(opening, first)]
    while queue:
        length, state = heapq.heappop(queue)
        if length > best.get(state, math.inf):
            continue
        if length > max_length:
            continue
        segment_id, lane_index, node, arrived = state
        segment = segments[segment_id]
        lane = model.lane_at(segment, lane_index)
        if arrived and state == goal:
            path = []
            while state is not None:
                path.append(state)
                state = previous[state]
            path.reverse()
            return {"length": length, "path": path}, None
        if arrived:
            degree = len(incident[node])
            for neighbour_id in incident[node]:
                if neighbour_id == segment_id and jm.UTURN == "forbidden":
                    continue
                if neighbour_id == segment_id and jm.UTURN == "deadend" and degree != 1:
                    continue
                if (segment_id, neighbour_id) not in partners[node]:
                    continue
                neighbour = segments[neighbour_id]
                for next_index in model.continues(
                    pairing, segment, neighbour, node, lane_index
                ):
                    if model.lane_at(neighbour, next_index) is None:
                        continue
                    next_state = (neighbour_id, next_index, node, False)
                    if length < best.get(next_state, math.inf):
                        best[next_state] = length
                        previous[next_state] = state
                        heapq.heappush(queue, (length, next_state))
        else:
            far = model.other_node(segment, node)
            if not model.can_travel(segment, lane, node):
                continue
            next_length = length + model.chord(segment)
            if next_length > max_length:
                continue
            next_state = (segment_id, lane_index, far, True)
            if next_length < best.get(next_state, math.inf):
                best[next_state] = next_length
                previous[next_state] = state
                heapq.heappush(queue, (next_length, next_state))
    return None, "no_directed_lane_path_within_max_length"


def witness(package, request, rule):
    """The model's own shortest witness path for one rule, or the reason it has none.

    `frozen:` rules use the accepted model's junction partner maps; this
    study's rules use `junction_model.node_alternatives`. The returned verdict
    is checked against `junction_model.Engine.predict` by the test suite.
    """
    segments, incident = model.train_index(package)
    if rule in jm.BASELINES or rule.split(":", 1)[-1] in model.BASELINES:
        return {"prediction": None, "reason": "baseline rule has no path"}
    if rule.startswith("frozen:"):
        inner = rule.split(":", 1)[1]
        kind, pairing, uturn, junction = model.parse_rule(inner)
        resolutions = model._node_alternatives(package, incident, junction, uturn)
    else:
        measure, kind, pairing, threshold = jm.parse_rule(rule)
        resolutions = jm.node_alternatives(package, incident, kind, measure, threshold)
    if resolutions is None:
        return {"prediction": jm.ABSTAIN, "reason": "ambiguous_junction_pairing"}
    best = None
    for partners in resolutions:
        try:
            found, reason = _search(
                segments, incident, partners, request, pairing, jm.MAX_LENGTH
            )
        except LookupError as error:
            return {"prediction": jm.ABSTAIN, "reason": str(error)}
        if found is None:
            continue
        if best is None or found["length"] < best["length"]:
            best = found
    if best is None:
        return {"prediction": jm.NO_PATH, "reason": reason}
    return {"prediction": jm.SUCCESS, **best}


def transitions(package, path):
    """Turn a state path into node crossings: (node, from, lane, to, lane)."""
    crossings = []
    for before, after in zip(path, path[1:]):
        if not before[3] or after[3]:
            continue
        segment_id, lane_index, node, _ = before
        neighbour_id, next_index, _, _ = after
        if segment_id == neighbour_id:
            continue
        crossings.append(
            {
                "node": node,
                "from_segment": segment_id,
                "from_lane": lane_index,
                "to_segment": neighbour_id,
                "to_lane": next_index,
                "chord_turn_degrees": jm.turn_degrees(
                    package, node, segment_id, neighbour_id, "chord"
                ),
                "tangent_turn_degrees": jm.turn_degrees(
                    package, node, segment_id, neighbour_id, "tangent"
                ),
            }
        )
    return crossings


def native_path(package, row):
    """The observed successful path as literal [segment, lane, offset] triples."""
    return [
        [int(v) for v in item]
        for item in (row.get("result", {}).get("positions") or [])
    ]


def native_transitions(package, row, reference_maps, tangent_maps):
    """Node crossings of a native successful path, with the lanes it used.

    In the harness's position list each traversed segment contributes its exit
    point (offset 0 = the segment's start node, 255 = its end node); the first
    entry is the path's initial point. Consecutive segments therefore share
    their one transition node, which is used directly, and the offsets only
    disambiguate a parallel pair of segments that share both ends.
    """
    positions = native_path(package, row)
    crossings = []
    for before, after in zip(positions, positions[1:]):
        a, lane_a, offset_a = before
        b, lane_b, offset_b = after
        if a == b:
            continue
        segment_a = package["segments"].get(a)
        segment_b = package["segments"].get(b)
        shared = (
            {segment_a["start"], segment_a["end"]}
            & {segment_b["start"], segment_b["end"]}
            if segment_a is not None and segment_b is not None
            else set()
        )
        leave = (
            (segment_a["start"] if offset_a == 0 else segment_a["end"])
            if segment_a is not None
            else None
        )
        node = (
            leave
            if leave in shared
            else (next(iter(shared)) if len(shared) == 1 else None)
        )
        crossing = {
            "node": node,
            "from_segment": a,
            "from_lane": lane_a,
            "to_segment": b,
            "to_lane": lane_b,
        }
        if node is not None and segment_a is not None and segment_b is not None:
            crossing["chord_turn_degrees"] = jm.turn_degrees(
                package, node, a, b, "chord"
            )
            crossing["tangent_turn_degrees"] = jm.turn_degrees(
                package, node, a, b, "tangent"
            )
        crossing["lanes_present"] = (
            model.lane_at(segment_a, lane_a) is not None
            and model.lane_at(segment_b, lane_b) is not None
            if segment_a is not None and segment_b is not None
            else False
        )
        crossing["reference_connects"] = (
            transition_verdict(reference_maps, node, a, b) if node is not None else None
        )
        crossing["correspondence_connects"] = (
            transition_verdict(tangent_maps, node, a, b) if node is not None else None
        )
        crossing["lane_continuation_reference"] = (
            bool(model.continues("any_lane", segment_a, segment_b, node, lane_a))
            if node is not None and segment_a is not None and segment_b is not None
            else None
        )
        crossings.append(crossing)
    return crossings


# ---------------------------------------------------------------- node frames


def node_frame(package, node, incident):
    """Every incident Train segment pair at one node, under both measures."""
    unique = sorted(dict.fromkeys(incident.get(node, [])))
    pairs = []
    for index, a in enumerate(unique):
        for b in unique[index + 1 :]:
            pairs.append(
                {
                    "a": a,
                    "b": b,
                    "chord_turn_degrees": jm.turn_degrees(package, node, a, b, "chord"),
                    "tangent_turn_degrees": jm.turn_degrees(
                        package, node, a, b, "tangent"
                    ),
                }
            )
    frame = {"node": node, "segments": unique, "pairs": pairs}
    for measure in ("chord", "tangent"):
        matchings = jm.node_alternatives(
            package, {node: unique}, "continuation", measure
        )
        # Lists, not tuples: this record is written to JSON and compared after
        # a round trip, so the in-memory shape has to match the file's.
        frame[f"{measure}_continuation"] = (
            None
            if matchings is None
            else sorted(
                sorted([list(sorted(pair)) for pair in partners[node]])
                for partners in matchings
            )
        )
    return frame


def pairing_difference(package):
    """Input-only: at how many nodes do the two continuation pairings differ?"""
    _, incident = model.train_index(package)
    compared = 0
    different = []
    for node, segment_ids in sorted(incident.items()):
        unique = sorted(dict.fromkeys(segment_ids))
        if len(unique) < 2:
            continue
        chord = jm.node_alternatives(package, {node: unique}, "continuation", "chord")
        tangent = jm.node_alternatives(
            package, {node: unique}, "continuation", "tangent"
        )
        if chord is None or tangent is None:
            continue
        compared += 1
        left = {frozenset(pair for pair in partners[node]) for partners in chord}
        right = {frozenset(pair for pair in partners[node]) for partners in tangent}
        if left != right:
            different.append(node)
    return {
        "nodes_compared": compared,
        "nodes_differing": len(different),
        "share_differing": (len(different) / compared) if compared else None,
        "differing_nodes": different,
    }


# ------------------------------------------------------------------ reporting


def verdict_for(rule, package, request):
    return jm.Engine(package).predict(request, rule)


def resolutions_for(package, rule):
    """The rule's per-node partner maps, computed once."""
    segments, incident = model.train_index(package)
    if rule.startswith("frozen:"):
        inner = rule.split(":", 1)[1]
        _, _, uturn, junction = model.parse_rule(inner)
        return model._node_alternatives(package, incident, junction, uturn)
    measure, kind, _, threshold = jm.parse_rule(rule)
    return jm.node_alternatives(package, incident, kind, measure, threshold)


def transition_verdict(resolutions, node, a, b):
    """Is (a -> b) a connection this rule allows at `node`?"""
    if resolutions is None:
        return None
    return all((a, b) in partners.get(node, set()) for partners in resolutions)


def observed_transitions(bundle, opening):
    """Every (node, from, to) the native successful paths of one opening used."""
    seen = set()
    for row in bundle["rows"]:
        if not isinstance(row.get("result"), dict) or not row["result"].get("success"):
            continue
        positions = [
            [int(v) for v in item] for item in row["result"].get("positions") or []
        ]
        for before, after in zip(positions, positions[1:]):
            if before[0] == after[0]:
                continue
            seen.add((opening, before[0], after[0]))
    return seen


def describe(package, request, rule):
    result = verdict_for(rule, package, request)
    found = witness(package, request, rule)
    if found["prediction"] != result["prediction"]:
        raise AssertionError("witness disagrees with the frozen prediction")
    return {
        "rule": rule,
        "verdict": result,
        "witness": found,
        "transitions": transitions(package, found["path"]) if "path" in found else [],
    }


def _first_difference(left, right, path=""):
    """The first leaf that differs, for a reproducible failure message."""
    if type(left) is not type(right):
        return f"{path} (type {type(left).__name__} vs {type(right).__name__})"
    if isinstance(left, dict):
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                return f"{path}/{key} (missing)"
            found = _first_difference(left[key], right[key], f"{path}/{key}")
            if found:
                return found
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return f"{path} (length {len(left)} vs {len(right)})"
        for index, (a, b) in enumerate(zip(left, right)):
            found = _first_difference(a, b, f"{path}[{index}]")
            if found:
                return found
        return None
    if left != right:
        return f"{path} ({left!r} vs {right!r})"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = binding.load_manifest()
    accepted = binding.accepted_openings(manifest, verify_observations=True)
    expected_queries, per_opening = binding.expected_query_set(
        accepted["openings"], accepted["integrity"]
    )
    protocol = json.loads(PROTOCOL.read_text())
    features = json.loads(FEATURES.read_text())
    predictions = json.loads(PREDICTIONS.read_text())
    evaluation = json.loads(EVALUATION.read_text())
    bundles = binding.bind_observations(
        predictions, protocol, features, accepted["openings"], accepted["packages"]
    )

    entries = {entry["opening"]: entry for entry in accepted["openings"]["openings"]}
    packages = {}
    for name, entry in entries.items():
        container = exports.cached_net(
            accepted["packages"][entry["package"]]["locator"]
        )
        native = topology.from_native(
            binding.load_json(binding.raw_dir(entry) / "networks.json.gz"), name
        )
        packages[name] = exports.attach(native, exports.tangents(container["net"]))

    geometry = {name: pairing_difference(package) for name, package in packages.items()}
    observed = {name: observed_transitions(bundles[name], name) for name in entries}

    focus = [REFERENCE, CORRESPONDENCE]
    selected = evaluation["selections"]["cohort_descriptive"]["rule"]
    if selected and selected not in focus:
        focus.append(selected)

    reference_maps = {}
    tangent_maps = {}
    mechanics = {}
    for rule in focus:
        errors = evaluation["counterexamples"].get(rule, [])
        rows = []
        as_reference = rule == REFERENCE
        for error in errors:
            name = error["opening"]
            package = packages[name]
            request = error["request"]
            incident = model.train_index(package)[1]
            if name not in reference_maps:
                reference_maps[name] = resolutions_for(package, REFERENCE)
                tangent_maps[name] = resolutions_for(package, CORRESPONDENCE)
            described = describe(package, request, rule)
            detail = {
                "query": error,
                "verdict": described["verdict"],
                "witness": {
                    "prediction": described["witness"]["prediction"],
                    "length": described["witness"].get("length"),
                    "crossings": len(described["transitions"]),
                    "max_chord_turn_degrees": max(
                        (t["chord_turn_degrees"] for t in described["transitions"]),
                        default=None,
                    ),
                    "max_tangent_turn_degrees": max(
                        (t["tangent_turn_degrees"] for t in described["transitions"]),
                        default=None,
                    ),
                },
            }
            crossings = described["transitions"]
            for crossing in crossings:
                crossing["reference_connects"] = transition_verdict(
                    reference_maps[name],
                    crossing["node"],
                    crossing["from_segment"],
                    crossing["to_segment"],
                )
                crossing["correspondence_connects"] = transition_verdict(
                    tangent_maps[name],
                    crossing["node"],
                    crossing["from_segment"],
                    crossing["to_segment"],
                )
                crossing["observed_natively"] = (
                    name,
                    crossing["from_segment"],
                    crossing["to_segment"],
                ) in observed[name]
            # The model's witness, shown by the transitions that carry the
            # decision: where the two measures disagree, or where the geometry
            # is least straight.
            differential = [
                crossing
                for crossing in crossings
                if crossing["reference_connects"] != crossing["correspondence_connects"]
            ]
            notable = sorted(
                crossings,
                key=lambda crossing: -(
                    abs(
                        crossing["chord_turn_degrees"]
                        - crossing["tangent_turn_degrees"]
                    )
                    + crossing["tangent_turn_degrees"] / 100.0
                ),
            )[:8]
            detail["witness_transitions_differing_by_measure"] = differential[:8]
            detail["witness_transitions_least_straight"] = notable
            detail["witness_crossings_observed_natively"] = sum(
                1 for crossing in crossings if crossing["observed_natively"]
            )
            decisive_nodes = sorted({crossing["node"] for crossing in differential})[:5]

            if error["kind"] == "false_negative":
                other_rule = CORRESPONDENCE if as_reference else REFERENCE
                other = witness(package, request, other_rule)
                other_crossings = (
                    transitions(package, other["path"]) if "path" in other else []
                )
                for crossing in other_crossings:
                    crossing["reference_connects"] = transition_verdict(
                        reference_maps[name],
                        crossing["node"],
                        crossing["from_segment"],
                        crossing["to_segment"],
                    )
                    crossing["correspondence_connects"] = transition_verdict(
                        tangent_maps[name],
                        crossing["node"],
                        crossing["from_segment"],
                        crossing["to_segment"],
                    )
                detail["other_measure"] = {
                    "rule": other_rule,
                    "prediction": other["prediction"],
                    "reason": other.get("reason"),
                    "length": other.get("length"),
                    "crossings": len(other_crossings),
                    "transitions_differing_by_measure": [
                        crossing
                        for crossing in other_crossings
                        if crossing["reference_connects"]
                        != crossing["correspondence_connects"]
                    ][:8],
                }
                row = bundles[name]["rows"][error["plan_index"]]
                native = native_transitions(
                    package, row, reference_maps[name], tangent_maps[name]
                )
                detail["native_path_segments"] = [
                    [before[0], before[1], before[2]]
                    for before, after in zip(
                        native_path(package, row), native_path(package, row)[1:]
                    )
                    if before[0] != after[0]
                ]
                rejected = [
                    (index, crossing)
                    for index, crossing in enumerate(native)
                    if crossing["reference_connects"] is False
                ]
                detail["native_transitions"] = len(native)
                detail["native_transitions_rejected_by_reference"] = len(rejected)
                detail["native_transitions_rejected_by_correspondence"] = sum(
                    1
                    for crossing in native
                    if crossing["correspondence_connects"] is False
                )
                if rejected:
                    index, crossing = rejected[0]
                    detail["first_rejected_native_transition"] = {
                        "index": index,
                        "node": crossing["node"],
                        "from_segment": crossing["from_segment"],
                        "from_lane": crossing["from_lane"],
                        "to_segment": crossing["to_segment"],
                        "to_lane": crossing["to_lane"],
                        "chord_turn_degrees": crossing.get("chord_turn_degrees"),
                        "tangent_turn_degrees": crossing.get("tangent_turn_degrees"),
                        "lanes_present": crossing["lanes_present"],
                        "lane_continuation_any_lane": crossing[
                            "lane_continuation_reference"
                        ],
                    }
                    if crossing["node"] is not None:
                        decisive_nodes = [crossing["node"]]
                detail["native_transitions_notable"] = sorted(
                    native,
                    key=lambda crossing: -(
                        abs(
                            (crossing.get("chord_turn_degrees") or 0)
                            - (crossing.get("tangent_turn_degrees") or 0)
                        )
                    ),
                )[:6]
            detail["node_frames"] = [
                node_frame(package, node, incident)
                for node in decisive_nodes
                if node is not None and node in incident
            ]
            rows.append(detail)
        mechanics[rule] = rows

    document = {
        "schema": 1,
        "study": FREEZE,
        "computed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "protocol_sha256": binding.file_digest(PROTOCOL),
        "features_sha256": binding.file_digest(FEATURES),
        "predictions_sha256": binding.file_digest(PREDICTIONS),
        "evaluation_sha256": binding.file_digest(EVALUATION),
        "note": (
            "This file is outcome-conditioned. Successful segment ids and native "
            "path transitions appear as diagnostics only; no rule reads them."
        ),
        "input_only_geometry": {
            "definition": (
                "how often the chord and tangent continuation pairings differ, "
                "computed from frozen topology alone"
            ),
            "packages": geometry,
        },
        "error_mechanics": mechanics,
    }
    if args.check:
        frozen = json.loads(DIAGNOSTICS.read_text())
        for key in ("input_only_geometry", "error_mechanics"):
            if frozen[key] != document[key]:
                path = _first_difference(frozen[key], document[key])
                raise SystemExit(f"diagnostics are not reproducible: {key} at {path}")
        print(
            json.dumps(
                {
                    "checked": True,
                    "diagnostics_sha256": binding.file_digest(DIAGNOSTICS),
                }
            )
        )
        return
    DIAGNOSTICS.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "focus": focus,
                "errors": {rule: len(rows) for rule, rows in mechanics.items()},
                "pairing_differences": {
                    name: {
                        "compared": value["nodes_compared"],
                        "differing": value["nodes_differing"],
                    }
                    for name, value in geometry.items()
                },
                "diagnostics_sha256": binding.file_digest(DIAGNOSTICS),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
