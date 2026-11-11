"""Paint natural resources and trees onto a prepared region and write its map.

    uv run python paint.py PREPARED LANDCOVER OUTPUT [--evidence E.json]
        [--trees 180000] [--resources balanced|real] [--fertile 1.0]

PREPARED holds terrain.u16, water.u16 and hydrology.json (gzipped or not),
as `region.prepare` or a frozen fixture leaves them. LANDCOVER is
`landcover.py` output. Writes the .crp, resources.png, resources.json and plan.npz: the resource
grids (south-first, 512 squared) and the trees, which `--plan` replays
through the encoders without planning.
"""

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
from PIL import Image

import resources as R
from crp import write_map

ROOT = Path(__file__).resolve().parent


def load(directory, name):
    for candidate in [directory / name, directory / (name + ".gz")]:
        if candidate.exists():
            raw = candidate.read_bytes()
            return gzip.decompress(raw) if candidate.suffix == ".gz" else raw
    raise FileNotFoundError(directory / name)


def preview(result, terrain, depth, path):
    """Hillshade with forest green, fertile yellow, ore red, oil black."""
    t = R.node_grid(terrain, R.RES, R.CELL)
    gz, gx = np.gradient(t, R.CELL)
    shade = np.clip(0.75 + (gx - gz) / 1.5, 0.35, 1.0)
    rgb = np.stack([shade * 200, shade * 196, shade * 180], -1)
    wet = R.node_grid((depth > 0).astype(float), R.RES, R.CELL) > 0.5
    layers = [
        (result["forest"] / 255, (40, 110, 45)),
        (result["fertility"] / 255, (235, 205, 70)),
        (result["ore"] / 255, (200, 50, 40)),
        (result["oil"] / 255, (20, 20, 20)),
    ]
    for amount, colour in layers:
        a = (amount * 0.85)[..., None]
        rgb = rgb * (1 - a) + np.array(colour) * a
    rgb[wet] = (60, 110, 200)
    tiles = np.zeros((R.RES, R.RES), bool)
    edges = np.flatnonzero(np.diff(R.tile_index()))
    tiles[edges, :] = tiles[:, edges] = True
    rgb[tiles] = rgb[tiles] * 0.6
    image = Image.fromarray(np.flipud(rgb).astype(np.uint8))  # north up
    image.resize((1024, 1024), Image.NEAREST).save(path)


PLAN_KEYS = ["ore", "oil", "fertility", "forest", "tree"]


def save_plan(result, path):
    px, pz, kinds = (
        result["trees"]
        if len(result["trees"])
        else (np.zeros(0, np.int16),) * 2 + (np.zeros(0, np.uint16),)
    )
    np.savez_compressed(
        path, **{k: result[k] for k in PLAN_KEYS}, px=px, pz=pz, kinds=kinds
    )


def load_plan(path):
    z = np.load(path)
    result = {k: z[k] for k in PLAN_KEYS}
    result["trees"] = (z["px"], z["pz"], z["kinds"]) if len(z["px"]) else []
    result.update({"evidence": [], "placed": []})
    return result


def paint(
    prepared,
    landcover,
    out,
    geometry=None,
    evidence=None,
    knobs=None,
    map_name=None,
    plan=None,
):
    """Plan (or replay a frozen plan) and write the map. Returns the report."""
    knobs = knobs or R.Knobs()
    out.mkdir(parents=True, exist_ok=True)
    for name in ["terrain.u16", "water.u16", "hydrology.json"]:
        (out / name).write_bytes(load(prepared, name))
    hydro = json.loads((out / "hydrology.json").read_text())
    if map_name:
        hydro["map_name"] = map_name
        (out / "hydrology.json").write_text(json.dumps(hydro, indent=2) + "\n")
    raw = np.fromfile(out / "terrain.u16", dtype="<u2").reshape(1081, 1081)
    depth = np.fromfile(out / "water.u16", dtype="<u2").reshape(1081, 1081)
    terrain = raw.astype(float) / 64
    layout_path = ROOT / "templates/native-corridors.json"
    if plan is not None:
        result, theme = load_plan(plan), None
    else:
        json.loads(
            load(geometry.parent, geometry.name)
            if geometry
            else load(prepared, "geometry.json")
        )
        lc = np.frombuffer(gzip.decompress(landcover.read_bytes()), np.uint8)
        side = int(round(np.sqrt(lc.size)))
        lc = np.flipud(lc.reshape(side, side))  # landcover.py is north-first
        layout = json.loads(layout_path.read_text())
        found = json.loads(evidence.read_text())["evidence"] if evidence else []
        theme = R.theme_of((ROOT / "templates/native-corridors.crp").read_bytes())
        result = R.plan(terrain, depth, lc, layout, hydro, found, knobs, theme)
    package = write_map(
        ROOT / "templates/native-corridors.crp",
        layout_path,
        out / "terrain.u16",
        out / "water.u16",
        out / "hydrology.json",
        out / (hydro["map_id"] + ".crp"),
        resources=(result, R.TREE_NAMES),
    )
    water, _ = R.water_cells(depth, raw)
    _, per_tile = R.area_totals(result, water)
    report = R.summary(result, per_tile, knobs)
    report.update({"theme": theme, "package": package})
    preview(result, terrain, depth, out / "resources.png")
    save_plan(result, out / "plan.npz")
    (out / "resources.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("landcover", type=Path, nargs="?")
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--geometry", type=Path, help="defaults to PREPARED/geometry.json(.gz)"
    )
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--trees", type=int, default=R.Knobs.trees)
    parser.add_argument(
        "--resources", choices=["balanced", "real"], default=R.Knobs.resources
    )
    parser.add_argument(
        "--fertile",
        type=float,
        default=R.Knobs.fertile,
        help="scale fertile land from crop and pasture",
    )
    defaults = R.Knobs().targets
    for kind in ["ore", "oil", "fertile"]:
        parser.add_argument(
            f"--{kind}-share",
            type=float,
            default=defaults[kind],
            help=f"balanced: top {kind} up to this New Game share (default {defaults[kind]})",
        )
    parser.add_argument(
        "--outer-trees",
        type=float,
        default=R.Knobs.outer_trees,
        help="tree density outside the 25 tiles",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--map-name", help="override the New Game name")
    parser.add_argument(
        "--plan", type=Path, help="replay a frozen plan.npz instead of planning"
    )
    args = parser.parse_args()
    if args.plan is None and args.landcover is None:
        parser.error("LANDCOVER is required unless --plan is given")
    knobs = R.Knobs(
        trees=args.trees,
        resources=args.resources,
        fertile=args.fertile,
        seed=args.seed,
        outer_trees=args.outer_trees,
        targets={
            "ore": args.ore_share,
            "oil": args.oil_share,
            "fertile": args.fertile_share,
        },
    )
    report = paint(
        args.prepared,
        args.landcover,
        args.output,
        args.geometry,
        args.evidence,
        knobs,
        args.map_name,
        args.plan,
    )
    print(
        json.dumps(
            {k: report[k] for k in ["trees", "unlockable", "cells", "placed", "theme"]},
            indent=2,
        )
    )
    print(json.dumps(report["package"], indent=2))


if __name__ == "__main__":
    main()
