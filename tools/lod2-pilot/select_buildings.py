"""Pick the pilot buildings before any lidar is read.

Two neighbourhoods (Montford, an early-1900s residential district, and downtown), 25
buildings each. The hard cases the issue asks for are found from data that is not the
roof evidence: tree crowns from NAIP (pixel-asheville's `trees.naip.u16`), ground relief
from the scene terrain, and the county outline itself (shape, shared walls). Quotas
guarantee each hard case appears; the rest is a seeded random draw. Ten become the
development set, forty stay locked.

    uv run select_buildings.py --pixel <workbench>/pixel-asheville/public/data

Round 2 (PL-909) draws a second locked set from the same pools after its method was
frozen: `--fresh 20 --seed 909` keeps the buildings already in `selection/buildings.json`
as they are and adds 20 per neighbourhood that are not among them, all locked, with the
hard-case quotas scaled to the smaller draw.
"""

from __future__ import annotations

import argparse
import random
import struct
from pathlib import Path

import numpy as np
import requests
from pyproj import Transformer
from shapely import STRtree
from shapely.geometry import Point, Polygon, shape

from common import EXP, FOOTPRINTS, FTUS, to_local, write_json

SEED = 900
AOIS = {  # lon0, lat0, lon1, lat1
    "montford": (-82.5720, 35.5990, -82.5600, 35.6090),
    "downtown": (-82.5570, 35.5915, -82.5450, 35.5990),
}
# The one 2025 QL1 tile held so far (SDD job 234441), EPSG:6543 ftUS.
TILE_2025 = (945000.0, 690000.0, 947500.0, 692500.0)
MIN_AREA = 30.0  # m2; smaller outlines are sheds


