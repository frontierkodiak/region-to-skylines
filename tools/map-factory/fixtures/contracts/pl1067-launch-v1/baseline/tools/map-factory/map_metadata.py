"""Map-derived listing information and deterministic terrain preview images.

These previews render the packaged grids, not a native game screenshot. A
caller can instead supply a genuine capture without changing simulation data.
"""

from io import BytesIO

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


def preview_image(terrain, depth, hydro, spec, capture=None):
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
