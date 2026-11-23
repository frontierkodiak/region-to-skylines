"""Field-specific obligation ledger on complete retained startup-support domains."""

import argparse
from collections import Counter
from functools import lru_cache
from pathlib import Path
import shutil

import numpy as np
from scipy import ndimage

from bank_authority import ROOT, load, sha, write
from region import raster
from stage_contracts_v2 import json_scalars

POLICY = "complete-field-protection-obligation-contract-v1"
CONTRACT = "calibration/pl1191-construction-v1/development/phase30-field-contract.json"
FILES = (
    "diagnostics/field_protection_contract.py",
    "diagnostics/test_field_protection_contract.py",
    CONTRACT,
    "calibration/pl1191-construction-v1/development/phase30-field-policy.md",
)
TRACE = {
    "closed_starter_envelope": (
        "closed_storage_candidate.py",
        "def construction_masks",
        "def construct_after_networks",
    ),
    "reservoir_operation": (
        "reservoir_basin.py",
        "def construct_closed_reservoir",
        None,
    ),
    "natural_body_protection": (
        "natural_basins.py",
        "def protection",
        "def validate_basin",
    ),
    "natural_body_final_contract": ("natural_basins.py", "def validate_final", None),
    "stream_envelope_guards": ("stream_construction.py", "def", None),
    "joint_terrain_depth_guard": (
        "diagnostics/open_interface_operations.py",
        "def field_operation",
        "def control_record",
    ),
    "blanket_startup_model": (
        "diagnostics/startup_support_bound.py",
        "def point_bound",
        "def aggregate",
    ),
    "primary_acceptance": (
        "calibration/pl1191-construction-v1/maintained-water-definition.json",
        None,
        None,
    ),
}


@lru_cache(maxsize=1)
def field_rules():
    return load(ROOT / CONTRACT)["rules"]


def obligation(
    field,
    changed,
    contacts,
    own_body_only=False,
    owner_known=True,
    own_body_interior=False,
):
    if not changed:
        return "identity_only_old_refusal_not_cleared"
    rules = field_rules()
    if field not in rules:
        raise ValueError("Unknown field, no implicit permission")
    if field in ("initial_velocity", "old_control_raw43", "new_control_raw43"):
        return rules[field]
    if field == "terrain":
        return rules[field]["protected_change" if contacts else "unprotected_change"]
    if any(
        n in contacts
        for n in ("original_stream_bank_union", "all_current_graph_bank_union")
    ):
        return rules[field]["bank_change"]
    if not owner_known:
        return rules[field]["unknown_owner_change"]
    other = set(contacts) - {"old_mapped_body_128m"}
    if other:
        return rules[field]["infrastructure_or_coupling_change"]
    if "old_mapped_body_128m" in contacts:
        if own_body_only and not own_body_interior:
            return rules[field]["own_buffer_not_body_change"]
        return rules[field][
            "own_body_only_change" if own_body_only else "other_water_change"
        ]
    return rules[field]["unprotected_change"]


def stage(original, derived_protocol, derived, output):
    if output.exists():
        raise ValueError("Fresh field contract protocol required")
    f = load(derived_protocol / "freeze.json")
    for root, mapping in (
        (derived_protocol, f["files_sha256"]),
        (ROOT, f["source_files_sha256"]),
    ):
        for n, h in mapping.items():
            if sha(root / n) != h:
                raise ValueError(f"Changed original dependency: {n}")
    r = load(derived / "receipt.json")
    if r["input_freeze_sha256"] != sha(derived_protocol / "freeze.json"):
        raise ValueError("Wrong derived lineage")
    for n, h in r["files_sha256"].items():
        if sha(derived / n) != h:
            raise ValueError("Changed derived result")
    original_freeze = load(original / "freeze.json")
    for n, h in original_freeze["files_sha256"].items():
        if sha(original / n) != h:
            raise ValueError("Changed complete original input")
    output.mkdir(parents=True)
    shutil.copytree(original, output / "original-protocol")
    shutil.copytree(derived_protocol, output / "ordering-protocol")
    shutil.copytree(derived, output / "retained-results")
    trace = {}
    for key, (name, start, end) in TRACE.items():
        text = (ROOT / name).read_text()
        first = text.index(start) if start else 0
        last = text.index(end, first + len(start)) if end else len(text)
        trace[key] = {
            "source": name,
            "source_sha256": sha(ROOT / name),
            "origin": "source-code contract, not attributed to a user",
            "excerpt": text[first:last],
            "start_line": text[:first].count("\n") + 1,
        }
    write(output / "source-authority-trace.json", trace)
    deps = dict(f["source_files_sha256"])
    for n in FILES:
        deps[n] = sha(ROOT / n)
    for n, _, _ in TRACE.values():
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
            "prior_outcomes_known": True,
            "new_annotations_not_yet_computed": True,
            "physical_or_native_change": False,
        },
    )


