"""Omit unsupported daylight connectors, including their inherited polygon cut.

Source geometry remains intact. Admission uses the uncarved DEM and explicit
portal connectivity, never a region name, observation or acceptance mask.
"""

from collections import Counter
import json

import numpy as np
from scipy import ndimage

from prepare import pixel


def feature_id(feature):
    return json.dumps(feature, sort_keys=True, separators=(",", ":"))


def connector_status(path, banks, geometry, features, channel, raster, lowering):
    if not geometry.get("undergroundWaterways"):
        return None
    ends = Counter()
    selected = []
    for feature in features:
        if (raster(geometry["sq"], [feature]) & channel).any():
            selected.append(feature)
            ends.update([tuple(feature["pts"][0]), tuple(feature["pts"][-1])])
    open_ends = [p for p, count in ends.items() if count == 1]
    portals = {
        tuple(p)
        for feature in geometry.get("undergroundWaterways", [])
        for p in [feature["pts"][0], feature["pts"][-1]]
    }
    if len(open_ends) != 2 or not all(p in portals for p in open_ends):
        return None
    y, x = path.T
    bed = banks[y, x]
    # Existing bounds: three metres of incision, one metre of wet headroom,
    # and a quarter metre of bank freeboard. Test both possible flow directions.
    lower, ceiling = bed - lowering + 1, bed - 0.25
    excess = [
        float((np.maximum.accumulate(a[::-1])[::-1] - b).max())
        for a, b in [(lower, ceiling), (lower[::-1], ceiling[::-1])]
    ]
    if min(excess) <= 1 / 64:
        return None
    return {"features": selected, "gravity_excess_m": excess}


def stroke(sq, features):
    """The browser carver's pixel-centre 0.6px segment-distance mask."""
    mask = np.zeros((1081, 1081), dtype=bool)
    for feature in features:
        points = [pixel(sq, p) for p in feature["pts"]]
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            c0, c1 = (
                max(0, int(np.floor(min(ax, bx) - 0.6))),
                min(1080, int(np.floor(max(ax, bx) + 0.6))),
            )
            r0, r1 = (
                max(0, int(np.floor(min(ay, by) - 0.6))),
                min(1080, int(np.floor(max(ay, by) + 0.6))),
            )
            if c0 > c1 or r0 > r1:
                continue
            yy, xx = np.mgrid[r0 : r1 + 1, c0 : c1 + 1]
            dx, dy = bx - ax, by - ay
            length = dx * dx + dy * dy
            t = (
                np.clip(((xx - ax) * dx + (yy - ay) * dy) / length, 0, 1)
                if length
                else 0
            )
            mask[r0 : r1 + 1, c0 : c1 + 1] |= (
                np.hypot(xx - ax - t * dx, yy - ay - t * dy) <= 0.6
            )
    return mask


def polygons(sq, features):
    """Browser fillMask's even-odd pixel-centre fill, preserving holes."""
    mask = np.zeros((1081, 1081), dtype=bool)
    for feature in features:
        rings = [[pixel(sq, p) for p in ring] for ring in feature["rings"]]
        ys = [y for ring in rings for _, y in ring]
        if not ys:
            continue
        for row in range(
            max(0, int(np.floor(min(ys)))), min(1080, int(np.ceil(max(ys)))) + 1
        ):
            xs = []
            for ring in rings:
                for (xi, yi), (xj, yj) in zip(ring, ring[-1:] + ring[:-1]):
                    if (yi > row) != (yj > row):
                        xs.append(xi + (row - yi) * (xj - xi) / (yj - yi))
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2]):
                ca, cb = max(0, int(np.ceil(a))), min(1081, int(np.ceil(b)))
                mask[row, ca : max(ca, cb)] = True
    return mask


def distance(mask):
    return (
        ndimage.distance_transform_edt(~mask)
        if mask.any()
        else np.full(mask.shape, np.inf)
    )


def remove_connector_cuts(ground, banks, geometry, surveys):
    """Replay only the change in the browser's combined line/body excavation.

    Polygon cells belong to their nearest mapped surface line. Retained lines
    win ties; lakes remain independent. The combined cut is blurred only after
    contributions are combined, just as in terrain.js. No deeper bed is added.
    """
    selected = {feature_id(f) for s in surveys for f in s["features"]}
    features = geometry.get("rivers", [])
    rejected = [f for f in features if feature_id(f) in selected]
    retained = [f for f in features if feature_id(f) not in selected]
    sq = geometry["sq"]
    removed_line = stroke(sq, rejected)
    retained_line = stroke(sq, retained)
    rejected_distance, retained_distance = (
        distance(removed_line),
        distance(retained_line),
    )
    areas = polygons(sq, geometry.get("riverAreas", []))
    retained_areas = areas & (retained_distance <= rejected_distance)
    lake_mask = polygons(sq, geometry.get("lakes", []))
    labels, count = ndimage.label(lake_mask)
    lake_cut = np.zeros_like(banks)
    for label, region in enumerate(ndimage.find_objects(labels), 1):
        component = labels[region] == label
        if component.sum() >= 12:
            values = banks[region]
            lake_cut[region][component] = np.minimum(
                0,
                values[component].min()
                - 4 * geometry["fit"]["verticalScale"]
                - values[component],
            )
    spacing = 16 * sq["scale"]
    depth = 10 * geometry["fit"]["verticalScale"]

    def cut(line_distance, body):
        width = max(40, 2.5 * spacing)
        p = np.clip(1 - (line_distance * spacing / width) ** 2, 0, 1) ** 2
        result = -depth * p
        d = ndimage.distance_transform_edt(body)
        ramp = np.clip(d * spacing / max(2 * spacing, 24), 0, 1)
        ramp = ramp * ramp * (3 - 2 * ramp)
        result = np.minimum(result, -depth * ramp)
        result = np.minimum(result, lake_cut).astype(np.float32)
        # terrain.smooth stores the intermediate horizontal pass as Float32.
        kernel_x = ndimage.gaussian_filter1d(
            result, 1.2, axis=1, radius=3, mode="nearest", output=np.float32
        )
        return ndimage.gaussian_filter1d(
            kernel_x, 1.2, axis=0, radius=3, mode="nearest", output=np.float32
        )

    before = cut(np.minimum(rejected_distance, retained_distance), areas)
    after = cut(retained_distance, retained_areas)
    delta = np.maximum(0, after.astype(float) - before)
    restored = np.maximum(ground, np.minimum(banks, ground + delta))
    # Where no retained excavation contributes, use DEM itself, not the old
    # PNG's quantization residue. This restores all interpolation vertices.
    restored[(after == 0) & (delta > 0)] = banks[(after == 0) & (delta > 0)]
    report = {
        "rule": "explicit portal-bounded connector; no feasible bounded gravity profile in either direction",
        "deferred_source_features": list(
            {feature_id(f): f for s in surveys for f in s["features"]}.values()
        ),
        "profiles": [{"gravity_excess_m": s["gravity_excess_m"]} for s in surveys],
        "restored_vertices": int(np.count_nonzero(restored > ground)),
        "deferred_polygon_vertices": int(np.count_nonzero(areas & ~retained_areas)),
        "maximum_restoration_m": float((restored - ground).max()),
    }
    return restored, report
