"""Outside air and ship connections as two-way paths across the map (PL-982).

A flight path follows the extended centreline of the region's main runway, from
map edge to map edge, so planes arrive on the real approach track. A ship lane
runs through deep, edge-connected sea from one edge, past the starting tile's
shore, to another edge. Both return graph fragments in `osm_highways`' format
(kinds "air" and "ship", two-way, outside nodes on the edge) that
`network_writer.apply_highways` writes with native connection prefabs.

Runway axes come from OpenStreetMap `aeroway=runway` ways (Overpass, fetched
2026-11-15) for the five fixture regions; other squares pass their own airport
via `geometry["airport"]` = {"name", "lat", "lon", "heading"}.
"""

import heapq
import math

import numpy as np
from scipy import ndimage

from region import HALF, SIZE, pixel, sample

AIRPORTS = {
    "asheville": {
        "name": "AVL 17/35",
        "lat": 35.43616,
        "lon": -82.54207,
        "heading": 159.9,
    },
    "innsbruck": {
        "name": "INN 08/26",
        "lat": 47.26030,
        "lon": 11.33940,
        "heading": 80.9,
    },
    "pittsburgh": {
        "name": "PIT 10C/28C",
        "lat": 40.48941,
        "lon": -80.22857,
        "heading": 92.0,
    },
    "charleston": {
        "name": "CHS 15/33",
        "lat": 32.90261,
        "lon": -80.04023,
        "heading": 147.5,
    },
    "rio": {"name": "SDU 02/20", "lat": -22.91030, "lon": -43.16358, "heading": 356.6},
}
SPACING = 96.0
EDGE = HALF


def to_game(sq, lon, lat):
    col, row = pixel(sq, [lon, lat])
    return np.array([(col - 540) * 16.0, -(row - 540) * 16.0])


def _edge_name(point):
    x, z = point
    if abs(abs(x) - EDGE) < 1e-6:
        return "east" if x > 0 else "west"
    return "north" if z > 0 else "south"


def _clip_line(point, direction):
    """Parameters where point + t*direction meets the square's boundary."""
    ts = []
    for axis in [0, 1]:
        if abs(direction[axis]) < 1e-9:
            continue
        for bound in [-EDGE, EDGE]:
            t = (bound - point[axis]) / direction[axis]
            q = point + t * direction
            if abs(q[1 - axis]) <= EDGE + 1e-6:
                ts.append(t)
    if len(ts) < 2:
        return None
    return min(ts), max(ts)


def _fragment(points, heights, kind):
    nodes = [
        {"xyz": [float(p[0]), float(h), float(p[1])], "outside": None}
        for p, h in zip(points, heights)
    ]
    for i in [0, -1]:
        p = np.array(points[i], float)
        p = np.clip(p, -EDGE, EDGE)
        nodes[i]["xyz"][0], nodes[i]["xyz"][2] = float(p[0]), float(p[1])
        nodes[i]["outside"] = _edge_name(p)
    tangents = np.gradient(np.asarray(points, float), axis=0)
    tangents /= np.linalg.norm(tangents, axis=1)[:, None]
    edges = []
    for a in range(len(points) - 1):
        ta, tb = tangents[a], tangents[a + 1]
        edges.append(
            {
                "a": a,
                "b": a + 1,
                "kind": kind,
                "structure": "ground",
                "start_dir": [float(ta[0]), 0.0, float(ta[1])],
                "end_dir": [float(-tb[0]), 0.0, float(-tb[1])],
            }
        )
    return {"nodes": nodes, "edges": edges}


def air_path(geometry, ground):
    """A straight flight path along the runway axis, edge to edge, or None."""
    sq = geometry["sq"]
    airport = geometry.get("airport") or AIRPORTS.get(sq.get("slug"))
    if airport is None:
        return None, {"air": "no airport for this square"}
    centre = to_game(sq, airport["lon"], airport["lat"])
    heading = math.radians(airport["heading"])
    north = 1000 / 111320
    east = north / math.cos(math.radians(airport["lat"]))
    ahead = to_game(
        sq,
        airport["lon"] + east * math.sin(heading),
        airport["lat"] + north * math.cos(heading),
    )
    direction = (ahead - centre) / np.linalg.norm(ahead - centre)
    span = _clip_line(centre, direction)
    if span is None:
        return None, {"air": f"{airport['name']} runway axis misses the square"}
    t0, t1 = span
    count = max(2, int(math.ceil((t1 - t0) / SPACING)) + 1)
    points = [centre + t * direction for t in np.linspace(t0, t1, count)]
    terrain = sample(ground, points)
    # Cruise above the highest ground under the track, within the game's 1024 m.
    altitude = float(min(1000.0, max(300.0, terrain.max() + 300.0)))
    inside = bool(np.all(np.abs(centre) <= EDGE))
    return _fragment(points, [altitude] * count, "air"), {
        "air": {
            "airport": airport["name"],
            "airport_inside_square": inside,
            "airport_xz": [float(v) for v in centre],
            "heading_deg": airport["heading"],
            "edges": [
                _edge_name(np.clip(points[0], -EDGE, EDGE)),
                _edge_name(np.clip(points[-1], -EDGE, EDGE)),
            ],
            "altitude_m": altitude,
            "nodes": count,
        }
    }