def preflight(folder):
    f = load(folder / "freeze.json")
    if f["policy"] != POLICY:
        raise ValueError("Wrong field contract policy")
    for root, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for n, h in f[key].items():
            if sha(root / n) != h:
                raise ValueError(f"Changed bound source/input: {n}")


def body_provenance(geometry, ids):
    shape = (1081, 1081)
    count = np.zeros(shape, np.uint16)
    first = np.full(shape, -1, np.int32)
    own = {}
    for field in ("lakes", "riverAreas", "oceans"):
        for index, feature in enumerate(geometry.get(field, [])):
            key = f"{field}:{index}"
            mask = raster(geometry["sq"], [feature], polygons=True)
            buffer = (
                ndimage.distance_transform_edt(~mask) * 16 <= 128
                if mask.any()
                else mask
            )
            label = ids.index(key)
            first[buffer & (count == 0)] = label
            count[buffer] += 1
            own[key] = (buffer, mask)
    return count, first, own


def analyze(folder, name, output):
    retained = load(folder / "retained-results" / f"{name}.json")
    result = {
        "policy": POLICY,
        "case": name,
        "retained_complete_result_sha256": sha(
            folder / "retained-results" / f"{name}.json"
        ),
        "all_source_entries": retained[
            "all_entries_including_excluded_outside_unsupported"
        ],
        "original_contract_hashes": retained["all_original_contract_hashes"],
        "source_geometry_sha256": retained["source_geometry_sha256"],
        "field_contract_sha256": sha(ROOT / CONTRACT),
        "no_old_obstruction_recalculated_or_refusal_cleared": True,
        "physical_admission": False,
        "promise": "unknown",
        "contracts": [],
    }
    if retained.get("retained_base_refusal"):
        result.update(
            retained_base_refusal=retained["retained_base_refusal"],
            floor=None,
            initialized_water=None,
            field_operations=None,
            contracts=[
                {
                    "contract": c["contract"],
                    "points": c["points"],
                    "field_obligations": None,
                }
                for c in retained["contracts"]
            ],
        )
        return result
    original = folder / "ordering-protocol/original-results"
    bits = np.fromfile(original / f"{name}-protection-bits.u16", "<u2").reshape(
        1081, 1081
    )
    base = folder / "original-protocol/parent/interface/parent/cases" / name
    geom = load(
        base
        / "input"
        / (
            "physical/geometry.json"
            if load(base / "case.json")["kind"] == "coastal"
            else "source/geometry.json"
        )
    )
    ids = retained["original_entry_order_is_owner_label"]
    counts, first, own = body_provenance(geom, ids)
    if not np.array_equal(counts > 0, (bits & 8) > 0):
        raise ValueError("Per-body provenance differs from unchanged old body mask")
    counts.astype("<u2").tofile(output / f"{name}-body-buffer-count.u16")
    first.astype("<i4").tofile(output / f"{name}-body-buffer-first-owner.i32")
    classes = Counter()
    decision_names = list(load(ROOT / CONTRACT)["rules"]["initial_depth"].values())
    result["depth_obligation_code_legend"] = decision_names
    result["node_witness_columns"] = [
        "north_flat_node",
        "unchanged_mask_bits",
        "foreign_owner_known",
        "foreign_contact",
        "body_buffer_count",
        "first_body_entry_index",
        "own_target_body_buffer_member",
        "own_original_polygon_interior_member",
        "depth_obligation_code",
    ]
    result["unchanged_mask_bit_order"] = retained["mask_bit_order"]
    result["entry_index_order"] = ids
    result["all_nodes_other_field_obligations"] = {
        "terrain": "protected contacts forbid change; otherwise full source/cut/stage/bank/safety plan required",
        "initial_velocity": obligation("initial_velocity", True, []),
        "old_control_raw43": obligation("old_control_raw43", True, []),
        "new_control_raw43": obligation("new_control_raw43", True, []),
        "actual_proposed_edits": False,
    }
    for c in retained["contracts"]:
        entry = c["entry_id"]
        rows = []
        for p in c["points"]:
            if "support_nodes_north_flat" not in p:
                rows.append(
                    {
                        "point_xz": p["point_xz"],
                        "exact_engineered_sampling": "unknown",
                        "field_operations": None,
                    }
                )
                continue
            witnesses = []
            foreign = set(p["foreign_protected_nodes"] or [])
            for n in p["support_nodes_north_flat"]:
                r, col = divmod(n, 1081)
                contacts = [
                    key
                    for i, key in enumerate(retained["mask_bit_order"])
                    if bits[r, col] & (1 << i)
                ]
                if n in foreign:
                    contacts.append("all_other_or_excluded_lines_128m")
                membership = bool(own[entry][0][r, col]) if entry in own else False
                interior = bool(own[entry][1][r, col]) if entry in own else False
                only = membership and int(counts[r, col]) == 1
                classification = obligation(
                    "initial_depth",
                    True,
                    contacts,
                    only,
                    c["target_component_ownership_known"],
                    interior,
                )
                classes[classification] += 1
                witnesses.append(
                    [
                        n,
                        int(bits[r, col]),
                        int(c["target_component_ownership_known"]),
                        int(n in foreign),
                        int(counts[r, col]),
                        int(first[r, col]),
                        int(membership),
                        int(interior),
                        decision_names.index(classification),
                    ]
                )
            rows.append(
                {
                    "point_xz": p["point_xz"],
                    "point_f32_xz": p["point_f32_xz"],
                    "retained_existing_initial_wet": p["existing_initial_wet"],
                    "retained_phase29_availability": p["availability"],
                    "nodes": witnesses,
                }
            )
        result["contracts"].append(
            {
                "contract": c["contract"],
                "entry_id": entry,
                "retained_phase29_baseline": c["baseline"],
                "retained_phase29_views": c["views"],
                "points": rows,
            }
        )
    result["depth_obligation_node_occurrences"] = dict(classes)
    result["body_buffer_union_equals_unchanged_phase29_mask"] = True
    result["all_old_control43bytes_and_source_physical_inputs_unchanged"] = True
    return json_scalars(result)


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh annotation output required")
    output.mkdir(parents=True)
    for name in load(folder / "freeze.json")["cases"]:
        print(name, flush=True)
        write(output / f"{name}.json", analyze(folder, name, output))
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "prospective_input_freeze_sha256": sha(folder / "freeze.json"),
            "files_sha256": {
                p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()
            },
            "new_physical_or_native": False,
        },
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest="command", required=True)
    a = s.add_parser("stage")
    for n in ("original", "derived_protocol", "derived", "output"):
        a.add_argument(n, type=Path)
    a = s.add_parser("preflight")
    a.add_argument("folder", type=Path)
    a = s.add_parser("evaluate")
    a.add_argument("folder", type=Path)
    a.add_argument("output", type=Path)
    a = p.parse_args()
    if a.command == "stage":
        stage(a.original, a.derived_protocol, a.derived, a.output)
    elif a.command == "preflight":
        preflight(a.folder)
    else:
        evaluate(a.folder, a.output)


if __name__ == "__main__":
    main()
