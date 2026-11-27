"""Native ranking contact sheet. Display crops do not enter model scoring."""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--font", type=Path, required=True)
    a = p.parse_args()
    result = json.loads((a.run / "ranking.json").read_text())
    plan = json.loads((a.run / "native-v1/plan.json").read_text())
    frames = json.loads((a.run / "native-v1/frames.json").read_text())
    im = Image.new("RGB", (1200, 1770), "#f5f3ee")
    d = ImageDraw.Draw(im)

    def text(x, y, s, size=24, color="#22302c"):
        d.text((x, y), s, fill=color, font=ImageFont.truetype(str(a.font), size))

    passed = sum(r["pass"] for r in result["ranks"])
    text(30, 24, f"Native BioCLIP ranking: {passed}/6 anchor-view checks pass", 34)
    text(
        30, 76, "15 frozen broadleaf controls + one anchor. Pass: ranks 1–4 of 16.", 25
    )
    for x, label in zip(
        (30, 430, 830), ("Close · 52", "Gameplay · 140", "Distant · 550")
    ):
        text(x, 125, label, 27)
    for i, name in enumerate(plan["anchors"]):
        title = name.split(".", 1)[1].replace("_Data", "")
        y = 170 + i * 285
        text(30, y, title, 25)
        for j, view in enumerate(("close", "gameplay", "billboard")):
            f = next(f for f in frames if f["name"] == name and f["view"] == view)
            tree = Image.open(a.run / "native-v1" / f["file"])
            tree = tree.crop((600, 180, 1320, 900)).resize((225, 225))
            x = 30 + j * 400
            im.paste(tree, (x, y + 32))
            if view == "billboard":
                text(x, y + 259, "Not scored by BioCLIP", 21)
            else:
                rank = next(
                    r
                    for r in result["ranks"]
                    if r["name"] == name and r["view"] == view
                )
                color = "#237249" if rank["pass"] else "#a73226"
                text(
                    x,
                    y + 259,
                    f"Rank {rank['rank']}/16 · {'PASS' if rank['pass'] else 'FAIL'}",
                    23,
                    color,
                )
    text(30, 1050, "Highest-scoring controls (not top-1 genus predictions)", 27)
    for i, (genus, view) in enumerate(
        (
            ("Ulmus", "close"),
            ("Ulmus", "gameplay"),
            ("Tilia", "close"),
            ("Tilia", "gameplay"),
        )
    ):
        x = 30 + (i % 2) * 600
        y = 1110 + (i // 2) * 205
        text(x, y, f"{genus} probability · {view}", 25)
        controls = sorted(
            [
                r
                for r in result["rows"]
                if r["name"] in plan["controls"] and r["view"] == view
            ],
            key=lambda r: r["probabilities"][genus],
            reverse=True,
        )
        for k, r in enumerate(controls[:3]):
            label = r["name"].split(".", 1)[1].replace("_Data", "")[:33]
            text(x, y + 42 + k * 35, f"{r['probabilities'][genus]:.3f}  {label}", 21)
    text(
        30,
        1550,
        "One tree per frame; game slot released before inference. No optimisation started.",
        23,
    )
    text(
        30,
        1590,
        "Gleditsia: no vetted Workshop anchor; native ranking remains untested.",
        23,
    )
    text(
        30,
        1630,
        "Display crops only; scoring used full frames with frozen prompts/preprocessing.",
        23,
    )
    text(
        30,
        1670,
        "Probabilities are conditional on Gleditsia/Tilia/Ulmus, not calibrated confidence.",
        23,
    )
    text(
        30,
        1720,
        "PL-1328 · native ranking v1 · PL-1326 source de93357 · 2026-11-27 UTC",
        21,
    )
    im.save(a.out)


if __name__ == "__main__":
    main()