def _route(cost, start, goal):
    """Dijkstra on an 8-connected grid; returns [(row, col)] or None."""
    rows, cols = cost.shape
    best = np.full(cost.shape, np.inf)
    previous = {}
    best[start] = 0
    heap = [(0.0, start)]
    steps = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1)] + [
        (dr, dc, math.sqrt(2)) for dr in [-1, 1] for dc in [-1, 1]
    ]
    while heap:
        d, cell = heapq.heappop(heap)
        if cell == goal:
            path = [cell]
            while cell in previous:
                cell = previous[cell]
                path.append(cell)
            return path[::-1]
        if d > best[cell]:
            continue
        r, c = cell
        for dr, dc, length in steps:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and np.isfinite(cost[nr, nc]):
                nd = d + length * cost[nr, nc]
                if nd < best[nr, nc]:
                    best[nr, nc] = nd
                    previous[(nr, nc)] = cell
                    heapq.heappush(heap, (nd, (nr, nc)))
    return None


def ship_path(geometry, ground, depth, start_tile, sea_level, min_depth=6.0):
    """A ship lane through deep edge-connected sea, past the start tile's shore."""
    if geometry.get("seaLevel") is None:
        return None, {"ship": "inland square"}
    step = 4  # route on a 64 m grid
    deep = (depth >= min_depth)[::step, ::step]
    labels, count = ndimage.label(deep)
    border = np.unique(
        np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    )
    border = border[border > 0]
    if not len(border):
        return None, {"ship": "no deep water reaches the map edge"}
    sea = np.isin(labels, border)
    # Keep lanes off the shore: cost falls with distance from land.
    clearance = ndimage.distance_transform_edt(sea)
    cost = np.where(sea, 1 + 6 / np.maximum(clearance, 1), np.inf)
    n = sea.shape[0]
    tx, tz = start_tile % 5 - 2, start_tile // 5 - 2
    target_xz = np.array([tx * 1920.0, tz * 1920.0])
    rows, cols = np.nonzero(sea)
    xz = np.column_stack([cols * step * 16 - HALF, HALF - rows * step * 16])
    near = int(np.argmin(np.linalg.norm(xz - target_xz, axis=1)))
    harbour = (int(rows[near]), int(cols[near]))
    edge_cells = [
        (int(r), int(c))
        for r, c in zip(rows, cols)
        if min(r, c, n - 1 - r, n - 1 - c) == 0
        and 4 < r < n - 5
        or min(r, c, n - 1 - r, n - 1 - c) == 0
        and 4 < c < n - 5
    ]
    if len(edge_cells) < 2:
        return None, {"ship": "too little deep sea on the edge"}
    # Two edge cells: the one with most open water, then the farthest from it.
    openness = [clearance[r, c] for r, c in edge_cells]
    a = edge_cells[int(np.argmax(openness))]
    far = [
        (np.hypot(r - a[0], c - a[1]) * min(clearance[r, c], 6), (r, c))
        for r, c in edge_cells
    ]
    b = max(far)[1]
    first = _route(cost, a, harbour)
    second = _route(cost, harbour, b)
    if first is None or second is None:
        return None, {"ship": "no sea route past the start tile"}
    cells = np.array(first + second[1:], float)
    points = np.column_stack(
        [cells[:, 1] * step * 16 - HALF, HALF - cells[:, 0] * step * 16]
    )
    points = ndimage.gaussian_filter1d(points, 3, axis=0, mode="nearest")
    points[0], points[-1] = _to_edge(points[0]), _to_edge(points[-1])
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    wanted = np.linspace(0, arc[-1], max(2, int(math.ceil(arc[-1] / SPACING)) + 1))
    points = np.column_stack([np.interp(wanted, arc, points[:, k]) for k in [0, 1]])
    return _fragment(list(points), [float(sea_level)] * len(points), "ship"), {
        "ship": {
            "edges": [
                _edge_name(_to_edge(points[0])),
                _edge_name(_to_edge(points[-1])),
            ],
            "length_km": float(arc[-1] / 1000),
            "closest_to_start_tile_m": float(np.linalg.norm(xz[near] - target_xz)),
            "min_depth_m": min_depth,
            "nodes": len(points),
        }
    }


def _to_edge(point):
    p = np.clip(np.asarray(point, float), -EDGE, EDGE)
    axis = int(np.argmax(np.abs(p)))
    p[axis] = math.copysign(EDGE, p[axis])
    return p


def merge(graph, *fragments):
    """Append fragments to a graph, re-indexing their nodes."""
    for fragment in fragments:
        if fragment is None:
            continue
        offset = len(graph["nodes"])
        graph["nodes"].extend(fragment["nodes"])
        for e in fragment["edges"]:
            graph["edges"].append({**e, "a": e["a"] + offset, "b": e["b"] + offset})
    return graph


__all__ = ["air_path", "ship_path", "merge", "AIRPORTS", "SIZE"]
