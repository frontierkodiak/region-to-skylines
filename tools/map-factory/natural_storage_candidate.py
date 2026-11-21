"""Fresh experimental passive natural-body construction; shipping stays unchanged."""

import argparse
import json
from pathlib import Path
import shutil

import numpy as np

from closed_storage_candidate import ROOT, export as export_base, native, sha
from closed_storage_observation import candidate_identity
from crp import N, decode_u16, read_package, write_map
from maintained_water_inventory import initial_natural_checks
from natural_basins import (
    POLICY,
    construct,
    lake_components,
    protection,
    validate_final,
)
from natural_water_inventory import compile_natural_inventory
from paint import paint
from reservoir_basin import validate_native_basin
from soak import panel_expectations
from template import manager_tag
from water_diagnostics import bind_sources, decode_water

NEW_SOURCES = [
    "natural_basins.py",
    "natural_water_inventory.py",
    "natural_storage_candidate.py",
    "maintained_water_inventory.py",
    "maintained_water.py",
    "osm_highways.py",
    "pyproject.toml",
    "uv.lock",
]


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def grid(path):
    return np.flipud(np.fromfile(path, "<u2").reshape(1081, 1081)) / 64


def validate_package(folder):
    base = folder / "base"
    candidate_identity(base)
    hydro = json.loads((folder / "hydrology.json").read_text())
    geometry = json.loads((folder / "geometry.json").read_text())
    plan = json.loads((folder / "natural-plan.json").read_text())
    old = json.loads((base / "hydrology.json").read_text())
    if (
        hydro["sources"] != old["sources"]
        or hydro["node_positions"] != old["node_positions"]
        or hydro["start_area"] != old["start_area"]
    ):
        raise ValueError(
            "Natural construction changed existing controls, networks or start"
        )
    expected = [e for e in plan["bodies"] if e["status"] == "constructed"]
    if hydro["maintained_features"] != expected:
        raise ValueError("Authored natural anchors differ from construction plan")
    components, source = lake_components(geometry)
    if source != plan["source_features"]:
        raise ValueError("Natural source feature accounting changed")
    original_t, original_w = grid(base / "terrain.u16"), grid(base / "water.u16")
    protected = protection(
        geometry,
        old,
        json.loads((ROOT / "templates/native-corridors.json").read_text()),
    )
    replay = construct(original_t, original_w, components, protected)
    if replay.entries != plan["bodies"]:
        raise ValueError("Natural plan differs from bounded source-only construction")
    floor, water = grid(folder / "terrain.u16"), grid(folder / "water.u16")
    checks = validate_final(
        original_t, original_w, floor, water, replay.masks, plan["bodies"], protected
    )
    package = folder / (hydro["map_id"] + ".crp")
    payload = next(
        a["payload"] for a in read_package(package.read_bytes())[1] if a["kind"] == 52
    )
    decoded = decode_water(payload)
    bind_sources(decoded, hydro)
    if decoded["depth"].astype("<u2").tobytes() != (folder / "water.u16").read_bytes():
        raise ValueError("Final package water differs from authored depth grid")
    tag = manager_tag("TerrainManager")
    encoded, offset = decode_u16(payload, N, payload.index(tag) + len(tag))
    delta, _ = decode_u16(payload, int((encoded != 0).sum()), offset)
    if (
        encoded.astype("<u2").tobytes() != (folder / "terrain.u16").read_bytes()
        or delta.any()
    ):
        raise ValueError("Final package terrain differs from bounded static floor")
    starter = [
        validate_native_basin(floor, decoded["sources"][index])
        for index, s in enumerate(hydro["sources"])
        if s.get("class") == "reservoir"
    ]
    return {
        "package_sha256": sha(package),
        "natural_bodies": checks,
        "starter_checks": starter,
        "qualification": "static rendered-floor geometry only; native hydraulic floor/retention unverified",
    }


