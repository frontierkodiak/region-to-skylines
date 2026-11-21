"""Freeze and collect new passive-natural-storage development observations."""

import argparse
import json
from pathlib import Path

import numpy as np

from closed_storage_candidate import ROOT, sha
from closed_storage_observation import VALIDATORS
from crp import read_package
from maintained_water_inventory import feature_outcome
from natural_basins import lake_components, validate_basin
from natural_storage_candidate import identity, write
from natural_water_inventory import compile_natural_inventory
from reservoir_basin import validate_native_basin
from run_water_panel import validate
from water_development_result import read_samples, verify_loaded_sources
from water_diagnostics import decode_water
from water_risk_corpus import native_outcome

DEFINITION = (
    ROOT / "calibration/pl1191-construction-v1/maintained-water-definition.json"
)
EXTRA = [
    "natural_storage_observation.py",
    "natural_storage_candidate.py",
    "natural_basins.py",
    "natural_water_inventory.py",
    "maintained_water_inventory.py",
]


def preflight(folder):
    generation = identity(folder)
    plan = json.loads((folder / "native-plan.json").read_text())
    if (
        plan["schema"] != "polli.passive-natural-storage-native-plan/1"
        or sha(folder / "generation.json") != plan["generation_sha256"]
    ):
        raise ValueError("Wrong natural generation or native plan")
    if (
        plan["item"]["files_sha256"] != generation["physical_files_sha256"]
        or sha(DEFINITION) != plan["definition_sha256"]
    ):
        raise ValueError("Natural observation inputs/definition changed")
    for name, digest in plan["validators_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"Natural observation validator changed: {name}")
    inventory = json.loads((folder / "inventory.json").read_text())
    expected = compile_natural_inventory(
        json.loads((folder / "geometry.json").read_text()),
        json.loads((folder / "hydrology.json").read_text()),
        json.loads((folder / "natural-plan.json").read_text()),
    )
    if inventory != expected:
        raise ValueError("Natural inventory no longer matches source-only compilation")
    probes = {
        p["name"]: p for p in json.loads((folder / "probes.json").read_text())["points"]
    }
    if any(probes.get(p["name"]) != p for p in inventory["points"]):
        raise ValueError("Natural native cohort omits an inventory contract")
    return plan, inventory


def freeze(folder, protocol):
    path = folder / "native-plan.json"
    if path.exists():
        raise ValueError("Do not overwrite a frozen natural native plan")
    generation = identity(folder)
    old = json.loads(protocol.read_text())
    if old["schema"] != "polli.closed-storage-native-plan/1":
        raise ValueError("Expected the pinned historical development runtime protocol")
    if not generation["final_static_check"]["natural_bodies"]:
        raise ValueError("No constructed natural body to observe")
    inventory = json.loads((folder / "inventory.json").read_text())
    names = set(generation["source_files_sha256"]) | set(VALIDATORS) | set(EXTRA)
    plan = {
        "schema": "polli.passive-natural-storage-native-plan/1",
        "generation_sha256": sha(folder / "generation.json"),
        "definition_sha256": inventory["definition_sha256"],
        "harness_source": old["harness_source"],
        "mod_sha256": old["mod_sha256"],
        "thresholds": old["thresholds"],
        "previous_protocol_sha256": sha(protocol),
        "item": {
            "slug": folder.name,
            "package": Path(generation["package"]["output"]).name,
            "files_sha256": generation["physical_files_sha256"],
        },
        "validators_sha256": {name: sha(ROOT / name) for name in sorted(names)},
        "stable_water_promise": "unknown",
        "qualification": "Development only; incomplete natural support, old loaded-assembly limitation, no product promise",
    }
    write(path, plan)
    preflight(folder)
    return {
        "plan_sha256": sha(path),
        "package_sha256": generation["final_static_check"]["package_sha256"],
    }


def collect(folder, native):
    plan, inventory = preflight(folder)
    report = validate(plan["item"], folder, native, plan["harness_source"])
    verdict = json.loads((native / "verdict.json").read_text())
    if (
        report["session"]["mod_sha256"] != plan["mod_sha256"]
        or verdict["thresholds"] != plan["thresholds"]
    ):
        raise ValueError("Natural runtime or original thresholds changed")
    samples = read_samples(native)
    package = folder / plan["item"]["package"]
    decoded = decode_water(
        next(
            a["payload"]
            for a in read_package(package.read_bytes())[1]
            if a["kind"] == 52
        )
    )
    controls = verify_loaded_sources(samples, decoded["sources"])
    hydro = json.loads((folder / "hydrology.json").read_text())
    construction = json.loads((folder / "natural-plan.json").read_text())
    components, _ = lake_components(json.loads((folder / "geometry.json").read_text()))
    floors = []
    for row in samples:
        path = native / "grids" / (row["label"] + "-water-ground.u16")
        if not path.exists():
            floors.append(
                {
                    "label": row["label"],
                    "status": "unknown",
                    "reason": "actual native hydraulic floor not captured",
                }
            )
            continue
        floor = np.flipud(np.fromfile(path, "<u2").reshape(1081, 1081)) / 64
        checks = []
        for body in construction["bodies"]:
            if body["status"] != "constructed":
                continue
            check = {"id": body["id"]}
            try:
                check.update(
                    status="pass",
                    geometry=validate_basin(
                        floor, components[body["id"]][0], body["target_m"]
                    ),
                )
            except ValueError as error:
                check.update(status="fail", reason=str(error))
            checks.append(check)
        for index, source in enumerate(hydro["sources"]):
            if source.get("class") != "reservoir":
                continue
            check = {"id": f"starter:{index}"}
            try:
                check.update(
                    status="pass",
                    geometry=validate_native_basin(floor, decoded["sources"][index]),
                )
            except ValueError as error:
                check.update(status="fail", reason=str(error))
            checks.append(check)
        floors.append(
            {
                "label": row["label"],
                "sha256": sha(path),
                "status": "fail"
                if any(c["status"] == "fail" for c in checks)
                else "pass",
                "checks": checks,
            }
        )
    features = feature_outcome(inventory, report, samples)
    original = native_outcome(report, verdict)
    failure = (
        features["status"] == "fail"
        or original["labels"]["flood"] is True
        or any(f["status"] == "fail" for f in floors)
    )
    return {
        "schema": "polli.passive-natural-storage-development-observation/1",
        "plan_sha256": sha(folder / "native-plan.json"),
        "game_minutes": report["game_minutes"],
        "maintained_water_status": "fail" if failure else "unknown",
        "stable_water_promise": "unknown",
        "features": features,
        "water_outcome_original_definition": original,
        "loaded_source_readback": controls,
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
        "runtime_identity": "Old protocol binds harness/mod, not full loaded-assembly identity. No historical identity retrofit or qualification.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("preflight")
    check.add_argument("folder", type=Path)
    prepare = commands.add_parser("freeze")
    prepare.add_argument("folder", type=Path)
    prepare.add_argument("protocol", type=Path)
    result = commands.add_parser("collect")
    result.add_argument("folder", type=Path)
    result.add_argument("native", type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    if command == "preflight":
        preflight(**args)
        obj = {"status": "inputs_and_protocol_unchanged"}
    else:
        obj = (freeze if command == "freeze" else collect)(**args)
    print(json.dumps(obj, indent=2))
