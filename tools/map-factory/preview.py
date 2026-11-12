"""Render frozen height/water grids. These are not native game screenshots."""

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent


def preview(output):
    manifest = json.loads((ROOT / "fixtures/manifest.json").read_text())
    size, gap, top = 512, 32, 100
    sheet = Image.new(
        "RGB", (3 * size + 4 * gap, 2 * (size + 82) + top + gap), "#111820"
    )
    draw = ImageDraw.Draw(sheet)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    title = ImageFont.truetype(font_path, 28)
    font = ImageFont.truetype(font_path, 18)
    small = ImageFont.truetype(font_path, 15)
    draw.text((gap, 20), "PL-857 / offline grid previews", font=title, fill="#f0ede3")
    draw.text(
        (gap, 60),
        "Not game screenshots. Initial water only; New Game, pathfinding and water stability are unverified.",
        font=font,
        fill="#b5c3cf",
    )
    for index, case in enumerate(manifest["cases"]):
        folder = ROOT / "fixtures" / case["slug"]
        hydro = json.loads(gzip.decompress((folder / "hydrology.json.gz").read_bytes()))
        terrain = (
            np.flipud(
                np.frombuffer(
                    gzip.decompress((folder / "terrain.u16.gz").read_bytes()),
                    dtype="<u2",
                ).reshape(1081, 1081)
            ).astype(float)
            / 64
        )
        depth = (
            np.flipud(
                np.frombuffer(
                    gzip.decompress((folder / "water.u16.gz").read_bytes()), dtype="<u2"
                ).reshape(1081, 1081)
            ).astype(float)
            / 64
        )
        dy, dx = np.gradient(terrain, 16)
        shade = (
            np.clip((2 + dx - dy) / np.sqrt((1 + dx * dx + dy * dy) * 6), 0, 1) * 0.6
            + 0.4
        )
        levels = [0, 80, 200, 450, 1000]
        colors = np.array(
            [
                [122, 123, 107],
                [156, 156, 128],
                [174, 163, 137],
                [187, 179, 163],
                [227, 226, 218],
            ]
        )
        rgb = (
            np.stack(
                [np.interp(terrain, levels, colors[:, i]) for i in range(3)], axis=-1
            )
            * shade[..., None]
        )
        rgb[depth > 0.1] = [39, 127, 167]
        panel = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).resize(
            (size, size), Image.Resampling.LANCZOS
        )
        painter = ImageDraw.Draw(panel)
        spec = json.loads((ROOT / manifest["layout"]).read_text())

        def point(position):
            return (
                (position[0] + 8640) / 17280 * (size - 1),
                (8640 - position[2]) / 17280 * (size - 1),
            )

        for route in spec["routes"]:
            points = [
                point(hydro["node_positions"][str(node)]) for node in route["nodes"]
            ]
            painter.line(
                points,
                fill="#dfbe64" if route["kind"] == "rail" else "#f3e7d4",
                width=2,
            )
        tile = hydro["start_tile"]
        center = [(tile % 5 - 2) * 1920, 0, (tile // 5 - 2) * 1920]
        a = point([center[0] - 960, 0, center[2] + 960])
        b = point([center[0] + 960, 0, center[2] - 960])
        painter.rectangle([a, b], outline="#ff9765", width=2)
        x, y = gap + index % 3 * (size + gap), top + index // 3 * (size + 82)
        sheet.paste(panel, (x, y + 28))
        draw.text(
            (x, y),
            hydro["map_name"].replace(" - Ready to Play", ""),
            font=font,
            fill="#f0ede3",
        )
        draw.text(
            (x, y + size + 36),
            f"Entry: {hydro['road_entry']['edge']} / extra channel cut <= 3 m",
            font=small,
            fill="#b5c3cf",
        )
        draw.text(
            (x, y + size + 57),
            f"{sum(len(p) for p in hydro['samples'].values()):,} initial wet samples / 17.28 km square",
            font=small,
            fill="#b5c3cf",
        )
    x, y = gap + 2 * (size + gap), top + size + 82 + 80
    for text, color in [
        ("Blue: initialized water", "#2780a7"),
        ("White: highway", "#f3e7d4"),
        ("Gold: railway", "#dfbe64"),
        ("Orange: starting tile", "#ff9765"),
    ]:
        draw.text((x, y), text, font=font, fill=color)
        y += 38
    draw.text(
        (x, y + 20), "Terrain and water grids are frozen", font=font, fill="#b5c3cf"
    )
    draw.text(
        (x, y + 50), "in the Python/JavaScript fixtures.", font=font, fill="#b5c3cf"
    )
    sheet.save(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    preview(parser.parse_args().output)
