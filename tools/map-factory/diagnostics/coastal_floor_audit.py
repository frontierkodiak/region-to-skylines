"""Frozen coastal current/target-floor audit; static connectivity is not flow."""

import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from scipy import ndimage

from bank_authority import ROOT, load, sha, write
from crp import N, decode_u16, read_package
from region import raster
from template import manager_tag
from water_diagnostics import bind_sources, decode_water
from waterway_pieces import catalog, digest

POLICY = "coast-retained-hydraulic-floor-v1"
SOURCE = "diagnostics/coastal_floor_audit.py"
DESIGN = (
    "calibration/pl1191-construction-v1/development/phase15-coastal-floor-policy.md"
)
PACKAGE_SHA = "457905c4a00cc6e83ab1f40a84feb2fa8888fa50de1bf4702bb082f1a55ed563"
PROBES_SHA = "0953f2ceb51ab045fea0172b23e4787ee62f54e146162005178d98e735c82d77"
TARGETS = ("Main Drain", "Bulimba Creek")
MARGINS = (0, 0.5, 2)


def grid(path):
    values = np.fromfile(path, "<u2")
    if values.size != N:
        raise ValueError("Expected complete native-order 1081x1081 grid")
    return values.reshape(1081, 1081)


def indices(points):
    coords = np.array([[p["x"], p["z"]] for p in points], float)
    if not np.isfinite(coords).all() or (np.abs(coords) > 8640).any():
        raise ValueError("Probe outside native grid")
    values = np.rint((coords + 8640) / 16).astype(int)
    return values[:, 1], values[:, 0]


def difference(actual, authored):
    delta = np.asarray(actual, np.int64) - np.asarray(authored, np.int64)
    return {
        "nodes": int(delta.size),
        "different_nodes": int(np.count_nonzero(delta)),
        "min_delta_m": float(delta.min()) / 64 if delta.size else None,
        "max_delta_m": float(delta.max()) / 64 if delta.size else None,
    }


def connected(floor, ocean, sea, margin, adjacency):
    below = floor.astype(np.int64) < (sea - margin) * 64
    edge = np.zeros_like(below)
    edge[[0, -1], :] = True
    edge[:, [0, -1]] = True
    seed = edge & ocean & below
    labels, _ = ndimage.label(
        below, ndimage.generate_binary_structure(2, 1 if adjacency == 4 else 2)
    )
    ids = np.unique(labels[seed])
    ids = ids[ids != 0]
    return np.isin(labels, ids), int(seed.sum())


def decoded_package(folder):
    source = folder / "physical"
    package = source / "PL857-low-coast-oceania.crp"
    if sha(package) != PACKAGE_SHA or sha(source / "probes.json") != PROBES_SHA:
        raise ValueError("Wrong fixed coastal physical cohort")
    payload = next(
        a["payload"] for a in read_package(package.read_bytes())[1] if a["kind"] == 52
    )
    water = decode_water(payload)
    bind_sources(water, load(source / "hydrology.json"))
    if len(water["sources"]) != 167 or any(
        s["intake_rate"] != 0 for s in water["sources"]
    ):
        raise ValueError("Expected all167intakes off, outputs retained")
    tag = manager_tag("TerrainManager")
    if payload.count(tag) != 1:
        raise ValueError("Ambiguous terrain manager")
    terrain, offset = decode_u16(payload, N, payload.index(tag) + len(tag))
    delta, _ = decode_u16(payload, int(np.count_nonzero(terrain)), offset)
    if (
        terrain.astype("<u2").tobytes() != (source / "terrain.u16").read_bytes()
        or delta.any()
    ):
        raise ValueError("Decoded physical terrain changed")
    if water["depth"].astype("<u2").tobytes() != (source / "water.u16").read_bytes():
        raise ValueError("Decoded physical initialization changed")
    return water


def source_domains(geometry):
    pieces = catalog(geometry)
    catalog_rows = {r["id"]: r for r in pieces["rows"]}
    result = []
    for field in ("rivers", "streams", "lakes", "riverAreas"):
        for i, feature in enumerate(geometry.get(field, [])):
            if feature.get("name") not in TARGETS:
                continue
            name = f"{field}:{i}"
            row = catalog_rows.get(name)
            mask = np.zeros((1081, 1081), bool)
            scope = row["status"] if row else "perennial_surface"
            if row:
                for clip in row["clips"]:
                    for r, c in clip["nodes_rc"]:
                        mask[1080 - r, c] = True
            else:
                mask = np.flipud(raster(geometry["sq"], [feature], polygons=True))
            result.append(
                (
                    {
                        "id": name,
                        "name": feature["name"],
                        "source_sha256": digest(feature),
                        "scope": scope,
                        "clipped_parts": row["clips"] if row else None,
                        "native_nodes": int(mask.sum()),
                        "geometry_model": "captured nearest16m line nodes or source polygon fill, not surveyed hydraulic width",
                    },
                    mask,
                )
            )
    return result


