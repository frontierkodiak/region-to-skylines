"""Build a map from a browser heightmap and its matching geographic inputs."""

import argparse
import json
from pathlib import Path

from crp import write_map
from region import prepare

ROOT = Path(__file__).resolve().parent


def generate(png, geometry, output, banks=None):
    template = ROOT / "templates/native-corridors.crp"
    layout = ROOT / "templates/native-corridors.json"
    summary = prepare(png, geometry, layout, output, banks)
    result = write_map(
        template,
        layout,
        output / "terrain.u16",
        output / "water.u16",
        output / "hydrology.json",
        output / (summary["map_id"] + ".crp"),
    )
    receipt = {"preparation": summary, "package": result, "in_game_verified": False}
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
    print(json.dumps(generate(**vars(parser.parse_args())), indent=2))
