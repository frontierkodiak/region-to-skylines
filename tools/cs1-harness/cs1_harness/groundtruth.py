"""Check a map against the world, not against our own code's frame.

Every other map check (probes, water readback, terracing) places and draws its
results in the same coordinate frame the map writer used, so a rotated,
mirrored or transposed map passes all of them. This check is independent of
the writer: it fetches elevation itself (AWS Terrain Tiles, Terrarium encoding),
projects it with pyproj into the game's frame, where +x is east and +z is
north, and compares it with the terrain heights the game itself reports.

- `orientation`: correlation of height anomalies between the game's terrain
  and the DEM, for the identity and the seven other rotations and mirrors. The
  map passes if the identity correlates strongly and clearly best. Otherwise the
  winning transform says how the map is turned.
- `landmarks`: the region's highest and lowest DEM points (lopsided by nature)
  and any named landmarks from the probe file, with the game's height there.

The region comes from the probe file's `ground_truth`:
    {"lat": 35.58, "lon": -82.555, "size_m": 17280, "rotation": 0, "base": 572.44,
     "landmarks": [{"name": "Town Mountain", "lat": ..., "lon": ...}]}
`base` (the DEM height at game height 0) is optional; it only adds absolute
height errors to the landmark rows.
"""

from __future__ import annotations

import math
import os
import pathlib
import urllib.request

import numpy as np
from PIL import Image

N = 1081
CELL = 16.0
HALF = 8640.0
TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
CACHE = pathlib.Path(os.environ.get("CS1_HARNESS_DEM_CACHE", str(pathlib.Path.home() / ".cache/cs1-harness/terrarium")))
ZOOM = 13
STEP = 4  # compare on a 64 m grid

THRESHOLDS = {
    "min_correlation": 0.9,  # identity must correlate at least this well
    "min_margin": 0.15,  # and beat every other rotation or mirror by this much
}

# Transforms of a north-up array (row 0 = north, col 0 = west), as seen on a north-up map.
TRANSFORMS = {
    "as is": lambda a: a,
    "rotated 90° clockwise": lambda a: np.rot90(a, -1),
    "rotated 180°": lambda a: np.rot90(a, 2),
    "rotated 90° counter-clockwise": lambda a: np.rot90(a, 1),
    "mirrored east-west": lambda a: a[:, ::-1],
    "mirrored north-south": lambda a: a[::-1, :],
    "transposed (x and z swapped)": lambda a: a.T,
    "anti-transposed": lambda a: np.rot90(a, 2).T,
}


def tile(z: int, x: int, y: int) -> np.ndarray:
    path = CACHE / str(z) / str(x) / f"{y}.png"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(TILE_URL.format(z=z, x=x, y=y), headers={"User-Agent": "cs1-harness"})
        with urllib.request.urlopen(req, timeout=60) as r:
            path.write_bytes(r.read())
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)
    return rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768


def dem_at(lon: np.ndarray, lat: np.ndarray, zoom: int = ZOOM) -> np.ndarray:
    """Bilinear DEM height (m) at WGS84 points, from Web Mercator Terrarium tiles."""
    n = 2**zoom
    px = (lon + 180) / 360 * n * 256
    lat_r = np.radians(lat)
    py = (1 - np.log(np.tan(lat_r) + 1 / np.cos(lat_r)) / math.pi) / 2 * n * 256
    tx0, tx1 = int(px.min() // 256), int(px.max() // 256) + 1
    ty0, ty1 = int(py.min() // 256), int(py.max() // 256) + 1
    mosaic = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256))
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            mosaic[(ty - ty0) * 256 : (ty - ty0 + 1) * 256, (tx - tx0) * 256 : (tx - tx0 + 1) * 256] = tile(
                zoom, tx, ty
            )
    fx, fy = px - tx0 * 256 - 0.5, py - ty0 * 256 - 0.5
    x0, y0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
    ax, ay = fx - x0, fy - y0
    x0 = np.clip(x0, 0, mosaic.shape[1] - 2)
    y0 = np.clip(y0, 0, mosaic.shape[0] - 2)
    m = mosaic
    return (
        m[y0, x0] * (1 - ax) * (1 - ay)
        + m[y0, x0 + 1] * ax * (1 - ay)
        + m[y0 + 1, x0] * (1 - ax) * ay
        + m[y0 + 1, x0 + 1] * ax * ay
    )


def projection(region: dict):
    """Game metres (x east, z north) -> lon/lat, a transverse Mercator centred on the region."""
    from pyproj import Transformer

    tm = f"+proj=tmerc +lat_0={region['lat']} +lon_0={region['lon']} +k=1 +x_0=0 +y_0=0 +ellps=WGS84 +units=m"
    to_ll = Transformer.from_crs(tm, "EPSG:4326", always_xy=True)
    scale = float(region.get("size_m", 2 * HALF)) / (2 * HALF)
    rot = math.radians(float(region.get("rotation", 0)))

    def inverse(x, z):
        # A rotated region turns the game square on the ground: rotate, then scale.
        e = (x * math.cos(rot) - z * math.sin(rot)) * scale
        n_ = (x * math.sin(rot) + z * math.cos(rot)) * scale
        return to_ll.transform(e, n_)

    def forward(lon, lat):
        from pyproj import Transformer as T

        e, n_ = T.from_crs("EPSG:4326", tm, always_xy=True).transform(lon, lat)
        e, n_ = e / scale, n_ / scale
        return e * math.cos(rot) + n_ * math.sin(rot), -e * math.sin(rot) + n_ * math.cos(rot)

    return inverse, forward


