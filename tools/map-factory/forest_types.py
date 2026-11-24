"""Acquire a global leaf-habit *pixel prior*, never an individual-tree trait.

Copernicus Global Land Service LC100, Collection 3 v3.0.1, 2019 NRT epoch.
The separate forest-type layer types pixels with tree cover fraction >1%;
unlike the discrete land-cover map it is not restricted to forest classes.
Its ~100 m support cannot identify species, palms, shrubs or individual trees.

Primary dataset / CC BY 4.0: https://doi.org/10.5281/zenodo.3939050
Codes and limitations, section 3.3.3:
https://land.copernicus.eu/en/technical-library/global-dynamic-land-cover-product-user-manual-v3.0/@@download/file

The historic vito.landcover.global S3 bucket is unavailable. The preserved
global tiled TIFF on Zenodo supports anonymous HTTP range reads. It has no
overviews and is not claimed to be a strictly conformant COG. Do not download
the entire ~1 GB object: a square needs only its small source window.
"""

import math
from datetime import UTC, datetime

import numpy as np
from landcover import lonlat

URL = (
    "https://zenodo.org/records/3939050/files/"
    "PROBAV_LC100_global_v3.0.1_2019-nrt_Forest-Type-layer_EPSG-4326.tif"
)
SOURCE_URL = "https://doi.org/10.5281/zenodo.3939050"
CLASSES = {
    0: "unknown",
    1: "evergreen needleleaf",
    2: "evergreen broadleaf",
    3: "deciduous needleleaf",
    4: "deciduous broadleaf",
    5: "mixed forest types",
    255: "no data",
}


def sample(sq, step_m=100):
    """Return ``(uint8 class grid, receipt)`` in the rotated game frame.

    Same real-world cell-centre frame as ``canopy.sample``: side 17280*scale
    metres, ceil(side/step_m) cells per axis, north-first rows. Nearest native
    source pixel, no class interpolation. Code 0 is unknown, 255 is no data,
    and class 5 remains mixed (never invent a 50/50 split). Use these as local
    composition priors only where direct trait evidence is missing; never
    label a species or observed individual with an inferred pixel trait.
    """
    import rasterio
    from rasterio.windows import Window

    geometry = {k: float(sq[k]) for k in ("lon", "lat", "scale", "rotation")}
    if not all(math.isfinite(v) for v in geometry.values()):
        raise ValueError("Square geometry must be finite")
    if geometry["scale"] <= 0 or not math.isfinite(step_m) or step_m <= 0:
        raise ValueError("Scale and spacing must be positive and finite")
    if not -180 <= geometry["lon"] <= 180 or not -60 < geometry["lat"] < 80:
        raise ValueError("CGLS LC100 coverage is 60°S to 80°N")
    side_m = 17280 * geometry["scale"]
    size = math.ceil(side_m / step_m)
    if size > 8192:
        raise ValueError("Requested forest-type grid exceeds 8192 cells per side")
    centres = (np.arange(size) + 0.5) * (17280 / size) - 8640
    x, z = np.meshgrid(centres, centres[::-1])
    lon, lat = lonlat(geometry, x, z)
    lon = (lon + 180) % 360 - 180
    out = np.full((size, size), 255, np.uint8)
    with (
        rasterio.Env(
            GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            GDAL_HTTP_TIMEOUT="20",
            GDAL_HTTP_MAX_RETRY="0",
            CPL_VSIL_CURL_USE_HEAD="NO",
        ),
        rasterio.open("/vsicurl/" + URL) as src,
    ):
        if src.crs != rasterio.crs.CRS.from_epsg(4326):
            raise ValueError(f"Unexpected CGLS forest-type CRS: {src.crs}")
        cols, rows = (~src.transform) @ (lon, lat)
        cols, rows = np.floor(cols).astype(int), np.floor(rows).astype(int)
        inside = (cols >= 0) & (cols < src.width) & (rows >= 0) & (rows < src.height)
        groups = [inside]
        if np.ptp(lon) > 180:
            groups = [inside & (lon < 0), inside & (lon >= 0)]
        windows = []
        for group in groups:
            if not group.any():
                continue
            left, right = int(cols[group].min()), int(cols[group].max()) + 1
            top, bottom = int(rows[group].min()), int(rows[group].max()) + 1
            window = Window(left, top, right - left, bottom - top)
            block = src.read(1, window=window, masked=True).filled(255)
            out[group] = block[rows[group] - top, cols[group] - left]
            windows.append(list(window.flatten()))
        source = {
            "url": URL,
            "crs": str(src.crs),
            "bounds": list(src.bounds),
            "pixel_degrees": list(src.res),
            "nodata": src.nodata,
            "windows": windows,
            "published_archive_md5": "17aed9604a2df8f0247f0ff0e297c1c4",
        }
    out[~np.isin(out, list(CLASSES))] = 255
    values, counts = np.unique(out, return_counts=True)
    return out, {
        "schema": "polli.forest-type-prior/1",
        "dataset": "CGLS-LC100-C3-v3.0.1-2019-nrt-forest-type",
        "source_url": SOURCE_URL,
        "license": "CC-BY-4.0",
        "attribution": "Buchhorn et al. (2020), Copernicus Global Land Service LC100 Collection 3, epoch 2019; Copernicus Service information 2020.",
        "accessed_utc": datetime.now(UTC).isoformat(),
        "sq": geometry,
        "shape": [size, size],
        "side_m": side_m,
        "step_m": side_m / size,
        "classes": CLASSES,
        "class_counts": {int(v): int(n) for v, n in zip(values, counts)},
        "valid_fraction": float((out != 255).mean()),
        "typed_fraction": float(((out >= 1) & (out <= 5)).mean()),
        "interpretation": "2019 ~100 m forest-type pixel prior, not an individual-tree trait or species abundance",
        "sampling": "nearest native source pixel; repeated finer samples add no source resolution",
        "source": source,
    }
