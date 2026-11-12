# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow==13.0.0", "numpy==2.5.4"]
# ///
"""Turn the archived white-background AI concept controls into explicit RGBA inputs."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    records = {}
    for name in ("bungalow", "storefront", "apartment"):
        path = args.directory / (name + ".png")
        image = Image.open(path).convert("RGB")
        pixels = np.asarray(image)
        white = np.all(pixels > 245, axis=2)
        flood = Image.fromarray((white * 255).astype(np.uint8)).copy()
        for corner in (
            (0, 0),
            (image.width - 1, 0),
            (0, image.height - 1),
            (image.width - 1, image.height - 1),
        ):
            ImageDraw.floodfill(flood, corner, 128, thresh=0)
        alpha = Image.fromarray(
            np.where(np.asarray(flood) == 128, 0, 255).astype(np.uint8)
        )
        if alpha.getextrema() != (0, 255):
            raise ValueError(f"{name}: foreground/background separation failed")
        image = image.convert("RGBA")
        image.putalpha(alpha)
        image = image.crop(alpha.getbbox())
        image.thumbnail((1024, 1024))
        output = args.directory / (name + "-input.png")
        image.save(output)
        records[name] = {
            "concept_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "input_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "background_rule": "RGB >245 and connected to an image corner",
            "source": "AI-generated photo-informed interpretation, NOT a real photo or survey",
        }
    (args.directory / "manifest.json").write_text(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
