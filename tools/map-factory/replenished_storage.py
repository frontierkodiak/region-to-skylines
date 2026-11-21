"""Experimental node-local lake regulation on an immutable passive candidate.

Only WaterSimulation controls and its metadata assetRef may change. Encoded
rates are a bounded experimental setting, not measured physical flux units.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

from closed_storage_candidate import ROOT, sha
from closed_storage_observation import VALIDATORS
from crp import patch_metadata, read_package, water_payload, write_package
from maintained_water_inventory import feature_outcome
from natural_basins import lake_components, validate_basin
from natural_storage_candidate import grid, identity as passive_identity, write
from natural_storage_observation import DEFINITION, EXTRA
from natural_water_inventory import compile_natural_inventory
from reservoir_basin import validate_native_basin
from run_water_panel import validate
from soak import panel_expectations
from water_development_result import read_samples, verify_loaded_sources
from water_diagnostics import bind_sources, decode_water, encoded_sources
from water_risk_corpus import native_outcome

POLICY = "node-local-mapped-lake-regulation-v1"
RATE = 128
FIXED = [
    "terrain.u16",
    "water.u16",
    "geometry.json",
    "mapped-water.u8",
    "natural-plan.json",
    "authored-initialization.json",
]


def controls(geometry, construction, floor):
    # At rate128 the existing native-node footprint model has radius14.525m,
    # strictly below the16m neighbour spacing. Never enlarge its footprint.
    radius = float(10 + 0.4 * np.sqrt(RATE))
    if not 0 < RATE <= 224 or not radius < 16:
        raise ValueError("Node-local rate footprint would reach another node")
    components, _ = lake_components(geometry)
    sources, bodies = [], []
    for body in construction["bodies"]:
        if body["status"] != "constructed":
            continue
        mask = components[body["id"]][0]
        check = validate_basin(floor, mask, body["target_m"])
        first = len(sources)
        for row, col in zip(*np.nonzero(mask)):
            sources.append(
                {
                    "name": body["id"] + f":node:{row}:{col}",
                    "class": "lake",
                    "role": "bounded_node_regulation",
                    "body_id": body["id"],
                    "feature_ids": body["feature_ids"],
                    "position": [int(col * 16 - 8640), 0, int(8640 - row * 16)],
                    "target": body["target_m"],
                    "capacity": RATE / 65535,
                    "output_capacity": RATE / 65535,
                }
            )
        bodies.append(
            {
                "id": body["id"],
                "control_first": first,
                "control_count": len(sources) - first,
                "static_geometry": check,
            }
        )
    return {
        "policy": POLICY,
        "encoded_rate_per_direction_per_node": RATE,
        "radius_model_m": radius,
        "native_footprint_nodes_per_control": 1,
        "sources": sources,
        "bodies": bodies,
        "sum_encoded_rates_per_direction": len(sources) * RATE,
        "physical_flux_units": "unknown; not an evaporation or demand budget",
    }


def patch(source, hydro, additions):
    package, assets = read_package(source)
    simulation = next(a for a in assets if a["kind"] == 52)
    original = simulation["payload"]
    decoded = decode_water(original)
    bind_sources(decoded, hydro)
    if len(decoded["sources"]) + len(additions) > 65535:
        raise ValueError("Native source-count bound exceeded")
    replacement = (
        decoded["tag"]
        + water_payload(
            decoded["depth"],
            encoded_sources(decoded) + additions,
            decoded["frame"],
            decoded["sea_level_m"],
        )
        + decoded["tail"]
    )
    updated = original[: decoded["start"]] + replacement + original[decoded["end"] :]
    simulation["payload"] = updated
    old_ref, new_ref = (
        hashlib.md5(original).hexdigest(),
        hashlib.md5(updated).hexdigest(),
    )
    for asset in assets:
        if asset["kind"] == 100:
            old = asset["payload"]
            asset["payload"] = patch_metadata(old, new_ref)
            if patch_metadata(asset["payload"], old_ref) != old:
                raise ValueError("Metadata changed outside simulation reference")
    return write_package(package, assets)


def export(source, output):
    if output.exists():
        raise ValueError("Use a fresh replenishment candidate directory")
    parent = passive_identity(source)
    output.mkdir(parents=True)
    shutil.copytree(source, output / "parent")
    for name in FIXED:
        shutil.copyfile(source / name, output / name)
    hydro = json.loads((source / "hydrology.json").read_text())
    rule = controls(
        json.loads((source / "geometry.json").read_text()),
        json.loads((source / "natural-plan.json").read_text()),
        grid(source / "terrain.u16"),
    )
    original = source / Path(parent["package"]["output"]).name
    package = output / (hydro["map_id"] + "-regulated.crp")
    package.write_bytes(patch(original.read_bytes(), hydro, rule["sources"]))
    hydro["sources"].extend(rule["sources"])
    write(output / "hydrology.json", hydro)
    write(
        output / "inventory.json",
        compile_natural_inventory(
            json.loads((source / "geometry.json").read_text()),
            hydro,
            json.loads((source / "natural-plan.json").read_text()),
        ),
    )
    write(output / "regulation.json", rule)
    probes = json.loads((source / "probes.json").read_text())
    probes["new_game_panel"] = panel_expectations(package)
    write(output / "probes.json", probes)
    names = FIXED + [
        "inventory.json",
        "hydrology.json",
        "regulation.json",
        "probes.json",
        package.name,
    ]
    names_source = (
        set(parent["source_files_sha256"])
        | set(VALIDATORS)
        | set(EXTRA)
        | {"replenished_storage.py"}
    )
    generation = {
        "schema": "polli.replenished-natural-storage-candidate/1",
        "policy": POLICY,
        "stable_water_promise": "unknown",
        "package": package.name,
        "parent_generation_sha256": sha(output / "parent/generation.json"),
        "physical_files_sha256": {name: sha(output / name) for name in names},
        "source_files_sha256": {
            name: sha(ROOT / name) for name in sorted(names_source)
        },
    }
    write(output / "generation.json", generation)
    identity(output)
    return generation


def identity(folder):
    generation = json.loads((folder / "generation.json").read_text())
    if (
        generation["schema"] != "polli.replenished-natural-storage-candidate/1"
        or generation["policy"] != POLICY
        or generation["stable_water_promise"] != "unknown"
    ):
        raise ValueError("Wrong replenishment generation")
    for name, digest in generation["source_files_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"Replenishment writer/validator changed: {name}")
    for name, digest in generation["physical_files_sha256"].items():
        if sha(folder / name) != digest:
            raise ValueError(f"Replenishment physical input changed: {name}")
    parent = folder / "parent"
    old = passive_identity(parent)
    if sha(parent / "generation.json") != generation["parent_generation_sha256"]:
        raise ValueError("Passive parent generation changed")
    for name in FIXED:
        if (parent / name).read_bytes() != (folder / name).read_bytes():
            raise ValueError(f"Source-only intervention changed {name}")
    geometry = json.loads((folder / "geometry.json").read_text())
    construction = json.loads((folder / "natural-plan.json").read_text())
    rule = controls(geometry, construction, grid(folder / "terrain.u16"))
    if json.loads((folder / "regulation.json").read_text()) != rule:
        raise ValueError("Declared controls differ from general node-local rule")
    original_hydro = json.loads((parent / "hydrology.json").read_text())
    hydro = copy.deepcopy(original_hydro)
    hydro["sources"].extend(rule["sources"])
    if json.loads((folder / "hydrology.json").read_text()) != hydro:
        raise ValueError("Existing hydrology or controls changed")
    if compile_natural_inventory(geometry, hydro, construction) != json.loads(
        (folder / "inventory.json").read_text()
    ):
        raise ValueError("Natural inventory differs from full source compilation")
    package = folder / generation["package"]
    original = parent / Path(old["package"]["output"]).name
    if package.read_bytes() != patch(
        original.read_bytes(), original_hydro, rule["sources"]
    ):
        raise ValueError(
            "Package changed beyond declared WaterSimulation control addition"
        )
    decoded = decode_water(
        next(
            a["payload"]
            for a in read_package(package.read_bytes())[1]
            if a["kind"] == 52
        )
    )
    bind_sources(decoded, hydro)
    probes = json.loads((parent / "probes.json").read_text())
    probes["new_game_panel"] = panel_expectations(package)
    if probes != json.loads((folder / "probes.json").read_text()):
        raise ValueError("Matched probe cohort/reference changed")
    return generation


def freeze(folder, protocol):
    if (folder / "native-plan.json").exists():
        raise ValueError("Do not overwrite a native plan")
    generation = identity(folder)
    if not json.loads((folder / "regulation.json").read_text())["sources"]:
        raise ValueError("No new constructed-body control to observe")
    old = json.loads(protocol.read_text())
    if old["schema"] not in {
        "polli.closed-storage-native-plan/1",
        "polli.passive-natural-storage-native-plan/1",
    }:
        raise ValueError("Expected explicit pinned development runtime protocol")
    plan = {
        "schema": "polli.replenished-natural-storage-native-plan/1",
        "generation_sha256": sha(folder / "generation.json"),
        "definition_sha256": sha(DEFINITION),
        "harness_source": old["harness_source"],
        "mod_sha256": old["mod_sha256"],
        "thresholds": old["thresholds"],
        "previous_protocol_sha256": sha(protocol),
        "validators_sha256": generation["source_files_sha256"],
        "item": {
            "slug": folder.name,
            "package": generation["package"],
            "files_sha256": generation["physical_files_sha256"],
        },
        "stable_water_promise": "unknown",
        "physical_flux_budget": "unknown",
    }
    write(folder / "native-plan.json", plan)
    preflight(folder)
    return {
        "plan_sha256": sha(folder / "native-plan.json"),
        "package_sha256": sha(folder / generation["package"]),
    }


def preflight(folder):
    generation = identity(folder)
    plan = json.loads((folder / "native-plan.json").read_text())
    if (
        plan["schema"] != "polli.replenished-natural-storage-native-plan/1"
        or plan["generation_sha256"] != sha(folder / "generation.json")
        or plan["definition_sha256"] != sha(DEFINITION)
        or plan["item"]["package"] != generation["package"]
        or plan["item"]["files_sha256"] != generation["physical_files_sha256"]
        or plan["validators_sha256"] != generation["source_files_sha256"]
    ):
        raise ValueError("Replenishment protocol binding changed")
    inventory = json.loads((folder / "inventory.json").read_text())
    probes = {
        p["name"]: p for p in json.loads((folder / "probes.json").read_text())["points"]
    }
    if inventory["definition_sha256"] != plan["definition_sha256"] or any(
        probes.get(p["name"]) != p for p in inventory["points"]
    ):
        raise ValueError("Frozen cohort omits a mandatory contract")
    return plan, inventory


def collect(folder, native):
    plan, inventory = preflight(folder)
    report = validate(plan["item"], folder, native, plan["harness_source"])
    verdict = json.loads((native / "verdict.json").read_text())
    if (
        report["session"]["mod_sha256"] != plan["mod_sha256"]
        or verdict["thresholds"] != plan["thresholds"]
    ):
        raise ValueError("Runtime or original thresholds differ from plan")
    samples = read_samples(native)
    decoded = decode_water(
        next(
            a["payload"]
            for a in read_package((folder / plan["item"]["package"]).read_bytes())[1]
            if a["kind"] == 52
        )
    )
    readback = verify_loaded_sources(samples, decoded["sources"])
    geometry = json.loads((folder / "geometry.json").read_text())
    construction = json.loads((folder / "natural-plan.json").read_text())
    hydro = json.loads((folder / "hydrology.json").read_text())
    floors = []
    for sample in samples:
        path = native / "grids" / (sample["label"] + "-water-ground.u16")
        if not path.exists():
            floors.append(
                {
                    "label": sample["label"],
                    "status": "unknown",
                    "reason": "actual hydraulic floor not captured",
                }
            )
            continue
        floor = grid(path)
        try:
            body_checks = controls(geometry, construction, floor)["bodies"]
            starter = [
                validate_native_basin(floor, decoded["sources"][i])
                for i, s in enumerate(hydro["sources"])
                if s.get("class") == "reservoir"
            ]
            floors.append(
                {
                    "label": sample["label"],
                    "status": "pass",
                    "sha256": sha(path),
                    "static_authored_stage_checks": body_checks,
                    "starter_checks": starter,
                }
            )
        except ValueError as error:
            floors.append(
                {
                    "label": sample["label"],
                    "status": "fail",
                    "reason": str(error),
                    "sha256": sha(path),
                }
            )
    features = feature_outcome(inventory, report, samples)
    original = native_outcome(report, verdict)
    failed = (
        features["status"] == "fail"
        or original["labels"]["flood"] is True
        or any(f["status"] == "fail" for f in floors)
    )
    return {
        "schema": "polli.replenished-natural-storage-observation/1",
        "plan_sha256": sha(folder / "native-plan.json"),
        "game_minutes": report["game_minutes"],
        "maintained_water_status": "fail" if failed else "unknown",
        "stable_water_promise": "unknown",
        "features": features,
        "water_outcome_original_definition": original,
        "loaded_source_readback": readback,
        "native_hydraulic_floor_checks": floors,
        "native_failed_checks": [
            c["name"] for c in verdict["checks"] if c["status"] == "fail"
        ],
        "cleanup": report["session"]["cleanup"],
        "native_files_sha256": {
            name: sha(native / name)
            for name in [
                "report.json",
                "verdict.json",
                "timeline.jsonl",
                "harness-source.json",
                "probes.json",
                "mapped-water.u8",
                "reference-water.u16",
            ]
        },
        "runtime_identity": "Executable/on-disk sidecar only; not full loaded-assembly identity.",
        "physical_flux_budget": "unknown; configured rates/instantaneous flow are not integrated flux",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, arguments in [
        ("export", ["source", "output"]),
        ("freeze", ["folder", "protocol"]),
        ("preflight", ["folder"]),
        ("collect", ["folder", "native"]),
    ]:
        command = commands.add_parser(name)
        for argument in arguments:
            command.add_argument(argument, type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    result = globals()[command](**args)
    print(
        json.dumps(
            {"status": "inputs_and_protocol_unchanged"}
            if command == "preflight"
            else result,
            indent=2,
        )
    )
