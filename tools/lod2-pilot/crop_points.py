"""Cut each pilot building's lidar out of the neighbourhood clouds.

Per building and per epoch (2017 USGS EPT, 2025 NC QL1 where the held tile covers it)
this writes the points within 25 m of the outline, and splits the points over the
outline into a fitting set and a withheld set: 2 m patches, one in five withheld, chosen
by a hash of the patch position. Reconstruction only ever sees the fitting set.

    uv run crop_points.py [--set dev|locked|all]
"""

from __future__ import annotations

import argparse
import hashlib

import laspy
import numpy as np
from shapely import contains_xy
from shapely.geometry import Polygon

from common import EXP, WORK_EPSG, read_json, to_work, write_json

BUFFER = 25.0
PATCH = 2.0
HOLD_ONE_IN = 5
CLOUDS = {
    "2017": {"montford": "ept2017/montford.laz", "downtown": "ept2017/downtown.laz"},
    "2025": {"downtown": "las2025/tile234441.laz"},
}


if (EXP / "clouds.json").exists():  # a second city names its own clouds
    CLOUDS = read_json(EXP / "clouds.json")


def held(ix: np.ndarray, iy: np.ndarray) -> np.ndarray:
    """True for points in withheld patches; depends only on patch position."""
    key = (ix.astype(np.int64) * 73856093) ^ (iy.astype(np.int64) * 19349663)
    key = (key ^ (key >> 13)) * 0x5BD1E995 & 0xFFFFFFFF
    return (key ^ (key >> 15)) % HOLD_ONE_IN == 0


def write_las(path, x, y, z, cls, rn, nr):
    hdr = laspy.LasHeader(point_format=6, version="1.4")
    hdr.scales = [0.001, 0.001, 0.001]
    hdr.offsets = [np.floor(x.min()), np.floor(y.min()), np.floor(z.min())] if len(x) else [0, 0, 0]
    from pyproj import CRS

    hdr.add_crs(CRS.from_epsg(WORK_EPSG))
    las = laspy.LasData(hdr)
    las.x, las.y, las.z = x, y, z
    las.classification = cls
    las.return_number = np.clip(rn, 1, 15)
    las.number_of_returns = np.clip(nr, 1, 15)
    path.parent.mkdir(parents=True, exist_ok=True)
    las.write(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="all")
    args = ap.parse_args()
    sel = read_json(EXP / "selection" / "buildings.json")["buildings"]
    if args.set != "all":
        sel = [b for b in sel if b["set"] == args.set]
    for epoch, files in CLOUDS.items():
        for hood, rel in files.items():
            todo = [b for b in sel if b["hood"] == hood and (epoch != "2025" or b["in_2025_tile"])]
            if not todo:
                continue
            las = laspy.read(EXP / "data" / rel)
            X, Y, Z = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)
            C = np.asarray(las.classification)
            RN, NR = np.asarray(las.return_number), np.asarray(las.number_of_returns)
            order = np.argsort(X, kind="stable")
            Xs = X[order]
            for b in todo:
                ring = [to_work(x, z) for x, z in b["ring"]]
                poly = Polygon(ring)
                x0, y0, x1, y1 = poly.bounds
                lo, hi = np.searchsorted(Xs, [x0 - BUFFER, x1 + BUFFER])
                idx = order[lo:hi]
                idx = idx[(Y[idx] >= y0 - BUFFER) & (Y[idx] <= y1 + BUFFER)]
                x, y, z, c, rn, nr = X[idx], Y[idx], Z[idx], C[idx], RN[idx], NR[idx]
                inside = contains_xy(poly, x, y)
                h = inside & held(np.floor(x / PATCH), np.floor(y / PATCH))
                out = EXP / "buildings" / str(b["id"]) / epoch
                write_las(out / "fit.las", x[~h], y[~h], z[~h], c[~h], rn[~h], nr[~h])
                write_las(out / "held.las", x[h], y[h], z[h], c[h], rn[h], nr[h])
                cls_in = np.bincount(c[inside], minlength=20)
                info = {
                    "id": b["id"], "epoch": epoch, "points": int(len(x)), "inside": int(inside.sum()),
                    "held": int(h.sum()), "density_inside": round(float(inside.sum() / poly.area), 2),
                    "class_inside": {str(i): int(n) for i, n in enumerate(cls_in) if n},
                    "sha256_fit": hashlib.sha256((out / "fit.las").read_bytes()).hexdigest(),
                }
                write_json(out / "crop.json", info)
                print(epoch, hood, b["id"], b["set"], info["inside"], info["density_inside"], info["class_inside"])
            del las, X, Y, Z, C, RN, NR, order, Xs


if __name__ == "__main__":
    main()
