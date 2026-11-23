"""Complete read-only joint-node obligations and conditional water-only intervals."""

import argparse
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
import shutil

import numpy as np
from scipy import ndimage

from bank_authority import ROOT, load, sha, write
from coastal_floor_audit import grid
from region import raster
from open_interface_authority import literal_faces
from stage_contracts_v2 import json_scalars
from waterway_pieces import digest

POLICY = "source-complete-multi-obligation-joint-initialization-v1"
SCHEMA = "calibration/pl1191-construction-v1/development/phase31-joint-schema.json"
FILES = (
    "diagnostics/joint_initialization_plan.py",
    "diagnostics/test_joint_initialization_plan.py",
    SCHEMA,
    "calibration/pl1191-construction-v1/development/phase31-joint-policy.md",
)


@lru_cache(maxsize=1)
def schema():
    return load(ROOT / SCHEMA)


def flag(name):
    return 1 << schema()["obligation_bit_order"].index(name)


def role(names):
    return sum(1 << schema()["role_bit_order"].index(n) for n in set(names))


def obligations(witness, field, matching_component):
    _, oldbits, known, foreign, count, _, member, interior, _ = witness
    value = int(oldbits)
    if foreign:
        value |= flag("foreign_or_excluded_line_128m") | flag(
            "other_water_or_excluded_geometry"
        )
    if count and (not member or count > 1):
        value |= flag("other_water_or_excluded_geometry")
    if not known:
        value |= flag("unknown_target_owner")
    if count > 1:
        value |= flag("overlapping_polygon_buffers")
    if member and not interior:
        value |= flag("own_buffer_not_body")
    if interior and not matching_component:
        value |= flag("different_original_body_component")
    if field in ("rivers", "streams"):
        value |= flag("open_line_lateral_direction_unknown")
    if field in ("riverAreas", "oceans"):
        value |= flag("open_receiving_water_stage_unknown")
    for name in (
        "inlet_supply_outlet_capacity_unknown",
        "complete_startup_safety_plan_missing",
        "native_retention_acceptance_missing",
        "packing_roundtrip_required",
    ):
        value |= flag(name)
    return value


def local_interval(terrain_q, initial_q, context, authorized_geometry):
    """Conditional expression only, never authorization or a chosen water value."""
    if not authorized_geometry:
        return {"status": "unresolved_obligations", "chosen_stage_q": None}
    if (
        not context
        or context["external_rim_unknown"]
        or context["wet_rim_nodes"]
        or context["non_proximity_source_interfaces"]
    ):
        return {
            "status": "unresolved_open_or_wet_rim_interface",
            "chosen_stage_q": None,
        }
    minimum = max(schema()["minimum_design_depth_q"], int(initial_q))
    low = int(terrain_q) + minimum
    high = min(65535, context["minimum_source_rim_terrain_q"] - schema()["freeboard_q"])
    return {
        "status": "conditional_local_interval"
        if low <= high
        else "empty_source_space_interval",
        "bed_q": [int(terrain_q), int(terrain_q)],
        "stage_q": [low, high],
        "depth_q": [minimum, high - int(terrain_q)],
        "initial_depth_delta_q": [
            minimum - int(initial_q),
            high - int(terrain_q) - int(initial_q),
        ],
        "terrain_delta_q": 0,
        "velocity_values_delta": 0,
        "chosen_stage_q": None,
        "future_native_floor": None,
        "physical_admission": False,
    }


def stage(parent, results, review, consumed, output):
    if output.exists():
        raise ValueError("Fresh joint protocol required")
    f = load(parent / "freeze.json")
    for root, key in ((parent, "files_sha256"), (ROOT, "source_files_sha256")):
        for n, h in f[key].items():
            if sha(root / n) != h:
                raise ValueError(f"Changed parent source/input: {n}")
    r = load(results / "receipt.json")
    if r["prospective_input_freeze_sha256"] != sha(parent / "freeze.json"):
        raise ValueError("Wrong parent results")
    for n, h in r["files_sha256"].items():
        if sha(results / n) != h:
            raise ValueError("Parent output changed")
    if load(review)["acceptance_scope"] != "LIMITED_CPU_FIELD_CONTRACT_RESULTS_ONLY":
        raise ValueError("Wrong review")
    output.mkdir(parents=True)
    shutil.copytree(parent, output / "parent")
    shutil.copytree(results, output / "retained-fields")
    shutil.copyfile(review, output / "review.json")
    shutil.copyfile(consumed, output / "review-consumed.json")
    deps = dict(f["source_files_sha256"])
    for n in FILES:
        deps[n] = sha(ROOT / n)
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": f["cases"],
            "source_files_sha256": deps,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "prior_results_and_review_known": True,
            "new_joint_outputs_not_yet_computed": True,
            "physical_or_native": False,
        },
    )


