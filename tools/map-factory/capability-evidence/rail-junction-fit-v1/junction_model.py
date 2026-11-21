"""Junction-connection hypotheses: chord vs authored tangent, continuation vs turn.

The accepted `rail-query-model-v1` fitted rule connects, at every node, only the
disjoint straightest-first pairing of incident Train segments, with the turn
angle computed from the **chord** between node positions. The export also
carries the **authored endpoint tangents** the game itself stores on each
segment, and this module asks whether the junction rule is better described
with those than with chords.

Nothing here re-implements the reachability core. `model._reach` (the accepted
corrected search: Train-only domain, `Invert`-aware travel bits, raw lane
indexes, chord lower-bound length with shortest-first relaxation) is called
unchanged. This module only produces the per-node partner maps and combines the
resolutions exactly as the accepted `model.reachable` does.

Families (all members are predeclared in `manifest.json`, never grown around an
observed error):

* `chord:continuation:<pairing>` / `tangent:continuation:<pairing>` — the
  accepted greedy disjoint straightest-first pairing, with the turn angle
  measured from chords or from authored tangents.
* `<measure>:turn:<T>:<pairing>` — a node connects every incident Train segment
  pair whose turn angle is at most `T` degrees. `T=180` is "every pair"; `T=0`
  is "only an exactly straight pair".
* `frozen:*` — the accepted v2 rules, delegated to the pinned accepted model,
  for the baseline comparison.

The pairing is the lane-continuation hypothesis: `any_lane` (the fitted v2
choice) or `orientation_index` (the v2 pre-registered lateral-side rule). A
`*:orientation_index` turn rule is the lane-compatible turn-angle hypothesis:
the turn has to be inside the threshold *and* the lateral lane order has to be
preserved.
"""

from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPABILITY = HERE.parent
ACCEPTED = CAPABILITY / "rail-query-model-v1"
sys.path[:0] = [str(HERE.parents[1]), str(ACCEPTED)]

import model  # noqa: E402

SUCCESS = model.SUCCESS
NO_PATH = model.NO_PATH
ABSTAIN = model.ABSTAIN

MODEL_VERSION = "rail-junction-fit-v1"

# Same tie representation as the accepted model: equal-turn continuation
# candidates are alternatives, not an allocation-id ordering.
TIE_TOLERANCE_DEGREES = 1e-6
# A turn is inside a threshold when it is not above it beyond float32 noise.
# Positions and directions are stored as binary32; one ulp of a unit vector is
# about 6e-4 degrees, so 1e-6 degrees is only a boundary-convention guard.
THRESHOLD_TOLERANCE_DEGREES = 1e-6
MAX_ALTERNATIVES = model.MAX_ALTERNATIVES
UTURN = "forbidden"
MAX_LENGTH = model.MAX_LENGTH

MEASURES = ("chord", "tangent")
PAIRINGS = ("any_lane", "orientation_index")
JUNCTION_KINDS = ("continuation", "turn")
THRESHOLDS = (0, 5, 10, 15, 20, 30, 45, 60, 90, 120, 150, 180)

BASELINES = ("frozen:always_fail", "frozen:always_candidate", "frozen:weak_component")
FROZEN_RULES = (
    "frozen:junction:continuation:any_lane",
    "frozen:junction:continuation:orientation_index",
    "frozen:junction:single:any_lane",
)
# The two primary comparisons, fixed before any score is computed.
PRIMARY_EQUIVALENT = "tangent:continuation:any_lane"
PRIMARY_REFERENCE = "frozen:junction:continuation:any_lane"


def rule_names():
    names = list(BASELINES) + list(FROZEN_RULES)
    for measure in MEASURES:
        for pairing in PAIRINGS:
            names.append(f"{measure}:continuation:{pairing}")
    for measure in MEASURES:
        for threshold in THRESHOLDS:
            for pairing in PAIRINGS:
                names.append(f"{measure}:turn:{threshold}:{pairing}")
    return names


