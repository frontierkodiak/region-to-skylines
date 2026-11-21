"""Source-only branch-complete stream earthwork feasibility, not native admission.

Proposals do not add forcing or serialize a CRP. Supply, outlet/junction
hydraulics, actual floors and retention remain unresolved even when bounds fit.
"""

import argparse
from collections import Counter
import copy
import hashlib
import heapq
import json
from pathlib import Path
import shutil

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from closed_storage_candidate import ROOT, sha
from natural_basins import protection
from natural_storage_candidate import write
from natural_water_inventory import compile_natural_inventory
from osm_highways import Union
from region import raster
from waterway_pieces import catalog, compile_piece_inventory, digest

POLICY = "source-piece-stream-graph-feasibility-v1"
INPUTS = [
    "geometry.json",
    "hydrology.json",
    "terrain.u16",
    "water.u16",
    "natural-plan.json",
    "mapped-water.u8",
    "probes.json",
]
STEPS = [(y, x) for y in (-1, 0, 1) for x in (-1, 0, 1) if (y, x) != (0, 0)]


def greatest_profile(lower, upper, edges):
    """Greatest feasible integer potential on a DAG; a cycle is unresolved."""
    lower, upper = np.asarray(lower), np.asarray(upper)
    if (
        lower.ndim != 1
        or lower.shape != upper.shape
        or lower.dtype.kind not in "iu"
        or upper.dtype.kind not in "iu"
    ):
        raise ValueError("Expected matching integer native bounds")
    adjacency = [[] for _ in lower]
    degree = [0] * len(lower)
    for a, b in sorted(set(edges)):
        if not 0 <= a < len(lower) or not 0 <= b < len(lower):
            raise ValueError("Edge outside bound catalog")
        adjacency[a].append(b)
        degree[b] += 1
    ready = [i for i, d in enumerate(degree) if d == 0]
    heapq.heapify(ready)
    target = upper.astype(np.int64).copy()
    visited = 0
    while ready:
        node = heapq.heappop(ready)
        visited += 1
        for other in adjacency[node]:
            target[other] = min(target[other], target[node])
            degree[other] -= 1
            if degree[other] == 0:
                heapq.heappush(ready, other)
    if visited != len(lower):
        return {
            "status": "unresolved_cycle",
            "nodes": [i for i, d in enumerate(degree) if d],
        }
    bad = np.flatnonzero(target < lower)
    if len(bad):
        return {
            "status": "infeasible_bounds",
            "witnesses": [
                {
                    "node": int(i),
                    "lower_q": int(lower[i]),
                    "greatest_possible_q": int(target[i]),
                }
                for i in bad
            ],
        }
    return {"status": "feasible", "target_q": target.tolist()}


