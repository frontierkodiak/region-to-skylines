"""Complete source-piece/junction graph and conditional variable-stage plan.

Literal source incidence is a geometric hypothesis, not hydraulic connectivity.
Endpoint-floor direction is provisional. No source/control/CRP is materialized.
"""

import argparse
from collections import Counter, defaultdict
import copy
from pathlib import Path
import shutil

import numpy as np
from scipy.spatial import cKDTree

from bank_authority import ROOT, load, sha, write
from coastal_floor_audit import grid
from local_supply_envelope import physical as decode_physical, source_masks
from maintained_water_inventory import initial_natural_checks
from osm_highways import Union
from spill_port_topology import guard_masks, original_banks
from stage_contracts_complete import ocean_masks, preflight as parent_preflight
from stage_contracts_v2 import json_scalars
from stream_construction import greatest_profile, STEPS
from stream_support_ledger import all_line_rows
from unprepared_stream_ledger import geometry_only
from waterway_pieces import catalog, digest

POLICY = "complete-source-junction-variable-stage-plan-v1"
DESIGN = "calibration/pl1191-construction-v1/development/phase25-open-channel-policy.md"
FILES = (
    "diagnostics/open_channel_plan.py",
    "diagnostics/test_open_channel_plan.py",
    DESIGN,
)


def case_path(protocol, name):
    return protocol / "prior-protocol/input-v1/parent/parent-protocol" / name


def graph(geometry, ledger):
    """Join ONLY literal captured shared geographic vertices, never raster proximity."""
    rows = all_line_rows(geometry, catalog(geometry))
    clips = {
        c["id"]: {**c, "source_id": r["id"], "source_scope": r["status"]}
        for r in rows
        for c in r["clips"]
    }
    expected = {
        c["id"] for r in rows if r["status"] == "perennial_surface" for c in r["clips"]
    }
    if set(c["id"] for c in ledger["clips"]) != set(clips):
        raise ValueError("Complete source-interface catalog differs")
    keys = sorted(
        (name, *node)
        for name in expected
        for node in {tuple(n) for n in clips[name]["nodes_rc"]}
    )
    index = {key: i for i, key in enumerate(keys)}
    union = Union(len(keys))
    junctions = []
    for record in ledger["captured_geographic_vertex_incidence"]:
        members, all_incidence = [], record["incidence"]
        for item in all_incidence:
            name = item["clip_id"]
            if name not in expected:
                continue
            x, z = clips[name]["points_xz"][item["clip_vertex"]]
            r, c = int(np.rint((8640 - z) / 16)), int(np.rint((x + 8640) / 16))
            if (name, r, c) not in index:
                raise ValueError(
                    "Literal source vertex absent from complete native walk"
                )
            members.append(index[(name, r, c)])
        members = sorted(set(members))
        same_cell = len({keys[i][1:] for i in members}) <= 1
        if same_cell and members:
            for other in members[1:]:
                union.join(members[0], other)
        junctions.append(
            {
                **record,
                "conditional_surface_equality_nodes": members,
                "joined_in_geometric_hypothesis": bool(same_cell and len(members) > 1),
                "hydraulic_junction_authority": None,
                "excluded_or_unsupported_incidence": [
                    i for i in all_incidence if i["clip_id"] not in expected
                ],
                "quantized_shared_vertex_consistent": same_cell,
            }
        )
    aliases = defaultdict(list)
    for key, i in index.items():
        aliases[union.find(i)].append(key)
    roots = sorted(aliases, key=lambda i: min(aliases[i]))
    ids = {root: i for i, root in enumerate(roots)}
    nodes = [
        {
            "node_rc": list(aliases[root][0][1:]),
            "source_aliases": [list(k) for k in sorted(aliases[root])],
        }
        for root in roots
    ]
    walks = {
        name: [
            ids[union.find(index[(name, *node)])] for node in clips[name]["nodes_rc"]
        ]
        for name in sorted(expected)
    }
    connected = Union(len(nodes))
    for walk in walks.values():
        for a, b in zip(walk, walk[1:]):
            connected.join(a, b)
    groups = defaultdict(list)
    for i in range(len(nodes)):
        groups[connected.find(i)].append(i)
    components = [
        members for _, members in sorted(groups.items(), key=lambda item: item[1][0])
    ]
    cell_groups = defaultdict(list)
    for i, n in enumerate(nodes):
        cell_groups[tuple(n["node_rc"])].append(i)
    return {
        "rows": rows,
        "clips": clips,
        "eligible_clip_ids": sorted(expected),
        "nodes": nodes,
        "walks": walks,
        "components": components,
        "literal_source_junctions": junctions,
        "raster_coincidence_not_joined": [
            {"node_rc": list(n), "independent_graph_nodes": v}
            for n, v in sorted(cell_groups.items())
            if len(v) > 1
        ],
    }


