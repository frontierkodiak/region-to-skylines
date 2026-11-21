"""Explicit development exporter: fresh preparation, enclosed starter storage.

Not imported by the shipping exporter. Existing source-bound admission remains
an earthwork transformation, never qualification for this new candidate.
"""

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from crp import N, decode_u16, read_package, write_map
from region import (
    HALF,
    SIZE,
    fit_networks,
    hydrology,
    limit_source_footprints,
    raster,
    start_area,
)
from reservoir_basin import construct_closed_reservoir, validate_native_basin
from resources import Knobs
from soak import (
    geographic_river_probes,
    mapped_water_reference,
    panel_expectations,
    probes_for,
    world_references,
)
from surface_water import surface_geometry
from template import manager_tag
from water_diagnostics import bind_sources, decode_water
from wet_reach_admission import admit

ROOT = Path(__file__).resolve().parent
POLICY = "closed-starter-storage-development-v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native(values):
    return np.floor(values * 64 + 0.5).clip(0, 65535).astype("<u2")


@dataclass(frozen=True)
class PreparedStorage:
    terrain: np.ndarray
    water: np.ndarray
    hydro: dict
    preconstruction_terrain: np.ndarray
    preconstruction_water: np.ndarray


def construction_masks(terrain, water, geometry, start, network, layout):
    """Constrain the full excavation/rim, including unmodeled mapped features."""
    rows, cols = np.indices(terrain.shape)
    x, z = cols * 16 - HALF, HALF - rows * 16
    center_x, center_z = (start["x"] - 2) * 1920, (start["z"] - 2) * 1920
    candidate = (abs(x - center_x) < 960) & (abs(z - center_z) < 960)
    mapped = water > 0
    for field in ("rivers", "streams", "undergroundWaterways"):
        mapped |= raster(geometry["sq"], geometry.get(field, []))
    for field in ("lakes", "riverAreas", "oceans"):
        mapped |= raster(geometry["sq"], geometry.get(field, []), polygons=True)
    protected = (
        ndimage.distance_transform_edt(~mapped) * 16 <= 128
        if mapped.any()
        else np.zeros_like(mapped)
    )
    protected |= np.hypot(x - start["landing"][0], z - start["landing"][1]) <= 128
    image = Image.new("L", (SIZE, SIZE))
    draw = ImageDraw.Draw(image)
    for route in layout["routes"]:
        points = []
        for node in route["nodes"]:
            position = network["node_positions"][str(node)]
            if not np.isfinite(position).all():
                raise ValueError("Nonfinite network position")
            points.append(((position[0] + HALF) / 16, (HALF - position[2]) / 16))
        if len(points) >= 2:
            draw.line(points, fill=255, width=1)
    roads = np.asarray(image) > 0
    if roads.any():
        # The writer fits earthworks to 80m; allow two more cells for raster error.
        protected |= ndimage.distance_transform_edt(~roads) * 16 <= 112
    return candidate, protected


def construct_after_networks(terrain, water, geometry, start, network, layout, sources):
    candidate, protected = construction_masks(
        terrain, water, geometry, start, network, layout
    )
    rows, cols = np.indices(terrain.shape)
    x, z = cols * 16 - HALF, HALF - rows * 16
    for source in sources:
        rate = max(
            source["capacity"], source.get("output_capacity", source["capacity"])
        )
        radius = 10 + 0.4 * np.sqrt(np.floor(rate * 65535 + 0.5)) + 64
        protected |= (
            np.hypot(x - source["position"][0], z - source["position"][2]) <= radius
        )
    return construct_closed_reservoir(
        terrain, water, candidate, protected, np.asarray(start["landing"]) + [320, 0]
    )


def prepare_arrays(ground, banks, geometry, layout):
    """Never invoke the legacy pond carve or its prefill, even transiently."""
    geometry, _ = surface_geometry(geometry)
    ground, banks = np.array(ground, dtype=float), np.asarray(banks, dtype=float)
    if (
        ground.shape != (SIZE, SIZE)
        or banks.shape != ground.shape
        or not np.isfinite(ground).all()
        or not np.isfinite(banks).all()
    ):
        raise ValueError("Expected complete finite source elevation grids")
    depth, summary = hydrology(ground, banks, geometry)
    start = start_area(ground, depth, geometry)
    needs_storage = not start["has_water"]
    network = fit_networks(ground, depth, geometry, layout, start)
    limit_source_footprints(ground, depth, banks, geometry, summary)
    ground, depth = native(ground).astype(float) / 64, native(depth).astype(float) / 64
    before_terrain, before_water = ground.copy(), depth.copy()
    before_hash = hashlib.sha256(
        native(np.flipud(ground)).tobytes() + native(np.flipud(depth)).tobytes()
    ).hexdigest()
    construction = None
    if needs_storage:
        basin = construct_after_networks(
            ground, depth, geometry, start, network, layout, summary["sources"]
        )
        ground, depth = basin.terrain, basin.water
        summary["sources"].append(
            {**basin.source, "name": "constructed enclosed starter reservoir"}
        )
        construction = basin.receipt
        summary["starter_reservoir"] = True
        start["has_water"] = True
    summary.update(network)
    summary.update(
        {
            "start_tile": start["index"],
            "start_area": start,
            "map_id": "PL1191-" + geometry["sq"]["slug"] + "-closed-storage",
            "map_name": geometry["sq"]["name"] + " - Experimental enclosed storage",
            "wet_cells": int((depth > 0).sum()),
            "bank_input": "uncarved captured elevations",
            "water_construction": {
                "policy": POLICY,
                "legacy_pond_prefill_added": False,
                "preconstruction_native_grids_sha256": before_hash,
                "construction_after_network_earthworks": True,
                "constructed": construction,
                "qualification": "geometric development candidate only; NOT native qualified",
            },
        }
    )
    return PreparedStorage(ground, depth, summary, before_terrain, before_water)


