"""Complete source-selected interface observations from immutable retained native data."""

import argparse
from collections import defaultdict
import itertools
import json
import math
from pathlib import Path
import shutil

import numpy as np

from coupled_interface_contract import preflight as construction_preflight
from water_codec_audit import ROOT, check_files, load, write
from coastal_short_study import control_mismatches
from crp import read_package
from water_diagnostics import decode_water

POLICY = "complete-source-retained-interface-observation-v1"
DESIGN = "calibration/pl1191-construction-v1/development/phase34-interface-policy.md"
FILES = (
    "diagnostics/interface_observation.py",
    "diagnostics/test_interface_observation.py",
    DESIGN,
)
PACKAGE = "457905c4a00cc6e83ab1f40a84feb2fa8888fa50de1bf4702bb082f1a55ed563"
PROBES = "8b375da5c1db35e486a50931217cc8ccb50ae73cfe1fc8f7a0b185c2eee1daf5"
HARNESS = "e73138f45e6cc8959aa2a8be8d55caddd8fdcfa9"
DLL = "368955b1f0b0855c80b8078bf22805fcd7f8f8db8e0428218f262bd37eda6346"
FLOOR = "43f4be737024a039fa72c8ed651b4091272e1a9772238e53923d2a995443b138"
FIELDS = ("ground", "surface", "depth", "vx", "vy", "vz", "nearby_depth", "wet")
SIZE = 1081


def hash_file(p):
    import hashlib

    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(4000000), b""):
            h.update(block)
    return h.hexdigest()


def sample_location(xz):
    if len(xz) != 2 or not all(math.isfinite(v) for v in xz):
        raise ValueError("Finite x,z source coordinates required")
    x, z = map(float, xz)
    if max(abs(x), abs(z)) > 8640:
        return {"native_node": None, "status": "outside_square", "source_xz": [x, z]}
    c, r = round((x + 8640) / 16), round((z + 8640) / 16)
    sx, sz = c * 16 - 8640, r * 16 - 8640
    return {
        "source_xz": [x, z],
        "native_node": r * SIZE + c,
        "native_rc": [r, c],
        "sample_xz": [sx, sz],
        "source_to_sample_m": math.hypot(sx - x, sz - z),
        "status": "diagnostic_grid_sample_not_source_or_probe_replacement",
    }


def north_cell(rc):
    if len(rc) != 2 or any(type(v) is not int or not 0 <= v < SIZE for v in rc):
        raise ValueError("Original north-first native-cell domain invalid")
    r, c = rc
    return [c * 16 - 8640, 8640 - r * 16]


def exact_query_node(point):
    s = sample_location([point["x"], point["z"]])
    if s["native_node"] is None:
        return None
    return (
        s["native_node"]
        if max(abs(a - b) for a, b in zip(s["source_xz"], s["sample_xz"], strict=True))
        <= 0.001
        else None
    )


def projected_points(record):
    kind = record.get("kind")
    if kind == "point" and "xz_m" in record:
        return [record["xz_m"]]
    if kind == "overlap" and "endpoints_xz_micro" in record:
        return [[x / 1000000, z / 1000000] for x, z in record["endpoints_xz_micro"]]
    raise ValueError("Unsupported original projected-intersection schema")


