"""Terrain-shape interest measures, shared by stock, prepared and live readers.

These are terrain shape, not buildability: every node counts, including wet
ground, so the measure never needs a finished-water mask. Both cores use the
same 1081-square, 16 m, south-first game grids and the game's 1/64 m terrain
unit; `capability-model.js` mirrors this module. The stock survey tool and the
prepared report both import `terrain_interest_metrics`, so a stock observation
and a square's report can never be scored inside two catalogs.
"""

import numpy as np

# Mirrored in capability-model.js STOCK_MEASURES. Strings are asserted equal
# across both cores by the Python/JavaScript parity test.
TERRAIN_INTEREST_MEASURES = {
    "terrain_roughness_percent": {
        "name": "Terrain roughness",
        "unit": "%",
        "kind": "terrain_shape",
        "definition": "mean terrain gradient magnitude at 16 m spacing over all 1081 x 1081 nodes, in percent",
    },
    "central_terrain_diversity_m": {
        "name": "Central height range",
        "unit": "m",
        "kind": "terrain_shape",
        "definition": "90th minus 10th percentile of terrain height over the central 25 tiles' nodes, in metres",
    },
}

_NODE_INDEX = None


def central_node_index():
    """The central 25 tiles' sampled node rows/columns, from the survey's own mask.

    `survey.measure_maps.CENTRAL` marks the central 5 x 5 game tiles on the 512
    resource grid; `terrain_fields` samples each of those cells at its nearest
    16 m node. This is the same predicate, so a central all-terrain measure and
    the existing central land measures share one window.
    """
    global _NODE_INDEX
    if _NODE_INDEX is None:
        from survey.measure_maps import CELL, HN, RES

        tile = np.minimum(8, (np.arange(RES) * 9) // RES)
        keep = np.where((tile >= 2) & (tile <= 6))[0]
        _NODE_INDEX = np.clip(
            np.floor(((keep - 256 + 0.5) * CELL + 8640) / 16 + 0.5).astype(int),
            0,
            HN - 1,
        )
    return _NODE_INDEX


def quantize_terrain_unit(ground):
    """Round to the game's 1/64 m terrain unit, half up, as the writer stores it."""
    return np.floor(np.asarray(ground, dtype=float) * 64.0 + 0.5) / 64.0


def _gradient_percent(ground):
    """Euclidean gradient at 16 m spacing in percent, one-sided at the outer rows.

    Written as explicit slices so the JavaScript mirror reproduces the same
    arithmetic (differences of 1/64 m values divided by a power of two).
    """
    dz = np.empty_like(ground)
    dx = np.empty_like(ground)
    dz[1:-1, :] = (ground[2:, :] - ground[:-2, :]) / 32.0
    dz[0, :] = (ground[1, :] - ground[0, :]) / 16.0
    dz[-1, :] = (ground[-1, :] - ground[-2, :]) / 16.0
    dx[:, 1:-1] = (ground[:, 2:] - ground[:, :-2]) / 32.0
    dx[:, 0] = (ground[:, 1] - ground[:, 0]) / 16.0
    dx[:, -1] = (ground[:, -1] - ground[:, -2]) / 16.0
    return np.sqrt(dx * dx + dz * dz) * 100.0


def terrain_interest_metrics(ground):
    """The two terrain-shape measures on a 1081-square south-first metre grid."""
    from survey.measure_maps import HN

    ground = np.asarray(ground, dtype=float)
    if ground.shape != (HN, HN):
        raise ValueError("Terrain interest measures need a 1081-square terrain grid")
    if not np.isfinite(ground).all():
        raise ValueError("Terrain interest measures need finite terrain heights")
    quantized = quantize_terrain_unit(ground)
    gradient = _gradient_percent(quantized)
    node = central_node_index()
    central = quantized[np.ix_(node, node)]
    return {
        "terrain_roughness_percent": round(float(gradient.mean()), 2),
        "central_terrain_diversity_m": round(
            float(np.percentile(central, 90) - np.percentile(central, 10)), 1
        ),
    }
