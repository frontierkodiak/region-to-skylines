"""Read-only witnesses for frozen stream proposals; never alter admission masks."""

import argparse
from collections import Counter
import heapq
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree

from closed_storage_candidate import ROOT, sha
from natural_storage_candidate import write
from region import HALF, raster
from stream_construction import STEPS, preflight as stream_preflight
from waterway_pieces import digest

POLICY = "frozen-stream-contact-and-bound-witness-v1"


def members_for(component, clips):
    return sorted(
        {
            tuple(n)
            for name in component["source_clips"]
            for n in clips[name]["nodes_rc"]
        }
    )


def envelope_for(members):
    own = set(members)
    return sorted(
        n
        for n in own | {(r + y, c + x) for r, c in own for y, x in STEPS}
        if 0 <= n[0] <= 1080 and 0 <= n[1] <= 1080
    )


def xz(node):
    return [node[1] * 16 - HALF, HALF - node[0] * 16]


def raw_distance(point, points):
    """Distance to captured clipped geometry, separate from the admission raster."""
    points = np.asarray(points, float)
    if len(points) == 1:
        return float(np.linalg.norm(points[0] - point))
    a, v = points[:-1], np.diff(points, axis=0)
    length = np.einsum("ij,ij->i", v, v)
    t = np.divide(
        np.einsum("ij,ij->i", point - a, v),
        length,
        out=np.zeros_like(length),
        where=length > 0,
    ).clip(0, 1)
    return float(np.linalg.norm(a + t[:, None] * v - point, axis=1).min())


def contact_relation(own_clips, other, rows, clips):
    source = other["id"].rsplit(":clip:", 1)[0]
    own_rows = {name.rsplit(":clip:", 1)[0] for name in own_clips}
    same_source = source in own_rows
    shared_points = sorted(
        {tuple(p) for name in own_clips for p in clips[name]["points_xz"]}
        & {tuple(p) for p in other["points_xz"]}
    )
    shared_nodes = sorted(
        {tuple(n) for name in own_clips for n in clips[name]["nodes_rc"]}
        & {tuple(n) for n in other["nodes_rc"]}
    )
    row = rows[source]
    return {
        "source_row_relation": "same_captured_row_other_clipped_part"
        if same_source
        else "different_captured_source_row",
        "scope": row["status"],
        "scope_reason": row.get("reason"),
        "shared_captured_vertices_xz": [list(p) for p in shared_points],
        "shared_native_nodes_rc": [list(n) for n in shared_nodes],
        "junction": "mapped_vertex_contact_hydraulics_unresolved"
        if shared_points
        else "native_vertex_contact_only_hydraulics_unresolved"
        if shared_nodes
        else "buffer_proximity_only_hydraulic_relation_unknown",
        "identity_limit": "Different source rows do not prove different hydraulic waterways; no name-based merge or mask change.",
    }


def foreign_contacts(component, members, rows, clips):
    """Every guarded envelope node, attributed to every contacting foreign clip."""
    envelope = envelope_for(members)
    own = set(members)
    queries = np.asarray(envelope) * 16
    hits, covered = [], set()
    for row in rows.values():
        if row["field"] != "streams":
            continue
        for clip in row["clips"]:
            nodes = sorted(
                {
                    tuple(n)
                    for n in clip["nodes_rc"]
                    if row["status"] != "perennial_surface" or tuple(n) not in own
                }
            )
            if not nodes:
                continue
            distance, nearest = cKDTree(np.asarray(nodes) * 16).query(queries)
            selected = np.flatnonzero(distance <= 128)
            if not len(selected):
                continue
            witnesses = []
            for index in selected:
                node = envelope[index]
                covered.add(node)
                witnesses.append(
                    {
                        "node_rc": list(node),
                        "role": "channel" if node in own else "untouched_bank",
                        "protected_node_rc": list(nodes[int(nearest[index])]),
                        "native_distance_m": float(distance[index]),
                        "raw_geometry_distance_m": raw_distance(
                            np.array(xz(node)), clip["points_xz"]
                        ),
                    }
                )
            hits.append(
                {
                    "source_id": row["id"],
                    "source_sha256": row["source_sha256"],
                    "clip_id": clip["id"],
                    "buffer_m": 128,
                    "relation": contact_relation(
                        component["source_clips"], clip, rows, clips
                    ),
                    "witnesses": witnesses,
                }
            )
    expected = component["guards"]["foreign_stream_buffer_hits"]
    if len(covered) != expected:
        raise ValueError("Foreign witness union does not match frozen protection")
    return {"envelope_nodes": len(covered), "contacts": hits}


