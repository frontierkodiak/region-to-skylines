"""CPU-only falsification of held-DEM local-stage admission; never qualification.

No package is generated and the default prepare() does not use this path.
Source classification sees no region names, cameras, probes or native results.
Frozen observations are read only after terrain planning, to test that plan.
"""

import argparse
import gzip
import hashlib
import inspect
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

from admission import remove_connector_cuts
from region import fit_networks, hydrology, limit_source_footprints, start_area
from surface_water import surface_geometry
from verify_bank_restoration import native_water_ground, require_continuous_floor

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "cs1-harness"))
from cs1_harness.verdict import MAP_SOAK, required  # noqa: E402


def q(grid):
    return np.floor(np.flipud(grid) * 64 + 0.5).clip(0, 65535).astype("<u2")


def read(path):
    return json.loads(path.read_text())


def require_experimental_writer():
    if "fixed_paths" not in inspect.signature(hydrology).parameters:
        raise RuntimeError(
            "Rejected held-DEM experiment: replay a4b9653 in a separate worktree; the default writer is unchanged"
        )


def near_grid(terrain, stage_grid, positions):
    xy = np.asarray(positions)
    centers = np.rint((xy + 8640) / 16).astype(int)
    projected_wet = stage_grid.astype(int) - terrain.astype(int) >= 7
    near = np.zeros(len(positions), dtype=bool)
    for dz in range(-4, 5):
        for dx in range(-4, 5):
            cells = centers + [dx, dz]
            valid = ((cells >= 0) & (cells <= 1080)).all(axis=1)
            valid &= ((cells * 16 - 8640 - xy) ** 2).sum(axis=1) <= 64 * 64
            ids = np.flatnonzero(valid)
            near[ids] |= projected_wet[cells[ids, 1], cells[ids, 0]]
    return near


def native_ground_batch(terrain, positions):
    """Vectorized replay; compared with the installed-IL reference each case."""
    ground = np.asarray(terrain).reshape(1081, 1081).astype(np.int64)
    p = np.asarray(positions, dtype=np.float32)
    ix, iz = np.floor((p + np.float32(8640)) * np.float32(16)).astype(np.int64).T
    x0, x1 = np.clip(ix >> 8, 0, 1080), np.clip((ix >> 8) + 1, 0, 1080)
    z0, z1 = np.clip(iz >> 8, 0, 1080), np.clip((iz >> 8) + 1, 0, 1080)
    a = ground[z0, x0] + ((ground[z1, x0] - ground[z0, x0]) * (iz & 255) >> 8)
    b = ground[z0, x1] + ((ground[z1, x1] - ground[z0, x1]) * (iz & 255) >> 8)
    return (a + ((b - a) * (ix & 255) >> 8)) / 64


