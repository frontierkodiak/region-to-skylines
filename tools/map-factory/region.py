"""Prepare an arbitrary browser export for the fixed-topology CRP writer."""

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage, optimize

from prepare import pixel, route

SIZE, SPACING, HALF = 1081, 16, 8640


def raster(sq, features, polygons=False):
    image = Image.new("L", (SIZE, SIZE))
    draw = ImageDraw.Draw(image)
    for feature in features:
        if polygons:
            layer = Image.new("L", image.size)
            painter = ImageDraw.Draw(layer)
            for i, ring in enumerate(feature["rings"]):
                if len(ring) >= 3:
                    painter.polygon(
                        [pixel(sq, p) for p in ring], fill=255 if i == 0 else 0
                    )
            image = Image.fromarray(np.maximum(np.asarray(image), np.asarray(layer)))
            draw = ImageDraw.Draw(image)
        elif len(feature["pts"]) >= 2:
            draw.line([pixel(sq, p) for p in feature["pts"]], fill=255, width=1)
    return np.asarray(image) > 0


def clusters(mask):
    labels, _ = ndimage.label(mask, structure=np.ones((3, 3)))
    result = []
    for label, region in enumerate(ndimage.find_objects(labels), 1):
        if region is None:
            continue
        ys, xs = np.nonzero(labels[region] == label)
        result.append(
            (
                int(np.floor(xs.mean() + region[1].start + 0.5)),
                int(np.floor(ys.mean() + region[0].start + 0.5)),
            )
        )
    return result


def sample(grid, positions):
    positions = np.asarray(positions)
    return ndimage.map_coordinates(
        grid,
        [540 - positions[:, 1] / 16, 540 + positions[:, 0] / 16],
        order=1,
        mode="nearest",
    )


