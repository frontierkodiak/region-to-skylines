"""Literal outside open-face operation model; all in-square banks stay fixed."""

import argparse
from collections import Counter
import hashlib
from pathlib import Path
import shutil
import numpy as np

from bank_authority import ROOT, load, sha, write
from open_interface_operations import (
    context,
    field_operation,
    control_record,
    shared_cell_conflicts,
    preflight as prior_preflight,
)
from open_interface_authority import (
    cell_consistency,
    require_single_valued_cells,
    literal_faces,
    open_bank_witness,
)
from stage_contracts_v2 import json_scalars
from stream_construction import greatest_profile

POLICY = "complete-literal-open-face-operations-v2"
FILES = (
    "diagnostics/open_face_operations.py",
    "diagnostics/test_open_face_operations.py",
    "calibration/pl1191-construction-v1/development/phase28-open-face-operation-policy.md",
)


def witnesses(topology, component, floor):
    nodes = [topology["nodes"][i]["node_rc"] for i in component["graph_node_ids"]]
    own = set(map(tuple, nodes))
    result = []
    for graph_id, node in zip(component["graph_node_ids"], nodes):
        faces = set()
        for alias in topology["nodes"][graph_id]["source_aliases"]:
            clip = topology["clips"][alias[0]]
            for side, index in (("start", 0), ("end", -1)):
                if tuple(clip["nodes_rc"][index]) == tuple(node):
                    faces.update(literal_faces(clip, side))
        result.append(open_bank_witness(tuple(node), own, floor, faces))
    return result


def open_profile(topology, component, floor, water):
    old = component["conditional_variable_stage_plan"]
    if old["status"] != "unresolved_open_port_lateral_or_exterior_bank":
        return {**old, "old_profile_reused_without_resolve": True}
    w = witnesses(topology, component, floor)
    reason = {
        "literal_open_bank_witnesses": w,
        "in_square_bank_nodes_removed": 0,
        "external_stage_and_capacity": None,
        "old_refusal_unchanged": True,
    }
    if any(
        x["unknown_exterior_lateral_bank_nodes_rc"]
        or x["conditional_in_square_lateral_stage_cap_q"] is None
        for x in w
    ):
        return {
            **reason,
            "status": "unresolved_exterior_or_lateral_bank_no_literal_port",
            "target_q": None,
        }
    nodes = [topology["nodes"][i]["node_rc"] for i in component["graph_node_ids"]]
    depth = [max(96, int(water[tuple(n)])) for n in nodes]
    lower = [max(d, int(floor[tuple(n)]) - 192 + d) for n, d in zip(nodes, depth)]
    upper = [min(65535, x["conditional_in_square_lateral_stage_cap_q"]) for x in w]
    solved = greatest_profile(
        np.asarray(lower, np.int64),
        np.asarray(upper, np.int64),
        [tuple(e) for e in component["source_edges"]],
    )
    solved.update(reason, lower_q=lower, upper_q=upper, required_depth_q=depth)
    if solved["status"] == "feasible":
        target = solved["target_q"]
        beds = [
            min(int(floor[tuple(n)]), int(t) - d)
            for n, t, d in zip(nodes, target, depth)
        ]
        check = cell_consistency(nodes, target, beds)
        if not check["single_valued"]:
            return {
                **solved,
                "status": "refused_same_cell_potential_conflict",
                "tentative_target_q": target,
                "tentative_bed_q": beds,
                "same_cell_witness": check,
                "target_q": None,
            }
        solved.update(bed_q=beds, distinct_stages=len(set(target)))
    return solved