def profile(nodes, edges, floor, water):
    """Unchanged 1.5m authored initialization, no fill, <=3m cut, full8 banks."""
    own = set(map(tuple, nodes))
    lower, upper, required, banks = [], [], [], set()
    missing = []
    for i, raw in enumerate(nodes):
        node = tuple(raw)
        rim = {(node[0] + y, node[1] + x) for y, x in STEPS} - own
        banks |= rim
        if not rim or any(
            not (0 <= r < floor.shape[0] and 0 <= c < floor.shape[1]) for r, c in rim
        ):
            missing.append(i)
            lower.append(0)
            upper.append(0)
            required.append(None)
            continue
        depth = max(96, int(water[node]))
        required.append(depth)
        lower.append(max(depth, int(floor[node]) - 192 + depth))
        upper.append(min(65535, min(int(floor[n]) for n in rim) - 32))
    result = {
        "lower_q": lower,
        "upper_q": upper,
        "required_depth_q": required,
        "full_untouched_bank_nodes_rc": [list(n) for n in sorted(banks)],
        "missing_exterior_bank_at_nodes": missing,
    }
    if missing:
        return {
            **result,
            "status": "unresolved_open_port_lateral_or_exterior_bank",
            "target_q": None,
        }
    solved = greatest_profile(
        np.asarray(lower, np.int64), np.asarray(upper, np.int64), edges
    )
    result.update(solved)
    if solved["status"] == "feasible":
        target = solved["target_q"]
        beds = [
            min(int(floor[tuple(n)]), int(s) - d)
            for n, s, d in zip(nodes, target, required)
        ]
        if any(
            not 0 <= int(floor[tuple(n)]) - b <= 192 or s - b < d
            for n, b, s, d in zip(nodes, beds, target, required)
        ):
            raise ValueError("Conditional plan violates retained earthwork bounds")
        result.update(
            bed_q=beds,
            maximum_cut_q=max(int(floor[tuple(n)]) - b for n, b in zip(nodes, beds)),
            distinct_stages=len(set(target)),
        )
    return result


def direction_edges(topology, members, floor):
    local = {i: n for n, i in enumerate(members)}
    records, edges, unknown = [], [], []
    for name, walk in topology["walks"].items():
        if walk[0] not in local:
            continue
        a, b = [
            int(floor[tuple(topology["nodes"][i]["node_rc"])])
            for i in (walk[0], walk[-1])
        ]
        reverse = a < b if a != b else None
        records.append(
            {
                "clip": name,
                "reverse_source_order": reverse,
                "direction_authority": None,
                "conditional_evidence": "endpoint floor only",
            }
        )
        if reverse is None or len(set(walk)) < 2:
            unknown.append(name)
            continue
        selected = walk[::-1] if reverse else walk
        edges.extend(
            (local[x], local[y]) for x, y in zip(selected, selected[1:]) if x != y
        )
    return sorted(set(edges)), records, unknown