def game_terrain(path: pathlib.Path) -> np.ndarray:
    """The game's raw terrain dump, as metres in [row = z index (south first), col = x index]."""
    return np.fromfile(path, dtype="<u2").reshape(N, N) / 64.0


def corr(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a - a.mean(), b - b.mean()
    d = math.sqrt(float((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / d) if d else 0.0


def check(terrain_path: pathlib.Path, region: dict, out: pathlib.Path | None = None) -> dict:
    inverse, forward = projection(region)
    idx = np.arange(0, N, STEP)
    xs = idx * CELL - HALF
    zz, xx = np.meshgrid(xs, xs, indexing="ij")  # row = z (south to north), col = x (west to east)
    lon, lat = inverse(xx, zz)
    dem = dem_at(np.asarray(lon), np.asarray(lat))
    game = game_terrain(terrain_path)[::STEP, ::STEP]

    # Score "the game shows the world, transformed": turn the north-up DEM and compare.
    game_n, dem_n = np.flipud(game), np.flipud(dem)
    scores = {name: round(corr(game_n, f(dem_n)), 4) for name, f in TRANSFORMS.items()}
    best = max(scores, key=scores.get)
    identity = scores["as is"]
    runner = max(v for k, v in scores.items() if k != "as is")
    ok = identity >= THRESHOLDS["min_correlation"] and identity - runner >= THRESHOLDS["min_margin"]
    # Height mapping the game used, from a straight-line fit (base, vertical scale).
    slope, intercept = np.polyfit(game.ravel(), dem.ravel(), 1)
    resid = dem - (slope * game + intercept)

    landmarks = []
    # Lopsided landmarks: the highest and lowest DEM points at least 1 km inside the map edge.
    inner = (np.abs(xx) < HALF - 1000) & (np.abs(zz) < HALF - 1000)
    masked_hi, masked_lo = np.where(inner, dem, -np.inf), np.where(inner, dem, np.inf)
    for kind, flat in (("highest DEM point", int(masked_hi.argmax())), ("lowest DEM point", int(masked_lo.argmin()))):
        r, c = np.unravel_index(flat, dem.shape)
        landmarks.append(
            {"name": kind, "x": float(xx[r, c]), "z": float(zz[r, c]), "dem_m": round(float(dem[r, c]), 1)}
        )
    for lm in region.get("landmarks") or []:
        x, z = forward(lm["lon"], lm["lat"])
        landmarks.append({"name": lm["name"], "x": round(float(x), 1), "z": round(float(z), 1)})
    full = game_terrain(terrain_path)
    for lm in landmarks:
        ix, iz = int(round((lm["x"] + HALF) / CELL)), int(round((lm["z"] + HALF) / CELL))
        if 0 <= ix < N and 0 <= iz < N:
            lm["game_m"] = round(float(full[iz, ix]), 1)
            if "dem_m" not in lm:
                lo, la = inverse(np.array([lm["x"]]), np.array([lm["z"]]))
                lm["dem_m"] = round(float(dem_at(np.asarray(lo), np.asarray(la))[0]), 1)
            lm["dem_from_game_m"] = round(float(slope * lm["game_m"] + intercept), 1)
            lm["error_m"] = round(lm["dem_from_game_m"] - lm["dem_m"], 1)
            if region.get("base") is not None:
                lm["error_vs_base_m"] = round(lm["game_m"] + float(region["base"]) - lm["dem_m"], 1)

    result = {
        "passed": bool(ok),
        "orientation": "as is" if ok else best,
        "correlation": scores,
        "best": best,
        "fit": {"vertical_scale": round(float(slope), 3), "base_m": round(float(intercept), 1)},
        "residual_m": {
            "median_abs": round(float(np.median(np.abs(resid))), 1),
            "p95_abs": round(float(np.percentile(np.abs(resid), 95)), 1),
        },
        "landmarks": landmarks,
        "thresholds": THRESHOLDS,
        "dem": f"AWS Terrain Tiles (Terrarium) zoom {ZOOM}, fetched and projected by the harness (pyproj tmerc)",
    }
    if out is not None:
        side_by_side(game, dem, out / "ground-truth.png", best)
        result["image"] = "ground-truth.png"
    return result


def side_by_side(game: np.ndarray, dem: np.ndarray, path: pathlib.Path, best: str):
    """North-up hillshades: the real DEM, the game's terrain, and (if they differ) the DEM turned the way the game shows it."""

    def shade(h):
        gz, gx = np.gradient(h, CELL * STEP)
        s = (-gx + gz) / np.sqrt(1 + gx * gx + gz * gz)
        s = (s - s.min()) / max(1e-6, np.ptp(s))
        return (np.flipud(0.2 + 0.75 * s) * 255).astype(np.uint8)  # row 0 = north at the top

    panels = [shade(dem), shade(game)]
    if best != "as is":
        panels.append(
            np.flipud(shade(np.flipud(TRANSFORMS[best](np.flipud(dem)))))
            if False
            else shade(np.flipud(TRANSFORMS[best](np.flipud(dem))))
        )
    gap = np.full((dem.shape[0], 8), 255, np.uint8)
    row = panels[0]
    for p in panels[1:]:
        row = np.hstack([row, gap, p])
    Image.fromarray(row).save(path)
