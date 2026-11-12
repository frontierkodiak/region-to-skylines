"""Read-only retained surface-river coverage audit; no acceptance gate or hydrology fitting.
Run with the harness uv environment. --case SLUG RUN_DIRECTORY GEOMETRY_JSON repeatable.
Outputs only under --out. Existing artifacts are never changed. No network calls.
"""

import argparse
import collections
import hashlib
import importlib.util
import json
import math
import pathlib

import numpy as np

ROOT = pathlib.Path.cwd()
GROUND = (
    pathlib.Path(__file__).resolve().parents[1]
    / "cs1-harness/cs1_harness/groundtruth.py"
)
N = 1081


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path):
    path = pathlib.Path(path)
    try:
        name = str(path.relative_to(ROOT))
    except ValueError:
        name = path.name
    return {"file": name, "sha256": sha(path), "bytes": path.stat().st_size}


def read(path):
    return json.loads(path.read_text())


def raster(a, b):
    """Split projected segment at nearest-cell half-integer boundaries.
    Return (flat cell index, true projected segment length inside cell), with
    half-open nearest-center cells; no resampling/minimum reach-length cutoff.
    """
    a, b = np.asarray(a) / 16 + 540, np.asarray(b) / 16 + 540
    delta = b - a
    ts = [0.0, 1.0]
    for axis in (0, 1):
        if not delta[axis]:
            continue
        low, high = sorted((a[axis], b[axis]))
        boundaries = np.arange(math.ceil(low - 0.5), math.floor(high - 0.5) + 1) + 0.5
        ts.extend(float(t) for t in (boundaries - a[axis]) / delta[axis] if 0 < t < 1)
    ts = sorted(set(ts))
    length = float(np.linalg.norm(delta)) * 16
    for lo, hi in zip(ts, ts[1:]):
        x, z = np.floor(a + delta * ((lo + hi) / 2) + 0.5).astype(int)
        if 0 <= x < N and 0 <= z < N:
            yield int(z * N + x), length * (hi - lo)
    # Include isolated endpoints and zero-length features, not just traversed intervals.
    for point in (a, b):
        x, z = np.floor(point + 0.5).astype(int)
        if 0 <= x < N and 0 <= z < N:
            yield int(z * N + x), 0.0


def nearby(wet):
    near = wet.copy()
    for dz in range(-4, 5):
        for dx in range(-4, 5):
            if dx * dx + dz * dz > 16:
                continue
            near[max(0, dz) : N + min(0, dz), max(0, dx) : N + min(0, dx)] |= wet[
                max(0, -dz) : N - max(0, dz), max(0, -dx) : N - max(0, dx)
            ]
    return near


def bbox(cells):
    zs, xs = np.divmod(np.fromiter(cells, dtype=int), N)
    return [
        int(xs.min() * 16 - 8640),
        int(zs.min() * 16 - 8640),
        int(xs.max() * 16 - 8640),
        int(zs.max() * 16 - 8640),
    ]


def components(cells, owners):
    left = set(cells)
    result = []
    while left:
        first = left.pop()
        pending, group = [first], {first}
        while pending:
            cell = pending.pop()
            z, x = divmod(cell, N)
            for dz in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if not (0 <= x + dx < N and 0 <= z + dz < N):
                        continue
                    neighbor = cell + dz * N + dx
                    if neighbor in left:
                        left.remove(neighbor)
                        group.add(neighbor)
                        pending.append(neighbor)
        result.append(
            {
                "cells": len(group),
                "bbox_world_xz_m": bbox(group),
                "names": sorted(set(n for c in group for n in owners[c])),
            }
        )
    return sorted(result, key=lambda r: -r["cells"])


def summary(cells, wet, near, owners):
    exact_dry = [c for c in cells if not wet.flat[c]]
    nearby_dry = [c for c in cells if not near.flat[c]]
    n = len(cells)
    return {
        "mapped_cells": n,
        "exact_wet_cells": n - len(exact_dry),
        "near64_wet_cells": n - len(nearby_dry),
        "exact_wet_fraction": (n - len(exact_dry)) / n if n else None,
        "near64_wet_fraction": (n - len(nearby_dry)) / n if n else None,
        "exact_dry_components": components(exact_dry, owners),
        "near64_dry_components": components(nearby_dry, owners),
    }


def longest_stretches(features, mask):
    stretches = []
    for feature in features:
        length, cells = 0.0, set()

        def flush():
            if length:
                stretches.append(
                    {
                        "feature_index": feature["index"],
                        "name": feature["name"],
                        "length_m": round(length, 2),
                        "cells": len(cells),
                        "bbox_world_xz_m": bbox(cells),
                        "source_feature": feature["source"],
                    }
                )

        for cell, part_length in feature["intervals"]:
            if not part_length:
                continue
            if not mask.flat[cell]:
                length += part_length
                cells.add(cell)
            else:
                flush()
                length, cells = 0.0, set()
        flush()
    return sorted(stretches, key=lambda r: -r["length_m"])