def cohort(boundary, joint, probes):
    topology = boundary["complete_source_topology"]
    literal = defaultdict(list)
    for ji, junction in enumerate(topology["literal_source_junctions"]):
        participants = sorted({v["clip_id"] for v in junction["incidence"]})
        for pair in itertools.combinations(participants, 2):
            for inc in junction["incidence"]:
                if inc["clip_id"] in pair:
                    clip = topology["clips"][inc["clip_id"]]
                    literal[pair].append(
                        (
                            f"literal_junction:{ji}:{inc['clip_id']}:{inc['clip_vertex']}",
                            clip["points_xz"][inc["clip_vertex"]],
                        )
                    )
    contracts = defaultdict(list)
    for c in joint["contracts"]:
        contracts[c["entry_id"]].append(c)
    sites, all_nodes = [], set()
    for s in boundary["all_boundary_sites"]:
        raw, occurrences = s["original_source_record"], []

        def add(kind, source_ref, xz, extra=None):
            value = {
                "kind": kind,
                "source_reference": source_ref,
                **sample_location(xz),
            }
            if extra:
                value.update(extra)
            occurrences.append(value)

        if s["kind"] == "endpoint":
            add(
                "original_clipped_endpoint",
                "point_xz",
                raw["point_xz"],
                {"literal_outside_faces": raw["literal_outside_faces"]},
            )
        elif s["kind"] in ("line", "body"):
            for key in ("shared_native_nodes_rc", "native_raster_contact"):
                for i, rc in enumerate(raw.get(key, [])):
                    add(
                        "original_north_first_raster_contact",
                        f"{key}:{i}",
                        north_cell(rc),
                        {"original_north_rc": rc},
                    )
            for key in ("projected_1um_incidence", "projected_1um_intersections"):
                for i, record in enumerate(raw.get(key, [])):
                    for k, xz in enumerate(projected_points(record)):
                        add("original_projected_intersection", f"{key}:{i}:{k}", xz)
            if s["kind"] == "line":
                pair = tuple(sorted([raw["a_clip"], raw["b_clip"]]))
                for ref, xz in literal[pair]:
                    add("literal_captured_vertex_alias", ref, xz)
            if "path_vertex_membership" in raw:
                points = topology["clips"][raw["clip_id"]]["points_xz"]
                if len(points) != len(raw["path_vertex_membership"]):
                    raise ValueError(
                        "Original membership does not cover full clip vertices"
                    )
                for i, (xz, member) in enumerate(
                    zip(points, raw["path_vertex_membership"], strict=True)
                ):
                    add(
                        "complete_clip_vertex_membership",
                        f"clip_vertex:{i}",
                        xz,
                        {"membership": member},
                    )
        elif s["kind"] == "body-domain":
            for c in contracts[s["participants"][0]]:
                for i, point in enumerate(c["points"]):
                    add(
                        "complete_original_source_contract_point",
                        f"contract:{c['contract']['id']}:point:{i}",
                        point["point_xz"],
                        {"original_point_f32_xz": point.get("point_f32_xz")},
                    )
        elif s["kind"] not in ("authored-plan-domain", "unsupported-entry-domain"):
            raise ValueError("Unknown boundary-site kind")
        nodes = sorted(
            {v["native_node"] for v in occurrences if v["native_node"] is not None}
        )
        all_nodes.update(nodes)
        sites.append(
            {
                "site_id": s["id"],
                "site_kind": s["kind"],
                "active_potential": s["active_potential_interface_or_endpoint"],
                "source_record_sha256": s["original_source_record_sha256"],
                "participants": s["participants"],
                "occurrences": occurrences,
                "native_nodes": nodes,
                "support_status": "source_selected_grid_observations"
                if nodes
                else "no_in_square_source_observation_support_unknown_not_zero",
                "no_stage_direction_or_capacity_authority": True,
            }
        )
    nodes = sorted(all_nodes)
    selected = []
    for i, p in enumerate(probes["points"]):
        n = exact_query_node(p)
        if n is not None and n in all_nodes:
            selected.append(
                {
                    "original_query_index": i,
                    "name": p["name"],
                    "x": p["x"],
                    "z": p["z"],
                    "native_node": n,
                }
            )
    return {
        "policy": POLICY,
        "sites": sites,
        "native_nodes": nodes,
        "api_queries": selected,
        "all_original_query_objects_unchanged": True,
        "new_native_queries": 0,
        "grid_fields": [
            "current_floor_q",
            "target_floor_q",
            "depth_q",
            "wet_head_q_or_minus1",
        ],
        "api_fields": list(FIELDS),
        "grid_order": "south-first: z=-8640+16r, x=-8640+16c",
        "source_order": "north-first: z=8640-16r",
        "quantization": "nearest16m, ties-to-even; explicit displacement; not source movement",
        "missing_API": "all matching aliases retained; no query means unknown/NaN, never zero",
    }


