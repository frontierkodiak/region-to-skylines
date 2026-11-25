"""Prepare six anonymous gameplay-distance native pairs, with a separate decoder."""

import argparse
import hashlib
import json
from pathlib import Path
import random

from PIL import Image, ImageOps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_b", type=Path)
    parser.add_argument("native_c2", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("decoder", type=Path, help="keep outside the phone page")
    args = parser.parse_args()
    if args.decoder.resolve().is_relative_to(args.out.resolve()):
        parser.error("Decoder must stay outside the blind page")
    sources = []
    for native, label in ((args.native_b, "bake"), (args.native_c2, "c2")):
        pairs = json.loads((native / "fresh-city/specimens.json").read_text())
        for genus in ("Gleditsia", "Tilia", "Ulmus"):
            stem = f"Kudzu{genus}15{label}"
            pair = next(
                p for p in pairs if p["specimens"][0]["name"].split(".")[0] == stem
            )
            if pair["specimens"][1]["name"].split(".")[0] != f"Kudzu{genus}15sand3d":
                raise ValueError(
                    f"{stem}: expected the frozen A reference, not a substitute"
                )
            source = native / "fresh-city/session/shots" / f"{stem}-gameplay.png"
            if not source.is_file():
                raise ValueError(f"Missing native gameplay shot: {stem}")
            sources.append((source, pair))
    rng = random.Random(1328)
    rng.shuffle(sources)
    args.out.mkdir(parents=True, exist_ok=False)
    decoder, cards = [], []
    for i, (source, pair) in enumerate(sources, 1):
        im = Image.open(source)
        if im.size != (1920, 1080):
            raise ValueError(
                f"Inspect crop before using a new capture resolution: {im.size}"
            )
        # Fixed native pixel crop includes both crowns; no resampling or enhancement.
        im = im.crop((700, 430, 1220, 780))
        mirrored = rng.choice((False, True))
        if mirrored:
            im = ImageOps.mirror(im)
        image_name = f"pair-{i}.png"
        im.save(args.out / image_name)
        physical = list(reversed(pair["specimens"])) if mirrored else pair["specimens"]
        decoder.append(
            {
                "pair": i,
                "left": physical[0]["name"],
                "right": physical[1]["name"],
                "mirrored": mirrored,
                "native_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "crop": [700, 430, 1220, 780],
            }
        )
        cards.append(
            f'<article><h2>Pair {i}</h2><a href="{image_name}"><img src="{image_name}" alt="Tree comparison {i}"></a><select aria-label="Pair {i}" data-pair="{i}"><option value="">Choose…</option><option>Left</option><option>Right</option><option>No preference</option><option>Neither looks usable</option></select></article>'
        )
    args.decoder.write_text(json.dumps(decoder, indent=2) + "\n")
    (args.out / "index.html").write_text(
        """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tree comparisons</title>
<style>body{font:17px/1.5 system-ui;margin:20px;background:#edf0e9;color:#203126;max-width:700px}article{margin:28px 0;padding:12px;background:white}img{width:100%;display:block}select,button{font:inherit;padding:10px;max-width:100%}h1{line-height:1.1}</style>
<h1>Six tree comparisons</h1><p>Which canopy looks better at gameplay distance? Compare shape and texture. Tap an image to enlarge.</p>"""
        + "".join(cards)
        + """<button id="copy">Copy choices</button><p id="result"></p>
<script>const picks=[...document.querySelectorAll('select')];for(const p of picks){p.value=localStorage.getItem('tree-pair-'+p.dataset.pair)||'';p.onchange=()=>localStorage.setItem('tree-pair-'+p.dataset.pair,p.value)}document.querySelector('#copy').onclick=async()=>{const text=picks.map(p=>'Pair '+p.dataset.pair+': '+(p.value||'Unanswered')).join('; ');document.querySelector('#result').textContent=text;try{await navigator.clipboard.writeText(text)}catch{}};</script>"""
    )


if __name__ == "__main__":
    main()
