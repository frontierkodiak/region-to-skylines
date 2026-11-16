"""Audit DEM-resolution disagreement in the delivered terrain-stage arrays.

Diagnostic subsets only. This never changes the harness, maps or acceptance.
The stage order is the explicit order in diagnose_terrain_stages.py at 3db3a0f.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from admission import polygons

ROOT = Path(__file__).resolve().parent


def corr(a, b):
    return float(np.corrcoef(a.ravel(), b.ravel())[0, 1])


def audit(slug, arrays, output):
    source = ROOT / "fixtures" / slug / "shipping-geometry.json.gz"
    geometry = json.loads(gzip.decompress(source.read_bytes()))
    held = np.load(arrays)
    checker, capture = held["dem"], held["source_zoom_dem"]
    banks, prepared = held["sampled_stages"][[0, 2]]
    water = np.zeros((1081, 1081), dtype=bool)
    for key in ["lakes", "riverAreas", "oceans"]:
        water |= polygons(geometry["sq"], geometry.get(key, []))
    land = ~np.flipud(water)[::4, ::4]
    assert checker.shape == capture.shape == land.shape == banks.shape == prepared.shape
    fit = geometry["fit"]
    difference = capture[land] - checker[land]
    report = {
        "slug": slug,
        "diagnostic_only": True,
        "acceptance_unchanged": True,
        "all_points": int(land.size),
        "land_points": int(land.sum()),
        "land_fraction": float(land.mean()),
        "land_definition_not_acceptance_mask": "outside source lake, river-area and ocean polygons",
        "land_correlation": {
            "banks_vs_checker_zoom13": corr(banks[land], checker[land]),
            "prepared_vs_checker_zoom13": corr(prepared[land], checker[land]),
            "banks_vs_capture_zoom14": corr(banks[land], capture[land]),
            "prepared_vs_capture_zoom14": corr(prepared[land], capture[land]),
            "checker_vs_capture_dem": corr(checker[land], capture[land]),
        },
        "capture_minus_checker_dem_land_m": {
            "p05": float(np.percentile(difference, 5)),
            "median": float(np.median(difference)),
            "p95": float(np.percentile(difference, 95)),
        },
        "water_polygon_errors_against_matched_fitted_capture_dem_m": {},
        "sha256": {
            "stage_arrays": hashlib.sha256(arrays.read_bytes()).hexdigest(),
            "geometry_gzip": hashlib.sha256(source.read_bytes()).hexdigest(),
        },
        "limitations": "Matching the held source tests internal fidelity, not independent real-world DEM accuracy. Different underlying elevation products at the two zooms are an inference, not established provenance. Land-only correlations are diagnostics, not passes.",
    }
    reference = (capture - fit["base"]) * fit["verticalScale"] + 50
    for key in ["lakes", "riverAreas"]:
        mask = np.flipud(polygons(geometry["sq"], geometry.get(key, [])))[::4, ::4]
        report["water_polygon_errors_against_matched_fitted_capture_dem_m"][key] = {
            "points": int(mask.sum()),
            "banks_mae": float(np.abs(banks[mask] - reference[mask]).mean()),
            "prepared_mae": float(np.abs(prepared[mask] - reference[mask]).mean()),
        }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("arrays", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    audit(args.slug, args.arrays, args.output)
