"""PL-1001's bounded transient-margin experiment; not a shipping default.

Native snapshots select terrain/cut contributions, never qualification probes.
This prepares arrays only. Fresh native shorts must falsify the supplied-patch
and sampled-inactive-intake hypotheses before any qualification or integration.
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
from native_subreaches import eligible_lines
from region import raster
from surface_water import surface_geometry


def dilate(mask, cells=1):
    return ndimage.maximum_filter(mask, size=2 * cells + 1, mode="constant")


def retained_water(epochs, lines):
    """Keep mapped five-minute pools and every later observed water vertex."""
    five = epochs["t005"] > 0
    later = np.zeros_like(five)
    for label, depth in epochs.items():
        if int(label[1:]) > 5:
            later |= depth > 0
    labels, count = ndimage.label(five, np.ones((3, 3)))
    kept = np.unique(labels[(five & lines) | (five & later)])
    ignored = np.isin(labels, np.setdiff1d(np.arange(1, count + 1), kept))
    retained = (five & ~ignored) | later
    sustained = retained.copy()
    for label, depth in epochs.items():
        if int(label[1:]) >= 5:
            sustained &= depth > 0
    return retained, sustained, ignored


def ring_release(retained, sustained, initial):
    """Only one sustained patch may lie within the startup ring's two cells.

    Preserve a route for any adjacent startup cell not touching retained water.
    The full retained native interpolation ring wins independently of release.
    """
    labels, _ = ndimage.label(retained, np.ones((3, 3)))
    high = ndimage.maximum_filter(labels, size=5, mode="constant")
    low = -ndimage.maximum_filter(
        np.where(labels > 0, -labels, -1_000_000_000), size=5, mode="constant"
    )
    one_patch = (high > 0) & (high == low)
    transient_near = dilate(retained & ~sustained, 2)
    orphan = (initial > 0) & ~dilate(retained)
    release = one_patch & ~transient_near & ~dilate(orphan)
    return release, transient_near, (high > 0) & (high != low)


def footprint(source, rate, shape=(1081, 1081)):
    yy, xx = np.mgrid[: shape[0], : shape[1]]
    dx = np.asarray(xx * 16 - 8640 - np.float32(source["x"]), dtype=np.float32)
    dz = np.asarray(8640 - yy * 16 - np.float32(source["z"]), dtype=np.float32)
    radius = np.float32(np.sqrt(np.float32(rate)) * np.float32(0.4) + 10)
    return dx * dx + dz * dz <= radius * radius


def dry_capacity(floor, target, mask):
    return int(np.maximum(round(target * 64) - floor[mask].astype(np.int64), 0).sum())


def availability(floor, water, target, mask):
    # Native min(floor+water-max(target,floor),water) simplifies to this,
    # including negative contributions at dry vertices below target.
    return int(water[mask].astype(np.int64).sum()) - dry_capacity(floor, target, mask)


def intake_constraint(source, actual, floor, epochs, mask):
    """Zero sampled buffer is necessary; sampled nonpositive sums aren't enough.

    Above-target water requires invariant below-target dry capacity for every
    water state. Otherwise startup still needs its own paired floor/water test.
    """
    inactive = (
        source["type"] == 1
        and source["input_rate"] > 0
        and source["output_rate"] == 0
        and all(s["buffered_water"] == 0 and s["flow"] == 0 for s in actual)
    )
    target = round(source["target"] * 64)
    above = any(
        (
            (depth[mask] > 0) & (floor[mask].astype(np.int64) + depth[mask] > target)
        ).any()
        for label, depth in epochs.items()
        if int(label[1:]) >= 5
    )
    if not inactive:
        return mask.copy(), False, bool(above)
    return mask & (floor < target) if above else np.zeros_like(mask), True, bool(above)


def restore(
    terrain, water, original, banks, geometry, eligible, retained, sustained, hard
):
    guard = hard | dilate(retained)
    initial = water.copy()
    initial[(water > 0) & ~retained & ~guard] = 0
    browser = stroke(geometry["sq"], geometry.get("rivers", []))
    restored, cuts = restore_line_cuts(
        original, banks, geometry, browser & eligible, browser & ~eligible
    )
    lines = stroke(geometry["sq"], source_pieces(geometry)) | raster(
        geometry["sq"], source_pieces(geometry)
    )
    proposed = np.maximum(
        terrain / 64,
        np.minimum(banks, terrain / 64 + np.maximum(0, restored - original)),
    )
    near = distance(eligible)
    zone = (near <= 3) & (near < distance(lines & ~eligible))
    proposed[zone] = np.maximum(proposed[zone], restored[zone])
    candidate = np.maximum(terrain, quantize(proposed))
    release, transient_near, bridge = ring_release(retained, sustained, initial)
    startup_ring = dilate(initial > 0)
    frozen = guard | (startup_ring & ~release)
    candidate[frozen] = terrain[frozen]
    assert np.all(candidate >= terrain) and np.all(initial <= water)
    assert np.array_equal(candidate[hard], terrain[hard])
    assert np.array_equal(initial[guard], water[guard])
    assert not ((candidate != terrain) & startup_ring & ~release).any()
    released_raises = (candidate > terrain) & startup_ring
    assert not (released_raises & (transient_near | bridge)).any()
    return (
        candidate,
        initial,
        {
            "hard_guard": hard,
            "wet_guard": guard,
            "retained": retained,
            "sustained": sustained,
            "startup_ring": startup_ring,
            "ring_release": release,
            "released_raises": released_raises,
            "transient_near": transient_near,
            "bridge": bridge,
        },
        cuts,
    )


def plan(prepared, observed, fixture, output):
    if output.exists():
        raise ValueError("Refusing existing plan output")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True):
        raise ValueError("Commit the exact experimental source before planning")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    terrain, water, _, _, binding = native_evidence(prepared, observed)
    floor = grid(observed / "grids/t000-water-ground.u16").astype(np.int64)
    for label in ["t000", "t005"]:
        assert np.array_equal(floor, grid(observed / f"grids/{label}-water-ground.u16"))
        assert np.array_equal(
            floor, grid(observed / f"grids/{label}-water-ground-target.u16")
        )
    samples = [
        json.loads(s) for s in (observed / "timeline.jsonl").read_text().splitlines()
    ]
    samples = [s for s in samples if s.get("kind") == "sample"]
    epochs = {
        p.name[:4]: grid(p) for p in sorted((observed / "grids").glob("t*-water.u16"))
    }
    assert np.array_equal(epochs["t000"], water)
    geometry, _ = surface_geometry(read(prepared / "geometry.json"))
    assert (prepared / "geometry.json").read_bytes() == gzip.decompress(
        (fixture / "shipping-geometry.json.gz").read_bytes()
    )
    hydro = read(prepared / "hydrology.json")
    lines = stroke(geometry["sq"], source_pieces(geometry)) | raster(
        geometry["sq"], source_pieces(geometry)
    )
    retained, sustained, ignored = retained_water(epochs, lines)
    bodies = raster(
        geometry["sq"],
        geometry.get("lakes", []) + geometry.get("oceans", []),
        polygons=True,
    )
    fixed = protected_infrastructure({**hydro, "sources": []}) | dilate(
        bodies | (floor != terrain)
    )
    controls = []
    for i, source in enumerate(samples[0]["water"]["sources"]):
        actual = [s["water"]["sources"][i] for s in samples]
        assert source["id"] == i + 1
        for s in actual:
            assert all(
                s[k] == source[k]
                for k in ["id", "type", "x", "z", "target", "input_rate", "output_rate"]
            )
        mask = np.zeros_like(retained)
        for key in ["input_rate", "output_rate"]:
            if source[key]:
                mask |= footprint(source, source[key])
        guard, inactive, above = intake_constraint(source, actual, floor, epochs, mask)
        controls.append(
            {
                "source": source,
                "mask": mask,
                "guard": guard,
                "released": inactive,
                "above_target": above,
            }
        )
    original = np.asarray(Image.open(fixture / "input.png"), float) * 1024 / 65535
    banks = np.frombuffer(
        gzip.decompress((fixture / "banks.f32.gz").read_bytes()), "<f4"
    ).reshape(1081, 1081)
    eligible = eligible_lines(geometry, hydro)
    for _ in range(len(controls) + 1):
        hard = fixed.copy()
        for control in controls:
            hard |= control["guard"]
        candidate, initial, masks, cuts = restore(
            terrain,
            water,
            original,
            banks,
            geometry,
            eligible,
            retained,
            sustained,
            hard,
        )
        new_floor = floor + candidate.astype(np.int64) - terrain
        invalid = []
        for c in controls:
            if not c["released"]:
                continue
            s, mask = c["source"], c["mask"]
            shift = dry_capacity(floor, s["target"], mask) - dry_capacity(
                new_floor, s["target"], mask
            )
            initial_available = availability(new_floor, initial, s["target"], mask)
            if (c["above_target"] and shift != 0) or initial_available > 0:
                invalid.append(c)
        if not invalid:
            break
        for c in invalid:
            c["released"] = False
            c["guard"] = c["mask"]
    else:
        raise ValueError("Intake constraint did not converge")
    rows = []
    for c in controls:
        s, mask = c["source"], c["mask"]
        shift = dry_capacity(floor, s["target"], mask) - dry_capacity(
            new_floor, s["target"], mask
        )
        if not c["released"]:
            assert shift == 0
            assert np.array_equal(candidate[mask], terrain[mask])
            assert np.array_equal(initial[mask], water[mask])
        rows.append(
            {
                "native_id": s["id"],
                "released": c["released"],
                "above_target": c["above_target"],
                "capacity_shift_units": shift,
                "t000_availability_units": availability(
                    new_floor, initial, s["target"], mask
                ),
                "floor_changes": int(((candidate != terrain) & mask).sum()),
                "startup_water_changes": int(((initial != water) & mask).sum()),
            }
        )
    paths = [
        prepared / p
        for p in ["terrain.u16", "water.u16", "geometry.json", "hydrology.json"]
    ]
    paths += [
        observed / "timeline.jsonl",
        fixture / "input.png",
        fixture / "banks.f32.gz",
    ]
    paths += sorted((observed / "grids").glob("*.u16"))
    report = {
        "source_head": head,
        "status": "unqualified experimental arrays; no native or shipping acceptance",
        "binding": binding,
        "input_files_sha256": {str(p): sha(p) for p in paths},
        "terrain_raised": int((candidate > terrain).sum()),
        "terrain_lowered": 0,
        "startup_water_removed": int((initial < water).sum()),
        "startup_water_added": 0,
        "released_ring_vertices": int(
            (masks["ring_release"] & masks["startup_ring"] & ~masks["wet_guard"]).sum()
        ),
        "released_ring_raises": int(masks["released_raises"].sum()),
        "raised_near_transient_or_bridge": 0,
        "native_grid_epochs": list(epochs),
        "intakes": rows,
        "cuts": cuts,
    }
    output.mkdir(parents=True)
    write_grid(output / "terrain.u16", candidate)
    write_grid(output / "water.u16", initial)
    np.savez_compressed(output / "masks.npz", **masks, ignored_five=ignored)
    (output / "admission.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in ["binding", "input_files_sha256", "intakes"]
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["prepared", "observed", "fixture", "output"]:
        parser.add_argument(name, type=Path)
    plan(**vars(parser.parse_args()))