def validate_package(folder):
    """Validate final bytes after all earthworks, admission and resource packing."""
    hydro = json.loads((folder / "hydrology.json").read_text())
    package = folder / (hydro["map_id"] + ".crp")
    simulation = next(
        a["payload"] for a in read_package(package.read_bytes())[1] if a["kind"] == 52
    )
    decoded = decode_water(simulation)
    bind_sources(decoded, hydro)
    if decoded["depth"].astype("<u2").tobytes() != (folder / "water.u16").read_bytes():
        raise ValueError("Final package initial water differs from prepared grid")
    tag = manager_tag("TerrainManager")
    if simulation.count(tag) != 1:
        raise ValueError("Final terrain manager is not unique")
    encoded_floor, offset = decode_u16(simulation, N, simulation.index(tag) + len(tag))
    delta, _ = decode_u16(simulation, int((encoded_floor != 0).sum()), offset)
    if (
        encoded_floor.astype("<u2").tobytes() != (folder / "terrain.u16").read_bytes()
        or delta.any()
    ):
        raise ValueError("Final package terrain differs from its static floor")
    floor = (
        np.flipud(np.fromfile(folder / "terrain.u16", "<u2").reshape(SIZE, SIZE)) / 64
    )
    before_t = (folder / "preconstruction-terrain.u16").read_bytes()
    before_w = (folder / "preconstruction-water.u16").read_bytes()
    if (
        hashlib.sha256(before_t + before_w).hexdigest()
        != hydro["water_construction"]["preconstruction_native_grids_sha256"]
    ):
        raise ValueError("Preconstruction source grids no longer match")
    before_floor = np.flipud(np.frombuffer(before_t, "<u2").reshape(SIZE, SIZE)) / 64
    before_depth = np.flipud(np.frombuffer(before_w, "<u2").reshape(SIZE, SIZE)) / 64
    initial_depth = np.flipud(decoded["depth"].reshape(SIZE, SIZE)) / 64
    rows, cols = np.indices(floor.shape)
    storage = np.zeros_like(floor, dtype=bool)
    checks = []
    for i, source in enumerate(hydro["sources"]):
        if source.get("class") != "reservoir":
            continue
        control = decoded["sources"][i]
        check = validate_native_basin(floor, control)
        distance = np.hypot(
            cols * 16 - HALF - control["position"][0],
            HALF - rows * 16 - control["position"][2],
        )
        disk = distance < 96
        rim = ndimage.binary_dilation(disk, structure=np.ones((3, 3))) & ~disk
        core = distance <= check["source_radius_m"]
        cut = before_floor[disk] - floor[disk]
        if (
            (cut < 0).any()
            or (cut > 3).any()
            or not np.array_equal(floor[rim], before_floor[rim])
        ):
            raise ValueError(
                "Final storage earthworks violate no-fill/cut/untouched-rim bounds"
            )
        if (initial_depth[core] < 1).any():
            raise ValueError(
                "Final initial storage lacks one metre across source footprint"
            )
        checks.append(
            {
                "source_index": i,
                **check,
                "maximum_cut_m": float(cut.max()),
                "minimum_initial_footprint_depth_m": float(initial_depth[core].min()),
            }
        )
        storage |= disk
    if (initial_depth[~storage] > before_depth[~storage]).any():
        raise ValueError("Initial water added outside the new storage envelope")
    return {
        "package_sha256": sha(package),
        "static_storage_checks": checks,
        "native_hydraulic_floor_check": "not observed; required before qualification",
    }


