"""Query-scoped outside-connection reachability: predictions from pre-query topology.

Everything here is a pure function of (opening topology, frozen request). No
function in this module opens an observation, an outcome table, a path list or a
panel readback, so a prediction produced through this module cannot have seen
the label it is scored against.

The question is deliberately narrow. Given one literal-boundary request
`from=[segment,lane,offset]`, `to=[segment,lane,offset]` submitted to
`PathManager.CreatePath` with the accepted study's vehicle, category `All`,
laneTypes `Vehicle|TransportVehicle|CargoVehicle`, seed 857, maxLength 100000
and literal endpoints, did the game return a complete, released path whose
first and last positions equal the requested offsets?

The model is a directed reachability rule over `(segment, lane, node)` states,
one instance per mode:

* only segments with a lane of that mode's vehicle are in the graph, and only
  those lanes are traversable or continuable;
* a lane may be used away from a node only when its recorded direction grants
  travel in that sense (a `Both` lane grants both);
* a request lane must exist among the endpoint segment's mode lanes.

Junction pairing is fixed to `all`: at a road, ship-path or airplane-path node
every incident mode segment connects to every other. The retained queries are
reachability questions between two outside endpoints and contain no query that
would separate junction-pairing hypotheses, so those are not searched.

Two things stay named hypotheses rather than assumptions:

* `PAIRINGS` - which lane of one segment continues onto which lane of the next
  at a shared node;
* `UTURNS` - whether a vehicle may reverse inside one node.

Length is the sum of segment chords, a lower bound on the native curve length.
A path whose lower bound exceeds the protocol maximum is never a success.
"""

from __future__ import annotations

import heapq
import math

import topology

SUCCESS = "success"
NO_PATH = "no_path"
ABSTAIN = "abstain"


class Unresolved(Exception):
    """A request this topology cannot represent; the caller reports abstain."""

MODEL_VERSION = "outside-query-model-v1"

# The frozen protocol's own maximum path length.
MAX_LENGTH = 100000.0

PAIRINGS = {
    "any_lane": "every mode lane continues onto every mode lane at a node",
    "index_same": "lane ordinal i continues onto ordinal i",
    "index_mirror": "lane ordinal i continues onto ordinal n-1-i",
    "orientation_index": "i at a mixed node, n-1-i at a same-sided node",
    "orientation_mirror": "n-1-i at a mixed node, i at a same-sided node",
}

UTURNS = {
    "forbidden": "a vehicle never reverses inside a node",
    "allowed": "a vehicle may reverse inside a node",
}

BASELINES = [
    "always_fail",
    "always_candidate",
    "weak_component",
    "directed_segment",
]
LANE_RULES = [
    "lane:any_lane:forbidden",
    "lane:any_lane:allowed",
    "lane:index_same:forbidden",
    "lane:index_same:allowed",
    "lane:index_mirror:forbidden",
    "lane:orientation_index:forbidden",
    "lane:orientation_index:allowed",
    "lane:orientation_mirror:forbidden",
]
# Twelve generic rules per mode, frozen before any prediction was scored.
RULES = BASELINES + LANE_RULES
# Registered before the family was scored: the weakest lane-continuation
# hypothesis (any lane continues onto any lane) with no reversal.
PRIMARY_RULE = "lane:any_lane:forbidden"


def parse_rule(rule):
    if rule in BASELINES:
        return rule, None, None
    parts = rule.split(":")
    if parts[0] == "lane" and len(parts) == 3:
        _, pairing, uturn = parts
        if pairing in PAIRINGS and uturn in UTURNS:
            return "lane", pairing, uturn
    raise ValueError(f"unknown rule {rule}")


def chord(segment):
    return math.dist(segment["a"], segment["b"])


