# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow==13.0.0", "numpy==2.5.4"]
# ///
"""Produce deterministic control materials and slice the generated hybrid atlas."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--hybrid", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(881)
    colors = {
        "siding": (223, 211, 154),
        "brick": (137, 76, 53),
        "roof": (60, 63, 65),
        "stone": (124, 119, 107),
        "trim": (222, 220, 205),
        "glass": (40, 63, 73),
        "door": (87, 59, 40),
        "awning": (48, 64, 106),
        "cream": (188, 183, 151),
    }
    periods = {
        "siding": (512, 64),
        "brick": (128, 42),
        "roof": (128, 96),
        "stone": (170, 125),
    }
    source = Image.open(args.hybrid).convert("RGB")
    w, h = source.size
    quadrants = {
        "siding": (0, 0, w // 2, h // 2),
        "brick": (w // 2, 0, w, h // 2),
        "roof": (0, h // 2, w // 2, h),
        "stone": (w // 2, h // 2, w, h),
    }
    for material, color in colors.items():
        noise = rng.normal(0, 2.5, (512, 512, 1))
        pixels = np.clip(np.array(color)[None, None, :] + noise, 0, 255).astype(
            np.uint8
        )
        image = Image.fromarray(pixels)
        draw = ImageDraw.Draw(image)
        if material in periods:
            dx, dy = periods[material]
            for row, y in enumerate(range(0, 512, dy)):
                draw.line((0, y, 512, y), fill=(75, 72, 64), width=2)
                for x in range(-dx, 512, dx):
                    xx = x + (row % 2) * dx // 2
                    if material != "siding":
                        draw.line((xx, y, xx, y + dy), fill=(91, 84, 73), width=2)
        for method in ("A", "C"):
            folder = args.output / method
            folder.mkdir(exist_ok=True)
            diffuse = (
                source.crop(quadrants[material]).resize((512, 512))
                if (method == "C" and material in quadrants)
                else image
            )
            diffuse.save(folder / f"{material}_d.png")
            spec = 230 if material == "glass" else 10
            variation = 80 if material in ("siding", "trim", "door", "awning") else 0
            illumination = 255 if material == "glass" else 0
            for channel, value in (("s", spec), ("c", variation), ("i", illumination)):
                Image.new("RGB", (32, 32), (value,) * 3).save(
                    folder / f"{material}_{channel}.png"
                )
    manifest = {
        "seed": 881,
        "hybrid_sha256": hashlib.sha256(args.hybrid.read_bytes()).hexdigest(),
        "quadrants": quadrants,
        "hybrid_generator": "Codex built-in image_gen; exact model and billing not exposed",
        "cost": "Subscription generation; zero incremental API invoice observed, not a zero economic cost claim",
        "scale_m": {
            "siding": [1.5, 1.4],
            "brick": [1.6, 0.9],
            "roof": [2.0, 1.2],
            "stone": [1.5, 1.2],
        },
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
