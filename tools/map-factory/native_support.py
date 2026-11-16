"""Conservative support for CS1's existing water sampling, not new wetness gates.

The installed game's SampleWaterData interpolates occupied surface heights,
substituting the lowest occupied surface at empty corners. A patch can therefore
report water above an empty, lower corner. Protect those patches too, rather
than assuming only positive-depth vertices matter. Constants below reproduce
the installed sampler (eight units) and harness near-water check (seven).
"""

import numpy as np


def _surfaces(ground, depth):
    occupied = depth > 0
    raw = ground + depth
    minimum = np.min(np.where(occupied, raw, 1_000_000), axis=0)
    return np.where(occupied, raw, minimum), occupied.any(axis=0)


def interpolation_support(ground, depth):
    """All vertices in any patch capable of existing native wet/near support.

    Integer linear interpolation is monotone and commutes with an integer
    translation. If every effective corner's surface-minus-ground is below
    seven, nested interpolation cannot reach either existing water threshold.
    This is a conservative bound, not a renderer reconstruction or flow model.
    The ground array must be the actual hydraulic BlockHeights, not RawHeights.
    Grid orientation does not matter; both arrays must use the same orientation.
    """
    ground = np.asarray(ground, dtype=np.int64)
    depth = np.asarray(depth, dtype=np.int64)
    # The sampler clamps each corner separately outside the square. Include
    # those degenerate edge patches; an inward patch can have a different
    # minimum occupied surface and is not a substitute for a clamped patch.
    ground = np.pad(ground, 1, mode="edge")
    depth = np.pad(depth, 1, mode="edge")
    corners = [np.s_[:-1, :-1], np.s_[1:, :-1], np.s_[:-1, 1:], np.s_[1:, 1:]]
    g = np.stack([ground[c] for c in corners])
    d = np.stack([depth[c] for c in corners])
    surfaces, occupied = _surfaces(g, d)
    patches = occupied & ((surfaces - g).max(axis=0) >= 7)
    result = np.zeros_like(ground, dtype=bool)
    for corner in corners:
        result[corner] |= patches
    return result[1:-1, 1:-1]


def sample_water(ground, depth, positions):
    """Replay installed fixed-point ground/surface/boolean at world positions.

    Ground MUST be native BlockHeights, not RawHeights. Both grids are native
    south-first ushort arrays. Velocity and smooth render
    height are deliberately not reproduced. Compare against actual native
    readbacks before relying on this diagnostic.
    """
    ground = np.asarray(ground, dtype=np.int64)
    depth = np.asarray(depth, dtype=np.int64)
    p = np.asarray(positions, dtype=np.float32)
    cell = np.floor((p + np.float32(8640)) * np.float32(16)).astype(np.int64)
    x, z = cell.T
    x0, x1 = np.clip(x >> 8, 0, 1080), np.clip((x >> 8) + 1, 0, 1080)
    z0, z1 = np.clip(z >> 8, 0, 1080), np.clip((z >> 8) + 1, 0, 1080)
    indices = [(z0, x0), (z1, x0), (z0, x1), (z1, x1)]
    g = np.stack([ground[i] for i in indices])
    d = np.stack([depth[i] for i in indices])
    surfaces, occupied = _surfaces(g, d)

    def interpolate(values):
        a = values[0] + ((values[1] - values[0]) * (z & 255) >> 8)
        b = values[2] + ((values[3] - values[2]) * (z & 255) >> 8)
        return a + ((b - a) * (x & 255) >> 8)

    floor, surface = interpolate(g), interpolate(surfaces)
    wet = occupied & (surface - floor >= 8)
    return floor / 64, np.where(wet, surface / 64, 0), wet
