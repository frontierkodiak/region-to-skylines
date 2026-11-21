"""Prospective synthetic source-response protocol; independent review precedes launch.

This protocol never runs a game. Read-only CPU preparation is not native or
geographic qualification. A review receipt is separate from the immutable plan.
"""

import argparse
import copy
import json
import math
from pathlib import Path
import subprocess

import numpy as np

from closed_storage_candidate import ROOT, sha
from maintained_water_inventory import feature_outcome, initial_natural_checks
from natural_storage_candidate import write
from natural_storage_observation import DEFINITION
from run_water_panel import validate as validate_native
from synthetic_source_response import (
    OUTPUTS,
    POLICY,
    channel,
    inventory_for,
    package_check,
    patch_outputs,
    probe_spec,
)
from water_risk_corpus import native_outcome

SCHEMA = "polli.synthetic-source-response-protocol/1"
CADENCE = 0.25
FILES = ("water", "terrain", "water-ground", "water-ground-target")


def load(path):
    return json.loads(path.read_text())


def tracked_revision(repo):
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=repo).strip():
        raise ValueError("Freeze requires a clean committed source worktree")
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()


def dependencies():
    paths = [p for p in ROOT.glob("*.py") if not p.name.startswith("test_")]
    paths += [ROOT / p for p in ("pyproject.toml", "uv.lock")]
    paths += list((ROOT / "templates").glob("*"))
    paths += [
        DEFINITION,
        ROOT / "calibration/pl1191-construction-v1/outcome-freeze.json",
    ]
    paths += [
        ROOT
        / "calibration/pl1191-construction-v1/development/phase10-source-response-design.md"
    ]
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(paths)) if p.is_file()}


def replay(folder):
    """Recompile full geometry/cohort and replay every forcing-only package patch."""
    generation = load(folder / "generation.json")
    if (
        generation["policy"] != POLICY
        or [a["setting"] for a in generation["arms"]] != OUTPUTS
    ):
        raise ValueError("Wrong synthetic design/arms")
    parent = folder / "parent"
    layout = load(ROOT / "templates/native-corridors.json")
    geometry, hydro, floor, water, construction = channel(layout)
    for name, expected in (
        ("geometry.json", geometry),
        ("layout.json", layout),
        ("channel-plan.json", construction),
    ):
        if load(parent / name) != expected:
            raise ValueError(f"Source geometry/branch declaration changed: {name}")
    for name, expected in (("terrain.u16", floor), ("water.u16", water)):
        if (parent / name).read_bytes() != np.flipud(expected).astype("<u2").tobytes():
            raise ValueError(f"Declared bounded synthetic grid changed: {name}")
    package = parent / (hydro["map_id"] + ".crp")
    if sha(package) != generation["parent_package_sha256"]:
        raise ValueError("Parent physical package changed")
    decoded = package_check(parent, package, hydro, construction, geometry, layout)
    for source, native in zip(hydro["sources"], decoded["sources"]):
        source["position"] = native["position"]
    if load(parent / "hydrology.json") != hydro:
        raise ValueError("Parent control declaration changed")
    inventory = inventory_for(geometry, hydro)
    if not inventory["coverage_complete"] or inventory["definition_sha256"] != sha(
        DEFINITION
    ):
        raise ValueError("Incomplete synthetic source cohort")
    mask = np.zeros_like(water, np.uint8)
    for p in construction["nodes"]:
        mask[tuple(p["node_rc"])] = 1
    if (parent / "mapped-water.u8").read_bytes() != np.flipud(mask).tobytes():
        raise ValueError("Frozen mapped mask changed")
    probes = probe_spec(inventory, sha(parent / "mapped-water.u8"))
    initial = initial_natural_checks(inventory, np.flipud(water))
    for name, expected in (
        ("inventory.json", inventory),
        ("probes.json", probes),
        ("authored-initialization.json", initial),
    ):
        if load(parent / name) != expected:
            raise ValueError(f"Complete source-derived cohort changed: {name}")
    if (parent / "reference-water.u16").read_bytes() != (
        parent / "water.u16"
    ).read_bytes():
        raise ValueError("Water reference changed")
    fixed = [
        "terrain.u16",
        "water.u16",
        "geometry.json",
        "channel-plan.json",
        "layout.json",
        "inventory.json",
        "probes.json",
        "authored-initialization.json",
        "mapped-water.u8",
        "reference-water.u16",
    ]
    for arm in generation["arms"]:
        here = folder / arm["folder"]
        for name in fixed:
            if (here / name).read_bytes() != (parent / name).read_bytes():
                raise ValueError(f"Arm changes fixed geometry/cohort/reference: {name}")
        expected = copy.deepcopy(hydro)
        for s in expected["sources"][:2]:
            s["output_capacity"] = arm["setting"] / 65535
        if load(here / "hydrology.json") != expected:
            raise ValueError("Arm changed a fixed intake/target/position")
        path = here / arm["package"]
        if path.read_bytes() != patch_outputs(package.read_bytes(), arm["setting"]):
            raise ValueError(
                "Arm package changed beyond the declared joint upstream outputs"
            )
        package_check(here, path, expected, construction, geometry, layout)
        if sha(path) != arm["package_sha256"]:
            raise ValueError("Arm package receipt changed")
        for name, digest in arm["files_sha256"].items():
            if sha(here / name) != digest:
                raise ValueError(f"Arm input changed: {name}")
    return generation, inventory


