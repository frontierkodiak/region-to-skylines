"""Complete source-selected boundary obligations and conditional coupled bed/stage."""

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from open_interface_authority import literal_faces
from water_codec_audit import (
    ROOT,
    check_files,
    load,
    preflight as prior_preflight,
    sha,
    write,
)

POLICY = "source-authoritative-coupled-interface-spec-v1"
SCHEMA = "calibration/pl1191-construction-v1/development/phase33-boundary-schema.json"
FILES = (
    "diagnostics/coupled_interface_contract.py",
    "diagnostics/test_coupled_interface_contract.py",
    SCHEMA,
    "calibration/pl1191-construction-v1/development/phase33-boundary-policy.md",
)


def digest(value):
    return sha(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )


def coupled_interval(terrain_q, old_depth_q, cap_q):
    """Existential source-only enquiry; positive cuts remain unauthorized."""
    for v in (terrain_q, old_depth_q, cap_q):
        if type(v) is not int or not 0 <= v <= 65535:
            raise ValueError("Exact source uint16 quantization required")
    depth = max(96, old_depth_q)
    bed_low = max(0, terrain_q - 192)
    bed_high = min(terrain_q, cap_q - depth)
    if bed_low > bed_high:
        return {
            "status": "no_bounded_cut_interval",
            "minimum_cut_needed_q": max(0, terrain_q + depth - cap_q),
            "selected_bed_stage_depth": None,
        }
    cut = terrain_q - bed_high
    return {
        "status": "conditional_positive_cut_no_authority"
        if cut
        else "conditional_zero_minimum_cut_no_selected_plan",
        "bed_q": [bed_low, bed_high],
        "stage_q": [bed_low + depth, cap_q],
        "minimum_depth_q": depth,
        "minimum_cut_needed_q": cut,
        "coupling": "H=B+D; ranges are projections, not independent choices",
        "positive_cut_allowed_under_current_terrain_contract": False,
        "selected_bed_stage_depth": None,
    }


def potential_interface(record):
    """Only explicit separation is inactive; unknown schemas stay unresolved."""
    if "classification" in record:
        return record["classification"] != "proximity_only"
    if (
        record.get("projected_1um_incidence")
        or record.get("shared_native_nodes_rc")
        or record.get("native_raster_contact")
    ):
        return True
    membership = record.get("path_vertex_membership", [])
    if any(v not in ("inside", "boundary", "outside") for v in membership):
        raise ValueError("Unknown source membership classification")
    if any(v != "outside" for v in membership):
        return True
    distance = record.get("minimum_projected_distance_m")
    if (
        isinstance(distance, (float, int))
        and distance > 0
        and (membership or "shared_native_nodes_rc" in record)
    ):
        return False
    return True


def site(kind, index, record, participants, schema, active=True):
    return {
        "id": f"{kind}:{index}",
        "kind": kind,
        "participants": participants,
        "original_source_record": record,
        "original_source_record_sha256": digest(record),
        "active_potential_interface_or_endpoint": active,
        "authority": {k: None for k in schema["required_active_site_fields"]}
        if active
        else None,
        "status": "missing_boundary_contract"
        if active
        else "proximity_only_separation_and_protections_retained",
        "conditional_constraints": schema["conditional_constraints"] if active else [],
        "hydraulic_connection_direction_or_capacity_asserted": False,
    }


def stage(parent, prior_results, review, consumed, output):
    if output.exists():
        raise ValueError("Fresh coupled-interface protocol required")
    f = prior_preflight(parent)
    r = load(prior_results / "receipt.json")
    if r["input_freeze_sha256"] != sha((parent / "freeze.json").read_bytes()):
        raise ValueError("Wrong codec results")
    check_files(prior_results, r["files_sha256"])
    if (
        load(review)["acceptance_scope"]
        != "LIMITED_PHASE31_32_JOINT_PLAN_AND_VALUE_CODEC_RESULTS_ONLY"
    ):
        raise ValueError("Wrong independent results review")
    output.mkdir(parents=True)
    shutil.copytree(parent, output / "prior")
    shutil.copytree(prior_results, output / "codec-results")
    shutil.copyfile(review, output / "review.json")
    shutil.copyfile(consumed, output / "review-consumed.json")
    deps = dict(f["source_files_sha256"])
    deps.update({n: sha((ROOT / n).read_bytes()) for n in FILES})
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": f["cases"],
            "source_files_sha256": deps,
            "files_sha256": {
                str(p.relative_to(output)): sha(p.read_bytes())
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "prior_results_known": True,
            "new_boundary_outputs_not_yet_computed": True,
            "physical_or_native": False,
        },
    )


def preflight(folder):
    f = load(folder / "freeze.json")
    if f["policy"] != POLICY:
        raise ValueError("Wrong boundary policy")
    check_files(ROOT, f["source_files_sha256"])
    check_files(folder, f["files_sha256"])
    return f


