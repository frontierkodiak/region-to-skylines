"""Sample ESA WorldCover 2021 (10 m, CC-BY 4.0) onto a region's game grid.

The output is a 1728-square uint8 grid of WorldCover class codes at 10 game
metres, rows north to south, the same frame and rotation as the browser
heightmap (`prepare.pixel`). It is the land-cover input of `resources.py`.

Classes: 10 tree cover, 20 shrubland, 30 grassland, 40 cropland, 50 built-up,
60 bare/sparse vegetation, 70 snow and ice, 80 permanent water, 90 herbaceous
wetland, 95 mangroves, 100 moss and lichen, 0 no data.

The S3 bucket serves byte ranges but no CORS headers, so a browser port needs
a same-origin proxy; this reference reads it directly with GDAL.
"""

import argparse
import gzip
import json
import math
from pathlib import Path

import numpy as np

GRID, STEP, HALF = 1728, 10.0, 8640.0
URL = (
    "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
)
ATTRIBUTION = "ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium"


def tile_name(lat, lon):
    la, lo = 3 * math.floor(lat / 3), 3 * math.floor(lon / 3)
    return (
        f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}"
    )


def lonlat(sq, x, z):
    """Inverse of prepare.pixel for game metres (x east, z north)."""
    a, e2 = 6378137, 0.00669437999014
    w = 1 - e2 * np.sin(np.deg2rad(sq["lat"])) ** 2
    m = a * (1 - e2) / w**1.5
    nc = a / np.sqrt(w) * np.cos(np.deg2rad(sq["lat"]))
    t = np.deg2rad(sq["rotation"])
    u, v = np.asarray(x) * sq["scale"], np.asarray(z) * sq["scale"]
    east = u * np.cos(t) + v * np.sin(t)
    north = -u * np.sin(t) + v * np.cos(t)
    return sq["lon"] + np.rad2deg(east / nc), sq["lat"] + np.rad2deg(north / m)


def sample(sq):
    import rasterio
    from rasterio.windows import from_bounds

    centres = (np.arange(GRID) + 0.5) * STEP - HALF
    x, z = np.meshgrid(centres, centres[::-1])
    lon, lat = lonlat(sq, x, z)
    out = np.zeros((GRID, GRID), dtype=np.uint8)
    tiles = {
        tile_name(la, lo)
        for la in np.linspace(lat.min(), lat.max(), 8)
        for lo in np.linspace(lon.min(), lon.max(), 8)
    }
    read = []
    env = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "AWS_NO_SIGN_REQUEST": "YES"}
    with rasterio.Env(**env):
        for tile in sorted(tiles):
            try:
                src = rasterio.open(URL.format(tile=tile))
            except rasterio.errors.RasterioIOError:
                continue  # Open ocean has no WorldCover tile.
            with src:
                left, bottom, right, top = src.bounds
                inside = (lon >= left) & (lon < right) & (lat > bottom) & (lat <= top)
                if not inside.any():
                    continue
                pad = 2 * src.res[0]
                window = (
                    from_bounds(
                        max(left, lon[inside].min() - pad),
                        max(bottom, lat[inside].min() - pad),
                        min(right, lon[inside].max() + pad),
                        min(top, lat[inside].max() + pad),
                        src.transform,
                    )
                    .round_offsets()
                    .round_lengths()
                )
                block = src.read(1, window=window)
                transform = src.window_transform(window)
                col = np.floor((lon[inside] - transform.c) / transform.a).astype(int)
                row = np.floor((lat[inside] - transform.f) / transform.e).astype(int)
                ok = (
                    (row >= 0)
                    & (row < block.shape[0])
                    & (col >= 0)
                    & (col < block.shape[1])
                )
                values = np.zeros(int(inside.sum()), dtype=np.uint8)
                values[ok] = block[row[ok], col[ok]]
                out[inside] = values
                read.append(tile)
    return out, read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geometry", type=Path, help="browser geometry JSON (.gz ok)")
    parser.add_argument("output", type=Path, help="landcover.u8.gz to write")
    args = parser.parse_args()
    raw = args.geometry.read_bytes()
    geometry = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    grid, tiles = sample(geometry["sq"])
    args.output.write_bytes(gzip.compress(grid.tobytes(), mtime=0))
    classes, counts = np.unique(grid, return_counts=True)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "tiles": tiles,
                "share": {
                    int(c): round(n / grid.size, 4) for c, n in zip(classes, counts)
                },
                "attribution": ATTRIBUTION,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
