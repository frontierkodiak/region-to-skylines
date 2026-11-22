"""Full-grid geometry/floor/control-distance drawdown; not causal flux inference."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crp import read_package  # noqa: E402
from region import raster  # noqa: E402
from water_diagnostics import decode_water  # noqa: E402

POLICY = "calibration/pl1191-construction-v1/development/phase19-drawdown-policy.md"
DISTANCE_BINS = [128, 512, 2048]
FLOOR_BINS = [-8, -2, 0]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def grid(path):
    return np.fromfile(path, "<u2").reshape(1081, 1081)


def quantiles(values):
    values = np.asarray(values)
    if not values.size:
        return {
            "count": 0,
            "min": None,
            "p10": None,
            "median": None,
            "p90": None,
            "max": None,
        }
    return dict(
        zip(
            ["min", "p10", "median", "p90", "max"],
            map(float, np.percentile(values, [0, 10, 50, 90, 100])),
        ),
        count=int(values.size),
    )


def classes(control_distance, boundary_distance, floor, ocean, sea):
    if not all(
        v.shape == floor.shape for v in [control_distance, boundary_distance, ocean]
    ):
        raise ValueError("Geometry strata do not share a complete lattice")
    control = np.searchsorted(DISTANCE_BINS, control_distance, side="right")
    boundary = np.searchsorted(DISTANCE_BINS, boundary_distance, side="right")
    bed = np.searchsorted(FLOOR_BINS, floor - sea, side="right")
    return (((ocean.astype(int) * 4 + bed) * 4 + boundary) * 4 + control).astype("u1")


def interval_metrics(mask, initial, final, elapsed):
    a, b = initial[mask].astype(float) / 64, final[mask].astype(float) / 64
    paired = (a > 0.1) & (b > 0.1)
    return {
        "all_vertices": int(mask.sum()),
        "initial_wet": int(np.count_nonzero(a > 0.1)),
        "final_wet": int(np.count_nonzero(b > 0.1)),
        "net_depth_change_q": int(
            np.sum(final[mask].astype(np.int64) - initial[mask].astype(np.int64))
        ),
        "all_vertex_depth_change_m_per_game_min": quantiles((b - a) / elapsed),
        "paired_wet_head_change_m_per_game_min": quantiles(
            (b[paired] - a[paired]) / elapsed
        ),
        "unobserved_paired_head_vertices": int(len(a) - paired.sum()),
    }


def near_far_comparison(near, far):
    # No common support is a finding, never a zero association or pooled proof.
    if not near["all_vertices"] or not far["all_vertices"]:
        return {
            "status": "no common geometric support",
            "median_difference_m_per_game_min": None,
        }
    return {
        "status": "descriptive association only",
        "median_difference_m_per_game_min": near[
            "all_vertex_depth_change_m_per_game_min"
        ]["median"]
        - far["all_vertex_depth_change_m_per_game_min"]["median"],
    }


def stage(parent, native, result, review, acceptance, output):
    if output.exists():
        raise ValueError("Fresh read-only protocol required")
    if (
        sha(parent / "native-plan.json")
        != "ec4b88258310808f7a558c10c8368a384abd99bede88f5864441079b892e130f"
        or sha(result / "result.json")
        != "2b52060635addd2d36149e34f6516309910e035e839ebb555a3728f986efab75"
        or load(result / "receipt.json")["result_sha256"] != sha(result / "result.json")
    ):
        raise ValueError("Wrong reviewed physical/query/measurement cohort")
    parent_plan = load(parent / "native-plan.json")
    if (
        sha(parent / "physical/PL857-low-coast-oceania.crp")
        != parent_plan["package_sha256"]
        or sha(parent / "physical/probes.json") != parent_plan["probes_sha256"]
        or load(result / "result.json")["native_plan_sha256"]
        != sha(parent / "native-plan.json")
    ):
        raise ValueError("Reviewed parent identities differ")
    output.mkdir(parents=True)
    manifest = load(result / "receipt.json")["native_files_sha256"]
    data = load(result / "result.json")
    snapshots = data["samples"]
    if len(snapshots) != 61:
        raise ValueError("Expected complete retained 61-snapshot cohort")
    files = [
        (parent / "native-plan.json", "parent-native-plan.json"),
        (result / "result.json", "parent-result.json"),
        (result / "receipt.json", "parent-receipt.json"),
        (review, "review.json"),
        (acceptance, "acceptance.json"),
    ]
    for name in [
        "geometry.json",
        "probes.json",
        "terrain.u16",
        "water.u16",
        "PL857-low-coast-oceania.crp",
    ]:
        files.append((parent / "physical" / name, "physical/" + name))
    floor_hashes = {}
    for row in snapshots:
        prefix = row["prefix"]
        depth = native / "grids" / (prefix + "-water.u16")
        if sha(depth) != manifest["grids/" + depth.name]:
            raise ValueError("Retained raw depth differs")
        floor = native / "grids" / (prefix + "-water-ground.u16")
        floor_hashes[prefix] = sha(floor)
        if floor_hashes[prefix] != row["floor_sha256"]:
            raise ValueError("Actual floor readback differs")
        files.append((depth, "grids/" + depth.name))
    if len(set(floor_hashes.values())) != 1:
        raise ValueError("Changing floors require a new explicit head model")
    files.append(
        (
            native / "grids" / (snapshots[0]["prefix"] + "-water-ground.u16"),
            "actual-floor.u16",
        )
    )
    for source, name in files:
        destination = output / name
        destination.parent.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(source, destination)
    sources = list(ROOT.glob("*.py")) + [
        Path(__file__),
        ROOT / "diagnostics/test_coastal_drawdown_strata.py",
        ROOT / POLICY,
        ROOT / "uv.lock",
    ]
    freeze = {
        "schema": "polli.coastal-drawdown-strata/1",
        "known_prior_evidence": "PL-1253 review and accepted phase17; not outcome-blind",
        "method_commit": subprocess.check_output(
            ["git", "-C", str(ROOT.parents[1]), "rev-parse", "HEAD"], text=True
        ).strip(),
        "files_sha256": {
            str(p.relative_to(output)): sha(p)
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
        "source_files_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sources},
        "all_retained_actual_floor_hashes": floor_hashes,
        "new_native_or_acceptance": False,
    }
    write(output / "freeze.json", freeze)
    return {"freeze_sha256": sha(output / "freeze.json")}


def preflight(folder):
    freeze = load(folder / "freeze.json")
    for root, field in [(folder, "files_sha256"), (ROOT, "source_files_sha256")]:
        for name, expected in freeze[field].items():
            if sha(root / name) != expected:
                raise ValueError("Bound byte mismatch: " + name)
    return freeze


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh result required")
    geo = load(folder / "physical/geometry.json")
    data = load(folder / "parent-result.json")
    payload = next(
        a["payload"]
        for a in read_package(
            (folder / "physical/PL857-low-coast-oceania.crp").read_bytes()
        )[1]
        if a["kind"] == 52
    )
    decoded = decode_water(payload)
    controls = np.array(
        [[c["position"][0], c["position"][2]] for c in decoded["sources"]]
    )
    if len(controls) != 167 or any(c["intake_rate"] for c in decoded["sources"]):
        raise ValueError("Expected original167 encoded controls, intakes zero")
    floor = grid(folder / "actual-floor.u16").astype(float) / 64
    ocean = np.flipud(raster(geo["sq"], geo.get("oceans", []), polygons=True))
    seeds = np.zeros_like(ocean)
    seeds[[0, -1], :] = ocean[[0, -1], :]
    seeds[:, [0, -1]] = ocean[:, [0, -1]]
    if not seeds.any():
        raise ValueError("No literal ocean-edge seed; boundary distance unknown")
    boundary_distance = ndimage.distance_transform_edt(~seeds) * 16
    rows, cols = np.indices(floor.shape)
    points = np.column_stack([(cols.ravel() - 540) * 16, (rows.ravel() - 540) * 16])
    control_distance = cKDTree(controls).query(points)[0].reshape(floor.shape)
    ids = classes(
        control_distance, boundary_distance, floor, ocean, decoded["sea_level_m"]
    )
    samples = data["samples"]
    early = [r for r in samples if r["minute"] <= 5]
    if len(early) < 2:
        raise ValueError("Insufficient original early samples")
    first, last = early[0], early[-1]
    initial = grid(folder / "grids" / (first["prefix"] + "-water.u16"))
    final = grid(folder / "grids" / (last["prefix"] + "-water.u16"))
    elapsed = last["minute"] - first["minute"]
    strata = []
    for i in range(128):
        mask = ids == i
        strata.append(
            {
                "id": i,
                "literal_ocean": bool(i // 64),
                "floor_relative_sea_bin": (i // 16) % 4,
                "ocean_edge_distance_bin": (i // 4) % 4,
                "control_distance_bin": i % 4,
                **interval_metrics(mask, initial, final, elapsed),
            }
        )
    contrasts = []
    for ocean_id in range(2):
        for bed in range(4):
            for edge in range(4):
                base = ((ocean_id * 4 + bed) * 4 + edge) * 4
                contrasts.append(
                    {
                        "literal_ocean": bool(ocean_id),
                        "floor_relative_sea_bin": bed,
                        "ocean_edge_distance_bin": edge,
                        **near_far_comparison(strata[base], strata[base + 3]),
                    }
                )
    far_deep = (
        ocean & (floor - decoded["sea_level_m"] < -2) & (control_distance >= 2048)
    )
    timeline = []
    for row in samples:
        depth = grid(folder / "grids" / (row["prefix"] + "-water.u16"))
        timeline.append(
            {
                "prefix": row["prefix"],
                "minute": row["minute"],
                "full_grid_depth_sum_q": int(depth.astype(np.uint64).sum()),
                "far_deep_ocean_vertices": int(far_deep.sum()),
                "far_deep_ocean_depth_change_m": quantiles(
                    (depth[far_deep].astype(float) - initial[far_deep]) / 64
                ),
                "boundary_source_ocean_wet_heads_m": quantiles(
                    (floor + depth / 64)[seeds & (depth > 6.4)]
                ),
            }
        )
    result = {
        "schema": "polli.coastal-drawdown-strata-result/1",
        "input_freeze_sha256": sha(folder / "freeze.json"),
        "full_grid_vertices": int(ids.size),
        "partition_count_matches_full_grid": sum(s["all_vertices"] for s in strata)
        == ids.size,
        "strata_distance_edges_m_left_inclusive": DISTANCE_BINS,
        "floor_relative_sea_edges_m_left_inclusive": FLOOR_BINS,
        "early_interval": {
            "first": first["prefix"],
            "last": last["prefix"],
            "minutes": elapsed,
            "rule": "first and last retained capture with game minute<=5, independent of water outcomes",
        },
        "strata": strata,
        "near_lt128_vs_far_ge2048_same_floor_boundary_stratum": contrasts,
        "full_61_sample_timeline": timeline,
        "far_deep_literal_ocean_early": interval_metrics(
            far_deep, initial, final, elapsed
        ),
        "configured_control_description": "167 output-enabled encoded controls with intake rate zero; not established active sinks or calibrated physical influence radius",
        "interpretation": "Distance-stratified association/finite differences only; control distance, authored floor and boundary proximity are confounded. No integrated flux, evaporation or exclusive causal mechanism established.",
        "full_hour_acceptance": "incomplete/unknown",
        "stable_water_promise": "unknown",
    }
    output.mkdir(parents=True)
    np.savez_compressed(
        output / "geometry-strata.npz",
        stratum_ids=ids,
        control_distance_m=control_distance.astype("f4"),
        ocean_edge_distance_m=boundary_distance.astype("f4"),
        far_deep_literal_ocean=far_deep,
    )
    write(output / "result.json", result)
    write(
        output / "receipt.json",
        {
            "freeze_sha256": sha(folder / "freeze.json"),
            "result_sha256": sha(output / "result.json"),
            "strata_sha256": sha(output / "geometry-strata.npz"),
        },
    )
    return {
        "result_sha256": sha(output / "result.json"),
        "partition_complete": result["partition_count_matches_full_grid"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, args in [
        ("stage", ["parent", "native", "result", "review", "acceptance", "output"]),
        ("preflight", ["folder"]),
        ("evaluate", ["folder", "output"]),
    ]:
        p = commands.add_parser(name)
        for arg in args:
            p.add_argument(arg, type=Path)
    args = vars(parser.parse_args())
    print(json.dumps(globals()[args.pop("command")](**args), indent=2))