def probe(slug, reference, output):
    require_experimental_writer()
    fixture = ROOT / "fixtures" / slug
    geometry, _ = surface_geometry(
        json.loads(
            gzip.decompress((fixture / "shipping-geometry.json.gz").read_bytes())
        )
    )
    original = np.asarray(Image.open(fixture / "input.png"), dtype=float) * 1024 / 65535
    banks = (
        np.frombuffer(gzip.decompress((fixture / "banks.f32.gz").read_bytes()), "<f4")
        .reshape(1081, 1081)
        .astype(float)
    )
    legacy_ground = original.copy()
    surveys = []
    paths = {}
    legacy_stage = np.full_like(original, geometry.get("seaLevel") or 0)
    legacy_depth, _ = hydrology(
        legacy_ground,
        banks,
        geometry,
        surveys=surveys,
        stages=legacy_stage,
        paths=paths,
    )
    start = start_area(legacy_ground, legacy_depth, geometry)
    spec = read(ROOT / "templates/native-corridors.json")
    layout = fit_networks(legacy_ground.copy(), legacy_depth, geometry, spec, start)
    baseline = read(reference / slug / "probes.json")
    ground = original.copy()
    if surveys:
        # Reuse the proven browser-kernel replay, not its rejected selector.
        ground, restoration = remove_connector_cuts(
            original, banks, geometry, [{**s, "gravity_excess_m": []} for s in surveys]
        )
    else:
        restoration = {"restored_vertices": 0}
    stage = np.full_like(ground, geometry.get("seaLevel") or 0)
    held_ground = ground.copy()
    admission_mask = np.zeros_like(ground, dtype=bool)
    depth, summary = hydrology(
        ground,
        banks,
        geometry,
        stages=stage,
        admission_mask=admission_mask,
        fixed_paths=paths,
    )
    planned_ground = ground.copy()
    supported = ndimage.maximum_filter(stage > ground, size=3, mode="constant")
    restore = admission_mask & ~supported & (ground < held_ground)
    old_surface = ground + depth
    ground[restore] = held_ground[restore]
    depth = np.maximum(0, old_surface - ground)
    require_continuous_floor(
        q(planned_ground), q(ground), q(np.maximum(0, stage - planned_ground))
    )
    before_network = ground.copy()
    network = fit_networks(
        ground, depth, geometry, spec, start, layout["node_positions"]
    )
    unsupported_controls = []
    for source in summary["sources"]:
        if not source.get("bank_limited"):
            continue
        col = round(540 + source["position"][0] / 16)
        row = round(540 - source["position"][2] / 16)
        target = np.floor(source["target"] * 64) / 64
        if target <= ground[row, col] + 0.125:
            unsupported_controls.append(
                {
                    "name": source["name"],
                    "role": source["role"],
                    "position": source["position"],
                    "target_m": float(target),
                    "prepared_ground_m": float(ground[row, col]),
                    "uncarved_dem_m": float(banks[row, col]),
                    "target_minus_dem_m": float(target - banks[row, col]),
                    "target_minus_floor_m": float(target - ground[row, col]),
                    "minimum_depth_guard_m": 0.125,
                }
            )
    footprint_error = None
    try:
        limit_source_footprints(ground, depth, banks, geometry, summary)
    except ValueError as error:
        footprint_error = str(error)
    summary.update(network)
    summary.update(
        start_tile=start["index"],
        start_area=start,
        map_id="PL857-" + slug,
        map_name=geometry["sq"]["name"] + " - Ready to Play",
        wet_cells=int((depth > 0).sum()),
        bank_input="uncarved browser elevations",
    )
    # This is an optimistic local profile field, NOT a hydraulic prediction:
    # actual controls are sparse, and their exact footprint test is separate.
    predicted = np.maximum(0, stage - ground)
    terrain, stage_grid = q(ground), q(stage)
    points = {p["name"]: p for p in baseline["points"]}
    first = next(
        json.loads(line)
        for line in (reference / slug / "timeline.jsonl").read_text().splitlines()
        if json.loads(line)["kind"] == "sample"
    )
    cohort = [
        p for p in first["water"]["samples"] if required(p, points[p["name"]], MAP_SOAK)
    ]
    positions = [[p["x"], p["z"]] for p in cohort]
    replay_ground = native_ground_batch(terrain, positions)
    replay_stage = native_ground_batch(stage_grid, positions)
    np.testing.assert_array_equal(
        replay_ground, native_water_ground(terrain, positions)
    )
    np.testing.assert_array_equal(
        replay_stage, native_water_ground(stage_grid, positions)
    )
    # Match CityOps.cs: surrounding 16m grid centres in the true 64m disk.
    # The depth field here is a planning estimate, never native water data.
    near = near_grid(terrain, stage_grid, positions)
    legacy_near = near_grid(q(legacy_ground), q(legacy_stage), positions)
    regressions = [
        p["name"]
        for i, p in enumerate(cohort)
        if (p["wet"] or p.get("wet_within_64m")) and not near[i]
    ]
    new_model_dry = [
        p["name"] for i, p in enumerate(cohort) if legacy_near[i] and not near[i]
    ]
    carved = ground < banks - 1 / 64
    dry_cut = carved & (predicted <= 0.1)
    legacy_dry = (legacy_ground < banks - 1 / 64) & (
        legacy_stage - legacy_ground <= 0.1
    )
    folder = output / slug
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "hydrology.json").write_text(json.dumps(summary, indent=2) + "\n")
    np.savez_compressed(
        folder / "design-grids.npz",
        ground=ground,
        banks=banks,
        optimistic_stage=stage,
        before_network=before_network,
        initial_depth=depth,
    )
    result = {
        "slug": slug,
        "cpu_only": True,
        "new_planned_continuous_floor_guard": True,
        "native_qualified": False,
        "restored_vertices": restoration["restored_vertices"],
        "selected_reaches": len(surveys),
        "required": len(cohort),
        "baseline_t000_wet_or_near": sum(
            bool(p["wet"] or p.get("wet_within_64m")) for p in cohort
        ),
        "optimistic_near64_count": int(near.sum()),
        "optimistic_new_dry_count": len(regressions),
        "optimistic_new_dry_names": regressions,
        "baseline_optimistic_near64_count": int(legacy_near.sum()),
        "model_regression_count": len(new_model_dry),
        "model_regression_names": new_model_dry,
        "exact_predicted_depth_min_m": float((replay_stage - replay_ground).min()),
        "dry_cut_km2": float(dry_cut.sum() * 256 / 1e6),
        "legacy_optimistic_dry_cut_km2_not_settled": float(
            legacy_dry.sum() * 256 / 1e6
        ),
        "start_tile": start["index"],
        "horizontal_network_unchanged": all(
            v[::2] == network["node_positions"][k][::2]
            for k, v in layout["node_positions"].items()
        ),
        "control_targets": summary["sources"],
        "caveat": "Optimistic local stages, not native water. No-film regressor is a preflight falsification, not acceptance. The original frozen probe file and native receipt are never changed.",
        "frozen_probes_sha256": hashlib.sha256(
            (reference / slug / "probes.json").read_bytes()
        ).hexdigest(),
        "source_footprint_error": footprint_error,
        "unsupported_controls": unsupported_controls,
    }
    (folder / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                not in [
                    "control_targets",
                    "optimistic_new_dry_names",
                    "unsupported_controls",
                ]
            }
        ),
        flush=True,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--only",
        nargs="+",
        default=["rio", "asheville", "innsbruck", "pittsburgh", "charleston"],
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = [probe(slug, args.reference, args.output) for slug in args.only]
    (args.output / "reports.json").write_text(json.dumps(results, indent=2) + "\n")
