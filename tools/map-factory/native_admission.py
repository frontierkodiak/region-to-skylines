"""Plan a bounded, native-evidence dry-reach removal; never change defaults.

Input is an exact previously observed prepared map, not an arbitrary DEM. A
complete mapped source piece must lack native water within 64 m at five minutes
and every later recorded epoch. Existing bank-limited rivers and feasible
modeled streams are eligible. Native wet support, controls and networks win. A piece
whose centreline cannot be completely restored is deferred, not half-admitted.
Fresh short captures and full evaluations remain mandatory after this CPU plan.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from admission import distance, remove_connector_cuts, stroke
from region import raster
from surface_water import surface_geometry
from verify_bank_restoration import require_continuous_floor

ROOT = Path(__file__).resolve().parent
PLANNER_FILES = [
    "native_admission.py",
    "admission.py",
    "region.py",
    "prepare.py",
    "surface_water.py",
    "verify_bank_restoration.py",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def grid(path):
    """Native south-first ushort grid to north-first planning grid."""
    return np.fromfile(path, "<u2").reshape(1081, 1081)[::-1].copy()


def quantize(values):
    return np.floor(values * 64 + 0.5).clip(0, 65535).astype("<u2")


def write_grid(path, values):
    values[::-1].astype("<u2").tofile(path)


def native_evidence(prepared, observed):
    generation = read(prepared / "generation.json")
    hydro = read(prepared / "hydrology.json")
    package = prepared / (hydro["map_id"] + ".crp")
    receipt = read(observed / "session-receipt.json")
    if not (
        sha(package) == generation["package"]["sha256"] == receipt["map"]["sha256"]
    ):
        raise ValueError("Native evidence belongs to a different package")
    if any(receipt["cleanup"].values()):
        raise ValueError("Native reference has incomplete cleanup")
    if read(observed / "report.json")["game_minutes"] < 5:
        raise ValueError("Native reference did not reach five minutes")
    terrain, water = (grid(prepared / f"{name}.u16") for name in ["terrain", "water"])
    for name in ["terrain", "water"]:
        if (prepared / f"{name}.u16").read_bytes() != (
            observed / f"grids/t000-{name}.u16"
        ).read_bytes():
            raise ValueError(f"Native initial {name} mismatch")
    epochs = sorted((observed / "grids").glob("t*-water.u16"))
    epochs = [p for p in epochs if p.name != "t000-water.u16"]
    if not any(p.name == "t005-water.u16" for p in epochs):
        raise ValueError("An actual five-minute native water grid is required")
    for path in (observed / "grids").glob("t*-terrain.u16"):
        if path.read_bytes() != (prepared / "terrain.u16").read_bytes():
            raise ValueError("Reference terrain changed during simulation")
    # >=7 is the unchanged harness near-water test. >0 protects even thinner
    # native water and all its neighboring interpolation vertices.
    observed_wet = np.zeros_like(terrain, dtype=bool)
    near_water = np.zeros_like(terrain, dtype=bool)
    for path in epochs:
        depth = grid(path)
        observed_wet |= depth > 0
        if (depth >= 7).any():
            near_water |= distance(depth >= 7) <= 4
    return (
        terrain,
        water,
        observed_wet,
        near_water,
        {
            "package_sha256": sha(package),
            "native_files_sha256": {
                str(p.relative_to(observed)): sha(p)
                for p in [
                    observed / "session-receipt.json",
                    observed / "report.json",
                    *epochs,
                ]
            },
            "epochs": [p.stem.removesuffix("-water") for p in epochs],
        },
    )


def protected_infrastructure(hydro):
    """Keep all physical control footprints and actual network corridors fixed."""
    yy, xx = np.mgrid[:1081, :1081]
    protected = np.zeros((1081, 1081), dtype=bool)
    for source in hydro["sources"]:
        x, _, z = source["position"]
        rate = max(source["capacity"], source.get("output_capacity", 0))
        radius = 10 + 0.4 * np.sqrt(np.floor(rate * 65535 + 0.5))
        protected |= np.hypot(xx * 16 - 8640 - x, 8640 - yy * 16 - z) <= radius + 32
    image = Image.new("L", (1081, 1081))
    draw = ImageDraw.Draw(image)
    positions = hydro["node_positions"]
    layout = read(ROOT / "templates/native-corridors.json")
    for segment in layout["segments"]:
        a, b = (positions[str(segment[k])] for k in ["from", "to"])
        draw.line([(540 + p[0] / 16, 540 - p[2] / 16) for p in [a, b]], fill=1, width=9)
    protected |= np.asarray(image) > 0
    return protected


def source_pieces(geometry):
    return geometry.get("rivers", []) + geometry.get("streams", [])


def retain_startup_support(terrain, candidate, water, zone, protected):
    """Omit a dry piece's film without changing another startup water patch."""
    candidate = candidate.copy()
    while True:
        clear = (zone | (candidate > terrain)) & ~protected
        remaining = (water > 0) & ~clear
        support = ndimage.maximum_filter(remaining, size=3, mode="constant")
        conflicts = support & (candidate > terrain)
        if not conflicts.any():
            return candidate
        # Restoring a previously cleared vertex may retain a startup water cell,
        # which can protect another patch. Continue to the finite fixed point.
        candidate[conflicts] = terrain[conflicts]


