"""Audit native soak inputs, exact probes, nearby water and off-channel spreading.

Nearby water is supplementary evidence, not a replacement for exact-point
failures. Spatial results cover the saved grids, not every simulation frame.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy import ndimage

from region import HALF, raster


def grid(path):
    return np.fromfile(path, dtype="<u2").reshape(1081, 1081) / 64


def audit(run, prepared, geometry, reference_water=None):
    report = json.loads((run / "report.json").read_text())
    hydro = json.loads((prepared / "hydrology.json").read_text())
    geo = json.loads(geometry.read_text())
    samples = [
        row
        for line in (run / "timeline.jsonl").read_text().splitlines()
        if (row := json.loads(line))["kind"] == "sample"
    ]
    initial = grid(run / "grids" / (report["first_dump"] + "-water.u16"))
    reference = reference_water or prepared / "water.u16"
    expected = grid(reference) > 0.1
    for field in ["rivers", "streams"]:
        expected |= np.flipud(raster(geo["sq"], geo.get(field, [])))
    for field in ["lakes", "riverAreas"]:
        expected |= np.flipud(raster(geo["sq"], geo.get(field, []), polygons=True))
    distance = ndimage.distance_transform_edt(~expected) * 16
    extents, nearby = [], []
    points = report["points"]
    for path in sorted((run / "grids").glob("t*-water.u16")):
        water = grid(path)
        far = (distance > 128) & (water > 0.5)
        extents.append(
            {
                "grid": path.name,
                "newly_wet_km2": float(
                    ((initial <= 0.1) & (water > 0.1)).sum() * 256 / 1e6
                ),
                "outside_128m_km2": float(far.sum() * 256 / 1e6),
                "outside_max_depth_m": float(water[far].max()) if far.any() else 0,
            }
        )
        local = []
        for point in points:
            ix, iz = round((point["x"] + HALF) / 16), round((point["z"] + HALF) / 16)
            candidates = []
            for dz in range(-4, 5):
                for dx in range(-4, 5):
                    if (
                        dx * dx + dz * dz <= 16
                        and 0 <= ix + dx <= 1080
                        and 0 <= iz + dz <= 1080
                    ):
                        if water[iz + dz, ix + dx] > 0.1:
                            candidates.append(math.hypot(dx, dz) * 16)
            local.append(min(candidates) if candidates else None)
        nearby.append(local)
    failures = []
    counts = {}
    for i, point in enumerate(points):
        boundary = max(abs(point["x"]), abs(point["z"])) >= HALF - 16
        playable = max(abs(point["x"]), abs(point["z"])) <= 4800
        kind = "river" if "[river]" in point["name"] else "other_waterway"
        exact_dry = [
            row["label"] for row in samples if not row["water"]["samples"][i]["wet"]
        ]
        native_nearby = [
            row for row in samples if "wet_within_64m" in row["water"]["samples"][i]
        ]
        native_nearby_dry = [
            row["label"]
            for row in native_nearby
            if not row["water"]["samples"][i]["wet_within_64m"]
        ]
        grid_dry = [
            row["grid"] for row, values in zip(extents, nearby) if values[i] is None
        ]
        cohorts = [kind + "_all"]
        if not boundary:
            cohorts.append(kind + "_nonboundary")
        if playable:
            cohorts.append(kind + "_playable_envelope")
        for cohort in cohorts:
            count = counts.setdefault(
                cohort,
                {
                    "points": 0,
                    "exact_wet_end": 0,
                    "ever_exact_dry": 0,
                    "ever_no_water_within_64m_in_saved_grids": 0,
                    "native_nearby_observations": 0,
                    "ever_no_water_within_64m_in_samples": 0,
                },
            )
            count["points"] += 1
            count["exact_wet_end"] += int(point["wet_end"])
            count["ever_exact_dry"] += bool(exact_dry)
            count["ever_no_water_within_64m_in_saved_grids"] += bool(grid_dry)
            count["native_nearby_observations"] += len(native_nearby)
            count["ever_no_water_within_64m_in_samples"] += bool(native_nearby_dry)
        if exact_dry or grid_dry or native_nearby_dry:
            failures.append(
                {
                    "name": point["name"],
                    "x": point["x"],
                    "z": point["z"],
                    "map_boundary": boundary,
                    "playable_envelope": playable,
                    "exact_dry_samples": exact_dry,
                    "no_nearby_water_samples": native_nearby_dry,
                    "no_nearby_water_grids": grid_dry,
                    "nearest_water_m_end": nearby[-1][i],
                }
            )
    observed = samples[0]["water"]["sources"]
    controls_match = len(observed) == len(hydro["sources"])
    for native, source in zip(observed, hydro["sources"]):
        controls_match &= (
            native["type"] == 1
            and abs(native["x"] - source["position"][0]) < 0.001
            and abs(native["z"] - source["position"][2]) < 0.001
            and abs(native["target"] - source["target"]) <= 1 / 128 + 1e-6
            and native["input_rate"]
            == native["output_rate"]
            == math.floor(source["capacity"] * 65535 + 0.5)
        )
    terrain = run / "grids" / (report["first_dump"] + "-terrain.u16")
    return {
        "map": report["map"]["map_name"],
        "game_minutes": report["game_minutes"],
        "terrain_exact": terrain.read_bytes()
        == (prepared / "terrain.u16").read_bytes(),
        "initial_water_exact": (
            run / "grids" / (report["first_dump"] + "-water.u16")
        ).read_bytes()
        == (prepared / "water.u16").read_bytes(),
        "source_controls_match": bool(controls_match),
        "prepared_terrain_sha256": hashlib.sha256(
            (prepared / "terrain.u16").read_bytes()
        ).hexdigest(),
        "cohorts": counts,
        "failures": failures,
        "spreading": extents,
        "spreading_definition": "depth >0.5m, >128m from reference water union mapped lines/polygons; saved grids only",
        "reference_water_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "nearby_definition": "depth >0.1m within 64m of the fixed probe; supplementary, exact failures retained",
        "paths_start": report.get("paths_start"),
        "paths_end": report.get("paths_end"),
        "strict_disableMods": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["run", "prepared", "geometry"]:
        parser.add_argument(name, type=Path)
    parser.add_argument(
        "--reference-water",
        type=Path,
        help="Common expected-water footprint for A/B spreading comparisons; defaults to prepared water",
    )
    args = parser.parse_args()
    print(json.dumps(audit(**vars(args)), indent=2))