def preflight(folder):
    f = load(folder / "freeze.json")
    if f["policy"] != POLICY:
        raise ValueError("Wrong joint policy")
    for root, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for n, h in f[key].items():
            if sha(root / n) != h:
                raise ValueError(f"Changed bound source/input: {n}")


def body_model(geometry, field, index, terrain, water, interfaces):
    mask = raster(geometry["sq"], [geometry[field][index]], polygons=True)
    labels, count = ndimage.label(mask, np.ones((3, 3)))
    contexts = {}
    for label in range(1, count + 1):
        body = labels == label
        rim = ndimage.binary_dilation(body, np.ones((3, 3))) & ~body
        external = bool(
            body[0].any() or body[-1].any() or body[:, 0].any() or body[:, -1].any()
        )
        nodes = np.flatnonzero(rim)
        contexts[label] = {
            "original_raster_component": label,
            "component_nodes": int(body.sum()),
            "full_untouched_rim_nodes_north_flat": nodes.tolist(),
            "external_rim_unknown": external,
            "minimum_source_rim_terrain_q": int(terrain[rim].min())
            if nodes.size
            else None,
            "wet_rim_nodes": int(np.count_nonzero(water[rim])),
            "non_proximity_source_interfaces": interfaces,
            "source_raster_not_surveyed_bank_or_hydraulic_connectivity": True,
            "all_terrain_and_rim_depth_unchanged": True,
        }
    return labels, contexts


def literal_endpoint_facts(topology):
    records = []
    for clip in topology["clips"].values():
        for side in ("start", "end"):
            faces = literal_faces(clip, side)
            if not faces:
                continue
            x, z = clip["points_xz"][0 if side == "start" else -1]
            n = int(np.rint((8640 - z) / 16)) * 1081 + int(np.rint((x + 8640) / 16))
            records.append(
                {
                    "source_id": clip["source_id"],
                    "clip_id": clip["id"],
                    "side": side,
                    "node_north_flat": n,
                    "literal_faces": faces,
                    "geometric_fact_not_accepted_port": True,
                }
            )
    return records


