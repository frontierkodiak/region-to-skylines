"""Unblind the judges' answers and count them.

    uv run score_judges.py [--set dev|locked|all] [--judge first|second]

Reads `judge/<set>/results-<judge>/{ab,topo}-*.json`, writes `results/judged-<set>-<judge>.json`.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from common import EXP, read_json, write_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="all")
    ap.add_argument("--judge", default="first")
    args = ap.parse_args()
    key = read_json(EXP / f"judge-key-{args.set}.json")
    answers = EXP / "judge" / args.set / f"results-{args.judge}"
    sel = {b["id"]: b for b in read_json(EXP / "selection" / "buildings.json")["buildings"]}
    ab, topo = [], []
    for f in sorted(answers.glob("ab-*.json")):
        for a in json.loads(f.read_text()):
            k = key["ab"][str(a["code"])]
            won = "tie" if a["choice"] == "tie" else k[a["choice"]]
            ab.append({**k, "code": a["code"], "winner": won, "confidence": a.get("confidence"), "reason": a.get("reason"),
                       "set": sel[k["id"]]["set"], "hood": sel[k["id"]]["hood"]})
    for f in sorted(answers.glob("topo-*.json")):
        for a in json.loads(f.read_text()):
            k = key["topo"][str(a["code"])]
            topo.append({**k, **a, "set": sel[k["id"]]["set"], "hood": sel[k["id"]]["hood"], "flags": sel[k["id"]]["flags"]})
    write_json(EXP / "results" / f"judged-{args.set}-{args.judge}.json", {"ab": ab, "topo": topo})
    names = {"h": "LoD2 vs height-only", "c": "LoD2 vs current generator"}
    for sets in (("dev",), ("locked",), ("dev", "locked")):
        if not any(r["set"] in sets for r in ab + topo) or (len(sets) == 2 and len({r["set"] for r in ab + topo}) < 2):
            continue
        print("==", "+".join(sets))
        for pair in ("h", "c"):
            for view in ("city", "close"):
                rows = [r for r in ab if r["pair"] == pair and r["view"] == view and r["set"] in sets]
                if not rows:
                    continue
                c = Counter(r["winner"] for r in rows)
                n = len(rows)
                other = "height" if pair == "h" else "current"
                print(f"{names[pair]:26s} {view:5s} n={n:2d}  LoD2 {c['lod2']:2d} ({c['lod2'] / n:.0%})  {other} {c[other]:2d}  tie {c['tie']:2d}")
                for hood in ("montford", "downtown"):
                    hc = Counter(r["winner"] for r in rows if r["hood"] == hood)
                    hn = sum(hc.values())
                    print(f"    {hood:9s} LoD2 {hc['lod2']:2d}/{hn}  {other} {hc[other]:2d}  tie {hc['tie']:2d}")
        rows = [r for r in topo if r["set"] in sets]
        c = Counter(r["verdict"] for r in rows)
        judgeable = len(rows) - c["cannot-judge"]
        print(f"roof form (LoD2): {dict(c)}; correct {c['correct']}/{judgeable} judgeable ({c['correct'] / max(1, judgeable):.0%}), "
              f"correct or partly {(c['correct'] + c['partly']) / max(1, judgeable):.0%}")
        for hood in ("montford", "downtown"):
            print("   ", hood, dict(Counter(r["verdict"] for r in rows if r["hood"] == hood)))


if __name__ == "__main__":
    main()
