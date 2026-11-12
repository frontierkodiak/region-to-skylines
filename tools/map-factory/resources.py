"""Natural resources and trees for a generated CS1 map.

Plans trees, forest, fertile land, ore and oil from land cover, terrain, water
and optional mineral/well evidence, then encodes the native
NaturalResourceManager and TreeManager sections and the New Game metadata
amounts. All grids here are south-first ([z, x], row 0 at z = -8640), the
frame of the native terrain and water arrays.

Native rules this follows (CS1 1.21.1-f9, see knowledge games/):
- Forest is not painted. TreeManager sets a 33.75 m cell's forest and tree
  bytes to min(60 x grown trees in the cell, 255), and zeroes its fertility.
- Ore and oil displace each other in a cell; so do fertility and sand.
- New Game shows the sum over the 25 central tiles of each resource, against
  maxResourceAmount (25 tiles x 3236.4 cells x 255).
"""

import json
import math
import struct
from dataclasses import asdict, dataclass, field

import numpy as np
from scipy import ndimage

RES, CELL, HALF = 512, 33.75, 8640.0
TREE_UNIT = 0.26367188  # metres per TreeInstance.m_posX step
TREE_SLOTS = 262143  # TreeManager buffer minus the reserved index 0
GROWN_TREE = 0x0F01  # Created | GrowState 15, as TreeManager.CreateTree sets
LC_STEP = 10.0

# WorldCover class -> relative tree density. Forest gets the budget; open
# classes get scattered trees and hedgerow, so they don't read as bare.
TREE_WEIGHT = {10: 1.0, 95: 1.0, 20: 0.35, 90: 0.15, 30: 0.03, 100: 0.05, 60: 0.02, 40: 0.0}
# WorldCover class -> fertile share. Pasture and hay land is farmland too.
FERTILE_WEIGHT = {40: 1.0, 30: 0.7, 90: 0.3, 20: 0.15}

# Original-release tree prefabs only (the set CO's 2015 maps use, data
# versions 244-320), so a player without DLC loses no trees. What loads
# depends on the map theme: shipped Sunny maps never use the conifers, which
# belong to the North and Europe themes; only Tropical has palms; Bush02 is
# Sunny and Tropical. Winter (Snowfall) has its own set and isn't covered.
THEMES = {
    "Sunny": {
        "broadleaf": [("Beech01low", 5), ("Tree2variant", 3), ("Tree3variant", 3)],
        "riparian": [("Alder01", 1)],
        "scrub": [("Bush01", 1), ("Bush02", 1)],
    },
    "North": {
        "broadleaf": [("Tree3variant", 2), ("Beech01low", 1)],
        "riparian": [("Alder01", 1)],
        "conifer": [("treeForest", 5), ("Conifer", 3), ("Conifer2", 2), ("Pine01low", 2)],
        "scrub": [("Bush01", 1)],
    },
    "Europe": {
        "broadleaf": [("Tree3variant", 3), ("Tree2variant", 2), ("Beech01low", 1)],
        "riparian": [("Alder01", 1)],
        "conifer": [("Pine01low", 4), ("Conifer2", 2), ("treeForest", 1)],
        "scrub": [("Bush01", 1)],
    },
    "Tropical": {
        "broadleaf": [("Beech01low", 3), ("palm01", 3), ("Tree2variant", 2), ("Tree3variant", 1)],
        "riparian": [("palmplant01", 1), ("palm01", 1)],
        "scrub": [("palmplant01", 2), ("Bush01", 1), ("Bush02", 1)],
    },
}
TREE_NAMES = sorted({name for theme in THEMES.values() for pool in theme.values() for name, _ in pool})


def theme_of(template_bytes):
    """The template's MapMetaData environment: it decides which trees load."""
    from crp import Reader, metadata_value, read_package

    _, assets = read_package(template_bytes)
    r = Reader(next(a["payload"] for a in assets if a["kind"] == 100))
    r.number("B"), r.string(), r.string()
    for _ in range(r.number("i")):
        if r.number("B"):
            continue
        typename, name = r.string().split(",")[0], r.string()
        value = metadata_value(r, typename)
        if name == "environment":
            return value
    raise ValueError("Template metadata has no environment")


@dataclass
class Knobs:
    """The few choices a map-maker would want; defaults need no touching."""

    trees: int = 180_000  # editor cap 250,000; leaves the player ~70k to plant
    outer_trees: float = 0.6  # tree density outside the 25 buyable tiles
    # "open": trees spread over all tree cover in stands and glades (1-2 per
    # 33.75 m cell). "dense": close-packed stands (~4 per cell) on forested
    # slopes, ridges and stream corridors, leaving buildable flats open.
    forest: str = "open"
    oil_cap: float = 0.07  # well-derived oil stays under this New Game share
    resources: str = "balanced"  # "real": evidence only; "balanced": top up
    fertile: float = 1.0  # scales fertile land from crop and pasture cover
    seed: int = 0
    # "balanced" tops each resource up to its New Game share (amount over
    # maxResourceAmount). Defaults are the official maps' medians, as the
    # community reads them: ore 5.2 %, oil 2.7 %, fertile land 3.4 %.
    targets: dict = field(default_factory=lambda: {"ore": 0.052, "oil": 0.027, "fertile": 0.034})


