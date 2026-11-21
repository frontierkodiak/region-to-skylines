"""Query-scoped rail reachability: predictions from pre-query package topology.

Everything here is a pure function of (package topology, frozen request). No
function in this module opens an observation, an outcome table or a path list,
so a prediction produced through this module cannot have seen the label it is
scored against.

The question is deliberately narrow: given one literal-boundary request
`from=[segment,lane,offset]`, `to=[segment,lane,offset]` submitted to
`PathManager.CreatePath` with Train/All/laneTypes(Vehicle, TransportVehicle,
CargoVehicle)/seed 857/maxLength 100000, was a complete path returned?

The model is a directed reachability rule over `(segment, lane, node)` states.
It differs between rules in three named choices, each an unobservable native
junction fact rather than something assumed:

* `PAIRINGS` - which lane of one segment continues onto which lane of another
  segment at a shared node.
* `UTURNS` - whether a train may reverse inside one node.
* `JUNCTIONS` - which incident segment pairs a node connects at all. `all`
  connects every pair (the upper bound). `continuation` connects only a
  disjoint best-aligned pairing, as if the track can only pass straight through
  a branching node. `single` connects only the single straightest pair.
"""

from __future__ import annotations

import math
from collections import deque

SUCCESS = "success"
NO_PATH = "no_path"
ABSTAIN = "abstain"

# A lane-continuation hypothesis. `orientation_*` uses the node role of the two
# segments: at a shared node a segment can arrive at its start, its end, both or
# neither. Two segments meet "mixed" when one starts there and the other ends
# there, and "same sided" when both start or both end there.
PAIRINGS = {
    # Every Train lane continues onto every Train lane at a node. This is the
    # upper bound: it makes reachability equal to weak component membership.
    "any_lane": "all lane pairs continue",
    # The same lane index continues (lane 0 -> lane 0, lane 1 -> lane 1).
    "index_same": "lane i continues onto lane i",
    # The mirrored index continues (lane 0 -> 1, 1 -> 0).
    "index_mirror": "lane i continues onto lane n-1-i",
    # Primary: lane index tracks the physical lateral side. Segments whose
    # travel headings agree at the node (one starts, one ends) keep the index;
    # segments whose headings oppose (both start, or both end) mirror it.
    "orientation_index": "i at a mixed node, n-1-i at a same-sided node",
    # Complement of the primary, for the opposite lateral-order convention.
    "orientation_mirror": "n-1-i at a mixed node, i at a same-sided node",
}

# Whether a train may reverse inside one node.
UTURNS = {
    "forbidden": "a train never reverses at a node",
    "deadend": "a train reverses only at a node with one incident Train segment",
    "allowed": "a train may reverse at any node",
}

# Which incident segment pairs a node connects at all.
JUNCTIONS = {
    "all": "every incident Train segment pair continues",
    "continuation": "a disjoint pairing, straightest first: a node passes one continuation per segment",
    "single": "only the single straightest incident pair continues",
}

BASELINES = ["always_fail", "always_candidate", "weak_component"]
# The pre-registered topology-only family. Rule names are frozen: they were
# scored before any junction rule existed.
LANE_RULES = [f"lane:{pairing}:{uturn}" for pairing in PAIRINGS for uturn in UTURNS]
# The junction family. Added after the first family failed to separate observed
# successes from observed failures; every member is reported, none is promoted.
JUNCTION_RULES = [
    f"junction:{junction}:{pairing}"
    for junction in ("continuation", "single")
    for pairing in PAIRINGS
]
RULES = BASELINES + LANE_RULES + JUNCTION_RULES
# Chosen before any prediction was scored, from the physical argument in the
# module docstring and README: lateral side is preserved across a node, which is
# `orientation_index`, and the frozen protocol never relies on a reversal.
PRIMARY_RULE = "lane:orientation_index:forbidden"
# The straightest-continuation junction rule with the any-lane continuation is
# the best fitting export-only member. It is a hypothesis: it was selected after
# the first family was scored, and the study makes no adoption claim. For a
# single-track two-lane railway the lane index is a direction record on one
# physical track, so "any lane continues" is also the physically motivated
# reading; the junction pairing is what does the discriminating.
FITTED_RULE = "junction:continuation:any_lane"

# The frozen protocol's own maximum path length. Chord sums are a lower bound on
# the native curve length, so the bound can only abstain on a lower bound.
MAX_LENGTH = 100000.0


