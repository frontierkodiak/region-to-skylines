"""Paint natural resources and trees onto a prepared region and write its map.

    uv run python paint.py PREPARED LANDCOVER OUTPUT [--evidence E.json]
        [--trees 180000] [--resources balanced|real] [--fertile 1.0]

PREPARED holds terrain.u16, water.u16 and hydrology.json (gzipped or not),
as `region.prepare` or a frozen fixture leaves them. LANDCOVER is
`landcover.py` output. Writes the .crp, resources.png, resources.json and the grids (resources.npz,
south-first 512 squared).
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("landcover", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--geometry", type=Path, help="defaults to PREPARED/geometry.json(.gz)")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--trees", type=int, default=R.Knobs.trees)
    parser.add_argument("--resources", choices=["balanced", "real"], default=R.Knobs.resources)
    parser.add_argument("--fertile", type=float, default=R.Knobs.fertile)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--map-name", help="override the New Game name")
    args = parser.parse_args()

    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    for name in ["terrain.u16", "water.u16", "hydrology.json"]:
        (out / name).write_bytes(load(args.prepared, name))
    hydro = json.loads((out / "hydrology.json").read_text())
    if args.map_name:
        hydro["map_name"] = args.map_name
        (out / "hydrology.json").write_text(json.dumps(hydro, indent=2) + "\n")
    geometry = json.loads(
        load(args.geometry.parent, args.geometry.name) if args.geometry else load(args.prepared, "geometry.json")
    )
    raw = np.fromfile(out / "terrain.u16", dtype="<u2").reshape(1081, 1081)
    depth = np.fromfile(out / "water.u16", dtype="<u2").reshape(1081, 1081)
    terrain = raw.astype(float) / 64
    lc = np.frombuffer(gzip.decompress(args.landcover.read_bytes()), np.uint8)
    lc = np.flipud(lc.reshape(R.GRID if hasattr(R, "GRID") else 1728, -1))
    layout_path = ROOT / "templates/native-corridors.json"
    layout = json.loads(layout_path.read_text())
    evidence = json.loads(args.evidence.read_text())["evidence"] if args.evidence else []
    knobs = R.Knobs(trees=args.trees, resources=args.resources, fertile=args.fertile, seed=args.seed)
    palette = R.palette_for(geometry["sq"]["lat"], terrain)
    result = R.plan(terrain, depth, lc, layout, hydro, evidence, knobs, palette)
    crp = out / (hydro["map_id"] + ".crp")
    package = write_map(
        ROOT / "templates/native-corridors.crp",
        layout_path,
        out / "terrain.u16",
        out / "water.u16",
        out / "hydrology.json",
        crp,
        resources=(result, R.TREE_NAMES),
    )
    water, _ = R.water_cells(depth, raw)
    _, per_tile = R.area_totals(result, water)
    report = R.summary(result, per_tile, knobs)
    report.update({"palette": palette, "package": package})
    preview(result, terrain, depth, out / "resources.png")
    np.savez_compressed(out / "resources.npz", **{k: result[k] for k in ["ore", "oil", "fertility", "forest"]})
    (out / "resources.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["trees", "unlockable", "cells", "placed", "palette"]}, indent=2))
    print(json.dumps(package, indent=2))


if __name__ == "__main__":
    main()
