"""Read-only half-metre elevated-stage envelopes and explicit open-edge ports.

The elevated region is instrumentation, NOT a new channel/basin footprint or a
license to retire untouched banks. Raster topology is not hydraulic capacity.
"""

import argparse
from collections import Counter
import hashlib
from pathlib import Path
import shutil
import struct

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from bank_authority import ROOT, load, sha, write
from coastal_floor_audit import grid
from crp import read_package
from local_supply_envelope import physical, preflight as parent_preflight, source_masks
from region import raster
from template import manager_tag
from waterway_pieces import digest

POLICY = "elevated-stage-spill-open-port-topology-v1"
DESIGN = "calibration/pl1191-construction-v1/development/phase23-spill-port-policy.md"
METHOD = "diagnostics/spill_port_topology.py"


def edge_arcs(nodes, width):
    remaining = set(int(n) for n in nodes)
    arcs = []
    while remaining:
        todo = [min(remaining)]
        remaining.remove(todo[0])
        found = []
        while todo:
            node = todo.pop()
            found.append(node)
            r, c = divmod(node, width)
            for y in (-1, 0, 1):
                for x in (-1, 0, 1):
                    if 0 <= r + y < width and 0 <= c + x < width:
                        other = (r + y) * width + c + x
                        if other in remaining:
                            remaining.remove(other)
                            todo.append(other)
        arcs.append(sorted(found))
    return arcs


