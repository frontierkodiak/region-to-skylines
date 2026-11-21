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