def dry_pieces(geometry, hydro, near_water):
    """Use source geography, not qualification observations or camera bounds."""
    eligible = {}
    for field, kind in [("rivers", "river"), ("streams", "stream")]:
        eligible[field] = np.zeros_like(near_water)
        modeled = [
            r
            for r in hydro["rivers"]
            if r["class"] == kind
            and (
                r.get("bank_limited")
                or (kind == "stream" and not r.get("unforced_infeasible_stream"))
            )
        ]
        for name in {r["name"] for r in modeled}:
            features = [
                f
                for f in geometry.get(field, [])
                if (f.get("name") or "unnamed waterway") == name
            ]
            mapped = raster(geometry["sq"], features)
            labels, _ = ndimage.label(
                ndimage.binary_dilation(mapped, iterations=2), structure=np.ones((3, 3))
            )
            for river in modeled:
                if river["name"] == name:
                    x, y = river["upstream"]
                    label = labels[y, x]
                    if label:
                        eligible[field] |= mapped & (labels == label)
    selected = []
    for index, feature in enumerate(source_pieces(geometry)):
        field = "rivers" if index < len(geometry.get("rivers", [])) else "streams"
        mapped = raster(geometry["sq"], [feature])
        browser_line = stroke(geometry["sq"], [feature])
        footprint = mapped | browser_line
        if not footprint.any() or (footprint & near_water).any():
            continue
        if not (mapped & eligible[field]).any() or (mapped & ~eligible[field]).any():
            continue
        selected.append((index, feature))
    return selected


