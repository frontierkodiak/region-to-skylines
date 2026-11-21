"""Diagnostics-only enclosed starter storage; no native qualification implied."""

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class ReservoirBasin:
    terrain: np.ndarray
    water: np.ndarray
    source: dict
    receipt: dict


def validate_native_basin(floor_m, encoded_control):
    """Check the radius<6 starter design against an actual encoded control.

    The caller supplies a north-up metre grid, not a rendered terrain image or
    a requested float target. This static check does not establish retention.
    """
    floor = np.asarray(floor_m, dtype=float)
    if (
        floor.ndim != 2
        or not np.isfinite(floor).all()
        or (floor < 0).any()
        or (floor > 65535 / 64).any()
        or not np.equal(floor * 64, np.floor(floor * 64)).all()
    ):
        raise ValueError("Expected a native quantized hydraulic floor in metres")
    target = encoded_control["target_fixed"] / 64
    rate = max(encoded_control["intake_rate"], encoded_control["output_rate"])
    if not 0 < rate <= 65535 or not 0 < target <= 65535 / 64:
        raise ValueError("Expected a positive bounded encoded storage control")
    x, _, z = encoded_control["position"]
    if not np.isfinite([x, z]).all():
        raise ValueError("Nonfinite encoded storage position")
    half_row, half_col = (np.array(floor.shape) - 1) / 2
    yy, xx = np.indices(floor.shape)
    radius_m = 10 + 0.4 * np.sqrt(rate)
    distance = np.hypot((xx - half_col) * 16 - x, (half_row - yy) * 16 - z)
    core = distance <= radius_m
    disk = distance < 6 * 16
    # A clipped source footprint cannot be certified from the available floor.
    edge_distance = min(
        x + half_col * 16,
        half_col * 16 - x,
        z + half_row * 16,
        half_row * 16 - z,
    )
    if edge_distance < 7 * 16 or not core.any():
        raise ValueError("Storage footprint is not fully inside the hydraulic grid")
    if (target - floor[core] < 1).any():
        raise ValueError("Storage footprint lacks one metre of hydraulic depth")
    adjacency = np.ones((3, 3), dtype=bool)
    labels, _ = ndimage.label(floor < target, structure=adjacency)
    components = np.unique(labels[core])
    if len(components) != 1 or components[0] == 0:
        raise ValueError("Storage footprint spans disconnected hydraulic domains")
    basin = labels == components[0]
    if (basin & ~disk).any():
        raise ValueError("Storage hydraulic domain escapes its constructed envelope")
    rim = ndimage.binary_dilation(disk, structure=adjacency) & ~disk
    freeboard = float((floor[rim] - target).min())
    if freeboard < 0.5:
        raise ValueError("Storage hydraulic rim lacks half a metre of freeboard")
    return {
        "qualification": "static actual-control geometry only; NOT native retention",
        "native_target_m": target,
        "source_radius_m": float(radius_m),
        "minimum_source_footprint_depth_m": float((target - floor[core]).min()),
        "minimum_rim_freeboard_m": freeboard,
        "domain_cells": int(basin.sum()),
        "domain_adjacency": 8,
    }


