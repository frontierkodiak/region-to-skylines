"""Query-scoped rail reachability: predictions from pre-query package topology.

Everything here is a pure function of (package topology, frozen request). No
function in this module opens an observation, an outcome table or a path list,
so a prediction produced through this module cannot have seen the label it is
scored against.

The question is deliberately narrow: given one literal-boundary request
`from=[segment,lane,offset]`, `to=[segment,lane,offset]` submitted to
`PathManager.CreatePath` with Train/All/laneTypes(Vehicle, TransportVehicle,
CargoVehicle)/seed 857/maxLength 100000, was a complete path returned?

Corrected domain (v2). The model consumes only Train-capable records:

* a segment is in the graph only when it has at least one Train lane of an
  accepted lane type, and only those lanes are traversable or continuable;
* a requested lane must be one of them;
* segment `Invert` swaps the required travel bit, following the accepted
  native planner (`cs1_harness/rail_study.py`: `forward = (offset == 0) ==
  source; if Invert: forward = not forward`). Lane indexes are never renumbered.

The model is a directed reachability rule over `(segment, lane, node)` states.
Three unobservable native choices stay named hypotheses:

* `PAIRINGS` - which lane of one segment continues onto which lane of another
  segment at a shared node, counted by ordinal among the segment's Train lanes.
* `UTURNS` - whether a train may reverse inside one node. A reversal is a
  self-pair `(segment, segment)` at the node, so it must exist in the partner
  map before the reversal branches can mean anything.
* `JUNCTIONS` - which incident segment pairs a node connects at all. When a
  junction's straightest candidates tie to within `TIE_TOLERANCE_DEGREES`, every
  resolution is represented, so segment allocation ids never break a tie. A
  query is `success` or `no_path` only when every resolution agrees, and
  `abstain` when they disagree or the enumeration bound is exceeded.

Length is the sum of segment chords, a lower bound on the native curve length.
It is relaxed shortest-first, never checked only at the goal, and a path whose
lower bound exceeds the protocol maximum is never a success.
"""

from __future__ import annotations

import heapq
import itertools
import math

import topology

SUCCESS = "success"
NO_PATH = "no_path"
ABSTAIN = "abstain"

MODEL_VERSION = "rail-query-model-v2-corrected"

# Two junction candidates closer than this (degrees) are a tie, and the tie is
# resolved by representing every resolution rather than by comparing ids.
TIE_TOLERANCE_DEGREES = 1e-6
# Bound on the number of junction resolutions carried through one query.
MAX_ALTERNATIVES = 32