def stage(
    construction, boundary_results, observation, native, old_results, harness, output
):
    if output.exists():
        raise ValueError("Fresh complete-interface protocol required")
    f = construction_preflight(construction)
    br = load(boundary_results / "receipt.json")
    if br["input_freeze_sha256"] != hash_file(construction / "freeze.json"):
        raise ValueError("Wrong boundary result lineage")
    check_files(boundary_results, br["files_sha256"])
    plan, receipt, result = (
        load(observation / "native-plan.json"),
        load(old_results / "receipt.json"),
        load(old_results / "result.json"),
    )
    if (
        plan["package_sha256"] != PACKAGE
        or plan["probes_sha256"] != PROBES
        or plan["harness_source"] != HARNESS
        or plan["mod_sha256"] != DLL
    ):
        raise ValueError("Wrong retained physical/source/runtime protocol")
    if (
        len(receipt["native_files_sha256"]) != 289
        or result["snapshots"] != 61
        or result["native_plan_sha256"] != hash_file(observation / "native-plan.json")
    ):
        raise ValueError("Wrong retained complete observation")
    if (
        hash_file(old_results / "result.json") != receipt["result_sha256"]
        or hash_file(old_results / "dense-api.f64") != receipt["dense_api_sha256"]
    ):
        raise ValueError("Retained derived observations changed")
    for root, files in (
        (observation, plan["files_sha256"]),
        (native, receipt["native_files_sha256"]),
        (harness, plan["harness_files_sha256"]),
        (ROOT, plan["source_files_sha256"]),
    ):
        for n, h in files.items():
            if hash_file(root / n) != h:
                raise ValueError(f"Changed retained input: {n}")
    session = load(native / "session-receipt.json")
    if (
        session["map"]["sha256"] != PACKAGE
        or session["mod_sha256"] != DLL
        or load(native / "harness-source.json")["commit"] != HARNESS
        or hash_file(native / "probes.json") != PROBES
    ):
        raise ValueError("Wrong actual retained session identity")
    geometry = [
        p
        for p in construction.rglob("geometry.json")
        if "low-coast-oceania" in p.parts and p.parent.name == "physical"
    ]
    if (
        len(geometry) != 1
        or hash_file(geometry[0]) != hash_file(observation / "physical/geometry.json")
        or hash_file(native / "grids/ws000000-water-ground.u16") != FLOOR
        or hash_file(native / "grids/t000-terrain.u16")
        != hash_file(observation / "physical/terrain.u16")
    ):
        raise ValueError(
            "Exact source geometry/package terrain/actual floor lineage mismatch"
        )
    output.mkdir(parents=True)
    shutil.copytree(construction, output / "construction")
    shutil.copytree(boundary_results, output / "boundary-results")
    for label, root, files in (
        ("observation", observation, plan["files_sha256"]),
        ("native", native, receipt["native_files_sha256"]),
        ("historical-runtime", harness, plan["harness_files_sha256"]),
        ("historical-observer", ROOT, plan["source_files_sha256"]),
    ):
        for n in files:
            target = output / label / n
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / n, target)
    shutil.copyfile(
        observation / "native-plan.json", output / "observation/native-plan.json"
    )
    shutil.copytree(old_results, output / "retained-results")
    joint = load(output / "construction/prior/joint-results/low-coast-oceania.json")
    c = cohort(
        load(output / "boundary-results/low-coast-oceania.json"),
        joint,
        load(output / "observation/physical/probes.json"),
    )
    write(output / "cohort.json", c)
    deps = dict(f["source_files_sha256"])
    deps.update({n: hash_file(ROOT / n) for n in FILES})
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": f["cases"],
            "source_files_sha256": deps,
            "files_sha256": {
                str(p.relative_to(output)): hash_file(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "prior_observations_known": True,
            "new_complete_cohort_outputs_not_yet_computed": True,
            "no_new_physical_or_native": True,
        },
    )


