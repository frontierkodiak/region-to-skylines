"""Order a city's saves in time, diff consecutive saves and summarise each.

Buffer ids are reused after demolition, so items are matched on what they are
and where they sit, not on their id.
"""

import math
from collections import Counter, defaultdict

import numpy as np

SKIP_SERVICES = {"pillar", "connection", "decoration"}
CELL_AREA_KM2 = 64e-6


def segment_key(seg):
    """Rounded end positions with the stored end directions (degrees). Unlike the
    curve's midpoint, these don't move when a neighbouring road changes an end
    node's kind (the Bézier control points depend on it)."""
    out = []
    for end, (dx, dz) in zip((seg["points"][0], seg["points"][-1]), seg["directions"]):
        out.append((round(end[0]), round(end[1]), round(math.degrees(math.atan2(dz, dx))) % 360))
    return tuple(sorted(out))


def building_key(b):
    return (round(b["x"] * 2), round(b["z"] * 2), b["width"], b["length"])


def zone_key(cell):
    return (round(cell[0] * 2), round(cell[1] * 2))


def diff(old, new):
    old_seg = {segment_key(s): s for s in old["segments"]}
    new_seg = {segment_key(s): s for s in new["segments"]}
    seg_added = [s for k, s in new_seg.items() if k not in old_seg]
    seg_removed = [s for k, s in old_seg.items() if k not in new_seg]
    seg_upgraded = [
        (old_seg[k]["prefab"], s["prefab"])
        for k, s in new_seg.items()
        if k in old_seg and old_seg[k]["prefab"] != s["prefab"]
    ]

    def live(city):
        return {building_key(b): b for b in city["buildings"] if b["service"] not in SKIP_SERVICES}

    old_b, new_b = live(old), live(new)
    b_added = [b for k, b in new_b.items() if k not in old_b]
    b_removed = [b for k, b in old_b.items() if k not in new_b]
    b_replaced = [
        (old_b[k]["prefab"], b["prefab"]) for k, b in new_b.items() if k in old_b and old_b[k]["prefab"] != b["prefab"]
    ]

    old_z = {zone_key(c): c[2] for c in old["zone_cells"]}
    new_z = {zone_key(c): c for c in new["zone_cells"]}
    zones_added = [(c[0], c[1], c[2]) for k, c in new_z.items() if c[2] > 1 and old_z.get(k, 0) != c[2]]
    zones_removed = sum(1 for k, code in old_z.items() if code > 1 and (k not in new_z or new_z[k][2] <= 1))
    return {
        "segments_added": seg_added,
        "segments_removed": seg_removed,
        "segments_upgraded": seg_upgraded,
        "buildings_added": b_added,
        "buildings_removed": b_removed,
        "buildings_replaced": b_replaced,
        "zones_added": zones_added,
        "zones_removed": zones_removed,
    }


def road_km(segments, player_only=True):
    out = Counter()
    for s in segments:
        if player_only and s["original"]:
            continue
        if s["category"] in ("road", "highway", "rail", "metro", "path", "water", "airport"):
            name = s["category"] if s["category"] != "road" else f"road ({s['level']})"
            out[name] += s["length"] / 1000
    return {k: round(v, 3) for k, v in out.items()}


def elevation_km(segments):
    out = Counter()
    for s in segments:
        if s["original"] or s["category"] not in ("road", "highway", "rail", "path"):
            continue
        out[s["elevation"]] += s["length"] / 1000
    return {k: round(v, 3) for k, v in out.items()}


