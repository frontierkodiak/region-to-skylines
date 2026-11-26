"""Sparse, deep, cut-only water authoring trial; not a calibrated flow model.

Dimensions/settings are an engineering trial informed by saved stock data.
Native reference outcomes calibrate the checks before this proposal is run.
Shipping and original-stock reference packages are separate and unchanged.
"""

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from catchment import local_catchment_area
from prepare import pixel
from surface_water import surface_geometry

SIZE, HALF, SPACING = 1081, 8640, 16


@dataclass(frozen=True)
class Design:
    river_depth_m: float
    river_width_m: float
    lake_depth_m: float
    bank_clearance_m: float
    minimum_lake_nodes: int
    river_setting: float
    lake_setting: float
    minor_river_width_m: float = 64
    minor_river_depth_m: float = 16
    minor_river_setting: float = 655 / 65535


DEFAULT_DESIGN = Design(
    river_depth_m=40,
    river_width_m=192,
    lake_depth_m=40,
    bank_clearance_m=2,
    minimum_lake_nodes=54,
    river_setting=32767 / 65535,
    lake_setting=32767 / 65535,
)


def raster(square, features, polygons=False):
    image = Image.new("L", (SIZE, SIZE))
    draw = ImageDraw.Draw(image)
    for feature in features:
        if polygons:
            layer = Image.new("L", image.size)
            painter = ImageDraw.Draw(layer)
            for i, ring in enumerate(feature["rings"]):
                if len(ring) >= 3:
                    painter.polygon(
                        [pixel(square, p) for p in ring], fill=0 if i else 1
                    )
            image = Image.fromarray(np.maximum(np.asarray(image), np.asarray(layer)))
        elif len(feature["pts"]) >= 2:
            draw.line([pixel(square, p) for p in feature["pts"]], fill=1, width=1)
    return np.asarray(image) > 0


def cut_water(ground, footprint, stage, depth, taper):
    """Carve only inside the declared footprint; never raise a bank or bed."""
    desired = np.maximum(0, stage - depth * taper)
    ground[footprint] = np.minimum(ground[footprint], desired[footprint])


def inlet_settings(catchment_km2, broad_inlets, design):
    """Share one network's game-setting budget; splitting feeds adds no supply.

    These are serialized settings, not discharge units. Integer allocation
    avoids a per-head minimum silently multiplying the network budget.
    """
    count = len(broad_inlets)
    if not count:
        return [], 0
    budget = int(
        np.floor(
            np.clip(
                design.river_setting * np.sqrt(max(catchment_km2, 1) / 75),
                0.01,
                design.river_setting,
            )
            * 65535
            + 0.5
        )
    )
    if count > budget:
        raise ValueError(
            "Network budget cannot give every retained inlet a positive setting"
        )
    quotient, remainder = divmod(budget, count)
    minor_cap = int(np.floor(design.minor_river_setting * 65535 + 0.5))
    settings = [
        min(quotient + (i < remainder), 65535 if broad else minor_cap) / 65535
        for i, broad in enumerate(broad_inlets)
    ]
    return settings, budget / 65535