def parse_rule(rule):
    """Return (kind, pairing, uturn, junction) for a rule name."""
    if rule in BASELINES:
        return rule, None, None, None
    parts = rule.split(":")
    if parts[0] == "lane" and len(parts) == 3:
        _, pairing, uturn = parts
        if pairing not in PAIRINGS or uturn not in UTURNS:
            raise ValueError(f"unknown rule {rule}")
        return "lane", pairing, uturn, "all"
    if parts[0] == "junction" and len(parts) == 3:
        _, junction, pairing = parts
        if junction not in JUNCTIONS or pairing not in PAIRINGS:
            raise ValueError(f"unknown rule {rule}")
        return "junction", pairing, "forbidden", junction
    raise ValueError(f"unknown rule {rule}")


def train_index(package):
    """Train-capable segments and the incident Train segments of each node."""
    segments = {
        segment_id: segment
        for segment_id, segment in package["segments"].items()
        if any(lane for lane in segment["lanes"])
    }
    incident = {}
    for segment_id, segment in segments.items():
        for node in (segment["start"], segment["end"]):
            incident.setdefault(node, []).append(segment_id)
    return segments, incident


def weak_components(package):
    """Undirected Train-segment components, returned as a node -> label map."""
    _, incident = train_index(package)
    segments = package["segments"]
    labels = {}
    for start in incident:
        if start in labels:
            continue
        label = start
        pending = [start]
        while pending:
            node = pending.pop()
            if node in labels:
                continue
            labels[node] = label
            for segment_id in incident[node]:
                segment = segments[segment_id]
                other = segment["end"] if segment["start"] == node else segment["start"]
                pending.append(other)
    return labels


def endpoint_node(segment, offset):
    return segment["start"] if int(offset) == 0 else segment["end"]


def other_node(segment, node):
    return segment["end"] if segment["start"] == node else segment["start"]


def can_travel(segment, lane, node):
    """Can this lane be used to move away from `node` to the segment's far end?"""
    if node == segment["start"]:
        return lane["forward"]
    if node == segment["end"]:
        return lane["backward"]
    raise ValueError("node is not an end of the segment")


def lane_at(segment, index):
    for lane in segment["lanes"]:
        if lane["index"] == int(index):
            return lane
    return None


def continues(pairing, source, target, node, lane_index):
    """Whether lane `lane_index` of `source` continues onto a lane of `target`."""
    target_lanes = len(target["lanes"])
    if lane_index >= target_lanes:
        return ()
    if pairing == "any_lane":
        return tuple(lane["index"] for lane in target["lanes"])
    if pairing == "index_same":
        return (lane_index,)
    if pairing == "index_mirror":
        return (target_lanes - 1 - lane_index,)
    same_side = (source["start"] == node and target["start"] == node) or (
        source["end"] == node and target["end"] == node
    )
    if pairing == "orientation_index":
        mirrored = same_side
    elif pairing == "orientation_mirror":
        mirrored = not same_side
    else:  # pragma: no cover - parse_rule guards this
        raise ValueError(f"unknown pairing {pairing}")
    return (target_lanes - 1 - lane_index if mirrored else lane_index,)


def chord(segment):
    a, b = segment["a"], segment["b"]
    return math.dist(a, b)


def _unit(a, b):
    vx, vz = b[0] - a[0], b[2] - a[2]
    length = math.hypot(vx, vz)
    return (vx / length, vz / length) if length else (0.0, 0.0)


def turn_degrees(package, node, source_id, target_id):
    """Heading change from arriving along `source` to leaving along `target`."""
    nodes = package["nodes"]
    source = package["segments"][source_id]
    target = package["segments"][target_id]
    into = _unit(nodes[other_node(source, node)]["position"], nodes[node]["position"])
    out = _unit(nodes[node]["position"], nodes[other_node(target, node)]["position"])
    cosine = max(-1.0, min(1.0, into[0] * out[0] + into[1] * out[1]))
    return math.degrees(math.acos(cosine))


def node_partners(package, incident, junction):
    """Directed (source, target) segment pairs this junction rule connects."""
    partners = {}
    for node, segment_ids in incident.items():
        unique = sorted(set(segment_ids))
        pairs = []
        if junction == "all":
            pairs = [(a, b) for a in unique for b in unique if a != b]
        elif len(unique) >= 2:
            candidates = sorted(
                (turn_degrees(package, node, a, b), a, b)
                for index, a in enumerate(unique)
                for b in unique[index + 1 :]
            )
            if junction == "single":
                pairs = [(candidates[0][1], candidates[0][2])]
            elif junction == "continuation":
                used = set()
                for _, a, b in candidates:
                    if a in used or b in used:
                        continue
                    used.update((a, b))
                    pairs.append((a, b))
            else:  # pragma: no cover - JUNCTIONS guards this
                raise ValueError(f"unknown junction {junction}")
        partners[node] = set(pairs) | {(b, a) for a, b in pairs}
    return partners