def preflight(folder):
    f = load(folder / "freeze.json")
    if f["policy"] != POLICY:
        raise ValueError("Wrong complete-interface protocol")
    check_files(ROOT, f["source_files_sha256"])
    for n, h in f["files_sha256"].items():
        if hash_file(folder / n) != h:
            raise ValueError(f"Changed copied input: {n}")
    return f


def wet_heads(floor, depth):
    h = floor.astype(np.int32) + depth.astype(np.int32)
    h[depth == 0] = -1
    return h


def api_row(sample):
    vector = sample.get("velocity")
    vector = (
        vector if isinstance(vector, list) and len(vector) == 3 else [float("nan")] * 3
    )
    return [
        sample.get("ground", float("nan")),
        sample.get("surface", float("nan")),
        sample.get("depth", float("nan")),
        *vector,
        sample.get("max_depth_within_64m", float("nan")),
        float(sample["wet"]) if type(sample.get("wet")) is bool else float("nan"),
    ]


def summarize_heads(heads, depths, reference_q):
    observed = heads >= 0
    values = heads[observed]
    return {
        "positive_depth_samples": int(observed.sum()),
        "depth_ge7q_samples": int((depths >= 7).sum()),
        "observed_head_q_min": int(values.min()) if values.size else None,
        "observed_head_q_max": int(values.max()) if values.size else None,
        "wet_heads_all_equal_reference": bool(np.all(values == reference_q))
        if values.size
        else None,
        "nonreference_wet_samples": int((values != reference_q).sum()),
        "dry_floor_not_a_head": True,
    }


