"""Attribute terrain correlation by comparing held generation stages, not gates.

Run with map-factory plus pyproj. This produces diagnostics only; no map,
acceptance mask, threshold or qualification record is rewritten.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

from admission import polygons

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "cs1-harness"))
from cs1_harness import groundtruth as gt  # noqa: E402


def diagnose(slug, prepared, output):
    fixture = ROOT / "fixtures" / slug
    geometry = json.loads(
        gzip.decompress((fixture / "shipping-geometry.json.gz").read_bytes())
    )
    sq = geometry["sq"]
    region = {
        "lon": sq["lon"],
        "lat": sq["lat"],
        "size_m": 17280 * sq["scale"],
        "rotation": -sq["rotation"],
    }
    inverse, _ = gt.projection(region)
    idx = np.arange(0, 1081, gt.STEP)
    zz, xx = np.meshgrid(idx * 16 - 8640, idx * 16 - 8640, indexing="ij")
    lon, lat = inverse(xx, zz)
    dem = gt.dem_at(np.asarray(lon), np.asarray(lat))
    banks = np.frombuffer(
        gzip.decompress((fixture / "banks.f32.gz").read_bytes()), "<f4"
    ).reshape(1081, 1081)
    browser = np.asarray(Image.open(fixture / "input.png"), dtype=float) * 1024 / 65535
    final = (
        np.flipud(np.fromfile(prepared / "terrain.u16", "<u2").reshape(1081, 1081)) / 64
    )
    lakes = polygons(sq, geometry.get("lakes", []))
    river_areas = polygons(sq, geometry.get("riverAreas", []))
    lake_influence = ndimage.binary_dilation(lakes, iterations=3)
    stages = {
        "uncarved_banks": banks,
        "browser_input": browser,
        "prepared": final,
        "counterfactual_restore_lake_polygons": np.where(lakes, banks, final),
        "counterfactual_restore_lake_kernel": np.where(lake_influence, banks, final),
    }
    sampled = {name: np.flipud(a)[:: gt.STEP, :: gt.STEP] for name, a in stages.items()}
    stats = {
        name: {"all_points_correlation": gt.corr(a, dem), "points": int(a.size)}
        for name, a in sampled.items()
    }
    # Compare fitting/carving in the writer's own physical frame as well as the
    # independent check. This separates checker variation from actual edits.
    fit = geometry["fit"]
    fitted_dem = (dem - fit["base"]) * fit["verticalScale"] + 50
    subsets = {}
    for label, mask in {
        "source_lake_polygons": lakes,
        "source_river_polygons": river_areas,
        "outside_source_water_polygons": ~(lakes | river_areas),
    }.items():
        mask = np.flipud(mask)[:: gt.STEP, :: gt.STEP]
        subsets[label] = {"points": int(mask.sum()), "stages": {}}
        for name, a in sampled.items():
            error = a[mask] - fitted_dem[mask]
            subsets[label]["stages"][name] = {
                "mae_m": float(np.abs(error).mean()),
                "p95_abs_m": float(np.percentile(np.abs(error), 95)),
                "max_abs_m": float(np.abs(error).max()),
            }
    raw = {"dem": dem, "sampled_stages": np.stack(list(sampled.values()))}
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output.with_suffix(".npz"), **raw)
    report = {
        "slug": slug,
        "diagnostic_only": True,
        "thresholds_unchanged": gt.THRESHOLDS,
        "source_dem": {"url": gt.TILE_URL, "zoom": gt.ZOOM},
        "grid_step_m": gt.STEP * 16,
        "fit": fit,
        "stages": stats,
        "subsets_not_acceptance_masks": subsets,
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                fixture / "input.png",
                fixture / "banks.f32.gz",
                fixture / "shipping-geometry.json.gz",
            ]
        },
        "prepared_terrain_sha256": hashlib.sha256(
            (prepared / "terrain.u16").read_bytes()
        ).hexdigest(),
        "counterfactual_note": "Lake restoration is an attribution experiment, not a proposed shipping bed or a rerun of acceptance.",
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("prepared", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    diagnose(args.slug, args.prepared, args.output)