def hydrology(ground, banks, geometry, max_lowering=3.0):
    """Bank-referenced monotone profiles, bounded incision and initialized water.

    The old running minimum followed anomalously deep bed pixels forever. A
    least-squares monotone fit to *uncarved* elevations avoids that ratchet.
    A downstream lower envelope then guarantees at least 1 m of thalweg water
    without exceeding the explicit additional-incision cap.
    """
    sq = geometry["sq"]
    sea = geometry.get("seaLevel")
    surface = np.full_like(ground, sea if sea is not None else 0)
    sources, summaries, samples = [], [], {}
    grouped = {}
    for river in geometry.get("rivers", []) + geometry.get("streams", []):
        key = (river.get("name") or "unnamed waterway", river.get("class", "river"))
        grouped.setdefault(key, []).append(river)
    masks = {key: raster(sq, features) for key, features in grouped.items()}
    union = np.zeros_like(ground, dtype=bool)
    for mask in masks.values():
        union |= mask
    areas = raster(sq, geometry.get("riverAreas", []), polygons=True)
    smooth_banks = ndimage.median_filter(banks, size=5)
    original = ground.copy()
    edge = np.zeros_like(union)
    edge[:2] = edge[-2:] = True
    edge[:, :2] = edge[:, -2:] = True
    for (name, kind), mask in sorted(
        masks.items(), key=lambda item: (-int(item[1].sum()), item[0])
    ):
        if mask.sum() < 45:
            continue
        near = ndimage.binary_dilation(mask, iterations=2)
        labels, count = ndimage.label(near, structure=np.ones((3, 3)))
        others = union & ~mask
        joins = ndimage.binary_dilation(others, iterations=3)
        for component in range(1, count + 1):
            channel = mask & (labels == component)
            if channel.sum() < 45:
                continue
            candidates = clusters(channel & edge) + clusters(channel & joins)
            # Include actual isolated line ends, but not ordinary tile seams.
            neighbors = ndimage.convolve(
                channel.astype(np.uint8),
                np.ones((3, 3), dtype=np.uint8),
                mode="constant",
            )
            candidates += clusters(
                channel
                & (neighbors <= 2)
                & ~ndimage.binary_dilation(joins, iterations=2)
            )
            if len(candidates) < 2:
                ys, xs = np.nonzero(channel)
                candidates += [
                    (int(xs[i]), int(ys[i]))
                    for i in [
                        np.argmin(xs),
                        np.argmax(xs),
                        np.argmin(ys),
                        np.argmax(ys),
                    ]
                ]
            candidates = sorted(set(candidates))
            levels = [smooth_banks[y, x] for x, y in candidates]
            start, end = (
                candidates[int(np.argmax(levels))],
                candidates[int(np.argmin(levels))],
            )
            if np.hypot(start[0] - end[0], start[1] - end[1]) < 20:
                # A level estuary still needs a spatially long path, not two
                # neighboring pixels selected by centimetres of DEM noise.
                start, end = max(
                    ((a, b) for a in candidates for b in candidates),
                    key=lambda ab: (
                        (ab[0][0] - ab[1][0]) ** 2 + (ab[0][1] - ab[1][1]) ** 2
                    ),
                )
                if smooth_banks[start[1], start[0]] < smooth_banks[end[1], end[0]]:
                    start, end = end, start
            path = route(channel, start, end, ground=ground)
            y, x = path.T
            if len(path) < 45:
                continue
            arc = np.r_[0, np.cumsum(np.hypot(np.diff(x), np.diff(y)) * SPACING)]
            wanted = (
                ndimage.gaussian_filter1d(
                    ndimage.median_filter(banks[y, x], size=13), 5
                )
                - 2
            )
            slope = 0.00005
            fitted = optimize.isotonic_regression(
                wanted + arc * slope, increasing=False
            ).x
            lower = original[y, x] - max_lowering + 1 + arc * slope
            fitted = (
                np.maximum(fitted, np.maximum.accumulate(lower[::-1])[::-1])
                - arc * slope
            )
            if sea is not None:
                fitted = np.maximum(fitted, sea)
            line = np.zeros_like(channel)
            line[y, x] = True
            distance, nearest = ndimage.distance_transform_edt(
                ~line, return_indices=True
            )
            line_levels = np.zeros_like(ground)
            line_levels[y, x] = fitted
            local_surface = line_levels[tuple(nearest)]
            desired_bed = local_surface - 3.0 + (distance * SPACING / 32) ** 2 * 3.0
            corridor = distance <= 3
            ground[corridor] = np.maximum(
                original[corridor] - max_lowering,
                np.minimum(ground[corridor], desired_bed[corridor]),
            )
            wet = ((distance <= 4) | (areas & (distance <= 32))) & (
                ground < local_surface
            )
            surface[wet] = np.maximum(surface[wet], local_surface[wet])
            key = f"{name} [{kind}] #{component}"
            samples[key] = [
                [int(px * 16 - HALF), 0, int(HALF - py * 16)]
                for py, px in path[:: max(1, len(path) // 30)]
            ]
            interior = np.flatnonzero(
                (x >= 6) & (x <= SIZE - 7) & (y >= 6) & (y <= SIZE - 7)
            )
            source_i = (
                int(interior[min(2, len(interior) - 1)]) if len(interior) else None
            )
            if source_i is not None and (sea is None or fitted[source_i] > sea + 0.5):
                capacity = 0.06 if kind == "stream" else 0.2
                sources.append(
                    {
                        "name": name,
                        "class": kind,
                        "position": [
                            int(x[source_i] * 16 - HALF),
                            0,
                            int(HALF - y[source_i] * 16),
                        ],
                        "target": float(fitted[source_i]),
                        "capacity": capacity,
                    }
                )
            summaries.append(
                {
                    "name": name,
                    "class": kind,
                    "length_m": float(arc[-1]),
                    "upstream": list(start),
                    "downstream": list(end),
                    "max_surface_above_uncarved_m": float((fitted - banks[y, x]).max()),
                }
            )
    lake_mask = raster(sq, geometry.get("lakes", []), polygons=True)
    labels, count = ndimage.label(lake_mask)
    for label, region in enumerate(ndimage.find_objects(labels), 1):
        component = labels[region] == label
        if component.sum() < 8:
            continue
        bed, bank = ground[region][component], banks[region][component]
        level = float(np.percentile(bank, 25) - 0.5)
        if sea is not None:
            level = max(sea, level)
        values = surface[region]
        values[component] = np.maximum(values[component], level)
        ys, xs = np.nonzero(component)
        deepest = int(np.argmax(level - bed))
        if level > (sea if sea is not None else 0) + 0.5 and level - bed[deepest] > 0.5:
            row, col = ys[deepest] + region[0].start, xs[deepest] + region[1].start
            sources.append(
                {
                    "name": "lake",
                    "class": "lake",
                    "position": [int(col * 16 - HALF), 0, int(HALF - row * 16)],
                    "target": level,
                    "capacity": 0.06,
                }
            )
    depth = np.maximum(0, surface - ground)
    coverage = []
    for (name, kind), mask in sorted(masks.items()):
        if mask.sum() >= 45:
            coverage.append(
                {
                    "name": name,
                    "class": kind,
                    "mapped_cells": int(mask.sum()),
                    "initial_wet_fraction": float((depth[mask] > 0.1).mean()),
                }
            )
    return depth, {
        "sources": sources,
        "samples": samples,
        "rivers": summaries,
        "sea_level_m": float(sea if sea is not None else 0),
        "max_channel_lowering_m": float((original - ground).max()),
        "channel_lowering_cap_m": max_lowering,
        "mapped_waterway_coverage": coverage,
    }


def start_area(ground, depth, geometry):
    dy, dx = np.gradient(ground, 16)
    buildable = (np.hypot(dx, dy) < 0.15) & (depth < 0.25)
    road_mask = raster(
        geometry["sq"],
        [
            r
            for r in geometry.get("roads", [])
            if r.get("class") in ["motorway", "trunk"]
        ],
    )
    road_distance = (
        ndimage.distance_transform_edt(~road_mask)
        if road_mask.any()
        else np.zeros_like(ground)
    )
    options = []
    for z in range(5):
        for x in range(5):
            col, row = 540 + (x - 2) * 120, 540 - (z - 2) * 120
            area = np.s_[row - 60 : row + 60, col - 60 : col + 60]
            land = float(buildable[area].mean())
            water = int((depth[area] > 0.5).sum())
            if land > 0.15:
                options.append(
                    (
                        int(water >= 8),
                        int(road_mask[area].any()),
                        land - 0.15 * np.hypot(x - 2, z - 2),
                        x,
                        z,
                    )
                )
    if not options:
        raise ValueError("No buildable starting tile in the vanilla 25-tile area")
    has_water, _, _, x, z = max(options)
    col, row = 540 + (x - 2) * 120, 540 - (z - 2) * 120
    yy, xx = np.mgrid[row - 50 : row + 51, col - 50 : col + 51]
    cost = (
        (xx - col) ** 2
        + (yy - row) ** 2
        + np.hypot(dx[yy, xx], dy[yy, xx]) * 3000
        + road_distance[yy, xx] ** 2 * 25
    )
    cost[~buildable[yy, xx]] += 1e7
    target = np.unravel_index(np.argmin(cost), cost.shape)
    return {
        "index": z * 5 + x,
        "x": x,
        "z": z,
        "has_water": bool(has_water),
        "landing": [int(xx[target] * 16 - HALF), int(HALF - yy[target] * 16)],
        "buildable_fraction": float(
            buildable[row - 60 : row + 60, col - 60 : col + 60].mean()
        ),
    }


def crossings(geometry, classes):
    result = []
    for feature in geometry.get("roads", []):
        kind = feature.get("class")
        if kind not in classes:
            continue
        points = [
            (np.asarray(pixel(geometry["sq"], p)) - 540) * [16, -16]
            for p in feature["pts"]
        ]
        for a, b in itertools.pairwise(points):
            for axis in [0, 1]:
                if abs(b[axis] - a[axis]) < 1e-8:
                    continue
                for boundary in [-HALF, HALF]:
                    t = (boundary - a[axis]) / (b[axis] - a[axis])
                    if 0 <= t <= 1:
                        point = a + (b - a) * t
                        if abs(point[1 - axis]) < HALF - 80 and not any(
                            np.linalg.norm(point - np.asarray(c["point"])) < 160
                            for c in result
                        ):
                            edge = (
                                ["west", "east"] if axis == 0 else ["south", "north"]
                            )[int(boundary > 0)]
                            result.append(
                                {"point": point.tolist(), "edge": edge, "class": kind}
                            )
    return sorted(result, key=lambda c: (c["class"], c["edge"], c["point"]))


def fit_networks(ground, depth, geometry, spec, start):
    landing = np.asarray(start["landing"], dtype=float)
    entries = crossings(geometry, {"motorway", "trunk"})
    if entries:
        entry = min(
            entries,
            key=lambda c: (
                c["class"] != "motorway",
                np.linalg.norm(np.asarray(c["point"]) - landing),
            ),
        )
    else:
        edges = [
            [-HALF, landing[1]],
            [HALF, landing[1]],
            [landing[0], -HALF],
            [landing[0], HALF],
        ]
        i = int(np.argmin(sample(ground, edges)))
        entry = {
            "point": edges[i],
            "edge": ["west", "east", "south", "north"][i],
            "class": "synthetic fallback",
        }
    outside = np.asarray(entry["point"], dtype=float)
    inward = landing - outside
    inward /= np.linalg.norm(inward)
    right = np.array([inward[1], -inward[0]])
    # Boundary pairs must remain exactly on their edge, not offset outside it.
    transverse = (
        np.array([0, 1]) if entry["edge"] in ["east", "west"] else np.array([1, 0])
    )
    if np.dot(transverse, right) < 0:
        transverse = -transverse
    rails = crossings(geometry, {"rail"})
    if len(rails) >= 2:
        pairs = [
            (a, b)
            for a in rails
            for b in rails
            if np.linalg.norm(np.asarray(a["point"]) - np.asarray(b["point"])) >= HALF
        ]
        if not pairs:
            pairs = [(a, b) for a in rails for b in rails if a is not b]
        rail_a, rail_b = min(
            pairs,
            key=lambda ab: float(
                sample(ground, [ab[0]["point"], ab[1]["point"]]).mean()
            ),
        )
        rail_ends = np.array([rail_a["point"], rail_b["point"]])
    else:
        rail_ends = np.array([[-HALF, 1500], [HALF, -1500]], dtype=float)
    positions, spans = {}, []
    original = ground.copy()
    wet_margin = ndimage.binary_dilation(depth > 0.1, iterations=6)

    def alignment(ends, kind, count):
        features = [
            r
            for r in geometry.get("roads", [])
            if r.get("class") in ({"rail"} if kind == "rail" else {"motorway", "trunk"})
        ]
        mask = raster(geometry["sq"], features)
        if not mask.any():
            return ends[0] * (1 - np.linspace(0, 1, count)[:, None]) + ends[
                1
            ] * np.linspace(0, 1, count)[:, None], False
        points = (np.asarray(ends) * [1, -1]) / 16 + 540
        try:
            path = route(mask, points[0], points[1])
        except ValueError:
            return ends[0] * (1 - np.linspace(0, 1, count)[:, None]) + ends[
                1
            ] * np.linspace(0, 1, count)[:, None], False
        xy = (path[:, ::-1] - 540) * [16, -16]
        xy = np.vstack([ends[0], xy, ends[1]])
        arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
        wanted = np.linspace(0, arc[-1], count)
        return np.column_stack(
            [np.interp(wanted, arc, xy[:, axis]) for axis in [0, 1]]
        ), True

    road_xy, road_real = alignment([outside, landing], "road", 57)
    for route_spec in spec["routes"]:
        ids, kind = route_spec["nodes"], route_spec["kind"]
        if kind == "rail":
            xy, follows_osm = alignment(rail_ends, "rail", len(ids))
            max_grade = 0.04
        else:
            side = 1 if kind == "road_in" else -1
            xy = road_xy.copy()
            tangent = np.gradient(xy, axis=0)
            tangent /= np.linalg.norm(tangent, axis=1)[:, None]
            normal = np.column_stack([tangent[:, 1], -tangent[:, 0]])
            xy += normal * side * 24
            xy[0] = outside + transverse * side * 24
            xy[-1] = landing + right * side * 24
            follows_osm = road_real
            if kind == "road_out":
                xy = xy[::-1]
            max_grade = 0.12
        arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
        required = sample(ground + depth, xy) + 12
        # A crest between nodes must clear the deck too. Native lane curves
        # have horizontal end tangents, so both ends clear each segment's crest.
        for i, (a, b) in enumerate(itertools.pairwise(xy)):
            fractions = np.linspace(0, 1, int(np.ceil(np.linalg.norm(b - a) / 8)) + 1)[
                :, None
            ]
            crest = (
                float(sample(ground + depth, a * (1 - fractions) + b * fractions).max())
                + 12
            )
            required[i : i + 2] = np.maximum(required[i : i + 2], crest)
        heights = np.max(
            required[None, :] - max_grade * np.abs(arc[:, None] - arc[None, :]), axis=1
        )
        if heights.max() >= 1023:
            raise ValueError(
                "Terrain leaves insufficient vertical clearance for a template corridor"
            )
        for node, point, height in zip(ids, xy, heights):
            positions[str(node)] = [float(point[0]), float(height), float(point[1])]
        for a, b, ha, hb in zip(xy, xy[1:], heights, heights[1:]):
            xmin, zmin = np.minimum(a, b) - 80
            xmax, zmax = np.maximum(a, b) + 80
            c0, c1 = (
                max(0, int((xmin + HALF) / 16)),
                min(SIZE, int((xmax + HALF) / 16) + 1),
            )
            r0, r1 = (
                max(0, int((HALF - zmax) / 16)),
                min(SIZE, int((HALF - zmin) / 16) + 1),
            )
            yy, xx = np.mgrid[r0:r1, c0:c1]
            grid = np.stack([xx * 16 - HALF, HALF - yy * 16], axis=-1)
            delta = b - a
            fraction = np.clip(
                np.sum((grid - a) * delta, axis=-1) / np.dot(delta, delta), 0, 1
            )
            distance = np.linalg.norm(grid - (a + fraction[..., None] * delta), axis=-1)
            blend = np.clip((80 - distance) / 56, 0, 1)
            blend = blend * blend * (3 - 2 * blend)
            blend[wet_margin[yy, xx]] = 0
            target = ha * (1 - fraction) + hb * fraction - 12
            target = np.clip(target, original[yy, xx] - 3, original[yy, xx] + 3)
            ground[yy, xx] += (target - ground[yy, xx]) * blend
        spans.append(
            {
                "kind": kind,
                "nodes": len(ids),
                "follows_osm": follows_osm,
                "maximum_grade": float(np.max(np.abs(np.diff(heights)) / np.diff(arc))),
                "maximum_deck_height_above_ground_m": float(
                    (heights - sample(ground, xy)).max()
                ),
            }
        )
    return {
        "node_positions": positions,
        "road_entry": entry,
        "rail_real_crossings": len(rails),
        "corridors": spans,
        "max_corridor_cut_m": float(np.maximum(0, original - ground).max()),
        "max_corridor_fill_m": float(np.maximum(0, ground - original).max()),
    }


def prepare(png, geometry, layout, output, banks=None):
    data = json.loads(geometry.read_text())
    spec = json.loads(layout.read_text())
    image = np.asarray(Image.open(png))
    if image.shape != (SIZE, SIZE) or image.min() < 0 or image.max() > 65535:
        raise ValueError("Expected a 1081-square 16-bit heightmap")
    ground = image.astype(float) * 1024 / 65535
    bank_grid = (
        np.fromfile(banks, dtype="<f4").reshape(SIZE, SIZE).astype(float)
        if banks
        else ndimage.maximum_filter(ground, size=7)
    )
    if not np.all(np.isfinite(bank_grid)):
        raise ValueError("Uncarved elevation grid contains non-finite values")
    depth, summary = hydrology(ground, bank_grid, data)
    start = start_area(ground, depth, data)
    if not start["has_water"]:
        # A dry region still needs starting water. This is explicitly constructed
        # infrastructure, never mislabeled as an OSM lake or river.
        x, z = np.asarray(start["landing"]) + [320, 0]
        col, row = int((x + HALF) / 16), int((HALF - z) / 16)
        yy, xx = np.mgrid[:SIZE, :SIZE]
        radius = np.hypot(xx - col, yy - row)
        level = float(ground[row, col] - 0.5)
        pond = radius < 6
        ground[pond] = np.maximum(
            ground[pond] - 3,
            np.minimum(
                ground[pond], level - 2.5 * np.clip((6 - radius[pond]) / 3, 0, 1)
            ),
        )
        depth[pond] = np.maximum(0, level - ground[pond])
        summary["sources"].append(
            {
                "name": "constructed starter reservoir",
                "class": "reservoir",
                "position": [int(x), 0, int(z)],
                "target": level,
                "capacity": 0.06,
            }
        )
        summary["starter_reservoir"] = True
        start["has_water"] = True
    network = fit_networks(ground, depth, data, spec, start)
    summary.update(network)
    summary.update(
        {
            "start_tile": start["index"],
            "start_area": start,
            "map_id": "PL857-" + data["sq"]["slug"],
            "map_name": data["sq"]["name"] + " - Ready to Play",
            "wet_cells": int((depth > 0).sum()),
            "bank_input": "uncarved browser elevations"
            if banks
            else "local maximum estimate",
        }
    )
    output.mkdir(parents=True, exist_ok=True)
    for name, values in [("terrain.u16", ground), ("water.u16", depth)]:
        np.floor(np.flipud(values) * 64 + 0.5).clip(0, 65535).astype("<u2").tofile(
            output / name
        )
    (output / "hydrology.json").write_text(json.dumps(summary, indent=2) + "\n")
    return {
        k: v
        for k, v in summary.items()
        if k not in ["samples", "node_positions", "sources", "rivers"]
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["png", "geometry", "layout", "output"]:
        parser.add_argument(name, type=Path)
    parser.add_argument("--banks", type=Path)
    print(json.dumps(prepare(**vars(parser.parse_args())), indent=2))
