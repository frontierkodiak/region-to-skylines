"""Prepare stock first-hour controls without exporting maps or acquiring the game.

Read the exact stock packages named in a frozen preregistration. The existing
survey reader supports their old CRP formats; the shipping writer stays pinned
to its own format-12 contract. Only expectations and byte hashes are written.
"""

import argparse
import hashlib
import json
from pathlib import Path

from survey.craft_anatomy import read_package
from survey.measure_maps import parse_metadata


def prepare(plan, stock, output):
    controls = []
    for control in plan["controls"]:
        source = stock / control["filename"]
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != control["sha256"]:
            raise ValueError(f"Stock control bytes changed: {source.name}")
        package, assets = read_package(raw)
        if not all(asset["md5_ok"] for asset in assets):
            raise ValueError("Stock package asset checksum mismatch")
        metadata = parse_metadata(
            next(asset["payload"] for asset in assets if asset["kind"] == 100)
        )
        panel = {
            "map_name": metadata["mapName"],
            "author": "",
            "buildableArea": metadata["buildableArea"],
            "require_resource_bars": True,
            "require_window_capture": True,
            "resources": {
                key: metadata[key]
                for key in (
                    "maxResourceAmount",
                    "oilAmount",
                    "oreAmount",
                    "forestAmount",
                    "fertileLandAmount",
                    "waterAmount",
                )
            },
            "connections": {
                direction + kind: metadata[direction + kind]
                for direction in ("incoming", "outgoing")
                for kind in ("Roads", "TrainTracks", "ShipPath", "PlanePath")
            },
        }
        slug = control["name"].lower().replace(" ", "-")
        folder = output / slug
        folder.mkdir(parents=True, exist_ok=True)
        probes = folder / "probes.json"
        probes.write_text(
            json.dumps(
                {
                    "scope": "Stock-map player-policy control; no exported-map geography claims",
                    "points": [],
                    "new_game_panel": panel,
                    "stock_package_sha256": control["sha256"],
                },
                indent=2,
            )
            + "\n"
        )
        controls.append(
            {
                "slug": slug,
                "map": str(source.resolve()),
                "probes": str(probes.resolve()),
                "package_format": package["format"],
                "package_sha256": control["sha256"],
            }
        )
    (output / "controls.json").write_text(json.dumps(controls, indent=2) + "\n")
    return controls


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("stock", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(json.loads(args.plan.read_text()), args.stock, args.output),
            indent=2,
        )
    )