def elevated_envelope(floor, initial, mapped, stage, nodes, adjacency, guards, banks):
    structure = ndimage.generate_binary_structure(2, adjacency // 4)
    base, _ = ndimage.label(floor < stage, structure)
    elevated, _ = ndimage.label(floor.astype(np.int64) < stage + 32, structure)
    slices = ndimage.find_objects(elevated)
    edge = np.zeros_like(mapped)
    edge[[0, -1]] = True
    edge[:, [0, -1]] = True
    result = []
    for label in sorted(int(v) for v in np.unique(base.ravel()[nodes])):
        candidates = nodes[base.ravel()[nodes] == label]
        upper_id = int(elevated.ravel()[candidates[0]])
        if label == 0 or not np.all(elevated.ravel()[candidates] == upper_id):
            raise ValueError(
                "Base component not contained in a single elevated component"
            )
        box = slices[upper_id - 1]
        upper = elevated[box] == upper_id
        old = base[box] == label
        annulus = upper & ~old
        rr, cc = np.nonzero(upper)
        upper_nodes = (rr + box[0].start) * floor.shape[1] + cc + box[1].start
        edge_nodes = upper_nodes[edge.ravel()[upper_nodes]]
        ports = []
        for port_nodes in edge_arcs(edge_nodes, floor.shape[1]):
            ports.append(
                {
                    "nodes": port_nodes,
                    "serialized_stage_or_outlet_authority": "not supplied by raster contact",
                    "upstream_supply_port": None,
                    "flow_direction_and_capacity": "unknown",
                }
            )
        outside = upper & ~mapped[box]
        dry = initial[box] == 0
        entering_banks = annulus & banks[box]
        witness = np.flatnonzero(entering_banks)
        first_bank = None
        if witness.size:
            r, c = np.unravel_index(witness[0], upper.shape)
            first_bank = [int(r + box[0].start), int(c + box[1].start)]
        result.append(
            {
                "parent_id": f"stage:{stage}:adj:{adjacency}:component:{label}",
                "stage_q": int(stage),
                "elevated_stage_q": int(stage + 32),
                "adjacency": adjacency,
                "candidate_nodes": candidates.tolist(),
                "base_nodes": int(old.sum()),
                "elevated_nodes": int(upper.sum()),
                "elevated_nodes_i32_sha256": hashlib.sha256(
                    upper_nodes.astype("<i4").tobytes()
                ).hexdigest(),
                "added_diagnostic_nodes": int(annulus.sum()),
                "off_mask_nodes": int(outside.sum()),
                "off_mask_initially_dry_nodes": int((outside & dry).sum()),
                "off_mask_already_initialized_nodes": int((outside & ~dry).sum()),
                "new_envelope_initially_dry_nodes": int((annulus & dry).sum()),
                "old_source_bank_nodes_in_diagnostic_annulus": int(
                    entering_banks.sum()
                ),
                "first_original_source_bank_rc": first_bank,
                "protected_incidence": {
                    name: int((upper & mask[box]).sum())
                    for name, mask in guards.items()
                },
                "ports": ports,
                "topology": "map_edge_open_at_elevated_stage"
                if edge_nodes.size
                else "interior_at_elevated_stage",
                "closed_basin_or_stream_admission": False,
            }
        )
    return result


def network_positions_match(payload, layout, positions):
    tag = manager_tag("NetManager")
    if payload.count(tag) != 1:
        raise ValueError("Unique packed network manager required")
    original = next(
        r["start"] for r in layout["ranges"] if r["type"] == "NetManager+Data"
    )
    delta = payload.index(tag) - original
    for node in layout["nodes"]:
        pos = positions[str(node["id"])]
        offset = node["offset"] + delta
        if payload[offset : offset + 12] != struct.pack(">3f", *pos):
            raise ValueError(
                f"Layout/network source positions differ at node {node['id']}"
            )
    return len(layout["nodes"])


def guard_masks(physical_folder, layout):
    hydro = load(physical_folder / "hydrology.json")
    decoded, controls = physical(physical_folder)
    payload = next(
        a["payload"]
        for a in read_package(next(physical_folder.glob("*.crp")).read_bytes())[1]
        if a["kind"] == 52
    )
    network_count = network_positions_match(payload, layout, hydro["node_positions"])
    r, c = np.indices((1081, 1081))
    x, z = c * 16 - 8640, r * 16 - 8640
    landing = hydro["start_area"]["landing"]
    masks = {"landing_128m": np.hypot(x - landing[0], z - landing[1]) <= 128}
    mask = np.zeros_like(x, bool)
    for source in controls:
        radius = (
            10 + 0.4 * np.sqrt(max(source["intake_rate"], source["output_rate"])) + 64
        )
        mask |= np.hypot(x - source["position"][0], z - source["position"][2]) <= radius
    masks["old_control_radius_plus64m"] = mask
    image = Image.new("L", (1081, 1081))
    draw = ImageDraw.Draw(image)
    for route in layout["routes"]:
        points = [hydro["node_positions"][str(n)] for n in route["nodes"]]
        if len(points) >= 2:
            draw.line(
                [((p[0] + 8640) / 16, (8640 - p[2]) / 16) for p in points],
                fill=255,
                width=1,
            )
    roads = np.flipud(np.asarray(image) > 0)
    masks["old_corridor_112m"] = (
        ndimage.distance_transform_edt(~roads) * 16 <= 112 if roads.any() else roads
    )
    return masks, {
        "all_packed_node_xyz_match_declared_hydro": True,
        "nodes": network_count,
        "control_records": len(controls),
        "layout_sha256": digest(layout),
        "source_budget": "unknown; protected incidence not discharge/flood proof",
    }


def original_banks(source, rows):
    banks = np.zeros((1081, 1081), bool)
    plan = source / "source/stream-plan.json"
    if not plan.exists():
        return (
            banks,
            "no previous stream construction-bank model for coast; no invented banks",
        )
    clips = {c["id"]: c for r in rows for c in r.get("clips", [])}
    for component in load(plan)["components"]:
        nodes = {
            tuple(n)
            for name in component["source_clips"]
            for n in clips[name]["nodes_rc"]
        }
        for r, c in nodes:
            for y in (-1, 0, 1):
                for x in (-1, 0, 1):
                    n = r + y, c + x
                    if n not in nodes and 0 <= n[0] <= 1080 and 0 <= n[1] <= 1080:
                        banks[1080 - n[0], n[1]] = True
    return (
        banks,
        "unchanged full8-neighbour original stream-graph bank union; not a new physical mask",
    )


def analyze(folder, case_name):
    old = folder / "parent-protocol" / case_name
    previous = load(folder / "parent-results" / f"{case_name}.json")
    source = old / "input"
    result = {
        "case": case_name,
        "original_case_sha256": sha(folder / "parent-results" / f"{case_name}.json"),
        "original_rows": len(previous["all_rows"]),
        "original_mandatory_stream_parts": sum(
            len(r.get("clips", []))
            for r in previous["all_rows"]
            if r.get("field") == "streams" and r["status"] == "perennial_surface"
        ),
        "physical_admission": False,
        "new_physical_or_native": False,
    }
    if previous["domains"] is None:
        return {
            **result,
            "original_base_refusal": previous["original_base_refusal"],
            "floor": None,
            "controls": None,
            "envelopes": None,
            "ports": None,
        }
    kind = load(old / "case.json")["kind"]
    physical_folder = source / "physical"
    geometry = load(
        (source / "source/geometry.json")
        if kind == "geographic"
        else physical_folder / "geometry.json"
    )
    rows, _, mapped = source_masks(geometry)
    layout = (
        load(source / "source/layout.json")
        if kind == "geographic"
        else load(folder / "coastal-network-layout.json")
    )
    guards, network_check = guard_masks(physical_folder, layout)
    floor = (
        grid(old / "current-floor.u16")
        if kind == "coastal"
        else grid(physical_folder / "terrain.u16")
    )
    initial = grid(physical_folder / "water.u16")
    banks, bank_authority = original_banks(source, rows)
    prior = {d["id"]: d for d in previous["domains"]}
    envelopes = []
    for stage in sorted({d["stage_q"] for d in previous["domains"]}):
        for adjacency in (4, 8):
            selected = [
                d
                for d in previous["domains"]
                if d["stage_q"] == stage and d["adjacency"] == adjacency
            ]
            nodes = np.asarray(
                sorted({n for d in selected for n in d["candidate_nodes"]}), np.int64
            )
            envelopes.extend(
                elevated_envelope(
                    floor, initial, mapped, stage, nodes, adjacency, guards, banks
                )
            )
    ocean = np.flipud(raster(geometry["sq"], geometry.get("oceans", []), polygons=True))
    endpoint_index = {}
    for row in rows:
        for clip in row.get("clips", []):
            for end, index, clipped in [
                ("start", 0, clip["start_clipped"]),
                ("end", -1, clip["end_clipped"]),
            ]:
                r, c = clip["nodes_rc"][index]
                if clipped or r in (0, 1080) or c in (0, 1080):
                    endpoint_index.setdefault((1080 - r) * 1081 + c, []).append(
                        {
                            "row": row["id"],
                            "clip": clip["id"],
                            "end": end,
                            "source_clipped": clipped,
                            "captured_xz": clip["points_xz"][index],
                        }
                    )
    for record in envelopes:
        if record["base_nodes"] != prior[record["parent_id"]]["nodes"]:
            raise ValueError("Original whole-domain membership count differs")
        for port in record["ports"]:
            port["literal_ocean_mask_nodes"] = int(ocean.ravel()[port["nodes"]].sum())
            port["serialized_sea_level_m"] = previous["sea_m"]
            port["exact_raster_source_endpoint_incidences"] = [
                entry for n in port["nodes"] for entry in endpoint_index.get(n, [])
            ]
    if set(prior) != {r["parent_id"] for r in envelopes}:
        raise ValueError("A complete original envelope disappeared")
    return {
        **result,
        "network_protection_authority": network_check,
        "bank_authority": bank_authority,
        "envelopes": envelopes,
        "topology_counts": dict(Counter(e["topology"] for e in envelopes)),
        "upstream_supply_outlet_capacity_direction": "unknown; explicit empty proposals, no endpoint guessing",
        "water_land_plan": "unresolved; already-wet off-mask shoulders are not surveyed water/land authority",
        "full_original_source_incidence": "complete copied parent ledger/geometry; raster port incidence does not establish hydraulic junction",
    }


def stage(parent_protocol, parent_results, review, layout, output):
    parent_preflight(parent_protocol)
    if output.exists():
        raise ValueError("Fresh read-only spill/port protocol required")
    output.mkdir(parents=True)
    shutil.copytree(parent_protocol, output / "parent-protocol")
    shutil.copytree(parent_results, output / "parent-results")
    shutil.copyfile(review, output / "review-thread.json")
    shutil.copyfile(layout, output / "coastal-network-layout.json")
    previous = load(parent_protocol / "freeze.json")
    dependencies = dict(previous["source_files_sha256"])
    for name in [METHOD, "diagnostics/test_spill_port_topology.py", DESIGN]:
        dependencies[name] = sha(ROOT / name)
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": previous["cases"],
            "source_files_sha256": dict(sorted(dependencies.items())),
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "method_before_outputs": True,
            "earlier_review_and_native_outcomes_known": True,
            "new_physical_or_native": False,
        },
    )


def preflight(folder):
    frozen = load(folder / "freeze.json")
    if frozen["policy"] != POLICY:
        raise ValueError("Wrong spill/port method")
    for base, key in [(ROOT, "source_files_sha256"), (folder, "files_sha256")]:
        for name, value in frozen[key].items():
            if sha(base / name) != value:
                raise ValueError(f"Frozen method/input changed: {name}")
    parent_preflight(folder / "parent-protocol")


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh CPU output required")
    output.mkdir(parents=True)
    for case in load(folder / "freeze.json")["cases"]:
        write(output / f"{case}.json", analyze(folder, case))
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "freeze_sha256": sha(folder / "freeze.json"),
            "result_files_sha256": {
                p.name: sha(p) for p in sorted(output.glob("*.json"))
            },
            "physical_or_native": False,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, args in [
        ("stage", ["parent_protocol", "parent_results", "review", "layout", "output"]),
        ("preflight", ["folder"]),
        ("evaluate", ["folder", "output"]),
    ]:
        p = sub.add_parser(name)
        for arg in args:
            p.add_argument(arg, type=Path)
    args = vars(parser.parse_args())
    globals()[args.pop("command")](**args)
