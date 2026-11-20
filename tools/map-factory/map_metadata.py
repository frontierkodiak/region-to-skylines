"""Map-derived listing information and deterministic terrain preview images.

These previews render the packaged grids, not a native game screenshot. A
caller can instead supply a genuine capture without changing simulation data.
"""

from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps


def buildable_area(terrain, water_amount, max_resource_amount):
    """Reproduce the installed CS1 save-panel flatness score, not a slope cutoff.

    Heights are native 1/64-metre integers. Each 16-metre quad contributes a
    quantized inverse-square height-range weight. The installed game's
    GetUnlockableTerrainFlatness/GetTileFlatness compose two +2 tile offsets;
    preserve that native score rather than silently substitute a new metric.
    Water totals, unlike this flatness quirk, use the central 25 resource tiles.
    """
    grid = np.asarray(terrain, dtype=np.int64).reshape(1081, 1081)
    corners = [grid[:-1, :-1], grid[1:, :-1], grid[:-1, 1:], grid[1:, 1:]]
    span = np.minimum(np.maximum.reduce(corners) - np.minimum.reduce(corners), 32768)
    weight = 512 * 4096 // (512 + span * span // 512)
    patches = weight.reshape(9, 120, 9, 120).mean(axis=(1, 3)) / 4096
    flatness = float(patches[4:9, 4:9].mean())
    dry_fraction = 1 - water_amount / max_resource_amount
    return int(np.clip(np.floor(flatness * dry_fraction * 100), 0, 100))


def preview_image(terrain, depth, hydro, spec, capture=None, square=False):
    """Render north-up terrain, water and actual fitted transport corridors."""
    size = (1800, 1008)
    if capture is not None:
        with Image.open(capture) as source:
            return ImageOps.fit(source.convert("RGB"), size, Image.Resampling.LANCZOS)
    height = np.flipud(np.asarray(terrain).reshape(1081, 1081)).astype(float) / 64
    water = np.flipud(np.asarray(depth).reshape(1081, 1081)) > 6
    dz, dx = np.gradient(height, 16)
    shade = 0.45 + 0.55 * np.clip(
        (2 + dx - dz) / np.sqrt(6 * (1 + dx * dx + dz * dz)), 0, 1
    )
    low, high = np.quantile(height, [0.02, 0.98])
    relative = np.clip((height - low) / max(1, high - low), 0, 1)
    colors = np.array([[134, 158, 110], [166, 164, 123], [211, 207, 190]])
    rgb = (
        np.stack(
            [np.interp(relative, [0, 0.55, 1], colors[:, i]) for i in range(3)], axis=-1
        )
        * shade[..., None]
    )
    rgb[water] = [44, 125, 164]
    image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(image)

    def point(position):
        return ((position[0] + 8640) / 16, (8640 - position[2]) / 16)

    for route in spec.get("routes", []):
        positions = hydro.get("node_positions", {})
        if all(str(node) in positions for node in route["nodes"]):
            draw.line(
                [point(positions[str(node)]) for node in route["nodes"]],
                fill="#dfbe64" if route["kind"] == "rail" else "#f3e7d4",
                width=2,
            )
    # Wide framing includes the entire central 25-tile playable square, without
    # distorting the geography or padding the listing with an empty black panel.
    if square:
        return image
    band = image.height * size[1] / size[0]
    return image.crop((0, (1081 - band) / 2, 1081, (1081 + band) / 2)).resize(
        size, Image.Resampling.LANCZOS
    )


def texture_payload(name, image):
    """Uncompressed PNG-backed native Texture asset (package format 12)."""
    import struct

    from crp import string

    stream = BytesIO()
    image.save(stream, format="PNG", compress_level=9)
    png = stream.getvalue()
    typename = (
        "ColossalFramework.Importers.Image, ColossalManaged, Version=0.3.0.0, "
        "Culture=neutral, PublicKeyToken=null"
    )
    return (
        b"\0"
        + string(typename)
        + string(name)
        + struct.pack("<?ii", False, 1, len(png))
        + png
    )


def listing_fields(package_path):
    """Read the actual packaged MapMetaData, not an estimated UI score."""
    from crp import Reader, metadata_value, read_package

    _, assets = read_package(package_path.read_bytes())
    reader = Reader(next(a["payload"] for a in assets if a["kind"] == 100))
    reader.number("B")
    reader.string()
    reader.string()
    fields = {}
    for _ in range(reader.number("i")):
        if reader.number("B"):
            continue
        typename, name = reader.string().split(",")[0], reader.string()
        fields[name] = metadata_value(reader, typename)
    return fields