def hydrology(ground, banks, geometry, design):
    if ground.shape != (SIZE, SIZE) or banks.shape != ground.shape:
        raise ValueError("Expected complete 1081-square game-metre terrain")
    if not np.isfinite(ground).all() or not np.isfinite(banks).all():
        raise ValueError("Nonfinite terrain")
    geometry, classification = surface_geometry(geometry)
    square = geometry["sq"]
    original = ground.copy()
    all_streams = raster(square, geometry.get("streams", []))
    line = raster(
        square,
        [
            feature
            for field in ["rivers", "streams"]
            for feature in geometry.get(field, [])
            if feature.get("intermittent") not in (True, 1, "yes", "true")
        ],
    )
    ocean = raster(square, geometry.get("oceans", []), True)
    river_area = raster(square, geometry.get("riverAreas", []), True)
    lakes = raster(square, geometry.get("lakes", []), True)
    sea = geometry.get("seaLevel")
    stage = np.zeros_like(ground)
    footprint = np.zeros_like(line)
    river = np.zeros_like(line)
    broad_channel = np.zeros_like(line)
    areas = local_catchment_area(banks) if line.any() else np.zeros_like(ground)

    if line.any():
        distance, nearest = ndimage.distance_transform_edt(~line, return_indices=True)
        distance *= SPACING
        radius = design.river_width_m / 2
        # A mapped river line does not establish a broad river. In particular,
        # do not turn every small side channel into the main river section.
        broad_line = line & ndimage.binary_dilation(river_area, iterations=2)
        broad_distance = (
            ndimage.distance_transform_edt(~broad_line) * SPACING
            if broad_line.any()
            else np.full_like(ground, np.inf)
        )
        broad_channel = broad_distance < radius
        minor_radius = design.minor_river_width_m / 2
        river = (
            (distance < minor_radius) | broad_channel | (river_area & (distance < 512))
        )
        # Sample banks outside the physical channel, not a running downstream
        # minimum or an artificial levee. Smooth only the source-line signal.
        rim = ndimage.binary_dilation(river, np.ones((3, 3))) & ~(
            river | river_area | lakes | ocean
        )
        bank_values = np.where(rim, banks, np.inf)
        broad_cap = ndimage.minimum_filter(
            bank_values, size=int(np.ceil(radius / SPACING)) * 2 + 5
        )
        minor_cap = ndimage.minimum_filter(
            bank_values, size=int(np.ceil(minor_radius / SPACING)) * 2 + 5
        )
        cap = np.where(broad_channel | river_area, broad_cap, minor_cap)
        seed = np.minimum(
            banks - design.bank_clearance_m, cap - design.bank_clearance_m
        )
        seed = np.where(np.isfinite(seed), seed, banks - design.bank_clearance_m)
        weight = ndimage.gaussian_filter(line.astype(float), 2)
        numerator = ndimage.gaussian_filter(np.where(line, seed, 0), 2)
        smoothed = np.divide(numerator, weight, out=seed.copy(), where=weight > 0)
        seed = np.maximum(0, np.minimum(smoothed, cap - design.bank_clearance_m))
        stage[river] = seed[tuple(nearest)][river]
        taper = (design.minor_river_depth_m / design.river_depth_m) * np.clip(
            1 - (distance / minor_radius) ** 2, 0, 1
        )
        taper = np.maximum(taper, np.clip(1 - (broad_distance / radius) ** 2, 0, 1))
        # Captured broad river areas keep deep interior water rather than a
        # one-cell thalweg through an otherwise dry mapped body.
        area_distance = ndimage.distance_transform_edt(river_area) * SPACING
        taper = np.maximum(taper, np.clip(area_distance / 48, 0, 1))
        cut_water(ground, river, stage, design.river_depth_m, taper)
        footprint |= river

    lake_labels, lake_count = ndimage.label(lakes, np.ones((3, 3)))
    lake_records = []
    for identity, region in enumerate(ndimage.find_objects(lake_labels), 1):
        body = lake_labels == identity
        count = int(body.sum())
        if count < design.minimum_lake_nodes:
            lake_records.append(
                {
                    "component": identity,
                    "nodes": count,
                    "construction": "small mapped body left as ground/marsh; no engineered pool",
                }
            )
            continue
        rim = ndimage.binary_dilation(body) & ~body
        level = (
            max(0.0, float(banks[rim].min()) - design.bank_clearance_m)
            if rim.any()
            else 0.0
        )
        joined = body & river
        if joined.any():
            level = min(level, float(stage[joined].min()))
        stage[body] = level
        inside = ndimage.distance_transform_edt(body) * SPACING
        cut_water(ground, body, stage, design.lake_depth_m, np.clip(inside / 48, 0, 1))
        footprint |= body
        lake_records.append(
            {
                "component": identity,
                "nodes": count,
                "construction": "cut-only lake",
                "surface_m": level,
            }
        )

    if sea is not None and ocean.any():
        stage[ocean] = sea
        inside = ndimage.distance_transform_edt(ocean) * SPACING
        cut_water(
            ground, ocean, stage, design.lake_depth_m, np.clip(inside / 192, 0, 1)
        )
        footprint |= ocean
    depth = np.where(footprint, np.maximum(0, stage - ground), 0)
    labels, count = ndimage.label(depth > 0.1, np.ones((3, 3)))
    edge = np.zeros_like(line)
    edge[[0, -1], :] = True
    edge[:, [0, -1]] = True
    sources, ports, samples = [], [], {}
    receiving_levels = []
    rr, cc = np.indices(ground.shape)
    edge_distance = np.minimum.reduce([rr, cc, SIZE - 1 - rr, SIZE - 1 - cc]) * SPACING
    neighbours = np.ones((3, 3), dtype=np.uint8)
    neighbours[1, 1] = 0
    endpoints = line & (ndimage.convolve(line.astype(np.uint8), neighbours) == 1)

    def source(row, col, setting, role, component):
        x, z = col * SPACING - HALF, HALF - row * SPACING
        sources.append(
            {
                "name": f"stock-style {role} {component}",
                "class": "river" if role == "inlet" else "lake",
                "role": role,
                "position": [int(x), 0, int(z)],
                "target": float(stage[row, col]),
                "capacity": float(setting),
                "output_capacity": float(setting),
            }
        )

    for component, region in enumerate(ndimage.find_objects(labels), 1):
        body = labels == component
        river_nodes = body & line
        if river_nodes.any():
            boundary = river_nodes & edge
            port_labels, nports = ndimage.label(boundary, np.ones((3, 3)))
            candidates = []
            for port in range(1, nports + 1):
                rows, cols = np.nonzero(port_labels == port)
                index = int(np.argmin(stage[rows, cols]))
                candidates.append((int(rows[index]), int(cols[index])))
            receiving_ocean = bool((body & ocean).any())
            receiving_edge = bool((body & edge).any())
            if not receiving_edge and not receiving_ocean:
                ports.append(
                    {
                        "component": component,
                        "role": "unresolved receiving outlet; no river source added",
                        "river_nodes": int(river_nodes.sum()),
                    }
                )
                continue
            if receiving_edge:
                receiving_levels.append(float(stage[body & edge].min()))
            # This is an engineered direction, not a geographic flow inference.
            outlet = (
                min(candidates, key=lambda rc: (stage[rc], rc)) if candidates else None
            )
            inlets = [rc for rc in candidates if rc != outlet]
            inboard = []
            for row, col in inlets:
                nearby = (
                    river_nodes
                    & (edge_distance >= 128)
                    & ((rr - row) ** 2 + (cc - col) ** 2 <= 32**2)
                )
                ys, xs = np.nonzero(nearby)
                if len(ys):
                    i = int(np.argmin((ys - row) ** 2 + (xs - col) ** 2))
                    inboard.append((int(ys[i]), int(xs[i])))
            inland_heads = []
            ys, xs = np.nonzero(
                river_nodes & endpoints & (edge_distance >= 128) & ~ocean & ~lakes
            )
            for row, col in zip(ys, xs):
                adjacent = [
                    (row + dr, col + dc)
                    for dr in [-1, 0, 1]
                    for dc in [-1, 0, 1]
                    if (dr or dc) and line[row + dr, col + dc]
                ]
                # This selects an engineered feed by the authored stage slope;
                # it does not establish a geographic spring or flow direction.
                if stage[row, col] >= stage[adjacent[0]]:
                    inland_heads.append((int(row), int(col)))
            inlets = list(dict.fromkeys(inboard + inland_heads))
            if not inlets:
                rows, cols = np.nonzero(river_nodes & (edge_distance >= 128))
                if not len(rows):
                    ports.append(
                        {
                            "component": component,
                            "role": "no inboard river source location; source not added",
                        }
                    )
                    continue
                index = int(np.argmax(stage[rows, cols]))
                inlets = [(int(rows[index]), int(cols[index]))]
            catchment_km2 = float(areas[river_nodes].max() / 1e6)
            settings, budget = inlet_settings(
                catchment_km2,
                [bool(broad_channel[row, col]) for row, col in inlets],
                design,
            )
            for (row, col), actual in zip(inlets, settings):
                # Keep the source on the channel; no local circular source pool.
                source(row, col, actual, "inlet", component)
            ports.append(
                {
                    "component": component,
                    "role": "edge/sea receiving boundary",
                    "outlet_source_row_col": list(outlet) if outlet else None,
                    "inlet_source_row_cols": [list(rc) for rc in inlets],
                    "inland_head_source_row_cols": [list(rc) for rc in inland_heads],
                    "map_local_catchment_km2": catchment_km2,
                    "inlet_settings": settings,
                    "inlet_setting_budget": budget,
                    "inlet_setting_sum": sum(settings),
                    "off_map_catchment": "unknown",
                }
            )
        elif not (body & ocean).any() and (body & lakes).any():
            distance = ndimage.distance_transform_edt(body)
            row, col = np.unravel_index(np.argmax(distance), body.shape)
            source(int(row), int(col), design.lake_setting, "lake-level", component)

    for field in ["rivers", "streams"]:
        for index, feature in enumerate(geometry.get(field, [])):
            coords = [pixel(square, p) for p in feature["pts"]]
            samples[f"{feature.get('name') or 'unnamed'} [{field}] #{index}"] = [
                [float(x * 16 - HALF), 0, float(HALF - y * 16)]
                for x, y in coords
                if 0 <= x < SIZE and 0 <= y < SIZE
            ]
    assert np.all(ground <= original + 1e-9), "Water authoring must not raise terrain"
    assert np.array_equal(ground[~footprint], original[~footprint])
    return depth, {
        "sources": sources,
        "samples": samples,
        "rivers": [],
        "sea_level_m": float(
            sea if sea is not None else min(receiving_levels, default=0)
        ),
        "receiving_stage_policy": "captured coast level, otherwise lowest constructed river-edge stage; not geographic sea or calibrated outlet capacity",
        "surface_water_classification": classification,
        "construction": "stock-style cut-only trial",
        "design": vars(design),
        "ports": ports,
        "lake_components": lake_records,
        "water_max_cut_m": float((original - ground).max()),
        "water_max_raise_m": 0,
        "water_changed_nodes": int((original != ground).sum()),
        "mapped_stream_nodes_without_initial_water": int(
            (all_streams & (depth <= 0.1)).sum()
        ),
        "mapped_lake_components": lake_count,
        "wet_components": count,
        "unmodeled_short_surface_reaches": [],
    }
