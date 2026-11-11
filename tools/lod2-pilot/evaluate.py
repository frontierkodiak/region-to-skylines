"""Geometry checks against points the reconstruction never saw.

Two references, kept apart:

- `held`: the withheld 3 m patches of the 2017 cloud. Models are the ones fitted without
  them (`<classes>-fit`).
- `x2025`: the 2025 QL1 tile, a different flight and sensor eight years later. Models are
  the shipped ones fitted to all of 2017 (`<classes>-all`). Only buildings under the tile.

For each arm the model's roof is its upper surface; a reference point's error is its
height minus that surface at the same place (where an arm has no roof over a point, the
ground stands in and the point counts as uncovered). Reference points are roof-labelled
by the same frozen rule as the fitting cloud and thinned to the highest point per 0.5 m
cell, which drops most wall hits. Ridge is the model's highest roof point against the
reference's 99th percentile; eave compares 5th percentiles over points within 1.5 m of
the outline.

    uv run evaluate.py --set dev
"""

from __future__ import annotations

import argparse

import numpy as np
from shapely import contains_xy
from shapely.geometry import Polygon

from common import CLASSES, EXP, FIT_EPOCH, read_json, to_local, write_json
from reconstruct import label_roof, load

ORIGIN_Y = 592.86


def surface(tri: np.ndarray, qx: np.ndarray, qz: np.ndarray) -> np.ndarray:
    """Upper envelope height of triangles (n, 3, 3: x, y, z) at query points; nan where none."""
    out = np.full(len(qx), -np.inf)
    for a, b, c in tri:
        x0, x1 = min(a[0], b[0], c[0]), max(a[0], b[0], c[0])
        z0, z1 = min(a[2], b[2], c[2]), max(a[2], b[2], c[2])
        m = np.flatnonzero((qx >= x0) & (qx <= x1) & (qz >= z0) & (qz <= z1))
        if not len(m):
            continue
        d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
        if abs(d) < 1e-9:
            continue
        w0 = ((b[2] - c[2]) * (qx[m] - c[0]) + (c[0] - b[0]) * (qz[m] - c[2])) / d
        w1 = ((c[2] - a[2]) * (qx[m] - c[0]) + (a[0] - c[0]) * (qz[m] - c[2])) / d
        w2 = 1 - w0 - w1
        ok = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        y = w0 * a[1] + w1 * b[1] + w2 * c[1]
        out[m[ok]] = np.maximum(out[m[ok]], y[ok])
    out[np.isinf(out)] = np.nan
    return out


def roof_tris(tri, kind=None):
    t = np.array(tri, float).reshape(-1, 3, 3)
    if kind is not None:
        return t[np.array(kind) == "roof"]
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    ny = n[:, 1] / np.maximum(np.linalg.norm(n, axis=1), 1e-9)
    return t[ny > 0.05]


def reference(b, epoch, which, classes):
    """Roof-labelled reference points (local x, NAVD88 y, local z), thinned to cell tops."""
    x, y, z, c = load(b["id"], epoch, "all")
    c, poly, ground, inside, _ = label_roof(b, x, y, z, c, classes)
    roof = inside & (c == 6)
    if which == "held":
        xh, yh, zh, _ = load(b["id"], epoch, "held")
        key = set(zip(np.round(xh, 3), np.round(yh, 3), np.round(zh, 3)))
        roof &= np.fromiter(((a, bb, cc) in key for a, bb, cc in zip(np.round(x, 3), np.round(y, 3), np.round(z, 3))), bool, len(x))
    lx, lz = to_local(x[roof], y[roof])
    ly = z[roof]
    if not len(lx):
        return np.zeros((0, 3)), ground
    cell = np.floor(lx / 0.5).astype(np.int64) * 1000003 + np.floor(lz / 0.5).astype(np.int64)
    order = np.lexsort((ly, cell))
    last = np.r_[cell[order][1:] != cell[order][:-1], True]
    k = order[last]
    return np.c_[lx[k], ly[k], lz[k]], ground


