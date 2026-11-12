"""Run Roofer on each pilot building and write the three arms' geometry inputs.

For each building and epoch:

- prepare the fitting cloud. `--classes asis` leaves the delivered classes; `--classes
  promote` (the frozen choice, see README) also marks as building every non-ground point
  over the outline that is 2 m or more above the ground beside it, because both
  collections only call something class 6 when it is 800 ft2 or larger;
- run Roofer (LoD 1.2, 1.3, 2.2) on that cloud and the county outline, nothing tuned per
  building;
- measure the height-only arm ourselves: outline extruded from the ground beside it to
  the 70th percentile of the building points (the LoD1.2 convention), so that arm does
  not depend on Roofer succeeding.

Each building is reconstructed twice: from the fitting set only (`fit`, used to check
accuracy on the withheld patches) and from every point (`all`, the geometry that is
rendered, judged and exported).

Writes `<building>/<epoch>/<classes>-<cloud>/recon.json` with Roofer's attributes, timing, and
triangles for LoD2.2 and LoD1.2 in the local frame (x east, y up NAVD88 m, z south).

    uv run reconstruct.py --set dev --classes promote
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

import geopandas as gpd
import laspy
import mapbox_earcut as earcut
import numpy as np
from shapely import contains_xy
from shapely.geometry import Polygon

from common import EXP, FIT_EPOCH, WORK_EPSG, read_json, to_local, to_work, write_json
from crop_points import write_las

ROOFER = EXP / "tools" / "roofer" / "bin" / "roofer"
MIN_ABOVE = 2.0  # m above the ground beside the outline to count as roof evidence
NOT_ROOF = (2, 7, 9, 18)  # ground, low noise, water, high noise
PLANE_TOL = 0.12  # m, inlier distance when looking for unclassified roof planes


def ground_beside(poly: Polygon, x, y, z, c) -> float | None:
    """Roofer's rule: 5th percentile of ground points within 4 m of the outline."""
    ring = poly.buffer(4.0)
    g = (c == 2) & contains_xy(ring, x, y) & ~contains_xy(poly, x, y)
    if g.sum() < 5:
        g = c == 2
    return float(np.percentile(z[g], 5)) if g.sum() else None


def roof_planes(P: np.ndarray, seed: int) -> np.ndarray:
    """Points of P (n, 3) that lie on roof-like planes: sequential RANSAC, accepting a plane
    when it is no steeper than 60 degrees and its inliers cover 6 m2 or more at 3 points/m2."""
    from scipy.spatial import ConvexHull

    rng = np.random.default_rng(seed)
    left = np.arange(len(P))
    keep = np.zeros(len(P), bool)
    for _ in range(12):
        if len(left) < 25:
            break
        Q = P[left]
        best = None
        for _ in range(300):
            i = rng.choice(len(Q), 3, replace=False)
            n = np.cross(Q[i[1]] - Q[i[0]], Q[i[2]] - Q[i[0]])
            ln = np.linalg.norm(n)
            if ln < 1e-6:
                continue
            n /= ln
            if abs(n[2]) < 0.5:
                continue
            inl = np.abs((Q - Q[i[0]]) @ n) <= PLANE_TOL
            if best is None or inl.sum() > best.sum():
                best = inl
        if best is None or best.sum() < 25:
            break
        xy = Q[best][:, :2]
        try:
            area = ConvexHull(xy).volume
        except Exception:
            area = 0.0
        if area >= 6.0 and best.sum() / area >= 3.0:
            keep[left[best]] = True
        left = left[~best]
    return keep


def load(bid, epoch: str, cloud: str):
    """x, y, z, class of a building's crop: the fitting set, or everything ("all")."""
    parts = []
    for name in ("fit", "held") if cloud == "all" else (cloud,):
        las = laspy.read(EXP / "buildings" / str(bid) / epoch / f"{name}.las")
        parts.append(np.c_[np.asarray(las.x), np.asarray(las.y), np.asarray(las.z), np.asarray(las.classification)])
    P = np.vstack(parts)
    return P[:, 0], P[:, 1], P[:, 2], P[:, 3].astype(np.uint8)


def label_roof(b, x, y, z, c, classes: str):
    """Classes after the frozen preparation, the ground beside the outline, and counts."""
    c = c.copy()
    poly = Polygon([to_work(px, pz) for px, pz in b["ring"]])
    ground = ground_beside(poly, x, y, z, c)
    inside = contains_xy(poly, x, y)
    promoted = 0
    rescue_only = classes == "rescue" and (c[inside] == 6).sum() < 50
    if (classes == "promote" or rescue_only) and ground is not None:
        up = np.flatnonzero(inside & ~np.isin(c, NOT_ROOF + (6,)) & (z >= ground + MIN_ABOVE))
        on = roof_planes(np.c_[x, y, z][up], b["id"]) if len(up) >= 25 else np.zeros(len(up), bool)
        promoted = int(on.sum())
        c[up[on]] = 6
    return c, poly, ground, inside, promoted