def freeze(folder, harness, thresholds):
    path = folder / "protocol.json"
    if path.exists():
        raise ValueError("Never overwrite a prospective protocol")
    generation, _ = replay(folder)
    source = tracked_revision(ROOT.parents[1])
    runtime = tracked_revision(harness)
    build = harness / "tools/cs1-harness/.build"
    receipt = load(build / "build-receipt.json")
    if (
        receipt["trace"] is not None
        or sha(build / "Cs1Harness.dll") != receipt["dll_sha256"]
    ):
        raise ValueError(
            "Expected exact ordinary owned telemetry build, not a hooked observer"
        )
    for name, digest in receipt["sources"].items():
        if sha(harness / "tools/cs1-harness/mod" / name) != digest:
            raise ValueError("Runtime build is stale")
    # Keep own build bytes/receipt, never copy proprietary reference assemblies.
    import shutil

    shutil.copyfile(build / "Cs1Harness.dll", folder / "Cs1Harness.dll")
    shutil.copyfile(build / "build-receipt.json", folder / "build-receipt.json")
    plan = {
        "schema": SCHEMA,
        "policy": POLICY,
        "recipe_commit": source,
        "harness_source": runtime,
        "mod_sha256": receipt["dll_sha256"],
        "dependencies_sha256": dependencies(),
        "definition_sha256": sha(DEFINITION),
        "thresholds": load(thresholds),
        "thresholds_file_sha256": sha(thresholds),
        "files_sha256": {
            str(p.relative_to(folder)): sha(p)
            for p in sorted(folder.rglob("*"))
            if p.is_file()
        },
        "arms": generation["arms"],
        "game_minutes": 60,
        "water_study_every": CADENCE,
        "independent_pre_native_review_required": True,
        "review_receipt": "Separate receipt must bind this protocol SHA, both commits and DLL before launch; no source changes under this protocol.",
        "scope": "Synthetic branched channel; not geographic qualification. Joint upstream outputs0/32/128; all three intakes128 remain active, downstream output0 fixed.",
        "temporal_scope": "Brackets, actual named counters, missed slots retained; no atomic snapshot, integrated flux, evaporation cadence or continuous-behaviour claim.",
        "runtime_scope": "Owned ordinary build; module metadata/location hashes are not full loaded-image/JIT identity or runtime health.",
        "stable_water_promise": "unknown",
    }
    write(path, plan)
    preflight(folder)
    return {
        "protocol_sha256": sha(path),
        "harness_source": runtime,
        "mod_sha256": receipt["dll_sha256"],
    }


def preflight(folder):
    plan = load(folder / "protocol.json")
    if (
        plan["schema"] != SCHEMA
        or plan["policy"] != POLICY
        or plan["definition_sha256"] != sha(DEFINITION)
    ):
        raise ValueError("Wrong synthetic prospective protocol")
    if plan["dependencies_sha256"] != dependencies():
        raise ValueError(
            "Bound recipe/compiler/validator dependency changed; use a fresh version"
        )
    for name, digest in plan["files_sha256"].items():
        if sha(folder / name) != digest:
            raise ValueError(f"Prospective physical/probe/runtime file changed: {name}")
    generation, inventory = replay(folder)
    if (
        plan["arms"] != generation["arms"]
        or plan["water_study_every"] != CADENCE
        or plan["game_minutes"] != 60
        or plan["independent_pre_native_review_required"] is not True
    ):
        raise ValueError("Predeclared factor/cadence/review requirement changed")
    return plan, inventory


