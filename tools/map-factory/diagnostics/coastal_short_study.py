"""Frozen 15-minute coastal telemetry, not a 60-minute qualification or repair."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import numpy as np

from coastal_floor_audit import (
    ROOT,
    PACKAGE_SHA,
    PROBES_SHA,
    TARGETS,
    decoded_package,
    difference,
    grid,
    load,
    preflight as audit_preflight,
    sha,
    source_domains,
    write,
)

SOURCE = "diagnostics/coastal_short_study.py"
DESIGN = (
    "calibration/pl1191-construction-v1/development/phase15-coastal-short-policy.md"
)
HARNESS = "0ec989dabbc89b0b2a429fa4247ec1f0ab36d888"
DLL = "368955b1f0b0855c80b8078bf22805fcd7f8f8db8e0428218f262bd37eda6346"


def git(harness, *args):
    return subprocess.check_output(
        ["git", "-C", str(harness), *args], text=True
    ).strip()


def groups(points, legacy):
    names = {p["name"] for p in legacy}
    return {
        "all_frozen_probes": list(range(len(points))),
        **{
            name: [
                i
                for i, p in enumerate(points)
                if p["name"].removeprefix("geography:").split(" [", 1)[0] == name
            ]
            for name in TARGETS
        },
        "fixed_historical162": [i for i, p in enumerate(points) if p["name"] in names],
    }


def metrics(samples, selected):
    result = {}
    for name, ids in selected.items():
        rows = [samples[i] for i in ids]
        velocity = np.asarray([p["velocity"] for p in rows], float)
        if velocity.shape != (len(rows), 3) or not np.isfinite(velocity).all():
            raise ValueError("Missing/nonfinite complete probe velocities")
        speed = np.hypot(velocity[:, 0], velocity[:, 2])
        result[name] = {
            "points": len(rows),
            "native_wet_flag": sum(bool(p["wet"]) for p in rows),
            "depth_gt_0_1m": sum(p["depth"] > 0.1 for p in rows),
            "nearby_depth_gt_0_1m": sum(p["max_depth_within_64m"] > 0.1 for p in rows),
            "horizontal_velocity_nonzero_api": int(np.count_nonzero(speed > 1e-9)),
            "max_horizontal_velocity_api": float(speed.max()) if len(rows) else None,
            "velocity_units": "API readback only; not integrated discharge or physical supply budget",
        }
    return result


def retained_transition(audit):
    points = load(audit / "physical/probes.json")["points"]
    legacy = load(audit / "prior-coastal-audit.json")["static_ocean_connectivity"][
        "probes"
    ]
    legacy = [
        p
        for p in legacy
        if p["name"].removeprefix("geography:").split(" [", 1)[0] in TARGETS
    ]
    selected = groups(points, legacy)
    result = []
    with (audit / "retained-native/timeline.jsonl").open() as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("kind") != "sample":
                continue
            samples = row["water"]["samples"]
            if [p["name"] for p in samples] != [p["name"] for p in points]:
                raise ValueError("Retained full probe cohort differs")
            result.append(
                {
                    "label": row["label"],
                    "stats_frame": row["stats"]["frame"],
                    "water_reported_simulation_frame": row["water"]["frame"],
                    "groups": metrics(samples, selected),
                }
            )
    return {
        "scope": "retained13sample velocities DO exist; the missing question is sub-five-minute transition/floors, not absence of old velocity fields",
        "samples": result,
        "new_native_outcome": False,
    }


def runtime_check(harness):
    if git(harness, "rev-parse", "HEAD") != HARNESS or git(
        harness, "status", "--porcelain"
    ):
        raise ValueError("Owned runtime must be exact clean0ec989d before collection")
    project = harness / "tools/cs1-harness"
    receipt = load(project / ".build/build-receipt.json")
    if sha(project / ".build/Cs1Harness.dll") != DLL or receipt["dll_sha256"] != DLL:
        raise ValueError("Owned runtime DLL differs from declared reviewed code")
    for name, expected in receipt["sources"].items():
        if sha(project / "mod" / name) != expected:
            raise ValueError(f"Build source differs: {name}")
    sys.path.insert(0, str(project))
    from cs1_harness.config import Config

    cfg = Config.for_host("blade")
    for name, expected in receipt["game_assemblies"].items():
        if sha(cfg.game_dir / "Cities_Data/Managed" / name) != expected:
            raise ValueError(f"On-disk compile reference differs: {name}")
    return receipt


def prepare(audit, output, harness):
    audit_preflight(audit)
    if output.exists():
        raise ValueError("Use a fresh prospective coastal telemetry protocol")
    runtime_check(harness)
    output.mkdir(parents=True)
    shutil.copytree(audit / "physical", output / "physical")
    for src, name in (
        (audit / "audit.json", "retained-floor-audit.json"),
        (audit / "result-receipt.json", "retained-audit-receipt.json"),
        (audit / "prospective-freeze.json", "retained-audit-freeze.json"),
        (audit / "prior-coastal-audit.json", "prior-coastal-audit.json"),
    ):
        shutil.copyfile(src, output / name)
    transition = retained_transition(audit)
    write(output / "retained-transition.json", transition)
    first15 = transition["samples"][:4]
    changed = any(
        s["groups"][name]["nearby_depth_gt_0_1m"]
        != first15[0]["groups"][name]["nearby_depth_gt_0_1m"]
        for s in first15[1:]
        for name in TARGETS
    )
    dependencies = {
        str(p.relative_to(ROOT)): sha(p)
        for directory in (ROOT, ROOT / "diagnostics")
        for p in directory.glob("*.py")
        if not p.name.startswith("test_")
    }
    for name in (
        DESIGN,
        "pyproject.toml",
        "uv.lock",
        "maintained-water-definition.json",
        "outcome-freeze.json",
    ):
        dependencies[name] = sha(ROOT / name)
    project = harness / "tools/cs1-harness"
    harness_files = {
        str(p.relative_to(harness)): sha(p)
        for suffix in ("*.py", "*.cs")
        for p in project.rglob(suffix)
        if ".venv" not in p.parts
    }
    for name in (
        ".build/Cs1Harness.dll",
        ".build/build-receipt.json",
        "pyproject.toml",
        "uv.lock",
    ):
        path = project / name
        harness_files[str(path.relative_to(harness))] = sha(path)
    write(
        output / "native-plan.json",
        {
            "schema": "polli.coastal-short-study-protocol/1",
            "question": "During first15minutes, do captured actual-floor changes coincide with drying, and what sub-five-minute velocity/head/depth readbacks occur?",
            "game_minutes": 15,
            "water_study_every": 0.25,
            "old_first15_nearby_state_changes_observed": changed,
            "harness_source": HARNESS,
            "mod_sha256": DLL,
            "source_files_sha256": dependencies,
            "harness_files_sha256": harness_files,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "package_sha256": PACKAGE_SHA,
            "probes_sha256": PROBES_SHA,
            "primary_60minute_acceptance": "not_attempted; always incomplete/unknown in this diagnostic",
            "independent_results_review_before_adoption": True,
            "pre_native_permission_gate": False,
            "new_forcing_or_geometry": False,
            "holdout_inputs_accessed": False,
            "stable_water_promise": "unknown",
        },
    )
    preflight(output, harness)
    return {
        "native_plan_sha256": sha(output / "native-plan.json"),
        "old_first15_nearby_state_changes_observed": changed,
    }


def preflight(folder, harness):
    plan = load(folder / "native-plan.json")
    if (
        plan["schema"] != "polli.coastal-short-study-protocol/1"
        or plan["game_minutes"] != 15
        or plan["water_study_every"] != 0.25
        or not plan["old_first15_nearby_state_changes_observed"]
    ):
        raise ValueError("Wrong/unjustified fixed short-window question")
    runtime_check(harness)
    for names, root in (
        ("source_files_sha256", ROOT),
        ("harness_files_sha256", harness),
        ("files_sha256", folder),
    ):
        for name, expected in plan[names].items():
            if sha(root / name) != expected:
                raise ValueError(f"Frozen short-study bytes changed: {name}")
    decoded_package(folder)


def control_mismatches(actual, expected):
    problems = []
    controls = {s["id"]: s for s in actual}
    if len(controls) != len(actual) or set(controls) != set(
        range(1, len(expected) + 1)
    ):
        problems.append(
            {"scope": "active_control_ids_or_count", "actual_count": len(actual)}
        )
    for original in expected:
        source = controls.get(original["index"] + 1)
        if source is None:
            continue
        for field, key in (
            ("type", "type"),
            ("target_fixed", "target_fixed"),
            ("input_rate", "intake_rate"),
            ("output_rate", "output_rate"),
        ):
            if source[field] != original[key]:
                problems.append(
                    {
                        "id": source["id"],
                        "field": field,
                        "expected": original[key],
                        "actual": source[field],
                    }
                )
        for field in ("input_position", "output_position"):
            if any(
                abs(a - b) > 0.001 for a, b in zip(source[field], original["position"])
            ):
                problems.append(
                    {
                        "id": source["id"],
                        "field": field,
                        "expected": original["position"],
                        "actual": source[field],
                    }
                )
    return problems


def collect(folder, native, harness, output):
    preflight(folder, harness)
    if output.exists():
        raise ValueError("Retain all collections; use a fresh output")
    decoded = decoded_package(folder)
    session = load(native / "session-receipt.json")
    if (
        session["map"]["sha256"] != PACKAGE_SHA
        or session["mod_sha256"] != DLL
        or sha(native / "probes.json") != PROBES_SHA
    ):
        raise ValueError("Wrong observed package/runtime/full probe cohort")
    points = load(folder / "physical/probes.json")["points"]
    legacy = load(folder / "prior-coastal-audit.json")["static_ocean_connectivity"][
        "probes"
    ]
    selected = groups(
        points,
        [
            p
            for p in legacy
            if p["name"].removeprefix("geography:").split(" [", 1)[0] in TARGETS
        ],
    )
    domains = source_domains(load(folder / "physical/geometry.json"))
    rows, runtime, ordinary, unique_floors = [], [], [], {}
    with (native / "timeline.jsonl").open() as stream:
        for line in stream:
            e = json.loads(line)
            if e.get("kind") == "water_study_runtime":
                runtime.append(e)
            if e.get("kind") == "sample":
                ordinary.append(
                    {
                        "label": e["label"],
                        "stats_frame": e["stats"]["frame"],
                        "water_reported_simulation_frame": e["water"]["frame"],
                    }
                )
            if e.get("kind") != "water_study_snapshot":
                continue
            if not re.fullmatch(r"ws[0-9]{6}", e["prefix"]):
                raise ValueError("Unexpected study prefix")
            if len(e["samples"]) != len(points) or any(
                s["name"] != p["name"]
                or abs(s["x"] - p["x"]) > 0.001
                or abs(s["z"] - p["z"]) > 0.001
                for s, p in zip(e["samples"], points)
            ):
                raise ValueError("Full probe names/coordinates changed")
            for kind, record in e["files"].items():
                path = native / "grids" / f"{e['prefix']}-{kind}.u16"
                if sha(path) != record["sha256"]:
                    raise ValueError("Actual snapshot grid hash mismatch")
            floor_hash = e["files"]["water-ground"]["sha256"]
            if floor_hash not in unique_floors:
                floor = grid(native / "grids" / f"{e['prefix']}-water-ground.u16")
                reference = grid(folder / "physical/terrain.u16")
                unique_floors[floor_hash] = {
                    "current_vs_authored": difference(floor, reference),
                    "source_features": [
                        {
                            "id": entry["id"],
                            "scope": entry["scope"],
                            "nodes": entry["native_nodes"],
                            "current_vs_authored": difference(
                                floor[mask], reference[mask]
                            )
                            if mask.any()
                            else None,
                        }
                        for entry, mask in domains
                    ],
                }
            rows.append(
                {
                    "prefix": e["prefix"],
                    "sequence": e["sequence"],
                    "trigger_game_minute": e["trigger_game_minute"],
                    "missed_slots": e["missed_slots"],
                    "before": e["before"],
                    "after": e["after"],
                    "floor_sha256": floor_hash,
                    "groups": metrics(e["samples"], selected),
                    "control_mismatches": control_mismatches(
                        e["sources"], decoded["sources"]
                    ),
                    "reported_controls": len(e["sources"]),
                    "depth_sum_q": e["depth_sum_q"],
                }
            )
    if not rows:
        raise ValueError("No new study snapshots; retain failed capture")
    times = [r["trigger_game_minute"] for r in rows]
    result = {
        "schema": "polli.coastal-short-study-result/1",
        "native_plan_sha256": sha(folder / "native-plan.json"),
        "native_directory": str(native),
        "raw_verdict_sha256": sha(native / "verdict.json"),
        "raw_report_sha256": sha(native / "report.json"),
        "session_sha256": sha(native / "session-receipt.json"),
        "samples": rows,
        "snapshots": len(rows),
        "unique_actual_floors": unique_floors,
        "ordinary_sample_counters": ordinary,
        "runtime_metadata": runtime,
        "elapsed_trigger_minutes": times[-1],
        "max_observed_trigger_gap_minutes": float(np.diff(times).max())
        if len(times) > 1
        else None,
        "missed_slots": sum(len(r["missed_slots"]) for r in rows),
        "control_tables_all_match": all(not r["control_mismatches"] for r in rows),
        "full_hour_acceptance": "incomplete/unknown; only15minutes requested, no old gate/score/certificate changed",
        "loaded_image_identity_and_runtime_health": "not established by metadata/current file hashes",
        "between_sample_floor_and_integrated_flux": "unknown",
        "stable_water_promise": "unknown",
    }
    output.mkdir(parents=True)
    write(output / "result.json", result)
    write(
        output / "receipt.json",
        {
            "native_plan_sha256": result["native_plan_sha256"],
            "result_sha256": sha(output / "result.json"),
            "raw_verdict_unchanged": result["raw_verdict_sha256"],
            "native_files_sha256": {
                str(p.relative_to(native)): sha(p)
                for p in sorted(native.rglob("*"))
                if p.is_file()
            },
        },
    )
    return {
        "snapshots": len(rows),
        "floor_hashes": len(unique_floors),
        "elapsed_trigger_minutes": times[-1],
        "control_tables_all_match": result["control_tables_all_match"],
        "result_sha256": sha(output / "result.json"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, arguments in (
        ("prepare", ("audit", "output", "harness")),
        ("preflight", ("folder", "harness")),
        ("collect", ("folder", "native", "harness", "output")),
    ):
        command = commands.add_parser(name)
        for argument in arguments:
            command.add_argument(argument, type=Path)
    args = vars(parser.parse_args())
    print(
        json.dumps(
            globals()[args.pop("command")](**args) or {"status": "preflight_pass"},
            indent=2,
        )
    )
