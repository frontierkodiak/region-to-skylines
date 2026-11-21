"""Frozen source-selected dense coastal API queries; no physical intervention."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np
from scipy import ndimage

from bank_authority import ROOT, load, write
from coastal_floor_audit import PACKAGE_SHA, PROBES_SHA, source_domains
from coastal_short_study import DLL, control_mismatches, git, metrics
from coastal_transport_witness import aligned_node
from crp import read_package
from water_diagnostics import decode_water

HARNESS = "e73138f45e6cc8959aa2a8be8d55caddd8fdcfa9"
DESIGN = (
    "calibration/pl1191-construction-v1/development/phase17-dense-interface-policy.md"
)
FIELDS = ("ground", "surface", "depth", "vx", "vy", "vz", "nearby_depth", "wet")


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def query_domain(geometry, paths):
    domains = source_domains(geometry)
    source = np.zeros((1081, 1081), bool)
    for _, mask in domains:
        source |= mask
    corridor = np.zeros_like(source)
    by_id = {entry["id"]: entry for entry, _ in domains}
    for feature in paths["features"]:
        original = by_id[feature["id"]]
        if (
            original["source_sha256"] != feature["source_sha256"]
            or original["name"] != feature["name"]
        ):
            raise ValueError("Source-piece identity differs from frozen corridors")
        if original["name"] == "Main Drain":
            for path in feature["paths"]:
                if path["kind"] == "subsea_shortest":
                    corridor.ravel()[path["nodes"]] = True
    domain = ndimage.binary_dilation(source, np.ones((3, 3)), iterations=8)
    domain |= ndimage.binary_dilation(corridor, np.ones((3, 3)), iterations=2)
    return domain, [entry for entry, _ in domains]


def augment(original, nodes):
    new = copy.deepcopy(original)
    points = new["points"]
    existing = {}
    for i, point in enumerate(points):
        node = aligned_node(point, 1081)
        if node is not None:
            existing.setdefault(node, i)
    names = {p["name"] for p in points}
    selected = []
    for node in nodes:
        node = int(node)
        if node not in existing:
            r, c = divmod(node, 1081)
            name = f"dense-source-interface-v1:{r},{c}"
            if name in names:
                raise ValueError("Diagnostic query name collision")
            existing[node] = len(points)
            points.append(
                {
                    "name": name,
                    "x": c * 16 - 8640,
                    "z": r * 16 - 8640,
                    "required": False,
                    "diagnostic": "source-selected interface, not primary qualification",
                }
            )
            names.add(name)
        selected.append(existing[node])
    if len(points) > 100000:
        raise ValueError(
            "Complete query budget exceeded; never truncate source domains"
        )
    return new, selected


def runtime_check(harness):
    if git(harness, "rev-parse", "HEAD") != HARNESS or git(
        harness, "status", "--porcelain"
    ):
        raise ValueError("Owned exact clean e73138f runtime required until collection")
    project = harness / "tools/cs1-harness"
    receipt = load(project / ".build/build-receipt.json")
    if sha(project / ".build/Cs1Harness.dll") != DLL or receipt["dll_sha256"] != DLL:
        raise ValueError("Bound runtime DLL differs")
    for name, expected in receipt["sources"].items():
        if sha(project / "mod" / name) != expected:
            raise ValueError("Build source changed")
    sys.path.insert(0, str(project))
    from cs1_harness.config import Config

    cfg = Config.for_host("blade")
    for name, expected in receipt["game_assemblies"].items():
        if sha(cfg.game_dir / "Cities_Data/Managed" / name) != expected:
            raise ValueError("On-disk compile reference changed")


def readback_metrics(samples, selected, dense_finite):
    try:
        if not dense_finite:
            raise ValueError("Nonfinite dense readbacks")
        return metrics(samples, selected)
    except (ValueError, KeyError, TypeError) as error:
        return {
            "status": "unknown; raw readback failure retained",
            "detail": str(error),
        }


def prepare(parent, witness, review, output, harness):
    runtime_check(harness)
    if output.exists():
        raise ValueError("Fresh prospective dense protocol required")
    if (
        sha(parent / "physical/PL857-low-coast-oceania.crp") != PACKAGE_SHA
        or sha(parent / "physical/probes.json") != PROBES_SHA
    ):
        raise ValueError("Wrong original physical cohort")
    output.mkdir(parents=True)
    shutil.copytree(parent / "physical", output / "physical")
    shutil.copyfile(parent / "native-plan.json", output / "parent-native-plan.json")
    shutil.copyfile(witness / "analysis/paths.json", output / "geometric-paths.json")
    shutil.copyfile(
        witness / "prospective-freeze.json", output / "geometric-input-freeze.json"
    )
    shutil.copyfile(review, output / "review.json")
    shutil.copyfile(
        output / "physical/probes.json", output / "physical/original-probes.json"
    )
    original = load(output / "physical/original-probes.json")
    domain, features = query_domain(
        load(output / "physical/geometry.json"), load(output / "geometric-paths.json")
    )
    nodes = np.flatnonzero(domain).astype("<i4")
    new, indices = augment(original, nodes)
    write(output / "physical/probes.json", new)
    nodes.tofile(output / "query-nodes.i32")
    write(
        output / "domains.json",
        {
            "source_features": features,
            "source_buffer_cells": 8,
            "all_static_Main_corridor_buffer_cells": 2,
            "query_nodes": int(nodes.size),
            "query_point_indices": indices,
            "original_point_count": len(original["points"]),
            "total_point_count": len(new["points"]),
            "added_points": len(new["points"]) - len(original["points"]),
            "wet_outcome_selection": False,
            "construction_or_mask_change": False,
        },
    )
    dependencies = {
        str(p.relative_to(ROOT)): sha(p)
        for d in (ROOT, ROOT / "diagnostics")
        for p in d.glob("*.py")
        if not p.name.startswith("test_")
    }
    for name in (
        DESIGN,
        "pyproject.toml",
        "uv.lock",
        "calibration/pl1191-construction-v1/maintained-water-definition.json",
        "calibration/pl1191-construction-v1/outcome-freeze.json",
    ):
        dependencies[name] = sha(ROOT / name)
    project = harness / "tools/cs1-harness"
    runtime = {
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
        runtime[str((project / name).relative_to(harness))] = sha(project / name)
    write(
        output / "native-plan.json",
        {
            "schema": "polli.coastal-dense-study-protocol/1",
            "question": "Dense source-selected head/velocity readbacks during coastal drawdown; not proof of flux or evaporation",
            "game_minutes": 15,
            "water_study_every": 0.25,
            "harness_source": HARNESS,
            "mod_sha256": DLL,
            "package_sha256": PACKAGE_SHA,
            "original_probes_sha256": PROBES_SHA,
            "probes_sha256": sha(output / "physical/probes.json"),
            "source_files_sha256": dependencies,
            "harness_files_sha256": runtime,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "full_hour_acceptance": "incomplete/unknown; diagnostic15minutes only",
            "new_physical_forcing": False,
            "pre_native_review_gate": False,
            "holdout_inputs_accessed": False,
            "stable_water_promise": "unknown",
        },
    )
    preflight(output, harness)
    return {
        "native_plan_sha256": sha(output / "native-plan.json"),
        **load(output / "domains.json")
        | {
            "source_features": len(features),
            "query_point_indices": "bound in domains.json",
        },
    }


def preflight(folder, harness):
    plan = load(folder / "native-plan.json")
    if (
        plan["schema"] != "polli.coastal-dense-study-protocol/1"
        or plan["game_minutes"] != 15
        or plan["water_study_every"] != 0.25
    ):
        raise ValueError("Wrong fixed dense question")
    runtime_check(harness)
    for field, root in (
        ("source_files_sha256", ROOT),
        ("harness_files_sha256", harness),
        ("files_sha256", folder),
    ):
        for name, expected in plan[field].items():
            if sha(root / name) != expected:
                raise ValueError(f"Bound bytes changed: {name}")
    if (
        sha(folder / "physical/PL857-low-coast-oceania.crp") != PACKAGE_SHA
        or sha(folder / "physical/original-probes.json") != PROBES_SHA
    ):
        raise ValueError("Original package/cohort changed")
    original = load(folder / "physical/original-probes.json")
    nodes = np.fromfile(folder / "query-nodes.i32", "<i4")
    domain, _ = query_domain(
        load(folder / "physical/geometry.json"), load(folder / "geometric-paths.json")
    )
    if not np.array_equal(nodes, np.flatnonzero(domain)):
        raise ValueError("Complete source query domain differs")
    expected, indices = augment(original, nodes)
    if (
        expected != load(folder / "physical/probes.json")
        or indices != load(folder / "domains.json")["query_point_indices"]
    ):
        raise ValueError("Original+diagnostic cohort differs")
    for name, expected_sha in load(folder / "parent-native-plan.json")[
        "files_sha256"
    ].items():
        if (
            name.startswith("physical/")
            and name != "physical/probes.json"
            and sha(folder / name) != expected_sha
        ):
            raise ValueError("Non-probe physical input changed")
    return {
        "preflight_pass": True,
        "native_plan_sha256": sha(folder / "native-plan.json"),
    }


def collect(folder, native, harness, output):
    preflight(folder, harness)
    if output.exists():
        raise ValueError("Fresh collection output required")
    plan = load(folder / "native-plan.json")
    session = load(native / "session-receipt.json")
    if (
        session["map"]["sha256"] != PACKAGE_SHA
        or session["mod_sha256"] != DLL
        or sha(native / "probes.json") != plan["probes_sha256"]
        or load(native / "harness-source.json")["commit"] != HARNESS
    ):
        raise ValueError("Wrong observed package/runtime/cohort")
    payload = next(
        a["payload"]
        for a in read_package(
            (folder / "physical/PL857-low-coast-oceania.crp").read_bytes()
        )[1]
        if a["kind"] == 52
    )
    expected_controls = decode_water(payload)["sources"]
    points = load(folder / "physical/probes.json")["points"]
    domain = load(folder / "domains.json")
    original_count = domain["original_point_count"]
    selected = {
        "original_all": list(range(original_count)),
        "dense_domain": domain["query_point_indices"],
    }
    for name in ("Main Drain", "Bulimba Creek"):
        selected["original_" + name] = [
            i
            for i, p in enumerate(points[:original_count])
            if p["name"].removeprefix("geography:").split(" [", 1)[0] == name
        ]
    rows, profiles, ordinary, runtime = [], [], [], []
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
                        "water_frame": e["water"]["frame"],
                        "sea_level": e["water"]["sea_level"],
                    }
                )
            if e.get("kind") != "water_study_snapshot":
                continue
            samples = e["samples"]
            if len(samples) != len(points) or any(
                s["name"] != p["name"]
                or max(abs(s["x"] - p["x"]), abs(s["z"] - p["z"])) > 0.001
                for s, p in zip(samples, points)
            ):
                raise ValueError("Complete query identity changed")
            for kind, record in e["files"].items():
                if sha(native / f"grids/{e['prefix']}-{kind}.u16") != record["sha256"]:
                    raise ValueError("Raw grid hash differs")
            values = []
            for i in domain["query_point_indices"]:
                s = samples[i]
                v = s.get("velocity")
                vector = (
                    v if isinstance(v, list) and len(v) == 3 else [float("nan")] * 3
                )
                values.append(
                    [
                        s.get("ground", float("nan")),
                        s.get("surface", float("nan")),
                        s.get("depth", float("nan")),
                        *vector,
                        s.get("max_depth_within_64m", float("nan")),
                        float(s["wet"])
                        if isinstance(s.get("wet"), bool)
                        else float("nan"),
                    ]
                )
            a = np.asarray(values, "<f8")
            profiles.append(a)
            finite = bool(np.isfinite(a).all())
            rows.append(
                {
                    "prefix": e["prefix"],
                    "minute": e["trigger_game_minute"],
                    "before": e["before"],
                    "after": e["after"],
                    "missed_slots": e["missed_slots"],
                    "floor_sha256": e["files"]["water-ground"]["sha256"],
                    "target_sha256": e["files"]["water-ground-target"]["sha256"],
                    "terrain_sha256": e["files"]["terrain"]["sha256"],
                    "control_mismatches": control_mismatches(
                        e["sources"], expected_controls
                    ),
                    "reported_controls": len(e["sources"]),
                    "dense_nonfinite_values": int(np.count_nonzero(~np.isfinite(a))),
                    "groups": readback_metrics(samples, selected, finite),
                    "depth_sum_q": e["depth_sum_q"],
                }
            )
    if not rows:
        raise ValueError("No study captures; retain raw failure")
    output.mkdir(parents=True)
    np.asarray(profiles, "<f8").tofile(output / "dense-api.f64")
    times = [r["minute"] for r in rows]
    result = {
        "schema": "polli.coastal-dense-study-result/1",
        "native_plan_sha256": sha(folder / "native-plan.json"),
        "snapshots": len(rows),
        "query_nodes": domain["query_nodes"],
        "query_points": len(points),
        "original_points": original_count,
        "dense_profile_shape": [len(rows), domain["query_nodes"], len(FIELDS)],
        "dense_profile_fields": FIELDS,
        "dense_api_sha256": sha(output / "dense-api.f64"),
        "samples": rows,
        "ordinary_counters": ordinary,
        "runtime_metadata": runtime,
        "elapsed_minutes": times[-1],
        "max_trigger_gap_minutes": float(np.diff(times).max())
        if len(times) > 1
        else None,
        "missed_slots": sum(len(r["missed_slots"]) for r in rows),
        "all_control_tables_match": all(not r["control_mismatches"] for r in rows),
        "raw_verdict_sha256": sha(native / "verdict.json"),
        "raw_verdict": load(native / "verdict.json").get("verdict", "unknown"),
        "full_hour_acceptance": "incomplete/unknown;15minute diagnostic only",
        "flux_evaporation_and_physical_source_budget": "not established by API readbacks",
        "loaded_image_identity_and_runtime_health": "unknown",
        "stable_water_promise": "unknown",
    }
    write(output / "result.json", result)
    write(
        output / "receipt.json",
        {
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
        k: result[k]
        for k in (
            "snapshots",
            "query_nodes",
            "query_points",
            "elapsed_minutes",
            "all_control_tables_match",
            "raw_verdict",
        )
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, arguments in (
        ("prepare", ("parent", "witness", "review", "output", "harness")),
        ("preflight", ("folder", "harness")),
        ("collect", ("folder", "native", "harness", "output")),
    ):
        command = commands.add_parser(name)
        for argument in arguments:
            command.add_argument(argument, type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps(globals()[command](**args), indent=2))
