"""Fresh source-only remaining-output-zero diagnostic, not controls removed."""

import argparse
import json
from pathlib import Path
import shutil
import sys

import numpy as np

from coastal_dense_study import FIELDS, readback_metrics, sha
from coastal_short_study import DLL, control_mismatches, git

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crp import read_package  # noqa: E402
from water_diagnostics import decode_water, transform  # noqa: E402

HARNESS = "9c41756c9eb364ef99789aec00d173333e73833b"
POLICY = "calibration/pl1191-construction-v1/development/phase19-rate-zero-policy.md"


def load(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def rate_only_change(before, after):
    if len(before) != 167 or len(after) != 167:
        raise ValueError("All167 controls must remain")
    for a, b in zip(before, after):
        expected = dict(a, output_rate=0)
        if a["intake_rate"] != 0 or a["output_rate"] <= 0 or b != expected:
            raise ValueError("Only all167 positive encoded output rates may change")


def missed_slot_count(rows):
    if any(not isinstance(r.get("missed_slots"), list) for r in rows):
        raise ValueError("Missing/malformed missed-slot lists remain unknown")
    return sum(len(r["missed_slots"]) for r in rows)


def patch(parent):
    physical = parent / "physical"
    source = (physical / "PL857-low-coast-oceania.crp").read_bytes()
    hydro = load(physical / "hydrology.json")
    terrain = np.fromfile(physical / "terrain.u16", "<u2").astype(float) / 64
    data, new_hydro, _, receipt = transform(source, hydro, terrain, "all-output-off")
    rate_only_change(receipt["source_controls"], receipt["diagnostic_controls"])
    if receipt["initial_water_changed_cells"]:
        raise ValueError("Initial water must remain unchanged")
    return data, new_hydro, receipt


def runtime_check(harness):
    if git(harness, "rev-parse", "HEAD") != HARNESS or git(
        harness, "status", "--porcelain"
    ):
        raise ValueError("Exact clean owned9c41756 runtime required until collection")
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
        != "ec4b88258310808f7a558c10c8368a384abd99bede88f5864441079b892e130f"
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
    write(output / "rate-only-change.json", receipt)
    parent_plan = load(parent / "native-plan.json")
    sources = (
        list(ROOT.glob("*.py"))
        + list((ROOT / "diagnostics").glob("*.py"))
        + [ROOT / POLICY, ROOT / "uv.lock"]
    )
    plan = {
        "schema": "polli.coastal-remaining-output-zero/1",
        "question": "Are remaining positive encoded output rates necessary for early distant-ocean/channel drawdown under this fixed initialized package? Joint all167 outputs to0; intakes already0. Not sources removed, evaporation proof, repair or primary acceptance.",
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
    if plan["schema"] != "polli.coastal-remaining-output-zero/1":
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
        or receipt != load(folder / "rate-only-change.json")
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
        "schema": "polli.coastal-remaining-output-zero-result/1",
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