def assess(geometry, hydro, floor, water, layout):
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
        raise ValueError("Expected complete integer authored grids in1/64m units")
    pieces = catalog(geometry)
    clips = [
        c
        for r in pieces["rows"]
        if r["field"] == "streams" and r["status"] == "perennial_surface"
        for c in r["clips"]
    ]
    nodes = sorted({tuple(n) for c in clips for n in c["nodes_rc"]})
    node_index = {n: i for i, n in enumerate(nodes)}
    union = Union(len(nodes))
    for clip in clips:
        for a, b in zip(clip["nodes_rc"], clip["nodes_rc"][1:]):
            union.join(node_index[tuple(a)], node_index[tuple(b)])
    groups = {}
    for node, index in node_index.items():
        groups.setdefault(union.find(index), []).append(node)
    groups = sorted(groups.values(), key=lambda ns: ns[0])
    owners = {n: i for i, ns in enumerate(groups) for n in ns}
    foreign = {}
    for row in pieces["rows"]:
        if row["field"] != "streams":
            continue
        for clip in row["clips"]:
            for raw in clip["nodes_rc"]:
                node = tuple(raw)
                foreign.setdefault(node, set()).add(
                    owners.get(node, -1) if row["status"] == "perennial_surface" else -1
                )
    foreign_nodes = sorted(foreign)
    tree = cKDTree(np.array(foreign_nodes) * 16) if foreign_nodes else None
    environment = copy.deepcopy(geometry)
    environment["streams"] = []
    protection_unknown = None
    try:
        protected = protection(environment, hydro, layout)
        lakes = raster(geometry["sq"], geometry.get("lakes", []), polygons=True)
        if lakes.any():
            protected |= ndimage.distance_transform_edt(~lakes) * 16 <= 128
    except (ValueError, KeyError, IndexError, TypeError) as error:
        protection_unknown = str(error)
        protected = np.ones(floor.shape, bool)
    unknown_foreign = any(
        r["field"] == "streams" and r["status"] == "unresolved" for r in pieces["rows"]
    )
    components, memberships = [], {}
    for number, members in enumerate(groups):
        name = f"stream-component:{number}"
        own = set(members)
        local = {n: i for i, n in enumerate(members)}
        selected = [c for c in clips if tuple(c["nodes_rc"][0]) in own]
        issues, edges, directions = [], [], []
        for clip in selected:
            memberships[clip["id"]] = name
            walk = [tuple(n) for n in clip["nodes_rc"]]
            a, b = int(floor[walk[0]]), int(floor[walk[-1]])
            if len(walk) < 2 or a == b:
                issues.append(
                    {
                        "reason": "flow direction unresolved at quantized endpoints",
                        "clip": clip["id"],
                    }
                )
                continue
            reversed_order = a < b
            if reversed_order:
                walk.reverse()
            edges.extend((local[a], local[b]) for a, b in zip(walk, walk[1:]))
            directions.append(
                {
                    "clip": clip["id"],
                    "reverse_source_order": reversed_order,
                    "evidence": "inferred endpoint terrain only, not geographic/native flow proof",
                }
            )
        envelope = own | {(r + y, c + x) for r, c in own for y, x in STEPS}
        boundary = any(not (0 <= r <= 1080 and 0 <= c <= 1080) for r, c in envelope)
        valid_envelope = sorted(
            n for n in envelope if 0 <= n[0] <= 1080 and 0 <= n[1] <= 1080
        )
        protected_hits = sum(bool(protected[n]) for n in valid_envelope)
        foreign_hits = 0
        if tree is not None:
            nearby = tree.query_ball_point(np.array(valid_envelope) * 16, 128)
            foreign_hits = sum(
                any(
                    any(owner != number for owner in foreign[foreign_nodes[i]])
                    for i in ids
                )
                for ids in nearby
            )
        guards = {
            "protection_unknown": protection_unknown,
            "infrastructure_or_other_water_hits": protected_hits,
            "foreign_stream_buffer_hits": foreign_hits,
            "foreign_geometry_unknown": unknown_foreign,
            "full_bank_inside_square": not boundary,
        }
        lower, upper, required = [], [], []
        wet_bank = set()
        for node in members:
            bank = [
                (node[0] + y, node[1] + x)
                for y, x in STEPS
                if (node[0] + y, node[1] + x) not in own
            ]
            bank = [n for n in bank if 0 <= n[0] <= 1080 and 0 <= n[1] <= 1080]
            if not bank:
                issues.append(
                    {"reason": "no exterior bank witness", "node_rc": list(node)}
                )
            depth = max(64, int(water[node]))
            required.append(depth)
            lower.append(max(depth, int(floor[node]) - 192 + depth))
            upper.append(min(65535, min((int(floor[n]) for n in bank), default=0) - 32))
            wet_bank.update(n for n in bank if water[n] > 0)
        solve = (
            greatest_profile(
                np.array(lower, np.int64), np.array(upper, np.int64), edges
            )
            if not issues
            else {"status": "unresolved_direction_or_bank"}
        )
        proposed = []
        if solve["status"] == "feasible":
            for node, stage, depth in zip(members, solve["target_q"], required):
                bed = min(int(floor[node]), stage - depth)
                assert 0 <= int(floor[node]) - bed <= 192 and stage - bed >= max(
                    64, int(water[node])
                )
                proposed.append(
                    {
                        "node_rc": list(node),
                        "bed_q": bed,
                        "stage_q": stage,
                        "depth_q": stage - bed,
                    }
                )
        guard_pass = (
            not protected_hits
            and not foreign_hits
            and not unknown_foreign
            and not boundary
            and protection_unknown is None
        )
        components.append(
            {
                "id": name,
                "source_clips": [c["id"] for c in selected],
                "node_count": len(members),
                "source_edges": [list(e) for e in sorted(set(edges))],
                "directions": directions,
                "issues": issues,
                "guards": guards,
                "geometry": solve,
                "proposal": proposed,
                "status": "geometry_proposal_only"
                if guard_pass and solve["status"] == "feasible"
                else "refused_or_unresolved",
                "wet_exterior_bank_nodes": len(wet_bank),
                "supply_outlet_junction_status": "unresolved",
                "native_admission": "unresolved",
            }
        )
    plan = {
        "schema": "polli.stream-piece-static-feasibility/1",
        "policy": POLICY,
        "catalog_sha256": digest(pieces),
        "clip_components": memberships,
        "components": components,
        "infrastructure_protection_sha256": hashlib.sha256(
            protected.tobytes()
        ).hexdigest(),
        "foreign_protection": "all other/excluded stream nodes buffered128m; current whole graph only is target; no name grouping or post-refusal mask change",
        "floor_scope": "authored quantized terrain, not actual native hydraulic floor",
        "physical_forcing_budget": "unknown; lake rate128 is not a flowing-water budget",
        "stable_water_promise": "unknown",
        "native_observation": False,
    }
    return pieces, plan