def launch_preview(output, receipt):
    """One shareable image of the final packaged grids and listing values."""
    import json
    from PIL import ImageFont

    terrain = np.fromfile(output / "terrain.u16", dtype="<u2").reshape(1081, 1081)
    depth = np.fromfile(output / "water.u16", dtype="<u2").reshape(1081, 1081)
    hydro = json.loads((output / "hydrology.json").read_text())
    spec = json.loads(
        (Path(__file__).parent / "templates/native-corridors.json").read_text()
    )
    fields = listing_fields(output / (hydro["map_id"] + ".crp"))
    sheet = Image.new("RGB", (1200, 1510), "#f4f3eb")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=24)
    small = ImageFont.load_default(size=20)
    draw.text((30, 18), hydro["map_name"], fill="#26382a", font=font)
    main = preview_image(terrain, depth, hydro, spec, square=True).resize((860, 860))
    painter = ImageDraw.Draw(main)
    for k in range(1, 9):
        pos = round(k * 860 / 9)
        painter.line((pos, 0, pos, 860), fill="#ffffff", width=1)
        painter.line((0, pos, 860, pos), fill="#ffffff", width=1)
    tile = hydro["start_tile"]
    x, y = (tile % 5 + 2) * 860 / 9, (6 - tile // 5) * 860 / 9
    painter.rectangle((x, y, x + 860 / 9, y + 860 / 9), outline="#ff8b20", width=4)
    sheet.paste(main, (30, 62))
    lines = [
        "DAYLIGHT TOP-DOWN",
        "Initial water in blue",
        "Roads white / rail gold",
        "Orange: starting tile",
        "",
        f"Buildable: {fields['buildableArea']}%",
        f"Start tile: {tile}",
        "",
        "Outside connections",
    ]
    for label, key in [
        ("Road in", "incomingRoads"),
        ("Road out", "outgoingRoads"),
        ("Rail in", "incomingTrainTracks"),
        ("Rail out", "outgoingTrainTracks"),
        ("Ship in", "incomingShipPath"),
        ("Ship out", "outgoingShipPath"),
        ("Air in", "incomingPlanePath"),
        ("Air out", "outgoingPlanePath"),
    ]:
        lines.append(f"{label}: {fields.get(key, 0)}")
    resources = receipt.get("resources") or {}
    budget = resources.get("tree_budget", {})
    lines += [
        "",
        f"Trees: {budget['planted']:,}" if budget else "Trees: not measured",
        f"Planting room: {budget['planting_headroom']:,}"
        if budget
        else "Planting room: unknown",
        "",
        "Vanilla: choose 9 of 25",
        "Mods: 25 / 81 tiles",
    ]
    for k, line in enumerate(lines):
        draw.text((915, 65 + k * 31), line, fill="#26382a", font=small)
    heights = np.flipud(terrain).astype(float) / 64
    rel = (heights - heights.min()) / max(1, float(np.ptp(heights)))
    height_image = Image.fromarray(np.uint8(rel * 255)).convert("RGB")
    water_image = Image.fromarray(np.uint8(np.flipud(depth) > 6) * 255).convert("RGB")
    resource_image = (
        Image.open(output / "resources.png")
        if (output / "resources.png").exists()
        else Image.new("RGB", (360, 360), "#e1e2d8")
    )
    for x, image, label in [
        (30, resource_image, "Resources" if resources else "Resources not planned"),
        (420, water_image, "Initial water"),
        (810, height_image, "Height"),
    ]:
        sheet.paste(image.resize((360, 360)), (x, 970))
        draw.text((x, 936), label, fill="#26382a", font=font)
    captions = [
        "Resources: forest green / fertile yellow / ore red / oil black.",
        f"Height: {heights.min():.0f}-{heights.max():.0f} game metres. Water overlay: white is wet.",
        "Rendered from packaged grids, not a game screenshot. Initial water is not a stability test.",
        "Terrain: AWS / Mapzen. Water and roads: © OpenStreetMap contributors.",
        "Land cover: ESA WorldCover 2021 (CC BY 4.0). Minerals: USGS MRDS.",
    ]
    for k, text in enumerate(captions):
        draw.text((30, 1340 + k * 29), text, fill="#26382a", font=small)
    sheet.save(output / "preview.png")
    return {
        key: fields[key]
        for key in fields
        if key not in ("mods", "assetRef", "imageRef", "steamPreviewRef")
    }