def export(source, output):
    if output.exists():
        raise ValueError("Use a fresh natural-storage candidate directory")
    output.mkdir(parents=True)
    base = output / "base"
    original = export_base(
        source / "source-input.png",
        source / "geometry.json",
        source / "source-banks.f32",
        base,
        landcover=source / "source-landcover.u8.gz"
        if (source / "source-landcover.u8.gz").exists()
        else None,
        evidence=source / "source-evidence.json"
        if (source / "source-evidence.json").exists()
        else None,
    )
    for name in (
        "geometry.json",
        "terrain.u16",
        "water.u16",
        "hydrology.json",
        "mapped-water.u8",
    ):
        shutil.copyfile(base / name, output / name)
    geometry = json.loads((output / "geometry.json").read_text())
    hydro = json.loads((output / "hydrology.json").read_text())
    components, entries = lake_components(geometry)
    result = construct(
        grid(base / "terrain.u16"),
        grid(base / "water.u16"),
        components,
        protection(
            geometry,
            hydro,
            json.loads((ROOT / "templates/native-corridors.json").read_text()),
        ),
    )
    plan = {
        "policy": POLICY,
        "source_features": entries,
        "bodies": result.entries,
        "stable_water_promise": "unknown",
    }
    write(output / "natural-plan.json", plan)
    native(np.flipud(result.terrain)).tofile(output / "terrain.u16")
    native(np.flipud(result.water)).tofile(output / "water.u16")
    hydro["map_id"] = "PL1191-" + geometry["sq"]["slug"] + "-natural-storage"
    hydro["map_name"] = geometry["sq"]["name"] + " - Experimental natural storage"
    hydro["maintained_features"] = [
        e for e in result.entries if e["status"] == "constructed"
    ]
    hydro["natural_storage_policy"] = POLICY
    write(output / "hydrology.json", hydro)
    package = output / (hydro["map_id"] + ".crp")
    packed = write_map(
        ROOT / "templates/native-corridors.crp",
        ROOT / "templates/native-corridors.json",
        output / "terrain.u16",
        output / "water.u16",
        output / "hydrology.json",
        package,
    )
    if (base / "source-landcover.u8.gz").exists():
        packed = paint(
            output,
            base / "source-landcover.u8.gz",
            output,
            output / "geometry.json",
            base / "source-evidence.json"
            if (base / "source-evidence.json").exists()
            else None,
        )["package"]
    inventory = compile_natural_inventory(geometry, hydro, plan)
    write(output / "inventory.json", inventory)
    write(
        output / "authored-initialization.json",
        initial_natural_checks(
            inventory, np.fromfile(output / "water.u16", "<u2").reshape(1081, 1081)
        ),
    )
    probes = json.loads((base / "probes.json").read_text())
    probes["points"].extend(inventory["points"])
    probes["new_game_panel"] = panel_expectations(package)
    # Reference/mapped-mask paths stay relative to these exact new grids.
    write(output / "probes.json", probes)
    final = validate_package(output)
    names = [
        package.name,
        "terrain.u16",
        "water.u16",
        "geometry.json",
        "hydrology.json",
        "mapped-water.u8",
        "probes.json",
        "inventory.json",
        "authored-initialization.json",
        "natural-plan.json",
    ]
    receipt = {
        "schema": "polli.natural-storage-development-candidate/1",
        "policy": POLICY,
        "status": "prepared_not_native_qualified",
        "stable_water_promise": "unknown",
        "base_generation_sha256": sha(base / "generation.json"),
        "source_files_sha256": {
            name: sha(ROOT / name)
            for name in sorted(
                set(original["source"]["files_sha256"]) | set(NEW_SOURCES)
            )
        },
        "physical_files_sha256": {name: sha(output / name) for name in names},
        "package": packed,
        "final_static_check": final,
        "limits": "Passive captured-lake subset only; no new source forcing, flowing waterways unsupported, no inherited admission/terrain/native qualification.",
    }
    write(output / "generation.json", receipt)
    return receipt


def identity(folder):
    receipt = json.loads((folder / "generation.json").read_text())
    if (
        receipt["schema"] != "polli.natural-storage-development-candidate/1"
        or receipt["stable_water_promise"] != "unknown"
    ):
        raise ValueError("Expected an unqualified natural-storage candidate")
    for name, digest in receipt["source_files_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"Natural candidate writer changed: {name}")
    for name, digest in receipt["physical_files_sha256"].items():
        if sha(folder / name) != digest:
            raise ValueError(f"Frozen natural candidate changed: {name}")
    if (
        sha(folder / "base/generation.json") != receipt["base_generation_sha256"]
        or validate_package(folder) != receipt["final_static_check"]
    ):
        raise ValueError("Natural candidate no longer matches bounded preparation")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    print(json.dumps(export(**vars(parser.parse_args())), indent=2))
