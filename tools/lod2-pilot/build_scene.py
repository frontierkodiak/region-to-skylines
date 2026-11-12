"""Assemble what the renderer and the judges see for each pilot building.

Writes `<building>/scene.json`: the three arms as triangles in one frame (metres, x east,
y up from the lidar ground beside the outline, z south, origin at the outline's centroid),
the ground around the building (1 m grid from lidar ground points), a reference surface
(0.5 m first-surface grid from an epoch's full cloud; the 2025 tile where it covers the
building, because the reconstruction is fitted to 2017), the outline, and the wall
material. Also fetches the spring-2025 6-inch orthoimage chip as `ortho.png`.

    uv run build_scene.py --set dev
"""

from __future__ import annotations

import argparse
import io

import laspy
import numpy as np
import requests
from PIL import Image, ImageDraw
from scipy.interpolate import NearestNDInterpolator
from shapely.geometry import Polygon

from common import EXP, FIT_EPOCH, FTUS, ORTHO_2025, WORK_EPSG, read_json, to_local, to_work, write_json

ORIGIN_Y = 592.86  # pixel-asheville's elevation origin, NAVD88 m
MARGIN = 14.0


def cloud(bid, epoch):
    parts = []
    for name in ("fit", "held"):
        p = EXP / "buildings" / str(bid) / epoch / f"{name}.las"
        if p.exists():
            las = laspy.read(p)
            x, z = to_local(np.asarray(las.x), np.asarray(las.y))
            parts.append(np.c_[x, np.asarray(las.z), z, np.asarray(las.classification)])
    return np.vstack(parts) if parts else None


def grid(P, x0, z0, nx, nz, cell, how):
    i = np.floor((P[:, 0] - x0) / cell).astype(int)
    j = np.floor((P[:, 2] - z0) / cell).astype(int)
    ok = (i >= 0) & (i < nx) & (j >= 0) & (j < nz)
    i, j, y = i[ok], j[ok], P[ok, 1]
    out = np.full((nz, nx), np.nan)
    if how == "max":
        order = np.argsort(y)
        out[j[order], i[order]] = y[order]
        return out, ok, (j, i)
    s = np.zeros((nz, nx))
    n = np.zeros((nz, nx))
    np.add.at(s, (j, i), y)
    np.add.at(n, (j, i), 1)
    out[n > 0] = s[n > 0] / n[n > 0]
    return out, ok, (j, i)


def fill(a):
    if np.isnan(a).all():
        return np.zeros_like(a)
    jj, ii = np.nonzero(~np.isnan(a))
    f = NearestNDInterpolator(np.c_[jj, ii], a[jj, ii])
    J, I = np.mgrid[0 : a.shape[0], 0 : a.shape[1]]
    return np.where(np.isnan(a), f(J, I), a)