def analyze(folder, name):
    schema = load(ROOT / SCHEMA)
    joint_path = folder / "prior/joint-results" / f"{name}.json"
    joint = load(joint_path)
    topology = joint["complete_source_topology"]
    sites = []
    for kind, key in (
        ("line", "all_source_line_interfaces"),
        ("body", "all_source_body_interfaces"),
    ):
        for i, record in enumerate(joint[key]):
            participants = [
                record[k]
                for k in ("a_clip", "b_clip", "clip_id", "polygon_id")
                if k in record
            ]
            sites.append(
                site(kind, i, record, participants, schema, potential_interface(record))
            )
    endpoints = []
    for clip_id, clip in topology["clips"].items():
        for side in ("start", "end"):
            record = {
                "source_id": clip["source_id"],
                "clip_id": clip_id,
                "source_scope": clip["source_scope"],
                "side": side,
                "point_xz": clip["points_xz"][0 if side == "start" else -1],
                "literal_outside_faces": literal_faces(clip, side),
                "role_not_inferred_from_endpoint_order": True,
            }
            endpoints.append(record)
            sites.append(
                site(
                    "endpoint",
                    len(endpoints) - 1,
                    record,
                    [clip_id],
                    schema,
                    clip_id in topology["eligible_clip_ids"],
                )
            )
    body_entries = [
        e
        for e in joint["all_original_entries"]
        if e["field"] not in ("rivers", "streams")
    ]
    for i, e in enumerate(body_entries):
        sites.append(
            site(
                "body-domain",
                i,
                {
                    "entry_id": e["id"],
                    "field": e["field"],
                    "status": e["status"],
                    "complete_entry_sha256": digest(e),
                },
                [e["id"]],
                schema,
                e["status"] != "excluded",
            )
        )
    output = {
        "schema": schema,
        "policy": POLICY,
        "case": name,
        "joint_result_sha256": sha(joint_path.read_bytes()),
        "all_original_entries": joint["all_original_entries"],
        "all_original_contract_hashes": joint["all_original_contract_hashes"],
        "complete_source_topology": topology,
        "source_component_roles": joint["source_component_roles"],
        "all_boundary_sites": sites,
        "site_counts": dict(Counter(s["kind"] for s in sites)),
        "active_missing_boundary_contracts": sum(
            s["active_potential_interface_or_endpoint"] for s in sites
        ),
        "literal_boundary_endpoint_facts": [
            e for e in endpoints if e["literal_outside_faces"]
        ],
        "all_old_refusals_and_contracts_unchanged": True,
        "new_selected_operations_or_candidate": None,
        "physical_admission": False,
        "promise": "unknown",
    }
    if joint.get("retained_base_refusal"):
        return {
            **output,
            "retained_base_refusal": joint["retained_base_refusal"],
            "physical": None,
            "coupled_queries": None,
            "original_contracts_and_points": joint["contracts"],
        }
    queries, retained = [], Counter()
    for contract in joint["contracts"]:
        for point_index, point in enumerate(contract["points"]):
            for node in point["nodes"]:
                status = joint["interval_status_legend"][node[5]]
                retained[status] += 1
                if status not in (
                    "conditional_local_interval",
                    "empty_source_space_interval",
                ):
                    continue
                result = coupled_interval(node[3], node[4], node[7])
                queries.append(
                    {
                        "entry_id": contract["entry_id"],
                        "contract_id": contract["contract"]["id"],
                        "point_index": point_index,
                        "original_point_f32_xz": point["point_f32_xz"],
                        "north_flat_node": node[0],
                        "original_obligation_bits": node[1],
                        "original_role_bits": node[2],
                        "source_terrain_q": node[3],
                        "old_depth_q": node[4],
                        "retained_source_cap_q": node[7],
                        "old_interval_status": status,
                        "coupled_design_enquiry": result,
                        "current_terrain_operation": "unchanged_only",
                        "any_positive_cut_is_forbidden_not_admitted": True,
                    }
                )
    output.update(
        physical={
            "source_terrain_sha256": joint["source_terrain_sha256"],
            "initial_water_sha256": joint["initial_water_sha256"],
            "old_controls": joint["old_controls"],
        },
        coupled_queries=queries,
        coupled_status_occurrences=dict(
            Counter(q["coupled_design_enquiry"]["status"] for q in queries)
        ),
        all_original_node_status_occurrences=dict(retained),
        all_other_node_and_open_interface_obligations_retained_at_joint_result=True,
    )
    return output


def evaluate(folder, output):
    f = preflight(folder)
    if output.exists():
        raise ValueError("Fresh boundary output required")
    output.mkdir(parents=True)
    for name in f["cases"]:
        print(name, flush=True)
        write(output / f"{name}.json", analyze(folder, name))
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "input_freeze_sha256": sha((folder / "freeze.json").read_bytes()),
            "files_sha256": {
                p.name: sha(p.read_bytes())
                for p in sorted(output.iterdir())
                if p.is_file()
            },
            "physical_or_native": False,
        },
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest="command", required=True)
    a = s.add_parser("stage")
    for key in ("parent", "prior_results", "review", "consumed", "output"):
        a.add_argument(key, type=Path)
    a = s.add_parser("preflight")
    a.add_argument("folder", type=Path)
    a = s.add_parser("evaluate")
    a.add_argument("folder", type=Path)
    a.add_argument("output", type=Path)
    a = p.parse_args()
    if a.command == "stage":
        stage(a.parent, a.prior_results, a.review, a.consumed, a.output)
    elif a.command == "preflight":
        preflight(a.folder)
    else:
        evaluate(a.folder, a.output)


if __name__ == "__main__":
    main()
