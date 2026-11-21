"""Pre-query package topology normalised for the rail reachability model.

Two sources produce the same record:

* `from_native` reads one of the frozen `networks.json.gz` snapshots that the
  PL-1215 native harness captured at opening, before any query was submitted.
* `from_bridge` (bridge.py) reads the same fields out of a saved `.crp` export.

A record only carries what the model is allowed to see before a query: node and
segment identity, flags, positions, prefab name, and per-lane category, type,
vehicle and travel bits. It never carries a query outcome, a successful path,
an artifact id or a special-segment marker.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

# NetInfo lane types the frozen protocol asks PathManager to accept.
LANE_TYPES = frozenset({"Vehicle", "TransportVehicle", "CargoVehicle"})


def tokens(value):
    return frozenset(part for part in (value or "").split(", ") if part)


def train_lanes(segment):
    """Lanes a Train request with the frozen protocol could use."""
    return [
        lane
        for lane in segment["lanes"]
        if tokens(lane["vehicle"]) & {"Train"}
        and tokens(lane["type"]) & LANE_TYPES
    ]


def _lane(record):
    forward = bool(record["forward"])
    backward = bool(record["backward"])
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
        "flags": tokens(record["flags"]),
        "prefab": str(prefab) if prefab is not None else "",
        "lanes": [_lane(lane) for lane in record["lanes"]],
    }


def from_native(networks, name=""):
    """Normalise a parsed native network snapshot."""
    segments = {}
    nodes = {}
    for record in networks["segments"]:
        segment = _segment(record, record.get("prefab"))
        segments[segment["id"]] = segment
        nodes.setdefault(segment["start"], {"flags": set(), "position": None})
        nodes.setdefault(segment["end"], {"flags": set(), "position": None})
        nodes[segment["start"]]["position"] = segment["a"]
        nodes[segment["end"]]["position"] = segment["b"]
    # Native snapshots do not carry a node table; the per-end flag strings are
    # the node flags. A node shared by two segments must agree, which is checked.
    for record in networks["segments"]:
        for key in ("start", "end"):
            node = nodes[int(record[key])]
            flags = tokens(record[key + "_flags"])
            if node["flags"] and flags and node["flags"] != set(flags):
                raise ValueError(f"node {record[key]} has conflicting native flags")
            node["flags"] = set(flags)
    return {"name": name, "segments": segments, "nodes": nodes}


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


def load_plan(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf8") as stream:
            frozen = json.load(stream)
    else:
        frozen = json.loads(path.read_text())
    return frozen


def outside_nodes(package):
    return {
        node_id
        for node_id, node in package["nodes"].items()
        if "Outside" in node["flags"]
    }
