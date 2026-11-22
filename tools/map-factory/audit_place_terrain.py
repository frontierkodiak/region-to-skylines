"""Attribute terrain errors offline without changing inputs or native gates.

Compare the canonical DEM, fitted banks, input PNG and prepared native terrain
in one frame. A source/reference disagreement must not be attributed to the
exporter. This is a diagnostic, not a map-qualification or water-safety gate.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

from place_input import Frame, sample_grid
from place_model import read_grid, read_manifest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "cs1-harness"))
from cs1_harness import groundtruth as gt  # noqa: E402
from cs1_harness import report as native_report  # noqa: E402


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_units(north_metres):
    """The writer's exact final quantization and north-to-south conversion."""
    return np.floor(np.flipud(north_metres) * 64 + 0.5).clip(0, 65535).astype("<u2")


def stage_metrics(north_metres, reference_south, source_game_north, fit):
    """Use the unchanged frozen metrics; source error includes all vertices."""
    raw = native_units(north_metres)
    game_north = np.flipud(raw[:: gt.STEP, :: gt.STEP]) / 64.0
    if game_north.shape != reference_south.shape:
        raise ValueError("Reference shape differs from the frozen judge grid")
    reference_north = np.flipud(reference_south)
    scores = {
        name: round(gt.corr(game_north, turn(reference_north)), 4)
        for name, turn in gt.TRANSFORMS.items()
    }
    source_error = (north_metres - source_game_north) / fit["verticalScale"]
    quantization_error = np.flipud(raw) / 64.0 - north_metres
    return {
        "terracing": native_report.terracing(raw),
        "correlation": scores,
        "identity_margin": round(
            scores["as is"] - max(v for k, v in scores.items() if k != "as is"),
            4,
        ),
        "error_vs_canonical_dem_source_metres": {
            "mean_abs": float(np.abs(source_error).mean()),
            "p95_abs": float(np.percentile(np.abs(source_error), 95)),
            "maximum_abs": float(np.abs(source_error).max()),
            "signed_percentiles_0_1_5_50_95_99_100": np.percentile(
                source_error, [0, 1, 5, 50, 95, 99, 100]
            ).tolist(),
        },
        "native_quantization_maximum_abs_game_metres": float(
            np.abs(quantization_error).max()
        ),
    }


def audit(place, inputs, prepared, output):
    """Audit an exact place/compiled-input/prepared-terrain tuple, read-only."""
    manifest_path = place / "place.json"
    manifest = read_manifest(place)
    geometry_path = inputs / "geometry.json"
    geometry = json.loads(geometry_path.read_text())
    if geometry["placeInput"]["manifest_sha256"] != sha256(manifest_path):
        raise ValueError("Place manifest differs from the one bound to these inputs")
    terrain_desc = manifest["layers"]["terrain"]
    terrain_path = place / terrain_desc["path"]
    if sha256(terrain_path) != terrain_desc["sha256"]:
        raise ValueError("Canonical terrain differs from its manifest hash")
    frame = Frame(manifest)
    region = {
        "lon": frame.sq["lon"],
        "lat": frame.sq["lat"],
        "size_m": frame.side,
        "rotation": 0,
    }
    fit = geometry["fit"]
    if (
        not np.isfinite([fit["base"], fit["verticalScale"]]).all()
        or fit["verticalScale"] <= 0
    ):
        raise ValueError("Terrain fit must be finite with positive vertical scale")
    source = sample_grid(read_grid(place, "terrain"), terrain_desc, frame.crop, gt.N)
    source_game = (source - fit["base"]) * fit["verticalScale"] + 50
    banks_path, png_path = inputs / "banks.f32", inputs / "input.png"
    prepared_path = prepared / "terrain.u16"
    with Image.open(png_path) as image:
        png = np.asarray(image, dtype=float) * 1024 / 65535
    stages = {
        "canonical_affine_only": source_game,
        "fitted_banks": np.fromfile(banks_path, "<f4").reshape(gt.N, gt.N),
        "input_png": png,
        "prepared_native": np.flipud(gt.game_terrain(prepared_path)),
    }
    if any(
        a.shape != (gt.N, gt.N) or not np.isfinite(a).all() for a in stages.values()
    ):
        raise ValueError("All stages must be finite 1081 by 1081 grids")
    coordinates = np.arange(0, gt.N, gt.STEP) * gt.CELL - gt.HALF
    zz, xx = np.meshgrid(coordinates, coordinates, indexing="ij")
    inverse, _ = gt.projection(region)
    lon, lat = inverse(xx, zz)
    reference = gt.dem_at(np.asarray(lon), np.asarray(lat))
    metrics = {
        name: stage_metrics(a, reference, source_game, fit)
        for name, a in stages.items()
    }
    result = {
        "schema": "place-terrain-stage-audit/1",
        "diagnostic_only": True,
        "native_run_performed": False,
        "place": manifest["id"],
        "region": region,
        "fit": fit,
        "stages": metrics,
        "thresholds_unchanged": {
            **gt.THRESHOLDS,
            "terracing": native_report.TERRACED,
        },
        "reference": {
            "url": gt.TILE_URL,
            "zoom": gt.ZOOM,
            "step_game_metres": gt.STEP * gt.CELL,
            "points": int(reference.size),
        },
        "sha256": {
            "place_manifest": sha256(manifest_path),
            "canonical_terrain": sha256(terrain_path),
            "geometry": sha256(geometry_path),
            "banks": sha256(banks_path),
            "png": sha256(png_path),
            "prepared_terrain": sha256(prepared_path),
            "groundtruth_code": sha256(Path(gt.__file__)),
            "report_code": sha256(Path(native_report.__file__)),
            "audit_code": sha256(Path(__file__)),
        },
        "limitations": [
            "Affine-only source is a counterfactual, not an exported or water-qualified map.",
            "Source and independent reference can disagree before any exporter policy.",
            "Offline grid metrics do not replace native world-sampler observations.",
            "No points, water polygons or failures are excluded; no threshold is tuned.",
        ],
    }
    output.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(output / "stages.npz", reference_south=reference, **stages)
    result["sha256"]["retained_arrays"] = sha256(output / "stages.npz")
    (output / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("place", type=Path)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("output", type=Path, help="New diagnostic directory")
    arguments = parser.parse_args()
    print(json.dumps(audit(**vars(arguments)), indent=2))
