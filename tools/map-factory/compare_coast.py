"""Initial inundation by independent WorldCover class; no acceptance mask/gate.

Native 1081-square depth is south-first, vertex sampled every 16m. WorldCover
is 1728-square north-first, cell-centred every 10m over the identical footprint.
Reports the whole square and central 25 tiles, with no coastal exclusion mask.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample_depth(depth):
    indices = (np.arange(1728) + 0.5) * 10 / 16
    z, x = np.meshgrid(indices, indices, indexing="ij")
    return ndimage.map_coordinates(depth, [z, x], order=1, mode="nearest")


def measure(prepared, landcover):
    depth = np.fromfile(prepared / "water.u16", dtype="<u2").reshape(1081, 1081) / 64
    cover = np.flipud(
        np.frombuffer(gzip.decompress(landcover.read_bytes()), dtype=np.uint8).reshape(
            1728, 1728
        )
    )
    water = sample_depth(depth)
    axis = (np.arange(1728) + 0.5) * 10 - 8640
    central = (np.abs(axis[:, None]) < 4800) & (np.abs(axis[None, :]) < 4800)
    regions = {}
    for name, window in [
        ("whole_square", np.ones_like(cover, dtype=bool)),
        ("central_25_tiles", central),
    ]:
        classes = {}
        for label, code in [("built_up", 50), ("forest", 10)]:
            selected = (cover == code) & window
            n = int(selected.sum())
            values = water[selected]
            classes[label] = {
                "class": code,
                "cells": n,
                "area_km2": n * 0.0001,
                "inundated_cells": int((values > 0.1).sum()),
                "inundated_fraction": float((values > 0.1).mean()) if n else None,
                "any_depth_fraction": float((values > 0).mean()) if n else None,
                "p95_depth_m": float(np.quantile(values, 0.95)) if n else None,
                "max_depth_m": float(values.max()) if n else None,
            }
        regions[name] = {
            "classes": classes,
            "wet_fraction": float((water[window] > 0.1).mean()),
        }
    return {
        "water_sha256": sha(prepared / "water.u16"),
        "landcover_sha256": sha(landcover),
        "regions": regions,
    }


def compare(before, after, landcover):
    return {
        "in_game_verified": False,
        "measurement": "initial prepared depth, not native simulation",
        "wet_threshold_m": 0.1,
        "resampling": "bilinear native south-first 16m nodes to WorldCover south-first 10m centres",
        "coastal_exclusion_mask": None,
        "before": measure(before, landcover),
        "after": measure(after, landcover),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["before", "after", "landcover", "output"]:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = compare(args.before, args.after, args.landcover)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