def summary(city):
    services = Counter(
        b["service"]
        for b in city["buildings"]
        if b["service"] not in SKIP_SERVICES and not b["original"] and b["service"] != "growable"
    )
    growables = [b for b in city["buildings"] if b["service"] == "growable"]
    zone_km2 = {
        k: round(v * CELL_AREA_KM2, 4) for k, v in city["zone_counts"].items() if k not in ("Unzoned", "Distant")
    }
    return {
        "population": city["population"],
        "game_date": city["game_date"],
        "saved_at": city["saved_at"],
        "road_km": road_km(city["segments"]),
        "elevation_km": elevation_km(city["segments"]),
        "zone_km2": zone_km2,
        "services": dict(services),
        "growables": len(growables),
        "growable_levels": dict(Counter(b["level"] for b in growables)),
        "abandoned": sum(1 for b in growables if b["abandoned"]),
        "unlocked_tiles": int(sum(1 for v in city["area_grid"] if v)),
        "player_segments": sum(1 for s in city["segments"] if not s["original"]),
        "map_segments": sum(1 for s in city["segments"] if s["original"]),
    }


# Layout measures for the observations ------------------------------------------


def orientation_share(segments, tolerance_deg=7.5):
    """Dominant road direction (mod 90 degrees) and the share of straight-ish
    road length within `tolerance_deg` of it, weighted by length."""
    angles, weights = [], []
    for s in segments:
        if s["category"] not in ("road",):
            continue
        p = np.asarray(s["points"])
        d = p[-1] - p[0]
        if s["length"] < 8:
            continue
        angles.append(math.degrees(math.atan2(d[1], d[0])) % 90)
        weights.append(s["length"])
    if not angles:
        return None
    angles, weights = np.asarray(angles), np.asarray(weights)
    hist, edges = np.histogram(angles, bins=90, range=(0, 90), weights=weights)
    smooth = np.convolve(np.concatenate([hist[-7:], hist, hist[:7]]), np.ones(15), "valid")
    peak = float(np.argmax(smooth)) + 0.5
    delta = np.abs((angles - peak + 45) % 90 - 45)
    return {
        "dominant_deg": round(peak, 1),
        "aligned_share": round(float(weights[delta <= tolerance_deg].sum() / weights.sum()), 3),
        "km": round(float(weights.sum()) / 1000, 3),
    }


def curved_share(segments):
    total = curved = 0.0
    for s in segments:
        if s["category"] != "road":
            continue
        p = np.asarray(s["points"])
        chord = float(np.hypot(*(p[-1] - p[0])))
        total += s["length"]
        if s["length"] > 0 and chord / s["length"] < 0.995:
            curved += s["length"]
    return round(curved / total, 3) if total else None


def terrain_sample(raw, x, z):
    """TerrainManager.SampleRawHeightSmooth's grid: x/16+540, z/16+540, X contiguous."""
    gx = np.clip(np.asarray(x) / 16 + 540, 0, 1079.999)
    gz = np.clip(np.asarray(z) / 16 + 540, 0, 1079.999)
    i, j = gz.astype(int), gx.astype(int)
    fz, fx = gz - i, gx - j
    h = raw.astype(np.float32) / 64
    return (
        h[i, j] * (1 - fx) * (1 - fz)
        + h[i, j + 1] * fx * (1 - fz)
        + h[i + 1, j] * (1 - fx) * fz
        + h[i + 1, j + 1] * fx * fz
    )


def slope_grid(raw):
    h = raw.astype(np.float32) / 64
    gz, gx = np.gradient(h, 16.0)
    return np.degrees(np.arctan(np.hypot(gx, gz)))


def water_distance_grid(depth):
    """Distance in metres from each terrain cell to the nearest wet cell (city-scale)."""
    from scipy.ndimage import distance_transform_edt

    wet = depth > 16
    return distance_transform_edt(~wet) * 16.0


def at_grid(grid, x, z):
    gx = np.clip(np.round(np.asarray(x) / 16 + 540).astype(int), 0, 1080)
    gz = np.clip(np.round(np.asarray(z) / 16 + 540).astype(int), 0, 1080)
    return grid[gz, gx]


