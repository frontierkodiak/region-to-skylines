# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow==13.0.0"]
# ///
"""Freeze explicit foreground masks; never replace real photos with generated views."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("references", type=Path)
    args = parser.parse_args()
    # Normalized hand-traced silhouette masks. Occluding trees remain; no invented pixels.
    outlines = {
        "bungalow": [
            (0.13, 0.40),
            (0.17, 0.17),
            (0.31, 0.20),
            (0.50, 0.06),
            (0.69, 0.18),
            (0.78, 0.34),
            (0.78, 0.76),
            (0.14, 0.76),
        ],
        "storefront": [(0.01, 0.01), (0.72, 0.03), (0.72, 0.85), (0.01, 0.94)],
        "apartment": [
            (0.01, 0.38),
            (0.70, 0.01),
            (0.94, 0.01),
            (0.995, 0.19),
            (0.995, 0.78),
            (0.01, 0.65),
        ],
    }
    records = {}
    for name, polygon in outlines.items():
        suffix = ".webp" if name == "apartment" else ".jpg"
        source = Image.open(args.references / (name + suffix)).convert("RGBA")
        mask = Image.new("L", source.size)
        ImageDraw.Draw(mask).polygon(
            [(int(x * source.width), int(y * source.height)) for x, y in polygon],
            fill=255,
        )
        source.putalpha(mask)
        image = source.crop(mask.getbbox())
        image.thumbnail((768, 768))
        path = args.references / (name + "-input.png")
        image.save(path)
        records[name] = {
            "polygon_normalized": polygon,
            "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": image.size,
            "limitation": "Single occluded real view; unobserved sides and depth are not ground truth.",
        }
    (args.references / "inputs.json").write_text(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