def cell_centres():
    return (np.arange(RES) + 0.5) * CELL - HALF


def tile_index():
    """Area tile of each resource row/column, as SimulationStepImpl2 bins it."""
    return (np.arange(RES) * 18) >> 10


def resample(grid, step, out_size, out_step, order=1):
    """Resample a south-first square grid with cell size `step` (first sample
    at -HALF + step/2) onto another, by grid-centre coordinates."""
    centres = (np.arange(out_size) + 0.5) * out_step - HALF
    idx = (centres + HALF) / step - 0.5
    zz, xx = np.meshgrid(idx, idx, indexing="ij")
    return ndimage.map_coordinates(grid, [zz, xx], order=order, mode="nearest")


def node_grid(values, out_size, out_step):
    """Sample a 1081 vertex grid (16 m, first vertex at -HALF) at cell centres."""
    centres = (np.arange(out_size) + 0.5) * out_step - HALF
    idx = (centres + HALF) / 16.0
    zz, xx = np.meshgrid(idx, idx, indexing="ij")
    return ndimage.map_coordinates(values, [zz, xx], order=1, mode="nearest")


def smooth_noise(shape, scale_px, rng):
    """Zero-mean, unit-std noise with features about `scale_px` cells wide."""
    field_ = ndimage.gaussian_filter(rng.standard_normal(shape), scale_px, mode="wrap")
    return (field_ - field_.mean()) / (field_.std() + 1e-9)


def network_mask(positions, segments, out_size, out_step, width):
    """Cells within `width` metres of a fitted network segment."""
    mask = np.zeros((out_size, out_size), bool)
    for segment in segments:
        a = positions.get(str(segment["from"]))
        b = positions.get(str(segment["to"]))
        if a is None or b is None:
            continue
        length = math.hypot(b[0] - a[0], b[2] - a[2])
        for t in np.linspace(0, 1, max(2, int(length / (out_step / 2)) + 1)):
            x, z = a[0] + (b[0] - a[0]) * t, a[2] + (b[2] - a[2]) * t
            c, r = int((x + HALF) / out_step), int((z + HALF) / out_step)
            if 0 <= r < out_size and 0 <= c < out_size:
                mask[r, c] = True
    return ndimage.binary_dilation(mask, iterations=max(1, int(math.ceil(width / out_step))))


def slope_percent(terrain):
    gz, gx = np.gradient(terrain, 16.0)
    return np.hypot(gx, gz) * 100


def blob(x0, z0, radius, size=RES, step=CELL):
    centres = cell_centres() if size == RES else (np.arange(size) + 0.5) * step - HALF
    dz = (centres[:, None] - z0) / radius
    dx = (centres[None, :] - x0) / radius
    d = np.hypot(dx, dz)
    return np.clip(1.5 - 1.5 * d, 0, 1) ** 0.7  # flat core, soft rim


