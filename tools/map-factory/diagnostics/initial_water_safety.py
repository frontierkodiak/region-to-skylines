"""Read-only initial-inundation counterexamples; never clears water safety."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crp import N, decode_u16, read_package  # noqa: E402
from region import raster  # noqa: E402
from template import manager_tag  # noqa: E402
from water_diagnostics import decode_water  # noqa: E402

POLICY = (
    "calibration/pl1191-construction-v1/development/phase18-initial-safety-policy.md"
)
WRITER = "874bf0298cafef9cb36c9f948e09f84a72942858"


def load(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def grid(path):
    values = np.fromfile(path, "<u2")
    if values.size != N:
        raise ValueError("Expected complete native south-first 1081-square grid")
    return values.reshape(1081, 1081)


def cover_native(path, size=1081):
    values = np.frombuffer(gzip.decompress(path.read_bytes()), "u1")
    if values.size != 1728**2:
        raise ValueError("Expected complete retained north-up 1728-square cover")
    index = np.minimum(np.floor(np.linspace(0, 1728, size)).astype(int), 1727)
    return np.flipud(values.reshape(1728, 1728)[np.ix_(index, index)])


def masks(before, after, built, mapped, ocean):
    if not all(a.shape == after.shape for a in [before, built, mapped, ocean]):
        raise ValueError("Mask/grid alignment differs")
    old, new = before > 32, after > 32
    delta = new & ~old
    return {
        "baseline_deep": old,
        "candidate_deep": new,
        "new_deep": delta,
        "no_longer_deep": old & ~new,
        "new_deep_dated_built_up": delta & built,
        "new_deep_outside_mapped_water": delta & ~mapped,
        "new_deep_outside_literal_ocean": delta & ~ocean,
        "new_deep_built_up_outside_mapped": delta & built & ~mapped,
        "new_deep_built_up_outside_ocean": delta & built & ~ocean,
        "initial_shallow_0_125_to_0_25m": (after >= 8) & (after <= 16),
    }


def count(mask):
    nodes = int(mask.sum())
    return {"vertices": nodes, "game_vertex_area_km2": nodes * 256 / 1e6}


def retention(mask, values):
    wet = values.astype(float) / 64 > 0.1
    # Same native 16m Euclidean lattice radius as the primary nearby definition;
    # this diagnostic cohort is not a replacement source-sector denominator.
    nearby = ndimage.distance_transform_edt(~wet) <= 4 if wet.any() else wet
    return {
        "cohort_vertices": int(mask.sum()),
        "exact_wet": int((mask & wet).sum()),
        "nearby_wet_within64m": int((mask & nearby).sum()),
    }


def probe_scope(probes, checks):
    return {
        "full_original_probe_count": len(probes),
        "explicit_required_true_overrides": sum(
            p.get("required") is True for p in probes
        ),
        "old_native_water_gate_status": {
            name: checks[name]["status"]
            for name in ["probes_wet_end", "probes_wet_throughout"]
        },
        "primary_natural_sector_coverage": "not established by these legacy point counts",
    }


def preflight(folder):
    freeze = load(folder / "freeze.json")
    for base, field in [(folder, "files_sha256"), (ROOT, "source_files_sha256")]:
        for name, expected in freeze[field].items():
            if sha(base / name) != expected:
                raise ValueError(f"Bound input/method differs: {name}")
    return freeze


def stage(baseline, prepared, native, cover, output):
    if output.exists():
        raise ValueError("Fresh output required; old evidence is immutable")
    output.mkdir(parents=True)
    files = [
        (baseline / "water.u16", "baseline-water.u16"),
        (cover, "landcover.u8.gz"),
    ]
    for name in [
        "terrain.u16",
        "water.u16",
        "mapped-water.u8",
        "geometry.json",
        "probes.json",
        "generation.json",
        "hydrology.json",
        "water-risk.json",
    ]:
        files.append((prepared / name, "physical/" + name))
    packages = list(prepared.glob("*.crp"))
    if len(packages) != 1:
        raise ValueError("Exactly one physical package required")
    files.append((packages[0], "physical/map.crp"))
    for name in ["session-receipt.json", "report.json", "verdict.json", "probes.json"]:
        files.append((native / name, "native/" + name))
    for path in sorted((native / "grids").glob("*.u16")):
        files.append((path, "native/grids/" + path.name))
    for source, name in files:
        destination = output / name
        destination.parent.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(source, destination)
    for name in ["region.py", "generate.py", "crp.py", "terrain_fidelity.mjs"]:
        data = subprocess.check_output(
            [
                "git",
                "-C",
                str(ROOT.parents[1]),
                "show",
                WRITER + ":tools/map-factory/" + name,
            ]
        )
        destination = output / "writer" / name
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes(data)
    sources = list(ROOT.glob("*.py")) + [
        Path(__file__),
        ROOT / "diagnostics/test_initial_water_safety.py",
        ROOT / POLICY,
        ROOT / "uv.lock",
    ]
    freeze = {
        "schema": "polli.initial-water-safety-diagnostic/1",
        "writer_source_commit": WRITER,
        "method_commit": subprocess.check_output(
            ["git", "-C", str(ROOT.parents[1]), "rev-parse", "HEAD"], text=True
        ).strip(),
        "known_prior_evidence": "PL-1244 handoff/retained footprint; not outcome-blind",
        "source_files_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sources},
        "files_sha256": {
            str(p.relative_to(output)): sha(p)
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
        "new_native": False,
        "old_gates_or_inputs_changed": False,
        "water_safety_cleared": False,
    }
    write(output / "freeze.json", freeze)
    return {
        "freeze_sha256": sha(output / "freeze.json"),
        "files": len(freeze["files_sha256"]),
    }


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh result required")
    physical, native = folder / "physical", folder / "native"
    package = physical / "map.crp"
    if load(native / "session-receipt.json")["map"]["sha256"] != sha(package):
        raise ValueError("Native run has a different physical package")
    if sha(physical / "probes.json") != sha(native / "probes.json"):
        raise ValueError("Full original native probe cohort differs")
    before, after, terrain = (
        grid(folder / "baseline-water.u16"),
        grid(physical / "water.u16"),
        grid(physical / "terrain.u16"),
    )
    payload = next(
        a["payload"] for a in read_package(package.read_bytes())[1] if a["kind"] == 52
    )
    decoded = decode_water(payload)
    tag = manager_tag("TerrainManager")
    if payload.count(tag) != 1:
        raise ValueError("Ambiguous terrain manager")
    actual_terrain, _ = decode_u16(payload, N, payload.index(tag) + len(tag))
    if not np.array_equal(
        actual_terrain.reshape(terrain.shape), terrain
    ) or not np.array_equal(decoded["depth"].reshape(after.shape), after):
        raise ValueError("Decoded package differs from authored grids")
    if not np.array_equal(
        grid(native / "grids/t000-terrain.u16"), terrain
    ) or not np.array_equal(grid(native / "grids/t000-water.u16"), after):
        raise ValueError("Retained native initial grids differ from package")
    geo = load(physical / "geometry.json")
    mapped = np.fromfile(physical / "mapped-water.u8", "u1").reshape(after.shape) > 0
    ocean = np.flipud(raster(geo["sq"], geo.get("oceans", []), polygons=True))
    built = cover_native(folder / "landcover.u8.gz") == 50
    groups = masks(before, after, built, mapped, ocean)
    sea_q = round(decoded["sea_level_m"] * 64)
    sea_depth = np.maximum(0, sea_q - terrain.astype(np.int64))
    new = groups["new_deep"]
    sea_equal = new & (after == sea_depth)
    t0_expected = (after.astype(float) / 64 > 0.1) | mapped
    # Every initial >0.5m node belongs to the old >0.1m reference by construction.
    # This is a descriptive coverage identity, not a rewritten flood verdict.
    checks = {c["name"]: c for c in load(native / "verdict.json")["checks"]}
    samples = []
    for path in sorted((native / "grids").glob("t*-water.u16")):
        values = grid(path)
        samples.append(
            {
                "grid": path.name,
                "groups": {
                    name: retention(mask, values)
                    for name, mask in groups.items()
                    if name
                    in [
                        "new_deep",
                        "new_deep_dated_built_up",
                        "initial_shallow_0_125_to_0_25m",
                    ]
                },
            }
        )
    probes = load(physical / "probes.json")["points"]
    result = {
        "schema": "polli.initial-water-safety-result/1",
        "input_freeze_sha256": sha(folder / "freeze.json"),
        "package_sha256": sha(package),
        "native_initial_terrain_and_water_exact_package": True,
        "source_rows": {
            key: len(geo.get(key, []))
            for key in [
                "rivers",
                "streams",
                "lakes",
                "riverAreas",
                "oceans",
                "undergroundWaterways",
            ]
        },
        "probe_scope": probe_scope(probes, checks),
        "footprints": {name: count(mask) for name, mask in groups.items()},
        "new_deep_equal_quantized_sea_minus_authored_terrain": count(sea_equal),
        "new_deep_inside_old_initial_water_reference": count(new & t0_expected),
        "old_flood_growth_check_unchanged": checks.get("no_flooding"),
        "native_water_samples": samples,
        "sea_level_game_m": decoded["sea_level_m"],
        "configured_control_count": len(decoded["sources"]),
        "construction_constraint": "Retaining source low land cannot be cleared by a growth-only flood pass or later drying; separate source-authoritative initialization and sustained-water evidence required. No shelf restoration or selective water removal is validated here.",
        "interpretation": "The extra initial depth is already serialized; engine runtime auto-fill is not necessary to explain t000. A global sea-stage initialization path exists in the exact writer. Sea-depth equality is attribution evidence, not full browser-to-writer replay or exclusive later drying mechanism.",
        "limits": "Dated WorldCover and 16m vertex-area approximation, not surveyed flood area or source-water exclusion authority. Literal ocean/mapped masks differ and are diagnostic partitions, not new acceptance thresholds. Shallow cohort is not a complete natural feature inventory. No physical flux or evaporation proof.",
        "water_safety": "not cleared; counterexample retained",
        "full_natural_water_qualification": "unknown; mandatory source-sector protocol not measured by this audit",
        "holdout_accessed": False,
        "stable_water_promise": "unknown",
    }
    output.mkdir(parents=True)
    np.savez_compressed(output / "diagnostic-masks.npz", **groups)
    write(output / "result.json", result)
    write(
        output / "receipt.json",
        {
            "freeze_sha256": sha(folder / "freeze.json"),
            "result_sha256": sha(output / "result.json"),
            "masks_sha256": sha(output / "diagnostic-masks.npz"),
        },
    )
    return {
        "result_sha256": sha(output / "result.json"),
        "water_safety": result["water_safety"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, args in [
        ("stage", ["baseline", "prepared", "native", "cover", "output"]),
        ("preflight", ["folder"]),
        ("evaluate", ["folder", "output"]),
    ]:
        p = commands.add_parser(name)
        for argument in args:
            p.add_argument(argument, type=Path)
    arguments = vars(parser.parse_args())
    function = globals()[arguments.pop("command")]
    print(json.dumps(function(**arguments), indent=2))