# A lane-continuation hypothesis. `orientation_*` uses the node role of the two
# segments: at a shared node a segment can arrive at its start, its end, both or
# neither. Two segments meet "mixed" when one starts there and the other ends
# there, and "same sided" when both start or both end there.
PAIRINGS = {
    # Every Train lane continues onto every Train lane at a node. This is the
    # upper bound: it makes reachability equal to weak component membership.
    "any_lane": "all Train lane pairs continue",
    # The same lane ordinal continues (first Train lane -> first Train lane).
    "index_same": "Train lane ordinal i continues onto ordinal i",
    # The mirrored ordinal continues (first -> last).
    "index_mirror": "Train lane ordinal i continues onto ordinal n-1-i",
    # Primary: lane ordinal tracks the physical lateral side. Segments whose
    # travel headings agree at the node (one starts, one ends) keep the ordinal;
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
# The topology-only family. Rule names are frozen from the first freeze.
LANE_RULES = [f"lane:{pairing}:{uturn}" for pairing in PAIRINGS for uturn in UTURNS]
# The junction family, also frozen from the first freeze.
JUNCTION_RULES = [
    f"junction:{junction}:{pairing}"
    for junction in ("continuation", "single")
    for pairing in PAIRINGS
]
RULES = BASELINES + LANE_RULES + JUNCTION_RULES
# Chosen before any prediction was scored in the first freeze.
PRIMARY_RULE = "lane:orientation_index:forbidden"
# Best fitting member of the junction family; a hypothesis, not an adopted rule.
FITTED_RULE = "junction:continuation:any_lane"

# The frozen protocol's own maximum path length.
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


def train_lanes(segment):
    """The segment's Train-capable lanes, in prefab order."""
    return topology.train_lanes(segment)


def train_index(package):
    """Train-capable segments and the incident Train segments of each node."""
    segments = {
        segment_id: segment
        for segment_id, segment in package["segments"].items()
        if train_lanes(segment)
    }
    incident = {}
    for segment_id, segment in segments.items():
        for node in dict.fromkeys((segment["start"], segment["end"])):
            incident.setdefault(node, []).append(segment_id)
    return segments, incident


def weak_components(package):
    """Undirected Train-segment components, returned as a node -> label map."""
    segments, incident = train_index(package)
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


def effective_forward(segment, node):
    """Is travel away from `node` forward once segment Invert is applied?"""
    forward = node == segment["start"]
    if "Invert" in segment["flags"]:
        forward = not forward
    return forward


def can_travel(segment, lane, node):
    """Can this lane be used to move away from `node` to the segment's far end?"""
    if node not in (segment["start"], segment["end"]):
        raise ValueError("node is not an end of the segment")
    return lane["forward"] if effective_forward(segment, node) else lane["backward"]


def lane_at(segment, index):
    for lane in train_lanes(segment):
        if lane["index"] == int(index):
            return lane
    return None


def lane_ordinal(segment, index):
    for ordinal, lane in enumerate(train_lanes(segment)):
        if lane["index"] == int(index):
            return ordinal
    return None


def continues(pairing, source, target, node, lane_index):
    """Raw indexes of `target`'s Train lanes that `lane_index` continues onto."""
    source_ordinal = lane_ordinal(source, lane_index)
    if source_ordinal is None:
        return ()
    target_lanes = train_lanes(target)
    if not target_lanes:
        return ()
    if pairing == "any_lane":
        return tuple(lane["index"] for lane in target_lanes)
    if pairing == "index_same":
        return (
            (target_lanes[source_ordinal]["index"],)
            if source_ordinal < len(target_lanes)
            else ()
        )
    if pairing == "index_mirror":
        ordinal = len(target_lanes) - 1 - source_ordinal
        return (
            (target_lanes[ordinal]["index"],)
            if 0 <= ordinal < len(target_lanes)
            else ()
        )
    same_side = (source["start"] == node and target["start"] == node) or (
        source["end"] == node and target["end"] == node
    )
    if pairing == "orientation_index":
        mirrored = same_side
    elif pairing == "orientation_mirror":
        mirrored = not same_side
    else:  # pragma: no cover - parse_rule guards this
        raise ValueError(f"unknown pairing {pairing}")
    ordinal = len(target_lanes) - 1 - source_ordinal if mirrored else source_ordinal
    return (target_lanes[ordinal]["index"],) if 0 <= ordinal < len(target_lanes) else ()


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


def _continuation_matchings(package, node, segment_ids):
    """Every greedy straightest-first matching, all tie resolutions included.

    Returns None when the number of resolutions exceeds `MAX_ALTERNATIVES`,
    which the caller reports as an unresolved junction rather than guessing.
    """
    results = []
    seen = set()
    truncated = False

    def record(chosen):
        signature = frozenset(chosen)
        if signature not in seen:
            seen.add(signature)
            results.append(signature)

    def step(remaining, chosen):
        nonlocal truncated
        if truncated:
            return
        if len(remaining) < 2:
            record(chosen)
            if len(results) > MAX_ALTERNATIVES:
                truncated = True
            return
        turns = []
        for index, a in enumerate(remaining):
            for b in remaining[index + 1 :]:
                turns.append((turn_degrees(package, node, a, b), a, b))
        best = min(turn for turn, _, _ in turns)
        group = [(a, b) for turn, a, b in turns if turn - best <= TIE_TOLERANCE_DEGREES]
        for a, b in group:
            step([item for item in remaining if item not in (a, b)], chosen + [(a, b)])
            if truncated:
                return

    step(list(segment_ids), [])
    if truncated:
        return None
    return results


def _node_alternatives(package, incident, junction, uturn):
    """One or more partner maps, or None when a junction has no unique reading."""

    def reversals_for(unique):
        return {(a, a) for a in unique} if uturn != "forbidden" else set()

    alternatives_per_node = {}
    for node, segment_ids in incident.items():
        unique = list(dict.fromkeys(segment_ids))
        reversals = reversals_for(unique)
        if junction == "all":
            pairs = {(a, b) for a in unique for b in unique if a != b}
            alternatives_per_node[node] = [pairs | reversals]
            continue
        if len(unique) < 2:
            alternatives_per_node[node] = [reversals]
            continue
        if junction == "single":
            turns = sorted(
                (turn_degrees(package, node, a, b), a, b)
                for index, a in enumerate(unique)
                for b in unique[index + 1 :]
            )
            best = turns[0][0]
            alternatives_per_node[node] = [
                {(a, b), (b, a)} | reversals
                for turn, a, b in turns
                if turn - best <= TIE_TOLERANCE_DEGREES
            ]
            continue
        matchings = _continuation_matchings(package, node, unique)
        if matchings is None:
            return None
        alternatives_per_node[node] = [
            {(a, b) for a, b in matching} | {(b, a) for a, b in matching} | reversals
            for matching in matchings
        ]
    nodes = sorted(alternatives_per_node)
    total = 1
    for node in nodes:
        total *= max(1, len(alternatives_per_node[node]))
        if total > MAX_ALTERNATIVES:
            return None
    partners = []
    for combination in itertools.product(
        *(alternatives_per_node[node] for node in nodes)
    ):
        partners.append(dict(zip(nodes, combination)))
    return partners


def _lookup(segments, request, side):
    segment_id, lane_index = int(request[side][0]), int(request[side][1])
    segment = segments.get(segment_id)
    if segment is None:
        raise LookupError(f"segment {segment_id} is not Train-capable here")
    lane = lane_at(segment, lane_index)
    if lane is None:
        raise LookupError(f"segment {segment_id} has no Train lane {lane_index}")
    return segment, lane


def _reach(segments, incident, partners, request, pairing, uturn, max_length):
    """Directed reachability under one junction resolution, shortest lower bound."""
    source, source_lane = _lookup(segments, request, "from")
    target, target_lane = _lookup(segments, request, "to")
    start = endpoint_node(source, request["from"][2])
    finish = endpoint_node(target, request["to"][2])
    if start not in partners or finish not in partners:
        raise LookupError("request endpoint node is absent from the Train graph")
    if not can_travel(source, source_lane, start):
        return NO_PATH, {"reason": "source_lane_cannot_leave_node"}
    # Arriving at the target node means travelling along the target lane from
    # the segment's other end toward it.
    if not can_travel(target, target_lane, other_node(target, finish)):
        return NO_PATH, {"reason": "target_lane_cannot_reach_node"}

    first = (source["id"], source_lane["index"], other_node(source, start), True)
    opening = chord(source)
    if opening > max_length:
        return NO_PATH, {"reason": "path_lower_bound_exceeds_max_length"}
    goal = (target["id"], target_lane["index"], finish, True)
    best = {first: opening}
    queue = [(opening, first)]
    while queue:
        length, state = heapq.heappop(queue)
        if length > best.get(state, math.inf):
            continue
        if length > max_length:
            continue
        segment_id, lane_index, node, arrived = state
        segment = segments[segment_id]
        lane = lane_at(segment, lane_index)
        if arrived and state == goal:
            return SUCCESS, {"path_lower_bound_length": length}
        if arrived:
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
                    if lane_at(neighbour, next_index) is None:
                        continue
                    next_state = (neighbour_id, next_index, node, False)
                    if length < best.get(next_state, math.inf):
                        best[next_state] = length
                        heapq.heappush(queue, (length, next_state))
        else:
            far = other_node(segment, node)
            if not can_travel(segment, lane, node):
                continue
            next_length = length + chord(segment)
            if next_length > max_length:
                continue
            next_state = (segment_id, lane_index, far, True)
            if next_length < best.get(next_state, math.inf):
                best[next_state] = next_length
                heapq.heappush(queue, (next_length, next_state))
    return NO_PATH, {"reason": "no_directed_lane_path_within_max_length"}


def reachable(package, request, pairing, uturn, junction="all", max_length=MAX_LENGTH):
    """Directed reachability, combining every unresolved junction resolution."""
    segments, incident = train_index(package)
    resolutions = _node_alternatives(package, incident, junction, uturn)
    if resolutions is None:
        return ABSTAIN, {"reason": "ambiguous_junction_pairing"}
    outcomes = [
        _reach(segments, incident, partners, request, pairing, uturn, max_length)
        for partners in resolutions
    ]
    predictions = {prediction for prediction, _ in outcomes}
    if len(predictions) == 1:
        prediction = predictions.pop()
        if prediction == SUCCESS:
            detail = min(
                (detail for result, detail in outcomes if result == SUCCESS),
                key=lambda detail: detail["path_lower_bound_length"],
            )
            return SUCCESS, detail
        return NO_PATH, outcomes[0][1]
    return ABSTAIN, {
        "reason": "ambiguous_junction_pairing",
        "resolutions": len(resolutions),
        "outcomes": sorted(predictions),
    }


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