def export(png, geometry, banks, output, landcover=None, evidence=None, knobs=None):
    if output.exists():
        raise ValueError("Use a fresh candidate output directory")
    inputs = {
        "source-input.png": png,
        "geometry.json": geometry,
        "source-banks.f32": banks,
    }
    if landcover is not None:
        inputs["source-landcover.u8.gz"] = landcover
    if evidence is not None:
        inputs["source-evidence.json"] = evidence
    frozen = {name: path.read_bytes() for name, path in inputs.items()}
    output.mkdir(parents=True)
    for name, raw in frozen.items():
        (output / name).write_bytes(raw)
    data = json.loads(frozen["geometry.json"])
    image = np.asarray(Image.open(output / "source-input.png"))
    if image.shape != (SIZE, SIZE) or image.min() < 0 or image.max() > 65535:
        raise ValueError("Expected a 1081-square 16-bit captured heightmap")
    layout_path = ROOT / "templates/native-corridors.json"
    layout = json.loads(layout_path.read_text())
    prepared = prepare_arrays(
        image.astype(float) * 1024 / 65535,
        np.fromfile(output / "source-banks.f32", "<f4").reshape(SIZE, SIZE),
        data,
        layout,
    )
    for name, grid in [
        ("terrain.u16", prepared.terrain),
        ("water.u16", prepared.water),
        ("preconstruction-terrain.u16", prepared.preconstruction_terrain),
        ("preconstruction-water.u16", prepared.preconstruction_water),
    ]:
        native(np.flipud(grid)).tofile(output / name)
    (output / "hydrology.json").write_text(json.dumps(prepared.hydro, indent=2) + "\n")
    package = output / (prepared.hydro["map_id"] + ".crp")

    def pack():
        return write_map(
            ROOT / "templates/native-corridors.crp",
            layout_path,
            output / "terrain.u16",
            output / "water.u16",
            output / "hydrology.json",
            package,
        )

    result = pack()
    admission = admit(
        output,
        output / "source-input.png",
        output / "geometry.json",
        output / "source-banks.f32",
    )
    if admission["applied"]:
        result = pack()
    resources = None
    if landcover is not None:
        from paint import paint

        resources = paint(
            output,
            output / "source-landcover.u8.gz",
            output,
            output / "geometry.json",
            output / "source-evidence.json" if evidence else None,
            knobs,
        )
        result = resources["package"]
    final_check = validate_package(output)
    hydro = json.loads((output / "hydrology.json").read_text())
    probes = probes_for(hydro, layout)
    probes["points"].extend(
        {
            "name": f"engineered-storage:{i}",
            "x": source["position"][0],
            "z": source["position"][2],
            "required": True,
        }
        for i, source in enumerate(hydro["sources"])
        if source.get("class") == "reservoir"
    )
    probes["reference_water"] = "water.u16"
    geographic_river_probes(probes, data)
    mapped_water_reference(probes, data, output)
    probes["new_game_panel"] = panel_expectations(package)
    world_references(probes, data)
    (output / "probes.json").write_text(json.dumps(probes, indent=2) + "\n")
    source_files = [
        "closed_storage_candidate.py",
        "reservoir_basin.py",
        "region.py",
        "prepare.py",
        "surface_water.py",
        "wet_reach_admission.py",
        "native-water-admission.json",
        "paint.py",
        "resources.py",
        "crp.py",
        "soak.py",
        "templates/native-corridors.crp",
        "templates/native-corridors.json",
    ]
    receipt = {
        "schema": "polli.closed-storage-development-candidate/1",
        "policy": POLICY,
        "status": "prepared_not_native_qualified",
        "stable_water_promise": "unknown",
        "preparation": {
            k: value
            for k, value in hydro.items()
            if k not in {"samples", "sources", "node_positions", "rivers"}
        },
        "package": result,
        "final_static_check": final_check,
        "native_admission": admission,
        "source": {
            "inputs_sha256": {
                name: hashlib.sha256(raw).hexdigest() for name, raw in frozen.items()
            },
            "files_sha256": {name: sha(ROOT / name) for name in source_files},
        },
        "physical_files_sha256": {
            name: sha(output / name)
            for name in [
                package.name,
                "terrain.u16",
                "water.u16",
                "hydrology.json",
                "probes.json",
                "mapped-water.u8",
                "preconstruction-terrain.u16",
                "preconstruction-water.u16",
            ]
        },
        "in_game_verified": False,
        "limits": [
            "New source-prepared development candidate; not a matched source-only ablation.",
            "Natural-feature primary inventory/evaluator and nine-square nonregression remain unfinished.",
            "Final rendered-floor geometry is not an actual native hydraulic-floor or retention observation.",
        ],
    }
    if resources is not None:
        receipt["resource_plan"] = {
            "file": "plan.npz",
            "sha256": sha(output / "plan.npz"),
        }
    (output / "generation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("png", "geometry", "banks", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--landcover", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument(
        "--knobs", type=Path, help="Captured resource report with a knobs object"
    )
    args = vars(parser.parse_args())
    knobs_path = args.pop("knobs")
    args["knobs"] = (
        Knobs(**json.loads(knobs_path.read_text())["knobs"]) if knobs_path else None
    )
    print(json.dumps(export(**args), indent=2))
