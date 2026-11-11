"""Prepare an arbitrary browser export for the fixed-topology CRP writer."""

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage, optimize, signal

from prepare import pixel, route
from surface_water import surface_geometry

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
    Feasible monotone profiles retain the bounded-incision lower envelope.
    Where it would lift water above banks, local stages and extra regulators
    replace the impossible global fit without raising the floodplain.
    """
    geometry, visibility = surface_geometry(geometry)
    sq = geometry["sq"]
    sea = geometry.get("seaLevel")
    surface = np.full_like(ground, sea if sea is not None else 0)
    sources, summaries, samples, short_reaches = [], [], {}, []
    grouped = {}
    for river in geometry.get("rivers", []) + geometry.get("streams", []):
        key = (river.get("name") or "unnamed waterway", river.get("class", "river"))
        grouped.setdefault(key, []).append(river)
    masks = {key: raster(sq, features) for key, features in grouped.items()}
    union = np.zeros_like(ground, dtype=bool)
    for mask in masks.values():
        union |= mask
    major_rivers = np.zeros_like(union)
    for (_, kind), mask in masks.items():
        if kind == "river":
            major_rivers |= mask
    major_distance = (
        ndimage.distance_transform_edt(~major_rivers) * SPACING
        if major_rivers.any()
        else np.full_like(ground, np.inf)
    )
    areas = raster(sq, geometry.get("riverAreas", []), polygons=True)
    underground = raster(sq, geometry.get("undergroundWaterways", []))
    # A visible crossing/body takes precedence over a different underground
    # waterway below it. Otherwise prevent routing/earthworks around a short
    # omitted tunnel gap from recreating that tunnel as a surface canal.
    visible = union | areas | raster(sq, geometry.get("lakes", []), polygons=True)
    forbidden = ndimage.binary_dilation(underground, iterations=2) & ~visible
    tunnel_distance = (
        ndimage.distance_transform_edt(~underground) * SPACING
        if underground.any()
        else np.full_like(ground, np.inf)
    )
    smooth_banks = ndimage.median_filter(banks, size=5)
    original = ground.copy()
    edge = np.zeros_like(union)
    edge[:2] = edge[-2:] = True
    edge[:, :2] = edge[:, -2:] = True
    for (name, kind), mask in sorted(
        masks.items(), key=lambda item: (-int(item[1].sum()), item[0])
    ):
        if mask.sum() < 45:
            short_reaches.append(
                {
                    "name": name,
                    "class": kind,
                    "mapped_vertices": int(mask.sum()),
                    "reason": "below existing 45-vertex modeled-reach minimum",
                }
            )
            continue
        near = ndimage.binary_dilation(mask, iterations=2) & ~forbidden
        labels, count = ndimage.label(near, structure=np.ones((3, 3)))
        others = union & ~mask
        joins = ndimage.binary_dilation(others, iterations=3)
        for component in range(1, count + 1):
            channel = mask & (labels == component)
            if channel.sum() < 45:
                short_reaches.append(
                    {
                        "name": name,
                        "class": kind,
                        "component": component,
                        "mapped_vertices": int(channel.sum()),
                        "reason": "below existing 45-vertex modeled-reach minimum",
                    }
                )
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
            path = route(channel, start, end, ground=ground, forbidden=forbidden)
            y, x = path.T
            if len(path) < 45:
                short_reaches.append(
                    {
                        "name": name,
                        "class": kind,
                        "component": component,
                        "routed_vertices": len(path),
                        "reason": "below existing 45-vertex modeled-reach minimum",
                    }
                )
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
            ceiling = np.maximum(banks[y, x] - 0.25, sea if sea is not None else 0)
            overbank = float((fitted - ceiling).max())
            bank_limited = kind == "river" and overbank > 1 / 64
            unforced_stream = kind == "stream" and overbank > 1 / 64
            if bank_limited:
                fitted = np.minimum(fitted, ceiling)
            line = np.zeros_like(channel)
            line[y, x] = True
            distance, nearest = ndimage.distance_transform_edt(
                ~line, return_indices=True
            )
            line_levels = np.zeros_like(ground)
            line_levels[y, x] = fitted
            local_surface = line_levels[tuple(nearest)]
            desired_bed = local_surface - 3.0 + (distance * SPACING / 32) ** 2 * 3.0
            corridor = (distance <= 3) & ~forbidden
            ground[corridor] = np.maximum(
                original[corridor] - max_lowering,
                np.minimum(ground[corridor], desired_bed[corridor]),
            )
            wet = (
                ((distance <= 4) | (areas & (distance <= 32)))
                & (ground < local_surface)
                & ~forbidden
            )
            initial_surface = (
                np.minimum(local_surface, ground + 0.25)
                if kind == "stream"
                else local_surface
            )
            if bank_limited:
                initial_surface = np.minimum(
                    initial_surface,
                    np.minimum(
                        np.maximum(banks - 0.25, sea if sea is not None else 0),
                        np.maximum(ground + 1.0, sea if sea is not None else 0),
                    ),
                )
            surface[wet] = np.maximum(surface[wet], initial_surface[wet])
            key = f"{name} [{kind}] #{component}"
            samples[key] = [
                [int(px * 16 - HALF), 0, int(HALF - py * 16)]
                for py, px in path[:: max(1, len(path) // 30)]
            ]
            interior = np.flatnonzero(
                (x >= 6) & (x <= SIZE - 7) & (y >= 6) & (y <= SIZE - 7)
            )
            controls = (
                [
                    ("upstream", int(interior[min(2, len(interior) - 1)])),
                    ("downstream", int(interior[max(0, len(interior) - 3)])),
                ]
                if len(interior)
                else []
            )
            if kind == "river" and len(interior):
                # Endpoint-only forcing can leave dry gaps on long reaches.
                # Supply omitted catchment inflow at fixed arc intervals,
                # independently of the verification sample locations.
                spacing = 512 if bank_limited else 2048
                controls[1:1] = [
                    ("interior", int(interior[np.argmin(abs(arc[interior] - at))]))
                    for at in np.arange(spacing, arc[-1] - spacing / 2, spacing)
                ]
                if bank_limited:
                    levels = ndimage.gaussian_filter1d(fitted, 3)
                    allowed = set(map(int, interior))
                    for role, sign in [("crest", 1), ("trough", -1)]:
                        peaks, _ = signal.find_peaks(
                            levels * sign, prominence=0.5, distance=8
                        )
                        controls += [(role, int(i)) for i in peaks if int(i) in allowed]
                    occupied = {i for _, i in controls}
                    bed_peaks, _ = signal.find_peaks(
                        ndimage.gaussian_filter1d(ground[y, x], 1),
                        prominence=0.5,
                        distance=8,
                    )
                    controls += [
                        ("bed_crest", int(i))
                        for i in bed_peaks
                        if int(i) in allowed and int(i) not in occupied
                    ]
                    controls = [
                        (role, i)
                        for i, role in sorted({i: role for role, i in controls}.items())
                    ]
            # A missing continuation in OSM is an open hydraulic boundary, not
            # a closed basin. Natural sources regulate both excess and deficit;
            # a downstream control supplies tailwater and drains blocked ends.
            for role, source_i in controls:
                if sea is not None and fitted[source_i] <= sea + 0.5:
                    continue
                if kind == "stream" and major_distance[y[source_i], x[source_i]] <= 96:
                    # A confluence already has an outlet. A creek regulator
                    # here would draw down the receiving perennial river.
                    continue
                gradient = (fitted[0] - fitted[-1]) / arc[-1]
                capacity = (
                    0.01 if kind == "stream" else 0.8 if gradient <= 0.005 else 0.2
                )
                target = float(fitted[source_i])
                if bank_limited:
                    target = min(target, float(ground[y[source_i], x[source_i]]) + 1.0)
                portal = None
                endpoint = (
                    path[0]
                    if role == "upstream"
                    else path[-1]
                    if role == "downstream"
                    else None
                )
                if endpoint is not None and tunnel_distance[tuple(endpoint)] <= 64:
                    portal = (
                        "surface_outlet_from_tunnel"
                        if role == "upstream"
                        else "surface_inlet_to_tunnel"
                    )
                    if role == "downstream":
                        target = min(
                            target, float(ground[y[source_i], x[source_i]]) + 0.25
                        )
                if kind == "stream":
                    bed = float(ground[y[source_i], x[source_i]])
                    # A creek outlet is not a second spring. Below-center-bed
                    # targets alone do not prevent injection into lower cells
                    # within the native source's radius; output must be zero.
                    target = max(
                        0, min(target, bed + (0.25 if role == "upstream" else -0.25))
                    )
                    capacity = 0.01
                sources.append(
                    {
                        "name": name,
                        "class": kind,
                        "role": role,
                        "position": [
                            int(x[source_i] * 16 - HALF),
                            0,
                            int(HALF - y[source_i] * 16),
                        ],
                        "target": target,
                        "capacity": capacity,
                    }
                )
                if kind == "stream" and role == "downstream":
                    sources[-1]["output_capacity"] = 0
                if unforced_stream:
                    # A shallow mapped creek with an infeasible gravity profile
                    # cannot be kept perennial by pumping water off its valley.
                    # Retain prefill, intake, geometry and every dry probe.
                    sources[-1]["output_capacity"] = 0
                    sources[-1]["unforced_infeasible_stream"] = True
                if bank_limited:
                    sources[-1]["bank_limited"] = True
                if portal:
                    sources[-1]["underground_portal"] = portal
                    if role == "downstream":
                        sources[-1]["output_capacity"] = 0
            summaries.append(
                {
                    "name": name,
                    "class": kind,
                    "length_m": float(arc[-1]),
                    "upstream": list(start),
                    "downstream": list(end),
                    "max_surface_above_uncarved_m": float(
                        (initial_surface[y, x] - banks[y, x]).max()
                    ),
                    "profile_above_uncarved_m": float((fitted - banks[y, x]).max()),
                }
            )
            if bank_limited:
                summaries[-1].update(
                    bank_limited=True,
                    rejected_monotone_overbank_m=overbank,
                    control_spacing_m=512,
                )
            if unforced_stream:
                summaries[-1].update(
                    unforced_infeasible_stream=True,
                    rejected_monotone_overbank_m=overbank,
                )
    lake_mask = raster(sq, geometry.get("lakes", []), polygons=True)
    labels, count = ndimage.label(lake_mask)
    for label, region in enumerate(ndimage.find_objects(labels), 1):
        component = labels[region] == label
        if component.sum() < 8:
            continue
        bed, bank = ground[region][component], banks[region][component]
        # A percentile of lake-interior DEM heights can sit above its outlet.
        # Regulating to that level continuously floods the downstream valley.
        # The lowest actual bank around the polygon bounds the retained level.
        full_component = labels == label
        rim = ndimage.binary_dilation(full_component) & ~full_component
        level = float(np.percentile(bank, 25) - 0.5)
        if rim.any():
            level = min(level, float(np.minimum(banks[rim], ground[rim]).min() - 0.5))
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
        "river_control_spacing_m": 2048,
        "mapped_waterway_coverage": coverage,
        "surface_water_classification": visibility,
        "unmodeled_short_surface_reaches": short_reaches,
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
                        int(water >= 256),
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
        "initial_deep_water_vertices": int(
            (depth[row - 60 : row + 60, col - 60 : col + 60] > 0.5).sum()
        ),
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
            raw_xy = xy.copy()
            fractions = np.linspace(0, 1, len(ids))[:, None]
            for sigma in [2, 4, 8, 16]:
                xy = ndimage.gaussian_filter1d(raw_xy, sigma, axis=0, mode="nearest")
                xy += (rail_ends[0] - xy[0]) * (1 - fractions) + (
                    rail_ends[1] - xy[-1]
                ) * fractions
                xy = np.clip(xy, -HALF, HALF)
                vectors = np.diff(xy, axis=0)
                lengths = np.linalg.norm(vectors, axis=1)
                cosine = np.sum(vectors[:-1] * vectors[1:], axis=1) / (
                    lengths[:-1] * lengths[1:]
                )
                if np.isfinite(cosine).all() and cosine.min() >= np.cos(np.pi / 4):
                    break
            else:
                xy = rail_ends[0] * (1 - fractions) + rail_ends[1] * fractions
                follows_osm = False
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
                "maximum_turn_degrees": float(
                    np.degrees(
                        np.arccos(
                            np.clip(
                                np.sum(
                                    np.diff(xy, axis=0)[:-1] * np.diff(xy, axis=0)[1:],
                                    axis=1,
                                )
                                / (np.diff(arc)[:-1] * np.diff(arc)[1:]),
                                -1,
                                1,
                            )
                        )
                    ).max()
                ),
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


def limit_source_footprints(ground, depth, banks, geometry, summary):
    """Bound local-stage regulators after the final corridor earthworks."""
    limited = [s for s in summary["sources"] if s.get("bank_limited")]
    if not limited:
        return
    sq = geometry["sq"]
    channels = ndimage.binary_dilation(
        raster(sq, geometry.get("rivers", []) + geometry.get("streams", [])),
        iterations=4,
    )
    channels |= depth > 0.1
    for field in ["lakes", "riverAreas"]:
        channels |= raster(sq, geometry.get(field, []), polygons=True)
    ceiling = np.maximum(banks - 0.25, summary["sea_level_m"])
    for source in limited:
        col = round((source["position"][0] + HALF) / SPACING)
        row = round((HALF - source["position"][2]) / SPACING)
        target = np.floor(source["target"] * 64) / 64
        if target <= ground[row, col] + 0.125:
            raise ValueError(
                "Bank-bounded regulator has insufficient local water depth"
            )
        maximum = int(np.floor(source["capacity"] * 65535 + 0.5))
        radius = 10 + 0.4 * np.sqrt(maximum)
        extent = int(np.ceil(radius / SPACING)) + 1
        r0, r1 = max(0, row - extent), min(SIZE, row + extent + 1)
        c0, c1 = max(0, col - extent), min(SIZE, col + extent + 1)
        region = np.s_[r0:r1, c0:c1]
        yy, xx = np.mgrid[r0:r1, c0:c1]
        distance = np.hypot(yy - row, xx - col) * SPACING
        bed, wet_channel = ground[region], channels[region]

        def safe_rate(unsafe):
            if not unsafe.any():
                return maximum
            clearance = float(distance[unsafe].min()) - 0.01
            return min(
                maximum,
                int(np.floor((max(0, clearance - 10) / 0.4) ** 2)),
            )

        intake = (
            maximum
            if source.get("underground_portal") == "surface_inlet_to_tunnel"
            else safe_rate(wet_channel & (bed >= target - 0.125))
        )
        output = min(
            safe_rate((bed < target) & ((ceiling[region] < target) | ~wet_channel)),
            int(
                np.floor(
                    source.get("output_capacity", source["capacity"]) * 65535 + 0.5
                )
            ),
        )
        source.update(
            target=float(target),
            capacity=intake / 65535,
            output_capacity=output / 65535,
        )
    summary["bank_limited_regulators"] = len(limited)


def prepare(png, geometry, layout, output, banks=None):
    data, _ = surface_geometry(json.loads(geometry.read_text()))
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
    limit_source_footprints(ground, depth, bank_grid, data, summary)
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