def fetch(aoi):
    lon0, lat0, lon1, lat1 = aoi
    r = requests.get(
        FOOTPRINTS + "/query",
        params={
            "where": "1=1", "geometry": f"{lon0},{lat0},{lon1},{lat1}", "geometryType": "esriGeometryEnvelope",
            "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": "objectid,pinnum,status",
            "outSR": 2264, "f": "geojson",
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["features"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pixel", type=Path, required=True, help="pixel-asheville public/data")
    ap.add_argument("--out", type=Path, default=EXP / "selection")
    ap.add_argument("--fresh", type=int, default=0, help="add this many new locked buildings per neighbourhood to the existing selection")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    per_hood = args.fresh or 25
    before = __import__("json").loads((args.out / "buildings.json").read_text()) if args.fresh else None
    used = {b["id"] for b in before["buildings"]} if before else set()
    meta = __import__("json").loads((args.pixel / "meta.json").read_text())
    X0, Z0, X1, Z1 = meta["bounds"]
    cols, rows = meta["cols"], meta["rows"]
    terrain = np.frombuffer((args.pixel / "terrain.u16").read_bytes(), "<u2").reshape(rows, cols) / 100 + meta["heightBase"]
    trees = np.frombuffer((args.pixel / "trees.naip.u16").read_bytes(), "<u2").reshape(-1, 6)
    tx, tz, tr = trees[:, 0] / 8 + X0, trees[:, 1] / 8 + Z0, trees[:, 3] / 100
    crowns = [Point(x, z).buffer(r, 8) for x, z, r in zip(tx, tz, tr) if -2400 < x < 1300 and -2200 < z < 800]
    crown_tree = STRtree(crowns)

    def ground(x, z):
        fx = np.clip((x - X0) / (X1 - X0) * (cols - 1), 0, cols - 1.001)
        fz = np.clip((z - Z0) / (Z1 - Z0) * (rows - 1), 0, rows - 1.001)
        i, j = int(fx), int(fz)
        u, v = fx - i, fz - j
        t = terrain
        return (t[j, i] * (1 - u) + t[j, i + 1] * u) * (1 - v) + (t[j + 1, i] * (1 - u) + t[j + 1, i + 1] * u) * v

    to_ll = Transformer.from_crs(2264, 4326, always_xy=True)
    picked, table, everyone = [], [], []
    for hood, aoi in AOIS.items():
        feats = fetch(aoi)
        polys, rows_ = [], []
        for f in feats:
            g = shape(f["geometry"])
            if g.geom_type == "MultiPolygon":
                g = max(g.geoms, key=lambda p: p.area)
            ring = [to_local(x * FTUS, y * FTUS) for x, y in g.exterior.coords]
            p = Polygon(ring)
            if not p.is_valid:
                p = p.buffer(0)
            polys.append(p)
            rows_.append((f["properties"], g))
        tree = STRtree(polys)
        cands = []
        for k, (p, (props, g2264)) in enumerate(zip(polys, rows_)):
            c = p.centroid
            lon, lat = to_ll.transform(g2264.centroid.x, g2264.centroid.y)
            if not (aoi[0] <= lon <= aoi[2] and aoi[1] <= lat <= aoi[3]) or p.area < MIN_AREA:
                continue
            # canopy: share of the outline under NAIP tree crowns
            near = [crowns[i] for i in crown_tree.query(p)]
            canopy = sum(p.intersection(cr).area for cr in near) / p.area if near else 0.0
            # relief: ground range under the outline's bounding ring
            ring = np.array(p.buffer(2).exterior.coords)
            gz = [ground(x, z) for x, z in ring]
            relief = max(gz) - min(gz)
            # shape: fill of the minimum rotated rectangle, and vertex count after 0.5 m simplify
            fill = p.area / p.minimum_rotated_rectangle.area
            nv = len(p.simplify(0.5).exterior.coords) - 1
            # shared walls: another outline within 0.4 m along at least 3 m
            adj = 0.0
            for i in tree.query(p.buffer(0.4)):
                if i != k:
                    adj = max(adj, p.buffer(0.4).intersection(polys[i].buffer(0.4)).area / 0.8)
            e, n = g2264.centroid.x, g2264.centroid.y
            cands.append({
                "id": props["objectid"], "pin": props["pinnum"], "status": props["status"], "hood": hood,
                "x": round(c.x, 2), "z": round(c.y, 2), "lon": round(lon, 6), "lat": round(lat, 6),
                "area": round(p.area, 1), "canopy": round(min(canopy, 1.0), 3), "relief": round(relief, 2),
                "fill": round(fill, 3), "vertices": nv, "shared_wall_m": round(adj, 1),
                "in_2025_tile": TILE_2025[0] <= e <= TILE_2025[2] and TILE_2025[1] <= n <= TILE_2025[3],
                "ring": [[round(x, 3), round(z, 3)] for x, z in p.exterior.coords],
            })
        for c in cands:
            c["flags"] = [
                name for name, on in [
                    # NAIP crowns stop at roof edges, so this is overhang: the top decile in Montford
                    ("canopy", c["canopy"] >= 0.2),
                    ("complex", c["fill"] < 0.72 or c["vertices"] >= 12),
                    ("steep", c["relief"] >= 3.0),
                    # the county draws many downtown blocks as one outline; those are adjoining buildings too
                    ("adjoining", c["shared_wall_m"] >= 3.0 or (hood == "downtown" and c["area"] >= 1500)),
                    ("small", c["area"] < 74.3),  # under 800 ft2: outside the lidar's class-6 definition
                ] if on
            ]
        everyone += [{k: v for k, v in c.items() if k != "ring"} for c in cands]
        rng = random.Random(f"{args.seed}-{hood}")
        cands = [c for c in cands if c["id"] not in used]
        cands.sort(key=lambda c: c["id"])
        quotas = (
            {"canopy": 6, "complex": 6, "steep": 5, "small": 2} if hood == "montford"
            else {"adjoining": 8, "complex": 5, "steep": 4, "tile": 10, "small": 1}
        )
        quotas = {flag: round(n * per_hood / 25) for flag, n in quotas.items()}
        chosen: dict[int, dict] = {}
        for flag, n in quotas.items():
            pool = [c for c in cands if (c["in_2025_tile"] if flag == "tile" else flag in c["flags"]) and c["id"] not in chosen]
            have = sum(1 for c in chosen.values() if (c["in_2025_tile"] if flag == "tile" else flag in c["flags"]))
            for c in rng.sample(pool, min(len(pool), max(0, n - have))):
                chosen[c["id"]] = c
        rest = [c for c in cands if c["id"] not in chosen]
        for c in rng.sample(rest, per_hood - len(chosen)):
            chosen[c["id"]] = c
        sel = sorted(chosen.values(), key=lambda c: c["id"])
        dev = set() if args.fresh else set(c["id"] for c in rng.sample(sel, 5))
        for c in sel:
            c["set"] = "dev" if c["id"] in dev else "locked"
        picked += sel
        table.append({"hood": hood, "candidates": len(cands), "flag_counts": {
            f: sum(1 for c in cands if f in c["flags"]) for f in ["canopy", "complex", "steep", "adjoining", "small"]},
            "in_2025_tile": sum(1 for c in cands if c["in_2025_tile"])})
    if before:
        write_json(args.out / "buildings.json", before | {"fresh": {"seed": args.seed, "per_hood": per_hood, "pools": table},
                                                          "buildings": before["buildings"] + picked})
    else:
        write_json(args.out / "buildings.json", {"seed": args.seed, "aois": AOIS, "pools": table, "buildings": picked})
        write_json(args.out / "candidates.json", everyone, indent=None)
    for t in table:
        print(t)
    for c in picked:
        print(c["set"], c["hood"], c["id"], c["area"], c["flags"], "tile" if c["in_2025_tile"] else "")


if __name__ == "__main__":
    main()
