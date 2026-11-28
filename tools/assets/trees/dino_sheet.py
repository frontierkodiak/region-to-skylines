"""One-sheet comparison of the frozen native BioCLIP and DINOv3 checks."""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("native", type=Path)
    p.add_argument("result", type=Path)
    p.add_argument("audit", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--font", type=Path, required=True)
    a = p.parse_args()
    dino = json.loads(a.result.read_text())
    audit = json.loads(a.audit.read_text())
    frames = json.loads((a.native / "frames.json").read_text())
    anchors = json.loads((a.native / "plan.json").read_text())["anchors"]
    im = Image.new("RGB", (1200, 1370), "#f5f3ee")
    draw = ImageDraw.Draw(im)

    def text(x, y, label, size=24, color="#22302c"):
        draw.text((x, y), label, font=ImageFont.truetype(str(a.font), size), fill=color)

    text(30, 24, "Neither genus judge passes the native ranking gate", 34)
    text(30, 78, "Same 15 controls. Top quarter = rank 1–4 of 16. No CMA-ES.", 25)
    for i, name in enumerate(anchors):
        y = 135 + i * 310
        text(30, y, name.split(".", 1)[1].replace("_Data", ""), 28)
        for j, view in enumerate(("close", "gameplay")):
            f = next(f for f in frames if f["name"] == name and f["view"] == view)
            photo = (
                Image.open(a.native / f["file"])
                .crop((600, 180, 1320, 900))
                .resize((225, 225))
            )
            x = 30 + j * 265
            im.paste(photo, (x, y + 40))
            text(x, y + 268, view.capitalize(), 22)
        text(595, y + 42, "Ranks", 23)
        text(775, y + 42, "BioCLIP", 24)
        text(985, y + 42, "DINOv3", 24)
        for k, view in enumerate(("close", "gameplay")):
            text(595, y + 100 + k * 65, view.capitalize(), 22)
            for x, rows in ((775, audit["bioclip_ranks"]), (985, dino["ranks"])):
                r = next(r for r in rows if r["name"] == name and r["view"] == view)
                text(
                    x,
                    y + 100 + k * 65,
                    f"{r['rank']}/16",
                    30,
                    "#237249" if r["pass"] else "#a73226",
                )
    text(
        30,
        1080,
        "Control audit: no elm or linden in creator titles / exact prefab identities.",
        24,
    )
    text(
        30,
        1120,
        "DINOv3 ViT-L/16: mean target-photo cosine minus other-genus means.",
        24,
    )
    text(
        30,
        1160,
        "12 reserved iNat photos; frozen official 224px processor; full native frames.",
        24,
    )
    text(
        30,
        1215,
        "Next fitness: crown shape + gap fraction + leaf colour; Caleb’s blind pairs.",
        25,
    )
    text(
        30,
        1260,
        "Not implemented or optimised here. Whole-crown reference QA is still needed.",
        23,
    )
    text(
        30,
        1320,
        "PL-1328 · 2026-11-27 · Display crops only; no new game slot or paid calls.",
        21,
    )
    im.save(a.out)


if __name__ == "__main__":
    main()
