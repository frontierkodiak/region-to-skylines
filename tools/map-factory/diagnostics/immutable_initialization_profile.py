"""Source-space variable reach profiles with immutable terrain/depth pins."""

import argparse
from collections import Counter
from pathlib import Path
import shutil

import numpy as np

from bank_authority import ROOT, load, sha, write
from coastal_floor_audit import grid
from interface_observation import hash_file
from open_face_operations import witnesses
from open_interface_authority import cell_consistency
from open_interface_operations import field_operation, shared_cell_conflicts
from stream_construction import greatest_profile

POLICY = "immutable-initialization-pinned-reach-v1"
FILES = (
    "diagnostics/immutable_initialization_profile.py",
    "diagnostics/test_immutable_initialization_profile.py",
    "calibration/pl1191-construction-v1/development/phase36-immutable-pin-policy.md",
)


def pinned_profile(terrain, water, lower, upper, edges, pins):
    t, w, lo, hi = (
        np.asarray(x, dtype=np.int64) for x in (terrain, water, lower, upper)
    )
    if not (t.ndim == 1 and t.shape == w.shape == lo.shape == hi.shape):
        raise ValueError("Complete aligned source-node bounds required")
    if np.any(t < 0) or np.any(t > 65535) or np.any(w < 0) or np.any(w > 65535):
        raise ValueError("Source values must be uint16")
    if any(type(i) is not int or not 0 <= i < len(t) for i in pins):
        raise ValueError("Pin outside complete source-node domain")
    lo, hi = lo.copy(), hi.copy()
    bad = [
        {
            "node_index": i,
            "source_terrain_q": int(t[i]),
            "initial_depth_q": int(w[i]),
            "required_depth_q": max(96, int(w[i])),
        }
        for i in pins
        if w[i] < 96
    ]
    if bad:
        return {
            "status": "refused_protected_initial_depth_below_design96q",
            "witnesses": bad,
            "target_q": None,
            "bed_q": None,
        }
    for i in pins:
        h = int(t[i]) + int(w[i])
        lo[i], hi[i] = max(int(lo[i]), h), min(int(hi[i]), h)
    result = greatest_profile(lo, hi, [tuple(e) for e in edges])
    result.update(lower_with_pins_q=lo.tolist(), upper_with_pins_q=hi.tolist())
    if result["status"] == "feasible":
        h = np.asarray(result["target_q"], np.int64)
        bed = np.minimum(t, h - np.maximum(96, w))
        depth = h - bed
        if (
            np.any(bed < 0)
            or np.any(bed > t)
            or np.any(t - bed > 192)
            or np.any(depth < np.maximum(96, w))
        ):
            raise ValueError("Pinned profile violates retained nofill/cut/depth design")
        if any(bed[i] != t[i] or depth[i] != w[i] for i in pins):
            raise ValueError("Pin did not preserve both fields")
        result.update(bed_q=bed.tolist(), depth_q=depth.tolist())
    return result


def stage(prior, results, source_freeze, review, consumed, output):
    old = load(prior / "freeze.json")
    for n, h in old["files_sha256"].items():
        if sha(prior / n) != h:
            raise ValueError("Historical operation input changed")
    receipt = load(results / "receipt.json")
    if receipt["prospective_freeze_sha256"] != sha(prior / "freeze.json"):
        raise ValueError("Wrong retained operation result")
    for n, h in receipt["result_files_sha256"].items():
        if sha(results / n) != h:
            raise ValueError("Historical operation result changed")
    deps = dict(load(source_freeze)["source_files_sha256"])
    deps.update({n: sha(ROOT / n) for n in FILES})
    for n, h in deps.items():
        if sha(ROOT / n) != h:
            raise ValueError("Current method/dependency source mismatch")
    if (
        load(review)["acceptance_scope"]
        != "LIMITED_PHASE35_SOURCE_WALK_CONTINUITY_AND_INTERFACE_MODELS_ONLY"
    ):
        raise ValueError("Wrong results review")
    if output.exists():
        raise ValueError("Fresh pinned construction protocol required")
    output.mkdir(parents=True)
    shutil.copytree(prior, output / "prior")
    shutil.copytree(results, output / "old-operation-results")
    shutil.copyfile(review, output / "review.json")
    shutil.copyfile(consumed, output / "review-consumed.json")
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": old["cases"],
            "source_files_sha256": deps,
            "files_sha256": {
                str(p.relative_to(output)): hash_file(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "old_outcomes_known": True,
            "new_pinned_outputs_not_yet_computed": True,
            "old_source_freezes_historical_new_reader_uses_current_sources": True,
            "physical_or_native": False,
        },
    )