def plan(prepared, observed, fixture, output):
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--", *PLANNER_FILES], cwd=ROOT, text=True
    ).strip():
        raise ValueError("Commit the exact planner snapshot before producing plans")
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    planner_hashes = {name: sha(ROOT / name) for name in PLANNER_FILES}
    terrain, water, wet, near, binding = native_evidence(prepared, observed)
    geometry, _ = surface_geometry(read(prepared / "geometry.json"))
    if (prepared / "geometry.json").read_bytes() != gzip.decompress(
        (fixture / "shipping-geometry.json.gz").read_bytes()
    ):
        raise ValueError("Browser-cut replay needs the exact held source geometry")
    banks = np.fromfile(prepared / "banks.f32", "<f4").reshape(1081, 1081).astype(float)
    if not np.all(np.isfinite(banks)):
        raise ValueError("Uncarved DEM contains non-finite values")
    if (prepared / "banks.f32").read_bytes() != gzip.decompress(
        (fixture / "banks.f32.gz").read_bytes()
    ):
        raise ValueError("Uncarved DEM does not match held browser input")
    original = np.asarray(Image.open(fixture / "input.png"), dtype=float) * 1024 / 65535
    hydro = read(prepared / "hydrology.json")
    selected = dry_pieces(geometry, hydro, near)
    initially_selected = [i for i, _ in selected]
    protected = ndimage.maximum_filter(
        wet, size=3, mode="constant"
    ) | protected_infrastructure(hydro)
    independent_bodies = raster(
        geometry["sq"],
        geometry.get("lakes", []) + geometry.get("oceans", []),
        polygons=True,
    )
    protected |= ndimage.maximum_filter(independent_bodies, size=3, mode="constant")
    deferred = []
    while True:
        if not selected:
            candidate = terrain.copy()
            zone = np.zeros_like(protected)
            restoration = None
            break
        surveys = [{"features": [f for _, f in selected], "gravity_excess_m": []}]
        restored_input, restoration = remove_connector_cuts(
            original, banks, geometry, surveys
        )
        chosen = {i for i, _ in selected}
        rejected = stroke(geometry["sq"], [f for _, f in selected])
        retained = stroke(
            geometry["sq"],
            [f for i, f in enumerate(source_pieces(geometry)) if i not in chosen],
        )
        removed_distance, retained_distance = distance(rejected), distance(retained)
        zone = (removed_distance <= 3) & (removed_distance < retained_distance)
        delta = np.maximum(0, restored_input - original)
        proposed = np.maximum(terrain / 64, np.minimum(banks, terrain / 64 + delta))
        # Also remove the old Python incision inside the selected dry territory.
        # Never remove a different reach's floor or a native wet/control support.
        proposed[zone] = np.maximum(proposed[zone], restored_input[zone])
        candidate = np.maximum(terrain, quantize(proposed))
        candidate[protected] = terrain[protected]
        candidate = retain_startup_support(terrain, candidate, water, zone, protected)
        failed = []
        for index, feature in selected:
            line = stroke(geometry["sq"], [feature]) | raster(geometry["sq"], [feature])
            # The held DEM plus independently retained browser cuts is the
            # target, not bare banks: a neighboring admitted river may still
            # contribute at a shared endpoint. Do not erase that other cut.
            if (candidate[line] < quantize(restored_input)[line]).any():
                failed.append(index)
                deferred.append(
                    {
                        "source_piece": index,
                        "reason": "retained wet/control/network or independent cut prevents complete centreline restoration",
                    }
                )
        if not failed:
            break
        selected = [(i, f) for i, f in selected if i not in failed]
    changed = candidate > terrain
    # No startup film is put on an omitted source line or its restored cut.
    # Existing sea/lake/other-river support won every conflict above.
    clear = (zone | changed) & ~protected
    initial = water.copy()
    initial[clear] = 0
    if (candidate < terrain).any():
        raise ValueError("Admission must never deepen an existing floor")
    require_continuous_floor(terrain, candidate, wet.astype(np.uint16))
    require_continuous_floor(terrain, candidate, initial)
    # Retain the whole observation contract byte-for-byte in the eventual run.
    frozen = observed / "probes.json"
    report = {
        "planner_source_commit": source_commit,
        "status": "CPU-only; fresh native short result and five-map evaluation required",
        "rule": "complete modeled minor source piece dry and not within native 64m water at five minutes and every later recorded epoch; independently supported cuts win",
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
        "frozen_probes_sha256": sha(frozen),
        "frozen_observations": len(read(frozen)["points"]),
        "initially_dry_pieces": initially_selected,
        "admitted_uncarved_pieces": [
            {"source_piece": i, "feature": f} for i, f in selected
        ],
        "deferred_pieces": deferred,
        "terrain_raised_vertices": int(changed.sum()),
        "terrain_lowered_vertices": 0,
        "maximum_raise_m": float((candidate.astype(int) - terrain).max() / 64),
        "startup_water_removed_vertices": int((initial != water).sum()),
        "native_wet_interpolation_support_unchanged": True,
        "retained_startup_interpolation_support_unchanged": True,
        "source_controls_unchanged": True,
        "network_corridor_unchanged": True,
        "browser_replay_restored_vertices": 0
        if restoration is None
        else restoration["restored_vertices"],
    }
    output.mkdir(parents=True, exist_ok=False)
    write_grid(output / "terrain.u16", candidate)
    write_grid(output / "water.u16", initial)
    (output / "hydrology.json").write_bytes((prepared / "hydrology.json").read_bytes())
    report["candidate_files_sha256"] = {
        name: sha(output / name)
        for name in ["terrain.u16", "water.u16", "hydrology.json"]
    }
    if planner_hashes != {name: sha(ROOT / name) for name in PLANNER_FILES}:
        raise ValueError("Planner source changed during generation; discard this plan")
    report["planner_files_sha256"] = planner_hashes
    (output / "admission.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["prepared", "observed", "fixture", "output"]:
        parser.add_argument(name, type=Path)
    result = plan(**vars(parser.parse_args()))
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                not in ["binding", "prepared_files_sha256", "admitted_uncarved_pieces"]
            },
            indent=2,
        )
    )