def ortho(b, half, path):
    cx, cz = Polygon(b["ring"]).centroid.coords[0]
    e, n = to_work(cx, cz)
    e, n, h = e / FTUS, n / FTUS, half / FTUS
    r = requests.get(
        ORTHO_2025 + "/exportImage",
        params={"bbox": f"{e - h},{n - h},{e + h},{n + h}", "bboxSR": 6543, "imageSR": 6543, "size": "640,640",
                "format": "png", "bandIds": "0,1,2", "f": "image"},
        timeout=120,
    )
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    im.save(path.with_name("ortho_plain.png"))
    d = ImageDraw.Draw(im)
    s = 640 / (2 * half)
    d.line([((x - cx + half) * s, (z - cz + half) * s) for x, z in b["ring"]], fill=(255, 220, 0), width=2)
    im.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev")
    ap.add_argument("--classes", default="promote")
    args = ap.parse_args()
    for b in read_json(EXP / "selection" / "buildings.json")["buildings"]:
        if args.set != "all" and b["set"] != args.set:
            continue
        d = EXP / "buildings" / str(b["id"])
        rec = read_json(d / FIT_EPOCH / f"{args.classes}-all" / "recon.json")
        cur = read_json(d / "current.json") if (d / "current.json").exists() else {"tri": [], "ground": 0}
        poly = Polygon(b["ring"])
        cx, cz = poly.centroid.coords[0]
        g0 = rec["prepare"]["ground"]
        if g0 is None:
            g0 = cur["ground"] + ORIGIN_Y

        def shift(tri, dy):
            t = np.array(tri, float).reshape(-1, 3) - [cx, dy, cz]
            return np.round(t, 3).reshape(-1).tolist()

        arms = {}
        t = np.array(cur["tri"], float).reshape(-1, 3, 3)
        if len(t):
            nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
            ny = nrm[:, 1] / np.maximum(np.linalg.norm(nrm, axis=1), 1e-9)
            arms["current"] = {"tri": shift(cur["tri"], g0 - ORIGIN_Y), "kind": ["roof" if v > 0.35 else "wall" for v in ny],
                               "note": cur["how"]}
        if rec["height_only"]:
            arms["height"] = {"tri": shift(rec["height_only"]["tri"], g0), "kind": rec["height_only"]["kind"]}
        usable = bool(rec["lod22"]) and (rec["roofer"] or {}).get("rf_extrusion_mode") == "standard"
        if usable:
            keep = [k for k, kind in enumerate(rec["lod22"]["kind"]) if kind != "ground"]
            tri = np.array(rec["lod22"]["tri"]).reshape(-1, 9)[keep]
            arms["lod2"] = {"tri": shift(tri.reshape(-1).tolist(), g0), "kind": [rec["lod22"]["kind"][k] for k in keep]}
        elif "height" in arms:
            arms["lod2"] = arms["height"] | {"note": "fallback: height-only"}

        x0, z0, x1, z1 = poly.bounds
        half = max(x1 - x0, z1 - z0) / 2 + MARGIN
        P17 = cloud(b["id"], FIT_EPOCH)
        P25 = cloud(b["id"], "2025")
        ref_epoch = "2025" if P25 is not None else FIT_EPOCH
        P = P25 if P25 is not None else P17
        P = P - [cx, g0, cz, 0]
        G = P17 - [cx, g0, cz, 0]
        n1 = int(np.ceil(2 * half))
        dtm, _, _ = grid(G[G[:, 3] == 2], -half, -half, n1, n1, 1.0, "mean")
        dtm = fill(dtm)
        n2 = n1 * 2
        Q = P[~np.isin(P[:, 3], (7, 18))]
        dsm, ok, (j, i) = grid(Q, -half, -half, n2, n2, 0.5, "max")
        order = np.argsort(Q[ok, 1])
        cls = np.zeros((n2, n2), int)
        c = Q[ok, 3][order]
        cls[j[order], i[order]] = np.where(c == 2, 0, np.where(np.isin(c, (3, 4, 5)), 1, 2))
        hole = np.isnan(dsm)
        up = np.kron(dtm, np.ones((2, 2)))
        dsm = np.where(hole, up, dsm)
        cls[hole] = 0
        if WORK_EPSG == 6542:  # the NC orthoimage only covers North Carolina
            ortho(b, half, d / "ortho.png")
        scene = {
            "id": b["id"], "hood": b["hood"], "set": b["set"], "flags": b["flags"], "half": round(half, 2),
            "ring": [[round(x - cx, 3), round(z - cz, 3)] for x, z in b["ring"]],
            "wall": cur.get("wall") or "siding", "roof_rgb": cur.get("roof_rgb"),
            "ground_y": g0, "centre": [cx, cz], "fit_epoch": FIT_EPOCH, "reference_epoch": ref_epoch,
            "arms": arms,
            "dtm": {"n": n1, "cell": 1.0, "y": np.round(dtm, 2).reshape(-1).tolist()},
            "dsm": {"n": n2, "cell": 0.5, "y": np.round(dsm, 2).reshape(-1).tolist(), "cls": cls.reshape(-1).tolist()},
        }
        write_json(d / "scene.json", scene, indent=None)
        print(b["id"], b["set"], "arms", {k: len(v["kind"]) for k, v in arms.items()}, "ref", ref_epoch, "half", round(half, 1))


if __name__ == "__main__":
    main()
