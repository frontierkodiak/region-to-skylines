"""Bounded passive storage on captured lake footprints, never a stream fallback.

No control is added or moved. Open/controlled bodies and infeasible banks are
explicit refusals. The existing starter constructor and its masks are unchanged.
"""

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from maintained_water_inventory import position, source_tag
from region import HALF, SIZE, raster

ADJACENCY = np.ones((3, 3), dtype=bool)
POLICY = "mapped-passive-lake-storage-v1"
INITIAL_DEPTH = 1.5


@dataclass(frozen=True)
class NaturalBasins:
    terrain: np.ndarray
    water: np.ndarray
    masks: dict
    entries: list


def lake_components(geometry):
    masks, entries = {}, []
    union = np.zeros((SIZE, SIZE), bool)
    for index, feature in enumerate(geometry.get("lakes", [])):
        entry = {"feature_id": f"lakes:{index}", "name": feature.get("name", "")}
        try:
            if source_tag(feature, "intermittent") in (True, 1, "1", "yes", "true"):
                entry.update(status="excluded", reason="explicit intermittent")
            elif source_tag(feature, "brunnel") == "tunnel":
                entry.update(status="excluded", reason="explicit underground")
            else:
                mask = raster(geometry["sq"], [feature], polygons=True)
                if mask.any():
                    masks[entry["feature_id"]] = mask
                    union |= mask
                    entry.update(status="mapped")
                else:
                    pts = np.array(
                        [
                            position(geometry["sq"], p)
                            for ring in feature["rings"]
                            for p in ring
                        ]
                    )
                    outside = (
                        pts.ndim == 2
                        and np.isfinite(pts).all()
                        and bool(
                            np.any((pts.min(axis=0) > HALF) | (pts.max(axis=0) < -HALF))
                        )
                    )
                    entry.update(
                        status="outside_square" if outside else "unresolved",
                        reason="source polygon bounding box outside square"
                        if outside
                        else "no supported in-square raster footprint",
                    )
        except (ValueError, KeyError, TypeError) as error:
            entry.update(status="unresolved", reason=str(error))
        entries.append(entry)
    labels, count = ndimage.label(union, ADJACENCY)
    members = {index: [] for index in range(1, count + 1)}
    for name, feature in masks.items():
        for index in np.unique(labels[feature]):
            if index:
                members[int(index)].append(name)
    components = {}
    for index in range(1, count + 1):
        mask = labels == index
        components[f"lake-component:{index}"] = (mask, members[index])
    return components, entries


def protection(geometry, hydro, layout):
    protected = np.zeros((SIZE, SIZE), bool)
    for field in ("rivers", "streams", "undergroundWaterways"):
        protected |= raster(geometry["sq"], geometry.get(field, []))
    for field in ("riverAreas", "oceans"):
        protected |= raster(geometry["sq"], geometry.get(field, []), polygons=True)
    if protected.any():
        protected = ndimage.distance_transform_edt(~protected) * 16 <= 128
    rows, cols = np.indices(protected.shape)
    x, z = cols * 16 - HALF, HALF - rows * 16
    landing = hydro["start_area"]["landing"]
    protected |= np.hypot(x - landing[0], z - landing[1]) <= 128
    for source in hydro["sources"]:
        rate = max(
            source["capacity"], source.get("output_capacity", source["capacity"])
        )
        radius = 10 + 0.4 * np.sqrt(np.floor(rate * 65535 + 0.5)) + 64
        protected |= (
            np.hypot(x - source["position"][0], z - source["position"][2]) <= radius
        )
    image = Image.new("L", (SIZE, SIZE))
    draw = ImageDraw.Draw(image)
    for route in layout["routes"]:
        pts = [hydro["node_positions"][str(n)] for n in route["nodes"]]
        if len(pts) >= 2:
            draw.line(
                [((p[0] + HALF) / 16, (HALF - p[2]) / 16) for p in pts],
                fill=255,
                width=1,
            )
    roads = np.asarray(image) > 0
    if roads.any():
        protected |= ndimage.distance_transform_edt(~roads) * 16 <= 112
    return protected


def validate_basin(floor, mask, target):
    rim = ndimage.binary_dilation(mask, ADJACENCY) & ~mask
    if np.any(mask[[0, -1]]) or np.any(mask[:, [0, -1]]) or not mask.any():
        raise ValueError("Full natural-body rim is not inside the square")
    minimum_depth = float((target - floor[mask]).min())
    freeboard = float((floor[rim] - target).min())
    if minimum_depth < 1:
        raise ValueError("Natural storage lacks one metre of hydraulic depth")
    if freeboard < 0.5:
        raise ValueError(
            "Natural storage lacks half a metre on its full eight-neighbour rim"
        )
    return {
        "minimum_body_depth_m": minimum_depth,
        "minimum_rim_freeboard_m": freeboard,
        "body_cells": int(mask.sum()),
        "rim_cells": int(rim.sum()),
        "adjacency": 8,
    }