def audit(folder):
    decoded = decoded_package(folder)
    physical, native = folder / "physical", folder / "retained-native"
    if (
        load(native / "session-receipt.json")["map"]["sha256"] != PACKAGE_SHA
        or sha(native / "probes.json") != PROBES_SHA
    ):
        raise ValueError("Retained native package/probe identity mismatch")
    geometry, probes = (
        load(physical / "geometry.json"),
        load(physical / "probes.json")["points"],
    )
    if geometry["seaLevel"] != decoded["sea_level_m"]:
        raise ValueError("Authored ocean stage changed")
    authored = grid(physical / "terrain.u16")
    floors = {
        "authored": authored,
        **{
            label: grid(native / "grids" / f"{label}-water-ground.u16")
            for label in ("t000", "t005")
        },
    }
    ocean = np.flipud(raster(geometry["sq"], geometry.get("oceans", []), polygons=True))
    domains = source_domains(geometry)
    prior = load(folder / "prior-coastal-audit.json")["static_ocean_connectivity"][
        "probes"
    ]
    legacy = [
        p
        for p in prior
        if p["name"].removeprefix("geography:").split(" [", 1)[0] in TARGETS
    ]
    if len(legacy) != 162:
        raise ValueError("The fixed historical failure-selected cohort changed")
    complete_rc, legacy_rc = indices(probes), indices(legacy)
    target_points = {
        name: [
            p
            for p in probes
            if p["name"].removeprefix("geography:").split(" [", 1)[0] == name
        ]
        for name in TARGETS
    }
    comparison = {}
    for label in ("t000", "t005"):
        current, raw, target = (
            floors[label],
            grid(native / "grids" / f"{label}-terrain.u16"),
            grid(native / "grids" / f"{label}-water-ground-target.u16"),
        )
        comparison[label] = {
            "current_floor_sha256": sha(native / "grids" / f"{label}-water-ground.u16"),
            "raw_terrain_vs_authored": difference(raw, authored),
            "current_floor_vs_authored": difference(current, authored),
            "target_vs_current_floor": difference(target, current),
            "full_probe_floor_deltas": difference(
                current[complete_rc], authored[complete_rc]
            ),
        }
    profiles = []
    for label, floor in floors.items():
        for margin in MARGINS:
            for adjacency in (4, 8):
                connection, seeds = connected(
                    floor, ocean, decoded["sea_level_m"], margin, adjacency
                )
                profiles.append(
                    {
                        "floor": label,
                        "static_margin_m": margin,
                        "adjacency": adjacency,
                        "ocean_edge_seeds": seeds,
                        "all_frozen_probes": {
                            "count": len(probes),
                            "connected": int(connection[complete_rc].sum()),
                        },
                        "full_target_probe_groups": {
                            name: {
                                "points": len(ps),
                                "connected": int(connection[indices(ps)].sum()),
                            }
                            for name, ps in target_points.items()
                        },
                        "fixed_historical_cohort": [
                            {
                                "name": p["name"],
                                "x": p["x"],
                                "z": p["z"],
                                "floor_q": int(floor[r, c]),
                                "connected": bool(connection[r, c]),
                            }
                            for p, r, c in zip(legacy, *legacy_rc)
                        ],
                        "source_features": [
                            {
                                **entry,
                                "connected_nodes": int(connection[mask].sum())
                                if entry["scope"] == "perennial_surface"
                                else None,
                                "floor_delta_vs_authored": difference(
                                    floor[mask], authored[mask]
                                )
                                if mask.any()
                                else None,
                            }
                            for entry, mask in domains
                        ],
                    }
                )
    samples = []
    with (native / "timeline.jsonl").open() as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("kind") == "sample":
                water = row["water"]
                samples.append(
                    {
                        "label": row["label"],
                        "stats_frame": row["stats"]["frame"],
                        "water_reported_simulation_frame": water["frame"],
                        "sea_level": water["sea_level"],
                        "probe_count": len(water["samples"]),
                        "source_count": len(water["sources"]),
                        "probe_velocity_available": all(
                            "velocity" in p for p in water["samples"]
                        ),
                    }
                )
    return {
        "schema": "polli.coastal-retained-floor-audit/1",
        "policy": POLICY,
        "package_sha256": PACKAGE_SHA,
        "probes_sha256": PROBES_SHA,
        "full_probe_count": len(probes),
        "decoded_controls": decoded["sources"],
        "decoded_sea_level_m": decoded["sea_level_m"],
        "comparisons": comparison,
        "current_floor_t000_to_t005": difference(floors["t005"], floors["t000"]),
        "profiles": profiles,
        "old_sample_metadata": samples,
        "later_or_between_sample_floors": "unavailable",
        "flow_or_supply_inference": "unresolved; static connected/head-margin geometry is not transport",
        "fixed_cohort_scope": "pre-existing failure-selected162, secondary diagnostic only; full27386probes and all named source features also retained",
        "physical_changes": False,
        "stable_water_promise": "unknown",
    }


