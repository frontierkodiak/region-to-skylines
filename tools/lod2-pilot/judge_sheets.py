"""Blind judging sheets.

`ab`: references on the left, two unnamed candidates A and B on the right, for two
pairings (measured LoD2 against measured height; measured LoD2 against the current
generator) and two views (city, close). Sides are shuffled per sheet, and sheets carry a
random code instead of the building id. `topo`: references and one unnamed candidate
(measured LoD2) seen from above and obliquely, for the roof-form check. The key that maps
codes back to buildings and arms is written outside the folder judges are given.

    uv run judge_sheets.py [--set dev|locked|all] [--pairs h,c] [--seed N]

Sheets go to `judge/<set>/ab` and `judge/<set>/topo`, the key to `judge-key-<set>.json`.
"""

from __future__ import annotations

import argparse
import random

from PIL import Image, ImageDraw

from common import EXP, read_json, write_json
from sheets import fit

SEED = 900900
PAIRS = {"h": ("lod2", "height"), "c": ("lod2", "current")}


def panel(path, w, h, nearest=False):
    return fit(Image.open(path).convert("RGB"), w, h, nearest=nearest)


def compose(cells, labels, w=330, h=330):
    out = Image.new("RGB", (w * len(cells) + 8 * (len(cells) + 1), h + 30), "white")
    dr = ImageDraw.Draw(out)
    for i, (im, lab) in enumerate(zip(cells, labels)):
        x = 8 + i * (w + 8)
        out.paste(im, (x, 24))
        dr.text((x + 2, 6), lab, fill="black")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="all")
    ap.add_argument("--pairs", default="h,c")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    sel = [b for b in read_json(EXP / "selection" / "buildings.json")["buildings"] if args.set in ("all", b["set"])]
    out = EXP / "judge" / args.set
    (out / "ab").mkdir(parents=True, exist_ok=True)
    (out / "topo").mkdir(parents=True, exist_ok=True)
    key = {"ab": {}, "topo": {}}
    codes = rng.sample(range(1000, 9999), 5 * len(sel))
    for b in sel:
        d = EXP / "buildings" / str(b["id"])
        scene = read_json(d / "scene.json")
        r = d / "render"
        refs = [panel(d / "ortho.png", 330, 330), panel(r / "ref-top.png", 330, 330), panel(r / "ref-close.png", 330, 330)]
        ref_labels = ["REFERENCE: 2025 aerial photo (outline yellow)", "REFERENCE: lidar surface from above", "REFERENCE: lidar surface, oblique"]
        if "height" not in scene["arms"] or "lod2" not in scene["arms"]:
            continue
        for pair, (x, y) in PAIRS.items():
            if pair not in args.pairs.split(",") or y not in scene["arms"]:
                continue
            for view in ("city", "close"):
                code = codes.pop()
                sides = [x, y]
                rng.shuffle(sides)
                cells = refs + [panel(r / f"{s}-{view}.png", 330, 330, nearest=view == "city") for s in sides]
                compose(cells, ref_labels + ["CANDIDATE A", "CANDIDATE B"]).save(out / "ab" / f"{code}.png")
                key["ab"][str(code)] = {"id": b["id"], "pair": pair, "view": view, "A": sides[0], "B": sides[1]}
        code = codes.pop()
        cells = refs + [panel(r / "lod2-top.png", 330, 330), panel(r / "lod2-close.png", 330, 330)]
        compose(cells, ref_labels + ["CANDIDATE from above", "CANDIDATE oblique"]).save(out / "topo" / f"{code}.png")
        key["topo"][str(code)] = {"id": b["id"], "fallback": bool(scene["arms"]["lod2"].get("note"))}
    write_json(EXP / f"judge-key-{args.set}.json", key)
    print(len(key["ab"]), "A/B sheets,", len(key["topo"]), "roof-form sheets")


if __name__ == "__main__":
    main()
