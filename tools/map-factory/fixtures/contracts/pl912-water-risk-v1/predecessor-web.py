"""Entry points for the website and its CLI, which run this package under Pyodide.

Pyodide has no sockets and no GDAL, so the JavaScript side does every network
read and this module does the arithmetic, exactly as the reference does it:

- Land cover: `landcover_plan` picks the WorldCover tiles `landcover.sample`
  would open; the caller reads each tile's GeoTIFF header and hands it to
  `landcover_windows`, which returns the pixel window rasterio would read;
  the caller reads those windows and `landcover_assemble` indexes them into
  the 1728-square grid, with `landcover.sample`'s own NumPy code. The rasterio
  1.5.2 and affine 3.0.1 arithmetic it needs (`from_bounds`, `round_offsets`,
  `round_lengths`, `windows.transform`) is copied below, operation for operation.
- Deposits: `evidence_url` and `evidence_parse` split `evidence.mrds` around
  its one HTTP request.
- `build` runs `generate.generate` on files the caller wrote.
"""

import gzip
import json
import math
from pathlib import Path

import numpy as np

import evidence
import landcover

_grid = {}


def landcover_plan(sq_json):
    """The WorldCover tiles `landcover.sample` opens for this square, in its order."""
    sq = json.loads(sq_json)
    centres = (np.arange(landcover.GRID) + 0.5) * landcover.STEP - landcover.HALF
    x, z = np.meshgrid(centres, centres[::-1])
    lon, lat = landcover.lonlat(sq, x, z)
    _grid.update(
        lon=lon, lat=lat, out=np.zeros((landcover.GRID, landcover.GRID), dtype=np.uint8)
    )
    tiles = {
        landcover.tile_name(la, lo)
        for la in np.linspace(lat.min(), lat.max(), 8)
        for lo in np.linspace(lon.min(), lon.max(), 8)
    }
    return json.dumps(sorted(tiles))


def _bounds(t, width, height):
    """rasterio DatasetBase.bounds for a north-up transform."""
    a, b, c, d, e, f = t
    return c, f + e * height, c + a * width, f


def _matmul(s, o):
    """affine 3.0.1 Affine.__matmul__ for two transforms (a, b, c, d, e, f)."""
    sa, sb, sc, sd, se, sf = s
    oa, ob, oc, od, oe, of = o
    return (
        sa * oa + sb * od,
        sa * ob + sb * oe,
        sa * oc + sb * of + sc,
        sd * oa + se * od,
        sd * ob + se * oe,
        sd * oc + se * of + sf,
    )


def _from_bounds(left, bottom, right, top, t):
    """rasterio.windows.from_bounds, then round_offsets() and round_lengths()."""
    matrix = np.asarray(list(t) + [0.0, 0.0, 1.0], dtype="float64").reshape(3, 3)
    xs, ys = (
        np.asarray([left, right, right, left]),
        np.asarray([top, top, bottom, bottom]),
    )
    bi = np.broadcast(xs, ys)
    inputs = np.empty((3, bi.size))
    inputs[0] = bi.iters[0]
    inputs[1] = bi.iters[1]
    inputs[2] = 1
    cols, rows = np.linalg.solve(matrix, inputs)[:2]
    rows, cols = np.array(list(map(float, rows))), np.array(list(map(float, cols)))
    row_start, row_stop, col_start, col_stop = (
        min(rows),
        max(rows),
        min(cols),
        max(cols),
    )
    width, height = max(col_stop - col_start, 0.0), max(row_stop - row_start, 0.0)
    col_off, row_off = math.floor(col_start + 0.1), math.floor(row_start + 0.1)
    return col_off, row_off, math.floor(width + 0.5), math.floor(height + 0.5)