def plan(terrain, depth, landcover, layout, hydro, evidence, knobs, theme="Sunny"):
    """Return resource grids (512², south-first) and the tree list.

    terrain, depth: 1081² south-first metres. landcover: 1728² south-first
    WorldCover classes. layout/hydro: template layout and the region's fitted
    network positions and start tile. evidence: list of {"kind": "ore"|"oil",
    "x", "z", "weight", "source"} in game metres.
    """
    rng = np.random.default_rng(knobs.seed)
    wet16 = depth > 0
    slope = slope_percent(terrain)
    positions = hydro.get("node_positions", {})
    segments = layout.get("segments", [])
    start_tile = hydro.get("start_tile", 12)
    sx, sz = start_tile % 5 + 2, start_tile // 5 + 2  # tile in the 9x9 grid

    lc = landcover
    lc_wet = node_grid(wet16.astype(float), lc.shape[0], LC_STEP) > 0.25
    lc_road = network_mask(positions, segments, lc.shape[0], LC_STEP, 18)

    # Fertile land first: farms need flat, open, dry ground, and a cell with a
    # tree loses its fertility, so trees stay off the fields we keep.
    fert_px = np.zeros(lc.shape, float)
    for cls, w in FERTILE_WEIGHT.items():
        fert_px[lc == cls] = w
    fert_px[lc_wet | lc_road] = 0
    fert = resample(fert_px, LC_STEP, RES, CELL, order=1)
    cell_slope = node_grid(slope, RES, CELL)
    cell_wet = node_grid(wet16.astype(float), RES, CELL) > 0.5
    flat = np.clip((14 - cell_slope) / 8, 0, 1)  # full below 6 %, none above 14 %
    suit = ndimage.gaussian_filter(np.clip(fert * 1.6 * knobs.fertile, 0, 1) * flat, 2.0)
    # Shipped maps have a few coherent fields (median 0.7 km2), not specks:
    # close gaps, drop pieces under ~0.05 km2, ramp up from a soft rim.
    mask = ndimage.binary_opening(ndimage.binary_closing(suit > 0.22, iterations=2))
    mask &= ~cell_wet & ~network_mask(positions, segments, RES, CELL, 24)
    labels, n = ndimage.label(mask)
    sizes = np.bincount(labels.ravel(), minlength=n + 1)
    mask &= sizes[labels] >= 40
    inward = (ndimage.distance_transform_edt(mask) - 1).clip(0) * CELL
    # Real valleys are narrower than shipped maps' plains, so ramp faster.
    value = 50 + 205 * (1 - np.exp(-inward / 75))  # ~200 at 100 m
    fertility = np.where(mask, value * np.clip(0.65 + suit, 0.65, 1), 0)
    placed = []
    if knobs.resources == "balanced":
        placed += top_up_fertile(fertility, cell_slope, cell_wet, positions, segments, sx, sz, knobs, rng, node_grid(terrain, RES, CELL), lc)
    fertility = np.floor(fertility + 0.5).astype(np.uint8)

    # Trees: weight by cover, cluster into stands and glades, and keep them out
    # of water, off the networks and off the fields.
    cover = np.zeros(lc.shape, float)
    for cls, v in TREE_WEIGHT.items():
        cover[lc == cls] = v
    fertile_px = resample(fertility.astype(float), CELL, lc.shape[0], LC_STEP, order=0) > 0
    # Trees touching water die, and vanilla keeps them off rock faces.
    cover[ndimage.binary_dilation(lc_wet) | lc_road | fertile_px] = 0
    cover *= np.clip((60 - node_grid(slope, lc.shape[0], LC_STEP)) / 15, 0, 1)
    # Makers spend the budget inside the 25 buyable tiles (1920 m each).
    centres = (np.arange(lc.shape[0]) + 0.5) * LC_STEP - HALF
    inner = np.abs(centres) < 2.5 * 1920
    outer_px = ~(inner[:, None] & inner[None, :])
    trees = []
    if knobs.forest == "dense" and knobs.trees > 0 and cover.sum() > 0:
        rows, cols, x, z = dense_stands(cover, cell_slope, cell_wet, fertility, positions, segments, terrain, knobs, rng, (sx, sz))
        trees = finish_trees(rows, cols, x, z, lc, terrain, wet16, slope, rng, theme)
    # Stands and glades: 262k trees can't carpet a real forest, so put them
    # where they read as woods (shipped maps: ~2 trees per 33.75 m forest cell).
    w = cover.copy()
    stands = 0.65 * smooth_noise(lc.shape, 7, rng) + 0.35 * smooth_noise(lc.shape, 25, rng)
    w *= np.clip(0.35 + 0.9 * stands, 0, None)
    w[outer_px] *= knobs.outer_trees
    total = w.sum()
    if knobs.forest == "open" and knobs.trees > 0 and total > 0:
        lo, hi = 0.0, 1e6
        for _ in range(60):  # expected count = budget, each pixel at most one tree
            k = (lo + hi) / 2
            if np.minimum(1, k * w).sum() > knobs.trees:
                hi = k
            else:
                lo = k
        p = np.minimum(1, lo * w)
        rows, cols = np.nonzero(rng.random(lc.shape) < p)
        if len(rows) > knobs.trees:
            keep = rng.choice(len(rows), knobs.trees, replace=False)
            rows, cols = rows[np.sort(keep)], cols[np.sort(keep)]
        x = (cols + rng.random(len(cols))) * LC_STEP - HALF
        z = (rows + rng.random(len(rows))) * LC_STEP - HALF
        # A 10 m pixel can straddle a 33.75 m cell edge: drop trees that land
        # in a field cell, since one tree would erase that cell's fertility.
        keep = fertility[(z / CELL + 256).astype(int).clip(0, RES - 1), (x / CELL + 256).astype(int).clip(0, RES - 1)] == 0
        trees = finish_trees(rows[keep], cols[keep], x[keep], z[keep], lc, terrain, wet16, slope, rng, theme)

    forest, tree = forest_cells(trees)
    fertility[forest > 0] = 0

    # Ore and oil: patches from evidence, shaped to terrain the way shipped maps
    # place them, then topped up in "balanced" mode.
    ore = np.zeros((RES, RES))
    oil = np.zeros((RES, RES))
    used = []
    for e in evidence:
        if e["kind"] == "well":
            continue
        r = 260 + 340 * min(1.0, e.get("weight", 1.0))
        target = ore if e["kind"] == "ore" else oil
        np.maximum(target, np.clip(1.3 * blob(e["x"], e["z"], r), 0, 1), out=target)
        used.append({**e, "radius_m": r})
    rugged = np.clip(0.7 + cell_slope / 40, 0.7, 1)  # ore reads as hills
    level = np.clip((24 - cell_slope) / 12, 0.7, 1)  # oil reads as plains
    # Players punish resources they can't build on: peaks, cliffs, water and
    # land already under the outside-connection roads.
    usable = np.clip((40 - cell_slope) / 10, 0, 1) * ~cell_wet * ~network_mask(positions, segments, RES, CELL, 24)
    shape = {"ore": rugged * usable, "oil": level * usable}
    wells = [(e["x"], e["z"]) for e in evidence if e["kind"] == "well"]
    if wells:
        field_, threshold = well_oil(np.array(wells), shape["oil"], knobs)
        np.maximum(oil, field_, out=oil)
        used.append({"kind": "oil", "source": f"NETL WELLS: density of {len(wells)} oil and gas wells", "wells_per_km2_threshold": round(threshold, 3)})
    if knobs.resources == "balanced":
        placed += top_up(ore, oil, cell_slope, cell_wet, shape, sx, sz, knobs, rng, node_grid(terrain, RES, CELL), fertility)
    ore = np.floor(ore * shape["ore"] * 255 + 0.5)
    oil = np.floor(oil * shape["oil"] * 255 + 0.5)
    ore[cell_wet] = 0
    oil[cell_wet] = 0
    both = (ore > 0) & (oil > 0)  # ChangeMaterial: one displaces the other
    ore[both & (oil > ore)] = 0
    oil[both & (ore >= oil)] = 0
    return {
        "ore": ore.astype(np.uint8),
        "oil": oil.astype(np.uint8),
        "fertility": fertility,
        "forest": forest,
        "tree": tree,
        "trees": trees,
        "evidence": used,
        "placed": placed,
    }


