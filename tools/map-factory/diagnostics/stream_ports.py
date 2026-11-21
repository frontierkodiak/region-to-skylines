"""Experimental branch-complete port recipe under unchanged geographic masks.

Fresh CPU protocols only. No CRP/native admission, physical flux budget or
inventory promotion is produced by a numerically feasible profile.
"""

import argparse
from collections import Counter
import heapq
import json
from pathlib import Path
import shutil
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from closed_storage_candidate import ROOT, sha  # noqa: E402
from natural_storage_candidate import write  # noqa: E402
from stream_construction import STEPS, greatest_profile  # noqa: E402
from stream_support_ledger import preflight as prepared_preflight  # noqa: E402
from unprepared_stream_ledger import preflight as refused_preflight  # noqa: E402
from waterway_pieces import catalog, digest  # noqa: E402

POLICY = "branched-head-terminal-recipe-v1"
DEPTH_Q = 96
INTAKE, OUTPUT = 128, 32
NEW_SOURCE = "diagnostics/stream_ports.py"
DESIGN = "calibration/pl1191-construction-v1/development/phase12-stream-port-policy.md"


def load(path):
    return json.loads(path.read_text())


def graph_profile(nodes, edges, floor, water):
    """Quantized grade and full-bank bounds; no direction/budget inference here."""
    if (
        floor.shape != (1081, 1081)
        or water.shape != floor.shape
        or floor.dtype.kind not in "iu"
        or water.dtype.kind not in "iu"
        or np.any(floor < 0)
        or np.any(floor > 65535)
        or np.any(water < 0)
        or np.any(water > 65535)
    ):
        raise ValueError("Expected complete bounded integer authored grids")
    nodes = [tuple(n) for n in nodes]
    if len(set(nodes)) != len(nodes) or not nodes:
        raise ValueError("Expected a nonempty unique complete node catalog")
    edges = sorted(set(tuple(e) for e in edges))
    adjacency = [[] for _ in nodes]
    indegree = [0] * len(nodes)
    for a, b in edges:
        if not (0 <= a < len(nodes) and 0 <= b < len(nodes)) or a == b:
            raise ValueError("Invalid directed source edge")
        if max(abs(nodes[a][i] - nodes[b][i]) for i in (0, 1)) != 1:
            raise ValueError("Source walk skips a native cell")
        adjacency[a].append(b)
        indegree[b] += 1
    if any(not indegree[i] and not adjacency[i] for i in range(len(nodes))):
        return {"status": "unresolved_isolated_stream", "controls": None}
    heads = [i for i, n in enumerate(indegree) if n == 0]
    terminals = [i for i, ns in enumerate(adjacency) if not ns]
    ready = heads.copy()
    heapq.heapify(ready)
    degree = indegree.copy()
    distance = np.zeros(len(nodes), float)
    order = []
    while ready:
        node = heapq.heappop(ready)
        order.append(node)
        for other in adjacency[node]:
            length = float(np.linalg.norm(np.subtract(nodes[node], nodes[other]))) * 16
            distance[other] = max(distance[other], distance[node] + length)
            degree[other] -= 1
            if not degree[other]:
                heapq.heappush(ready, other)
    if len(order) != len(nodes):
        return {
            "status": "unresolved_cycle",
            "controls": None,
            "cycle_nodes": [i for i, d in enumerate(degree) if d],
        }
    own = set(nodes)
    if any(not (0 <= r <= 1080 and 0 <= c <= 1080) for r, c in own):
        return {"status": "unresolved_exterior_bank", "controls": None}
    lower, upper, required = [], [], []
    rim = set()
    for node in nodes:
        bank = {(node[0] + y, node[1] + x) for y, x in STEPS} - own
        rim.update(bank)
        if not bank or any(not (0 <= r <= 1080 and 0 <= c <= 1080) for r, c in bank):
            return {
                "status": "unresolved_exterior_bank",
                "node_rc": list(node),
                "controls": None,
            }
        depth = max(DEPTH_Q, int(water[node]))
        required.append(depth)
        lower.append(max(depth, int(floor[node]) - 192 + depth))
        upper.append(min(65535, min(int(floor[n]) for n in bank) - 32))
    offset = np.floor(distance / 24 + 0.5).astype(np.int64)
    solved = greatest_profile(
        np.asarray(lower, np.int64) + offset,
        np.asarray(upper, np.int64) + offset,
        edges,
    )
    result = {
        "status": solved["status"],
        "heads": heads,
        "terminals": terminals,
        "grade_offset_q": offset.tolist(),
        "longest_distance_m": distance.tolist(),
        "lower_q": lower,
        "upper_q": upper,
        "required_depth_q": required,
        "full_rim_rc": [list(n) for n in sorted(rim)],
        "controls": None,
    }
    if solved["status"] != "feasible":
        result["witnesses"] = [
            {
                "node": w["node"],
                "node_rc": list(nodes[w["node"]]),
                "lower_potential_q": w["lower_q"],
                "greatest_possible_potential_q": w["greatest_possible_q"],
                "lower_stage_q": w["lower_q"] - int(offset[w["node"]]),
                "greatest_possible_stage_q": w["greatest_possible_q"]
                - int(offset[w["node"]]),
            }
            for w in solved.get("witnesses", [])
        ]
        return result
    stages = np.asarray(solved["target_q"], np.int64) - offset
    beds = [min(int(floor[n]), int(s) - d) for n, s, d in zip(nodes, stages, required)]
    if any(
        not (0 <= int(floor[n]) - bed <= 192) or int(s) - bed < d
        for n, s, bed, d in zip(nodes, stages, beds, required)
    ):
        raise ValueError("Recipe violates fixed no-fill/cut/initialization bounds")
    if any(stages[b] > stages[a] - (offset[b] - offset[a]) for a, b in edges):
        raise ValueError("Recipe violates authored grade")
    controls = []
    for role, indices in (("head_inlet", heads), ("terminal_intake", terminals)):
        for i in sorted(indices, key=lambda i: (nodes[i][1], -nodes[i][0])):
            r, c = nodes[i]
            controls.append(
                {
                    "role": role,
                    "node_index": i,
                    "node_rc": [r, c],
                    "position": [c * 16 - 8640, beds[i] / 64, 8640 - r * 16],
                    "type": 1,
                    "target_fixed": int(stages[i]),
                    "intake_rate": INTAKE,
                    "output_rate": OUTPUT if role == "head_inlet" else 0,
                    "source_radius_model_m": float(10 + 0.4 * np.sqrt(INTAKE)),
                    "full_footprint_node_indices": [i],
                    "minimum_static_source_depth_m": (int(stages[i]) - beds[i]) / 64,
                }
            )
    if any(
        c["source_radius_model_m"] >= 16 or c["minimum_static_source_depth_m"] < 1
        for c in controls
    ):
        raise ValueError("Port footprint/depth is not bounded")
    result.update(
        target_q=stages.tolist(),
        bed_q=beds,
        controls=controls,
        new_control_count=len(controls),
        no_per_node_regulators=True,
    )
    return result


