"""Contact sheets: one image per building with the references and the three arms."""

from __future__ import annotations

import argparse

from PIL import Image, ImageDraw

from common import EXP, read_json

LABELS = {"ref": "lidar first surface", "current": "1 current generator", "height": "2 measured height", "lod2": "3 measured LoD2 (Roofer)"}


def fit(im, w, h, nearest=False):
    s = min(w / im.width, h / im.height)
    if nearest:
        s = max(1, int(s))
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.NEAREST if nearest else Image.LANCZOS)
    out = Image.new("RGB", (w, h), "white")
    out.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return out


def sheet(b, cell=340):
    d = EXP / "buildings" / str(b["id"])
    cols = ["ortho", "ref", "current", "height", "lod2"]
    rows = ["close", "top", "city"]
    out = Image.new("RGB", (cell * len(cols), (cell + 18) * len(rows) + 22), "white")
    dr = ImageDraw.Draw(out)
    dr.text((6, 4), f"{b['id']}  {b['hood']}  {b['set']}  {','.join(b['flags']) or 'plain'}  {b['area']} m2", fill="black")
    for r, view in enumerate(rows):
        for c, what in enumerate(cols):
            y = 22 + r * (cell + 18)
            if what == "ortho":
                im = Image.open(d / "ortho.png") if r == 0 and (d / "ortho.png").exists() else None
                label = "2025 orthoimage, outline in yellow"
            else:
                p = d / "render" / f"{what}-{view}.png"
                im = Image.open(p) if p.exists() else None
                label = f"{LABELS[what]} · {view}"
            if im is not None:
                out.paste(fit(im.convert("RGB"), cell - 6, cell - 6, nearest=view == "city" and what != "ortho"), (c * cell + 3, y + 16))
                dr.text((c * cell + 6, y + 2), label, fill="black")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev")
    args = ap.parse_args()
    (EXP / "sheets").mkdir(exist_ok=True)
    for b in read_json(EXP / "selection" / "buildings.json")["buildings"]:
        if args.set in ("all", b["set"]) and (EXP / "buildings" / str(b["id"]) / "render").exists():
            sheet(b).save(EXP / "sheets" / f"{b['set']}-{b['hood']}-{b['id']}.png")


if __name__ == "__main__":
    main()