def review_gate(folder, plan, receipt):
    review = load(receipt)
    expected = {
        "protocol_sha256": sha(folder / "protocol.json"),
        "recipe_commit": plan["recipe_commit"],
        "harness_source": plan["harness_source"],
        "mod_sha256": plan["mod_sha256"],
    }
    if (
        review.get("status") != "pass"
        or not review.get("review_issue")
        or any(review.get(k) != v for k, v in expected.items())
    ):
        raise ValueError(
            "Independent pre-native review is missing or applies to different bytes"
        )
    return review


def study_rows(native, points, expected_sources):
    """Check raw snapshots without converting absent/malformed evidence into a pass."""
    timeline = [
        json.loads(s) for s in (native / "timeline.jsonl").read_text().splitlines()
    ]
    rows = [r for r in timeline if r["kind"] == "water_study_snapshot"]
    if not rows:
        raise ValueError("No new-protocol telemetry")
    for i, row in enumerate(rows):
        if (
            row.get("sequence") != i
            or row.get("prefix") != f"ws{i:06d}"
            or row.get("schema") != "polli.water-study-snapshot/1"
        ):
            raise ValueError("Telemetry sequence missing/duplicated or wrong schema")
        if len(row["samples"]) != len(points):
            raise ValueError("Telemetry omitted an authored branch/probe")
        for point, sample in zip(points, row["samples"]):
            if sample.get("name") != point["name"] or any(
                not math.isfinite(sample[a]) or abs(sample[a] - point[a]) > 0.001
                for a in ("x", "z")
            ):
                raise ValueError("Telemetry changed authored probe identity")
        if len(row["sources"]) != len(expected_sources):
            raise ValueError("Telemetry source count differs")
        for source, expected in zip(row["sources"], expected_sources):
            fixed = {
                "type": expected["type"],
                "target_fixed": expected["target_fixed"],
                "input_rate": expected["intake_rate"],
                "output_rate": expected["output_rate"],
            }
            if any(source[k] != v for k, v in fixed.items()) or any(
                not math.isfinite(source[p][j])
                or abs(source[p][j] - expected["position"][j]) > 0.001
                for p in ("input_position", "output_position")
                for j in range(3)
            ):
                raise ValueError("Telemetry changed fixed control table")
        for name in FILES:
            info = row["files"][name]
            path = native / "grids" / f"{row['prefix']}-{name}.u16"
            if (
                Path(info["path"]).name != path.name
                or path.stat().st_size != 1081 * 1081 * 2
                or info["bytes"] != path.stat().st_size
                or sha(path) != info["sha256"]
            ):
                raise ValueError("Telemetry grid size/hash/identity mismatch")
        depth = np.fromfile(
            native / "grids" / f"{row['prefix']}-water.u16", dtype="<u2"
        )
        if (
            row["cells"] != depth.size
            or row["depth_sum_q"] != int(depth.astype(np.uint64).sum())
            or row["wet_nodes"] != int((depth > 0).sum())
        ):
            raise ValueError("Telemetry storage checksum mismatch")
    return rows, [r for r in timeline if r["kind"] == "water_study_runtime"]


