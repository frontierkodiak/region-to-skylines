"""Top-down maps of a city model (see city.extract) as PNG images.

World axes follow the game: +x east, +z north, metres, map centre at 0.
"""

import math

import numpy as np
from PIL import Image, ImageDraw

GRID = 1081
CELL = 16.0  # metres between terrain samples
HALF = 8640.0

ZONE_RGB = {
    2: (128, 196, 96),
    3: (62, 140, 58),  # residential low / high
    4: (110, 170, 230),
    5: (50, 104, 196),  # commercial low / high
    6: (232, 196, 64),  # industrial
    7: (96, 200, 206),  # office
}
ROAD_STYLE = {
    # category/level: (width m, rgb)
    ("highway", None): (20, (214, 120, 52)),
    ("road", "large"): (16, (90, 90, 98)),
    ("road", "medium"): (13, (104, 104, 112)),
    ("road", "small"): (9, (124, 124, 130)),
    ("rail", None): (6, (128, 74, 138)),
    ("metro", None): (5, (176, 90, 176)),
    ("path", None): (3, (168, 148, 112)),
    ("water", None): (5, (70, 120, 170)),
    ("airport", None): (30, (150, 150, 150)),
}
SERVICE_RGB = {
    "growable": (70, 70, 74),
    "industry": (150, 120, 40),
    "police": (40, 70, 160),
    "fire": (190, 50, 40),
    "health": (210, 70, 110),
    "deathcare": (90, 80, 90),
    "education": (150, 90, 190),
    "electricity": (220, 170, 0),
    "water_service": (40, 140, 200),
    "garbage": (120, 100, 60),
    "transport": (130, 60, 140),
    "monument": (200, 140, 30),
    "park": (60, 150, 70),
    "other": (90, 90, 90),
}
SKIP_SERVICES = {"pillar", "connection", "decoration"}


class Frame:
    """World-to-pixel mapping for a crop of the map."""

    def __init__(self, bounds, width, scale=2):
        x0, z0, x1, z1 = bounds
        self.x0, self.z1 = x0, z1
        self.mpp = (x1 - x0) / width  # metres per output pixel
        self.scale = scale
        self.width = width
        self.height = int(round((z1 - z0) / self.mpp))

    def px(self, x, z):
        s = self.scale
        return ((x - self.x0) / self.mpp * s, (self.z1 - z) / self.mpp * s)

    def size(self):
        return self.width * self.scale, self.height * self.scale


def hillshade(raw, depth, frame):
    """Grey hillshade of the terrain with water, cropped and resampled to the frame."""
    h = raw.astype(np.float32) / 64.0
    gz, gx = np.gradient(h, CELL)
    # light from the north-west, 45 degrees up; rows run south to north
    nx, nz = -gx, gz
    shade = (nx * -0.5 + nz * 0.5 + 1.0) / np.sqrt(nx**2 + nz**2 + 1.0)
    shade = np.clip(0.55 + 0.45 * shade / np.sqrt(1.5), 0, 1)
    x0 = (frame.x0 + HALF) / CELL
    x1 = (frame.x0 + frame.width * frame.mpp + HALF) / CELL
    zt = (HALF - frame.z1) / CELL
    zb = zt + frame.height * frame.mpp / CELL
    box = (x0, zt, x1, zb)

    def resample(grid):
        img = Image.fromarray(np.flipud(grid.astype(np.float32)), mode="F")  # north up
        return np.asarray(img.transform(frame.size(), Image.EXTENT, box, Image.BILINEAR))

    shade = resample(shade)
    # Interpolate the water fraction and cut at one half, so shorelines come out
    # smooth instead of as 16 m steps.
    wet = resample((depth > 16).astype(np.float32)) > 0.5
    rgb = np.array([236, 232, 222], dtype=np.float32) * shade[..., None]
    rgb[wet] = np.array([150, 190, 222]) * (0.85 + 0.15 * shade[wet, None])
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


def _poly(draw, pts, width, fill):
    draw.line(pts, fill=fill, width=max(1, int(round(width))), joint="curve")