def infrastructure_sources(geometry, hydro, layout):
    """Decompose the existing protection into exact raster/analytic sources."""
    sources = []
    for field in ("rivers", "undergroundWaterways", "riverAreas", "oceans", "lakes"):
        polygon = field in ("riverAreas", "oceans", "lakes")
        for index, feature in enumerate(geometry.get(field, [])):
            mask = raster(geometry["sq"], [feature], polygons=polygon)
            nodes = np.argwhere(mask)
            if len(nodes):
                sources.append(
                    {
                        "id": f"{field}:{index}",
                        "source_sha256": digest(feature),
                        "radius_m": 128,
                        "nodes": nodes,
                        "model": "existing_PIL_raster_Euclidean_buffer",
                    }
                )
    sources.append(
        {
            "id": "start_area:landing",
            "source_sha256": digest(hydro["start_area"]["landing"]),
            "radius_m": 128,
            "position_xz": hydro["start_area"]["landing"],
            "model": "existing_analytic_radius",
        }
    )
    for index, source in enumerate(hydro["sources"]):
        rate = max(
            source["capacity"], source.get("output_capacity", source["capacity"])
        )
        sources.append(
            {
                "id": f"hydrology:sources:{index}",
                "source_sha256": digest(source),
                "radius_m": float(
                    10 + 0.4 * np.sqrt(np.floor(rate * 65535 + 0.5)) + 64
                ),
                "position_xz": [source["position"][0], source["position"][2]],
                "model": "existing_control_radius_plus_64m_not_physical_flux",
            }
        )
    for index, route in enumerate(layout["routes"]):
        positions = [hydro["node_positions"][str(n)] for n in route["nodes"]]
        if len(positions) < 2:
            continue
        image = Image.new("L", (1081, 1081))
        ImageDraw.Draw(image).line(
            [((p[0] + HALF) / 16, (HALF - p[2]) / 16) for p in positions],
            fill=255,
            width=1,
        )
        sources.append(
            {
                "id": f"layout:routes:{index}",
                "source_sha256": digest({"route": route, "positions": positions}),
                "radius_m": 112,
                "nodes": np.argwhere(np.asarray(image) > 0),
                "model": "existing_PIL_corridor_raster_Euclidean_buffer",
            }
        )
    for source in sources:
        if "nodes" in source:
            source["tree"] = cKDTree(source["nodes"] * 16)
    return sources


def infrastructure_contacts(component, members, sources):
    envelope, own = envelope_for(members), set(members)
    queries = np.asarray(envelope) * 16
    contacts, covered = [], set()
    for source in sources:
        if "tree" in source:
            distance, nearest = source["tree"].query(queries)
        else:
            distance = np.linalg.norm(
                np.array([xz(n) for n in envelope]) - source["position_xz"], axis=1
            )
        selected = np.flatnonzero(distance <= source["radius_m"])
        if not len(selected):
            continue
        witnesses = []
        for index in selected:
            node = envelope[index]
            covered.add(node)
            witness = {
                "node_rc": list(node),
                "role": "channel" if node in own else "untouched_bank",
                "distance_m": float(distance[index]),
            }
            if "nodes" in source:
                witness["protected_raster_node_rc"] = source["nodes"][
                    nearest[index]
                ].tolist()
            witnesses.append(witness)
        contacts.append(
            {
                **{k: v for k, v in source.items() if k not in ("nodes", "tree")},
                "witnesses": witnesses,
            }
        )
    if len(covered) != component["guards"]["infrastructure_or_other_water_hits"]:
        raise ValueError(
            "Infrastructure witness union does not match frozen protection"
        )
    return {"envelope_nodes": len(covered), "contacts": contacts}


def trace_bounds(lower, upper, edges):
    """A checkable path from each greatest stage to one limiting ancestor U."""
    adjacency, degree = [[] for _ in lower], [0] * len(lower)
    for a, b in sorted(set(map(tuple, edges))):
        adjacency[a].append(b)
        degree[b] += 1
    ready = [i for i, d in enumerate(degree) if d == 0]
    heapq.heapify(ready)
    stage, parent = list(upper), [None] * len(lower)
    visited = 0
    while ready:
        node = heapq.heappop(ready)
        visited += 1
        for other in adjacency[node]:
            if stage[node] < stage[other]:
                stage[other], parent[other] = stage[node], node
            degree[other] -= 1
            if not degree[other]:
                heapq.heappush(ready, other)
    if visited != len(lower):
        raise ValueError("No DAG bound certificate for a directed cycle")
    result = []
    for node in range(len(lower)):
        if stage[node] >= lower[node]:
            continue
        path = [node]
        while parent[path[-1]] is not None:
            path.append(parent[path[-1]])
        result.append(
            {
                "node": node,
                "lower_q": int(lower[node]),
                "local_upper_q": int(upper[node]),
                "greatest_possible_q": int(stage[node]),
                "limiting_ancestor": path[-1],
                "path": path[::-1],
                "deficit_q": int(lower[node] - stage[node]),
                "local_bounds_already_conflict": bool(upper[node] < lower[node]),
            }
        )
    return result


