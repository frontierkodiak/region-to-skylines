"""Result reporting under PL-1191's explicit user review-order override.

The physical protocol and its frozen validators are not changed. This adapter
uses those validators and fixed primary thresholds, but records the author's
instruction instead of fabricating a pre-native independent-review pass.
Independent review of these results is still required before adoption.
"""

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from closed_storage_candidate import sha  # noqa: E402
from maintained_water_inventory import feature_outcome  # noqa: E402
from run_water_panel import validate  # noqa: E402
from synthetic_source_protocol import CADENCE, load, preflight, study_rows  # noqa: E402
from synthetic_source_response import package_check  # noqa: E402
from water_risk_corpus import native_outcome  # noqa: E402

COMMENT = "01a1ff6d-7295-72b6-8481-d925cb4a2f5c"


def runtime_locations(records, receipt):
    expected = {**receipt["game_assemblies"], "Cs1Harness.dll": receipt["dll_sha256"]}
    checks = []
    for name, digest in expected.items():
        matches = [
            m
            for r in records
            for m in r.get("modules", [])
            if m.get("name", "").split(",")[0] + ".dll" == name
        ]
        states = [m.get("current_location_sha256") for m in matches]
        checks.append(
            {
                "assembly": name,
                "status": "unknown"
                if not states or any(s is None for s in states)
                else "pass"
                if all(s == digest for s in states)
                else "fail",
                "expected_current_file_sha256": digest,
                "recorded_current_file_sha256": states,
            }
        )
    return {
        "scope": "Loaded-module metadata/current on-disk location hash comparison only, NOT loaded-image/JIT identity or runtime health.",
        "checks": checks,
    }


def authorized(folder, authorization):
    record = load(authorization)
    if (
        record.get("authorizing_comment") != COMMENT
        or record.get("frozen_protocol_sha256") != sha(folder / "protocol.json")
        or record.get("independent_results_review_before_adoption") is not True
    ):
        raise ValueError("Missing exact user review-order instruction/protocol")
    return record


def floor_checks(native, row, construction):
    floor = np.flipud(
        np.fromfile(
            native / "grids" / f"{row['prefix']}-water-ground.u16", "<u2"
        ).reshape(1081, 1081)
    )
    own = {tuple(p["node_rc"]): p["stage_q"] for p in construction["nodes"]}
    minimum_depth_q = min(stage - int(floor[n]) for n, stage in own.items())
    minimum_rim_q = min(
        int(floor[tuple(n)])
        - max(
            stage
            for p, stage in own.items()
            if max(abs(p[0] - n[0]), abs(p[1] - n[1])) == 1
        )
        for n in construction["rim_rc"]
    )
    return {
        "prefix": row["prefix"],
        "status": "pass" if minimum_depth_q >= 64 and minimum_rim_q >= 32 else "fail",
        "minimum_authored_stage_to_actual_floor_m": minimum_depth_q / 64,
        "minimum_actual_rim_to_authored_stage_m": minimum_rim_q / 64,
        "floor_sha256": row["files"]["water-ground"]["sha256"],
        "scope": "Static authored-stage minus actual floor, separately from actual water depth; no unobserved stability claim.",
    }