class Prepared:
    """One mode's pre-query graph, built once per opening."""

    def __init__(self, package, mode):
        self.package = package
        self.mode = mode
        self.segments = {}
        self.lanes = {}
        self.ordinals = {}
        self.incident = {}
        for segment_id, segment in package["segments"].items():
            lanes = []
            for lane in topology.mode_lanes(segment, mode):
                if "forward" not in lane or "backward" not in lane:
                    forward, backward = topology.direction_bits(lane["direction"])
                    lane = {**lane, "forward": forward, "backward": backward}
                lanes.append(lane)
            if not lanes:
                continue
            self.segments[segment_id] = segment
            self.lanes[segment_id] = lanes
            self.ordinals[segment_id] = {
                lane["index"]: ordinal for ordinal, lane in enumerate(lanes)
            }
        for segment_id, segment in self.segments.items():
            for node in dict.fromkeys((segment["start"], segment["end"])):
                self.incident.setdefault(node, []).append(segment_id)
        self._weak = None

    def lane_at(self, segment_id, index):
        for lane in self.lanes[segment_id]:
            if lane["index"] == int(index):
                return lane
        return None

    def weak_labels(self):
        if self._weak is None:
            labels = {}
            for start in self.incident:
                if start in labels:
                    continue
                pending = [start]
                while pending:
                    node = pending.pop()
                    if node in labels:
                        continue
                    labels[node] = start
                    for segment_id in self.incident[node]:
                        segment = self.segments[segment_id]
                        pending.append(
                            segment["end"]
                            if segment["start"] == node
                            else segment["start"]
                        )
            self._weak = labels
        return self._weak


def effective_forward(segment, node):
    """Is travel away from `node` forward once the segment's `Invert` is applied?"""
    forward = node == segment["start"]
    if "Invert" in segment.get("flags", ()):
        forward = not forward
    return forward


def can_travel(segment, lane, node):
    """Can this lane carry a vehicle away from `node` to the segment's far end?"""
    if node not in (segment["start"], segment["end"]):
        raise ValueError("node is not an end of the segment")
    return lane["forward"] if effective_forward(segment, node) else lane["backward"]


def continues(prepared, pairing, source_id, target_id, node, lane_index):
    """Raw indexes of `target`'s mode lanes that `lane_index` continues onto."""
    source_ordinal = prepared.ordinals[source_id][int(lane_index)]
    target_lanes = prepared.lanes[target_id]
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
    source = prepared.segments[source_id]
    target = prepared.segments[target_id]
    same_side = (source["start"] == node and target["start"] == node) or (
        source["end"] == node and target["end"] == node
    )
    mirrored = same_side if pairing == "orientation_index" else not same_side
    ordinal = len(target_lanes) - 1 - source_ordinal if mirrored else source_ordinal
    return (target_lanes[ordinal]["index"],) if 0 <= ordinal < len(target_lanes) else ()


def _lookup(prepared, request, side):
    segment_id, lane_index = int(request[side][0]), int(request[side][1])
    segment = prepared.segments.get(segment_id)
    if segment is None:
        raise Unresolved(f"segment {segment_id} has no {prepared.mode} lane here")
    lane = prepared.lane_at(segment_id, lane_index)
    if lane is None:
        raise Unresolved(
            f"segment {segment_id} has no {prepared.mode} lane {lane_index}"
        )
    return segment, lane