def collect(folder, arm_name, native, review):
    plan, inventory = preflight(folder)
    review_gate(folder, plan, review)
    arm = next(a for a in plan["arms"] if a["folder"] == arm_name)
    here = folder / arm_name
    report = validate_native(
        {**arm, "slug": arm_name}, here, native, plan["harness_source"]
    )
    verdict = load(native / "verdict.json")
    if (
        report["session"]["mod_sha256"] != plan["mod_sha256"]
        or verdict["thresholds"] != plan["thresholds"]
    ):
        raise ValueError("Runtime/unchanged native thresholds differ")
    decoded = package_check(
        here,
        here / arm["package"],
        load(here / "hydrology.json"),
        load(here / "channel-plan.json"),
        load(here / "geometry.json"),
        load(here / "layout.json"),
    )
    rows, modules = study_rows(native, inventory["points"], decoded["sources"])
    samples = [
        {
            "label": r["prefix"],
            "stats": {"frame": r["before"]["simulation_frame"]},
            "water": {"samples": r["samples"]},
        }
        for r in rows
    ]
    features = feature_outcome(inventory, report, samples)
    construction = load(here / "channel-plan.json")
    floors = []
    for row in rows:
        floor = np.flipud(
            np.fromfile(
                native / "grids" / f"{row['prefix']}-water-ground.u16", dtype="<u2"
            ).reshape(1081, 1081)
        )
        body_ok = all(
            p["stage_q"] - int(floor[tuple(p["node_rc"])]) >= 64
            for p in construction["nodes"]
        )
        bank_ok = all(
            int(floor[tuple(n)])
            - max(
                p["stage_q"]
                for p in construction["nodes"]
                if max(abs(p["node_rc"][0] - n[0]), abs(p["node_rc"][1] - n[1])) == 1
            )
            >= 32
            for n in construction["rim_rc"]
        )
        floors.append(
            {
                "prefix": row["prefix"],
                "status": "pass" if body_ok and bank_ok else "fail",
                "sha256": row["files"]["water-ground"]["sha256"],
                "scope": "Authored stage minus actual floor; not actual depth or unobserved floor stability.",
            }
        )
    times = [
        (r["before"]["simulation_frame"] - report["start_frame"])
        / report["frames_per_game_minute"]
        for r in rows
    ]
    cadence_ok = (
        times[0] <= 0.001
        and times[-1] >= 60
        and all(0 < b - a <= CADENCE + 0.05 for a, b in zip(times, times[1:]))
        and not any(r["missed_slots"] for r in rows)
    )
    counters_available = all(
        v.get("available") is True
        for r in rows
        for side in ("before", "after")
        for v in r[side]["water_fields"].values()
    ) and all(
        len(r[side]["water_fields"]) == 4 for r in rows for side in ("before", "after")
    )
    original = native_outcome(report, verdict)
    failed = (
        features["status"] == "fail"
        or any(f["status"] == "fail" for f in floors)
        or original["labels"]["flood"] is True
    )
    return {
        "schema": "polli.synthetic-source-response-observation/1",
        "protocol_sha256": sha(folder / "protocol.json"),
        "review_sha256": sha(review),
        "arm": arm_name,
        "game_minutes": report["game_minutes"],
        "sampled_contract_status": "fail" if failed else "unknown",
        "features": features,
        "actual_floor_authored_stage_checks": floors,
        "cadence_complete": cadence_ok,
        "named_counters_all_available": counters_available,
        "runtime_metadata_records": len(modules),
        "snapshot_count": len(rows),
        "measured_storage_q": [
            {
                "prefix": r["prefix"],
                "sum": r["depth_sum_q"],
                "wet_nodes": r["wet_nodes"],
                "before": r["before"],
                "after": r["after"],
                "missed_slots": r["missed_slots"],
            }
            for r in rows
        ],
        "water_outcome_original_definition": original,
        "raw_failed_checks": [
            c["name"] for c in verdict["checks"] if c["status"] == "fail"
        ],
        "native_files_sha256": {
            p.name: sha(p)
            for p in (
                native / "report.json",
                native / "verdict.json",
                native / "timeline.jsonl",
                native / "harness-source.json",
            )
        },
        "scope": "Development-only synthetic measurement; joint upstream output settings with intakes fixed. Bracketed reads, not atomic or integrated physical flux. Runtime health/full loaded-image identity unknown. No between-sample guarantee.",
        "stable_water_promise": "unknown",
        "geographic_qualification": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, arguments in (
        ("freeze", ["folder", "harness", "thresholds"]),
        ("preflight", ["folder"]),
        ("collect", ["folder", "arm_name", "native", "review"]),
    ):
        command = sub.add_parser(name)
        for argument in arguments:
            command.add_argument(argument, type=str if argument == "arm_name" else Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    result = globals()[command](**args)
    print(
        json.dumps(
            {
                "status": "pass",
                "review_gate": "pending; no launch authorization from preflight",
            }
            if command == "preflight"
            else result,
            indent=2,
        )
    )