def reporting_notes(old, floor_native, geometry, results):
    rows, masks, _ = source_masks(geometry)
    own = {r["id"]: m for r, m in zip(rows, masks)}
    own.update({name: mask for name, mask, _ in ocean_masks(geometry)})
    corrections = []
    for model in old["models"]:
        ceiling = (
            np.fromfile(
                results / f"{old['case']}-adj{model['adjacency']}-escape.i32", "<i4"
            ).reshape(floor_native.shape)
            - 32
        )
        entries = []
        for row in model["source_footprints"]:
            ns = np.flatnonzero(own[row["id"]])
            feasible = ns[
                floor_native.ravel()[ns].astype(np.int64) + 64 <= ceiling.ravel()[ns]
            ]
            entries.append(
                {
                    "id": row["id"],
                    "old_unfiltered_floor_plus1_q": row[
                        "minimum_stage_for_any_1m_source_q"
                    ],
                    "minimum_feasible_stage_for_any_1m_source_q": int(
                        floor_native.ravel()[feasible].min()
                    )
                    + 64
                    if feasible.size
                    else None,
                    "conditional_1m_footprint_nodes": int(feasible.size),
                    "source_support_status": "nonempty_source_raster"
                    if ns.size
                    else "empty_source_raster_unresolved_or_outside_not_zero_water",
                }
            )
        split = {
            kind: {
                key: sum(
                    c["kind"] == kind and c[key]["numeric_fit_only"]
                    for c in model["contracts"]
                )
                for key in (
                    "optimistic_any_nearby_raster",
                    "restricted_own_source_raster",
                )
            }
            for kind in ("natural", "engineered")
        }
        corrections.append(
            {
                "adjacency": model["adjacency"],
                "source_footprints": entries,
                "numeric_fit_counts_by_kind": split,
            }
        )
    return {
        "prior_result_unchanged": True,
        "reporting_only_no_contract_or_fit_change": True,
        "models": corrections,
    }