def _search(prepared, request, pairing, uturn, max_length, enforce_lanes):
    """Dijkstra over (segment, lane, node) states; returns (result, detail)."""
    source, source_lane = _lookup(prepared, request, "from")
    target, target_lane = _lookup(prepared, request, "to")
    start = topology.endpoint_node(source, request["from"][2])
    finish = topology.endpoint_node(target, request["to"][2])
    if start not in prepared.incident or finish not in prepared.incident:
        raise Unresolved("request endpoint node is absent from the mode graph")
    if not can_travel(source, source_lane, start):
        return NO_PATH, {"reason": "source_lane_cannot_leave_node"}
    # Arriving at the target node means travelling along the target lane from
    # the segment's other end toward it.
    if not can_travel(target, target_lane, topology.other_node(target, finish)):
        return NO_PATH, {"reason": "target_lane_cannot_reach_node"}

    first_lane = source_lane["index"] if enforce_lanes else None
    goal_lane = target_lane["index"] if enforce_lanes else None
    first = (source["id"], first_lane, start, False)
    goal = (target["id"], goal_lane, finish, True)
    # Every path must traverse the source segment, so this is a cheap necessary
    # condition. The length itself is added when the search crosses it; the
    # start state carries zero length so the source chord is never counted twice.
    if chord(source) > max_length:
        return NO_PATH, {"reason": "path_lower_bound_exceeds_max_length"}

    best = {first: 0.0}
    queue = [(0.0, first)]
    while queue:
        length, state = heapq.heappop(queue)
        if length > best.get(state, math.inf):
            continue
        if length > max_length:
            continue
        if state == goal:
            return SUCCESS, {"path_lower_bound_length": round(length, 6)}
        segment_id, lane_index, node, arrived = state
        segment = prepared.segments[segment_id]
        if arrived:
            for neighbour_id in prepared.incident[node]:
                if enforce_lanes and neighbour_id == segment_id:
                    if uturn == "forbidden":
                        continue
                neighbour = prepared.segments[neighbour_id]
                if enforce_lanes:
                    candidates = continues(
                        prepared, pairing, segment_id, neighbour_id, node, lane_index
                    )
                else:
                    # The segment-level baseline carries no lane state.
                    candidates = (None,)
                for next_index in candidates:
                    if enforce_lanes and prepared.lane_at(neighbour_id, next_index) is None:
                        continue
                    next_state = (neighbour_id, next_index, node, False)
                    if length < best.get(next_state, math.inf):
                        best[next_state] = length
                        heapq.heappush(queue, (length, next_state))
        else:
            far = topology.other_node(segment, node)
            if enforce_lanes:
                lane = prepared.lane_at(segment_id, lane_index)
            else:
                lane = next(
                    (
                        item
                        for item in prepared.lanes[segment_id]
                        if can_travel(segment, item, node)
                    ),
                    None,
                )
            if lane is None or not can_travel(segment, lane, node):
                continue
            next_length = length + chord(segment)
            if next_length > max_length:
                continue
            next_state = (segment_id, lane_index, far, True)
            if next_length < best.get(next_state, math.inf):
                best[next_state] = next_length
                heapq.heappush(queue, (next_length, next_state))
    return NO_PATH, {"reason": "no_directed_lane_path_within_max_length"}


def predict(prepared, request, rule):
    """One prediction. Returns {"prediction", "detail"}."""
    mode = prepared.mode
    if rule == "always_fail":
        return {"prediction": NO_PATH, "detail": {"reason": "baseline"}}
    if rule == "always_candidate":
        return {"prediction": SUCCESS, "detail": {"reason": "baseline"}}
    if rule == "weak_component":
        source = prepared.segments.get(int(request["from"][0]))
        target = prepared.segments.get(int(request["to"][0]))
        if source is None or target is None:
            return {"prediction": ABSTAIN, "detail": {"reason": "segment_absent"}}
        labels = prepared.weak_labels()
        source_node = topology.endpoint_node(source, request["from"][2])
        target_node = topology.endpoint_node(target, request["to"][2])
        same = labels.get(source_node) == labels.get(target_node)
        return {
            "prediction": SUCCESS if same else NO_PATH,
            "detail": {
                "reason": "same_weak_component" if same else "different_weak_component"
            },
        }
    kind, pairing, uturn = parse_rule(rule)
    enforce_lanes = kind == "lane"
    try:
        prediction, detail = _search(
            prepared, request, pairing, uturn, MAX_LENGTH, enforce_lanes
        )
    except Unresolved as error:
        return {"prediction": ABSTAIN, "detail": {"reason": str(error)}}
    return {"prediction": prediction, "detail": detail}
