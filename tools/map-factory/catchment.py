"""Map-local D8 drainage; contributing area is not whole-watershed discharge."""

from dataclasses import dataclass
from heapq import heappop, heappush
import math

import numpy as np


@dataclass(frozen=True)
class CatchmentDrainage:
    """Priority-flood drainage forest rooted at every outer-edge cell.

    ``parent`` has the grid shape and stores flattened downstream indices, or -1
    at edge roots. ``order`` contains flattened indices in flood visitation
    order. Every parent precedes its children, including on perfectly flat
    terrain. ``filled_elevation`` is a modeling copy, never a terrain edit.
    """

    area: np.ndarray
    filled_elevation: np.ndarray
    parent: np.ndarray
    order: np.ndarray


def priority_flood_drainage(elevation, spacing=16) -> CatchmentDrainage:
    """Build deterministic drainage and local contributing area in square metres.

    All cells contribute ``spacing**2``. All outer-edge cells are open outlets;
    no off-map catchment is inferred. D8 neighbors are visited in row-major
    order and heap ties use flattened cell indices. A cell chooses its parent
    when first reached from an already visited cell, not by independently
    selecting a downhill neighbor: that construction prevents cycles on flats
    and routes closed depressions over their modeled spill elevation.
    """
    try:
        cell_area = float(spacing) ** 2
        valid_spacing = (
            float(spacing) > 0 and cell_area > 0 and math.isfinite(cell_area)
        )
    except (TypeError, ValueError, OverflowError):
        valid_spacing = False
    if not valid_spacing:
        raise ValueError("spacing must be finite and positive with finite cell area")
    if np.iscomplexobj(elevation):
        raise ValueError("elevation must be a finite real two-dimensional grid")
    try:
        grid = np.asarray(elevation, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            "elevation must be a finite real two-dimensional grid"
        ) from exc
    if grid.ndim != 2 or not grid.size or not np.isfinite(grid).all():
        raise ValueError("elevation must be a nonempty finite two-dimensional grid")

    rows, cols = grid.shape
    size = grid.size
    # Python scalars keep the per-neighbor loop inexpensive in CPython/Pyodide.
    filled = grid.ravel().tolist()
    parents = [-1] * size
    seen = bytearray(size)
    heap = []
    for row in range(rows):
        for col in range(cols):
            if row == 0 or row == rows - 1 or col == 0 or col == cols - 1:
                index = row * cols + col
                seen[index] = 1
                heappush(heap, (filled[index], index))

    order = []
    neighbors = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
    while heap:
        height, index = heappop(heap)
        order.append(index)
        row, col = divmod(index, cols)
        for dr, dc in neighbors:
            nr, nc = row + dr, col + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            neighbor = nr * cols + nc
            if seen[neighbor]:
                continue
            seen[neighbor] = 1
            parents[neighbor] = index
            spill = max(height, filled[neighbor])
            filled[neighbor] = spill
            heappush(heap, (spill, neighbor))

    area = [cell_area] * size
    for index in reversed(order):
        parent = parents[index]
        if parent != -1:
            area[parent] += area[index]
    return CatchmentDrainage(
        area=np.asarray(area).reshape(grid.shape),
        filled_elevation=np.asarray(filled).reshape(grid.shape),
        parent=np.asarray(parents, dtype=np.int64).reshape(grid.shape),
        order=np.asarray(order, dtype=np.int64),
    )


def local_catchment_area(elevation, spacing=16) -> np.ndarray:
    """Return map-local contributing area (m²), without changing elevation."""
    return priority_flood_drainage(elevation, spacing).area
