"""Sample Meta/WRI CHMv2 top-of-canopy heights on a rotated real-world square.

This is area-sampled canopy structure, not a distribution of individual tree
heights. Coarse reads use the provider's COG overviews (aggregation unspecified)
and nearest-cell lookup. Unknown/cloud-masked pixels remain NaN; zero is a real
height. No older dataset is silently substituted.

Source and CC BY 4.0 attribution:
https://registry.opendata.aws/dataforgood-fb-forestsv2/
Format, cloud mask, observation-date metadata and view-angle limitations:
https://github.com/facebookresearch/dinov3/blob/main/notebooks/chmv2_dataset_exploration.ipynb
"""

import argparse
import gzip
import hashlib
import json
import math
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from landcover import lonlat

VERSION = "meta-wri-chmv2-dinov3-global-ml3"
SAMPLER_VERSION = 1
BASE_URL = (
    "https://dataforgood-fb-data.s3.us-east-1.amazonaws.com/"
    "forests/v2/global/dinov3_global_chm_v2_ml3"
)
SOURCE_URL = "https://registry.opendata.aws/dataforgood-fb-forestsv2/"
ATTRIBUTION = (
    "Meta and World Resources Institute (WRI), 2026, Version 2 High Resolution "
    "Canopy Height Maps (CHMv2); source imagery for CHM © 2016 Vantor. "
    "CC BY 4.0."
)
HALF_GAME_M = 8640.0
MERCATOR_LIMIT = 85.0511287798066


def quadkey(x, y):
    """Name a zoom-10 Web Mercator tile, retaining leading zeroes."""
    return "".join(str(((x >> i) & 1) + 2 * ((y >> i) & 1)) for i in range(9, -1, -1))


def _tile_ids(lon, lat):
    x = np.floor((lon + 180) / 360 * 1024).astype(np.int32)
    y = np.floor((1 - np.arcsinh(np.tan(np.deg2rad(lat))) / np.pi) / 2 * 1024).astype(
        np.int32
    )
    return np.clip(y, 0, 1023) * 1024 + np.clip(x, 0, 1023)


def _sample_dataset(src, lon, lat):
    """Read only the required window, respecting CRS, affine and validity mask."""
    from rasterio.warp import transform
    from rasterio.windows import Window

    x, y = transform("EPSG:4326", src.crs, lon.tolist(), lat.tolist())
    cols, rows = (~src.transform) @ (np.asarray(x), np.asarray(y))
    cols, rows = np.floor(cols).astype(int), np.floor(rows).astype(int)
    inside = (cols >= 0) & (cols < src.width) & (rows >= 0) & (rows < src.height)
    values = np.full(lon.shape, np.nan, np.float32)
    if not inside.any():
        return values, None
    left, right = int(cols[inside].min()), int(cols[inside].max()) + 1
    top, bottom = int(rows[inside].min()), int(rows[inside].max()) + 1
    window = Window(left, top, right - left, bottom - top)
    block = src.read(1, window=window, masked=True).astype(np.float32).filled(np.nan)
    # CHMv2's TIFF nodata metadata can be unset. Its internal cloud mask is
    # authoritative; 255 is also excluded, never converted to zero metres.
    block[block == 255] = np.nan
    values[inside] = block[rows[inside] - top, cols[inside] - left]
    return values, [left, top, right - left, bottom - top]


def _read_tile(key, lon, lat, step_m):
    import rasterio

    url = f"{BASE_URL}/chm/{key}.tif"
    path = "/vsicurl/" + url
    receipt = {
        "tile": key,
        "url": url,
        "metadata_url": f"{BASE_URL}/metadata/{key}.geojson",
    }
    try:
        with rasterio.open(path) as base:
            if base.crs != rasterio.crs.CRS.from_epsg(3857):
                raise ValueError(f"Unexpected CHMv2 CRS: {base.crs}")
            ground_pixel_m = abs(base.res[0]) * np.cos(np.deg2rad(float(np.mean(lat))))
            factors = base.overviews(1)
            eligible = [f for f in factors if f * ground_pixel_m <= step_m]
            factor = max(eligible, default=1)
            receipt.update(
                source_crs=str(base.crs),
                source_pixel_m_projected=list(base.res),
                source_nodata=base.nodata,
                overview_factor=factor,
                approximate_ground_pixel_m=float(factor * ground_pixel_m),
            )
            if factor == 1:
                values, window = _sample_dataset(base, lon, lat)
            else:
                with rasterio.open(
                    path, overview_level=factors.index(factor)
                ) as overview:
                    values, window = _sample_dataset(overview, lon, lat)
        receipt.update(
            status="read", window=window, valid_samples=int(np.isfinite(values).sum())
        )
        return values, receipt
    except rasterio.errors.RasterioIOError as exc:
        # A missing ocean tile and a failed network request are not evidence of
        # zero canopy. Preserve both as unknown, with different receipt states.
        message = str(exc)
        status = "missing_tile" if "404" in message else "read_error"
        receipt.update(status=status, error=message)
        return np.full(lon.shape, np.nan, np.float32), receipt


