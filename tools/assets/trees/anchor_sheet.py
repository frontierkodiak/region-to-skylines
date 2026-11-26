"""One-sheet display of the frozen anchor probe; crops never enter the scorer."""

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
    rows = json.loads((a.run / "results.json").read_text())["rows"]
    sheet = Image.new("RGB", (1200, 1770), "#f5f3ee")
    draw = ImageDraw.Draw(sheet)

    def text(x, y, s, size=24, color="#222b29"):
        draw.text((x, y), s, font=ImageFont.truetype(str(a.font), size), fill=color)

    text(35, 25, "BioCLIP anchor test: stop before optimisation", 36)
    text(35, 80, "Workshop renders 4/9 correct. Reserved iNaturalist photos 12/12.", 25)
    for x, label in zip(
        (35, 425, 815), ("Close · 52", "Gameplay · 140", "Distant · 550*")
    ):
        text(x, 130, label, 27)
    for i, (item, name, genus) in enumerate(
        (
            ("2456536855", "American Elm", "Ulmus"),
            ("2928288862", "Kaiserlinde 16m", "Tilia"),
            ("2402946167", "Bigleaf Linden", "Tilia"),
        )
    ):
        y = 180 + i * 310
        text(35, y, f"{name}  /  expected {genus}", 25)
        for j, view in enumerate(("close", "gameplay", "billboard")):
            row = next(
                r for r in rows if r.get("title") == name and r.get("view") == view
            )
            x = 35 + j * 390
            im = Image.open(a.run / "offline-v4" / item / (view + ".png"))
            # Same fixed display window at every distance; no per-tree auto-crop.
            im = im.crop((600, 180, 1320, 900)).resize((240, 240))
            sheet.paste(im, (x, y + 35))
            color = "#237249" if row["correct"] else "#a73226"
            text(
                x,
                y + 278,
                f"{row['predicted']} · P({genus}) {row['probabilities'][genus]:.2f}",
                22,
                color,
            )
    text(35, 1130, "Photo check: Gleditsia 3/3 · Tilia 6/6 · Ulmus 3/3", 27)
    text(
        35, 1170, "Small, unbalanced pilot; photos have not passed whole-crown QA.", 23
    )
    for x, genus in ((35, "Ulmus"), (615, "Tilia")):
        native = Image.open(a.run / "native-evidence" / (genus + "-close.png"))
        native = native.crop((230, 200, 820, 850)).resize((220, 242))
        sheet.paste(native, (x, 1230))
        item = "2456536855" if genus == "Ulmus" else "2928288862"
        offline = Image.open(a.run / "offline-v4" / item / "close.png")
        offline = offline.crop((600, 180, 1320, 900)).resize((242, 242))
        sheet.paste(offline, (x + 230, 1230))
        text(x, 1480, f"{genus}: accepted game capture / offline", 22)
    text(
        35,
        1530,
        "Silhouettes/alpha checked; offline colour and lighting do not match the game.",
        23,
    )
    text(35, 1570, "Scoring used full 1920×1080 frames, not these display crops.", 23)
    text(
        35,
        1610,
        "* Distant view projects the main mesh; it is not the native billboard shader.",
        23,
    )
    text(
        35,
        1650,
        "Three-way probabilities are conditional, not calibrated confidence.",
        23,
    )
    text(
        35,
        1700,
        "PL-1328 · 2026-11-26 · Sources: accepted PL-1326 / PR103 de93357; Cabinet pilot v1",
        20,
    )
    sheet.save(a.out)


if __name__ == "__main__":
    main()
