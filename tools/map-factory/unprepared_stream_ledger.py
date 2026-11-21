"""Source interfaces for retained base refusals; absent physical support is unknown."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil

import numpy as np

from closed_storage_candidate import ROOT, sha
from maintained_water_inventory import compile_inventory, coordinate, position
from natural_storage_candidate import write
from stream_support_ledger import (
    DEFINITIONS,
    all_line_rows,
    contract_parts,
    polygon_catalog,
)
from waterway_incidence import (
    in_polygon,
    intersections,
    micro,
    minimum_distance,
    near_boxes,
)
from waterway_pieces import catalog

SOURCES = [
    "unprepared_stream_ledger.py",
    "stream_support_ledger.py",
    "waterway_incidence.py",
]


def geometry_only(geometry):
    # No synthetic floor, dry grid, empty configured source table or native probe plan.
    inventory = compile_inventory(geometry, {})
    rows = all_line_rows(geometry, catalog(geometry))
    entries = {e["id"]: e for e in inventory["entries"]}
    polygons, models = polygon_catalog(geometry, inventory)
    clips, raw_vertices = {}, defaultdict(list)
    neighbors, owners = defaultdict(set), defaultdict(set)
    for row in rows:
        contracts = entries.get(row["id"], {}).get("contracts", [])
        for clip, ids in zip(row["clips"], contract_parts(geometry, row, contracts)):
            feature = geometry[row["field"]][row["source_index"]]
            raw = defaultdict(list)
            for index, geo in enumerate(feature["pts"]):
                raw[tuple(coordinate(position(geometry["sq"], geo)))].append(
                    (index, tuple(geo))
                )
            for vertex, point in enumerate(clip["points_xz"]):
                for index, geo in raw[tuple(point)]:
                    raw_vertices[geo].append(
                        {
                            "clip_id": clip["id"],
                            "clip_vertex": vertex,
                            "source_vertex": index,
                        }
                    )
            clips[clip["id"]] = {
                "id": clip["id"],
                "source_id": row["id"],
                "source_scope": row["status"],
                "contract_ids": ids,
                "clip": clip,
                "authored_floor": None,
                "authored_initialization": "unknown_no_prepared_initial_grid",
                "forcing_support": "unknown_no_configured_physical_plan",
                "native_admission": "unresolved",
            }
            if row["field"] == "streams" and row["status"] == "perennial_surface":
                nodes = [tuple(n) for n in clip["nodes_rc"]]
                for node in nodes:
                    owners[node].add(clip["id"])
                for a, b in zip(nodes, nodes[1:]):
                    neighbors[a].add(b)
                    neighbors[b].add(a)
    lines = {name: micro(record["clip"]["points_xz"]) for name, record in clips.items()}
    relations, body_relations = [], []
    names = sorted(clips)
    for ai, a in enumerate(names):
        for b in names[ai:]:
            if not near_boxes(lines[a], lines[b]):
                continue
            hits = intersections(lines[a], lines[b], self_pair=a == b)
            if a == b and not hits:
                continue
            distance = 0.0 if hits else minimum_distance(lines[a], lines[b])
            native = (
                sorted(
                    {tuple(n) for n in clips[a]["clip"]["nodes_rc"]}
                    & {tuple(n) for n in clips[b]["clip"]["nodes_rc"]}
                )
                if a != b
                else []
            )
            if distance <= 128 or native:
                relations.append(
                    {
                        "a_clip": a,
                        "b_clip": b,
                        "projected_1um_incidence": hits,
                        "shared_native_nodes_rc": [list(n) for n in native],
                        "minimum_projected_distance_m": distance,
                        "hydraulic_connectivity": "unresolved",
                    }
                )
        for polygon_id, (rings, mask) in models.items():
            if not near_boxes(lines[a], np.concatenate(rings)):
                continue
            hits = [
                {"ring": ri, **h}
                for ri, ring in enumerate(rings)
                for h in intersections(lines[a], ring, closed_b=True)
            ]
            membership = [in_polygon(p, rings) for p in lines[a]]
            distance = (
                0.0
                if hits or any(p != "outside" for p in membership)
                else min(
                    minimum_distance(lines[a], ring, closed_b=True) for ring in rings
                )
            )
            native = [n for n in clips[a]["clip"]["nodes_rc"] if mask[tuple(n)]]
            if distance <= 128 or native:
                body_relations.append(
                    {
                        "clip_id": a,
                        "polygon_id": polygon_id,
                        "projected_1um_incidence": hits,
                        "path_vertex_membership": membership,
                        "native_raster_contact": native,
                        "minimum_projected_distance_m": distance,
                        "hydraulic_connectivity": "unresolved",
                    }
                )
    return {
        "schema": "polli.unprepared-source-interface-ledger/1",
        "line_rows": rows,
        "polygons": polygons,
        "clips": list(clips.values()),
        "line_interfaces": relations,
        "body_interfaces": body_relations,
        "captured_geographic_vertex_incidence": [
            {
                "geographic": list(geo),
                "incidence": incidence,
                "hydraulic_connectivity": "unresolved",
            }
            for geo, incidence in sorted(raw_vertices.items())
            if len(incidence) > 1
        ],
        "native_stream_branches": [
            {
                "node_rc": list(node),
                "neighbors_rc": [list(n) for n in sorted(neighbors[node])],
                "source_clips": sorted(owners[node]),
            }
            for node in sorted(owners)
            if len(neighbors[node]) > 2 or len(owners[node]) > 1
        ],
        "source_contract_inventory": inventory,
        "configured_controls": None,
        "authored_floor": None,
        "authored_initial_grid": None,
        "native_probe_plan": None,
        "new_physical_package": None,
        "native_observation": False,
        "scope": "Complete captured interfaces and prospective source contracts only; physical baseline refused, unknown is not zero, no geographic impossibility or admission.",
        "stable_water_promise": "unknown",
    }


def analyze(folder):
    record = json.loads((folder / "original-preparation.json").read_text())
    slug = json.loads((folder / "case.json").read_text())["slug"]
    refusals = [r for r in record["cases"] if r["square"] == slug]
    if (
        len(refusals) != 1
        or refusals[0]["status"] != "refused_under_construction_bounds"
    ):
        raise ValueError("Missing exact retained original base refusal")
    result = geometry_only(json.loads((folder / "source/geometry.json").read_text()))
    result["retained_base_refusal"] = refusals[0]
    return result


def stage(source, output):
    if output.exists():
        raise ValueError("Use a fresh unprepared interface protocol")
    output.mkdir(parents=True)
    shutil.copytree(source, output / "source")
    shutil.copyfile(
        source.parent / "preparation.json", output / "original-preparation.json"
    )
    write(output / "case.json", {"slug": source.name})
    write(output / "ledger.json", analyze(output))
    original = json.loads(
        (
            ROOT / "calibration/pl1191-construction-v1/stream-piece-freeze-v3.json"
        ).read_text()
    )
    names = set(original["source_files_sha256"]) | set(SOURCES + DEFINITIONS)
    freeze = {
        "schema": "polli.unprepared-source-interface-protocol/1",
        "source_files_sha256": {n: sha(ROOT / n) for n in sorted(names)},
        "files_sha256": {
            str(p.relative_to(output)): sha(p)
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
        "definition_sha256": original["definition_sha256"],
        "panel_sha256": original["panel_sha256"],
        "holdout_inputs_accessed": False,
        "new_physical_package": None,
        "native_observation": False,
    }
    write(output / "freeze.json", freeze)
    preflight(output)
    ledger = json.loads((output / "ledger.json").read_text())
    return {
        "freeze_sha256": sha(output / "freeze.json"),
        "line_rows": len(ledger["line_rows"]),
        "clips": len(ledger["clips"]),
        "line_interfaces": len(ledger["line_interfaces"]),
        "body_interfaces": len(ledger["body_interfaces"]),
        "retained_base_refusal": ledger["retained_base_refusal"],
        "forcing_and_initialization": "unknown",
    }


def preflight(folder):
    frozen = json.loads((folder / "freeze.json").read_text())
    original = json.loads(
        (
            ROOT / "calibration/pl1191-construction-v1/stream-piece-freeze-v3.json"
        ).read_text()
    )
    names = set(original["source_files_sha256"]) | set(SOURCES + DEFINITIONS)
    if (
        frozen["schema"] != "polli.unprepared-source-interface-protocol/1"
        or frozen["new_physical_package"] is not None
        or frozen["native_observation"]
        or frozen["holdout_inputs_accessed"]
    ):
        raise ValueError("Not a retained-refusal source-only protocol")
    if set(frozen["source_files_sha256"]) != names:
        raise ValueError("Unprepared dependency closure changed")
    for name, expected in frozen["source_files_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Unprepared dependency changed: {name}")
    if {str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file()} != set(
        frozen["files_sha256"]
    ) | {"freeze.json"}:
        raise ValueError("Unprepared physical-file inventory changed")
    for name, expected in frozen["files_sha256"].items():
        if sha(folder / name) != expected:
            raise ValueError(f"Unprepared input/result changed: {name}")
    if any(frozen[k] != original[k] for k in ("definition_sha256", "panel_sha256")):
        raise ValueError("Unprepared definition/panel changed")
    if json.loads((folder / "ledger.json").read_text()) != analyze(folder):
        raise ValueError("Unprepared interface ledger does not replay")


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
    print(
        json.dumps(
            globals()[command](**args)
            or {"status": "retained_refusal_interfaces_replayed"},
            indent=2,
        )
    )
