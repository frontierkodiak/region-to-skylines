"""Prepare an observational harness request from an unchanged native CRP.

Uses the map-factory environment for package decoding, before any game slot is
acquired. It never writes a map, grid, source, qualification probe or gate.
"""

import argparse
import hashlib
import json
from pathlib import Path

from crp import read_package
from water_diagnostics import decode_water


def prepare(package, sources, cells, max_steps=512):
    _, assets = read_package(package.read_bytes())
    decoded = decode_water(next(a["payload"] for a in assets if a["kind"] == 52))
    controls = [
        {
            "type": s["type"],
            "target": s["target_fixed"],
            "input": s["position"],
            "output": s["position"],
            "input_rate": s["intake_rate"],
            "output_rate": s["output_rate"],
        }
        for s in decoded["sources"]
    ]
    if not (sources or cells) or any(not 1 <= s <= len(controls) for s in sources):
        raise ValueError("trace requires valid source IDs or cells")
    if any(
        len(p) != 2 or any(v < -8640 or v > 8640 or v % 16 for v in p) for p in cells
    ):
        raise ValueError("cells must be native 16m x,z grid nodes")
    if not 1 <= max_steps <= 512:
        raise ValueError("max_steps must be 1..512")
    return {
        "sources": sources,
        "cells": cells,
        "controls": controls,
        "max_steps": max_steps,
        "binding": {"package_sha256": hashlib.sha256(package.read_bytes()).hexdigest()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--sources", type=int, nargs="*", default=[])
    parser.add_argument(
        "--cells", type=Path, help="JSON array of [x,z] native grid nodes"
    )
    parser.add_argument("--max-steps", type=int, default=512)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(
        args.package,
        args.sources,
        json.loads(args.cells.read_text()) if args.cells else [],
        args.max_steps,
    )
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "source_count": len(result["controls"]),
                "targets": result["sources"],
                "binding": result["binding"],
            }
        )
    )


if __name__ == "__main__":
    main()