def analyze(folder, name):
    old = load(folder / "prior/interface/prior-results" / f"{name}.json")
    ops = load(folder / "old-operation-results" / f"{name}.json")
    topo = old["complete_source_topology"]
    base = folder / "prior/interface/parent/cases" / name / "input/physical"
    result = {
        "policy": POLICY,
        "case": name,
        "all_original_contracts": old["original_contracts"],
        "all_source_topology": topo,
        "all_old_operation_results_sha256": sha(
            folder / "old-operation-results" / f"{name}.json"
        ),
        "configured_controls": ops.get("configured_controls"),
        "components": [],
        "new_controls": None,
        "complete_physical_candidate": False,
        "physical_admission": False,
        "promise": "unknown",
    }
    if old["components"] is None:
        return {
            **result,
            "physical_support": None,
            "retained_base_refusal": old["retained_base_refusal"],
            "conditional_operations": None,
        }
    t = np.flipud(grid(base / "terrain.u16")).astype(np.int64)
    water = np.flipud(grid(base / "water.u16")).astype(np.int64)
    result["physical_support"] = {
        "serialized_terrain_sha256": sha(base / "terrain.u16"),
        "serialized_initial_water_sha256": sha(base / "water.u16"),
        "new_native_floor": None,
        "old_control_raw43_table_sha256": ops["configured_control_raw43_table_sha256"],
    }
    proposals = []
    for c, retained in zip(old["components"], ops["components"], strict=True):
        if c["id"] != retained["id"]:
            raise ValueError("Incomplete original component alignment")
        nodes = [topo["nodes"][i]["node_rc"] for i in c["graph_node_ids"]]
        banks = witnesses(topo, c, t)
        contacts = {
            tuple(x["node_rc"]): x for x in retained["protected_contact_witnesses"]
        }
        for n, v in contacts.items():
            if (
                int(t[n]) != v["serialized_terrain_q"]
                or int(water[n]) != v["initial_depth_q"]
            ):
                raise ValueError("Frozen protected-field identity changed")
        pins = [i for i, n in enumerate(nodes) if tuple(n) in contacts]
        row = {
            "id": c["id"],
            "source_clips": c["source_clips"],
            "graph_node_ids": c["graph_node_ids"],
            "source_edges_provisional_not_geographic_flow": c["source_edges"],
            "complete_source_roles": retained["complete_source_roles"],
            "all_protected_contact_witnesses": retained["protected_contact_witnesses"],
            "pinned_node_indices": pins,
            "full_bank_witnesses": banks,
            "old_profile_status": retained["old_profile_status"],
            "old_refusal_reasons_unchanged": retained["old_refusal_reasons_unchanged"],
            "terrain_water_operations": None,
            "old_refusal_cleared": False,
            "missing_authority": [
                "direction",
                "lateral_water_land",
                "inlet_outlet_supply_capacity",
                "runtime_receiving_stage",
                "complete_startup_safety",
                "native_retention",
            ],
            "new_controls": None,
            "physical_admission": False,
        }
        if any(
            b["unknown_exterior_lateral_bank_nodes_rc"]
            or b["conditional_in_square_lateral_stage_cap_q"] is None
            for b in banks
        ):
            row["new_profile"] = {
                "status": "unresolved_exterior_lateral_bank",
                "target_q": None,
            }
        else:
            ts = [int(t[tuple(n)]) for n in nodes]
            ws = [int(water[tuple(n)]) for n in nodes]
            req = [max(96, w) for w in ws]
            lo = [max(d, v - 192 + d) for v, d in zip(ts, req)]
            hi = [
                min(65535, b["conditional_in_square_lateral_stage_cap_q"])
                for b in banks
            ]
            solved = pinned_profile(ts, ws, lo, hi, c["source_edges"], pins)
            row["new_profile"] = solved
            if solved["status"] == "feasible":
                consistent = cell_consistency(
                    nodes, solved["target_q"], solved["bed_q"]
                )
                row["same_cell_consistency"] = consistent
                if not consistent["single_valued"]:
                    solved["status"] = "refused_same_cell_profile_conflict"
                else:
                    delta = [
                        field_operation(
                            n,
                            T,
                            T,
                            w,
                            bed,
                            head,
                            contacts.get(tuple(n), {}).get("protected_by", []),
                        )
                        for n, T, w, bed, head in zip(
                            nodes,
                            ts,
                            ws,
                            solved["bed_q"],
                            solved["target_q"],
                            strict=True,
                        )
                    ]
                    if any(
                        o["protected_edits"]
                        or not o["serialized_no_fill_cut3_depth1_5_valid"]
                        for o in delta
                    ):
                        raise ValueError("Protected pin/earthwork operation violated")
                    row["terrain_water_operations"] = delta
                    row["field_only_bounds_valid"] = True
                    proposals.append((c["id"], delta))
        result["components"].append(row)
    result["cross_component_cell_conflicts"] = shared_cell_conflicts(proposals)
    result["status_counts"] = dict(
        Counter(c["new_profile"]["status"] for c in result["components"])
    )
    return result


def evaluate(folder, output):
    f = load(folder / "freeze.json")
    if f["policy"] != POLICY or output.exists():
        raise ValueError("Matching protocol and fresh result required")
    for root, files in ((ROOT, f["source_files_sha256"]), (folder, f["files_sha256"])):
        for n, h in files.items():
            if hash_file(root / n) != h:
                raise ValueError(f"Changed source/input: {n}")
    output.mkdir(parents=True)
    for name in f["cases"]:
        write(output / f"{name}.json", analyze(folder, name))
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "input_freeze_sha256": sha(folder / "freeze.json"),
            "files_sha256": {p.name: sha(p) for p in sorted(output.iterdir())},
            "physical_or_native": False,
        },
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sp = p.add_subparsers(dest="command", required=True)
    s = sp.add_parser("stage")
    for n in ("prior", "results", "source_freeze", "review", "consumed", "output"):
        s.add_argument(n, type=Path)
    e = sp.add_parser("evaluate")
    e.add_argument("folder", type=Path)
    e.add_argument("output", type=Path)
    a = p.parse_args()
    if a.command == "stage":
        stage(a.prior, a.results, a.source_freeze, a.review, a.consumed, a.output)
    else:
        evaluate(a.folder, a.output)


if __name__ == "__main__":
    main()