def analyze(folder):
    geometry = json.loads((folder / "geometry.json").read_text())
    hydro = json.loads((folder / "hydrology.json").read_text())
    layout = json.loads((folder / "layout.json").read_text())
    floor, water = [
        np.flipud(np.fromfile(folder / name, "<u2").reshape(1081, 1081)).astype(
            np.int64
        )
        for name in ("terrain.u16", "water.u16")
    ]
    pieces, plan = assess(geometry, hydro, floor, water, layout)
    inventory = compile_piece_inventory(
        geometry,
        hydro,
        json.loads((folder / "natural-plan.json").read_text()),
        pieces,
        plan,
    )
    old = json.loads((folder / "inventory-v2.json").read_text())
    replay = compile_natural_inventory(
        geometry, hydro, json.loads((folder / "natural-plan.json").read_text())
    )
    if old != replay or inventory["points"] != old["points"]:
        raise ValueError("Frozen v2 inventory or source cohort changed")
    return pieces, plan, inventory


def stage(source, output, layout=ROOT / "templates/native-corridors.json"):
    if output.exists():
        raise ValueError("Use a fresh stream-feasibility protocol directory")
    output.mkdir(parents=True)
    for name in INPUTS:
        shutil.copyfile(source / name, output / name)
    shutil.copyfile(source / "inventory.json", output / "inventory-v2.json")
    shutil.copyfile(layout, output / "layout.json")
    pieces, plan, inventory = analyze(output)
    for name, obj in [
        ("pieces.json", pieces),
        ("stream-plan.json", plan),
        ("inventory.json", inventory),
    ]:
        write(output / name, obj)
    previous = json.loads(
        (
            ROOT / "calibration/pl1191-construction-v1/inventory-freeze-v2.json"
        ).read_text()
    )
    names = set(previous["source_files_sha256"]) | {
        "waterway_pieces.py",
        "stream_construction.py",
    }
    files = INPUTS + [
        "inventory-v2.json",
        "layout.json",
        "pieces.json",
        "stream-plan.json",
        "inventory.json",
    ]
    freeze = {
        "schema": "polli.stream-piece-feasibility-protocol/1",
        "source_files_sha256": {n: sha(ROOT / n) for n in sorted(names)},
        "files_sha256": {n: sha(output / n) for n in files},
        "definition_sha256": inventory["definition_sha256"],
        "panel_sha256": previous["panel_sha256"],
        "physical_package": None,
        "native_observation": False,
        "holdout_inputs_accessed": False,
        "stable_water_promise": "unknown",
    }
    write(output / "freeze.json", freeze)
    preflight(output)
    return {
        "source_rows": len(pieces["rows"]),
        "stream_clips": len(plan["clip_components"]),
        "components": len(plan["components"]),
        "dispositions": dict(Counter(c["status"] for c in plan["components"])),
        "geometry_statuses": dict(
            Counter(c["geometry"]["status"] for c in plan["components"])
        ),
        "freeze_sha256": sha(output / "freeze.json"),
        "native_admission": "unresolved",
    }


def preflight(folder):
    freeze = json.loads((folder / "freeze.json").read_text())
    if (
        freeze["schema"] != "polli.stream-piece-feasibility-protocol/1"
        or freeze["physical_package"] is not None
        or freeze["native_observation"]
    ):
        raise ValueError("Not an unqualified geometry-only protocol")
    if (
        sha(
            ROOT / "calibration/pl1191-construction-v1/maintained-water-definition.json"
        )
        != freeze["definition_sha256"]
    ):
        raise ValueError("Primary maintained-water definition changed")
    for name, expected_hash in freeze["source_files_sha256"].items():
        if sha(ROOT / name) != expected_hash:
            raise ValueError(f"Stream compiler/validator changed: {name}")
    for name, expected_hash in freeze["files_sha256"].items():
        if sha(folder / name) != expected_hash:
            raise ValueError(f"Stream protocol input changed: {name}")
    for name, expected in zip(
        ("pieces.json", "stream-plan.json", "inventory.json"), analyze(folder)
    ):
        if json.loads((folder / name).read_text()) != expected:
            raise ValueError(f"Stream protocol does not replay: {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("stage")
    create.add_argument("source", type=Path)
    create.add_argument("output", type=Path)
    check = commands.add_parser("preflight")
    check.add_argument("folder", type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    result = globals()[command](**args)
    print(json.dumps(result or {"status": "inputs_and_protocol_unchanged"}, indent=2))