def reachable(package, request, pairing, uturn, junction="all", max_length=MAX_LENGTH):
    """Directed reachability from the request's from-position to its to-position.

    Returns (SUCCESS or NO_PATH, detail dict). Raises LookupError when the
    request names a node, segment or lane the package does not have, which the
    caller reports as ABSTAIN rather than as a failure.

    States are (segment, lane, node, arrived): `arrived` is True when the state
    was reached by travelling along that segment's lane to `node`, and False
    when it was reached by continuing from another lane at `node`. A lane is
    only entered by a traversal, so the path alternates continue/travel and no
    chain of continues can cross a node without using its pairing rule.
    """
    segments, incident = train_index(package)
    partners = node_partners(package, incident, junction)
    source_id, source_lane_index, source_offset = (int(v) for v in request["from"])
    target_id, target_lane_index, target_offset = (int(v) for v in request["to"])

    def lookup(segment_id, lane_index):
        segment = segments.get(segment_id)
        if segment is None:
            raise LookupError(f"segment {segment_id} is not Train-capable here")
        lane = lane_at(segment, lane_index)
        if lane is None:
            raise LookupError(f"segment {segment_id} has no lane {lane_index}")
        return segment, lane

    source, source_lane = lookup(source_id, source_lane_index)
    target, target_lane = lookup(target_id, target_lane_index)
    start = endpoint_node(source, source_offset)
    finish = endpoint_node(target, target_offset)
    if start not in package["nodes"] or finish not in package["nodes"]:
        raise LookupError("request endpoint node is absent from the package")
    if not can_travel(source, source_lane, start):
        return NO_PATH, {"reason": "source_lane_cannot_leave_node"}
    # Arriving at the target node means travelling along the target lane from
    # the segment's other end toward it.
    if not can_travel(target, target_lane, other_node(target, finish)):
        return NO_PATH, {"reason": "target_lane_cannot_reach_node"}

    first = (source_id, source_lane_index, other_node(source, start), True)
    distance = {first: chord(source)}
    seen = {first}
    queue = deque([first])
    goal = (target_id, target_lane_index, finish, True)
    while queue:
        segment_id, lane_index, node, arrived = queue.popleft()
        length = distance[(segment_id, lane_index, node, arrived)]
        segment = segments[segment_id]
        lane = lane_at(segment, lane_index)
        if arrived:
            # Continue at this node; `uturn` may allow the same segment.
            degree = len(incident[node])
            for neighbour_id in incident[node]:
                if neighbour_id == segment_id and uturn == "forbidden":
                    continue
                if neighbour_id == segment_id and uturn == "deadend" and degree != 1:
                    continue
                if (segment_id, neighbour_id) not in partners[node]:
                    continue
                neighbour = segments[neighbour_id]
                for next_index in continues(
                    pairing, segment, neighbour, node, lane_index
                ):
                    next_lane = lane_at(neighbour, next_index)
                    if next_lane is None:
                        continue
                    state = (neighbour_id, next_index, node, False)
                    if state in seen:
                        continue
                    seen.add(state)
                    distance[state] = length
                    queue.append(state)
        else:
            # Travel this lane away from the node.
            far = other_node(segment, node)
            if can_travel(segment, lane, node) and length <= max_length:
                state = (segment_id, lane_index, far, True)
                if state not in seen:
                    seen.add(state)
                    distance[state] = length + chord(segment)
                    queue.append(state)
    if goal in seen:
        return SUCCESS, {"path_lower_bound_length": distance[goal]}
    return NO_PATH, {"reason": "no_directed_lane_path"}


def predict(package, request, rule):
    """One prediction. Returns {prediction, detail}."""
    if rule == "always_fail":
        return {"prediction": NO_PATH, "detail": {"reason": "baseline"}}
    if rule == "always_candidate":
        return {"prediction": SUCCESS, "detail": {"reason": "baseline"}}
    if rule == "weak_component":
        segments, _ = train_index(package)
        source = segments.get(int(request["from"][0]))
        target = segments.get(int(request["to"][0]))
        if source is None or target is None:
            return {"prediction": ABSTAIN, "detail": {"reason": "segment_absent"}}
        labels = weak_components(package)
        source_node = endpoint_node(source, request["from"][2])
        target_node = endpoint_node(target, request["to"][2])
        same = labels.get(source_node) == labels.get(target_node)
        return {
            "prediction": SUCCESS if same else NO_PATH,
            "detail": {
                "reason": "same_weak_component" if same else "different_weak_component"
            },
        }
    _, pairing, uturn, junction = parse_rule(rule)
    try:
        prediction, detail = reachable(package, request, pairing, uturn, junction)
    except LookupError as error:
        return {"prediction": ABSTAIN, "detail": {"reason": str(error)}}
    return {"prediction": prediction, "detail": detail}