def construct_closed_reservoir(
    terrain, water, candidate_mask, protected_mask, preferred_position
):
    """Search final north-up metre grids, without modifying caller-owned arrays.

    ``water`` is initial depth in metres. Masks constrain the whole basin and
    its untouched rim, not just its center. ``preferred_position`` is world
    (x, z), normally the legacy landing + (320, 0). Grid spacing is 16 m and
    the center vertex is world (0, 0). Modified heights and target are native
    1/64 m values; existing vertices outside excavation remain byte-identical.
    """
    terrain = np.asarray(terrain, dtype=float)
    water = np.asarray(water, dtype=float)
    candidate_mask = np.asarray(candidate_mask, dtype=bool)
    protected_mask = np.asarray(protected_mask, dtype=bool)
    if (
        terrain.ndim != 2
        or any(
            a.shape != terrain.shape for a in (water, candidate_mask, protected_mask)
        )
        or not np.isfinite(terrain).all()
        or not np.isfinite(water).all()
        or (terrain < 0).any()
        or (water < 0).any()
    ):
        raise ValueError("Expected matching finite nonnegative terrain/depth grids")
    if (terrain > 65535 / 64).any():
        raise ValueError("Terrain exceeds native uint16 height range")
    preferred = np.asarray(preferred_position, dtype=float)
    if preferred.shape != (2,) or not np.isfinite(preferred).all():
        raise ValueError("Expected finite preferred world (x, z)")

    yy, xx = np.mgrid[-6:7, -6:7]
    radius = np.hypot(xx, yy)
    disk = radius < 6
    adjacency = np.ones((3, 3), dtype=bool)
    envelope = ndimage.binary_dilation(disk, structure=adjacency)
    ring = envelope & ~disk
    native_rate = round(0.06 * 65535)
    source_radius_m = 10 + 0.4 * np.sqrt(native_rate)
    core = radius * 16 <= source_radius_m

    # Filters evaluate every lattice center once, not every candidate patch.
    available = candidate_mask & ~protected_mask & (water == 0)
    fits = ndimage.minimum_filter(
        available.astype(np.uint8), footprint=envelope, mode="constant", cval=0
    ).astype(bool)
    rim_floor = ndimage.minimum_filter(
        terrain, footprint=ring, mode="constant", cval=-np.inf
    )
    targets = np.floor((rim_floor - 0.5) * 64) / 64
    lowest_legal = np.maximum(0, np.ceil((terrain - 3) * 64) / 64)
    core_floor = ndimage.maximum_filter(
        lowest_legal, footprint=core, mode="constant", cval=np.inf
    )
    fits &= (targets >= 1) & (core_floor <= targets - 1)
    rows, cols = np.nonzero(fits)
    half_row, half_col = (np.array(terrain.shape) - 1) / 2
    distances = ((cols - half_col) * 16 - preferred[0]) ** 2 + (
        (half_row - rows) * 16 - preferred[1]
    ) ** 2
    order = np.lexsort((cols, rows, distances))
    for index in order:
        row, col = int(rows[index]), int(cols[index])
        region = np.s_[row - 6 : row + 7, col - 6 : col + 7]
        before = terrain[region]
        target = float(targets[row, col])
        taper = np.clip(
            (radius - source_radius_m / 16) / (6 - source_radius_m / 16), 0, 1
        )
        desired = target - 1.5 + 2 * taper**2
        carved = before.copy()
        carved[disk] = np.maximum(
            lowest_legal[region][disk],
            np.minimum(
                np.floor(before[disk] * 64) / 64, np.floor(desired[disk] * 64) / 64
            ),
        )
        depths = np.maximum(0, target - carved)
        quantized_rim = np.floor(carved[ring] * 64) / 64
        # Prove the quantized artifact, not only the pre-search bounds.
        if (
            (carved[disk] > before[disk]).any()
            or (before[disk] - carved[disk] > 3).any()
            or (depths[core] < 1).any()
            or (quantized_rim - target < 0.5).any()
        ):
            continue
        connected, _ = ndimage.label(depths > 0, structure=adjacency)
        center_label = connected[6, 6]
        if not center_label or not (connected[core] == center_label).all():
            continue
        if ((connected == center_label) & ~disk).any():
            continue
        output_terrain, output_water = terrain.copy(), water.copy()
        output_terrain[region] = carved
        output_water[region][disk] = depths[disk]
        position = [(col - half_col) * 16, 0, (half_row - row) * 16]
        source = {
            "name": "diagnostic enclosed starter reservoir",
            "class": "reservoir",
            "position": position,
            "target": target,
            "capacity": 0.06,
        }
        receipt = {
            "qualification": "geometric only; NOT native verified",
            "center_row_col": [row, col],
            "source_radius_m": float(source_radius_m),
            "minimum_source_footprint_depth_m": float(depths[core].min()),
            "minimum_rim_freeboard_m": float((quantized_rim - target).min()),
            "maximum_cut_m": float((before - carved).max()),
            "excavated_cells": int((before != carved).sum()),
            "wet_cells": int((depths[disk] > 0).sum()),
            "containment": "untouched full eight-neighbor dilation rim around radius<6 disk",
            "wet_component_adjacency": 8,
            "target_quantum_m": 1 / 64,
            "preferred_distance_m": float(np.sqrt(distances[index])),
        }
        return ReservoirBasin(output_terrain, output_water, source, receipt)
    raise ValueError("No feasible enclosed reservoir within candidate/protected masks")