def analyze(folder):
    """Retain the whole old ledger/cohort; add explicit head/outlet proposals."""
    original = folder / "input"
    ledger = load(original / "ledger.json")
    geometry = load(original / "source/geometry.json")
    pieces = catalog(geometry)
    eligible = {
        c["id"]: c
        for r in pieces["rows"]
        if r["field"] == "streams" and r["status"] == "perennial_surface"
        for c in r["clips"]
    }
    result = {
        "schema": "polli.stream-head-terminal-feasibility/1",
        "policy": POLICY,
        "source_catalog_sha256": digest(pieces),
        "eligible_clip_ids": sorted(eligible),
        "original_ledger_sha256": sha(original / "ledger.json"),
        "original_line_rows": len(ledger["line_rows"]),
        "original_polygon_rows": len(ledger["polygons"]),
        "physical_package": None,
        "native_observation": False,
        "physical_supply_budget": "unknown; encoded32 is experimental, not qualified discharge/demand",
        "stable_water_promise": "unknown",
        "complete_geographic_candidate": False,
    }
    if "retained_base_refusal" in ledger:
        result.update(
            status="retained_base_refusal",
            original_refusal=ledger["retained_base_refusal"],
            components=None,
            authored_floor=None,
            configured_controls=None,
            authored_initialization=None,
            complete_original_source_contracts=ledger["source_contract_inventory"],
        )
        return result
    source = original / "source"
    old = load(source / "stream-plan.json")
    floor, water = [
        np.flipud(np.fromfile(source / name, "<u2").reshape(1081, 1081)).astype(
            np.int64
        )
        for name in ("terrain.u16", "water.u16")
    ]
    records = {c["id"]: c for c in ledger["clips"]}
    components = []
    for component in old["components"]:
        ids = component["source_clips"]
        nodes = sorted({tuple(n) for name in ids for n in eligible[name]["nodes_rc"]})
        if len(nodes) != component["node_count"]:
            raise ValueError("Incomplete original graph/branch catalog")
        own_ids = set(ids)
        interfaces = [
            r
            for r in ledger["line_interfaces"]
            if r["a_clip"] in own_ids or r["b_clip"] in own_ids
        ]
        bodies = [r for r in ledger["body_interfaces"] if r["clip_id"] in own_ids]
        raster_only = [
            r["id"]
            for r in interfaces
            if r["a_clip"] in own_ids
            and r["b_clip"] in own_ids
            and r["a_clip"] != r["b_clip"]
            and r["shared_native_nodes_rc"]
            and not r["projected_1um_intersections"]
        ]
        foreign = [
            r["id"]
            for r in interfaces
            if (r["a_clip"] in own_ids) != (r["b_clip"] in own_ids)
        ]
        boundaries = [
            {"clip": name, **e}
            for name in ids
            for e in records[name]["endpoints"]
            if e["source_clipped"] or e["native_vertex_touches_square_boundary"]
        ]
        geometry_plan = (
            graph_profile(nodes, component["source_edges"], floor, water)
            if not component["issues"]
            else {
                "status": "unresolved_direction_or_bank",
                "controls": None,
                "issues": component["issues"],
            }
        )
        if (
            geometry_plan["status"] == "feasible"
            and component["geometry"]["status"] != "feasible"
        ):
            raise ValueError(
                "Stricter port recipe cannot turn an old numeric refusal into feasible"
            )
        reasons = []
        guards = component["guards"]
        if geometry_plan["status"] != "feasible":
            reasons.append(geometry_plan["status"])
        if guards["protection_unknown"]:
            reasons.append("missing_protection")
        if guards["infrastructure_or_other_water_hits"]:
            reasons.append("protected_infrastructure_or_water")
        if guards["foreign_stream_buffer_hits"]:
            reasons.append("protected_foreign_stream_buffer")
        if guards["foreign_geometry_unknown"]:
            reasons.append("unsupported_foreign_geometry")
        if not guards["full_bank_inside_square"]:
            reasons.append("exterior_bank_outside_square")
        if component["wet_exterior_bank_nodes"]:
            reasons.append("wet_exterior_bank_interface_unresolved")
        if raster_only:
            reasons.append("raster_only_junction_unresolved")
        if foreign:
            reasons.append("foreign_line_interface_unresolved")
        if bodies:
            reasons.append("body_interface_unresolved")
        if boundaries:
            reasons.append("square_boundary_port_unresolved")
        if not reasons and component["status"] != "geometry_proposal_only":
            raise ValueError("Old refusal cannot become a recipe by relaxed guards")
        components.append(
            {
                "id": component["id"],
                "source_clips": ids,
                "source_provenance": [
                    {
                        "clip": name,
                        "source_sha256": records[name]["source_sha256"],
                        "contract_ids": records[name]["contract_ids"],
                    }
                    for name in ids
                ],
                "original_direction_evidence": component["directions"],
                "original_geometry_status": component["geometry"]["status"],
                "original_guards_unchanged": guards,
                "original_status": component["status"],
                "nodes_rc": [list(n) for n in nodes],
                "source_edges": component["source_edges"],
                "recipe": geometry_plan,
                "interfaces": {
                    "all_relevant_line_records": interfaces,
                    "all_relevant_body_records": bodies,
                    "raster_only_junctions": raster_only,
                    "foreign_line_interfaces": foreign,
                    "square_boundary_endpoints": boundaries,
                },
                "status": "refused_or_unresolved"
                if reasons
                else "experimental_recipe_only",
                "reasons": reasons,
                "physical_package": None,
                "native_admission": "unresolved; no materialized package or geographic native qualification",
            }
        )
    if {name for c in components for name in c["source_clips"]} != set(eligible):
        raise ValueError("A mandatory source piece/branch disappeared")
    result.update(
        status="incomplete_geographic_candidate",
        components=components,
        full_original_probes_sha256=sha(source / "probes.json"),
        full_original_inventory_sha256=sha(source / "inventory.json"),
        original_authored_initialization=ledger["authored_initialization"],
        existing_controls_unchanged=ledger["forcing"],
        dispositions=dict(Counter(c["status"] for c in components)),
        geometry_statuses=dict(Counter(c["recipe"]["status"] for c in components)),
        reason_counts=dict(
            Counter(reason for c in components for reason in c["reasons"])
        ),
    )
    return result


