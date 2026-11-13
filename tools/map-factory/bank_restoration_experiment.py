"""Rejected PL-912 bank-restoration arm; never called by default generation.

Native-tested full pipeline: debf9abe9874764183d54abd37fbc0806cfe9671.
This vertex-only support model failed continuous native wet-bed preservation.
See BANK_RESTORATION.md; retained for reproduction, not promotion.
"""

import numpy as np

from region import SIZE, SPACING, raster
from surface_water import surface_geometry


def restore_unsupported_banks(ground, depth, banks, geometry, summary):
    """Restore dry excavation, never the modeled wet floor or source headroom.

    The input heightmap already contains buffered browser incision. Its dry
    shoulders have no support from the feasible stage computed by hydrology.
    The uncarved DEM supplies their elevation, not a guessed channel width.
    Native observations are deliberately not inputs to this rule.
    """
    geometry, _ = surface_geometry(geometry)
    sq = geometry["sq"]
    supported = (depth > 0) | raster(
        sq, geometry.get("rivers", []) + geometry.get("streams", [])
    )
    for field in ["riverAreas", "lakes"]:
        supported |= raster(sq, geometry.get(field, []), polygons=True)
    # A source acts on an area, not only its centre vertex. Retain every
    # below-target bed cell in that existing physical footprint, including
    # unseeded cells; raising these was the rejected width experiment's bug.
    for source in summary["sources"]:
        x, _, z = source["position"]
        col, row = round(540 + x / SPACING), round(540 - z / SPACING)
        rate = max(source["capacity"], source.get("output_capacity", 0))
        radius = 10 + 0.4 * np.sqrt(np.floor(rate * 65535 + 0.5))
        extent = int(np.ceil(radius / SPACING))
        r0, r1 = max(0, row - extent), min(SIZE, row + extent + 1)
        c0, c1 = max(0, col - extent), min(SIZE, col + extent + 1)
        yy, xx = np.mgrid[r0:r1, c0:c1]
        region = np.s_[r0:r1, c0:c1]
        supported[region] |= (np.hypot(yy - row, xx - col) * SPACING <= radius) & (
            np.floor(ground[region] * 64 + 0.5) <= np.ceil(source["target"] * 64)
        )
        supported[row, col] = True
    # One native height quantum separates actual excavation from PNG rounding.
    restored = ~supported & (banks - ground > 1 / 64)
    delta = banks[restored] - ground[restored]
    ground[restored] = banks[restored]
    summary["bank_restoration"] = {
        "policy": "dry excavated margins outside modeled wet floor, visible geometry and source headroom",
        "restored_cells": int(restored.sum()),
        "max_raise_m": float(delta.max()) if len(delta) else 0,
        "wet_floor_changed_cells": 0,
        "source_headroom_changed_cells": 0,
    }
