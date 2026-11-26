"""Mapped edge crossings and widest water corridor; mirrored in connection-rules.js."""

import math
from collections import deque

DEFAULTS = dict(ship_width_m=256, margin_m=64, edge_margin_m=32, edge_separation_m=512)


def from_geometry(geometry):
    """Read the existing map-factory geometry using its shared square projection."""
    from prepare import pixel

    size = 271
    sq = geometry["sq"]

    def project(point):
        x, y = pixel(sq, point)
        return [float((x - 540) * 16), float((540 - y) * 16)]

    def raster(polygons):
        mask = [0] * (size * size)
        for polygon in polygons:
            rings = [
                [[x / 64 + 135.5, 135.5 - z / 64] for x, z in map(project, ring)]
                for ring in polygon["rings"]
            ]
            if not rings or not any(rings):
                continue
            y0 = max(0, math.floor(min(y for ring in rings for _, y in ring)))
            y1 = min(size - 1, math.ceil(max(y for ring in rings for _, y in ring)))
            for row in range(y0, y1 + 1):
                intersections = []
                y = row + 0.5
                for ring in rings:
                    for a, b in zip(ring, ring[-1:] + ring[:-1]):
                        if (a[1] > y) != (b[1] > y):
                            intersections.append(
                                a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                            )
                intersections.sort()
                for k in range(0, len(intersections) - 1, 2):
                    lo, hi = (
                        max(0, math.ceil(intersections[k] - 0.5)),
                        min(size, math.ceil(intersections[k + 1] - 0.5)),
                    )
                    if hi > lo:
                        mask[row * size + lo : row * size + hi] = [1] * (hi - lo)
        return mask

    oceans = geometry.get("oceans", [])
    return dict(
        extent_m=17280,
        roads=[
            dict(
                **{key: road.get(key) for key in ("class", "subclass", "service")},
                pts=list(map(project, road["pts"])),
            )
            for road in geometry.get("roads", [])
        ],
        water_grid=dict(
            size=size,
            spacing_m=64,
            water=raster(
                oceans + geometry.get("lakes", []) + geometry.get("riverAreas", [])
            ),
            sea=raster(oceans),
        ),
    )


def crosses(a, b, half):
    lo, hi = 0, 1
    for axis in range(2):
        delta = b[axis] - a[axis]
        if not delta:
            if abs(a[axis]) > half:
                return False
            continue
        t0, t1 = (-half - a[axis]) / delta, (half - a[axis]) / delta
        lo, hi = max(lo, min(t0, t1)), min(hi, max(t0, t1))
    if hi - lo < 1e-10:
        return False

    def inside(p):
        return max(abs(p[0]), abs(p[1])) < half - 1e-8

    t = (lo + hi) / 2
    if not inside([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]):
        return False
    return lo > 0 or hi < 1 or inside(a) != inside(b)


def edge_connection(lines, kind, half, margin):
    gap, eligible = math.inf, 0
    for line in lines:
        rail = (
            line["class"] == "rail"
            and line.get("subclass") not in ("subway", "light_rail", "tram", "monorail")
            and line.get("service") not in ("yard", "siding", "spur")
        )
        if not (line["class"] in ("motorway", "trunk") if kind == "road" else rail):
            continue
        eligible += 1
        points = line["pts"]
        if any(crosses(a, b, half) for a, b in zip(points, points[1:])):
            return dict(
                level="yes", reason="mapped_edge_crossing", crossings=1, edge_gap_m=0
            )
        for x, z in points:
            if abs(x) <= half and abs(z) <= half:
                gap = min(gap, half - max(abs(x), abs(z)))
    return dict(
        level="maybe" if gap <= margin else "no",
        reason="near_map_edge" if gap <= margin else "no_mapped_edge_crossing",
        crossings=0,
        edge_gap_m=math.floor(gap * 100 + 0.5) / 100 if math.isfinite(gap) else None,
        eligible_lines=eligible,
    )


def water_width(grid, separation=512):
    n, spacing, water = grid["size"], grid["spacing_m"], grid["water"]
    sea = grid.get("sea", [0] * (n * n))
    if not isinstance(n, int) or n < 2 or spacing <= 0 or len(water) != n * n:
        raise ValueError("Invalid mapped-water grid")
    distance = [n] * (n * n)
    queue = deque()
    for i, wet in enumerate(water):
        if not wet:
            distance[i] = 0
            queue.append(i)
    while queue:
        i = queue.popleft()
        r, c = divmod(i, n)
        for y in range(max(0, r - 1), min(n, r + 2)):
            for x in range(max(0, c - 1), min(n, c + 2)):
                j = y * n + x
                if distance[j] > distance[i] + 1:
                    distance[j] = distance[i] + 1
                    queue.append(j)
    order = sorted(
        (i for i, wet in enumerate(water) if wet), key=lambda i: (-distance[i], i)
    )
    parent = [-1] * (n * n)
    min_x, max_x = [n] * (n * n), [-1] * (n * n)
    min_y, max_y = [n] * (n * n), [-1] * (n * n)
    ocean = [False] * (n * n)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in order:
        r, c = divmod(i, n)
        parent[i], ocean[i] = i, bool(sea[i])
        if r in (0, n - 1) or c in (0, n - 1):
            min_x[i] = max_x[i] = c
            min_y[i] = max_y[i] = r
        for j in (
            i - n if r else -1,
            i + n if r < n - 1 else -1,
            i - 1 if c else -1,
            i + 1 if c < n - 1 else -1,
        ):
            if j < 0 or parent[j] < 0:
                continue
            a, b = find(i), find(j)
            if a != b:
                parent[b] = a
                min_x[a], max_x[a] = min(min_x[a], min_x[b]), max(max_x[a], max_x[b])
                min_y[a], max_y[a] = min(min_y[a], min_y[b]), max(max_y[a], max_y[b])
                ocean[a] = ocean[a] or ocean[b]
        root = find(i)
        span = max(max_x[root] - min_x[root], max_y[root] - min_y[root]) * spacing
        if span >= separation or (ocean[root] and max_x[root] >= 0):
            return max(0, 2 * distance[i] - 1) * spacing
    return 0


def check(data, rules=None):
    rules = rules or DEFAULTS
    width = water_width(data["water_grid"], rules["edge_separation_m"])
    delta = width - rules["ship_width_m"]
    return dict(
        road=edge_connection(
            data["roads"], "road", data["extent_m"] / 2, rules["edge_margin_m"]
        ),
        rail=edge_connection(
            data["roads"], "rail", data["extent_m"] / 2, rules["edge_margin_m"]
        ),
        ship=dict(
            level="no"
            if width == 0 or delta <= -rules["margin_m"]
            else "yes"
            if delta >= rules["margin_m"]
            else "maybe",
            reason="no_edge_waterway" if width == 0 else "mapped_water_width",
            width_m=width,
            threshold_m=rules["ship_width_m"],
            margin_m=rules["margin_m"],
        ),
        air=dict(level="yes", reason="plane_entries_always_written"),
    )