def landcover_windows(headers_json):
    """For each tile header {tile, transform: [a, b, c, d, e, f], width, height}
    (or {tile, missing: true}), the window to read: [col_off, row_off, width, height]."""
    lon, lat = _grid["lon"], _grid["lat"]
    result = []
    for h in json.loads(headers_json):
        if h.get("missing"):
            result.append(None)
            continue
        t = tuple(h["transform"])
        left, bottom, right, top = _bounds(t, h["width"], h["height"])
        inside = (lon >= left) & (lon < right) & (lat > bottom) & (lat <= top)
        if not inside.any():
            result.append(None)
            continue
        pad = 2 * t[0]
        result.append(
            _from_bounds(
                max(left, lon[inside].min() - pad),
                max(bottom, lat[inside].min() - pad),
                min(right, lon[inside].max() + pad),
                min(top, lat[inside].max() + pad),
                t,
            )
        )
    return json.dumps(result)


def landcover_add(header_json, window_json, block_path):
    """Index one tile's window (raw uint8 rows in a file) into the grid, as landcover.sample does."""
    h, (col_off, row_off, width, height) = (
        json.loads(header_json),
        json.loads(window_json),
    )
    lon, lat, out = _grid["lon"], _grid["lat"], _grid["out"]
    t = tuple(h["transform"])
    left, bottom, right, top = _bounds(t, h["width"], h["height"])
    inside = (lon >= left) & (lon < right) & (lat > bottom) & (lat <= top)
    block = np.fromfile(block_path, dtype=np.uint8).reshape(height, width)
    x, y = (
        col_off * t[0] + row_off * t[1] + t[2],
        col_off * t[3] + row_off * t[4] + t[5],
    )
    window_transform = _matmul((1.0, 0.0, x - t[2], 0.0, 1.0, y - t[5]), t)
    col = np.floor((lon[inside] - window_transform[2]) / window_transform[0]).astype(
        int
    )
    row = np.floor((lat[inside] - window_transform[5]) / window_transform[4]).astype(
        int
    )
    ok = (row >= 0) & (row < block.shape[0]) & (col >= 0) & (col < block.shape[1])
    values = np.zeros(int(inside.sum()), dtype=np.uint8)
    values[ok] = block[row[ok], col[ok]]
    out[inside] = values


def landcover_result(path):
    """Write the grid as landcover.py's gzip output; returns its class histogram."""
    out = _grid["out"]
    Path(path).write_bytes(gzip.compress(out.tobytes(), mtime=0))
    return json.dumps(
        {int(k): int(v) for k, v in zip(*np.unique(out, return_counts=True))}
    )


def evidence_url(sq_json):
    s, w, n, e = evidence.bbox(json.loads(sq_json))
    return evidence.MRDS.format(s=s, w=w, n=n, e=e)


def evidence_parse(sq_json, xml_path, path):
    """evidence.mrds after its request, written as evidence.py's output."""
    found = evidence.parse(json.loads(sq_json), Path(xml_path).read_bytes())
    Path(path).write_text(
        json.dumps(
            {"evidence": found, "sources": ["USGS MRDS (public domain)"]}, indent=2
        )
        + "\n"
    )
    return len(found)


def build(work, landcover_path=None, evidence_path=None):
    """generate.generate on {work}/input.png, geometry.json and banks.f32, with the
    reference's default resource knobs; returns the map file's path and receipt."""
    from generate import generate
    from resources import Knobs

    work = Path(work)
    receipt = generate(
        work / "input.png",
        work / "geometry.json",
        work / "out",
        banks=work / "banks.f32",
        landcover=Path(landcover_path) if landcover_path else None,
        evidence=Path(evidence_path) if evidence_path else None,
        knobs=Knobs(trees=180_000, resources="balanced", fertile=1.0),
    )
    crp = work / "out" / (receipt["preparation"]["map_id"] + ".crp")
    return json.dumps(
        {
            "crp": str(crp),
            "map_name": receipt["preparation"]["map_name"],
            "receipt": receipt,
        },
        default=str,
    )
