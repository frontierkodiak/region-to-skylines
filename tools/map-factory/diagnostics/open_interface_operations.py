"""Exact conditional field/port operations, preserving old refusals and masks.

No new profile is solved, no CRP is serialized and no contact becomes admission.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
from pathlib import Path
import shutil
import struct

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from bank_authority import ROOT, load, sha, write
from coastal_floor_audit import grid
from local_supply_envelope import physical as decode_physical
from open_interface_authority import (
    preflight as interface_preflight,
    require_single_valued_cells,
)
from qld_point_coverage import preflight as point_preflight
from region import raster
from spill_port_topology import guard_masks, original_banks
from stage_contracts_v2 import json_scalars
from waterway_pieces import digest

POLICY = "complete-open-interface-operation-ledger-v1"
FILES = (
    "diagnostics/open_interface_operations.py",
    "diagnostics/test_open_interface_operations.py",
    "calibration/pl1191-construction-v1/development/phase28-operation-policy.md",
)


def field_operation(node, terrain, reference, water, bed, stage, protected):
    r, c = map(int, node)
    depth = int(stage) - int(bed)
    changed = []
    records = {}
    for name, before, after in (
        ("terrain", int(terrain), int(bed)),
        ("initial_depth", int(water), depth),
    ):
        if not 0 <= after <= 65535:
            raise ValueError("Proposed serialized field outside uint16; no coercion")
        if before != after:
            changed.append(name)
        records[name] = {
            "before_q": before,
            "after_q": after,
            "before_u16le_hex": before.to_bytes(2, "little").hex(),
            "after_u16le_hex": after.to_bytes(2, "little").hex(),
        }
    return {
        "node_rc_north_first": [r, c],
        "native_u16le_byte_offset": 2 * ((1080 - r) * 1081 + c),
        "reference_hydraulic_floor_q": int(reference),
        "target_q": int(stage),
        "fields": records,
        "changed_fields": changed,
        "protected_contacts": sorted(protected),
        "protected_edits": sorted(protected) if changed else [],
        "serialized_no_fill_cut3_depth1_5_valid": 0 <= int(terrain) - int(bed) <= 192
        and depth >= max(96, int(water)),
        "native_floor_after_serialization": None,
        "old_refusal_cleared": False,
    }


def bank_clearance(nodes, targets, authored, reference):
    own = set(map(tuple, nodes))
    records = []
    for raw, stage in zip(nodes, targets):
        r, c = raw
        rim = {(r + y, c + x) for y in (-1, 0, 1) for x in (-1, 0, 1)} - own
        outside = [
            n
            for n in rim
            if not (0 <= n[0] < authored.shape[0] and 0 <= n[1] < authored.shape[1])
        ]
        inside = sorted(rim - set(outside))
        records.append(
            {
                "node_rc": list(raw),
                "outside_bank_nodes_rc": [list(n) for n in sorted(outside)],
                "minimum_serialized_bank_freeboard_q": min(
                    int(authored[n]) - int(stage) for n in inside
                )
                if inside
                else None,
                "minimum_reference_bank_freeboard_q": min(
                    int(reference[n]) - int(stage) for n in inside
                )
                if inside
                else None,
            }
        )
    return {
        "per_node": records,
        "full_banks_known": all(
            not r["outside_bank_nodes_rc"]
            and r["minimum_serialized_bank_freeboard_q"] is not None
            for r in records
        ),
        "serialized_freeboard_half_metre": all(
            not r["outside_bank_nodes_rc"]
            and r["minimum_serialized_bank_freeboard_q"] is not None
            and r["minimum_serialized_bank_freeboard_q"] >= 32
            for r in records
        ),
        "all_bank_terrain_and_water_unchanged_required": True,
    }


def control_record(node, bed, stage, role):
    if role not in ("head_inlet_proposal", "terminal_outlet_or_intake_proposal"):
        raise ValueError("Only declared head/terminal ports, never per-node regulators")
    r, c = map(int, node)
    xyz = [c * 16 - 8640, int(bed) / 64, 8640 - r * 16]
    output = 32 if role == "head_inlet_proposal" else 0
    raw = struct.pack(">6fHH", *xyz, *xyz, 1, int(stage)) + b"".join(
        v.to_bytes(3, "big") for v in (0, 0, 128, output, 0)
    )
    assert len(raw) == 43
    return {
        "role": role,
        "node_rc_north_first": [r, c],
        "input_xyz": xyz,
        "output_xyz": xyz,
        "type": 1,
        "target_q": int(stage),
        "intake_rate": 128,
        "output_rate": output,
        "raw43_hex": raw.hex(),
        "source_radius_model_m": float(10 + 0.4 * np.sqrt(128)),
        "minimum_static_depth_m": (int(stage) - int(bed)) / 64,
        "deployed": False,
        "physical_flux_or_supply_budget": None,
    }


def shared_cell_conflicts(proposals):
    cells = defaultdict(list)
    for component, operations in proposals:
        for op in operations:
            cells[tuple(op["node_rc_north_first"])].append(
                (
                    component,
                    op["target_q"],
                    op["fields"]["terrain"]["after_q"],
                    op["fields"]["initial_depth"]["after_q"],
                )
            )
    return [
        {"node_rc": list(n), "component_stage_bed_depth_q": rows}
        for n, rows in sorted(cells.items())
        if len({tuple(x[1:]) for x in rows}) > 1
    ]


def stage(interface, point, point_results, output):
    interface_preflight(interface)
    point_preflight(point)
    if load(point_results / "receipt.json")["prospective_freeze_sha256"] != sha(
        point / "freeze.json"
    ):
        raise ValueError("Wrong source point results")
    if output.exists():
        raise ValueError("Fresh operation protocol required")
    output.mkdir(parents=True)
    shutil.copytree(interface, output / "interface")
    shutil.copytree(point, output / "point-source")
    shutil.copytree(point_results, output / "point-results")
    deps = dict(load(point / "freeze.json")["source_files_sha256"])
    for n in FILES:
        deps[n] = sha(ROOT / n)
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": load(interface / "freeze.json")["cases"],
            "source_files_sha256": deps,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "old_numeric_and_QLD_outcomes_known": True,
            "operation_outputs_not_yet_computed": True,
            "new_native_or_physical_serialization": False,
        },
    )


def preflight(folder):
    f = load(folder / "freeze.json")
    if f["policy"] != POLICY:
        raise ValueError("Wrong operation policy")
    for base, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for n, h in f[key].items():
            if sha(base / n) != h:
                raise ValueError(f"Changed bound input/source: {n}")


def context(folder, name, old):
    case = folder / "interface/parent/cases" / name
    base = case / "input"
    physical = base / "physical"
    config = load(case / "case.json")
    geometry = load(
        base
        / (
            "physical/geometry.json"
            if config["kind"] == "coastal"
            else "source/geometry.json"
        )
    )
    if digest(geometry) != old["source_geometry_sha256"]:
        raise ValueError("Complete graph/source geometry mismatch")
    terrain = np.flipud(grid(physical / "terrain.u16")).astype(np.int64)
    water = np.flipud(grid(physical / "water.u16")).astype(np.int64)
    floor = (
        np.flipud(grid(case / "current-floor.u16")).astype(np.int64)
        if config["kind"] == "coastal"
        else terrain
    )
    decoded, controls = decode_physical(physical)
    if controls != old["configured_controls"]:
        raise ValueError("Existing complete control bytes changed")
    layout = (
        load(folder / "interface/parent/coastal-network-layout.json")
        if config["kind"] == "coastal"
        else load(base / "source/layout.json")
    )
    guards, checked = guard_masks(physical, layout)
    guards = {k: np.flipud(v) for k, v in guards.items()}
    bodies = np.zeros_like(terrain, dtype=bool)
    for field in ("lakes", "riverAreas", "oceans"):
        bodies |= raster(geometry["sq"], geometry.get(field, []), polygons=True)
    guards["old_mapped_body_128m"] = (
        ndimage.distance_transform_edt(~bodies) * 16 <= 128 if bodies.any() else bodies
    )
    banks, authority = original_banks(base, old["complete_source_topology"]["rows"])
    guards["original_stream_bank_union"] = np.flipud(banks)
    topo = old["complete_source_topology"]
    full_banks = np.zeros_like(terrain, dtype=bool)
    for component in old["components"]:
        own = {tuple(topo["nodes"][i]["node_rc"]) for i in component["graph_node_ids"]}
        bank = {
            (r + y, c + x) for r, c in own for y in (-1, 0, 1) for x in (-1, 0, 1)
        } - own
        for n in bank:
            if 0 <= n[0] <= 1080 and 0 <= n[1] <= 1080:
                full_banks[n] = True
    guards["all_current_graph_bank_union"] = full_banks
    owner = {n: i for i, c in enumerate(old["components"]) for n in c["source_clips"]}
    owners = defaultdict(set)
    for clip in topo["clips"].values():
        for n in clip["nodes_rc"]:
            owners[tuple(n)].add(owner.get(clip["id"], -1))
    foreign = sorted(owners)
    tree = cKDTree(np.asarray(foreign) * 16) if foreign else None
    return (
        case,
        terrain,
        floor,
        water,
        guards,
        controls,
        checked,
        authority,
        owners,
        foreign,
        tree,
    )


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
        numeric = c["conditional_variable_stage_plan"]
        numeric_ok = numeric["status"] == "feasible"
        entry = {
            "id": c["id"],
            "source_clips": c["source_clips"],
            "graph_node_ids": c["graph_node_ids"],
            "source_edges": c["source_edges"],
            "old_profile_status": numeric["status"],
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
            bank_bounds = bank_clearance(nodes, numeric["target_q"], terrain, floor)
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
        ("stage", ["interface", "point", "point_results", "output"]),
        ("preflight", ["folder"]),
        ("evaluate", ["folder", "output"]),
    ):
        q = sub.add_parser(n)
        for a in args:
            q.add_argument(a, type=Path)
    args = vars(p.parse_args())
    globals()[args.pop("command")](**args)