def parse_rule(rule):
    """(measure, kind, pairing, threshold) for one of this study's own rules."""
    parts = rule.split(":")
    if len(parts) < 3:
        raise ValueError(f"unknown rule {rule}")
    if parts[1] == "continuation" and len(parts) == 3:
        measure, _, pairing = parts
        threshold = None
    elif parts[1] == "turn" and len(parts) == 4:
        measure, _, raw, pairing = parts
        threshold = int(raw)
        if threshold not in THRESHOLDS:
            raise ValueError(f"rule {rule} is outside the frozen threshold grid")
    else:
        raise ValueError(f"unknown rule {rule}")
    if measure not in MEASURES:
        raise ValueError(f"unknown measure {measure}")
    if pairing not in PAIRINGS:
        raise ValueError(f"unknown pairing {pairing}")
    return measure, parts[1], pairing, threshold


# ------------------------------------------------------------------ geometry


def _xz_unit(vector):
    length = math.hypot(vector[0], vector[2])
    if not length:
        return (0.0, 0.0)
    return (vector[0] / length, vector[2] / length)


def outward(package, node, segment_id, measure):
    """Unit xz heading from `node` into the segment, under `measure`.

    Chord: from the node's position toward the segment's other end. Tangent:
    the authored direction the export stores at that end, which points into the
    segment (proved against the export's own node positions; see
    `export_topology.tangent_report` and the README).
    """
    segment = package["segments"][segment_id]
    if node == segment["start"]:
        end, direction = "start", segment.get("start_direction")
    elif node == segment["end"]:
        end, direction = "end", segment.get("end_direction")
    else:
        raise ValueError("node is not an end of the segment")
    if measure == "chord":
        nodes = package["nodes"]
        here = nodes[node]["position"]
        far = segment["b"] if end == "start" else segment["a"]
        return _xz_unit((far[0] - here[0], far[1] - here[1], far[2] - here[2]))
    if measure == "tangent":
        if direction is None:
            raise KeyError(f"segment {segment_id} has no authored tangent")
        return _xz_unit(direction)
    raise ValueError(f"unknown measure {measure}")


def turn_degrees(package, node, source_id, target_id, measure):
    """Heading change from arriving along `source` to leaving along `target`.

    Zero is straight through: the arrival heading is the negation of the
    source's outward heading, and the departure heading is the target's.
    """
    into = outward(package, node, source_id, measure)
    out = outward(package, node, target_id, measure)
    cosine = max(-1.0, min(1.0, (-into[0]) * out[0] + (-into[1]) * out[1]))
    return math.degrees(math.acos(cosine))


# --------------------------------------------------------------- partner maps