def bound_witnesses(component, members, clips, floor, water, comparison=None):
    own = set(members)
    ownership = {
        node: sorted(
            name
            for name in component["source_clips"]
            if list(node) in clips[name]["nodes_rc"]
        )
        for node in members
    }
    banks, lower, upper = [], [], []
    for node in members:
        bank = sorted(
            (node[0] + y, node[1] + x)
            for y, x in STEPS
            if (node[0] + y, node[1] + x) not in own
            and 0 <= node[0] + y <= 1080
            and 0 <= node[1] + x <= 1080
        )
        depth = max(64, int(water[node]))
        lower.append(max(depth, int(floor[node]) - 192 + depth))
        minimum = min(int(floor[n]) for n in bank)
        upper.append(min(65535, minimum - 32))
        banks.append([n for n in bank if floor[n] == minimum])

    def describe(node):
        record = {
            "node_rc": list(node),
            "xz_m": xz(node),
            "floor_q": int(floor[node]),
            "old_depth_q": int(water[node]),
            "source_clips": ownership.get(node, []),
        }
        if comparison is not None:
            raw, fitted_banks = comparison
            record.update(
                captured_input_m=float(raw[node]),
                captured_banks_m=float(fitted_banks[node]),
                authored_minus_captured_m=float(floor[node] / 64 - raw[node]),
                authored_minus_rounded_captured_q=int(
                    floor[node] - np.floor(raw[node] * 64 + 0.5)
                ),
            )
        return record

    witnesses = trace_bounds(lower, upper, component["source_edges"])
    compact = [
        {k: w[k] for k in ("node", "lower_q", "greatest_possible_q")} for w in witnesses
    ]
    if compact != component["geometry"]["witnesses"]:
        raise ValueError("Bound witnesses do not equal frozen solver refusals")
    for witness in witnesses:
        node, ancestor = members[witness["node"]], members[witness["limiting_ancestor"]]
        witness.update(
            node_evidence=describe(node),
            ancestor_evidence=describe(ancestor),
            limiting_untouched_banks=[
                describe(n) for n in banks[witness["limiting_ancestor"]]
            ],
            directed_path_rc=[list(members[i]) for i in witness["path"]],
            path_source_clips=[ownership[members[i]] for i in witness["path"]],
            required_cut_at_greatest_stage_q=max(
                0,
                int(floor[node])
                - (witness["greatest_possible_q"] - max(64, int(water[node]))),
            ),
        )
    return {
        "witnesses": witnesses,
        "summary": {
            "violating_nodes": len(witnesses),
            "local_bound_conflicts": sum(
                w["local_bounds_already_conflict"] for w in witnesses
            ),
            "propagation_only_conflicts": sum(
                not w["local_bounds_already_conflict"] for w in witnesses
            ),
            "ancestor_other_than_self": sum(
                w["node"] != w["limiting_ancestor"] for w in witnesses
            ),
            "largest_deficit_m": max(w["deficit_q"] for w in witnesses) / 64,
        },
    }