def collect(folder, arm_name, native, authorization):
    auth = authorized(folder, authorization)
    plan, inventory = preflight(folder)
    if (
        auth["harness_source"] != plan["harness_source"]
        or auth["mod_sha256"] != plan["mod_sha256"]
    ):
        raise ValueError("Authorized runtime differs from frozen protocol")
    arm = next(a for a in plan["arms"] if a["folder"] == arm_name)
    here = folder / arm_name
    report = validate({**arm, "slug": arm_name}, here, native, plan["harness_source"])
    verdict = load(native / "verdict.json")
    if (
        report["session"]["mod_sha256"] != plan["mod_sha256"]
        or verdict["thresholds"] != plan["thresholds"]
    ):
        raise ValueError("Runtime or original native thresholds differ")
    construction = load(here / "channel-plan.json")
    decoded = package_check(
        here,
        here / arm["package"],
        load(here / "hydrology.json"),
        construction,
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
    floors = [floor_checks(native, r, construction) for r in rows]
    clocks = (
        "m_waterFrameIndex",
        "m_waterFrameIndex2",
        "m_simulationFrameIndex",
        "m_stepIndex",
    )
    counters = all(
        set(r[s]["water_fields"]) == set(clocks)
        and all(r[s]["water_fields"][c].get("available") is True for c in clocks)
        for r in rows
        for s in ("before", "after")
    )
    times = [
        (r["before"]["simulation_frame"] - report["start_frame"])
        / report["frames_per_game_minute"]
        for r in rows
    ]
    cadence = (
        abs(times[0]) <= 0.001
        and times[-1] >= 60
        and all(math.isfinite(m) for m in times)
        and all(0 < b - a <= CADENCE + 0.05 for a, b in zip(times, times[1:]))
        and not any(r["missed_slots"] for r in rows)
    )
    own = [(1080 - p["node_rc"][0], p["node_rc"][1]) for p in construction["nodes"]]
    storage = []
    for row, minute in zip(rows, times):
        depths = np.fromfile(
            native / "grids" / f"{row['prefix']}-water.u16", "<u2"
        ).reshape(1081, 1081)
        values = [int(depths[n]) for n in own]
        storage.append(
            {
                "prefix": row["prefix"],
                "minute_before": minute,
                "trigger_game_minute": row["trigger_game_minute"],
                "scheduled_slot": row["scheduled_slot"],
                "missed_slots": row["missed_slots"],
                "full_depth_sum_q": row["depth_sum_q"],
                "full_wet_nodes": row["wet_nodes"],
                "declared_channel_depth_sum_q": sum(values),
                "declared_channel_depth_q": values,
                "before": row["before"],
                "after": row["after"],
            }
        )
    original = native_outcome(report, verdict)
    lineage_path = native / "derived-judgment-lineage.json"
    lineage = load(lineage_path) if lineage_path.exists() else None
    failed = (
        features["status"] == "fail"
        or any(r["status"] == "fail" for r in floors)
        or original["labels"]["flood"] is True
    )
    return {
        "schema": "polli.synthetic-source-response-authorized-result/1",
        "protocol_sha256": sha(folder / "protocol.json"),
        "authorization_sha256": sha(authorization),
        "authorizing_comment": COMMENT,
        "review_order": "User explicitly authorized native observation in parallel with PL-1226; no pre-native review pass fabricated.",
        "arm": arm_name,
        "game_minutes": report["game_minutes"],
        "snapshot_count": len(rows),
        "sampled_contract_status": "fail" if failed else "unknown",
        "features": features,
        "all_reported_controls_match": True,
        "source_count": len(decoded["sources"]),
        "actual_floor_authored_stage_checks": floors,
        "cadence_complete": cadence,
        "named_counters_all_available": counters,
        "runtime_metadata_records": len(modules),
        "runtime_location_hash_comparison": runtime_locations(
            modules, load(folder / "build-receipt.json")
        ),
        "measured_storage": storage,
        "water_outcome_original_definition": original,
        "raw_native_verdict": lineage["raw_verdict"]["verdict"]
        if lineage
        else verdict["verdict"],
        "derived_native_verdict": verdict["verdict"] if lineage else None,
        "judgment_lineage": lineage,
        "judged_nonpassing_checks": [
            c for c in verdict["checks"] if c["status"] != "pass"
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
        "cleanup": report["session"]["cleanup"],
        "independent_results_review": "required_before_adoption",
        "scope": "Synthetic sampled response only. Joint upstream outputs with intakes fixed. Bracketed, not atomic. Storage sums/counters/flow_raw are not integrated physical flux or evaporation proof. Full loaded-image identity/runtime health and between-sample behavior unknown.",
        "stable_water_promise": "unknown",
        "geographic_qualification": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("folder", "arm_name", "native", "authorization"):
        parser.add_argument(name, type=str if name == "arm_name" else Path)
    print(json.dumps(collect(**vars(parser.parse_args())), indent=2))