def placement_stats(points_xz, slope, water_dist, raw):
    if len(points_xz) == 0:
        return None
    p = np.asarray(points_xz)
    sl = at_grid(slope, p[:, 0], p[:, 1])
    wd = at_grid(water_dist, p[:, 0], p[:, 1])
    hh = terrain_sample(raw, p[:, 0], p[:, 1])
    return {
        "n": int(len(p)),
        "slope_median_deg": round(float(np.median(sl)), 2),
        "slope_over_10deg": round(float((sl > 10).mean()), 3),
        "water_dist_median_m": round(float(np.median(wd)), 1),
        "within_200m_of_water": round(float((wd <= 200).mean()), 3),
        "height_median_m": round(float(np.median(hh)), 1),
        "centroid": [round(float(p[:, 0].mean()), 1), round(float(p[:, 1].mean()), 1)],
    }


def segment_midpoints(segments):
    return [s["points"][len(s["points"]) // 2] for s in segments]


def bounds_of(cities, pad=400.0, square=False):
    xs, zs = [], []
    for c in cities:
        for s in c["segments"]:
            if s["original"]:
                continue
            for x, z in (s["points"][0], s["points"][-1]):
                xs.append(x)
                zs.append(z)
        for b in c["buildings"]:
            if not b["original"] and b["service"] not in SKIP_SERVICES:
                xs.append(b["x"])
                zs.append(b["z"])
    xs, zs = np.asarray(xs), np.asarray(zs)
    # robust bounds: ignore stray far-off items
    x0, x1 = np.percentile(xs, [0.2, 99.8])
    z0, z1 = np.percentile(zs, [0.2, 99.8])
    x0, x1, z0, z1 = x0 - pad, x1 + pad, z0 - pad, z1 + pad
    if square:
        cx, cz, r = (x0 + x1) / 2, (z0 + z1) / 2, max(x1 - x0, z1 - z0) / 2
        x0, x1, z0, z1 = cx - r, cx + r, cz - r, cz + r
    lim = 8640
    return (max(x0, -lim), max(z0, -lim), min(x1, lim), min(z1, lim))


def core_bounds(city, pad=300.0, aspect=1.0, cell=250.0):
    """Where the city lives: the box around the largest connected cluster of
    growable buildings in a save (250 m cells with 3+ growables, 8-connected),
    padded and widened to `aspect` (width / height)."""
    from scipy.ndimage import label

    pts = np.array([(b["x"], b["z"]) for b in city["buildings"] if b["service"] == "growable"])
    if len(pts) < 20:
        return None
    n = int(17280 / cell) + 1
    ix = ((pts[:, 0] + 8640) / cell).astype(int)
    iz = ((pts[:, 1] + 8640) / cell).astype(int)
    counts = np.zeros((n, n), dtype=int)
    np.add.at(counts, (iz, ix), 1)
    labels, _ = label(counts >= 3, structure=np.ones((3, 3)))
    sizes = np.bincount(labels.ravel(), weights=counts.ravel())
    sizes[0] = 0
    keep = labels[iz, ix] == int(np.argmax(sizes))
    sel = pts[keep]
    x0, z0 = sel.min(axis=0) - pad
    x1, z1 = sel.max(axis=0) + pad
    w, h = x1 - x0, z1 - z0
    if w / h < aspect:
        cx = (x0 + x1) / 2
        x0, x1 = cx - h * aspect / 2, cx + h * aspect / 2
    else:
        cz = (z0 + z1) / 2
        z0, z1 = cz - w / aspect / 2, cz + w / aspect / 2
    lim = 8640
    return (max(x0, -lim), max(z0, -lim), min(x1, lim), min(z1, lim))


def growth_by_district_ring(cities, origin):
    """Distance from `origin` of player road length added per save."""
    out = []
    for c in cities:
        d = [math.hypot(m[0] - origin[0], m[1] - origin[1]) for m in segment_midpoints(c["segments"]) if True]
        out.append(round(float(np.percentile(d, 90)), 0) if d else None)
    return out


def group_by(items, key):
    out = defaultdict(list)
    for item in items:
        out[key(item)].append(item)
    return out
