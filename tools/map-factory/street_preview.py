"""Render an offline road-coverage comparison, not an in-game screenshot."""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from real_roads import _grid


def render(prepared, output):
    hydro = json.loads((prepared / "hydrology.json").read_text())
    graph = hydro["highways"]
    ground, depth = _grid(prepared / "terrain.u16"), _grid(prepared / "water.u16")
    shade = np.clip((ground - np.percentile(ground, 2)) / 900, 0, 1)
    rgb = np.stack([34 + shade * 40, 47 + shade * 38, 48 + shade * 35], axis=2).astype(
        np.uint8
    )
    rgb[depth > 0.1] = [52, 133, 148]
    base = Image.fromarray(rgb).resize((820, 820), Image.Resampling.LANCZOS)
    sheet = Image.new("RGB", (1720, 1060), "#111d23")
    draw = ImageDraw.Draw(sheet)
    title, body = ImageFont.load_default(size=34), ImageFont.load_default(size=23)
    draw.text((30, 18), "Asheville: street import pilot", fill="#f1eee3", font=title)
    draw.text(
        (30, 66),
        "Offline coverage comparison, not an in-game capture.",
        fill="#b9c9cb",
        font=body,
    )
    for column, all_roads in enumerate((False, True)):
        panel = base.copy()
        ink = ImageDraw.Draw(panel)

        def xy(xz):
            return tuple((np.array(xz) * [1, -1] + 8640) / 17280 * 819)

        for e in sorted(graph["edges"], key=lambda e: e["kind"] in ("highway", "ramp")):
            if not all_roads and e["kind"] not in ("highway", "ramp", "rail"):
                continue
            if e["kind"] in ("air", "ship"):
                continue
            a, b = [np.array(graph["nodes"][e[k]]["xyz"])[[0, 2]] for k in ("a", "b")]
            length = np.linalg.norm(b - a)
            p = a + np.array(e["start_dir"])[[0, 2]] * length / 3
            q = b + np.array(e["end_dir"])[[0, 2]] * length / 3
            t = np.linspace(0, 1, 12)[:, None]
            curve = (
                (1 - t) ** 3 * a
                + 3 * (1 - t) ** 2 * t * p
                + 3 * (1 - t) * t**2 * q
                + t**3 * b
            )
            major = e["kind"] in ("highway", "ramp")
            color = (
                "#f8b96c" if major else "#8da9b5" if e["kind"] == "rail" else "#d6e4d9"
            )
            ink.line(
                [xy(point) for point in curve], fill=color, width=2 if major else 1
            )
        ink.rectangle(
            [xy([-4800, 4800]), xy([4800, -4800])], outline="#c0d293", width=2
        )
        x = 30 + column * 850
        sheet.paste(panel, (x, 155))
        draw.text(
            (x, 116),
            "All motor roads in 25 tiles" if all_roads else "Highways and rail only",
            fill="#f1eee3",
            font=body,
        )
    report = hydro["highway_report"]
    draw.text(
        (30, 995),
        f"{report['represented_osm_ways']:,} OSM ways retained. Green box: central 25 tiles. Curves are a provisional model.",
        fill="#b9c9cb",
        font=body,
    )
    draw.text(
        (30, 1025),
        "Data: OpenStreetMap contributors (ODbL). Full-square network is still over the native budget.",
        fill="#b9c9cb",
        font=body,
    )
    sheet.save(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(args.prepared, args.output)