def sample(sq, step_m=20, *, cache_dir=None):
    """Return ``(height_m, provenance)`` at equally spaced cell centres.

    ``step_m`` is the requested maximum *real-world* spacing, not game metres.
    A square has side ``17280 * sq['scale']`` metres and shape
    ``ceil(side / step_m) ** 2``; the exact spacing is recorded. Rows run from
    game north to south; columns run west to east, with ``sq['rotation']`` as
    in ``landcover.lonlat``. Heights are float32 metres above ground, NaN for
    missing data. ``cache_dir`` enables atomic, versioned sampled-grid caching;
    transient read failures are never cached. Source tiles are byte-range read.
    """
    import rasterio

    geometry = {k: float(sq[k]) for k in ("lon", "lat", "rotation", "scale")}
    if not all(math.isfinite(v) for v in geometry.values()):
        raise ValueError("Square coordinates, rotation and scale must be finite")
    if geometry["scale"] <= 0 or not math.isfinite(step_m) or step_m <= 0:
        raise ValueError("Scale and sample spacing must be positive and finite")
    if not -180 <= geometry["lon"] <= 180 or abs(geometry["lat"]) >= MERCATOR_LIMIT:
        raise ValueError("CHMv2 sampling requires a valid Web Mercator centre")
    side_m = 2 * HALF_GAME_M * geometry["scale"]
    size = math.ceil(side_m / step_m)
    if size > 8192:
        raise ValueError("Requested canopy grid exceeds 8192 cells per side")
    identity = json.dumps(
        {
            "sq": geometry,
            "step_m": step_m,
            "dataset": VERSION,
            "sampler": SAMPLER_VERSION,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(identity.encode()).hexdigest()
    cache = Path(cache_dir) / f"{digest}.npz" if cache_dir is not None else None
    if cache is not None and cache.exists():
        with np.load(cache, allow_pickle=False) as saved:
            heights = saved["height_m"]
            receipt = json.loads(str(saved["provenance"]))
        receipt["cache_hit"] = True
        return heights, receipt

    centres = (np.arange(size) + 0.5) * (2 * HALF_GAME_M / size) - HALF_GAME_M
    x, z = np.meshgrid(centres, centres[::-1])
    lon, lat = lonlat(geometry, x, z)
    if np.max(np.abs(lat)) >= MERCATOR_LIMIT:
        raise ValueError("Square extends outside Web Mercator coverage")
    lon = (lon + 180) % 360 - 180
    tile_ids = _tile_ids(lon, lat)
    heights = np.full((size, size), np.nan, np.float32)
    tiles = []
    env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "GDAL_HTTP_TIMEOUT": "20",
        "GDAL_HTTP_MAX_RETRY": "0",
    }
    with rasterio.Env(**env):
        for tile_id in np.unique(tile_ids):
            inside = tile_ids == tile_id
            key = quadkey(int(tile_id % 1024), int(tile_id // 1024))
            heights[inside], tile = _read_tile(
                key, lon[inside], lat[inside], side_m / size
            )
            tiles.append(tile)

    valid_count = int(np.isfinite(heights).sum())
    errors = any(t["status"] == "read_error" for t in tiles)
    status = (
        "partial"
        if errors and valid_count
        else "unavailable"
        if errors
        else "available"
        if valid_count
        else "no_data"
    )
    receipt = {
        "schema": "polli.canopy-samples/1",
        "sampler_version": SAMPLER_VERSION,
        "dataset": VERSION,
        "source_url": SOURCE_URL,
        "attribution": ATTRIBUTION,
        "license": "CC-BY-4.0",
        "accessed_utc": datetime.now(UTC).isoformat(),
        "sq": geometry,
        "side_m": side_m,
        "requested_step_m": step_m,
        "step_m": side_m / size,
        "shape": [size, size],
        "orientation": "north-first rows, west-first columns, rotated game frame",
        "units": "metres above ground",
        "nodata": "NaN (internal cloud/validity mask, 255, missing tiles or read errors)",
        "sampling": "nearest cell of provider COG overview; overview aggregation unspecified",
        "interpretation": "area samples of top-of-canopy structure, not individual tree heights",
        "limitations": [
            "Satellite-model estimates, not field-verified heights or individual tree counts.",
            "Single-time imagery mosaic; exact observation dates are in per-tile metadata.",
            "Viewing geometry and geographically sparse training data can affect estimates.",
            "Provider overviews may smooth tall crowns and narrow gaps; no subcanopy information.",
        ],
        "status": status,
        "valid_samples": valid_count,
        "coverage_fraction": valid_count / heights.size,
        "tiles": tiles,
        "cache_key": digest,
        "cache_hit": False,
    }
    if cache is not None and not errors:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=cache.parent, suffix=".npz", delete=False
        ) as tmp:
            temporary = Path(tmp.name)
            try:
                np.savez_compressed(
                    tmp, height_m=heights, provenance=json.dumps(receipt)
                )
                tmp.flush()
                temporary.replace(cache)
            finally:
                temporary.unlink(missing_ok=True)
    return heights, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "geometry", type=Path, help="geometry JSON, optionally gzip-compressed"
    )
    parser.add_argument(
        "output", type=Path, help="float32 north-first height raster (.npy)"
    )
    parser.add_argument("--step-m", type=float, default=20)
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
    raw = args.geometry.read_bytes()
    geometry = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    heights, receipt = sample(geometry["sq"], args.step_m, cache_dir=args.cache_dir)
    with args.output.open("wb") as handle:
        np.save(handle, heights)
    args.output.with_suffix(".json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