def evaluate(folder, output):
    f = preflight(folder)
    if output.exists():
        raise ValueError("Fresh complete-interface result required")
    c, prior = (
        load(folder / "cohort.json"),
        load(folder / "retained-results/result.json"),
    )
    nodes = np.array(c["native_nodes"], dtype=np.int64)
    lookup = {n: i for i, n in enumerate(c["native_nodes"])}
    queries = c["api_queries"]
    if prior["dense_profile_fields"] != list(FIELDS) or prior[
        "dense_profile_shape"
    ] != [61, 20049, 8]:
        raise ValueError("Unsupported retained dense-array schema")
    dense = np.memmap(
        folder / "retained-results/dense-api.f64",
        dtype="<f8",
        mode="r",
        shape=(61, 20049, 8),
    )
    dense_indices = {
        q: i
        for i, q in enumerate(
            load(folder / "observation/domains.json")["query_point_indices"]
        )
    }
    overlap = [
        (i, dense_indices[q["original_query_index"]])
        for i, q in enumerate(queries)
        if q["original_query_index"] in dense_indices
    ]
    probes = load(folder / "observation/physical/probes.json")["points"]
    payload = next(
        a["payload"]
        for a in read_package(
            (folder / "observation/physical/PL857-low-coast-oceania.crp").read_bytes()
        )[1]
        if a["kind"] == 52
    )
    physical = decode_water(payload)
    expected_controls = physical["sources"]
    reference_q = round(physical["sea_level_m"] * 64)
    output.mkdir(parents=True)
    grids = np.memmap(
        output / "interface-grid.i32", dtype="<i4", mode="w+", shape=(61, len(nodes), 4)
    )
    apis = np.memmap(
        output / "interface-api.f64",
        dtype="<f8",
        mode="w+",
        shape=(61, len(queries), 8),
    )
    apis[:] = np.nan
    metadata, index = [], 0
    with (folder / "native/timeline.jsonl").open() as stream:
        for line in stream:
            e = json.loads(line)
            if e.get("kind") != "water_study_snapshot":
                continue
            if (
                index >= 61
                or e["sequence"] != index
                or e["prefix"] != prior["samples"][index]["prefix"]
                or e["trigger_game_minute"] != prior["samples"][index]["minute"]
                or e["before"] != prior["samples"][index]["before"]
                or e["after"] != prior["samples"][index]["after"]
            ):
                raise ValueError("Retained capture/time/counter identity changed")
            if control_mismatches(e["sources"], expected_controls):
                raise ValueError("Retained complete control table changed")
            samples = e["samples"]
            if len(samples) != len(probes):
                raise ValueError("Retained complete query cohort changed")
            for p, s in zip(probes, samples, strict=True):
                if (
                    s["name"] != p["name"]
                    or max(abs(s[k] - p[k]) for k in ("x", "z")) > 0.001
                ):
                    raise ValueError("Retained query name/position changed")
            selected = {}
            files = {}
            for kind, rec in e["files"].items():
                name = f"grids/{e['prefix']}-{kind}.u16"
                p = folder / "native" / name
                if hash_file(p) != rec["sha256"] or p.stat().st_size != rec["bytes"]:
                    raise ValueError("Raw recorded grid identity mismatch")
                a = np.fromfile(p, "<u2")
                if a.size != SIZE * SIZE:
                    raise ValueError("Wrong native raster shape")
                selected[kind] = a[nodes]
                files[kind] = {
                    "native_relative_path": name,
                    "sha256": rec["sha256"],
                    "bytes": rec["bytes"],
                }
            grids[index, :, 0] = selected["water-ground"]
            grids[index, :, 1] = selected["water-ground-target"]
            grids[index, :, 2] = selected["water"]
            grids[index, :, 3] = wet_heads(selected["water-ground"], selected["water"])
            for qi, q in enumerate(queries):
                s = samples[q["original_query_index"]]
                if exact_query_node(s) != q["native_node"]:
                    raise ValueError("Exact-grid API alias changed")
                apis[index, qi] = api_row(s)
            if any(
                not np.array_equal(apis[index, a], dense[index, b], equal_nan=True)
                for a, b in overlap
            ):
                raise ValueError(
                    "Full-query extraction disagrees with unchanged dense API bytes"
                )
            metadata.append(
                {
                    k: e[k]
                    for k in (
                        "sequence",
                        "prefix",
                        "trigger_game_minute",
                        "scheduled_slot",
                        "scheduled_minute",
                        "missed_slots",
                        "before",
                        "after",
                        "sources",
                        "depth_sum_q",
                        "wet_nodes",
                        "scope",
                        "final",
                    )
                }
                | {"files": files}
            )
            index += 1
    if index != 61:
        raise ValueError("Incomplete retained snapshot sequence")
    grids.flush()
    apis.flush()
    write(output / "snapshots.json", metadata)
    aliases = defaultdict(list)
    for qi, q in enumerate(queries):
        aliases[q["native_node"]].append(qi)
    api_node_count = len(aliases)
    per_node = [
        {
            "native_node": int(n),
            "grid_column": i,
            "all_api_alias_columns": aliases.get(int(n), []),
            **summarize_heads(grids[:, i, 3], grids[:, i, 2], reference_q),
        }
        for i, n in enumerate(nodes)
    ]
    write(output / "nodes.json", per_node)
    summaries = []
    for s in c["sites"]:
        ids = [lookup[n] for n in s["native_nodes"]]
        api_ids = sorted(qi for n in s["native_nodes"] for qi in aliases.get(n, []))
        summaries.append(
            {
                "site_id": s["site_id"],
                "site_kind": s["site_kind"],
                "active_potential": s["active_potential"],
                "support_status": s["support_status"],
                "grid_columns": ids,
                "all_api_alias_columns": api_ids,
                "whole_trace_values_in_bound_binary_arrays": True,
                "snapshots": [
                    {
                        "prefix": m["prefix"],
                        "minute": m["trigger_game_minute"],
                        **summarize_heads(
                            grids[i, ids, 3], grids[i, ids, 2], reference_q
                        ),
                        "finite_vector_aliases": int(
                            np.isfinite(apis[i, api_ids, 3:6]).all(axis=1).sum()
                        ),
                    }
                    for i, m in enumerate(metadata)
                ],
            }
        )
    write(output / "sites.json", summaries)
    for name in f["cases"]:
        if name != "low-coast-oceania":
            b = load(folder / "boundary-results" / f"{name}.json")
            write(
                output / f"{name}.json",
                {
                    "case": name,
                    "boundary_result_sha256": hash_file(
                        folder / "boundary-results" / f"{name}.json"
                    ),
                    "status": "NULL_original_support_unknown"
                    if b.get("retained_base_refusal")
                    else "authored_only_native_interface_observations_unknown",
                    "coastal_native_qualification_transferred": False,
                    "all_source_sites_and_contracts_preserved_in_input": True,
                },
            )
    times = [m["trigger_game_minute"] for m in metadata]
    write(
        output / "result.json",
        {
            "policy": POLICY,
            "case": "low-coast-oceania",
            "site_records": len(c["sites"]),
            "sites_with_grid_support": sum(bool(s["native_nodes"]) for s in c["sites"]),
            "unique_grid_nodes": len(nodes),
            "api_query_aliases": len(queries),
            "nodes_with_API_alias": api_node_count,
            "nodes_missing_API_vectors_unknown": len(nodes) - api_node_count,
            "grid_shape": list(grids.shape),
            "grid_fields": c["grid_fields"],
            "api_shape": list(apis.shape),
            "api_fields": list(FIELDS),
            "grid_sha256": hash_file(output / "interface-grid.i32"),
            "api_sha256": hash_file(output / "interface-api.f64"),
            "reference_stage_q": reference_q,
            "reference_is_serialized_sea_parameter_not_all61_endpoint_measurements": True,
            "nodes_with_nonreference_wet_heads": sum(
                n["nonreference_wet_samples"] > 0 for n in per_node
            ),
            "nodes_never_positive_depth": sum(
                n["positive_depth_samples"] == 0 for n in per_node
            ),
            "nodes_with_variable_observed_wet_heads": sum(
                n["observed_head_q_min"] != n["observed_head_q_max"]
                for n in per_node
                if n["observed_head_q_min"] is not None
            ),
            "minutes": times,
            "max_gap_minutes": max(np.diff(times)),
            "missed_slots": sum(len(m["missed_slots"]) for m in metadata),
            "ordinary_sea_readbacks": prior["ordinary_counters"],
            "raw_verdict": prior["raw_verdict"],
            "raw_verdict_sha256": prior["raw_verdict_sha256"],
            "read_brackets_not_atomic": True,
            "full_hour_primary_acceptance": "incomplete/unknown; retained15min only",
            "boundary_stage_direction_supply_capacity_authority": None,
            "loaded_image_JIT_identity_runtime_health": "unknown",
            "physical_admission": False,
            "promise": "unknown",
        },
    )
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "input_freeze_sha256": hash_file(folder / "freeze.json"),
            "files_sha256": {
                p.name: hash_file(p) for p in sorted(output.iterdir()) if p.is_file()
            },
            "new_game_or_physical": False,
        },
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest="command", required=True)
    a = s.add_parser("stage")
    for k in (
        "construction",
        "boundary_results",
        "observation",
        "native",
        "old_results",
        "harness",
        "output",
    ):
        a.add_argument(k, type=Path)
    a = s.add_parser("preflight")
    a.add_argument("folder", type=Path)
    a = s.add_parser("evaluate")
    a.add_argument("folder", type=Path)
    a.add_argument("output", type=Path)
    a = p.parse_args()
    if a.command == "stage":
        stage(
            a.construction,
            a.boundary_results,
            a.observation,
            a.native,
            a.old_results,
            a.harness,
            a.output,
        )
    elif a.command == "preflight":
        preflight(a.folder)
    else:
        evaluate(a.folder, a.output)


if __name__ == "__main__":
    main()