def audit(slug, run, geometry, projection):
    report_path = run / "report.json"
    report = read(report_path)
    asked, got = report.get("requested_game_minutes"), report.get("game_minutes")
    if (
        not asked
        or got is None
        or got < asked * 0.99
        or not (run / "session-receipt.json").is_file()
    ):
        raise ValueError(
            f"{slug}: not a completed declared run; refusing to report partial data"
        )
    geo = read(geometry)
    region = {**geo["sq"], "rotation": 0, "size_m": 17280}
    _, project = projection(region)
    by_name, owners, features = (
        collections.defaultdict(set),
        collections.defaultdict(set),
        [],
    )
    tunnel = []
    for i, river in enumerate(geo["rivers"]):
        if river.get("brunnel") == "tunnel":
            tunnel.append(
                {
                    "index": i,
                    "name": river.get("name"),
                    "sourceFeature": river.get("sourceFeature"),
                }
            )
            continue
        name = river.get("name") or "(unnamed river)"
        points = river.get("pts", [])
        projected = [project(*p) for p in points]
        intervals = []
        for a, b in zip(projected, projected[1:]):
            intervals.extend(raster(a, b))
        if len(projected) == 1:
            intervals.extend(raster(projected[0], projected[0]))
        cells = {c for c, _ in intervals}
        by_name[name].update(cells)
        for c in cells:
            owners[c].add(name)
        sf = river.get("sourceFeature") or {}
        features.append(
            {
                "index": i,
                "name": name,
                "source": {
                    k: sf.get(k)
                    for k in (
                        "feature_id",
                        "feature_index",
                        "line_index",
                        "piece_index",
                        "original_field",
                        "original_index",
                    )
                },
                "input_vertices": len(points),
                "mapped_cells": len(cells),
                "intervals": intervals,
            }
        )
    all_cells = set(owners)
    central = {
        c
        for c in all_cells
        if max(abs((c % N) * 16 - 8640), abs((c // N) * 16 - 8640)) <= 4800
    }
    declared = [
        r
        for r in geo.get("undergroundWaterways", [])
        if (r.get("sourceFeature") or {}).get("original_field") == "rivers"
        or r.get("class") == "river"
    ]
    if any(r.get("brunnel") != "tunnel" for r in declared):
        raise ValueError("underground declaration without explicit tunnel flag")
    manifest = [
        ref(geometry),
        ref(report_path),
        ref(run / "session-receipt.json"),
        ref(run / "probes.json"),
    ]
    for extra in (geometry.parent / "generation.json", run / "input-audit.json"):
        if extra.is_file():
            manifest.append(ref(extra))
    hydro_path = geometry.parent / "hydrology.json"
    hydro = read(hydro_path) if hydro_path.is_file() else {}
    if hydro:
        manifest.append(ref(hydro_path))
    source_map = (report.get("session") or {}).get("map") or {}
    if not source_map.get("sha256") or len(source_map["sha256"]) != 64:
        raise ValueError("missing full native run CRP checksum")
    generation_path = geometry.parent / "generation.json"
    if generation_path.is_file():
        generation = read(generation_path)
        expected_geometry = generation.get("resources", {}).get(
            "prepared_geometry_sha256"
        )
        geometry_binding = {
            "generation_geometry_sha256": expected_geometry,
            "geometry_sha256_matches_generation": sha(geometry) == expected_geometry
            if expected_geometry
            else None,
            "generation_crp_sha256": generation.get("package", {}).get("sha256"),
            "generation_crp_matches_run": generation.get("package", {}).get("sha256")
            == source_map["sha256"],
        }
    else:
        geometry_binding = None
    map_source = pathlib.Path(source_map.get("source") or "/nonexistent")
    map_receipt = {"report_crp_sha256": source_map["sha256"], "actual_source_crp": None}
    if map_source.is_file():
        map_receipt["actual_source_crp"] = ref(map_source)
        if sha(map_source) != source_map["sha256"]:
            raise ValueError("source CRP bytes no longer match native run receipt")
    frozen_probes = read(run / "probes.json").get("points", [])
    probe_cohorts = {}
    for name in by_name:
        matching = [
            p for p in frozen_probes if p.get("name", "").split(" [")[0] == name
        ]
        probe_cohorts[name] = {
            "all_named_probes": len(matching),
            "river_labeled": sum("[river]" in p["name"] for p in matching),
            "stream_labeled": sum("[stream]" in p["name"] for p in matching),
            "central25_river_labeled": sum(
                "[river]" in p["name"] and max(abs(p["x"]), abs(p["z"])) <= 4800
                for p in matching
            ),
        }
    snapshots = []
    wet_all_times = np.ones((N, N), dtype=bool)
    near_all_times = wet_all_times.copy()
    for grid in sorted((run / "grids").glob("t*-water.u16")):
        if grid.stat().st_size != N * N * 2:
            raise ValueError(f"wrong native grid size: {grid.name}")
        manifest.append(ref(grid))
        water = np.fromfile(grid, dtype="<u2").reshape(N, N)
        wet = water / 64 > 0.1
        near = nearby(wet)
        wet_all_times &= wet
        near_all_times &= near
        snapshots.append(
            {
                "grid": grid.name,
                "all": summary(all_cells, wet, near, owners),
                "central25": summary(central, wet, near, owners),
                "named_rivers": {
                    name: {
                        "all": summary(cells, wet, near, owners),
                        "central25": summary(cells & central, wet, near, owners),
                    }
                    for name, cells in sorted(by_name.items())
                },
                "exact_dry_stretches_along_source_features": longest_stretches(
                    features, wet
                ),
                "near64_dry_stretches_along_source_features": longest_stretches(
                    features, near
                ),
            }
        )
    if not any(g["grid"] == f"{report['last_dump']}-water.u16" for g in snapshots):
        raise ValueError("completed report lacks final saved water grid")
    temporal = {
        "meaning": "cell wet at EVERY saved grid; not proof of continuous inter-grid wetness",
        "all": summary(all_cells, wet_all_times, near_all_times, owners),
        "central25": summary(central, wet_all_times, near_all_times, owners),
        "named_rivers": {
            name: {
                "all": summary(cells, wet_all_times, near_all_times, owners),
                "central25": summary(
                    cells & central, wet_all_times, near_all_times, owners
                ),
            }
            for name, cells in sorted(by_name.items())
        },
    }
    return {
        "slug": slug,
        "run_directory": str(run.relative_to(ROOT))
        if run.is_relative_to(ROOT)
        else run.name,
        "game_minutes": got,
        "region": region,
        "recorded_run_harness": report.get("harness"),
        "native_package": map_receipt,
        "geometry_generation_binding": geometry_binding,
        "source_manifest": manifest,
        "scope": {
            "retained_river_features": len(features),
            "retained_stream_features_not_audited": len(geo.get("streams", [])),
            "direct_tunnel_omissions": tunnel,
            "declared_river_tunnel_omissions": declared,
            "no_minimum_length_filter": True,
            "unmodeled_short_surface_river_reaches_declared_by_writer": [
                r
                for r in hydro.get("unmodeled_short_surface_reaches", [])
                if r.get("class") == "river"
            ],
            "retained_feature_inventory": [
                {k: v for k, v in f.items() if k != "intervals"} for f in features
            ],
        },
        "frozen_probe_cohorts_by_river_name": probe_cohorts,
        "through_all_saved_grids": temporal,
        "snapshots": snapshots,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        nargs=3,
        action="append",
        required=True,
        metavar=("SLUG", "RUN_DIRECTORY", "GEOMETRY_JSON"),
    )
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location(
        "coverage_independent_groundtruth", GROUND
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = args.case
    output = {
        "purpose": "read-only spatial coverage diagnostic; not a new acceptance gate",
        "method": {
            "projection": "harness groundtruth.projection pyproj; frame0, size17280, +x east,+z north",
            "projection_source": ref(GROUND),
            "script_sha256": sha(pathlib.Path(__file__)),
            "grid": "1081x1081 south-first native depth uint16/64m; wet strictly >0.1m",
            "raster": "exact segment half-integer crossings into nearest-center 16m cells, global/per-name dedup",
            "nearby": "cell-center Euclidean disk <=64m (integer offsets dx²+dz²<=16)",
            "dry_components": "8-connected mapped dry cells; bbox cell centers; no size cutoff",
            "dry_stretches": "consecutive dry projected lengths within each source piece; duplicate features may overlap",
            "cohort": "all retained geometry.rivers, no minimum length/name/intermittency exclusion; only explicit brunnel=tunnel omitted",
            "not_audited": "streams, polygon interiors, flooding, navigability; no acceptance conclusion",
        },
        "cases": [],
    }
    for slug, run, geo in cases:
        result = audit(slug, pathlib.Path(run), pathlib.Path(geo), module.projection)
        output["cases"].append(result)
        final = result["snapshots"][-1]
        print(
            slug,
            result["native_package"]["report_crp_sha256"],
            "final",
            final["grid"],
            "all",
            {k: v for k, v in final["all"].items() if not k.endswith("components")},
            "central25",
            {
                k: v
                for k, v in final["central25"].items()
                if not k.endswith("components")
            },
            flush=True,
        )
        print(
            "  longest near64 dry stretches",
            final["near64_dry_stretches_along_source_features"][:3],
            flush=True,
        )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "coverage-audit.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n"
    )


if __name__ == "__main__":
    main()