def open_bank_clearance(topology, component, targets, authored, reference):
    source = witnesses(topology, component, authored)
    observed = witnesses(topology, component, reference)
    records = []
    for a, b, target in zip(source, observed, targets):
        records.append(
            {
                "node_rc": a["node_rc"],
                "all_in_square_bank_nodes_rc": a["all_in_square_bank_nodes_rc"],
                "literal_exterior_open_face_nodes_rc": a[
                    "literal_exterior_open_face_nodes_rc"
                ],
                "unknown_exterior_lateral_bank_nodes_rc": a[
                    "unknown_exterior_lateral_bank_nodes_rc"
                ],
                "minimum_serialized_bank_freeboard_q": a[
                    "conditional_in_square_lateral_stage_cap_q"
                ]
                + 32
                - int(target)
                if a["conditional_in_square_lateral_stage_cap_q"] is not None
                else None,
                "minimum_reference_bank_freeboard_q": b[
                    "conditional_in_square_lateral_stage_cap_q"
                ]
                + 32
                - int(target)
                if b["conditional_in_square_lateral_stage_cap_q"] is not None
                else None,
            }
        )
    valid = all(
        not a["unknown_exterior_lateral_bank_nodes_rc"]
        and a["minimum_serialized_bank_freeboard_q"] is not None
        and a["minimum_serialized_bank_freeboard_q"] >= 32
        for a in records
    )
    return {
        "per_node": records,
        "serialized_freeboard_half_metre": valid,
        "in_square_bank_nodes_removed": 0,
        "external_stage_and_capacity": None,
        "all_bank_terrain_and_water_unchanged_required": True,
    }


def stage(prior, prior_results, output):
    prior_preflight(prior)
    receipt = load(prior_results / "receipt.json")
    if receipt["prospective_freeze_sha256"] != sha(prior / "freeze.json"):
        raise ValueError("Wrong v1 operation results")
    for n, h in receipt["result_files_sha256"].items():
        if sha(prior_results / n) != h:
            raise ValueError("Changed v1 operation result")
    if output.exists():
        raise ValueError("Fresh open-face protocol required")
    output.mkdir(parents=True)
    for name in ("interface", "point-source", "point-results"):
        shutil.copytree(prior / name, output / name)
    shutil.copyfile(prior / "freeze.json", output / "old-operation-freeze.json")
    shutil.copytree(prior_results, output / "old-operation-results")
    deps = dict(load(prior / "freeze.json")["source_files_sha256"])
    for n in FILES:
        deps[n] = sha(ROOT / n)
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": load(prior / "freeze.json")["cases"],
            "source_files_sha256": deps,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "old_v1_outcomes_and_literal_face_evidence_known": True,
            "new_open_face_outputs_not_yet_computed": True,
            "new_physical_or_native": False,
        },
    )


def preflight(folder):
    f = load(folder / "freeze.json")
    if f["policy"] != POLICY:
        raise ValueError("Wrong open-face operation policy")
    for base, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for n, h in f[key].items():
            if sha(base / n) != h:
                raise ValueError(f"Changed bound source/input: {n}")


