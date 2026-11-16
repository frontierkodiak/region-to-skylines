"""Unqualified PL-912 dry-subreach/startup-film experiment, not a default.

Native evidence selects cells, never qualification observations. No floor or
startup water changes inside physical source radii. Every later occupied-water
patch remains fixed. Exact current source/input hashes bind the prepared plan.
"""

import argparse
import gzip
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image
from scipy import ndimage

from admission import distance, restore_line_cuts, stroke
from native_admission import (
    ROOT,
    grid,
    native_evidence,
    protected_infrastructure,
    quantize,
    read,
    sha,
    source_pieces,
    write_grid,
)
from native_support import interpolation_support
from region import raster
from surface_water import surface_geometry
from verify_bank_restoration import require_continuous_floor

PLANNER_FILES = [
    "native_subreaches.py",
    "native_admission.py",
    "native_support.py",
    "admission.py",
    "region.py",
    "prepare.py",
    "surface_water.py",
    "verify_bank_restoration.py",
]


def source_radii(hydro):
    """Freeze every native type-1 intake/output footprint, including dry cells.

    Writer sources are type 1, co-located intake/output. Rate and radius use the
    encoded integer rate and native float32 arithmetic. Include the boundary
    conservatively; native reads strictly inside it. No extra 32 m blanket.
    """
    yy, xx = np.mgrid[:1081, :1081]
    result = np.zeros((1081, 1081), bool)
    for source in hydro["sources"]:
        x, _, z = source["position"]
        dx = np.asarray(xx * 16 - 8640 - np.float32(x), dtype=np.float32)
        dz = np.asarray(8640 - yy * 16 - np.float32(z), dtype=np.float32)
        d2 = dx * dx + dz * dz
        for capacity in [
            source["capacity"],
            source.get("output_capacity", source["capacity"]),
        ]:
            rate = int(np.floor(capacity * 65535 + 0.5))
            if rate:
                radius = np.float32(np.sqrt(np.float32(rate)) * np.float32(0.4) + 10)
                result |= d2 <= radius * radius
    return result


def eligible_lines(geometry, hydro):
    """Existing modeled bank-limited rivers/feasible streams; other lines win."""
    eligible = np.zeros((1081, 1081), bool)
    independent = np.zeros_like(eligible)
    for field, kind in [("rivers", "river"), ("streams", "stream")]:
        modeled = [
            r
            for r in hydro["rivers"]
            if r["class"] == kind
            and (
                r.get("bank_limited")
                or (kind == "stream" and not r.get("unforced_infeasible_stream"))
            )
        ]
        eligible_component = np.zeros_like(eligible)
        for name in {r["name"] for r in modeled}:
            features = [
                f
                for f in geometry.get(field, [])
                if (f.get("name") or "unnamed waterway") == name
            ]
            mapped = raster(geometry["sq"], features)
            labels, _ = ndimage.label(
                ndimage.binary_dilation(mapped, iterations=2), np.ones((3, 3))
            )
            for river in modeled:
                if river["name"] == name:
                    x, y = river["upstream"]
                    label = labels[y, x]
                    if label:
                        eligible_component |= mapped & (labels == label)
        for feature in geometry.get(field, []):
            mapped = raster(geometry["sq"], [feature])
            line = mapped | stroke(geometry["sq"], [feature])
            if (mapped & eligible_component).any() and not (
                mapped & ~eligible_component
            ).any():
                eligible |= line
            else:
                independent |= line
    return eligible & ~independent


def dry_domain(eligible, all_lines, later_water, hard_guard):
    """Connected dry line pixels and their own three-cell incision territory."""
    # This one-cell ring is a conservative superset of every native sampling
    # patch, regardless of floor: each patch has at least one occupied corner.
    # It also preserves the four-neighbour flow interface to recorded water.
    guard = ndimage.maximum_filter(later_water, size=3, mode="constant") | hard_guard
    line = eligible & ~guard
    removed, retained = distance(line), distance(all_lines & ~line)
    zone = (removed <= 3) & (removed < retained) & ~guard
    return line, zone, guard