def stage(physical, native, prior, output, oldharness, studyharness):
    if output.exists():
        raise ValueError("Use a fresh additive audit protocol")
    output.mkdir(parents=True)
    shutil.copytree(physical, output / "physical")
    here = output / "retained-native"
    here.mkdir()
    for name in (
        "timeline.jsonl",
        "report.json",
        "verdict.json",
        "probes.json",
        "session-receipt.json",
        "runtime-identity.json",
        "harness-source.json",
    ):
        shutil.copyfile(native / name, here / name)
    (here / "grids").mkdir()
    for label in ("t000", "t005"):
        for suffix in ("water", "terrain", "water-ground", "water-ground-target"):
            name = f"{label}-{suffix}.u16"
            shutil.copyfile(native / "grids" / name, here / "grids" / name)
    shutil.copyfile(prior, output / "prior-coastal-audit.json")
    (output / "semantics").mkdir()
    for source, name in (
        (oldharness / "tools/cs1-harness/mod/CityOps.cs", "old-CityOps.cs"),
        (
            studyharness / "tools/cs1-harness/mod/WaterStudyOps.cs",
            "study-WaterStudyOps.cs",
        ),
    ):
        shutil.copyfile(source, output / "semantics" / name)
    dependencies = {
        str(p.relative_to(ROOT)): sha(p)
        for p in ROOT.glob("*.py")
        if not p.name.startswith("test_")
    }
    for name in (SOURCE, DESIGN, "pyproject.toml", "uv.lock"):
        dependencies[name] = sha(ROOT / name)
    write(
        output / "prospective-freeze.json",
        {
            "schema": "polli.coastal-floor-audit-freeze/1",
            "policy": POLICY,
            "source_files_sha256": dependencies,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "physical_package_sha256": PACKAGE_SHA,
            "probes_sha256": PROBES_SHA,
            "no_original_input_or_gate_edits": True,
        },
    )
    write(output / "audit.json", audit(output))
    write(
        output / "result-receipt.json",
        {
            "prospective_freeze_sha256": sha(output / "prospective-freeze.json"),
            "audit_sha256": sha(output / "audit.json"),
        },
    )
    preflight(output)
    return load(output / "result-receipt.json")


def preflight(folder):
    frozen = load(folder / "prospective-freeze.json")
    if (
        frozen["schema"] != "polli.coastal-floor-audit-freeze/1"
        or frozen["policy"] != POLICY
    ):
        raise ValueError("Wrong coastal retained-floor protocol")
    for name, expected in frozen["source_files_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Bound source changed: {name}")
    for name, expected in frozen["files_sha256"].items():
        if sha(folder / name) != expected:
            raise ValueError(f"Bound physical/observation input changed: {name}")
    receipt = load(folder / "result-receipt.json")
    if (
        sha(folder / "prospective-freeze.json") != receipt["prospective_freeze_sha256"]
        or sha(folder / "audit.json") != receipt["audit_sha256"]
        or audit(folder) != load(folder / "audit.json")
    ):
        raise ValueError("Complete retained-floor replay differs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, arguments in (
        (
            "stage",
            ("physical", "native", "prior", "output", "oldharness", "studyharness"),
        ),
        ("preflight", ("folder",)),
    ):
        command = commands.add_parser(name)
        for argument in arguments:
            command.add_argument(argument, type=Path)
    args = vars(parser.parse_args())
    print(
        json.dumps(
            globals()[args.pop("command")](**args) or {"status": "replay_pass"},
            indent=2,
        )
    )
