"""Source-record-removal necessity diagnostic; implicit ocean boundary remains."""

import argparse
import copy
import hashlib
import struct
import json
from pathlib import Path
import shutil
import sys

import numpy as np

from coastal_dense_study import FIELDS, readback_metrics, sha
from coastal_short_study import DLL, control_mismatches, git

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crp import read_package, patch_metadata, water_payload, write_package  # noqa: E402
from water_diagnostics import decode_water, encoded_sources, bind_sources  # noqa: E402

HARNESS = "a647354b767aff17c880a2d07585fd9dcfb9d768"
POLICY = (
    "calibration/pl1191-construction-v1/development/phase20-source-absent-policy.md"
)


def load(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def missed_slot_count(rows):
    if any(not isinstance(r.get("missed_slots"), list) for r in rows):
        raise ValueError("Missing/malformed missed-slot lists remain unknown")
    return sum(len(r["missed_slots"]) for r in rows)


def remove_records(payload):
    water = decode_water(payload)
    if len(water["sources"]) != 167 or any(
        s["intake_rate"] != 0 or s["output_rate"] != 0 for s in water["sources"]
    ):
        raise ValueError("Exact167 rate-zero parent controls required")
    chunk = (
        water["tag"]
        + water_payload(
            water["depth"], encoded_sources(water), water["frame"], water["sea_level_m"]
        )
        + water["tail"]
    )
    if chunk != payload[water["start"] : water["end"]]:
        raise ValueError(
            "Full initial water/velocity/source encoding does not round-trip"
        )
    count_at = water["end"] - 14 - 43 * 167 - 2
    if payload[count_at : count_at + 2] != struct.pack(">H", 167):
        raise ValueError("Source-table location differs")
    updated = payload[:count_at] + b"\x00\x00" + payload[count_at + 2 + 43 * 167 :]
    after = decode_water(updated)
    if after["sources"] or after["sea_level_m"] != water["sea_level_m"]:
        raise ValueError("Wrong empty table/sea stage")
    if (
        not np.array_equal(after["depth"], water["depth"])
        or after["velocities"] != water["velocities"]
    ):
        raise ValueError("Initialized water or velocity changed")
    if (
        updated[:count_at] != payload[:count_at]
        or updated[count_at + 2 :] != payload[count_at + 2 + 43 * 167 :]
    ):
        raise ValueError("More than source table changed")
    return updated, water, after


def patch(parent):
    physical = parent / "physical"
    source = (physical / "PL857-low-coast-oceania.crp").read_bytes()
    package, assets = read_package(source)
    originals = copy.deepcopy(assets)
    sim = next(a for a in assets if a["kind"] == 52)
    original = sim["payload"]
    updated, before, after = remove_records(original)
    hydro = load(physical / "hydrology.json")
    bind_sources(before, hydro)
    sim["payload"] = updated
    old_ref, new_ref = (
        hashlib.md5(original).hexdigest(),
        hashlib.md5(updated).hexdigest(),
    )
    for a in assets:
        if a["kind"] == 100:
            old = a["payload"]
            a["payload"] = patch_metadata(old, new_ref)
            if patch_metadata(a["payload"], old_ref) != old:
                raise ValueError("Metadata differs beyond asset reference")
    data = write_package(package, assets)
    _, final = read_package(data)
    differences = []
    for a, b in zip(originals, final):
        changed = a["payload"] != b["payload"]
        if (
            a["name"] != b["name"]
            or a["kind"] != b["kind"]
            or (changed and a["kind"] not in (52, 100))
        ):
            raise ValueError("Non-water physical assets changed")
        differences.append(
            {
                "name": a["name"],
                "kind": a["kind"],
                "changed": changed,
                "before_sha256": hashlib.sha256(a["payload"]).hexdigest(),
                "after_sha256": hashlib.sha256(b["payload"]).hexdigest(),
            }
        )
    final_sim = next(a["payload"] for a in final if a["kind"] == 52)
    if final_sim != updated:
        raise ValueError("Final decoded payload differs")
    hydro = copy.deepcopy(hydro)
    hydro["sources"] = []
    receipt = {
        "factor": "remove all167 serialized rate-zero source records; implicit sea boundary unchanged",
        "source_controls": before["sources"],
        "diagnostic_controls": after["sources"],
        "source_crp_sha256": hashlib.sha256(source).hexdigest(),
        "crp_sha256": hashlib.sha256(data).hexdigest(),
        "removed_bytes": 43 * 167,
        "initial_water_changed_cells": 0,
        "sea_level_m": after["sea_level_m"],
        "velocity_arrays": after["velocities"],
        "assets": differences,
    }
    return data, hydro, receipt


def runtime_check(harness):
    if git(harness, "rev-parse", "HEAD") != HARNESS or git(
        harness, "status", "--porcelain"
    ):
        raise ValueError("Exact clean owneda647354 runtime required until collection")
    project = harness / "tools/cs1-harness"
    receipt = load(project / ".build/build-receipt.json")
    if sha(project / ".build/Cs1Harness.dll") != DLL or receipt["dll_sha256"] != DLL:
        raise ValueError("Bound DLL differs")
    for name, digest in receipt["sources"].items():
        if sha(project / "mod" / name) != digest:
            raise ValueError("Build source changed")
    sys.path.insert(0, str(project))
    from cs1_harness.config import Config

    cfg = Config.for_host("blade")
    for name, digest in receipt["game_assemblies"].items():
        if sha(cfg.game_dir / "Cities_Data/Managed" / name) != digest:
            raise ValueError("On-disk compile reference changed")


def prepare(parent, harness, output):
    if output.exists():
        raise ValueError("Fresh protocol required")
    if (
        sha(parent / "native-plan.json")
        != "165359fb140c717f39e40b4ac5584b8dabb07ef6ed221d7fd8cf5e0c6a60a409"
    ):
        raise ValueError("Wrong dense source/probe parent")
    runtime_check(harness)
    data, hydro, receipt = patch(parent)
    shutil.copytree(parent, output / "parent")
    for name in ["physical", "domains.json", "query-nodes.i32", "geometric-paths.json"]:
        source = parent / name
        if source.is_dir():
            shutil.copytree(source, output / name)
        else:
            shutil.copyfile(source, output / name)
    (output / "physical/PL857-low-coast-oceania.crp").write_bytes(data)
    write(output / "physical/hydrology.json", hydro)
    write(output / "source-record-removal.json", receipt)
    parent_plan = load(parent / "native-plan.json")
    sources = (
        list(ROOT.glob("*.py"))
        + list((ROOT / "diagnostics").glob("*.py"))
        + [ROOT / POLICY, ROOT / "uv.lock"]
    )
    plan = {
        "schema": "polli.coastal-source-record-absent/1",
        "question": "Are serialized rate-zero source records necessary for distant-ocean drawdown? Remove all167 records from rate-zero parent; retain sea90/initial water/velocity/terrain/all geometry/full probes. Implicit ocean boundary remains. Not evaporation proof, physical flux, repair or primary acceptance.",
        "game_minutes": 15,
        "water_study_every": 0.25,
        "harness_source": HARNESS,
        "mod_sha256": DLL,
        "parent_native_plan_sha256": sha(parent / "native-plan.json"),
        "package_sha256": sha(output / "physical/PL857-low-coast-oceania.crp"),
        "probes_sha256": sha(output / "physical/probes.json"),
        "source_files_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sources},
        "harness_files_sha256": {
            name: sha(harness / name) for name in parent_plan["harness_files_sha256"]
        },
        "files_sha256": {
            str(p.relative_to(output)): sha(p)
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
        "full_hour_acceptance": "incomplete/unknown;15minute diagnostic",
        "pre_native_review_permission_gate": False,
        "stable_water_promise": "unknown",
    }
    write(output / "native-plan.json", plan)
    return {
        "native_plan_sha256": sha(output / "native-plan.json"),
        "package_sha256": plan["package_sha256"],
    }


def preflight(folder, harness):
    plan = load(folder / "native-plan.json")
    if plan["schema"] != "polli.coastal-source-record-absent/1":
        raise ValueError("Wrong new protocol")
    runtime_check(harness)
    for root, field in [
        (folder, "files_sha256"),
        (ROOT, "source_files_sha256"),
        (harness, "harness_files_sha256"),
    ]:
        for name, digest in plan[field].items():
            if sha(root / name) != digest:
                raise ValueError("Bound input/source differs: " + name)
    data, hydro, receipt = patch(folder / "parent")
    if (
        data != (folder / "physical/PL857-low-coast-oceania.crp").read_bytes()
        or hydro != load(folder / "physical/hydrology.json")
        or receipt != load(folder / "source-record-removal.json")
    ):
        raise ValueError("Source-only physical replay differs")
    for path in (folder / "parent/physical").iterdir():
        if path.is_file() and path.name not in [
            "PL857-low-coast-oceania.crp",
            "hydrology.json",
        ]:
            if path.read_bytes() != (folder / "physical" / path.name).read_bytes():
                raise ValueError("Non-forcing physical/probe data changed")
    return {
        "preflight_pass": True,
        "native_plan_sha256": sha(folder / "native-plan.json"),
    }


def collect(folder, native, harness, output):
    preflight(folder, harness)
    if output.exists():
        raise ValueError("Fresh collection required")
    plan, session = (
        load(folder / "native-plan.json"),
        load(native / "session-receipt.json"),
    )
    if (
        session["map"]["sha256"] != plan["package_sha256"]
        or session["mod_sha256"] != DLL
        or load(native / "harness-source.json")["commit"] != HARNESS
        or sha(native / "probes.json") != plan["probes_sha256"]
    ):
        raise ValueError("Wrong observed package/runtime/full cohort")
    payload = next(
        a["payload"]
        for a in read_package(
            (folder / "physical/PL857-low-coast-oceania.crp").read_bytes()
        )[1]
        if a["kind"] == 52
    )
    expected = decode_water(payload)["sources"]
    points = load(folder / "physical/probes.json")["points"]
    domain = load(folder / "domains.json")
    original_count = domain["original_point_count"]
    selected = {
        "original_all": list(range(original_count)),
        "dense_domain": domain["query_point_indices"],
    }
    for name in ["Main Drain", "Bulimba Creek"]:
        selected["original_" + name] = [
            i
            for i, p in enumerate(points[:original_count])
            if p["name"].removeprefix("geography:").split(" [", 1)[0] == name
        ]
    rows, profiles, runtime = [], [], []
    with (native / "timeline.jsonl").open() as stream:
        for line in stream:
            event = json.loads(line)
            if event.get("kind") == "water_study_runtime":
                runtime.append(event)
            if event.get("kind") != "water_study_snapshot":
                continue
            samples = event["samples"]
            if len(samples) != len(points) or any(
                s["name"] != p["name"]
                or max(abs(s["x"] - p["x"]), abs(s["z"] - p["z"])) > 0.001
                for s, p in zip(samples, points)
            ):
                raise ValueError("Full query cohort differs")
            for kind, record in event["files"].items():
                if (
                    sha(native / ("grids/" + event["prefix"] + "-" + kind + ".u16"))
                    != record["sha256"]
                ):
                    raise ValueError("Captured grid identity differs")
            values = [
                [
                    s.get("ground", np.nan),
                    s.get("surface", np.nan),
                    s.get("depth", np.nan),
                    *s.get("velocity", [np.nan] * 3),
                    s.get("max_depth_within_64m", np.nan),
                    float(s["wet"]),
                ]
                for s in [samples[i] for i in domain["query_point_indices"]]
            ]
            a = np.asarray(values, float)
            profiles.append(a)
            rows.append(
                {
                    "prefix": event["prefix"],
                    "minute": event["trigger_game_minute"],
                    "before": event["before"],
                    "after": event["after"],
                    "missed_slots": event["missed_slots"],
                    "floor_sha256": event["files"]["water-ground"]["sha256"],
                    "target_sha256": event["files"]["water-ground-target"]["sha256"],
                    "terrain_sha256": event["files"]["terrain"]["sha256"],
                    "control_mismatches": control_mismatches(
                        event["sources"], expected
                    ),
                    "reported_controls": len(event["sources"]),
                    "dense_nonfinite_values": int(np.count_nonzero(~np.isfinite(a))),
                    "groups": readback_metrics(
                        samples, selected, bool(np.isfinite(a).all())
                    ),
                    "depth_sum_q": event["depth_sum_q"],
                }
            )
    if not rows:
        raise ValueError("No study snapshots; retain raw failure")
    output.mkdir(parents=True)
    np.asarray(profiles, "<f8").tofile(output / "dense-api.f64")
    result = {
        "schema": "polli.coastal-source-record-absent-result/1",
        "native_plan_sha256": sha(folder / "native-plan.json"),
        "samples": rows,
        "snapshots": len(rows),
        "query_nodes": len(domain["query_point_indices"]),
        "query_points": len(points),
        "original_points": original_count,
        "dense_profile_fields": FIELDS,
        "dense_profile_shape": list(np.asarray(profiles).shape),
        "dense_api_sha256": sha(output / "dense-api.f64"),
        "elapsed_minutes": rows[-1]["minute"],
        "max_trigger_gap_minutes": float(np.diff([r["minute"] for r in rows]).max())
        if len(rows) > 1
        else None,
        "missed_slots": missed_slot_count(rows),
        "all_control_tables_match": all(not r["control_mismatches"] for r in rows),
        "runtime_metadata": runtime,
        "raw_verdict_sha256": sha(native / "verdict.json"),
        "raw_verdict": load(native / "verdict.json")["verdict"],
        "full_hour_acceptance": "incomplete/unknown;15minute diagnostic",
        "loaded_image_identity_runtime_health_flux_and_evaporation": "unknown",
        "stable_water_promise": "unknown",
    }
    write(output / "result.json", result)
    write(
        output / "receipt.json",
        {
            "native_plan_sha256": sha(folder / "native-plan.json"),
            "result_sha256": sha(output / "result.json"),
            "dense_api_sha256": sha(output / "dense-api.f64"),
            "native_files_sha256": {
                str(p.relative_to(native)): sha(p)
                for p in sorted(native.rglob("*"))
                if p.is_file()
            },
        },
    )
    return {
        "snapshots": len(rows),
        "all_controls_match": result["all_control_tables_match"],
        "result_sha256": sha(output / "result.json"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, args in [
        ("prepare", ["parent", "harness", "output"]),
        ("preflight", ["folder", "harness"]),
        ("collect", ["folder", "native", "harness", "output"]),
    ]:
        p = commands.add_parser(name)
        for name_arg in args:
            p.add_argument(name_arg, type=Path)
    args = vars(parser.parse_args())
    print(json.dumps(globals()[args.pop("command")](**args), indent=2))