def restore(
    terrain,
    water,
    later_water,
    hard_guard,
    dry_line,
    zone,
    guard,
    original,
    banks,
    geometry,
):
    """Clear never-rewetted startup film; replay only each dry line's own cut."""
    initial = water.copy()
    clear = (water > 0) & ~later_water & ~hard_guard
    initial[clear] = 0
    browser = stroke(geometry["sq"], geometry.get("rivers", []))
    restored, replay = restore_line_cuts(
        original,
        banks,
        geometry,
        browser & dry_line,
        browser & ~dry_line,
    )
    delta = np.maximum(0, restored - original)
    proposed = np.maximum(terrain / 64, np.minimum(banks, terrain / 64 + delta))
    proposed[zone] = np.maximum(proposed[zone], restored[zone])
    candidate = np.maximum(terrain, quantize(proposed))
    startup_support = ndimage.maximum_filter(initial > 0, size=3, mode="constant")
    candidate[guard | startup_support] = terrain[guard | startup_support]
    assert not (candidate < terrain).any()
    assert np.array_equal(candidate[hard_guard], terrain[hard_guard])
    assert np.array_equal(initial[hard_guard], water[hard_guard])
    require_continuous_floor(terrain, candidate, later_water)
    require_continuous_floor(terrain, candidate, initial)
    return candidate, initial, clear, replay


