"""Literal open-face witnesses and explicit source-authority gaps, not admission.

No in-square bank is removed; no profile or envelope is solved again. Public
service metadata is discovery evidence only, never mapped bank or supply proof.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import shutil
import urllib.error
import urllib.request

import numpy as np

from bank_authority import ROOT, load, sha, write
from coastal_floor_audit import grid
from open_channel_plan import preflight as parent_preflight
from stage_contracts_v2 import json_scalars
from waterway_pieces import digest

POLICY = "literal-open-interface-source-authority-v1"
DESIGN = "calibration/pl1191-construction-v1/development/phase26-interface-authority-policy.md"
FILES = (
    "diagnostics/open_interface_authority.py",
    "diagnostics/test_open_interface_authority.py",
    DESIGN,
)
SERVICE = "https://hosting.wsapi.cloud.bom.gov.au/arcgis/rest/services/ahgf/Geofabric_V3x_All_Products/MapServer"
LAYER_NAMES = (
    "mapped stream",
    "mapped connectivity",
    "network stream",
    "network connectivity",
    "waterbody",
)


def cell_consistency(nodes, targets, beds):
    if not len(nodes) == len(targets) == len(beds):
        raise ValueError("Complete equal-sized node potentials required")
    cells = defaultdict(list)
    for i, (node, target, bed) in enumerate(zip(nodes, targets, beds)):
        cells[tuple(node)].append((i, int(target), int(bed)))
    repeated = [
        {
            "node_rc": list(n),
            "graph_nodes_target_bed_q": values,
            "consistent": len({(t, b) for _, t, b in values}) == 1,
        }
        for n, values in sorted(cells.items())
        if len(values) > 1
    ]
    return {
        "single_valued": all(r["consistent"] for r in repeated),
        "repeated_cells": repeated,
        "materialized": False,
    }


def require_single_valued_cells(nodes, targets, beds):
    result = cell_consistency(nodes, targets, beds)
    if not result["single_valued"]:
        raise ValueError("Refuse conflicting potentials at one native raster cell")
    return result  # This guards representation only, never physical admission.


def literal_faces(clip, side):
    if not clip[f"{side}_clipped"]:
        return []
    x, z = clip["points_xz"][0 if side == "start" else -1]
    return [
        face
        for face, match in (
            ("west", x == -8640),
            ("east", x == 8640),
            ("north", z == 8640),
            ("south", z == -8640),
        )
        if match
    ]


def outside_faces(node, size):
    r, c = node
    return {
        face
        for face, match in (
            ("north", r < 0),
            ("south", r >= size),
            ("west", c < 0),
            ("east", c >= size),
        )
        if match
    }


def open_bank_witness(node, own, floor, faces):
    """Partition the FULL bank. Only exterior cells on a literal face are ports."""
    r, c = node
    bank = {
        (r + y, c + x) for y in (-1, 0, 1) for x in (-1, 0, 1) if (y, x) != (0, 0)
    } - own
    inside, opening, unknown = [], [], []
    for n in sorted(bank):
        crossed = outside_faces(n, floor.shape[0])
        if not crossed:
            inside.append(list(n))
        elif crossed <= set(faces):
            opening.append(list(n))
        else:
            unknown.append(list(n))
    if set(map(tuple, inside + opening + unknown)) != bank:
        raise ValueError("A full-bank witness disappeared")
    return {
        "node_rc": list(node),
        "literal_open_faces": sorted(faces),
        "all_in_square_bank_nodes_rc": inside,
        "literal_exterior_open_face_nodes_rc": opening,
        "unknown_exterior_lateral_bank_nodes_rc": unknown,
        "conditional_in_square_lateral_stage_cap_q": min(
            int(floor[tuple(n)]) for n in inside
        )
        - 32
        if inside
        else None,
        "in_square_bank_nodes_removed": 0,
        "external_boundary_stage_and_capacity": None,
        "admission": False,
    }


def source_facts(geometry, topology):
    rows = {r["id"]: r for r in topology["rows"]}
    output = []
    for name in topology["eligible_clip_ids"]:
        clip = topology["clips"][name]
        row = rows[clip["source_id"]]
        source = geometry[row["field"]][row["source_index"]]
        props = {
            **source.get("sourceFeature", {}).get("properties", {}),
            **{k: v for k, v in source.items() if k not in ("pts", "sourceFeature")},
        }
        hints = {
            k: v
            for k, v in props.items()
            if k
            in (
                "width",
                "est_width",
                "bankfull_width",
                "flow_direction",
                "direction",
                "oneway",
                "osm_id",
                "id",
            )
        }
        output.append(
            {
                "clip_id": name,
                "source_id": clip["source_id"],
                "source_feature_sha256": row.get("source_sha256", digest(source)),
                "clip_sha256": digest(clip),
                "captured_property_keys": sorted(props),
                "unvalidated_hints": hints,
                "piece_linked_lateral_authority": None,
                "source_or_explicit_authored_direction": None,
                "explicit_inlet_junction_outlet_plan": None,
                "source_faithful_physical_admission": "unresolved_missing_piece_linked_authority",
                "geographic_impossibility": False,
            }
        )
    return output


def analyze(case, previous):
    topology = previous["complete_source_topology"]
    config = load(case / "case.json")
    geometry_path = (
        case
        / "input"
        / (
            "physical/geometry.json"
            if config["kind"] == "coastal"
            else "source/geometry.json"
        )
    )
    geometry = load(geometry_path)
    result = {
        "case": case.name,
        "source_geometry_file_sha256": sha(geometry_path),
        "previous_complete_graph_sha256": digest(topology),
        "all_original_contracts_retained": previous["original_contracts"],
        "source_authority_registry": source_facts(geometry, topology),
        "physical_admission": False,
        "promise": "unknown",
        "open_port_components": None,
        "cell_consistency": None,
    }
    if previous["components"] is None:
        return {
            **result,
            "retained_base_refusal": previous["retained_base_refusal"],
            "floor": None,
        }
    floor_path = (
        case / "current-floor.u16"
        if config["kind"] == "coastal"
        else case / "input/physical/terrain.u16"
    )
    floor = np.flipud(grid(floor_path))
    declarations = defaultdict(list)
    for name in topology["eligible_clip_ids"]:
        clip = topology["clips"][name]
        for side, index in (("start", 0), ("end", -1)):
            faces = literal_faces(clip, side)
            if faces:
                declarations[tuple(clip["nodes_rc"][index])].append(
                    {
                        "clip": name,
                        "side": side,
                        "faces": faces,
                        "source_clip_sha256": digest(clip),
                    }
                )
    ports = []
    consistency = []
    for component in previous["components"]:
        recipe = component["conditional_variable_stage_plan"]
        nodes = [topology["nodes"][i]["node_rc"] for i in component["graph_node_ids"]]
        if recipe["status"] == "feasible":
            consistency.append(
                {
                    "component": component["id"],
                    **cell_consistency(nodes, recipe["target_q"], recipe["bed_q"]),
                }
            )
        if recipe["status"] != "unresolved_open_port_lateral_or_exterior_bank":
            continue
        own = set(map(tuple, nodes))
        witnesses = []
        for i in recipe["missing_exterior_bank_at_nodes"]:
            node = nodes[i]
            graph_node = topology["nodes"][component["graph_node_ids"][i]]
            own_clips = {alias[0] for alias in graph_node["source_aliases"]}
            records = [
                r for r in declarations.get(tuple(node), []) if r["clip"] in own_clips
            ]
            faces = {f for r in records for f in r["faces"]}
            witnesses.append(
                {
                    **open_bank_witness(node, own, floor, faces),
                    "literal_source_declarations": records,
                }
            )
        ports.append(
            {
                "component": component["id"],
                "source_clips": component["source_clips"],
                "previous_status_unchanged": recipe["status"],
                "witnesses": witnesses,
                "all_missing_exterior_neighbors_have_literal_face_declaration": all(
                    not w["unknown_exterior_lateral_bank_nodes_rc"] for w in witnesses
                ),
                "conditional_lateral_geometry_only": True,
                "no_new_profile_solved": True,
                "bank_width_direction_boundary_plan_authority": None,
                "physical_admission": False,
            }
        )
    return {
        **result,
        "floor": previous["floor"],
        "open_port_components": ports,
        "cell_consistency": consistency,
        "new_profiles_or_envelopes_solved": False,
        "in_square_bank_nodes_removed": 0,
    }


def stage(parent, results, review, output):
    parent_preflight(parent)
    if output.exists():
        raise ValueError("Fresh interface protocol required")
    thread = load(review)
    if not any(
        r.get("id") == "01a2079e-ff5e-7124-9ecb-9b87f77c2a55"
        and "Verdict: PASS" in r.get("content", "")
        for r in thread
    ):
        raise ValueError("Actual PL1295 result required")
    receipt = load(results / "receipt.json")
    if receipt["prospective_freeze_sha256"] != sha(parent / "freeze.json"):
        raise ValueError("Wrong prior graph")
    for n, value in receipt["result_files_sha256"].items():
        if sha(results / n) != value:
            raise ValueError(f"Prior result changed: {n}")
    output.mkdir(parents=True)
    shutil.copytree(parent, output / "parent")
    shutil.copytree(results, output / "prior-results")
    shutil.copyfile(review, output / "review-thread.json")
    write(
        output / "metadata-spec.json",
        {
            "service": SERVICE,
            "layer_name_contains": LAYER_NAMES,
            "only_metadata_no_feature_query": True,
            "maximum_selected_layers": 32,
            "question": "Which official direction/connectivity/waterbody schema fields are exposed? Metadata alone supplies no clip correspondence, surveyed width, boundary stage or capacity.",
            "discovery_metadata_known_before_freeze": True,
        },
    )
    dependencies = dict(load(parent / "freeze.json")["source_files_sha256"])
    for name in FILES:
        dependencies[name] = sha(ROOT / name)
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": load(parent / "freeze.json")["cases"],
            "source_files_sha256": dependencies,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "prior_outcomes_known": True,
            "new_native_or_physical": False,
        },
    )


def preflight(folder):
    frozen = load(folder / "freeze.json")
    if frozen["policy"] != POLICY:
        raise ValueError("Wrong interface-authority rule")
    for root, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for n, value in frozen[key].items():
            if sha(root / n) != value:
                raise ValueError(f"Bound method/input changed: {n}")
    parent_preflight(folder / "parent")


def capture_metadata(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh metadata capture required")
    output.mkdir(parents=True)
    spec = load(folder / "metadata-spec.json")
    records = []

    def fetch(label, url):
        request = urllib.request.Request(
            url, headers={"User-Agent": "PL-1191-development-source-metadata/1"}
        )
        try:
            response = urllib.request.urlopen(request, timeout=45)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            status = response.status
            headers = dict(response.headers.items())
        path = output / f"{label}.json"
        path.write_bytes(body)
        records.append(
            {
                "filename": path.name,
                "url": url,
                "status": status,
                "headers": headers,
                "sha256": sha(path),
            }
        )
        if status != 200:
            raise ValueError(f"Metadata HTTP {status}; retained response, no retry")
        result = load(path)
        if "error" in result:
            raise ValueError("ArcGIS metadata error retained, no retry")
        return result

    try:
        service = fetch("service", spec["service"] + "?f=pjson")

        def normalized(s):
            return "".join(c for c in s.lower() if c.isalnum())

        selected = [
            layer
            for layer in service.get("layers", [])
            if not layer.get("subLayerIds")
            and any(
                normalized(k) in normalized(layer["name"])
                for k in spec["layer_name_contains"]
            )
        ]
        if len(selected) > spec["maximum_selected_layers"]:
            raise ValueError("Metadata budget exceeded; not truncated")
        for layer in selected:
            fetch(f"layer-{layer['id']}", spec["service"] + f"/{layer['id']}?f=pjson")
    finally:
        write(
            output / "receipt.json",
            {
                "prospective_freeze_sha256": sha(folder / "freeze.json"),
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "records": records,
                "feature_queries": 0,
                "no_geographic_inputs_or_native": True,
            },
        )


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh authority results required")
    output.mkdir(parents=True)
    for name in load(folder / "freeze.json")["cases"]:
        previous = load(folder / "prior-results" / f"{name}.json")
        write(
            output / f"{name}.json",
            json_scalars(analyze(folder / "parent/cases" / name, previous)),
        )
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "prospective_freeze_sha256": sha(folder / "freeze.json"),
            "result_files_sha256": {
                p.name: sha(p) for p in sorted(output.glob("*.json"))
            },
            "profiles_solved": 0,
            "new_physical_or_native": False,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, arguments in (
        ("stage", ["parent", "results", "review", "output"]),
        ("preflight", ["folder"]),
        ("capture_metadata", ["folder", "output"]),
        ("evaluate", ["folder", "output"]),
    ):
        cmd = sub.add_parser(name)
        for argument in arguments:
            cmd.add_argument(argument, type=Path)
    args = vars(parser.parse_args())
    globals()[args.pop("command")](**args)
