"""Freeze complete maintained-water probes before new native observations.

This creates a fresh protocol, never updates earlier packages, plans or verdicts.
Passing measured checks cannot supply missing loaded-runtime or product acceptance.
"""

import argparse
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np

from closed_storage_candidate import ROOT
from closed_storage_observation import VALIDATORS, candidate_identity
from crp import read_package
from maintained_water_inventory import (
    COMPILER_FILES,
    compile_inventory,
    feature_outcome,
    initial_natural_checks,
    sha,
)
from run_water_panel import validate
from water_development_result import read_samples, verify_loaded_sources
from water_diagnostics import decode_water
from water_risk_corpus import native_outcome


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def stage(folder, output):
    if output.exists():
        raise ValueError("Use a fresh maintained-water protocol directory")
    generation = candidate_identity(folder)
    old_plan = json.loads((folder / "native-plan.json").read_text())
    if sha(folder / "generation.json") != old_plan["generation_sha256"]:
        raise ValueError("Candidate generation differs from frozen native plan")
    inventory = compile_inventory(
        json.loads((folder / "geometry.json").read_text()),
        json.loads((folder / "hydrology.json").read_text()),
    )
    probes = json.loads((folder / "probes.json").read_text())
    names = {p["name"] for p in probes["points"]}
    if names.intersection(p["name"] for p in inventory["points"]):
        raise ValueError("Maintained probes already present")
    probes["points"].extend(inventory["points"])
    files = set(generation["physical_files_sha256"]) | {
        "geometry.json",
        "hydrology.json",
        "generation.json",
    }
    sources = (
        set(COMPILER_FILES)
        | set(VALIDATORS)
        | set(generation["source"]["files_sha256"])
        | {"maintained_water_plan.py"}
    )
    compiler_hashes = {name: sha(ROOT / name) for name in sorted(sources)}
    output.mkdir(parents=True)
    for name in sorted(files - {"probes.json"}):
        shutil.copyfile(folder / name, output / name)
    write(output / "inventory.json", inventory)
    write(
        output / "authored-initialization.json",
        initial_natural_checks(
            inventory, np.fromfile(folder / "water.u16", "<u2").reshape(1081, 1081)
        ),
    )
    write(output / "probes.json", probes)
    files |= {"inventory.json", "authored-initialization.json", "probes.json"}
    plan = {
        "schema": "polli.maintained-water-native-plan/1",
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "compiler_sources_sha256": compiler_hashes,
        "definition_sha256": inventory["definition_sha256"],
        "previous_candidate_plan_sha256": sha(folder / "native-plan.json"),
        "item": {
            "slug": folder.name,
            "package": old_plan["item"]["package"],
            "files_sha256": {name: sha(output / name) for name in sorted(files)},
        },
        "harness_source": old_plan["harness_source"],
        "mod_sha256": old_plan["mod_sha256"],
        "thresholds": old_plan["thresholds"],
        "stable_water_promise": "unknown",
        "qualification": "Fresh feature protocol; not a historical rescore. Old runtime lacks full loaded-assembly identity; no product promise.",
    }
    write(output / "native-plan.json", plan)
    return {
        "plan_sha256": sha(output / "native-plan.json"),
        "coverage_complete": inventory["coverage_complete"],
        "entries": len(inventory["entries"]),
        "new_probes": len(inventory["points"]),
    }


def preflight(folder):
    plan = json.loads((folder / "native-plan.json").read_text())
    if plan["schema"] != "polli.maintained-water-native-plan/1":
        raise ValueError("Not a maintained-water native plan")
    for name, expected in plan["compiler_sources_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Compiler or validator changed: {name}")
    for name, expected in plan["item"]["files_sha256"].items():
        if sha(folder / name) != expected:
            raise ValueError(f"Frozen maintained-water input changed: {name}")
    inventory = json.loads((folder / "inventory.json").read_text())
    expected = compile_inventory(
        json.loads((folder / "geometry.json").read_text()),
        json.loads((folder / "hydrology.json").read_text()),
    )
    if (
        inventory != expected
        or plan["definition_sha256"] != inventory["definition_sha256"]
    ):
        raise ValueError("Inventory is not the frozen source-only compilation")
    points = {
        p["name"]: p for p in json.loads((folder / "probes.json").read_text())["points"]
    }
    if any(points.get(p["name"]) != p for p in inventory["points"]):
        raise ValueError("Native probes omit or alter an inventory contract")
    initial = initial_natural_checks(
        inventory, np.fromfile(folder / "water.u16", "<u2").reshape(1081, 1081)
    )
    if json.loads((folder / "authored-initialization.json").read_text()) != initial:
        raise ValueError("Authored initialization diagnostic changed")
    return plan, inventory


def collect(folder, native):
    plan, inventory = preflight(folder)
    report = validate(plan["item"], folder, native, plan["harness_source"])
    verdict = json.loads((native / "verdict.json").read_text())
    if (
        report["session"]["mod_sha256"] != plan["mod_sha256"]
        or verdict["thresholds"] != plan["thresholds"]
    ):
        raise ValueError("Native mod or original thresholds differ from frozen plan")
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
    features = feature_outcome(inventory, report, samples)
    comparator = native_outcome(report, verdict)
    flood = comparator["labels"]["flood"]
    status = (
        "fail"
        if features["status"] == "fail" or flood is True
        else "pass"
        if features["status"] == "pass" and flood is False
        else "unknown"
    )
    return {
        "schema": "polli.maintained-water-development-observation/1",
        "native_plan_sha256": sha(folder / "native-plan.json"),
        "definition_sha256": plan["definition_sha256"],
        "sampled_water_checks_status": status,
        "maintained_water_status": "fail" if status == "fail" else "unknown",
        "stable_water_promise": "unknown",
        "features": features,
        "water_outcome_original_definition": comparator,
        "original_required_gates": [
            c
            for c in verdict["checks"]
            if c["name"] in {"probes_wet_end", "probes_wet_throughout"}
        ],
        "loaded_source_readback": controls,
        "native_failed_checks": [
            c["name"] for c in verdict["checks"] if c["status"] == "fail"
        ],
        "native_files_sha256": {
            name: sha(native / name)
            for name in (
                "report.json",
                "verdict.json",
                "harness-source.json",
                "timeline.jsonl",
                "probes.json",
                "mapped-water.u8",
                "reference-water.u16",
            )
        },
        "cleanup": report["session"]["cleanup"],
        "runtime_loaded_assembly_qualification": "unverified by old protocol; no holdout-backed promise",
        "scope": "Sampled empty-map water only. Continuing floors, terrain/start/connection gates, populated demand, long-term and human acceptance remain separate.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("stage")
    prepare.add_argument("folder", type=Path)
    prepare.add_argument("output", type=Path)
    check = sub.add_parser("preflight")
    check.add_argument("folder", type=Path)
    result = sub.add_parser("collect")
    result.add_argument("folder", type=Path)
    result.add_argument("native", type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    if command == "preflight":
        preflight(**args)
        output = {"status": "inputs_and_compiler_unchanged"}
    else:
        output = (stage if command == "stage" else collect)(**args)
    print(json.dumps(output, indent=2, allow_nan=False))
