# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow==13.0.0"]
# ///
"""Build a source-backed, portable image comparison and static review page."""

import argparse
import html
import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFont, ImageOps


NAMES = {
    "bungalow": "Norwood bungalow",
    "storefront": "Lexington storefront",
    "apartment": "Hillcrest-style row",
}
METHODS = [
    ("A", "Procedural"),
    ("B0", "Image-to-3D · photo"),
    ("B1", "Image-to-3D · concept"),
    ("C", "Hybrid"),
]
VIEWS = ("close", "gameplay", "lod", "night")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    images = args.destination / "images"
    images.mkdir(exist_ok=True)
    font = (
        ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        if Path("/System/Library/Fonts/Helvetica.ttc").exists()
        else ImageFont.load_default(size=20)
    )
    data = []
    reference_manifest = json.loads(
        (args.experiment / "references/manifest.json").read_text()
    )
    figures = []
    for name, title in NAMES.items():
        cards = []
        for key, label in METHODS:
            method = "B" if key.startswith("B") else key
            root = args.experiment / ("outputs-clean" if key == "B1" else "outputs")
            folder = root / (method + "-" + name)
            receipt = json.loads((folder / "receipt.json").read_text())
            model = None
            if method == "B":
                model_path = (
                    args.experiment
                    / ("trellis-clean" if key == "B1" else "trellis")
                    / "receipt.json"
                )
                model = json.loads(model_path.read_text())["assets"][name]
            scores_path = root / "clef.json"
            scores = json.loads(scores_path.read_text()) if scores_path.exists() else {}
            score = (
                scores.get(method + "-" + name + "-close", {})
                .get("response", {})
                .get("answers", {})
                .get("reference_fidelity", {})
                .get("score")
            )
            seconds = receipt["generation_seconds"] + (
                model["total_seconds"] if model else 0
            )
            row = {
                "target": name,
                "method": key,
                "main_triangles": receipt["main"]["triangles"],
                "lod_triangles": receipt["lod"]["triangles"],
                "model_and_prepare_seconds": seconds,
                "render_seconds": receipt["render_seconds"],
                "clef_close_ordinal_0_4": score,
                "dimensions_m": receipt["main"]["dimensions_m"],
                "extra_imagegen_calls": 1
                if key == "B1"
                else (1 / 3 if key == "C" else 0),
                "imagegen_seconds": "not exposed/measured; excluded, not zero",
                "money": "Local owned GPU/CPU; no external 3D API. Image-gen subscription billing not exposed.",
            }
            data.append(row)
            for view in VIEWS:
                shutil.copyfile(
                    folder / (view + ".png"),
                    images / (name + "-" + key + "-" + view + ".png"),
                )
            cards.append(
                f"<figure><figcaption><b>{key}</b> {html.escape(label)}</figcaption>"
                f'<img class="candidate" data-prefix="{name}-{key}" src="images/{name}-{key}-close.png" '
                f'alt="{html.escape(title + " — " + label)}">'
                f"<small>{row['main_triangles']:,} triangles · LOD {row['lod_triangles']} · "
                f"{seconds:.1f}s model + prepare</small></figure>"
            )
        suffix = ".webp" if name == "apartment" else ".jpg"
        photo = args.experiment / "references" / (name + suffix)
        naip = args.experiment / "references" / (name + "-naip.png")
        shutil.copyfile(photo, images / (name + "-photo" + suffix))
        shutil.copyfile(naip, images / (name + "-naip.png"))
        link = html.escape(reference_manifest[name]["source"], quote=True)
        figures.append(
            f'<section><h2>{html.escape(title)}</h2><div class="grid">'
            + "".join(cards)
            + f'</div><details><summary>Real photo and NAIP context</summary><div class="references">'
            f'<figure><img src="images/{name}-photo{suffix}" alt="Real photographic reference">'
            f'<figcaption><a href="{link}">Photo source</a> · reference only, not a survey</figcaption></figure>'
            f'<figure><img src="images/{name}-naip.png" alt="USGS NAIP aerial context">'
            "<figcaption>USGS NAIP · address-centred neighbourhood context; not a measured footprint</figcaption>"
            "</figure></div></details></section>"
        )
    for view in VIEWS:
        cell = 384
        canvas = Image.new("RGB", (cell * 4, cell * 3 + 148), (246, 245, 241))
        draw = ImageDraw.Draw(canvas)
        draw.text(
            (18, 12),
            "Asheville building bake-off — " + view,
            font=font,
            fill=(25, 35, 35),
        )
        draw.text(
            (18, 40),
            "Blender proxy, not CS1. B1 uses an AI-interpreted clean view; B0 uses the real photo.",
            font=font,
            fill=(55, 65, 65),
        )
        for col, (key, label) in enumerate(METHODS):
            draw.text(
                (col * cell + 12, 78), key + " · " + label, font=font, fill=(25, 35, 35)
            )
            for row, (name, title) in enumerate(NAMES.items()):
                img = Image.open(
                    images / (name + "-" + key + "-" + view + ".png")
                ).convert("RGB")
                canvas.paste(img.resize((cell, cell)), (col * cell, 120 + row * cell))
                draw.text(
                    (col * cell + 8, 122 + row * cell),
                    title,
                    font=font,
                    fill=(255, 255, 255),
                    stroke_width=1,
                    stroke_fill=(30, 40, 40),
                )
        canvas.save(args.destination / (view + "-comparison.png"))
    # The reference sheet is kept on the private review surface, not committed to the public repo.
    refs = Image.new("RGB", (1200, 720), (246, 245, 241))
    draw = ImageDraw.Draw(refs)
    for col, (name, title) in enumerate(NAMES.items()):
        suffix = ".webp" if name == "apartment" else ".jpg"
        draw.text((col * 400 + 10, 8), title, font=font, fill=(25, 35, 35))
        for row, filename in enumerate((name + "-photo" + suffix, name + "-naip.png")):
            img = Image.open(images / filename).convert("RGB")
            refs.paste(ImageOps.contain(img, (400, 320)), (col * 400, 40 + row * 340))
    refs.save(args.destination / "references.png")
    rows = "".join(
        f"<tr><td>{r['target']}</td><td>{r['method']}</td><td>{r['main_triangles']:,}</td>"
        f"<td>{r['lod_triangles']}</td><td>{r['model_and_prepare_seconds']:.1f}</td>"
        f"<td>{r['render_seconds']:.1f}</td><td>{r['clef_close_ordinal_0_4']:.2f}</td></tr>"
        for r in data
    )
    page = (
        """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Asheville building bake-off</title><link rel="icon" href="data:,"><style>
body{font:16px/1.5 system-ui,sans-serif;background:#f6f5f1;color:#182b2b;margin:0;padding:24px}main{max-width:1600px;margin:auto}
h1{font-size:clamp(28px,4vw,44px);letter-spacing:-.04em;margin:0}p{max-width:90ch}section{margin:32px 0}
.controls{position:sticky;top:0;display:flex;gap:8px;background:#f6f5f1ef;padding:12px 0;z-index:2;flex-wrap:wrap}
button{font:inherit;padding:8px 18px;border:1px solid #a7b8b3;border-radius:6px;background:white;cursor:pointer}
button[aria-pressed=true]{background:#173e38;color:white}button:focus-visible,a:focus-visible{outline:3px solid #be6f2d;outline-offset:3px}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}figure{margin:0;background:white;border:1px solid #d4ded7}
figcaption,small{display:block;padding:8px 10px}img{display:block;width:100%;height:auto}.references{display:grid;grid-template-columns:1fr 1fr;gap:12px;max-width:900px}
details{margin:12px 0}summary{cursor:pointer}table{border-collapse:collapse;min-width:700px}td,th{padding:8px 14px;border-bottom:1px solid #ccd7d0;text-align:left}
.table{overflow:auto}a{color:#125a4b}@media(max-width:800px){body{padding:14px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.references{grid-template-columns:1fr}}
</style><main><h1>Asheville building bake-off</h1>
<p><strong>Blender proxy, not an in-game verdict.</strong> Same three building types, matched camera, light and lot envelopes. A and C share geometry. B0 is direct-photo TRELLIS.2; B1 adds a clean, AI-interpreted view first. Unseen sides are inferred, not surveyed.</p>
<p><strong>Provisional choice: C for repeatable neighbourhood stock.</strong> B1 recovers richer details than B0, but still needs topology and window-mask repair. C preserves editable geometry and a predictable footprint at much lower triangle cost. A and C are near-tied at gameplay distance; C's visible improvement is mainly close up. No landmark or prop was tested, so that part of the original hypothesis remains open.</p>
<div class="controls" role="group" aria-label="View">"""
        + "".join(
            f'<button data-view="{view}" aria-pressed="{str(view == "close").lower()}">{view.title()}</button>'
            for view in VIEWS
        )
        + """</div>"""
        + "".join(figures)
        + """
<h2>Measured work</h2><p>Seconds separate model/export preparation from four preview renders. Image generation, downloads, compilation and model loading are excluded here, not zero. Clef's 0–4 ordinal expectations are advisory, uncalibrated, and do not certify visual quality.</p>
<div class="table"><table><thead><tr><th>Target</th><th>Method</th><th>Main tris</th><th>LOD tris</th><th>Model + prepare s</th><th>Render s</th><th>Clef close /4</th></tr></thead><tbody>"""
        + rows
        + """</tbody></table></div>
<p>A: no image-generation calls. C: one shared material-atlas call across three assets. B1: one concept call per asset. All 3D inference ran on owned local hardware; electricity, subscription allocation and exact image-generation billing/time were not measured. B has no automatic semantic night-window mask; its illumination and colour-variation maps deliberately disable those effects. Normal maps are neutral in every arm. Scale is a study envelope in metres, not a measured digital twin.</p>
<p>Reference photos: PSABC; Stilfehler / Wikimedia Commons (<a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>, Lexington photo); Asheville Housing Authority. Aerial imagery: USGS NAIP. Original photo rights remain with their owners. The generated assets are distinct from the reference imagery.</p>
<script src="app.js"></script></main></html>"""
    )
    (args.destination / "index.html").write_text(page)
    (args.destination / "app.js").write_text(
        """document.querySelectorAll('[data-view]').forEach(button=>{button.addEventListener('click',()=>{document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));document.querySelectorAll('.candidate').forEach(img=>{img.src='images/'+img.dataset.prefix+'-'+button.dataset.view+'.png';});});});"""
    )
    (args.destination / "measurements.json").write_text(json.dumps(data, indent=2))
    expected = [
        images / (name + "-" + key + "-" + view + ".png")
        for name in NAMES
        for key, _ in METHODS
        for view in VIEWS
    ]
    assert all(
        path.is_file() and Image.open(path).size == (768, 768) for path in expected
    )
    print(
        f"Report verified: {len(expected)} actual preview images plus six reference images"
    )


if __name__ == "__main__":
    main()