def prepare(b, epoch: str, classes: str, cloud: str, out: Path):
    x, y, z, c0 = load(b["id"], epoch, cloud)
    c, poly, ground, inside, promoted = label_roof(b, x, y, z, c0, classes)
    write_las(out / "cloud.las", x, y, z, c, np.ones(len(x), np.uint8), np.ones(len(x), np.uint8))
    roof = inside & (c == 6)
    stats = {
        "ground": ground, "inside": int(inside.sum()), "class6_delivered": int((c0[inside] == 6).sum()),
        "promoted": promoted, "roof_points": int(roof.sum()),
        "h70": float(np.percentile(z[roof], 70)) if roof.sum() >= 10 else None,
    }
    gpd.GeoDataFrame({"id": [str(b["id"])]}, geometry=[poly], crs=WORK_EPSG).to_file(out / "footprint.gpkg", driver="GPKG")
    return stats, poly


def triangulate(ring_sets, verts):
    """CityJSON surface (outer ring + holes, vertex indices) -> triangles (n, 3, 3)."""
    pts = [verts[r] for r in ring_sets]
    allp = np.vstack(pts)
    n = np.zeros(3)
    o = pts[0]
    for i in range(len(o)):  # Newell normal of the outer ring
        a, bb = o[i], o[(i + 1) % len(o)]
        n += [(a[1] - bb[1]) * (a[2] + bb[2]), (a[2] - bb[2]) * (a[0] + bb[0]), (a[0] - bb[0]) * (a[1] + bb[1])]
    ln = np.linalg.norm(n)
    if ln < 1e-9:
        return np.zeros((0, 3, 3)), n
    n /= ln
    u = np.cross(n, [0, 0, 1.0] if abs(n[2]) < 0.9 else [1.0, 0, 0])
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    flat = np.stack([allp @ u, allp @ v], axis=1)
    ends = np.cumsum([len(p) for p in pts]).astype(np.uint32)
    idx = earcut.triangulate_float64(flat, ends).reshape(-1, 3)
    return allp[idx], n


def parse(feature_path: Path, meta_path: Path):
    meta = json.loads(meta_path.read_text())
    s, t = np.array(meta["transform"]["scale"]), np.array(meta["transform"]["translate"])
    f = json.loads(feature_path.read_text().splitlines()[0])
    v = np.array(f["vertices"], float) * s + t
    # work (E, N, H) -> local (x east, y up, z south)
    lx, lz = to_local(v[:, 0], v[:, 1])
    verts = np.stack([lx, v[:, 2], lz], axis=1)
    parent = next(o for o in f["CityObjects"].values() if o["type"] == "Building")
    lods = {}
    for o in f["CityObjects"].values():
        if o["type"] != "BuildingPart":
            continue
        for g in o["geometry"]:
            tris, kinds, parts = [], [], []
            surfaces = g["semantics"]["surfaces"]
            roof_parts = []
            for shell, values in zip(g["boundaries"], g["semantics"]["values"]):
                for surf, val in zip(shell, values):
                    sem = surfaces[val]
                    tri, n = triangulate([np.array(r) for r in surf], verts)
                    if not len(tri):
                        continue
                    # outward normals: CityJSON rings are counter-clockwise seen from outside in
                    # (E, N, H); swapping N for -z mirrors them, so flip the winding back.
                    tri = tri[:, ::-1, :]
                    kind = {"RoofSurface": "roof", "GroundSurface": "ground"}.get(sem["type"], "wall")
                    if kind == "roof":
                        roof_parts.append({k: sem[k] for k in sem if k.startswith("rf_")} | {"triangles": len(tri)})
                    tris.append(tri)
                    kinds += [kind] * len(tri)
                    parts += [len(roof_parts) - 1 if kind == "roof" else -1] * len(tri)
            lods.setdefault(g["lod"], {"tri": [], "kind": [], "part": [], "roof_parts": []})
            L = lods[g["lod"]]
            off = len(L["roof_parts"])
            L["tri"] += np.round(np.vstack(tris), 3).reshape(-1, 9).tolist() if tris else []
            L["kind"] += kinds
            L["part"] += [p + off if p >= 0 else -1 for p in parts]
            L["roof_parts"] += roof_parts
    return parent["attributes"], lods


