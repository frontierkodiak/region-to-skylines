"""Pre-query prediction domain for outside-connection road, ship and air queries.

Two sources produce the same record:

* `from_native` reads one retained `networks.json.gz` opening snapshot that the
  outside-v1 harness captured before any query was submitted.
* `from_bridge` (`bridge.py`) reads the same fields out of a saved `.crp`
  export plus the fixed prefab lane-template catalog.

A record carries only what exists before a query: node and segment identity,
positions, prefab name, and per-lane index, lane type, vehicle, category and
direction. It never carries a request outcome, a successful path, a panel count
or an artifact id.

The numeric `flags` field that the outside-v1 snapshot writes beside each lane
is **not** a direction bitfield: a Ship lane with `flags` `"1"` is recorded as
`Both`, so the two cannot be the same encoding. The model therefore reads the
explicit `direction` string, and `bridge.py` checks that string against the
fixed prefab lane-template catalog rather than decoding the integer.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

# The three modes this study covers. Rail has its own reviewed research.
VEHICLE = {"road": "Car", "ship": "Ship", "air": "Plane"}

# NetInfo lane types the frozen outside-query protocol asks the pathfinder to
# accept. The protocol is copied from the accepted study's collector recipe.
ACCEPTED_LANE_TYPES = frozenset({"Vehicle", "TransportVehicle", "CargoVehicle"})

# NetInfo lane direction. `bits` is the travel permission the lane grants away
# from a node: forward, backward, both, or neither.
DIRECTION_BITS = {
    "Forward": (True, False),
    "Backward": (False, True),
    "Both": (True, True),
    "None": (False, False),
}


def tokens(value):
    """Split a comma-separated flag string, or pass an already-split record through."""
    if isinstance(value, (list, tuple, set, frozenset)):
        return frozenset(value)
    return frozenset(part for part in (value or "").split(", ") if part)


def direction_bits(direction):
    try:
        return DIRECTION_BITS[direction]
    except KeyError as error:  # pragma: no cover - guarded by the catalog
        raise ValueError(f"unknown lane direction {direction!r}") from error


def mode_lanes(segment, mode):
    """The lanes a request for `mode` with the frozen protocol could use."""
    vehicle = VEHICLE[mode]
    return [
        lane
        for lane in segment["lanes"]
        if vehicle in tokens(lane["vehicle"])
        and tokens(lane.get("lane_type", lane.get("type"))) & ACCEPTED_LANE_TYPES
    ]


def _lane(record):
    forward, backward = direction_bits(record["direction"])
    return {
        "index": int(record["index"]),
        "forward": forward,
        "backward": backward,
        # Recorded features, not filters: the frozen query accepts All categories.
        "lane_type": str(record["type"]),
        "vehicle": sorted(tokens(record["vehicle"])),
        "category": str(record["category"]),
    }


def _segment(record, prefab):
    return {
        "id": int(record["id"]),
        "start": int(record["start"]),
        "end": int(record["end"]),
        "a": tuple(float(v) for v in record["a"]),
        "b": tuple(float(v) for v in record["b"]),
        # `Invert` swaps which end of the segment counts as forward for the
        # lanes' travel grants; the model reads it through `effective_forward`.
        "flags": set(tokens(record.get("flags", ""))),
        "prefab": str(prefab) if prefab is not None else "",
        "lanes": [_lane(lane) for lane in record["lanes"]],
    }


def from_native(networks, name=""):
    """Normalise a parsed outside-v1 network snapshot.

    Node flags are captured for the eligibility inventory (the `Outside` role)
    but are not a model input. A node shared by two segments must agree; the
    retained snapshots do contain disagreements, so they are reported instead of
    raised.
    """
    segments = {}
    nodes = {}
    for record in networks["segments"]:
        segment = _segment(record, record.get("prefab"))
        segments[segment["id"]] = segment
        nodes.setdefault(segment["start"], {"flags": None, "position": None})
        nodes.setdefault(segment["end"], {"flags": None, "position": None})
        nodes[segment["start"]]["position"] = segment["a"]
        nodes[segment["end"]]["position"] = segment["b"]
    conflicts = []
    for record in networks["segments"]:
        for key in ("start", "end"):
            node = nodes[int(record[key])]
            flags = set(tokens(record[key + "_flags"]))
            if node["flags"] is None:
                node["flags"] = flags
            elif flags and node["flags"] != flags:
                conflicts.append(
                    {
                        "node": int(record[key]),
                        "kept": sorted(node["flags"]),
                        "seen": sorted(flags),
                    }
                )
    return {
        "name": name,
        "segments": segments,
        "nodes": nodes,
        "node_flag_conflicts": conflicts,
    }


def load_native(path, name=""):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf8") as stream:
            networks = json.load(stream)
    else:
        networks = json.loads(path.read_text())
    if networks.get("segments") is None:
        raise ValueError(f"{path} is not a network snapshot")
    return from_native(networks, name or path.parent.name)


def mode_index(package, mode):
    """Mode-capable segments and the incident segment ids of each node."""
    segments = {
        segment_id: segment
        for segment_id, segment in package["segments"].items()
        if mode_lanes(segment, mode)
    }
    incident = {}
    for segment_id, segment in segments.items():
        for node in dict.fromkeys((segment["start"], segment["end"])):
            incident.setdefault(node, []).append(segment_id)
    return segments, incident


def outside_roles(package, request):
    """The recorded Outside/OneWay roles of the request's two endpoint nodes."""
    roles = []
    for side in ("from", "to"):
        segment = package["segments"].get(int(request[side][0]))
        if segment is None:
            roles.append(None)
            continue
        node = endpoint_node(segment, request[side][2])
        recorded = package["nodes"].get(node, {}).get("flags")
        roles.append(None if recorded is None else sorted(recorded))
    return roles


def endpoint_node(segment, offset):
    offset = int(offset)
    if offset == 0:
        return segment["start"]
    if offset == 255:
        return segment["end"]
    raise ValueError("a boundary endpoint offset must be 0 or 255")


def other_node(segment, node):
    return segment["end"] if segment["start"] == node else segment["start"]