def analyze(folder, name):
    field_result = load(folder / "retained-fields" / f"{name}.json")
    previous = load(folder / "parent/retained-results" / f"{name}.json")
    old = load(
        folder
        / "parent/original-protocol/parent/interface/prior-results"
        / f"{name}.json"
    )
    topology = old["complete_source_topology"]
    result = {
        "policy": POLICY,
        "case": name,
        "schema": schema(),
        "all_original_entries": field_result["all_source_entries"],
        "all_original_contract_hashes": field_result["original_contract_hashes"],
        "complete_source_topology": topology,
        "all_source_line_interfaces": old["source_line_interfaces"],
        "all_source_body_interfaces": old["source_body_interfaces"],
        "field_result_sha256": sha(folder / "retained-fields" / f"{name}.json"),
        "old_b_and_scalar_codes_not_used_as_permission": True,
        "old_refusals_unchanged": True,
        "physical_admission": False,
        "complete_candidate": False,
        "promise": "unknown",
        "contracts": [],
        "body_models": {},
    }
    if previous.get("retained_base_refusal"):
        result.update(
            retained_base_refusal=previous["retained_base_refusal"],
            floor=None,
            initial_water=None,
            old_controls=None,
            source_component_roles=None,
            contracts=[
                {
                    "contract": c["contract"],
                    "points": c["points"],
                    "node_operations": None,
                }
                for c in previous["contracts"]
            ],
        )
        return result
    base = folder / "parent/original-protocol/parent/interface/parent/cases" / name
    terrain = np.flipud(grid(base / "input/physical/terrain.u16")).astype(np.int64)
    water = np.flipud(grid(base / "input/physical/water.u16")).astype(np.int64)
    geometry = load(
        base
        / "input"
        / (
            "physical/geometry.json"
            if load(base / "case.json")["kind"] == "coastal"
            else "source/geometry.json"
        )
    )
    result.update(
        source_terrain_sha256=sha(base / "input/physical/terrain.u16"),
        initial_water_sha256=sha(base / "input/physical/water.u16"),
        old_controls=previous["configured_controls"],
        old_controls_raw43_sha256=digest(
            [c["raw43_hex"] for c in previous["configured_controls"]]
        ),
        source_component_roles=[
            {
                "id": c["id"],
                "source_clips": c["source_clips"],
                "graph_node_ids": c["graph_node_ids"],
                "source_edges": c["source_edges"],
                "provisional_roles": c["piece_junction_inlet_outlet_roles"],
                "retained_old_reasons": c["reasons"],
                "retained_old_plan_status": c["conditional_variable_stage_plan"][
                    "status"
                ],
                "new_source_direction_stage_supply_capacity": None,
            }
            for c in old["components"]
        ],
    )
    endpoint_facts = literal_endpoint_facts(topology)
    result["literal_source_endpoint_facts"] = endpoint_facts
    literal_nodes = defaultdict(set)
    for fact in endpoint_facts:
        literal_nodes[fact["source_id"]].add(fact["node_north_flat"])
    source_nodes = defaultdict(set)
    port_roles = defaultdict(set)
    for clip in topology["clips"].values():
        source_nodes[clip["source_id"]].update(
            r * 1081 + c for r, c in clip["nodes_rc"]
        )
    for component in old["components"]:
        for p in component["piece_junction_inlet_outlet_roles"]:
            n = p["node_rc"][0] * 1081 + p["node_rc"][1]
            global_id = component["graph_node_ids"][p["node_index"]]
            for alias in topology["nodes"][global_id]["source_aliases"]:
                clip = alias[0]
                port_roles[(topology["clips"][clip]["source_id"], n)].update(p["roles"])
    interface_by_body = defaultdict(list)
    for i in old["source_body_interfaces"]:
        if i["classification"] != "proximity_only":
            interface_by_body[i["polygon_id"]].append(i)
    last_entry = None
    labels = None
    contexts = {}
    counts = Counter()
    overconservative = []
    result["node_columns"] = [
        "north_flat_node",
        "obligation_bits",
        "role_bits",
        "source_terrain_q",
        "old_depth_q",
        "interval_status_code",
        "stage_low_q",
        "stage_high_q",
        "depth_low_q",
        "depth_high_q",
        "depth_delta_low_q",
        "depth_delta_high_q",
    ]
    result["interval_status_legend"] = [
        "unresolved_obligations",
        "unresolved_open_or_wet_rim_interface",
        "conditional_local_interval",
        "empty_source_space_interval",
    ]
    for c, pc in zip(field_result["contracts"], previous["contracts"]):
        if c["contract"] != pc["contract"]:
            raise ValueError("Original contract changed")
        entry = c["entry_id"]
        field = entry.split(":")[0]
        if entry != last_entry:
            contexts = {}
            labels = None
            if field in ("lakes", "riverAreas", "oceans"):
                labels, contexts = body_model(
                    geometry,
                    field,
                    int(entry.split(":")[1]),
                    terrain,
                    water,
                    interface_by_body[entry],
                )
                result["body_models"][entry] = contexts
            last_entry = entry
        points = []
        for index, (p, pp) in enumerate(zip(c["points"], pc["points"])):
            if "nodes" not in p:
                points.append(
                    {
                        "point_xz": p["point_xz"],
                        "engineered_exact_sampling": "unknown",
                        "node_operations": None,
                    }
                )
                continue
            if (
                pc["target_component_ownership_known"]
                and pp["availability"]["a2_full_operation_masks"] is True
                and pp["availability"]["b_known_source_support"] is None
                and not set(pp["a2_editable_nodes"])
                & set(pp["ambiguous_source_membership_nodes"])
            ):
                overconservative.append([c["contract"]["id"], index])
            nodes = []
            for w in p["nodes"]:
                n, oldbits, known, foreign, bodycount, _, member, interior, _ = w
                r, col = divmod(n, 1081)
                component = int(labels[r, col]) if labels is not None else 0
                matching = component == c["contract"].get("component")
                ob = obligations(w, field, matching)
                roles = []
                if (
                    field == "lakes"
                    and interior
                    and member
                    and matching
                    and known
                    and bodycount == 1
                    and not foreign
                    and (oldbits & ~8) == 0
                ):
                    roles.append("owned_target_interior")
                if member and not interior:
                    roles.append("own_buffer_not_body")
                if n in source_nodes[entry]:
                    roles.append("channel_bed")
                if oldbits & 48:
                    roles.append("untouched_lateral_bank")
                if field in ("riverAreas", "oceans") or (bodycount and not member):
                    roles.append("open_receiving_water")
                ports = port_roles[(entry, n)]
                for source, target in (
                    ("head_inlet_proposal", "provisional_head_inlet"),
                    ("conditional_internal_junction", "internal_junction"),
                    (
                        "terminal_outlet_or_intake_proposal",
                        "provisional_terminal_outlet",
                    ),
                ):
                    if source in ports:
                        roles.append(target)
                if n in literal_nodes[entry]:
                    roles.append("literal_source_endpoint_fact")
                if not roles:
                    roles.append("unresolved_support")
                ctx = contexts.get(component)
                if ctx and ctx["external_rim_unknown"]:
                    ob |= flag("external_boundary_stage_unknown")
                if ctx and ctx["non_proximity_source_interfaces"]:
                    ob |= flag("source_interface_plan_unknown")
                allowed_geometry = field == "lakes" and bool(
                    interior
                    and member
                    and matching
                    and known
                    and bodycount == 1
                    and not foreign
                    and (oldbits & ~8) == 0
                )
                interval = local_interval(
                    terrain[r, col], water[r, col], ctx, allowed_geometry
                )
                status = interval["status"]
                counts[status] += 1
                q = interval.get("stage_q", [None, None])
                dep = interval.get("depth_q", [None, None])
                delta = interval.get("initial_depth_delta_q", [None, None])
                nodes.append(
                    [
                        n,
                        ob,
                        role(roles),
                        int(terrain[r, col]),
                        int(water[r, col]),
                        result["interval_status_legend"].index(status),
                        *q,
                        *dep,
                        *delta,
                    ]
                )
            points.append(
                {
                    "point_xz": p["point_xz"],
                    "point_f32_xz": p["point_f32_xz"],
                    "retained_baseline_wet": p["retained_existing_initial_wet"],
                    "retained_old_availability": p["retained_phase29_availability"],
                    "nodes": nodes,
                }
            )
        result["contracts"].append(
            {
                "contract": c["contract"],
                "entry_id": entry,
                "retained_baseline": pc["baseline"],
                "retained_old_views": pc["views"],
                "points": points,
            }
        )
    result["interval_node_occurrence_counts"] = dict(counts)
    result["review_finding_old_b_conservative_points_retained_not_relabelled"] = (
        overconservative
    )
    result["no_chosen_stage_combined_grid_new_control_or_CRP"] = True
    return json_scalars(result)


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh joint output required")
    output.mkdir(parents=True)
    for name in load(folder / "freeze.json")["cases"]:
        print(name, flush=True)
        write(output / f"{name}.json", analyze(folder, name))
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "input_freeze_sha256": sha(folder / "freeze.json"),
            "files_sha256": {
                p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()
            },
            "physical_or_native": False,
        },
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest="command", required=True)
    a = s.add_parser("stage")
    for n in ("parent", "results", "review", "consumed", "output"):
        a.add_argument(n, type=Path)
    a = s.add_parser("preflight")
    a.add_argument("folder", type=Path)
    a = s.add_parser("evaluate")
    a.add_argument("folder", type=Path)
    a.add_argument("output", type=Path)
    a = p.parse_args()
    if a.command == "stage":
        stage(a.parent, a.results, a.review, a.consumed, a.output)
    elif a.command == "preflight":
        preflight(a.folder)
    else:
        evaluate(a.folder, a.output)


if __name__ == "__main__":
    main()