def analyze(folder, name):
    case = folder / "cases" / name
    base = case / "input"
    config = load(case / "case.json")
    geometry = load(
        base
        / (
            "physical/geometry.json"
            if config["kind"] == "coastal"
            else "source/geometry.json"
        )
    )
    inventory = load(case / "complete-inventory.json")
    ledger = (
        load(base / "ledger.json")
        if (base / "ledger.json").exists()
        else geometry_only(geometry)
    )
    topology = graph(geometry, ledger)
    prior = load(case / "prior-stage-result.json")
    result = {
        "schema": "polli.source-junction-variable-stage-plan/1",
        "policy": POLICY,
        "case": name,
        "source_geometry_sha256": digest(geometry),
        "complete_inventory_sha256": sha(case / "complete-inventory.json"),
        "original_contracts": [
            {"id": c["id"], "sha256": digest(c), "points": len(c["points_xz"])}
            for e in inventory["entries"]
            for c in e.get("contracts", [])
        ],
        "complete_source_topology": topology,
        "source_line_interfaces": ledger["line_interfaces"],
        "source_body_interfaces": ledger["body_interfaces"],
        "all_physical_and_probe_bytes_unchanged": True,
        "new_controls": [],
        "physical_admission": False,
        "promise": "unknown",
        "components": None,
    }
    if prior["floor"] is None:
        return {
            **result,
            "retained_base_refusal": prior["original_base_refusal"],
            "floor": None,
            "initialization": None,
            "configured_controls": None,
            "review_reporting_notes": None,
        }
    physical = base / "physical"
    floor_path = (
        case / "current-floor.u16"
        if config["kind"] == "coastal"
        else physical / "terrain.u16"
    )
    floor_native, water_native = grid(floor_path), grid(physical / "water.u16")
    floor, water = np.flipud(floor_native), np.flipud(water_native)
    layout = (
        load(base / "source/layout.json")
        if config["kind"] == "geographic"
        else load(folder / "coastal-network-layout.json")
    )
    guards, checked = guard_masks(physical, layout)
    _, controls = decode_physical(physical)
    guards = {key: np.flipud(value) for key, value in guards.items()}
    banks, bank_authority = original_banks(base, topology["rows"])
    banks = np.flipud(banks)
    owners = defaultdict(set)
    component_for_clip = {}
    for number, members in enumerate(topology["components"]):
        for i in members:
            for alias in topology["nodes"][i]["source_aliases"]:
                component_for_clip[alias[0]] = number
    for clip in topology["clips"].values():
        for raw in clip["nodes_rc"]:
            owners[tuple(raw)].add(component_for_clip.get(clip["id"], -1))
    foreign_nodes = sorted(owners)
    tree = cKDTree(np.asarray(foreign_nodes) * 16) if foreign_nodes else None
    components = []
    for number, members in enumerate(topology["components"]):
        nodes = [topology["nodes"][i]["node_rc"] for i in members]
        source_ids = sorted(
            {
                alias[0]
                for i in members
                for alias in topology["nodes"][i]["source_aliases"]
            }
        )
        edges, directions, unknown = direction_edges(topology, members, floor)
        recipe = (
            profile(nodes, edges, floor, water)
            if not unknown
            else {
                "status": "unresolved_endpoint_direction",
                "unknown_clips": unknown,
                "target_q": None,
            }
        )
        own = set(map(tuple, nodes))
        rim = {(r + y, c + x) for r, c in own for y, x in STEPS} - own
        valid = sorted(n for n in own | rim if 0 <= n[0] <= 1080 and 0 <= n[1] <= 1080)
        guard_hits = {
            key: sum(bool(mask[n]) for n in valid) for key, mask in guards.items()
        }
        foreign_hits = (
            sum(
                any(
                    any(owner != number for owner in owners[foreign_nodes[j]])
                    for j in js
                )
                for js in tree.query_ball_point(np.asarray(valid) * 16, 128)
            )
            if tree is not None and valid
            else 0
        )
        incoming, outgoing = [set() for _ in nodes], [set() for _ in nodes]
        for a, b in edges:
            outgoing[a].add(b)
            incoming[b].add(a)
        ports = []
        for index, node in enumerate(nodes):
            roles = []
            if not incoming[index]:
                roles.append(
                    "head_inlet_proposal" if not unknown else "unresolved_head_role"
                )
            if not outgoing[index]:
                roles.append(
                    "terminal_outlet_or_intake_proposal"
                    if not unknown
                    else "unresolved_terminal_role"
                )
            if len(incoming[index]) > 1 or len(outgoing[index]) > 1:
                roles.append("conditional_internal_junction")
            if not roles:
                continue
            ports.append(
                {
                    "node_index": index,
                    "node_rc": node,
                    "roles": roles,
                    "literal_map_edge_node": any(v in (0, 1080) for v in node),
                    "boundary_stage_authority": "serialized sea parameter only; not an endpoint stage"
                    if config["kind"] == "coastal"
                    else None,
                    "serialized_sea_m": prior["serialized_sea_m"],
                    "flow_direction_authority": None,
                    "inlet_supply_and_outlet_capacity": None,
                    "deployed_control": None,
                }
            )
        body_contacts = [
            r for r in ledger["body_interfaces"] if r["clip_id"] in source_ids
        ]
        reasons = [
            "flow_direction_not_source_authoritative",
            "lateral_bank_width_not_source_authoritative",
            "inlet_supply_and_outlet_capacity_unmeasured",
        ]
        if recipe["status"] != "feasible":
            reasons.append(recipe["status"])
        if any(guard_hits.values()):
            reasons.append("fixed_infrastructure_or_control_protection_contact")
        if foreign_hits:
            reasons.append("fixed_foreign_line_128m_protection_contact")
        if body_contacts:
            reasons.append("mapped_body_interface_unresolved")
        old_bank_hits = sum(bool(banks[n]) for n in own)
        if old_bank_hits:
            reasons.append(
                "original_bank_nodes_in_proposed_channel_no_retirement_allowed"
            )
        if any(
            set(r["independent_graph_nodes"]) & set(members)
            for r in topology["raster_coincidence_not_joined"]
        ):
            reasons.append("raster_only_contact_not_hydraulic_junction")
        components.append(
            {
                "id": f"source-component:{number}",
                "graph_node_ids": members,
                "source_clips": source_ids,
                "source_edges": edges,
                "provisional_directions": directions,
                "conditional_variable_stage_plan": recipe,
                "piece_junction_inlet_outlet_roles": ports,
                "fixed_guard_hits": guard_hits,
                "foreign_128m_contacts": foreign_hits,
                "original_bank_nodes_in_channel": old_bank_hits,
                "source_body_interfaces": body_contacts,
                "construction_status": "refused_or_unresolved_no_admission",
                "reasons": reasons,
            }
        )
    result.update(
        components=components,
        floor=prior["floor"],
        package_sha256=prior["package_sha256"],
        configured_controls=controls,
        initialization=initial_natural_checks(inventory, water_native),
        old_bank_authority=bank_authority,
        network_protection_authority=checked,
        review_reporting_notes=reporting_notes(prior, floor_native, geometry, case),
        recipe_status_counts=dict(
            Counter(c["conditional_variable_stage_plan"]["status"] for c in components)
        ),
    )
    return json_scalars(result)


