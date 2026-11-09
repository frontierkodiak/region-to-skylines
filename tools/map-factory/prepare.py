"""Prepare a bounded Asheville hydrology fixture; no game files are modified.

Input PNG and OpenMapTiles river geometry must describe the same square.
Output grids run south to north, the native engine's order (PNG runs north down).
"""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
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


def route(mask, start, end):
    distance = ndimage.distance_transform_edt(~mask)
    corridor = distance < 10
    ids = np.full(mask.shape, -1, dtype=np.int32)
    ids[corridor] = np.arange(corridor.sum())
    ys, xs = np.nonzero(corridor)
    cost = 1 + distance**2
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
    data = json.loads(geometry.read_text())
    ground = np.array(Image.open(png), dtype=float) * 1024 / 65535
    original = ground.copy()
    surface = np.zeros_like(ground)
    samples = {}
    sources = []
    main_path = None
    for name, start, end in [
        ("French Broad River", (321, 1080), (269, 0)),
        ("Swannanoa River", (1080, 376), (451, 508)),
    ]:
        image = Image.new("L", (SIZE, SIZE))
        draw = ImageDraw.Draw(image)
        for river in data["rivers"]:
            if river["name"] == name:
                draw.line(
                    [pixel(data["sq"], p) for p in river["pts"]], fill=255, width=2
                )
        mask = np.array(image) > 0
        if main_path is not None:
            # The tributary joins the nearest main-river pixel to its mapped west end.
            coords = np.argwhere(mask)
            left = coords[np.argmin(coords[:, 1])]
            end_yx = main_path[np.argmin(((main_path - left) ** 2).sum(axis=1))]
            end = end_yx[::-1]
            draw.line([tuple(left[::-1]), tuple(end)], fill=255, width=2)
            mask = np.array(image) > 0
        path = route(mask, start, end)
        y, x = path.T
        bed = ground[y, x]
        wanted = ndimage.gaussian_filter1d(ndimage.median_filter(bed, size=13), 5) + 3.5
        arc = np.r_[0, np.cumsum(np.hypot(np.diff(x), np.diff(y)) * SPACING)]
        level = np.minimum.accumulate(wanted + arc * 0.0002) - arc * 0.0002
        if main_path is not None:
            target = surface[y[-1], x[-1]]
            level = np.maximum(level, target + (arc[-1] - arc) * 0.0002)
        path_mask = np.zeros_like(mask)
        path_mask[y, x] = True
        dist, indices = ndimage.distance_transform_edt(~path_mask, return_indices=True)
        indexed_level = np.zeros_like(ground)
        indexed_level[y, x] = level
        near_level = indexed_level[tuple(indices)]
        # Keep a 3.5 m thalweg with smoothly rising banks. Only lower terrain.
        carve = near_level - 3.5 + (dist * SPACING / 32) ** 2 * 3.5
        corridor = dist <= 4
        ground[corridor] = np.minimum(ground[corridor], carve[corridor])
        wet = (dist <= 7) & (ground < near_level) & (near_level - ground < 18)
        surface[wet] = np.maximum(surface[wet], near_level[wet])
        sources.append(
            {
                "name": name,
                "position": [float(x[8] * 16 - 8640), 0, float(8640 - y[8] * 16)],
                "target": float(level[8]),
                "capacity": 0.2,
            }
        )
        samples[name] = [
            [int(px * 16 - 8640), 0, int(8640 - py * 16)]
            for py, px in path[:: max(1, len(path) // 30)]
        ]
        if main_path is None:
            main_path = path
    depth = np.maximum(0, surface - ground)
    output.mkdir(parents=True, exist_ok=True)
    for filename, values in [("terrain.u16", ground), ("water.u16", depth)]:
        np.rint(np.flipud(values) * 64).clip(0, 65535).astype("<u2").tofile(
            output / filename
        )
    Image.fromarray(np.rint(ground * 65535 / 1024).astype(np.uint16)).save(
        output / "Asheville-hydraulic.png"
    )
    summary = {
        "input": str(png),
        "geometry": str(geometry),
        "sources": sources,
        "samples": samples,
        "wet_cells": int((depth > 0.1).sum()),
        "lowered_cells": int((original - ground > 0.1).sum()),
        "max_lowering_m": float((original - ground).max()),
        "mean_lowering_changed_m": float(
            (original - ground)[original - ground > 0.1].mean()
        ),
    }
    (output / "hydrology.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "samples"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("png", type=Path)
    parser.add_argument("geometry", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.png, args.geometry, args.output)
