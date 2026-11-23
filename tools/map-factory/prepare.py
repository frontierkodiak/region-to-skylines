"""Prepare mapped water for play; no installed game files are modified.

Input PNG and OpenMapTiles river geometry must describe the same square.
Output grids run south to north, the native engine's order (PNG runs north down).
"""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage, sparse
from scipy.sparse.csgraph import dijkstra

SIZE = 1081
SPACING = 16


def pixel(sq, lonlat):
    """Use the browser export's local WGS84 radii and clockwise frame."""
    lon, lat = lonlat
    a, e2 = 6378137, 0.00669437999014
    w = 1 - e2 * np.sin(np.deg2rad(sq["lat"])) ** 2
    m = a * (1 - e2) / w**1.5
    nc = a / np.sqrt(w) * np.cos(np.deg2rad(sq["lat"]))
    x = np.deg2rad(lon - sq["lon"]) * nc
    z = np.deg2rad(lat - sq["lat"]) * m
    t = np.deg2rad(sq["rotation"])
    u, v = x * np.cos(t) - z * np.sin(t), x * np.sin(t) + z * np.cos(t)
    return (u / sq["scale"] / SPACING + 540, 540 - v / sq["scale"] / SPACING)


def route(mask, start, end, ground=None, forbidden=None):
    distance = ndimage.distance_transform_edt(~mask)
    corridor = distance < 10
    if forbidden is not None:
        corridor &= ~forbidden
    if not corridor.any():
        raise ValueError("No surface routing corridor remains")
    ids = np.full(mask.shape, -1, dtype=np.int32)
    ids[corridor] = np.arange(corridor.sum())
    ys, xs = np.nonzero(corridor)
    cost = 1 + distance**2
    if ground is not None:
        # Prefer the existing low bed over DEM bridge decks and single-pixel
        # obstructions. Distance still keeps repairs inside the mapped corridor.
        cost += np.maximum(0, ground - ndimage.minimum_filter(ground, size=9)) ** 2
    rows, cols, values = [], [], []
    for dy, dx in [(0, 1), (1, 0), (1, 1), (1, -1)]:
        ny, nx = ys + dy, xs + dx
        valid = (ny >= 0) & (ny < SIZE) & (nx >= 0) & (nx < SIZE)
        src, ny, nx = ids[ys[valid], xs[valid]], ny[valid], nx[valid]
        dst = ids[ny, nx]
        good = dst >= 0
        src, dst, ny, nx = src[good], dst[good], ny[good], nx[good]
        edge = (cost[ys[src], xs[src]] + cost[ny, nx]) * np.hypot(dy, dx) / 2
        rows.extend([src, dst])
        cols.extend([dst, src])
        values.extend([edge, edge])
    graph = sparse.coo_matrix(
        (np.concatenate(values), (np.concatenate(rows), np.concatenate(cols))),
        shape=(len(xs), len(xs)),
    ).tocsr()

    def nearest(point):
        x, y = point
        return np.argmin((xs - x) ** 2 + (ys - y) ** 2)

    source, target = nearest(start), nearest(end)
    distances, previous = dijkstra(graph, indices=source, return_predecessors=True)
    if not np.isfinite(distances[target]):
        raise ValueError(
            "River geometry is disconnected within the 160 m repair corridor"
        )
    path = [target]
    while path[-1] != source:
        path.append(previous[path[-1]])
    return np.array([(ys[i], xs[i]) for i in path[::-1]])


def prepare(png, geometry, output):
    from playable_water import hydrology

    data = json.loads(geometry.read_text())
    ground = np.array(Image.open(png), dtype=float) * 1024 / 65535
    banks = ndimage.maximum_filter(ground, size=7)
    depth, summary = hydrology(ground, banks, data)
    output.mkdir(parents=True, exist_ok=True)
    for filename, values in [("terrain.u16", ground), ("water.u16", depth)]:
        np.floor(np.flipud(values) * 64 + 0.5).clip(0, 65535).astype("<u2").tofile(
            output / filename
        )
    Image.fromarray(np.rint(ground * 65535 / 1024).astype(np.uint16)).save(
        output / "Asheville-hydraulic.png"
    )
    (output / "hydrology.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("png", type=Path)
    parser.add_argument("geometry", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.png, args.geometry, args.output)