def finish_trees(rows, cols, x, z, lc, terrain, wet16, slope, rng, theme):
    """Quantize positions, keep them off cell edges, and pick species."""
    px = np.clip(np.round(x / TREE_UNIT), -32767, 32767).astype(np.int16)
    pz = np.clip(np.round(z / TREE_UNIT), -32767, 32767).astype(np.int16)
    # 128 position steps are exactly one 33.75 m cell, and TreesModified
    # counts a tree on a boundary in both cells; keep trees off them.
    px[px % 128 == 0] += 1
    pz[pz % 128 == 0] += 1
    kinds = species(px, pz, lc[rows, cols], terrain, wet16, slope, rng, theme)
    return (px, pz, kinds)


def dense_stands(cover, cell_slope, cell_wet, fertility, positions, segments, terrain, knobs, rng, start=(4, 4), per_cell=4, woods=5):
    """Close-packed stands, ~4 trees per 33.75 m cell, on tree cover the player
    can't easily build on (slopes over ~8 %, ridges, stream corridors), so the
    buildable flats stay open. A few forestry woods (~0.4 km2 each) also go on
    buildable, tree-covered ground nearest the start: forestry industry needs
    forest where it can build. Returns tree pixel rows/cols and positions."""
    step = LC_STEP
    cell_cover = resample(cover, step, RES, CELL)
    height = node_grid(terrain, RES, CELL)
    relief = height - ndimage.uniform_filter(height, 31)
    water_d = ndimage.distance_transform_edt(~cell_wet) * CELL
    unbuildable = np.maximum.reduce([
        np.clip((cell_slope - 8) / 12, 0, 1),
        np.clip(1 - water_d / 90, 0, 1) * (cell_cover > 0.2),
        np.clip(relief / 40, 0, 1),
    ])
    tiles = tile_index()
    inner = (tiles >= 2) & (tiles <= 6)
    central = inner[:, None] & inner[None, :]
    centres = cell_centres()
    sx_m, sz_m = (start[0] - 4) * 1920, (start[1] - 4) * 1920
    d_start = np.hypot(centres[None, :] - sx_m, centres[:, None] - sz_m)
    flat = (cell_slope < 10) & ~cell_wet & (fertility == 0)
    site = ndimage.uniform_filter(cell_cover * flat, 19) * np.clip(1.4 - d_start / 6000, 0.3, 1.4)
    site[~central] = 0
    for _ in range(woods):
        if site.max() <= 0.05:
            break
        r0, c0 = np.unravel_index(np.argmax(site), site.shape)
        d = np.hypot(centres[None, :] - centres[c0], centres[:, None] - centres[r0])
        unbuildable[(d < 360) & (cell_cover > 0.1)] = 1.0
        site[d < 1800] = 0
    score = cell_cover * (0.06 + 0.94 * unbuildable)
    score *= np.clip(1 + 0.25 * smooth_noise((RES, RES), 3, rng), 0.5, 1.5)
    score = ndimage.gaussian_filter(score, 1.0)
    score[~central] *= knobs.outer_trees
    blocked = cell_wet | (fertility > 0) | network_mask(positions, segments, RES, CELL, 18) | (cell_cover <= 0.02)
    score[blocked] = 0
    k = min(knobs.trees // per_cell, int(np.count_nonzero(score)))
    chosen = np.argsort(score.ravel(), kind="stable")[::-1][:k]
    counts = np.full(k, per_cell)
    counts[: min(k, knobs.trees - per_cell * k)] += 1  # spend the remainder on the best cells
    cell = np.repeat(chosen, counts)
    r, c = cell // RES, cell % RES
    best_x = best_z = None
    found = np.zeros(len(cell), bool)
    x = np.zeros(len(cell))
    z = np.zeros(len(cell))
    side = cover.shape[0]
    for _ in range(6):  # a few tries to land on a tree-cover pixel in the cell
        tx = (c + 0.02 + 0.96 * rng.random(len(cell))) * CELL - HALF
        tz = (r + 0.02 + 0.96 * rng.random(len(cell))) * CELL - HALF
        pr = np.clip(((tz + HALF) / step).astype(int), 0, side - 1)
        pc = np.clip(((tx + HALF) / step).astype(int), 0, side - 1)
        ok = ~found & (cover[pr, pc] > 0)
        x[ok], z[ok] = tx[ok], tz[ok]
        found |= ok
    x, z = x[found], z[found]
    rows = np.clip(((z + HALF) / step).astype(int), 0, side - 1)
    cols = np.clip(((x + HALF) / step).astype(int), 0, side - 1)
    return rows, cols, x, z


def well_oil(wells, shape, knobs):
    """Oil fields from well density: wells per km2 under a 600 m kernel, ramped
    from a threshold that rises until the field fits under the oil cap."""
    counts = np.zeros((RES, RES))
    c = np.clip(((wells[:, 0] + HALF) / CELL).astype(int), 0, RES - 1)
    r = np.clip(((wells[:, 1] + HALF) / CELL).astype(int), 0, RES - 1)
    np.add.at(counts, (r, c), 1)
    density = ndimage.gaussian_filter(counts, 600 / CELL) * (1e6 / CELL**2)
    tiles = tile_index()
    inner = (tiles >= 2) & (tiles <= 6)
    buildable = inner[:, None] & inner[None, :]
    maximum = 25 * 3686400 / 1139.0625 * 255
    threshold = 0.3
    for _ in range(40):
        field_ = np.clip((density - threshold) / (2.5 * threshold), 0, 1) ** 0.8
        amount = (np.floor(field_ * shape * 255 + 0.5) * buildable).sum()
        if amount <= knobs.oil_cap * maximum:
            break
        threshold *= 1.25
    return field_, threshold


def top_up_fertile(fertility, cell_slope, cell_wet, positions, segments, sx, sz, knobs, rng, height, lc):
    """Add fields until fertile land reaches its share: flat, low, open ground
    near water, nearest the start tile first (shipped maps have fertile land
    in the start tile on 91 of 104). Trees are planned after, around them."""
    tiles = tile_index()
    tz, tx = np.meshgrid(tiles, tiles, indexing="ij")
    buildable = (tx >= 2) & (tx <= 6) & (tz >= 2) & (tz <= 6)
    centres = cell_centres()
    maximum = 25 * 3686400 / 1139.0625 * 255
    built = resample((lc == 50).astype(float), LC_STEP, RES, CELL) > 0.5
    relief = height - ndimage.uniform_filter(height, 31)
    water_d = ndimage.distance_transform_edt(~cell_wet) * CELL
    sx_m, sz_m = (sx - 4.5 + 0.5) * 1920, (sz - 4.5 + 0.5) * 1920
    d_start = np.hypot(centres[None, :] - sx_m, centres[:, None] - sz_m)
    score = (
        np.clip((8 - cell_slope) / 8, 0, 1) * 2
        + np.clip(1 - water_d / 1200, 0, 1)
        + np.clip(-relief / 30, -0.5, 0.5)
        + np.clip(1 - d_start / 5000, 0, 1)
    )
    score = ndimage.uniform_filter(score, 9)
    blocked = cell_wet | built | network_mask(positions, segments, RES, CELL, 24) | (cell_slope > 12)
    score[~buildable | blocked] = -np.inf
    placed = []
    for _ in range(16):
        if (fertility * buildable).sum() >= knobs.targets["fertile"] * maximum or not np.isfinite(score).any():
            break
        r, c = np.unravel_index(np.argmax(score + rng.random(score.shape) * 0.3), score.shape)
        x, z = float(centres[c]), float(centres[r])
        radius = float(rng.uniform(450, 800))
        lobes = np.clip(0.8 + 0.35 * smooth_noise((RES, RES), 5, rng), 0.45, 1.1)
        patch = np.clip(blob(x, z, radius) * lobes * 1.3, 0, 1) * 235
        patch[blocked] = 0
        np.maximum(fertility, patch, out=fertility)
        placed.append({"kind": "fertile", "x": x, "z": z, "radius_m": round(radius), "source": "convention"})
        score[np.hypot(centres[None, :] - x, centres[:, None] - z) < 1400] = -np.inf
    return placed


def top_up(ore, oil, cell_slope, cell_wet, shape, sx, sz, knobs, rng, height, fertility):
    """Add patches until ore and oil reach their New Game share targets in the
    25 buildable tiles. Shipped maps put oil on low, flat ground near water and
    ore at the foot of hills, a tile out from the start; no top-up patch
    touches the start tile."""
    tiles = tile_index()
    tz, tx = np.meshgrid(tiles, tiles, indexing="ij")
    buildable = (tx >= 2) & (tx <= 6) & (tz >= 2) & (tz <= 6)
    start = (tx == sx) & (tz == sz)
    centres = cell_centres()
    placed = []
    relief = height - ndimage.uniform_filter(height, 31)  # vs the ~1 km mean
    near_water = ndimage.distance_transform_edt(~cell_wet) * CELL
    maximum = 25 * 3686400 / 1139.0625 * 255
    for kind, grid, other in [("ore", ore, oil), ("oil", oil, ore)]:
        if kind == "ore":
            # The foot of hills: a hilly neighbourhood, workable local slope,
            # and not the peaks.
            hills = ndimage.uniform_filter(cell_slope, 31)
            score = (
                np.clip(hills / 20, 0, 1)
                + np.clip(1 - np.abs(cell_slope - 12) / 12, 0, 1)
                - 0.5 * np.clip(relief / 60, 0, 1)
            )
        else:
            score = (
                np.clip((10 - cell_slope) / 10, 0, 1)
                + np.clip(-relief / 30, -0.5, 1)
                + np.clip(1 - near_water / 1500, 0, 1)
            )
        score = ndimage.uniform_filter(score, 11)
        score[~buildable | cell_wet] = -np.inf
        # Shipped maps put ore and oil a tile out from the start, not in it.
        score[ndimage.binary_dilation(start, iterations=6)] = -np.inf
        score[other > 0.2] = -np.inf
        score[ndimage.binary_dilation(fertility > 0, iterations=4)] = -np.inf  # keep fields clear
        for _ in range(16):
            amount = (np.floor(grid * shape[kind] * 255 + 0.5) * buildable).sum()
            if amount >= knobs.targets[kind] * maximum or not np.isfinite(score).any():
                break
            r, c = np.unravel_index(np.argmax(score + rng.random(score.shape) * 0.3), score.shape)
            x, z = float(centres[c]), float(centres[r])
            # Shipped maps: a few blobs of ~0.5-0.7 km2 (largest ~3 km2),
            # soft edges, about a quarter of cells at the cap.
            radius = float(rng.uniform(500, 900) if not placed or placed[-1]["kind"] != kind else rng.uniform(420, 700))
            lobes = np.clip(0.8 + 0.35 * smooth_noise((RES, RES), 5, rng), 0.45, 1.1)
            patch = np.clip(blob(x, z, radius) * lobes * 1.3, 0, 1)
            patch[(fertility > 0) | start] = 0  # whole patch, not just its centre
            np.maximum(grid, patch, out=grid)
            placed.append({"kind": kind, "x": x, "z": z, "radius_m": round(radius), "source": "convention"})
            d = np.hypot(centres[None, :] - x, centres[:, None] - z)
            score[d < 1600] = -np.inf  # spread patches across tiles
    return placed


def species(px, pz, cls, terrain, wet16, slope, rng, theme):
    """Prefab index (into TREE_NAMES) per tree. Stands (~100 m) share a
    dominant species, so the mix clumps as on shipped maps; conifers, where
    the theme has them, favour high and steep ground; alders line water;
    bushes fill shrubland."""
    roles = THEMES[theme]
    x, z = px * TREE_UNIT, pz * TREE_UNIT
    col = np.clip(((x + HALF) / 16).astype(int), 0, 1080)
    row = np.clip(((z + HALF) / 16).astype(int), 0, 1080)
    h = terrain[row, col]
    lo, hi = np.percentile(terrain, [10, 99])
    hn = np.clip((h - lo) / max(1.0, hi - lo), 0, 1)
    near_water = ndimage.binary_dilation(wet16, iterations=2)[row, col]
    conifer_p = np.clip(0.08 + 0.75 * hn**1.5 + slope[row, col] / 200, 0.03, 0.9)
    stand = (row // 6) * 4096 + (col // 6)
    _, inverse = np.unique(stand, return_inverse=True)
    stand_draw = rng.random(inverse.max() + 1)[inverse]
    stand_pick = rng.random(inverse.max() + 1)[inverse]
    pick, mix = rng.random(len(px)), rng.random(len(px))
    role = np.full(len(px), "broadleaf", dtype=object)
    if "conifer" in roles:
        role[stand_draw < conifer_p] = "conifer"
    role[near_water & (pick < 0.55)] = "riparian"
    role[(cls == 20) & (pick < 0.7)] = "scrub"
    out = np.empty(len(px), np.uint16)
    index = {n: i for i, n in enumerate(TREE_NAMES)}
    for name, pool in roles.items():
        names, weights = zip(*pool)
        cum = np.cumsum(weights) / sum(weights)
        sel = role == name
        # 75 % of trees take their stand's species, the rest mix freely.
        u = np.where(mix[sel] < 0.75, stand_pick[sel], pick[sel])
        choice = np.searchsorted(cum, u, side="right").clip(0, len(names) - 1)
        out[sel] = np.array([index[n] for n in names], np.uint16)[choice]
    return out


def forest_cells(trees):
    """TreeManager.TreesModified over every cell: forest and tree bytes."""
    forest = np.zeros((RES, RES), np.uint8)
    if not len(trees):
        return forest, forest.copy()
    px, pz, _ = trees
    x = px.astype(np.float32) * np.float32(TREE_UNIT)
    z = pz.astype(np.float32) * np.float32(TREE_UNIT)
    c = np.clip((x / np.float32(CELL) + 256).astype(int), 0, RES - 1)
    r = np.clip((z / np.float32(CELL) + 256).astype(int), 0, RES - 1)
    counts = np.bincount(r * RES + c, minlength=RES * RES).reshape(RES, RES)
    forest = np.minimum(counts * 60, 255).astype(np.uint8)
    return forest, forest.copy()  # grown trees: tree byte = 4 x 15 per tree


def water_cells(depth, terrain_raw):
    """CountWaterCoverage(cell centre, 20 m) for every resource cell: the mean
    capped depth of wet (>= 8/64 m) water cells, and the shore byte, which is
    the wet cells' mean surface + 4 m minus the mean ground, in 1/64 m."""
    d = depth.astype(np.int64)
    g = terrain_raw.astype(np.int64)
    wet = d >= 8
    capped = np.where(wet, np.minimum(255, d), 0)
    surface = np.where(wet, g + 256 + np.minimum(255, d), 0)

    def box(a):
        s = np.zeros((a.shape[0] + 1, a.shape[1] + 1), np.int64)
        s[1:, 1:] = a.cumsum(0).cumsum(1)
        return s

    sw, sc, ss, sg = box(wet.astype(np.int64)), box(capped), box(surface), box(g)
    centres = cell_centres()
    lo = np.maximum(((centres - 20 + HALF) / 16 + 0.5).astype(int), 0)
    hi = np.minimum(((centres + 20 + HALF) / 16 + 0.5).astype(int), 1080) + 1
    r0, c0 = np.meshgrid(lo, lo, indexing="ij")
    r1, c1 = np.meshgrid(hi, hi, indexing="ij")

    def total(s):
        return s[r1, c1] - s[r0, c1] - s[r1, c0] + s[r0, c0]

    n, area = total(sw), (r1 - r0) * (c1 - c0)
    safe = np.maximum(n, 1)
    water = np.where(n > 0, (total(sc) + (n >> 1)) // safe, 0)
    shore = np.where(
        n > 0,
        np.clip((total(ss) + (n >> 1)) // safe - (total(sg) + (area >> 1)) // area, 0, 255),
        0,
    )
    return water.astype(np.uint8), shore.astype(np.uint8)


def area_totals(grids, water):
    """Per-tile sums in the native order (temp then final; ore, oil, forest,
    fertility; then temp and final water), 81 entries each."""
    tiles = tile_index()
    idx = (tiles[:, None] * 9 + tiles[None, :]).ravel()

    def tot(g):
        return np.bincount(idx, weights=g.ravel().astype(np.float64), minlength=81).astype(np.uint32)

    ore, oil, forest, fert = (tot(grids[k]) for k in ["ore", "oil", "forest", "fertility"])
    w = tot(water)
    return np.concatenate([ore, oil, forest, fert, ore, oil, forest, fert, w, w]), {
        "ore": ore,
        "oil": oil,
        "forest": forest,
        "fertility": fert,
        "water": w,
    }


def unlockable(per_tile):
    """CalculateUnlockableResources: the 25 tiles at (2..6, 2..6)."""
    t = per_tile.reshape(9, 9)
    return int(t[2:7, 2:7].sum())


def encode_resources(data, span_start, span_end, prefix, grids, water, shore):
    """Rebuild the whole NaturalResourceManager section body."""
    from template import decode_array, encode_array

    def enc(values):
        return encode_array(np.asarray(values, np.uint8).ravel(), 1)

    forest = grids["forest"].ravel()
    body = b"".join(
        [
            enc(grids["ore"]),
            enc(grids["oil"]),
            enc(np.zeros(RES * RES, np.uint8)),  # sand
            enc(forest),
            enc(grids["tree"].ravel()[forest != 0]),
            enc(grids["fertility"].ravel()[forest == 0]),
            enc(water),
            enc(shore),
            enc(np.zeros(RES * RES, np.uint8)),  # pollution
            enc(np.zeros(RES * RES, np.uint8)),  # burned
            enc(np.zeros(RES * RES, np.uint8)),  # destroyed
        ]
    )
    areas, per_tile = area_totals(grids, water)
    body += encode_array(areas, 4)
    # Skip the template's own arrays to find its trailing scalars and end tag.
    offset = span_start + prefix
    for i in range(11):
        if i == 4:
            n = int(np.count_nonzero(old_forest))
        elif i == 5:
            n = RES * RES - int(np.count_nonzero(old_forest))
        else:
            n = RES * RES
        values, offset = decode_array(data, n, offset, 1)
        if i == 3:
            old_forest = values
    _, offset = decode_array(data, 81 * 10, offset, 4)
    # Used-resource counters and pollution-dispose rates: keep the template's.
    return data[span_start : span_start + prefix] + body + data[offset:span_end], per_tile


def encode_trees(data, span_start, span_end, prefix, trees, names):
    """Rebuild the whole TreeManager section body (no burning trees)."""
    from template import decode_array, encode_array

    px, pz, kinds = trees if len(trees) else (np.zeros(0, np.int16),) * 2 + (np.zeros(0, np.uint16),)
    n = len(px)
    if n > TREE_SLOTS:
        raise ValueError("More trees than the vanilla TreeManager holds")
    # A tree's size and brightness come from its slot number, so neighbours
    # must not get consecutive slots: shuffle them (deterministically).
    order = np.random.default_rng(n).permutation(n)
    px, pz, kinds = px[order], pz[order], kinds[order]
    used = np.unique(kinds)  # write only referenced names, as the game does
    kinds = np.searchsorted(used, kinds).astype(np.uint16)
    names = [names[i] for i in used]
    flags = np.zeros(TREE_SLOTS, np.uint16)
    flags[:n] = GROWN_TREE
    body = encode_array(flags, 2) + encode_array(kinds.astype(np.uint16), 2)
    body += struct.pack(">H", len(names))
    for name in names:
        raw = name.encode("latin1")
        body += (0x800000 | len(raw)).to_bytes(3, "big")
        previous = 128
        for ch in raw:
            body += bytes([(ch - previous) & 255])
            previous = ch
    body += encode_array(px.view(np.uint16), 2) + encode_array(pz.view(np.uint16), 2)
    body += (0).to_bytes(3, "big")
    # The template's own body: skip it to find the end tag.
    offset = span_start + prefix
    old_flags, offset = decode_array(data, TREE_SLOTS, offset, 2)
    m = int(np.count_nonzero(old_flags))
    _, offset = decode_array(data, m, offset, 2)
    count = struct.unpack_from(">H", data, offset)[0]
    offset += 2
    for _ in range(count):
        if data[offset] == 255:
            offset += 1
            continue
        length = int.from_bytes(data[offset : offset + 3], "big")
        offset += 3 + (length & 0x7FFFFF) * (1 if length & 0x800000 else 2)
    _, offset = decode_array(data, m, offset, 2)
    _, offset = decode_array(data, m, offset, 2)
    burning = int.from_bytes(data[offset : offset + 3], "big")
    offset += 3 + 5 * burning
    return data[span_start : span_start + prefix] + body + data[offset:span_end]


def apply(data, spec, depth, raw, result, names):
    """Replacements for the NaturalResourceManager and TreeManager sections,
    and the New Game amounts (25 central tiles) for MapMetaData."""
    from crp import begin_tag_size

    ranges = {r["type"]: r for r in spec["ranges"]}
    nr, tr = ranges["NaturalResourceManager+Data"], ranges["TreeManager+Data"]
    water, shore = water_cells(depth.reshape(1081, 1081), raw.reshape(1081, 1081))
    resources, per_tile = encode_resources(
        data,
        nr["start"],
        nr["end"],
        begin_tag_size(data, nr["start"], "NaturalResourceManager"),
        result,
        water,
        shore,
    )
    trees = encode_trees(
        data,
        tr["start"],
        tr["end"],
        begin_tag_size(data, tr["start"], "TreeManager"),
        result["trees"],
        names,
    )
    amounts = {
        "oreAmount": unlockable(per_tile["ore"]),
        "oilAmount": unlockable(per_tile["oil"]),
        "forestAmount": unlockable(per_tile["forest"]),
        "fertileLandAmount": unlockable(per_tile["fertility"]),
        "waterAmount": unlockable(per_tile["water"]),
    }
    return [(nr["start"], nr["end"], resources), (tr["start"], tr["end"], trees)], amounts, per_tile


def summary(result, per_tile, knobs):
    trees = result["trees"]
    return {
        "knobs": asdict(knobs),
        "trees": int(len(trees[0])) if len(trees) else 0,
        "unlockable": {k: unlockable(v) for k, v in per_tile.items()},
        "cells": {k: int(np.count_nonzero(result[k])) for k in ["ore", "oil", "fertility", "forest"]},
        "evidence": result["evidence"],
        "placed": result["placed"],
    }


if __name__ == "__main__":
    print(json.dumps({"tree_names": TREE_NAMES, "themes": THEMES}, indent=2))
