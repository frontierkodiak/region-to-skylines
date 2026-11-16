"""A city's layout from a decoded save: road and rail segments as Bézier curves,
building footprints, zone cells, trees and headline numbers.
"""

import math
from datetime import datetime, timedelta

import numpy as np

from . import classify
from .managers import ZONES, zone_cells

NODE_MIDDLE = 0x20
NODE_OUTSIDE = 0x400
ORIGINAL = 4  # Created by the map, not the player (Building, NetNode, NetSegment)
SEGMENT_UNTOUCHABLE = 0x20
BUILDING_UNTOUCHABLE = 0x10
BUILDING_COMPLETED = 0x10000
BUILDING_ABANDONED = 0x40000
BUILDING_COLLAPSED = 0x400000


def dotnet_ticks(ticks):
    return datetime(1, 1, 1) + timedelta(microseconds=ticks // 10)


def middle_points(a, da, b, db, smooth_a, smooth_b):
    """NetSegment.CalculateMiddlePoints on the XZ plane (directions point inward)."""
    dx, dz = b[0] - a[0], b[1] - a[1]
    distance = math.hypot(dx, dz)
    ux, uz = (dx / distance, dz / distance) if distance > 0 else (0.0, 0.0)
    dot = da[0] * db[0] + da[1] * db[1]
    if dot < -0.999 and da[0] * ux + da[1] * uz > 0.999:
        ka = distance * (0.3 if smooth_a else 0.15)
        kb = distance * (0.3 if smooth_b else 0.15)
        return (a[0] + da[0] * ka, a[1] + da[1] * ka), (b[0] + db[0] * kb, b[1] + db[1] * kb)
    u = v = None
    if dot >= -0.999:
        vx, vz = da
        wx, wz = db
        cross = vx * wz - vz * wx
        if cross != 0:
            px, pz = a[0] - b[0], a[1] - b[1]
            u = (pz * wx - px * wz) / cross
            v = (vx * pz - vz * px) / cross
    if u is not None:
        u = min(max(u, distance * 0.1), distance)
        v = min(max(v, distance * 0.1), distance)
        total = u + v
        ka, kb = min(u, total * 0.3), min(v, total * 0.3)
    else:
        ka = kb = distance * 0.3
    return (a[0] + da[0] * ka, a[1] + da[1] * ka), (b[0] + db[0] * kb, b[1] + db[1] * kb)


def bezier(a, b, c, d, steps=8):
    t = np.linspace(0, 1, steps + 1)[:, None]
    p = np.array([a, b, c, d], dtype=np.float64)
    return (1 - t) ** 3 * p[0] + 3 * (1 - t) ** 2 * t * p[1] + 3 * (1 - t) * t**2 * p[2] + t**3 * p[3]


def extract(save):
    """Plain-Python city model of one save (lists and dicts, JSON-ready)."""
    net = save.data["NetManager"]
    bld = save.data["BuildingManager"]
    zones = save.data["ZoneManager"]
    area = save.data["GameAreaManager"]
    meta = save.simulation_meta

    node_index = {int(n): i for i, n in enumerate(net["node_ids"])}
    positions = net["node_position"]
    node_flags = net["node_flags"]

    segments = []
    for k, sid in enumerate(net["segment_ids"]):
        prefab = net["segment_prefab"][k]
        kind = classify.net(prefab)
        if kind["category"] == "virtual":
            continue
        i, j = node_index[int(net["segment_start_node"][k])], node_index[int(net["segment_end_node"][k])]
        a = (float(positions[i][0]), float(positions[i][2]))
        b = (float(positions[j][0]), float(positions[j][2]))
        da = tuple(float(v) for v in net["segment_start_direction"][k][[0, 2]])
        db = tuple(float(v) for v in net["segment_end_direction"][k][[0, 2]])
        m1, m2 = middle_points(a, da, b, db, node_flags[i] & NODE_MIDDLE, node_flags[j] & NODE_MIDDLE)
        pts = bezier(a, m1, m2, b)
        length = float(np.hypot(*np.diff(pts, axis=0).T).sum())
        flags = int(net["segment_flags"][k])
        segments.append(
            {
                "id": int(sid),
                "prefab": prefab,
                "category": kind["category"],
                "level": kind["level"],
                "elevation": kind["elevation"],
                "original": bool(flags & ORIGINAL),
                "untouchable": bool(flags & SEGMENT_UNTOUCHABLE),
                "build_index": int(net["segment_build_index"][k]),
                "length": round(length, 2),
                "y": round((float(positions[i][1]) + float(positions[j][1])) / 2, 2),
                "points": np.round(pts, 1).tolist(),
                "directions": [[round(v, 4) for v in da], [round(v, 4) for v in db]],
                "nodes": [int(net["segment_start_node"][k]), int(net["segment_end_node"][k])],
            }
        )

    buildings = []
    for k, bid in enumerate(bld["ids"]):
        prefab = bld["prefab"][k]
        kind = classify.building(prefab)
        flags = int(bld["flags"][k])
        x, y, z = (float(v) for v in bld["position"][k])
        buildings.append(
            {
                "id": int(bid),
                "prefab": prefab,
                "service": kind["service"],
                "zone": kind["zone"],
                "level": int(bld["level"][k]) + 1,
                "x": round(x, 2),
                "y": round(y, 2),
                "z": round(z, 2),
                "angle": round(float(bld["angle"][k]), 4),
                "width": int(bld["width"][k]),
                "length": int(bld["length"][k]),
                "original": bool(flags & ORIGINAL),
                "untouchable": bool(flags & BUILDING_UNTOUCHABLE),
                "completed": bool(flags & BUILDING_COMPLETED),
                "abandoned": bool(flags & BUILDING_ABANDONED),
                "collapsed": bool(flags & BUILDING_COLLAPSED),
                "sub_building": int(bld["sub_building"][k]),
                "build_index": int(bld["build_index"][k]),
                "citizens": int(bld["citizen_count"][k]),
            }
        )

    cells = zone_cells(zones)
    zone_counts = {}
    for _, _, code, *_ in cells:
        name = ZONES.get(code, str(code))
        zone_counts[name] = zone_counts.get(name, 0) + 1

    _lot_zones(buildings, cells)
    trees = save.data.get("TreeManager")
    out = {
        "city": save.metadata.get("cityName"),
        "saved_at": save.metadata.get("timeStamp"),
        "population": _number(save.metadata.get("population")),
        "cash": save.metadata.get("cash"),
        "map": meta["map_name"],
        "environment": meta["environment"],
        "game_date": dotnet_ticks(meta["current_ticks"]).isoformat(),
        "start_date": dotnet_ticks(meta["starting_ticks"]).isoformat(),
        "frame_index": save.simulation["frame_index"],
        "build_index": save.simulation["build_index"],
        "area_grid": area["area_grid"].tolist(),
        "start_tile": area["start_tile"],
        "segments": segments,
        "buildings": buildings,
        "zone_cells": [(round(x, 1), round(z, 1), int(code), b) for x, z, code, b, _, _ in cells],
        "zone_counts": zone_counts,
        "tree_count": int(len(trees["ids"])) if trees else None,
        "names": save.data["InstanceManager"]["names"],
    }
    return out


def _number(text):
    if text is None:
        return None
    digits = "".join(ch for ch in str(text) if ch.isdigit())
    return int(digits) if digits else None


ZONE_CODES = {
    "ResidentialLow": 2,
    "ResidentialHigh": 3,
    "CommercialLow": 4,
    "CommercialHigh": 5,
    "Industrial": 6,
    "Office": 7,
}


def _lot_zones(buildings, cells):
    """A growable's zone: from its prefab's class when the catalog knows it,
    otherwise the zone of the cell nearest its position (within 12 m), the lot
    it stands on."""
    from scipy.spatial import cKDTree

    if not cells:
        return
    xy = np.array([(c[0], c[1]) for c in cells])
    codes = np.array([c[2] for c in cells])
    tree = cKDTree(xy)
    for b in buildings:
        if b["service"] != "growable":
            continue
        if b["zone"] in ZONE_CODES:
            b["lot_zone"] = ZONE_CODES[b["zone"]]
            continue
        dist, i = tree.query((b["x"], b["z"]))
        b["lot_zone"] = int(codes[i]) if dist <= 12 else None