def analyze(folder, name, source_points):
    old = load(folder / "interface/prior-results" / f"{name}.json")
    topo = old["complete_source_topology"]
    result = {
        "policy": POLICY,
        "case": name,
        "complete_old_result_sha256": sha(
            folder / "interface/prior-results" / f"{name}.json"
        ),
        "source_geometry_sha256": old["source_geometry_sha256"],
        "complete_inventory_sha256": old["complete_inventory_sha256"],
        "all_original_contracts": old["original_contracts"],
        "all_eligible_clip_ids": topo["eligible_clip_ids"],
        "all_source_rows_clips_branches_preserved_in_input": True,
        "new_physical_or_native": False,
        "complete_geographic_candidate": False,
        "physical_admission": False,
        "promise": "unknown",
    }
    if old["components"] is None:
        return {
            **result,
            "retained_base_refusal": old["retained_base_refusal"],
            "floor": None,
            "initialization": None,
            "configured_controls": None,
            "components": [
                {
                    "id": f"source-component:{i}",
                    "graph_node_ids": ids,
                    "source_clips": sorted(
                        {a[0] for k in ids for a in topo["nodes"][k]["source_aliases"]}
                    ),
                    "terrain_water_operations": None,
                    "proposed_controls": None,
                    "status": "original_base_refusal_physical_support_unknown",
                }
                for i, ids in enumerate(topo["components"])
            ],
        }
    (
        case,
        terrain,
        floor,
        water,
        guards,
        controls,
        checked,
        bank_authority,
        owners,
        foreign,
        tree,
    ) = context(folder, name, old)
    result.update(
        floor=old["floor"],
        package_sha256=old["package_sha256"],
        initialization=old["initialization"],
        configured_controls=controls,
        configured_control_raw43_table_sha256=hashlib.sha256(
            b"".join(bytes.fromhex(c["raw43_hex"]) for c in controls)
        ).hexdigest(),
        protection_mask_sha256={
            k: hashlib.sha256(v.astype("u1").tobytes()).hexdigest()
            for k, v in guards.items()
        },
        network_protection_binding=checked,
        old_bank_model_authority=bank_authority,
        authored_vs_reference_floor_changed_nodes=int(
            np.count_nonzero(terrain != floor)
        ),
        components=[],
    )
    proposed = []
    for number, c in enumerate(old["components"]):
        nodes = [topo["nodes"][i]["node_rc"] for i in c["graph_node_ids"]]
        own = set(map(tuple, nodes))
        rim = {
            (r + y, cc + x) for r, cc in own for y in (-1, 0, 1) for x in (-1, 0, 1)
        } - own
        valid = sorted(n for n in own | rim if 0 <= n[0] <= 1080 and 0 <= n[1] <= 1080)
        foreign_at = {n: False for n in valid}
        if tree is not None:
            for n, js in zip(valid, tree.query_ball_point(np.asarray(valid) * 16, 128)):
                foreign_at[n] = any(
                    any(i != number for i in owners[foreign[j]]) for j in js
                )

        def contacts(n):
            n = tuple(n)
            return [k for k, m in guards.items() if m[n]] + (
                ["all_other_or_excluded_lines_128m"] if foreign_at[n] else []
            )

        if (
            any(
                sum(bool(guards[k][n]) for n in valid) != v
                for k, v in c["fixed_guard_hits"].items()
            )
            or sum(foreign_at.values()) != c["foreign_128m_contacts"]
        ):
            raise ValueError(
                "Old fixed contact count changed; no reinterpreted refusal"
            )
        rows = [
            {
                "node_rc": list(n),
                "protected_by": contacts(n),
                "serialized_terrain_q": int(terrain[n]),
                "initial_depth_q": int(water[n]),
                "reference_floor_q": int(floor[n]),
                "unchanged_required": True,
            }
            for n in valid
            if contacts(n)
        ]
        numeric = open_profile(topo, c, floor, water)
        numeric_ok = numeric["status"] == "feasible"
        entry = {
            "id": c["id"],
            "source_clips": c["source_clips"],
            "graph_node_ids": c["graph_node_ids"],
            "source_edges": c["source_edges"],
            "old_profile_status": c["conditional_variable_stage_plan"]["status"],
            "new_open_face_conditional_profile": numeric,
            "old_refusal_reasons_unchanged": c["reasons"],
            "old_fixed_guard_hits": c["fixed_guard_hits"],
            "old_foreign_contact_count": c["foreign_128m_contacts"],
            "complete_source_roles": c["piece_junction_inlet_outlet_roles"],
            "all_current_in_square_bank_nodes_rc": [
                list(n) for n in sorted(rim) if 0 <= n[0] <= 1080 and 0 <= n[1] <= 1080
            ],
            "current_exterior_bank_nodes_rc": [
                list(n)
                for n in sorted(rim)
                if not (0 <= n[0] <= 1080 and 0 <= n[1] <= 1080)
            ],
            "protected_contact_witnesses": rows,
            "old_refusal_cleared": False,
            "physical_admission": False,
            "QLD_complete_interface_membership": source_points.get(c["id"])
            if name == "low-coast-oceania"
            else None,
            "terrain_water_operations": None,
            "proposed_controls": None,
            "operation_bounds_only": None,
        }
        if numeric_ok:
            require_single_valued_cells(nodes, numeric["target_q"], numeric["bed_q"])
            ops = [
                field_operation(
                    n,
                    terrain[tuple(n)],
                    floor[tuple(n)],
                    water[tuple(n)],
                    b,
                    s,
                    contacts(n),
                )
                for n, b, s in zip(nodes, numeric["bed_q"], numeric["target_q"])
            ]
            ports = []
            for p in c["piece_junction_inlet_outlet_roles"]:
                for role in p["roles"]:
                    if role not in (
                        "head_inlet_proposal",
                        "terminal_outlet_or_intake_proposal",
                    ):
                        continue
                    i = p["node_index"]
                    port = control_record(
                        nodes[i], numeric["bed_q"][i], numeric["target_q"][i], role
                    )
                    port["protected_contacts"] = contacts(nodes[i])
                    port["source_footprint_model_single_native_node"] = (
                        port["source_radius_model_m"] < 16
                    )
                    distances = []
                    for oldc in controls:
                        distance = float(
                            np.hypot(
                                port["input_xyz"][0] - oldc["position"][0],
                                port["input_xyz"][2] - oldc["position"][2],
                            )
                        )
                        required = (
                            10
                            + 0.4
                            * np.sqrt(max(oldc["intake_rate"], oldc["output_rate"]))
                            + 64
                            + port["source_radius_model_m"]
                        )
                        if distance <= required:
                            distances.append(
                                {
                                    "old_control_index": oldc["index"],
                                    "distance_m": distance,
                                    "required_full_model_circle_clearance_m": float(
                                        required
                                    ),
                                }
                            )
                    port["old_control_full_circle_contacts"] = distances
                    ports.append(port)
            bank_bounds = open_bank_clearance(
                topo, c, numeric["target_q"], terrain, floor
            )
            entry.update(
                full_bank_source_and_reference_check=bank_bounds,
                terrain_water_operations=ops,
                proposed_controls=ports,
                changed_terrain_nodes=sum(
                    "terrain" in o["changed_fields"] for o in ops
                ),
                changed_initial_depth_nodes=sum(
                    "initial_depth" in o["changed_fields"] for o in ops
                ),
                protected_edited_nodes=sum(bool(o["protected_edits"]) for o in ops),
                protected_identity_nodes=sum(
                    bool(o["protected_contacts"]) and not o["changed_fields"]
                    for o in ops
                ),
                operation_bounds_only=bank_bounds["serialized_freeboard_half_metre"]
                and all(
                    o["serialized_no_fill_cut3_depth1_5_valid"]
                    and not o["protected_edits"]
                    for o in ops
                )
                and all(
                    not p["protected_contacts"]
                    and not p["old_control_full_circle_contacts"]
                    and p["minimum_static_depth_m"] >= 1
                    and p["source_footprint_model_single_native_node"]
                    for p in ports
                ),
            )
            proposed.append((c["id"], ops))
        result["components"].append(entry)
    result["cross_component_cell_conflicts"] = shared_cell_conflicts(proposed)
    result["no_hypothetical_combined_map_materialized"] = True
    result["hypothetical_source_count_bound_only"] = (
        len(controls)
        + sum(len(c["proposed_controls"] or []) for c in result["components"])
        <= 65535
    )
    result["operation_status_counts"] = dict(
        Counter(
            "numeric_operation_bounds_only"
            if c["operation_bounds_only"]
            else "numeric_operation_refused"
            if c["operation_bounds_only"] is False
            else "no_numeric_operation_old_refusal"
            for c in result["components"]
        )
    )
    return json_scalars(result)


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh operation output required")
    output.mkdir(parents=True)
    points = load(folder / "point-results/coverage.json")
    records = {x["component"]: x for x in points["all_19_coastal_open_port_components"]}
    for name in load(folder / "freeze.json")["cases"]:
        write(output / f"{name}.json", analyze(folder, name, records))
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "prospective_freeze_sha256": sha(folder / "freeze.json"),
            "result_files_sha256": {
                p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()
            },
            "new_physical_or_native": False,
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for n, args in (
        ("stage", ["prior", "prior_results", "output"]),
        ("preflight", ["folder"]),
        ("evaluate", ["folder", "output"]),
    ):
        q = sub.add_parser(n)
        for a in args:
            q.add_argument(a, type=Path)
    args = vars(p.parse_args())
    globals()[args.pop("command")](**args)
