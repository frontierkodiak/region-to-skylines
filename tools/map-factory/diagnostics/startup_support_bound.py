"""Read-only necessary startup support under explicit preservation policies.

Boolean availability is optimistic, not an allowed water map or hydraulic plan.
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import shutil

import numpy as np

from bank_authority import ROOT, load, sha, write
from maintained_water_inventory import initial_natural_checks
from open_interface_operations import context
from region import raster
from stage_contracts import nearby_nodes
from stage_contracts_v2 import json_scalars
from waterway_pieces import digest

POLICY = "complete-contract-startup-support-bound-v1"
FILES = (
    "diagnostics/startup_support_bound.py",
    "diagnostics/test_startup_support_bound.py",
    "calibration/pl1191-construction-v1/development/phase29-startup-policy.md",
)
HARD = (
    "landing_128m",
    "old_control_radius_plus64m",
    "old_corridor_112m",
    "old_mapped_body_128m",
    "original_stream_bank_union",
)
COUPLING = "all_current_graph_bank_union"
VIEWS = ("a1_fixed_masks", "a2_full_operation_masks", "b_known_source_support")


def ownership(shape, supports):
    """A source row never inherits another row's raster identity at overlap."""
    labels = np.full(shape, -1, np.int32)
    ambiguous = np.zeros(shape, bool)
    for label, nodes in supports:
        nodes = np.asarray(nodes, np.int64)
        previous = labels.ravel()[nodes]
        ambiguous.ravel()[nodes] |= (previous >= 0) & (previous != label)
        labels.ravel()[nodes] = np.where(previous < 0, label, previous)
    return labels, ambiguous


def point_bound(nodes, water, hard, coupling, foreign, own, ambiguous, owner_known):
    nodes = np.asarray(nodes, np.int64)
    wet = water.ravel()[nodes] >= 7  # strictly >.1m at 1/64m
    a1 = ~hard.ravel()[nodes]
    a2 = (
        a1 & ~coupling.ravel()[nodes] & ~foreign
        if owner_known
        else np.zeros(len(nodes), bool)
    )
    b = a2 & own.ravel()[nodes] & ~ambiguous.ravel()[nodes]
    # Unknown ownership is not a false no-repair witness. A1 impossibility still
    # bounds A2/B; otherwise unresolved foreign/ownership may change the answer.
    a1_ok = bool(np.any(wet | a1))
    a2_ok = (
        True if wet.any() or a2.any() else False if not a1_ok or owner_known else None
    )
    b_unknown = bool(np.any(a1 & ambiguous.ravel()[nodes])) or not owner_known
    b_ok = True if wet.any() or b.any() else None if a1_ok and b_unknown else False
    return {
        "support_nodes_north_flat": nodes.tolist(),
        "existing_wet_nodes": nodes[wet].tolist(),
        "a1_editable_nodes": nodes[a1].tolist(),
        "a2_editable_nodes": nodes[a2].tolist() if owner_known else None,
        "b_owned_editable_nodes": nodes[b].tolist() if owner_known else None,
        "foreign_protected_nodes": nodes[foreign].tolist() if owner_known else None,
        "ambiguous_source_membership_nodes": nodes[ambiguous.ravel()[nodes]].tolist(),
        "existing_initial_wet": bool(wet.any()),
        "availability": dict(zip(VIEWS, (a1_ok, a2_ok, b_ok))),
    }


def aggregate(values, fraction):
    if not values:
        return {"points": 0, "known_supported": 0, "unknown": 0, "status": "unknown"}
    known = sum(v is True for v in values)
    unknown = sum(v is None for v in values)
    return {
        "points": len(values),
        "known_supported": known,
        "unknown": unknown,
        "required_fraction": fraction,
        "status": "necessary_support_available"
        if known / len(values) >= fraction
        else "conditional_preservation_obstruction"
        if (known + unknown) / len(values) < fraction
        else "unknown",
    }


def stage(parent, results, review, output):
    if output.exists():
        raise ValueError("Fresh startup protocol required")
    old = load(parent / "freeze.json")
    # Historical source hashes are preserved as historical. The new protocol
    # binds the CURRENT dependencies separately, including the future test fix.
    for name, expected in old["files_sha256"].items():
        if sha(parent / name) != expected:
            raise ValueError(f"Changed historical input: {name}")
    receipt = load(results / "receipt.json")
    if receipt["prospective_freeze_sha256"] != sha(parent / "freeze.json"):
        raise ValueError("Wrong historical results")
    for name, expected in receipt["result_files_sha256"].items():
        if sha(results / name) != expected:
            raise ValueError(f"Changed historical output: {name}")
    if load(review)["acceptance_scope"] != "LIMITED_SOURCE_CPU_DESIGN_RESULTS_ONLY":
        raise ValueError("Wrong limited results review")
    output.mkdir(parents=True)
    shutil.copytree(parent, output / "parent")
    shutil.copytree(results, output / "parent-results")
    shutil.copyfile(review, output / "review.json")
    dependencies = {name: sha(ROOT / name) for name in old["source_files_sha256"]}
    dependencies.update({name: sha(ROOT / name) for name in FILES})
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": old["cases"],
            "source_files_sha256": dependencies,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "prior_outcomes_known": True,
            "new_startup_outputs_not_yet_computed": True,
            "new_physical_or_native": False,
            "historical_source_hashes_not_retrofitted": True,
        },
    )