def score(tri, R, ground, edge):
    if not len(R):
        return None
    s = surface(tri, R[:, 0], R[:, 2]) if len(tri) else np.full(len(R), np.nan)
    covered = ~np.isnan(s)
    r = R[:, 1] - np.where(covered, s, ground)
    a = np.abs(r)
    out = {
        "n": int(len(R)), "covered": round(float(covered.mean()), 3), "median_abs": round(float(np.median(a)), 3),
        "rmse": round(float(np.sqrt((r**2).mean())), 3), "p90_abs": round(float(np.percentile(a, 90)), 3),
        "within_0.5": round(float((a <= 0.5).mean()), 3), "within_1": round(float((a <= 1.0).mean()), 3),
        "bias": round(float(np.median(r)), 3),
    }
    if len(tri):
        out["ridge_err"] = round(float(tri[:, :, 1].max() - np.percentile(R[:, 1], 99)), 2)
    if edge.sum() >= 8 and covered[edge].sum() >= 8:
        out["eave_err"] = round(float(np.percentile(s[edge & covered], 5) - np.percentile(R[edge & covered, 1], 5)), 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev")
    ap.add_argument("--classes", default=CLASSES)
    ap.add_argument("--tag", default="", help="suffix of the reconstruction folders, for parameter trials")
    args = ap.parse_args()
    rows = []
    for b in read_json(EXP / "selection" / "buildings.json")["buildings"]:
        if args.set != "all" and b["set"] != args.set:
            continue
        d = EXP / "buildings" / str(b["id"])
        cur = read_json(d / "current.json") if (d / "current.json").exists() else {"tri": []}
        cur_tri = roof_tris(cur["tri"]) + [0, ORIGIN_Y, 0] if cur["tri"] else np.zeros((0, 3, 3))
        poly = Polygon(b["ring"])
        row = {"id": b["id"], "hood": b["hood"], "set": b["set"], "flags": b["flags"], "checks": {}}
        for check, epoch, cloud in (("held", FIT_EPOCH, "fit"), ("x2025", "2025", "all")):
            if not (d / epoch / "fit.las").exists():
                continue
            rec = read_json(d / FIT_EPOCH / f"{args.classes}-{cloud}{args.tag}" / "recon.json")
            R, ground = reference(b, epoch, "held" if check == "held" else "all", args.classes)
            if not len(R):
                row["checks"][check] = None
                continue
            edge = ~contains_xy(poly.buffer(-1.5), R[:, 0], R[:, 2])
            g = rec["prepare"]["ground"] if rec["prepare"]["ground"] is not None else ground
            arms = {"current": cur_tri}
            arms["height"] = roof_tris(rec["height_only"]["tri"], rec["height_only"]["kind"]) if rec["height_only"] else np.zeros((0, 3, 3))
            # the joined model; a part Roofer did not reconstruct is already at its measured height in it
            ok = bool(rec["lod22"]) and (rec["roofer"] or {}).get("rf_extrusion_mode") == "standard"
            arms["lod2"] = roof_tris(rec["lod22"]["tri"], rec["lod22"]["kind"]) if rec["lod22"] else arms["height"]
            row["checks"][check] = {k: score(t, R, g, edge) for k, t in arms.items()}
            row["checks"][check]["lod2_is_fallback"] = not ok
        rows.append(row)
        for check, v in row["checks"].items():
            if v:
                print(b["id"], b["set"], check, " | ".join(
                    f"{k}: med {s['median_abs']} rmse {s['rmse']} ≤1m {s['within_1']} ridge {s.get('ridge_err')} eave {s.get('eave_err')}"
                    for k, s in v.items() if isinstance(s, dict)))
    name = "" if args.classes == CLASSES else f"-{args.classes}"
    write_json(EXP / "results" / f"geometry-{args.set}{name}{args.tag}.json", rows)
    for check in ("held", "x2025"):
        for arm in ("current", "height", "lod2"):
            v = [r["checks"][check][arm] for r in rows if r["checks"].get(check) and r["checks"][check].get(arm)]
            if v:
                print(f"{check:6s} {arm:8s} n={len(v):2d} median of medians {np.median([s['median_abs'] for s in v]):.2f} m, "
                      f"median rmse {np.median([s['rmse'] for s in v]):.2f}, mean share within 1 m {np.mean([s['within_1'] for s in v]):.2f}, "
                      f"geometry pass {np.mean([s['median_abs'] <= 0.5 and s['within_1'] >= 0.75 for s in v]):.2f}, ridge within 1 m {np.mean([abs(s.get('ridge_err', 99)) <= 1 for s in v]):.2f}, "
                      f"eave within 1 m {np.mean([abs(s.get('eave_err', 99)) <= 1 for s in v]):.2f}")


if __name__ == "__main__":
    main()