def _continuation_matchings(package, node, segment_ids, measure):
    """Every greedy straightest-first matching, all tie resolutions included.

    The procedure is the accepted model's; only the angle function differs.
    Returns None when the number of resolutions exceeds `MAX_ALTERNATIVES`.
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
                turns.append((turn_degrees(package, node, a, b, measure), a, b))
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


def _reversals(unique):
    return {(a, a) for a in unique} if UTURN != "forbidden" else set()


def node_alternatives(package, incident, kind, measure, threshold=None):
    """One or more partner maps, or None when a junction has no unique reading."""
    alternatives_per_node = {}
    for node, segment_ids in incident.items():
        unique = list(dict.fromkeys(segment_ids))
        reversals = _reversals(unique)
        if kind == "turn":
            if threshold is None:
                raise ValueError("a turn rule needs a threshold")
            pairs = set()
            for index, a in enumerate(unique):
                for b in unique[index + 1 :]:
                    angle = turn_degrees(package, node, a, b, measure)
                    if angle <= threshold + THRESHOLD_TOLERANCE_DEGREES:
                        pairs.add((a, b))
                        pairs.add((b, a))
            alternatives_per_node[node] = [pairs | reversals]
            continue
        if len(unique) < 2:
            alternatives_per_node[node] = [reversals]
            continue
        matchings = _continuation_matchings(package, node, unique, measure)
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
    resolutions = []
    for combination in itertools.product(
        *(alternatives_per_node[node] for node in nodes)
    ):
        resolutions.append(dict(zip(nodes, combination)))
    return resolutions


# ------------------------------------------------------------------ prediction


def _combine(segments, incident, resolutions, request, pairing):
    """Score one request under every resolution; agree, or abstain."""
    outcomes = [
        model._reach(  # noqa: SLF001 - the accepted reachability core, reused
            segments, incident, partners, request, pairing, UTURN, MAX_LENGTH
        )
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


class Engine:
    """A package's junction resolutions, computed once and reused per request.

    A junction partner map depends on the package, the measure, the junction
    kind and the threshold, never on the request or the outcome. Computing it
    per query is the same result at a large multiple of the cost, so the study
    memoises it here. `predict` and `reachable` keep the stateless API the
    tests use.
    """

    def __init__(self, package):
        self.package = package
        self.segments, self.incident = model.train_index(package)
        self._resolutions = {}

    def resolutions(self, kind, measure, threshold=None):
        key = (kind, measure, threshold)
        if key not in self._resolutions:
            try:
                value = node_alternatives(
                    self.package, self.incident, kind, measure, threshold
                )
            except KeyError as error:
                value = ("missing_tangent", str(error))
            self._resolutions[key] = value
        return self._resolutions[key]

    def frozen_resolutions(self, junction, uturn):
        key = ("frozen", junction, uturn)
        if key not in self._resolutions:
            self._resolutions[key] = model._node_alternatives(  # noqa: SLF001
                self.package, self.incident, junction, uturn
            )
        return self._resolutions[key]

    def predict(self, request, rule):
        if rule.startswith("frozen:"):
            inner = rule.split(":", 1)[1]
            if inner in model.BASELINES:
                return model.predict(self.package, request, inner)
            kind, pairing, uturn, junction = model.parse_rule(inner)
            if uturn != "forbidden":
                return model.predict(self.package, request, inner)
            resolutions = self.frozen_resolutions(junction, uturn)
            if resolutions is None:
                return {
                    "prediction": ABSTAIN,
                    "detail": {"reason": "ambiguous_junction_pairing"},
                }
            try:
                prediction, detail = _combine(
                    self.segments, self.incident, resolutions, request, pairing
                )
            except LookupError as error:
                return {"prediction": ABSTAIN, "detail": {"reason": str(error)}}
            return {"prediction": prediction, "detail": detail}
        measure, kind, pairing, threshold = parse_rule(rule)
        resolutions = self.resolutions(kind, measure, threshold)
        if (
            isinstance(resolutions, tuple)
            and resolutions
            and resolutions[0] == "missing_tangent"
        ):
            return {
                "prediction": ABSTAIN,
                "detail": {"reason": f"missing_tangent:{resolutions[1]}"},
            }
        if resolutions is None:
            return {
                "prediction": ABSTAIN,
                "detail": {"reason": "ambiguous_junction_pairing"},
            }
        try:
            prediction, detail = _combine(
                self.segments, self.incident, resolutions, request, pairing
            )
        except LookupError as error:
            return {"prediction": ABSTAIN, "detail": {"reason": str(error)}}
        return {"prediction": prediction, "detail": detail}


def reachable(package, request, kind, pairing, measure, threshold=None):
    """Stateless form of `Engine.predict` for one of this study's own rules."""
    return Engine(package).predict(
        request,
        f"{measure}:{kind}:"
        + (f"{threshold}:" if threshold is not None else "")
        + pairing,
    )


def predict(package, request, rule):
    """One prediction for one rule. `frozen:*` delegates to the accepted code."""
    return Engine(package).predict(request, rule)