def preflight(folder):
    f = load(folder / "freeze.json")
    if f["policy"] != POLICY:
        raise ValueError("Wrong startup policy")
    for root, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for name, expected in f[key].items():
            if sha(root / name) != expected:
                raise ValueError(f"Changed bound source/input: {name}")


def analyze(folder, name, output):
    parent = folder / "parent"
    old = load(parent / "interface/prior-results" / f"{name}.json")
    case = parent / "interface/parent/cases" / name
    inventory = load(case / "complete-inventory.json")
    if sha(case / "complete-inventory.json") != old["complete_inventory_sha256"]:
        raise ValueError("Complete original inventory changed")
    contracts = [c for e in inventory["entries"] for c in e.get("contracts", [])]
    if [
        {"id": c["id"], "sha256": digest(c), "points": len(c["points_xz"])}
        for c in contracts
    ] != old["original_contracts"]:
        raise ValueError("Original contract/denominator changed")
    result = {
        "policy": POLICY,
        "case": name,
        "inventory_sha256": sha(case / "complete-inventory.json"),
        "all_original_contract_hashes": old["original_contracts"],
        "source_geometry_sha256": old["source_geometry_sha256"],
        "source_topology_sha256": digest(old["complete_source_topology"]),
        "all_entries_including_excluded_outside_unsupported": inventory["entries"],
        "native_exact_engineered_initialization": "unknown; no API interpolation qualification transferred",
        "physical_admission": False,
        "candidate": False,
        "promise": "unknown",
        "no_grid_CRPor_control_table_serialized": True,
    }
    if old["components"] is None:
        result.update(
            retained_base_refusal=old["retained_base_refusal"],
            floor=None,
            water=None,
            masks=None,
            configured_controls=None,
            contracts=[
                {
                    "contract": c,
                    "points": [
                        {
                            "point_xz": p,
                            "availability": dict.fromkeys(VIEWS),
                            "existing_initial_wet": None,
                        }
                        for p in c["points_xz"]
                    ],
                    "views": {
                        v: aggregate(
                            [None] * len(c["points_xz"]),
                            1 if c["kind"] == "engineered" else 0.95,
                        )
                        for v in VIEWS
                    },
                }
                for c in contracts
            ],
        )
        return result
    (
        _,
        terrain,
        floor,
        water,
        guards,
        controls,
        checked,
        authority,
        owners,
        foreign_nodes,
        tree,
    ) = context(parent, name, old)
    shape = terrain.shape
    topo = old["complete_source_topology"]
    ids = [e["id"] for e in inventory["entries"]]
    id_index = {v: i for i, v in enumerate(ids)}
    supports = defaultdict(set)
    for clip in topo["clips"].values():
        row = clip["source_id"]
        if row in id_index:
            supports[row].update(r * shape[1] + c for r, c in clip["nodes_rc"])
    geometry = load(
        case
        / "input"
        / (
            "physical/geometry.json"
            if load(case / "case.json")["kind"] == "coastal"
            else "source/geometry.json"
        )
    )
    for field in ("lakes", "riverAreas", "oceans"):
        for i, feature in enumerate(geometry.get(field, [])):
            row = f"{field}:{i}"
            if row in id_index:
                supports[row].update(
                    np.flatnonzero(
                        raster(geometry["sq"], [feature], polygons=True)
                    ).tolist()
                )
    # Explicit engineered authored anchor is source-plan support ONLY at an exact
    # grid centre; off-grid/native exact sampling remains unknown below.
    for entry in inventory["entries"]:
        for contract in entry.get("contracts", []):
            if contract["kind"] == "engineered":
                for p in contract["points_xz"]:
                    x, z = map(float, np.asarray(p, np.float32))
                    rc = np.array([(8640 - z) / 16, (x + 8640) / 16])
                    if np.all(rc == np.rint(rc)) and np.all((rc >= 0) & (rc <= 1080)):
                        r, c = map(int, rc)
                        supports[entry["id"]].add(r * shape[1] + c)
    labels, ambiguous = ownership(
        shape,
        [(id_index[row], sorted(nodes)) for row, nodes in sorted(supports.items())],
    )
    hard = np.logical_or.reduce([guards[k] for k in HARD])
    coupling = guards[COUPLING]
    bits = np.zeros(shape, np.uint16)
    for i, key in enumerate((*HARD, COUPLING)):
        bits |= guards[key].astype(np.uint16) << i
    bits.astype("<u2").tofile(output / f"{name}-protection-bits.u16")
    labels.astype("<i4").tofile(output / f"{name}-source-owner.i32")
    ambiguous.astype("u1").tofile(output / f"{name}-ambiguous.u8")
    result.update(
        package_sha256=old["package_sha256"],
        floor=old["floor"],
        initial_water_sha256=sha(case / "input/physical/water.u16"),
        configured_controls=controls,
        network_binding=checked,
        old_bank_authority=authority,
        mask_bit_order=[*HARD, COUPLING],
        mask_orientation="north-first 1081 square",
        original_entry_order_is_owner_label=ids,
        authored_reference_floor_difference_nodes=int(
            np.count_nonzero(terrain != floor)
        ),
        contracts=[],
    )
    membership = defaultdict(set)
    for number, component in enumerate(old["components"]):
        for clip in component["source_clips"]:
            membership[topo["clips"][clip]["source_id"]].add(number)
    previous = {
        r["id"]: r
        for r in initial_natural_checks(inventory, np.flipud(water))["contracts"]
    }
    for entry in inventory["entries"]:
        component_ids = sorted(membership[entry["id"]])
        is_line = entry.get("field") in ("rivers", "streams")
        owner_known = len(component_ids) == 1 if is_line else True
        owner = component_ids[0] if len(component_ids) == 1 else None
        own = labels == id_index[entry["id"]]
        for contract in entry.get("contracts", []):
            rows = []
            for p in contract["points_xz"]:
                x, z = map(float, np.asarray(p, np.float32))
                if contract["kind"] == "engineered":
                    rows.append(
                        {
                            "point_xz": p,
                            "point_f32_xz": [x, z],
                            "availability": dict.fromkeys(VIEWS),
                            "existing_initial_wet": None,
                            "reason": "exact native API interpolation unverified; no nearby substitution",
                        }
                    )
                    continue
                south = nearby_nodes(p, shape)
                nodes = (1080 - south // 1081) * 1081 + south % 1081
                blocked = np.zeros(len(nodes), bool)
                if tree is not None and owner_known:
                    locations = np.column_stack(np.unravel_index(nodes, shape)) * 16
                    for i, js in enumerate(tree.query_ball_point(locations, 128)):
                        blocked[i] = any(
                            any(k != owner for k in owners[foreign_nodes[j]])
                            for j in js
                        )
                row = point_bound(
                    nodes, water, hard, coupling, blocked, own, ambiguous, owner_known
                )
                rows.append({"point_xz": p, "point_f32_xz": [x, z], **row})
            fraction = 1 if contract["kind"] == "engineered" else 0.95
            baseline = aggregate([r["existing_initial_wet"] for r in rows], fraction)
            if contract["kind"] == "natural":
                original = previous[contract["id"]]
                if original["wet"] != baseline["known_supported"] or original[
                    "total"
                ] != len(rows):
                    raise ValueError("Original authored initialization mismatch")
            else:
                original = None
            result["contracts"].append(
                {
                    "contract": contract,
                    "entry_id": entry["id"],
                    "target_component_ids": component_ids,
                    "target_component_ownership_known": owner_known,
                    "points": rows,
                    "old_authored_natural_initialization_unchanged": original,
                    "baseline": baseline,
                    "views": {
                        v: aggregate([r["availability"][v] for r in rows], fraction)
                        for v in VIEWS
                    },
                }
            )
    result["summary"] = {
        "natural_contracts": len(previous),
        "original_initialization_failures": sum(
            v["status"] == "fail" for v in previous.values()
        ),
        "engineered_contracts_exact_unknown": sum(
            c["kind"] == "engineered" for c in contracts
        ),
        "views_natural_only": {
            v: dict(
                Counter(
                    r["views"][v]["status"]
                    for r in result["contracts"]
                    if r["contract"]["kind"] == "natural"
                )
            )
            for v in VIEWS
        },
    }
    return json_scalars(result)


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh output required")
    output.mkdir(parents=True)
    for name in load(folder / "freeze.json")["cases"]:
        print(name, flush=True)
        write(output / f"{name}.json", analyze(folder, name, output))
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "prospective_freeze_sha256": sha(folder / "freeze.json"),
            "files_sha256": {
                p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()
            },
            "physical_or_native_admission": False,
        },
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest="command", required=True)
    a = s.add_parser("stage")
    for n in ("parent", "results", "review", "output"):
        a.add_argument(n, type=Path)
    a = s.add_parser("preflight")
    a.add_argument("protocol", type=Path)
    a = s.add_parser("evaluate")
    a.add_argument("protocol", type=Path)
    a.add_argument("output", type=Path)
    a = p.parse_args()
    if a.command == "stage":
        stage(a.parent, a.results, a.review, a.output)
    elif a.command == "preflight":
        preflight(a.protocol)
    else:
        evaluate(a.protocol, a.output)


if __name__ == "__main__":
    main()
