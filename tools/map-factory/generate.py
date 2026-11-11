"""Build a map from a browser heightmap and its matching geographic inputs."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from crp import write_map
from region import prepare

ROOT = Path(__file__).resolve().parent


def generate(
    png,
    geometry,
    output,
    banks=None,
    prefill=True,
    landcover=None,
    evidence=None,
    knobs=None,
):
    template = ROOT / "templates/native-corridors.crp"
    layout = ROOT / "templates/native-corridors.json"
    output.mkdir(parents=True, exist_ok=True)
    geometry_bytes = geometry.read_bytes()
    geometry_snapshot = output / "geometry.json"
    geometry_snapshot.write_bytes(geometry_bytes)
    geometry_sha256 = hashlib.sha256(geometry_bytes).hexdigest()
    summary = prepare(png, geometry_snapshot, layout, output, banks)
    if not prefill:
        terrain = np.fromfile(output / "terrain.u16", dtype="<u2").astype(float) / 64
        sea_depth = np.maximum(0, summary["sea_level_m"] - terrain)
        np.floor(sea_depth * 64 + 0.5).clip(0, 65535).astype("<u2").tofile(
            output / "water.u16"
        )
    if landcover is not None:
        # Resource stage: trees, forest, fertile land, ore and oil (PL-902).
        from paint import paint

        report = paint(output, landcover, output, geometry_snapshot, evidence, knobs)
        result = report["package"]
    else:
        report = None
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
        "resources": None
        if report is None
        else {
            **{k: report[k] for k in ["knobs", "trees", "unlockable", "placed"]},
            "prepared_geometry_sha256": geometry_sha256,
        },
        "source": {"inputs_sha256": {"geometry.json": geometry_sha256}},
        "prefill": prefill,
        "in_game_verified": False,
    }
    if report is not None:
        receipt["resource_plan"] = {
            "file": "plan.npz",
            "sha256": hashlib.sha256((output / "plan.npz").read_bytes()).hexdigest(),
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
    parser.add_argument(
        "--landcover", type=Path, help="landcover.py output; adds the resource stage"
    )
    parser.add_argument(
        "--evidence", type=Path, help="evidence.py output (ore/oil deposits)"
    )
    parser.add_argument(
        "--trees", type=int, default=180_000, help="tree count; vanilla holds 262,144"
    )
    parser.add_argument(
        "--resources",
        choices=["balanced", "real"],
        default="balanced",
        help="balanced tops ore and oil up to shipped-map shares; real uses evidence only",
    )
    parser.add_argument(
        "--fertile",
        type=float,
        default=1.0,
        help="scale fertile land from crop and pasture",
    )
    args = vars(parser.parse_args())
    from resources import Knobs

    args["knobs"] = Knobs(
        trees=args.pop("trees"),
        resources=args.pop("resources"),
        fertile=args.pop("fertile"),
    )
    print(json.dumps(generate(**args), indent=2))
