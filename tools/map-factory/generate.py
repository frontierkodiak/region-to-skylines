"""Build a map from a browser heightmap and its matching geographic inputs."""

import argparse
import json
from pathlib import Path

import numpy as np

from crp import write_map
from region import prepare

ROOT = Path(__file__).resolve().parent


def generate(png, geometry, output, banks=None, prefill=True):
    template = ROOT / "templates/native-corridors.crp"
    layout = ROOT / "templates/native-corridors.json"
    summary = prepare(png, geometry, layout, output, banks)
    if not prefill:
        terrain = np.fromfile(output / "terrain.u16", dtype="<u2").astype(float) / 64
        sea_depth = np.maximum(0, summary["sea_level_m"] - terrain)
        np.floor(sea_depth * 64 + 0.5).clip(0, 65535).astype("<u2").tofile(
            output / "water.u16"
        )
    result = write_map(
        template,
        layout,
        output / "terrain.u16",
        output / "water.u16",
        output / "hydrology.json",
        output / (summary["map_id"] + ".crp"),
    )
    receipt = {
        "preparation": summary,
        "package": result,
        "prefill": prefill,
        "in_game_verified": False,
    }
    (output / "generation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["png", "geometry", "output"]:
        parser.add_argument(name, type=Path)
    parser.add_argument(
        "--banks",
        type=Path,
        help="North-to-south uncarved Float32 elevations in game metres",
    )
    parser.add_argument(
        "--no-prefill",
        action="store_false",
        dest="prefill",
        help="Diagnostic comparison: initialize sea only",
    )
    print(json.dumps(generate(**vars(parser.parse_args())), indent=2))