def analyze(folder):
    source = folder / "source"
    stream_preflight(source)
    geometry, hydro, layout, pieces, plan = [
        json.loads((source / name).read_text())
        for name in (
            "geometry.json",
            "hydrology.json",
            "layout.json",
            "pieces.json",
            "stream-plan.json",
        )
    ]
    floor, water = [
        np.flipud(np.fromfile(source / name, "<u2").reshape(1081, 1081)).astype(
            np.int64
        )
        for name in ("terrain.u16", "water.u16")
    ]
    comparison = None
    if (folder / "comparison").exists():
        parent = folder / "comparison"
        for name in ("geometry.json", "terrain.u16"):
            if sha(parent / name) != sha(source / name):
                raise ValueError(
                    "Comparison does not bind identical geometry/authored terrain"
                )
        raw = (
            np.asarray(Image.open(parent / "source-input.png"), dtype=float)
            * 1024
            / 65535
        )
        banks = np.fromfile(parent / "source-banks.f32", "<f4").reshape(1081, 1081)
        if (
            raw.shape != floor.shape
            or not np.isfinite(raw).all()
            or not np.isfinite(banks).all()
        ):
            raise ValueError("Invalid captured comparison grids")
        comparison = raw, banks
    rows = {row["id"]: row for row in pieces["rows"]}
    clips = {c["id"]: c for row in rows.values() for c in row["clips"]}
    infrastructure = infrastructure_sources(geometry, hydro, layout)
    results = []
    for component in plan["components"]:
        members = members_for(component, clips)
        result = {
            "id": component["id"],
            "source_clips": component["source_clips"],
            "frozen_geometry_status": component["geometry"]["status"],
            "frozen_status": component["status"],
            "native_admission": "unresolved",
        }
        if component["geometry"]["status"] == "feasible":
            if component["guards"]["protection_unknown"]:
                raise ValueError("Cannot attribute unknown protection")
            result["foreign_streams"] = foreign_contacts(
                component, members, rows, clips
            )
            result["infrastructure"] = infrastructure_contacts(
                component, members, infrastructure
            )
            for contact in result["infrastructure"]["contacts"]:
                if contact["id"] in rows:
                    contact["source_clip_ids"] = [
                        c["id"] for c in rows[contact["id"]]["clips"]
                    ]
        elif component["geometry"]["status"] == "infeasible_bounds":
            result["bounds"] = bound_witnesses(
                component, members, clips, floor, water, comparison
            )
        results.append(result)
    return {
        "schema": "polli.stream-refusal-witnesses/1",
        "policy": POLICY,
        "source_freeze_sha256": sha(source / "freeze.json"),
        "components": results,
        "summary": dict(Counter(c["frozen_geometry_status"] for c in results)),
        "floor_scope": "authored quantized terrain, NOT actual native hydraulic floor",
        "bound_scope": "Proof only under frozen graph, provisional endpoint direction and untouched exterior bank model; not geographic impossibility.",
        "contacts_scope": "Complete guarded-node attribution; raw geometry distances do not replace native buffer distances. Nearest witnesses retain exact source IDs; not hydraulic identity or junction acceptance.",
        "physical_package": None,
        "native_observation": False,
        "stable_water_promise": "unknown",
    }


def stage(source, output, comparison=None):
    if output.exists():
        raise ValueError("Use a fresh witness protocol directory")
    stream_preflight(source)
    output.mkdir(parents=True)
    shutil.copytree(source, output / "source")
    if comparison is not None:
        (output / "comparison").mkdir()
        for name in (
            "geometry.json",
            "terrain.u16",
            "source-input.png",
            "source-banks.f32",
        ):
            shutil.copyfile(comparison / name, output / "comparison" / name)
    result = analyze(output)
    write(output / "witnesses.json", result)
    frozen = json.loads((source / "freeze.json").read_text())
    freeze = {
        "schema": "polli.stream-witness-protocol/1",
        "source_files_sha256": {
            **frozen["source_files_sha256"],
            "stream_witnesses.py": sha(ROOT / "stream_witnesses.py"),
        },
        "files_sha256": {
            str(p.relative_to(output)): sha(p)
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
        "definition_sha256": frozen["definition_sha256"],
        "panel_sha256": frozen["panel_sha256"],
        "native_observation": False,
        "physical_package": None,
        "holdout_inputs_accessed": False,
    }
    write(output / "freeze.json", freeze)
    preflight(output)
    return {"freeze_sha256": sha(output / "freeze.json"), "summary": result["summary"]}


def preflight(folder):
    frozen = json.loads((folder / "freeze.json").read_text())
    if (
        frozen["schema"] != "polli.stream-witness-protocol/1"
        or frozen["native_observation"]
        or frozen["physical_package"] is not None
        or frozen["holdout_inputs_accessed"]
    ):
        raise ValueError("Not a read-only witness protocol")
    original = json.loads((folder / "source/freeze.json").read_text())
    expected_sources = {
        **original["source_files_sha256"],
        "stream_witnesses.py": sha(ROOT / "stream_witnesses.py"),
    }
    if frozen["source_files_sha256"] != expected_sources:
        raise ValueError("Witness dependency closure changed")
    for name, expected in frozen["source_files_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Witness dependency changed: {name}")
    expected_paths = set(frozen["files_sha256"]) | {"freeze.json"}
    if {
        str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file()
    } != expected_paths:
        raise ValueError("Witness physical file inventory changed")
    for name, expected in frozen["files_sha256"].items():
        if sha(folder / name) != expected:
            raise ValueError(f"Witness input/result changed: {name}")
    result = analyze(folder)
    if json.loads((folder / "witnesses.json").read_text()) != result:
        raise ValueError("Witness result does not replay")
    if any(frozen[k] != original[k] for k in ("definition_sha256", "panel_sha256")):
        raise ValueError("Witness definition/panel changed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("stage")
    create.add_argument("source", type=Path)
    create.add_argument("output", type=Path)
    create.add_argument("--comparison", type=Path)
    check = commands.add_parser("preflight")
    check.add_argument("folder", type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(
        json.dumps(
            globals()[command](**args) or {"status": "witnesses_replayed"}, indent=2
        )
    )