def extrude(poly_local: Polygon, y0: float, y1: float):
    """Outline extruded between two heights, as triangles with kinds."""
    ring = np.array(poly_local.exterior.coords)[:-1]
    if Polygon(ring).exterior.is_ccw:  # make clockwise in (x, z) so walls face out with y up
        ring = ring[::-1]
    tris, kinds = [], []
    n = len(ring)
    for i in range(n):
        (ax, az), (bx, bz) = ring[i], ring[(i + 1) % n]
        a0, b0, a1, b1 = [ax, y0, az], [bx, y0, bz], [ax, y1, az], [bx, y1, bz]
        tris += [[a0, a1, b1], [a0, b1, b0]]
        kinds += ["wall", "wall"]
    idx = earcut.triangulate_float64(ring, np.array([n], np.uint32)).reshape(-1, 3)
    for i, j, k in idx:
        tris.append([[ring[i][0], y1, ring[i][1]], [ring[j][0], y1, ring[j][1]], [ring[k][0], y1, ring[k][1]]])
        kinds.append("roof")
    tri = np.array(tris, float)
    # orient: roof normals up, wall normals away from the centroid
    c = np.array([poly_local.centroid.x, 0, poly_local.centroid.y])
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    mid = tri.mean(axis=1)
    want = np.where(np.array(kinds)[:, None] == "roof", [[0, 1.0, 0]], (mid - c) * [1, 0, 1])
    flip = (nrm * want).sum(axis=1) < 0
    tri[flip] = tri[flip][:, ::-1, :]
    return np.round(tri, 3).reshape(-1, 9).tolist(), kinds


def run(b, epoch: str, classes: str, cloud: str):
    out = EXP / "buildings" / str(b["id"]) / epoch / f"{classes}-{cloud}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    stats, poly = prepare(b, epoch, classes, cloud, out)
    t0 = time.time()
    p = subprocess.run(
        [str(ROOFER), "--lod12", "--lod13", "--lod22", "--id-attribute", "id", "--split-cjseq", "-j", "2",
         "cloud.las", "footprint.gpkg", "roofer"],
        cwd=out, capture_output=True, text=True, timeout=1800,
    )
    seconds = time.time() - t0
    (out / "roofer.log").write_text(p.stdout + p.stderr)
    rec = {"id": b["id"], "epoch": epoch, "classes": classes, "cloud": cloud, "prepare": stats, "roofer_seconds": round(seconds, 2),
           "roofer_exit": p.returncode, "roofer": None, "lod22": None, "lod12": None}
    feats = list((out / "roofer").glob("objects/*/reconstruct/*.city.jsonl"))
    if p.returncode == 0 and feats:
        attrs, lods = parse(feats[0], out / "roofer" / "metadata.json")
        rec["roofer"] = attrs
        rec["lod22"], rec["lod12"] = lods.get("2.2"), lods.get("1.2")
    local = Polygon(b["ring"])
    if stats["ground"] is not None and stats["h70"] is not None:
        tri, kind = extrude(local, stats["ground"], stats["h70"])
        rec["height_only"] = {"tri": tri, "kind": kind, "ground": stats["ground"], "top": stats["h70"]}
    else:
        rec["height_only"] = None
    write_json(out / "recon.json", rec, indent=None)
    a = rec["roofer"] or {}
    print(b["id"], epoch, classes, cloud, b["set"], f"{seconds:.1f}s", "roof pts", stats["roof_points"], "promoted", stats["promoted"],
          "| roofer:", a.get("rf_extrusion_mode"), a.get("rf_roof_type"), "planes", a.get("rf_roof_planes"),
          "rmse22", round(a.get("rf_rmse_lod22") or -1, 2), "nodata", round(a.get("rf_nodata_frac") or -1, 2),
          "val", a.get("rf_val3dity_lod22"))
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev")
    ap.add_argument("--classes", default="promote", choices=["asis", "promote", "rescue"])
    ap.add_argument("--epoch", default="both", choices=[FIT_EPOCH, "2025", "both"])
    ap.add_argument("--cloud", default="both", choices=["fit", "all", "both"],
                    help="fit: without the withheld patches (for accuracy checks); all: every point (what ships)")
    args = ap.parse_args()
    sel = read_json(EXP / "selection" / "buildings.json")["buildings"]
    for b in sel:
        if args.set != "all" and b["set"] != args.set:
            continue
        for epoch in dict.fromkeys((FIT_EPOCH, "2025")):
            if args.epoch not in (epoch, "both") or not (EXP / "buildings" / str(b["id"]) / epoch / "fit.las").exists():
                continue
            for cloud in ("fit", "all"):
                if args.cloud in (cloud, "both"):
                    run(b, epoch, args.classes, cloud)


if __name__ == "__main__":
    main()