def construct(terrain, water, components, protected):
    terrain, water = np.asarray(terrain, float), np.asarray(water, float)
    if (
        terrain.shape != water.shape
        or terrain.shape != protected.shape
        or not np.isfinite(terrain).all()
        or not np.isfinite(water).all()
        or np.any(terrain < 0)
        or np.any(water < 0)
        or not np.equal(terrain * 64, np.floor(terrain * 64)).all()
    ):
        raise ValueError(
            "Expected matching finite, native-quantized floor/depth/mask grids"
        )
    floor, depth = terrain.copy(), water.copy()
    entries, accepted = [], {}
    occupied = np.zeros_like(protected, bool)
    for name, (mask, feature_ids) in components.items():
        entry = {
            "id": name,
            "feature_ids": feature_ids,
            "policy": POLICY,
            "source_controls_added": 0,
        }
        rim = ndimage.binary_dilation(mask, ADJACENCY) & ~mask
        envelope = mask | rim
        try:
            if not mask.any() or np.any(mask[[0, -1]]) or np.any(mask[:, [0, -1]]):
                raise ValueError("Full natural-body rim is not inside the square")
            if np.any(envelope & (protected | occupied)):
                raise ValueError(
                    "Natural body or full rim intersects protected infrastructure/water/control"
                )
            if np.any(water[rim] > 0):
                raise ValueError("Existing water crosses the proposed passive rim")
            target = float(np.floor((terrain[rim].min() - 0.5) * 64) / 64)
            if target < INITIAL_DEPTH or target > 65535 / 64:
                raise ValueError("Natural-body target outside native range")
            proposed = np.minimum(terrain[mask], target - INITIAL_DEPTH)
            maximum_cut = float((terrain[mask] - proposed).max())
            if maximum_cut > 3:
                raise ValueError(
                    f"Closed natural footprint needs {maximum_cut:.6f}m cut; fixed maximum is 3m"
                )
            values = target - proposed
            if np.any(values < water[mask]):
                raise ValueError(
                    "Passive construction would remove existing initial water"
                )
            trial = floor.copy()
            trial[mask] = proposed
            check = validate_basin(trial, mask, target)
            ys, xs = np.nonzero(mask)
            # Geometric anchor, not selected from an initial/native wet result.
            distance = ndimage.distance_transform_edt(mask)
            anchor = int(np.argmax(distance[ys, xs]))
            row, col = int(ys[anchor]), int(xs[anchor])
            floor[mask], depth[mask] = proposed, values
            occupied |= envelope
            accepted[name] = mask
            entry.update(
                status="constructed",
                target_m=target,
                maximum_cut_m=maximum_cut,
                anchor_xz=[col * 16 - HALF, HALF - row * 16],
                static_check=check,
            )
        except ValueError as error:
            entry.update(status="refused", reason=str(error))
        entries.append(entry)
    return NaturalBasins(floor, depth, accepted, entries)


def validate_final(before_floor, before_water, floor, water, masks, entries, protected):
    union = np.zeros_like(protected, bool)
    checks = []
    for entry in entries:
        if entry["status"] != "constructed":
            continue
        mask = masks[entry["id"]]
        rim = ndimage.binary_dilation(mask, ADJACENCY) & ~mask
        if np.any((mask | rim) & protected):
            raise ValueError("Final natural body intersects protected geometry")
        cut = before_floor[mask] - floor[mask]
        if (
            np.any(cut < 0)
            or np.any(cut > 3)
            or not np.array_equal(floor[rim], before_floor[rim])
        ):
            raise ValueError(
                "Final natural body violates no-fill/cut/untouched-rim bounds"
            )
        if not np.array_equal(water[mask], entry["target_m"] - floor[mask]):
            raise ValueError(
                "Final natural initial water no longer matches the authored stage"
            )
        if np.any(water[mask] < before_water[mask]):
            raise ValueError("Final natural construction removed existing water")
        checks.append(
            {"id": entry["id"], **validate_basin(floor, mask, entry["target_m"])}
        )
        union |= mask
    if not np.array_equal(floor[~union], before_floor[~union]) or not np.array_equal(
        water[~union], before_water[~union]
    ):
        raise ValueError(
            "Final natural construction changed cells outside mapped accepted bodies"
        )
    return checks