def stage(source, output, review):
    if output.exists():
        raise ValueError("Use a fresh additive port-recipe protocol")
    old = load(source / "ledger.json")
    (refused_preflight if "retained_base_refusal" in old else prepared_preflight)(
        source
    )
    receipt = load(review)
    if (
        receipt["status"] != "pass"
        or receipt["review_issue"] != "01a1ffaf-049d-7aa3-9e93-21b1c11725fd"
    ):
        raise ValueError("Expected exact independent synthetic results receipt")
    output.mkdir(parents=True)
    shutil.copytree(source, output / "input")
    shutil.copyfile(review, output / "results-review.json")
    result = analyze(output)
    write(output / "port-plan.json", result)
    previous = load(source / "freeze.json")
    dependencies = dict(previous["source_files_sha256"])
    for path in ROOT.glob("*.py"):
        if not path.name.startswith("test_"):
            dependencies[path.name] = sha(path)
    for name in ("pyproject.toml", "uv.lock"):
        dependencies[name] = sha(ROOT / name)
    for name in (NEW_SOURCE, DESIGN):
        dependencies[name] = sha(ROOT / name)
    freeze = {
        "schema": "polli.stream-port-recipe-protocol/1",
        "policy": POLICY,
        "source_files_sha256": dependencies,
        "files_sha256": {
            str(p.relative_to(output)): sha(p)
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
        "definition_sha256": previous["definition_sha256"],
        "previous_protocol_sha256": sha(source / "freeze.json"),
        "results_review_sha256": sha(review),
        "physical_package": None,
        "native_observation": False,
        "holdout_inputs_accessed": False,
        "stable_water_promise": "unknown",
    }
    write(output / "freeze.json", freeze)
    preflight(output)
    return {
        "eligible_clips": len(result["eligible_clip_ids"]),
        "status": result["status"],
        "dispositions": result.get("dispositions"),
        "geometry_statuses": result.get("geometry_statuses"),
        "reason_counts": result.get("reason_counts"),
        "freeze_sha256": sha(output / "freeze.json"),
    }


def preflight(folder):
    frozen = load(folder / "freeze.json")
    if (
        frozen["schema"] != "polli.stream-port-recipe-protocol/1"
        or frozen["policy"] != POLICY
        or frozen["physical_package"] is not None
        or frozen["native_observation"]
    ):
        raise ValueError("Wrong unqualified port-recipe protocol")
    for name, value in frozen["source_files_sha256"].items():
        if sha(ROOT / name) != value:
            raise ValueError(f"Bound port recipe dependency changed: {name}")
    for name, value in frozen["files_sha256"].items():
        if sha(folder / name) != value:
            raise ValueError(f"Bound source/cohort/result changed: {name}")
    if (
        sha(folder / "input/freeze.json") != frozen["previous_protocol_sha256"]
        or sha(folder / "results-review.json") != frozen["results_review_sha256"]
    ):
        raise ValueError("Original interface protocol or results receipt changed")
    ledger = load(folder / "input/ledger.json")
    (refused_preflight if "retained_base_refusal" in ledger else prepared_preflight)(
        folder / "input"
    )
    if load(folder / "port-plan.json") != analyze(folder):
        raise ValueError("Complete port-recipe source replay differs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, args in (
        ("stage", ("source", "output", "review")),
        ("preflight", ("folder",)),
    ):
        command = commands.add_parser(name)
        for arg in args:
            command.add_argument(arg, type=Path)
    args = vars(parser.parse_args())
    result = globals()[args.pop("command")](**args)
    print(json.dumps(result or {"status": "source_and_cohort_replay_pass"}, indent=2))