def draw_city(img, city, frame, mute=False, zones=True):
    d = ImageDraw.Draw(img, "RGBA")
    s = frame.scale / frame.mpp
    cell = 8 * s
    if zones:
        for x, z, code, _ in city["zone_cells"]:
            rgb = ZONE_RGB.get(code)
            if not rgb:
                continue
            cx, cy = frame.px(x, z)
            r = cell / 2
            a = 90 if mute else 150
            d.rectangle([cx - r, cy - r, cx + r, cy + r], fill=rgb + (a,))
    for b in city["buildings"]:
        if b["service"] in SKIP_SERVICES or b["width"] == 0:
            continue
        rgb = SERVICE_RGB.get(b["service"], SERVICE_RGB["other"])
        if b["service"] == "growable" and b.get("lot_zone") in ZONE_RGB:
            rgb = tuple(int(c * 0.62) for c in ZONE_RGB[b["lot_zone"]])
        if mute:
            rgb = tuple(int(c * 0.45 + 130) for c in rgb)
        d.polygon(footprint(b, frame), fill=rgb + (255,))
    order = [
        "path",
        "water",
        "airport",
        "metro",
        "rail",
        ("road", "small"),
        ("road", "medium"),
        ("road", "large"),
        "highway",
    ]
    for key in order:
        cat, lvl = (key, None) if isinstance(key, str) else key
        width, rgb0 = ROAD_STYLE[(cat, lvl)]
        for seg in city["segments"]:
            if seg["category"] != cat or (lvl and seg["level"] != lvl):
                continue
            rgb = rgb0
            if mute:
                rgb = tuple(int(c * 0.45 + 120) for c in rgb0)
            if seg["original"]:
                # map-made networks are context, not the player's choices
                rgb = tuple(int(c * 0.35 + 165) for c in rgb0)
            if seg["elevation"] == "tunnel" or cat == "metro" and seg["elevation"] != "elevated":
                continue
            _poly(d, [frame.px(x, z) for x, z in seg["points"]], max(width * s, 1.5 * frame.scale), rgb + (255,))


def footprint(b, frame):
    """Lot corners, width x length cells of 8 m around the position, in the
    frame Building.CalculatePosition uses: x along (cos a, sin a), z along
    (sin a, -cos a)."""
    a = b["angle"]
    rx, rz = math.cos(a), math.sin(a)
    fx, fz = math.sin(a), -math.cos(a)
    w, length = b["width"] * 4.0, b["length"] * 4.0
    pts = []
    for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x = b["x"] + sx * w * rx + sz * length * fx
        z = b["z"] + sx * w * rz + sz * length * fz
        pts.append(frame.px(x, z))
    return pts


def render(city, raw, depth, frame, out, previous=None, diff=None):
    """One frame. With `previous` and `diff`, mute what existed before and
    highlight what changed."""
    img = hillshade(raw, depth, frame).convert("RGB")
    if diff is None:
        draw_city(img, city, frame)
    else:
        draw_city(img, previous, frame, mute=True)
        draw_diff(img, diff, frame)
    w, h = img.size
    img = img.resize((w // frame.scale, h // frame.scale), Image.LANCZOS)
    img.save(out, optimize=True)


ADD_RGB = (230, 60, 140)
ZONE_ADD_RGB = (250, 150, 40)
REMOVE_RGB = (30, 30, 30)


def draw_diff(img, diff, frame):
    d = ImageDraw.Draw(img, "RGBA")
    s = frame.scale / frame.mpp
    cell = 8 * s
    for x, z, code in diff["zones_added"]:
        cx, cy = frame.px(x, z)
        r = cell / 2
        rgb = ZONE_RGB.get(code, ZONE_ADD_RGB)
        d.rectangle([cx - r, cy - r, cx + r, cy + r], fill=rgb + (210,))
    for b in diff["buildings_added"]:
        d.polygon(footprint(b, frame), fill=ADD_RGB + (230,))
    for b in diff["buildings_removed"]:
        d.polygon(footprint(b, frame), outline=REMOVE_RGB + (255,), width=max(1, frame.scale))
    for seg in diff["segments_removed"]:
        _poly(d, [frame.px(x, z) for x, z in seg["points"]], max(3 * s, frame.scale), REMOVE_RGB + (200,))
    for seg in diff["segments_added"]:
        width = ROAD_STYLE.get((seg["category"], seg["level"]), (8, None))[0]
        pts = [frame.px(x, z) for x, z in seg["points"]]
        if seg["elevation"] == "tunnel" or seg["category"] == "metro" and seg["elevation"] != "elevated":
            _dashed(d, pts, max(1.2 * frame.scale, 2 * s), ADD_RGB + (200,), 6 * frame.scale)
        else:
            _poly(d, pts, max(width * s, 2 * frame.scale), ADD_RGB + (255,))


def _dashed(draw, pts, width, fill, dash):
    """Underground additions: a thin dashed line."""
    carry, on = 0.0, True
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        t = 0.0
        while t < seg:
            step = min(dash - carry, seg - t)
            if on:
                a, b = t / seg, (t + step) / seg
                draw.line(
                    [(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)],
                    fill=fill,
                    width=max(1, int(width)),
                )
            t += step
            carry += step
            if carry >= dash:
                carry, on = 0.0, not on