def stage(parent, results, review, output):
    parent_preflight(parent)
    if output.exists():
        raise ValueError("Fresh protocol required")
    thread = load(review)
    if not any(
        r.get("id") == "01a2016d-8592-7d8a-b0df-a373911adbbf"
        and "PASS (limited CPU" in r.get("content", "")
        for r in thread
    ):
        raise ValueError("Actual PL1261 delivered review required")
    receipt = load(results / "receipt.json")
    if receipt["input_freeze_sha256"] != sha(parent / "freeze.json"):
        raise ValueError("Wrong prior results")
    for n, value in receipt["result_files_sha256"].items():
        if sha(results / n) != value:
            raise ValueError(f"Prior result changed: {n}")
    output.mkdir(parents=True)
    (output / "cases").mkdir()
    root = parent / "prior-protocol/input-v1"
    names = load(parent / "freeze.json")["cases"]
    for name in names:
        case = output / "cases" / name
        shutil.copytree(case_path(parent, name), case)
        shutil.copyfile(
            root / "inventories" / f"{name}.json", case / "complete-inventory.json"
        )
        shutil.copyfile(results / f"{name}.json", case / "prior-stage-result.json")
        for file in results.glob(f"{name}-adj*-escape.i32"):
            shutil.copyfile(file, case / file.name)
    shutil.copyfile(
        root / "parent/coastal-network-layout.json",
        output / "coastal-network-layout.json",
    )
    shutil.copyfile(review, output / "review-thread.json")
    deps = copy.deepcopy(load(parent / "freeze.json")["source_files_sha256"])
    for name in FILES:
        deps[name] = sha(ROOT / name)
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": names,
            "source_files_sha256": deps,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "earlier_results_known": True,
            "new_native_or_physical": False,
            "prior_complete_contract_freeze_sha256": sha(parent / "freeze.json"),
        },
    )


def preflight(folder):
    frozen = load(folder / "freeze.json")
    if frozen["policy"] != POLICY:
        raise ValueError("Wrong open-channel plan")
    for base, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for n, value in frozen[key].items():
            if sha(base / n) != value:
                raise ValueError(f"Bound source/input changed: {n}")


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh CPU output required")
    output.mkdir(parents=True)
    for name in load(folder / "freeze.json")["cases"]:
        print(name, flush=True)
        write(output / f"{name}.json", analyze(folder, name))
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
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, arguments in (
        ("stage", ["parent", "results", "review", "output"]),
        ("preflight", ["folder"]),
        ("evaluate", ["folder", "output"]),
    ):
        cmd = sub.add_parser(name)
        for argument in arguments:
            cmd.add_argument(argument, type=Path)
    args = vars(parser.parse_args())
    globals()[args.pop("command")](**args)
