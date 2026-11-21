"""Freeze and collect development observations without issuing a water promise."""

import argparse
import json
from pathlib import Path

import numpy as np

from closed_storage_candidate import ROOT, sha, validate_package
from crp import read_package
from maintained_water import storage_outcome
from reservoir_basin import validate_native_basin
from run_water_panel import validate
from water_development_result import read_samples, verify_loaded_sources
from water_diagnostics import decode_water
from water_risk_corpus import native_outcome

VALIDATORS = [
    "closed_storage_observation.py",
    "water_development_result.py",
    "run_water_panel.py",
    "maintained_water.py",
    "water_risk_corpus.py",
    "water_diagnostics.py",
    "crp.py",
    "reservoir_basin.py",
]
DEFINITION = (
    ROOT / "calibration/pl1191-construction-v1/maintained-water-definition.json"
)


def candidate_identity(folder):
    generation = json.loads((folder / "generation.json").read_text())
    if (
        generation["status"] != "prepared_not_native_qualified"
        or generation["stable_water_promise"] != "unknown"
    ):
        raise ValueError("Expected an unqualified prepared development candidate")
    for name, expected in generation["source"]["files_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Candidate writer changed: {name}")
    for binding in (
        generation["source"]["inputs_sha256"],
        generation["physical_files_sha256"],
    ):
        for name, expected in binding.items():
            if sha(folder / name) != expected:
                raise ValueError(f"Frozen candidate input changed: {name}")
    if validate_package(folder) != generation["final_static_check"]:
        raise ValueError("Final candidate geometry differs from preparation")
    return generation


def freeze(folder, baseline, plan_path, harness_source, mod_sha256):
    if plan_path.exists():
        raise ValueError("Do not overwrite a frozen native plan")
    generation = candidate_identity(folder)
    report = json.loads((baseline / "report.json").read_text())
    source = json.loads((baseline / "harness-source.json").read_text())
    verdict = json.loads((baseline / "verdict.json").read_text())
    if (
        report["game_minutes"] < 60
        or source.get("dirty") is not False
        or source["commit"] != harness_source
        or report["session"]["mod_sha256"] != mod_sha256
    ):
        raise ValueError("Baseline protocol lacks the pinned full observation")
    if not generation["final_static_check"]["static_storage_checks"]:
        raise ValueError("No constructed storage to observe")
    package = Path(generation["package"]["output"]).name
    plan = {
        "schema": "polli.closed-storage-native-plan/1",
        "generation_sha256": sha(folder / "generation.json"),
        "harness_source": harness_source,
        "mod_sha256": mod_sha256,
        "item": {
            "slug": folder.name,
            "package": package,
            "files_sha256": generation["physical_files_sha256"],
        },
        "thresholds": verdict["thresholds"],
        "baseline_protocol_sha256": {
            name: sha(baseline / name)
            for name in ("report.json", "verdict.json", "harness-source.json")
        },
        "definition_sha256": sha(DEFINITION),
        "validator_sources_sha256": {name: sha(ROOT / name) for name in VALIDATORS},
        "qualification": "Development only; not matched source-only or complete maintained-water/runtime qualification",
    }
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    return {
        "plan_sha256": sha(plan_path),
        "package": package,
        "package_sha256": plan["item"]["files_sha256"][package],
    }


def preflight(folder, plan):
    generation = candidate_identity(folder)
    if (
        plan.get("schema") != "polli.closed-storage-native-plan/1"
        or plan["item"]["files_sha256"] != generation["physical_files_sha256"]
        or plan["item"]["package"] != Path(generation["package"]["output"]).name
    ):
        raise ValueError("Native plan changes the frozen package or probe bindings")
    if (
        sha(folder / "generation.json") != plan["generation_sha256"]
        or sha(DEFINITION) != plan["definition_sha256"]
    ):
        raise ValueError(
            "Candidate generation or primary definition changed after freeze"
        )
    for name, expected in plan["validator_sources_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Observation validator changed after freeze: {name}")


def collect(folder, plan_path, native):
    plan = json.loads(plan_path.read_text())
    preflight(folder, plan)
    report = validate(plan["item"], folder, native, plan["harness_source"])
    verdict = json.loads((native / "verdict.json").read_text())
    if (
        report["session"]["mod_sha256"] != plan["mod_sha256"]
        or verdict["thresholds"] != plan["thresholds"]
    ):
        raise ValueError("Native mod bytes or original acceptance thresholds differ")
    hydro = json.loads((folder / "hydrology.json").read_text())
    package = folder / plan["item"]["package"]
    decoded = decode_water(
        next(
            a["payload"]
            for a in read_package(package.read_bytes())[1]
            if a["kind"] == 52
        )
    )
    samples = read_samples(native)
    source_readback = verify_loaded_sources(samples, decoded["sources"])
    floor_checks, cached = [], {}
    for sample in samples:
        label = sample["label"]
        path = native / "grids" / (label + "-water-ground.u16")
        if not path.is_file():
            floor_checks.append(
                {
                    "label": label,
                    "status": "unknown",
                    "reason": "missing actual native hydraulic floor",
                }
            )
            continue
        digest = sha(path)
        if digest not in cached:
            floor = np.flipud(np.fromfile(path, "<u2").reshape(1081, 1081)) / 64
            results = []
            for index, source in enumerate(hydro["sources"]):
                if source.get("class") != "reservoir":
                    continue
                row = {"source_index": index}
                try:
                    row.update(
                        status="pass",
                        geometry=validate_native_basin(
                            floor, decoded["sources"][index]
                        ),
                    )
                except ValueError as error:
                    row.update(status="fail", reason=str(error))
                results.append(row)
            cached[digest] = results
        rows = cached[digest]
        floor_checks.append(
            {
                "label": label,
                "sha256": digest,
                "status": "fail"
                if any(r["status"] == "fail" for r in rows)
                else "pass",
                "sources": rows,
            }
        )
    return {
        "schema": "polli.closed-storage-development-observation/1",
        "qualification": "Development candidate only; no complete natural-feature inventory, nine-square or holdout/runtime qualification",
        "stable_water_promise": "unknown",
        "plan_sha256": sha(plan_path),
        "definition_sha256": plan["definition_sha256"],
        "game_minutes": report["game_minutes"],
        "water_outcome_original_definition": native_outcome(report, verdict),
        "engineered_storage": storage_outcome(hydro, report, samples),
        "native_hydraulic_floor_checks": floor_checks,
        "loaded_source_readback": source_readback,
        "native_failed_checks": [
            c["name"] for c in verdict["checks"] if c["status"] == "fail"
        ],
        "cleanup": report["session"]["cleanup"],
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
        "runtime_loaded_assembly_qualification": "unverified by old protocol; never retrofitted onto historical observations",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("freeze")
    for name in ("folder", "baseline", "plan_path"):
        prepare.add_argument(name, type=Path)
    prepare.add_argument("--harness-source", required=True)
    prepare.add_argument("--mod-sha256", required=True)
    check = commands.add_parser("preflight")
    check.add_argument("folder", type=Path)
    check.add_argument("plan_path", type=Path)
    result = commands.add_parser("collect")
    for name in ("folder", "plan_path", "native"):
        result.add_argument(name, type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    if command == "freeze":
        output = freeze(**args)
    elif command == "preflight":
        preflight(args["folder"], json.loads(args["plan_path"].read_text()))
        output = {"status": "inputs_and_protocol_unchanged"}
    else:
        output = collect(**args)
    print(json.dumps(output, indent=2))
