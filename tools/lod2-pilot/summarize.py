"""One table per building and the acceptance numbers, from the frozen tolerances.

    uv run summarize.py [--classes rescue] [--tag ""]
"""

from __future__ import annotations

import argparse
from collections import Counter

import numpy as np

from common import CLASSES, EXP, read_json, write_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--classes", default=CLASSES)
    ap.add_argument("--tag", default="")
    ap.add_argument("--judge", default="first", help="whose answers fill the judged rows (results/judged-<set>-<judge>.json)")
    args = ap.parse_args()
    sel = read_json(EXP / "selection" / "buildings.json")["buildings"]
    suffix = "" if args.classes == CLASSES else f"-{args.classes}"
    geo = {}
    for s in ("dev", "locked"):
        f = EXP / "results" / f"geometry-{s}{suffix}{args.tag}.json"
        for r in read_json(f) if f.exists() else []:
            geo[r["id"]] = r
    judged = {"ab": [], "topo": []}
    for f in sorted((EXP / "results").glob(f"judged-*-{args.judge}.json")):
        for k, v in read_json(f).items():
            judged[k] += v
    topo = {r["id"]: r for r in judged["topo"]}
    rows = []
    for b in sel:
        if b["id"] not in geo:
            continue
        d = EXP / "buildings" / str(b["id"])
        rec = read_json(d / "2017" / f"{args.classes}-all{args.tag}" / "recon.json")
        a = rec["roofer"] or {}
        held = (geo[b["id"]]["checks"].get("held") or {})
        x25 = (geo[b["id"]]["checks"].get("x2025") or {})
        l = held.get("lod2")
        standard = a.get("rf_extrusion_mode") == "standard" and bool(rec["lod22"])
        geom_pass = bool(standard and l and not held.get("lod2_is_fallback") and l["median_abs"] <= 0.5 and l["within_1"] >= 0.75)
        cur = read_json(d / "current.json")
        rows.append({
            "id": b["id"], "set": b["set"], "hood": b["hood"], "flags": b["flags"], "area": b["area"],
            "current": cur["how"], "current_height_source": "estimate" if cur["estimated"] else "6 m placeholder",
            "class6_delivered": rec["prepare"]["class6_delivered"], "promoted": rec["prepare"]["promoted"],
            "parts": len(rec.get("parts", [])) or 1, "parts_standard": sum(q["standard"] for q in rec.get("parts", [])),
            "roofer_mode": a.get("rf_extrusion_mode"), "roof_type": a.get("rf_roof_type"), "planes": a.get("rf_roof_planes"),
            "seconds": rec["roofer_seconds"], "standard": standard, "geometry_pass": geom_pass, "usable": geom_pass,
            "held": {k: held.get(k) for k in ("current", "height", "lod2")}, "x2025": {k: x25.get(k) for k in ("current", "height", "lod2")} if x25 else None,
            "roof_form": (topo.get(b["id"]) or {}).get("verdict"), "roof_note": (topo.get(b["id"]) or {}).get("note"),
        })
    out = {"rows": rows, "acceptance": {}}
    for name, keep in (("dev", lambda r: r["set"] == "dev"), ("locked", lambda r: r["set"] == "locked"), ("all", lambda r: True)):
        R = [r for r in rows if keep(r)]
        if not R:
            continue
        L = [r["held"]["lod2"] for r in R if r["held"]["lod2"] and r["standard"]]
        ridge = [abs(s["ridge_err"]) <= 1 for s in L if "ridge_err" in s]
        eave = [abs(s["eave_err"]) <= 1 for s in L if "eave_err" in s]
        tv = Counter(r["roof_form"] for r in R if r["roof_form"])
        judgeable = sum(tv.values()) - tv["cannot-judge"]
        acc = {
            "attempts": len(R), "standard_mode": sum(r["standard"] for r in R), "usable": sum(r["usable"] for r in R),
            "usable_share": round(sum(r["usable"] for r in R) / len(R), 3),
            "ridge_within_1m": [sum(ridge), len(ridge)], "eave_within_1m": [sum(eave), len(eave)],
            "roof_form": dict(tv), "roof_form_correct_share": round(tv["correct"] / max(1, judgeable), 3),
            "median_abs_error_m": {arm: round(float(np.median([r["held"][arm]["median_abs"] for r in R if r["held"][arm]])), 2) for arm in ("current", "height", "lod2")},
            "share_within_1m": {arm: round(float(np.mean([r["held"][arm]["within_1"] for r in R if r["held"][arm]])), 2) for arm in ("current", "height", "lod2")},
        }
        X = [r for r in R if r["x2025"] and r["x2025"]["lod2"]]
        if X:
            acc["x2025"] = {"n": len(X)} | {arm: {"median_abs": round(float(np.median([r["x2025"][arm]["median_abs"] for r in X])), 2),
                                                   "within_1": round(float(np.mean([r["x2025"][arm]["within_1"] for r in X])), 2)} for arm in ("current", "height", "lod2")}
        for pair, other in (("h", "height"), ("c", "current")):
            for view in ("city", "close"):
                c = Counter(r["winner"] for r in judged["ab"] if r["pair"] == pair and r["view"] == view and (name == "all" or r["set"] == name))
                if not c:
                    continue
                acc[f"prefer_lod2_over_{other}_{view}"] = {"lod2": c["lod2"], other: c[other], "tie": c["tie"], "share": round(c["lod2"] / max(1, sum(c.values())), 3)}
        out["acceptance"][name] = acc
    who = "" if args.judge == "first" else f"-{args.judge}"
    write_json(EXP / "results" / f"summary{suffix}{args.tag}{who}.json", out)
    import json
    print(json.dumps(out["acceptance"], indent=1))
    print("not usable:", [(r["id"], r["hood"], r["flags"], r["roofer_mode"], (r["held"]["lod2"] or {}).get("median_abs"), (r["held"]["lod2"] or {}).get("within_1")) for r in rows if not r["usable"]])


if __name__ == "__main__":
    main()