def plan(prepared, observed, fixture, output, supplemental=()):
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--", *PLANNER_FILES],
        cwd=ROOT,
        text=True,
    ).strip():
        raise ValueError("Commit the exact planner snapshot before producing plans")
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    hashes = {p: sha(ROOT / p) for p in PLANNER_FILES}
    terrain, water, later, _, binding = native_evidence(prepared, observed)
    paths = list(sorted((observed / "grids").glob("t*-water.u16")))
    epochs = [(p, None) for p in paths if p.name != "t000-water.u16"]
    floor_differences = np.zeros_like(later)
    for native in supplemental:
        diagnostic = read(native / "diagnostic.json")
        receipt = read(native / "session-receipt.json")
        if (
            diagnostic["crp_sha256"] != binding["package_sha256"]
            or receipt["map"]["sha256"] != binding["package_sha256"]
            or diagnostic["elapsed_game_minutes"] < 5
            or any(receipt["cleanup"].values())
        ):
            raise ValueError(
                "Supplemental native run is not this exact cleaned-up reference"
            )
        for name in ["terrain", "water"]:
            if (native / f"grids/t000-{name}.u16").read_bytes() != (
                prepared / f"{name}.u16"
            ).read_bytes():
                raise ValueError("Supplemental initial grids differ")
        for name in ["diagnostic.json", "session-receipt.json"]:
            binding["native_files_sha256"][str(native / name)] = sha(native / name)
        for label in ["t000", "t005"]:
            raw = native / f"grids/{label}-terrain.u16"
            floor = native / f"grids/{label}-water-ground.u16"
            target = native / f"grids/{label}-water-ground-target.u16"
            if not np.array_equal(grid(raw), terrain) or not np.array_equal(
                grid(floor), grid(target)
            ):
                raise ValueError(
                    "Supplemental terrain changed or hydraulic floor is unsettled"
                )
            floor_differences |= grid(floor) != terrain
            for path in [raw, floor, target]:
                binding["native_files_sha256"][str(path)] = sha(path)
        depth_path = native / "grids/t005-water.u16"
        epochs.append((depth_path, native / "grids/t005-water-ground.u16"))
        binding["native_files_sha256"][str(depth_path)] = sha(depth_path)
        later |= grid(depth_path) > 0
    geometry, _ = surface_geometry(read(prepared / "geometry.json"))
    if (prepared / "geometry.json").read_bytes() != gzip.decompress(
        (fixture / "shipping-geometry.json.gz").read_bytes()
    ):
        raise ValueError("Browser-cut replay needs the exact held geometry")
    if (prepared / "banks.f32").read_bytes() != gzip.decompress(
        (fixture / "banks.f32.gz").read_bytes()
    ):
        raise ValueError("Browser-cut replay needs the exact held DEM")
    banks = np.fromfile(prepared / "banks.f32", "<f4").reshape(1081, 1081).astype(float)
    original = np.asarray(Image.open(fixture / "input.png"), dtype=float) * 1024 / 65535
    hydro = read(prepared / "hydrology.json")
    controls = source_radii(hydro)
    network = protected_infrastructure({**hydro, "sources": []})
    bodies = raster(
        geometry["sq"],
        geometry.get("lakes", []) + geometry.get("oceans", []),
        polygons=True,
    )
    hard_guard = (
        controls
        | network
        | ndimage.maximum_filter(bodies | floor_differences, size=3, mode="constant")
    )
    eligible = eligible_lines(geometry, hydro)
    all_lines = stroke(geometry["sq"], source_pieces(geometry)) | raster(
        geometry["sq"], source_pieces(geometry)
    )
    dry_line, zone, guard = dry_domain(eligible, all_lines, later, hard_guard)
    # Actual hydraulic-floor support is checked where available. The later
    # occupied-cell ring above safely contains it even without a floor dump.
    for depth, floor in epochs:
        if (
            floor is not None
            and (interpolation_support(grid(floor), grid(depth)) & ~guard).any()
        ):
            raise ValueError(
                "Native interpolation escaped the conservative occupied-cell ring"
            )
    candidate, initial, clear, replay = restore(
        terrain,
        water,
        later,
        hard_guard,
        dry_line,
        zone,
        guard,
        original,
        banks,
        geometry,
    )
    _, components = ndimage.label(dry_line, np.ones((3, 3)))
    report = {
        "planner_source_commit": commit,
        "planner_files_sha256": hashes,
        "status": "CPU experiment; no native or shipping qualification",
        "rule": "native dry line pixels and never-rewetted startup film; physical source radii and later wet patches unchanged",
        "binding": binding,
        "prepared_files_sha256": {
            p: sha(prepared / p)
            for p in [
                "terrain.u16",
                "water.u16",
                "hydrology.json",
                "geometry.json",
                "banks.f32",
            ]
        },
        "frozen_probes_sha256": sha(observed / "probes.json"),
        "frozen_observations": len(read(observed / "probes.json")["points"]),
        "eligible_line_pixels": int(eligible.sum()),
        "dry_line_pixels": int(dry_line.sum()),
        "dry_line_components": components,
        "incision_territory_pixels": int(zone.sum()),
        "terrain_raised_vertices": int((candidate > terrain).sum()),
        "terrain_lowered_vertices": 0,
        "maximum_raise_m": float((candidate.astype(int) - terrain).max() / 64),
        "startup_water_removed_vertices": int(clear.sum()),
        "source_controls_unchanged": True,
        "source_radius_floor_and_water_unchanged": True,
        "native_wet_interpolation_support_unchanged": True,
        "retained_startup_interpolation_support_unchanged": True,
        "browser_replay": replay,
    }
    output.mkdir(parents=True, exist_ok=False)
    write_grid(output / "terrain.u16", candidate)
    write_grid(output / "water.u16", initial)
    (output / "hydrology.json").write_bytes((prepared / "hydrology.json").read_bytes())
    np.savez_compressed(
        output / "masks.npz",
        dry_line=dry_line,
        zone=zone,
        guard=guard,
        hard_guard=hard_guard,
        source_radii=controls,
        later_water=later,
        cleared_film=clear,
    )
    report["candidate_files_sha256"] = {
        p: sha(output / p)
        for p in ["terrain.u16", "water.u16", "hydrology.json", "masks.npz"]
    }
    if hashes != {p: sha(ROOT / p) for p in PLANNER_FILES}:
        raise ValueError("Planner changed during generation")
    (output / "admission.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["prepared", "observed", "fixture", "output"]:
        parser.add_argument(name, type=Path)
    parser.add_argument("--supplemental", type=Path, action="append", default=[])
    print(json.dumps(plan(**vars(parser.parse_args())), indent=2))
