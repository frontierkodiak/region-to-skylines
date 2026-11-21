"""Read-only attribution of coastal plateaus and retained native observations.

Internal stage correlations are NOT independent DEM ground truth or acceptance.
No network, holdout labels, game execution, source edits or gate changes occur.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from PIL import Image


def plateau_measure(metres):
    raw = np.floor(metres * 64 + 0.5).astype(np.int32)
    window = sliding_window_view(np.pad(raw, 2, mode="edge"), (5, 5))
    sloped = window.max(axis=(2, 3)) - window.min(axis=(2, 3)) > 4 * 64
    pairs = sloped[:, 1:] & sloped[:, :-1]
    equal = (np.diff(raw, axis=1) == 0) & pairs
    total = int(equal.sum())
    levels = {}
    for level in (80, 91):
        count = int((equal & (raw[:, :-1] == level * 64)).sum())
        levels[str(level)] = {
            "cell_fraction": float((raw == level * 64).mean()),
            "equal_sloped_pairs": count,
            "fraction_of_equal_sloped_pairs": count / total if total else None,
        }
    return {
        "native_quantization_m": 1 / 64,
        "sloped_pairs": int(pairs.sum()),
        "equal_sloped_pairs": total,
        "equal_pair_fraction_on_slopes": total / int(pairs.sum())
        if pairs.any()
        else None,
        "diagnostic_fixed_levels_m_not_acceptance_masks": levels,
    }


def ocean_connectivity(geometry, hydro, report, probes, verdict, floor):
    """Static connectivity of native BlockHeights; not a water-flow solver."""
    from scipy import ndimage

    from region import raster

    sea = geometry.get("seaLevel")
    if sea is None:
        return {"applicable": False, "reason": "No explicit ocean sea level"}
    ocean = np.flipud(raster(geometry["sq"], geometry.get("oceans", []), polygons=True))
    below = floor < sea
    edge = np.zeros_like(below)
    edge[[0, -1], :] = True
    edge[:, [0, -1]] = True
    seed = ocean & edge & below
    connections = {}
    component_grids = {}
    for neighbours in (4, 8):
        labels, _ = ndimage.label(
            below, ndimage.generate_binary_structure(2, 1 if neighbours == 4 else 2)
        )
        ocean_labels = np.unique(labels[seed])
        component_grids[str(neighbours)] = labels
        connections[str(neighbours)] = np.isin(labels, ocean_labels[ocean_labels != 0])
    meta = {p["name"]: p for p in probes["points"]}
    thresholds = verdict["thresholds"]
    rows = []
    required_count = 0
    for point in report["points"]:
        declared = meta.get(point["name"], {})
        reach = max(abs(point["x"]), abs(point["z"]))
        required = declared.get(
            "required",
            reach <= thresholds["playable_half_m"]
            and reach < thresholds["edge_m"]
            and "[stream]" not in point["name"],
        )
        required_count += int(required)
        if not required or not point["wet_start"]:
            continue
        if point["wet_end"] or point.get("wet_within_64m_end", False):
            continue
        col = int(np.rint((point["x"] + 8640) / 16))
        row = int(np.rint((point["z"] + 8640) / 16))
        distances = [
            float(
                np.hypot(point["x"] - s["position"][0], point["z"] - s["position"][2])
            )
            for s in hydro["sources"]
        ]
        nearest = int(np.argmin(distances)) if distances else None
        source = hydro["sources"][nearest] if nearest is not None else None
        overlapping = []
        for source_index, (control, distance) in enumerate(
            zip(hydro["sources"], distances)
        ):
            rate = int(np.floor(control["capacity"] * 65535 + 0.5))
            radius = 10 + 0.4 * np.sqrt(rate)
            if distance <= radius:
                overlapping.append(
                    {
                        "source_index": source_index,
                        "name": control["name"],
                        "target_m": control["target"],
                        "distance_m": distance,
                        "intake_radius_m": float(radius),
                        "target_below_sea": control["target"] < sea,
                    }
                )
        rows.append(
            {
                "name": point["name"],
                "x": point["x"],
                "z": point["z"],
                "native_floor_m": float(floor[row, col]),
                "below_sea": bool(below[row, col]),
                "ocean_connected": {
                    k: bool(v[row, col]) for k, v in connections.items()
                },
                "below_sea_component": {
                    k: int(v[row, col]) for k, v in component_grids.items()
                },
                "initial_depth_m": point["depth_start"],
                "end_depth_m": point["depth_end"],
                "nearest_control": {
                    "source_index": nearest,
                    "name": source["name"],
                    "target_m": source["target"],
                    "distance_m": distances[nearest],
                }
                if source is not None
                else None,
                "controls_whose_nominal_intake_radius_covers_probe": overlapping,
            }
        )
    groups = {}
    for row in rows:
        name = row["name"].removeprefix("geography:").split(" [", 1)[0]
        group = groups.setdefault(
            name,
            {
                "lost": 0,
                "below_sea": 0,
                "connected_4": 0,
                "connected_8": 0,
                "overlapping_below_sea_intake": 0,
            },
        )
        group["lost"] += 1
        group["below_sea"] += int(row["below_sea"])
        for n in (4, 8):
            group[f"connected_{n}"] += int(row["ocean_connected"][str(n)])
        group["overlapping_below_sea_intake"] += int(
            any(
                s["target_below_sea"]
                for s in row["controls_whose_nominal_intake_radius_covers_probe"]
            )
        )
    for name, group in groups.items():
        group["controls_in_same_static_below_sea_components"] = {}
        for neighbours, labels in component_grids.items():
            ids = {
                p["below_sea_component"][neighbours]
                for p in rows
                if p["name"].removeprefix("geography:").split(" [", 1)[0] == name
            }
            ids.discard(0)
            sources = []
            for index, source in enumerate(hydro["sources"]):
                col = int(np.rint((source["position"][0] + 8640) / 16))
                row = int(np.rint((source["position"][2] + 8640) / 16))
                if int(labels[row, col]) in ids:
                    sources.append(
                        {
                            "index": index,
                            "name": source["name"],
                            "target_m": source["target"],
                            "native_floor_m": float(floor[row, col]),
                            "intake_capacity": source["capacity"],
                            "output_capacity": source.get(
                                "output_capacity", source["capacity"]
                            ),
                        }
                    )
            group["controls_in_same_static_below_sea_components"][neighbours] = sources
    unregulated_reaches = []
    controlled_names = {s["name"] for s in hydro["sources"]}
    for name, positions in hydro["samples"].items():
        if " [river]" not in name or name.split(" [river]", 1)[0] in controlled_names:
            continue
        points = np.asarray(positions)
        cols = np.rint((points[:, 0] + 8640) / 16).astype(int)
        rows_at = np.rint((points[:, 2] + 8640) / 16).astype(int)
        unregulated_reaches.append(
            {
                "reach": name,
                "samples": len(points),
                "below_sea_samples": int(below[rows_at, cols].sum()),
                "ocean_connected_samples": {
                    k: int(v[rows_at, cols].sum()) for k, v in connections.items()
                },
            }
        )
    return {
        "applicable": True,
        "floor": "native t000 TerrainManager.BlockHeights, south-first, units1/64m",
        "strict_below_sea_m": sea,
        "boundary_ocean_seed_cells": int(seed.sum()),
        "required_probe_count": required_count,
        "cohort": "required, exact-wet at start, neither exact nor native-within64m-wet at endpoint",
        "lost_probe_count": len(rows),
        "groups": groups,
        "unregulated_reaches": unregulated_reaches,
        "probes": rows,
        "connected_floor_cells": {k: int(v.sum()) for k, v in connections.items()},
        "limitations": "Static floor paths do not prove dynamic flow or boundary replenishment. Nearest/nominal-radius source overlap is association, not measured intake flux. Actual ocean polygons use region.raster and flip to native row order; initial below-sea prefill is not ocean evidence.",
    }


def audit(capture, staged, native):
    paths = {
        "geometry": staged / "geometry.json",
        "hydrology": staged / "hydrology.json",
        "banks": capture / "input-banks.f32",
        "browser": capture / "input.png",
        "staged_terrain": staged / "terrain.u16",
        "staged_water": staged / "water.u16",
        "native_terrain": native / "grids/t000-terrain.u16",
        "native_report": native / "report.json",
        "native_verdict": native / "verdict.json",
        "native_ground_truth": native / "ground-truth.json",
        "native_hydraulic_floor": native / "grids/t000-water-ground.u16",
        "native_probes": native / "probes.json",
    }
    objects = {
        key: json.loads(paths[key].read_text())
        for key in (
            "geometry",
            "hydrology",
            "native_report",
            "native_verdict",
            "native_ground_truth",
            "native_probes",
        )
    }
    geometry, hydro = objects["geometry"], objects["hydrology"]

    def read_grid(key):
        return np.fromfile(paths[key], "<u2").reshape(1081, 1081) / 64

    native_terrain = read_grid("native_terrain")
    terrain = read_grid("staged_terrain")
    water = read_grid("staged_water")
    banks = np.fromfile(paths["banks"], "<f4").reshape(1081, 1081)
    browser = np.asarray(Image.open(paths["browser"]), dtype=float) * 1024 / 65535
    stages = {
        "uncarved_fitted_banks": banks,
        "browser_input": browser,
        "staged": np.flipud(terrain),
        "native_t000": np.flipud(native_terrain),
    }
    checks = {check["name"]: check for check in objects["native_verdict"]["checks"]}
    retention = {}
    for key in ("probes_wet_end", "probes_wet_throughout"):
        value = checks[key]["value"] or {}
        retention[key] = {
            "status": checks[key]["status"],
            **{
                k: value[k]
                for k in ("wet", "required", "fraction", "samples", "wet_throughout")
                if k in value
            },
        }
    source_counts = {}
    for source in hydro["sources"]:
        name = source["name"]
        source_counts[name] = source_counts.get(name, 0) + 1
    sea = geometry.get("seaLevel")
    unregulated = []
    for name, points in hydro["samples"].items():
        if " [river]" not in name:
            continue
        label = name.split(" [river]", 1)[0]
        if source_counts.get(label):
            continue
        points = np.asarray(points)
        col = np.rint((points[:, 0] + 8640) / 16).astype(int)
        row = np.rint((points[:, 2] + 8640) / 16).astype(int)
        surface = (terrain + water)[row, col]
        unregulated.append(
            {
                "reach": name,
                "controls_with_same_name": 0,
                "initial_surface_range_m": [float(surface.min()), float(surface.max())],
                "samples_at_or_below_sea_plus_half_m": int((surface <= sea + 0.5).sum())
                if sea is not None
                else None,
                "samples": len(points),
                "caveat": "Association with suppression predicate, not an instrumented count of skipped controls.",
            }
        )
    ground_truth = objects["native_ground_truth"]
    return {
        "schema": 1,
        "diagnostic_only": True,
        "acceptance_unchanged": True,
        "square": geometry["sq"],
        "fit": geometry["fit"],
        "sea_level_m": sea,
        "ocean_feature_count": len(geometry.get("oceans", [])),
        "native_minutes": objects["native_report"]["game_minutes"],
        "native_harness": objects["native_report"]["harness"],
        "staged_native_terrain_bytes_identical": paths["staged_terrain"].read_bytes()
        == paths["native_terrain"].read_bytes(),
        "plateau_measures": {
            key: plateau_measure(value) for key, value in stages.items()
        },
        "internal_stage_correlations_not_ground_truth": {
            key: float(
                np.corrcoef(banks[::4, ::4].ravel(), value[::4, ::4].ravel())[0, 1]
            )
            for key, value in stages.items()
        },
        "independent_native_ground_truth": {
            "passed": ground_truth["passed"],
            "dem": ground_truth["dem"],
            "correlation_as_is": ground_truth["correlation"]["as is"],
            "caveat": "Retained checker result, not recomputed here. Banks are already fitted, not raw DEM; source/checker resolution disagreement remains unmeasured by this audit.",
        },
        "required_retention": retention,
        "unregulated_river_reaches": unregulated,
        "source_suppression_predicate": "region.py:329 skips fitted <= sea + 0.5 without proving ocean connectivity",
        "static_ocean_connectivity": ocean_connectivity(
            geometry,
            hydro,
            objects["native_report"],
            objects["native_probes"],
            objects["native_verdict"],
            read_grid("native_hydraulic_floor"),
        ),
        "files": {
            key: {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for key, path in paths.items()
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("staged", type=Path)
    parser.add_argument("native", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.capture, args.staged, args.native), indent=2))
