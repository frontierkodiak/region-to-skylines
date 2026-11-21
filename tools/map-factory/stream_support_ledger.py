"""Complete captured interfaces and authored forcing support, not stream admission."""

import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct

import numpy as np

from closed_storage_candidate import ROOT, sha
from crp import N, decode_u16, read_package, water_payload
from maintained_water_inventory import (
    coordinate,
    initial_natural_checks,
    position,
    source_tag,
)
from natural_storage_candidate import write
from osm_highways import arc, clip_box
from region import HALF, raster
from stream_construction import preflight as stream_preflight
from template import manager_tag
from water_diagnostics import bind_sources, decode_water, encoded_sources
from waterway_incidence import (
    in_polygon,
    intersections,
    micro,
    minimum_distance,
    near_boxes,
    point_distances,
)
from waterway_pieces import catalog, digest

POLICY = "complete-source-interface-forcing-ledger-v1"
NEW_SOURCES = ["waterway_incidence.py", "stream_support_ledger.py"]
DEFINITIONS = [
    "calibration/pl1191-construction-v1/" + n
    for n in (
        "maintained-water-definition.json",
        "outcome-freeze.json",
        "inventory-freeze-v2.json",
    )
]
SHARED_PHYSICAL = [
    "geometry.json",
    "hydrology.json",
    "terrain.u16",
    "water.u16",
    "mapped-water.u8",
    "natural-plan.json",
    "probes.json",
]


def package_controls(folder, physical):
    """Bind existing physical provenance and preserve all43bytes of every control."""
    generation = json.loads((physical / "generation.json").read_text())
    if generation["schema"] != "polli.replenished-natural-storage-candidate/1":
        raise ValueError("Unsupported existing physical generation record")
    files = generation["physical_files_sha256"]
    for name, expected in files.items():
        if Path(name).name != name or sha(physical / name) != expected:
            raise ValueError(f"Physical generation binding changed: {name}")
    for name in SHARED_PHYSICAL:
        if sha(folder / name) != files.get(name):
            raise ValueError(f"Source/physical cohort mismatch: {name}")
    if sha(folder / "inventory-v2.json") != files.get("inventory.json"):
        raise ValueError("Source/physical original inventory mismatch")
    hydro = json.loads((folder / "hydrology.json").read_text())
    package = physical / generation["package"]
    simulations = [
        a["payload"] for a in read_package(package.read_bytes())[1] if a["kind"] == 52
    ]
    if len(simulations) != 1:
        raise ValueError("Physical simulation is not unique")
    simulation = simulations[0]
    decoded = decode_water(simulation)
    bind_sources(decoded, hydro)
    if decoded["depth"].astype("<u2").tobytes() != (folder / "water.u16").read_bytes():
        raise ValueError("Physical package initial water differs from source")
    tag = manager_tag("TerrainManager")
    if simulation.count(tag) != 1:
        raise ValueError("Physical terrain manager is not unique")
    terrain, offset = decode_u16(simulation, N, simulation.index(tag) + len(tag))
    delta, _ = decode_u16(simulation, int((terrain != 0).sum()), offset)
    if (
        delta.any()
        or terrain.astype("<u2").tobytes() != (folder / "terrain.u16").read_bytes()
    ):
        raise ValueError("Physical package authored floor differs from source")
    chunk = (
        decoded["tag"]
        + water_payload(
            decoded["depth"],
            encoded_sources(decoded),
            decoded["frame"],
            decoded["sea_level_m"],
        )
        + decoded["tail"]
    )
    if chunk != simulation[decoded["start"] : decoded["end"]]:
        raise ValueError("Physical source/water encoding does not round-trip")
    end = decoded["end"] - 2 - 12
    start = end - len(decoded["sources"]) * 43
    if struct.unpack_from(">H", simulation, start - 2)[0] != len(decoded["sources"]):
        raise ValueError("Physical control-table boundary mismatch")
    controls = []
    floor = np.flipud(terrain.reshape(1081, 1081)) / 64
    for index, (encoded, authored) in enumerate(
        zip(decoded["sources"], hydro["sources"])
    ):
        raw = simulation[start + index * 43 : start + (index + 1) * 43]
        radius = float(
            10 + 0.4 * np.sqrt(max(encoded["intake_rate"], encoded["output_rate"]))
        )
        x, _, z = encoded["position"]
        c, r = (x + HALF) / 16, (HALF - z) / 16
        rr, cc = np.mgrid[
            max(0, int(np.floor(r - radius / 16))) : min(
                1080, int(np.ceil(r + radius / 16))
            )
            + 1,
            max(0, int(np.floor(c - radius / 16))) : min(
                1080, int(np.ceil(c + radius / 16))
            )
            + 1,
        ]
        inside = (cc * 16 - HALF - x) ** 2 + (HALF - rr * 16 - z) ** 2 <= radius**2
        footprint = floor[rr[inside], cc[inside]]
        controls.append(
            {
                "id": f"authored:sources:{index}",
                "authored": authored,
                "encoded": encoded,
                "raw43_hex": raw.hex(),
                "raw43_sha256": hashlib.sha256(raw).hexdigest(),
                "simulation_offset": start + index * 43,
                "source_radius_model_m": radius,
                "protection_radius_m": radius + 64,
                "footprint_nodes": int(inside.sum()),
                "full_radius_inside_square": abs(x) + radius <= HALF
                and abs(z) + radius <= HALF,
                "minimum_static_target_minus_authored_floor_m": float(
                    encoded["target_fixed"] / 64 - footprint.max()
                )
                if len(footprint)
                else None,
                "spatial_association": "source-radius model only, not feature ownership, integrated flux or supply proof",
                "physical_supply_budget": "unmeasured",
            }
        )
    return {
        "package": generation["package"],
        "package_sha256": sha(package),
        "generation_sha256": sha(physical / "generation.json"),
        "simulation_sha256": hashlib.sha256(simulation).hexdigest(),
        "raw_control_table_sha256": hashlib.sha256(simulation[start:end]).hexdigest(),
        "controls": controls,
        "sea_level_m": decoded["sea_level_m"],
        "scope": "Existing authored package bytes/grid binding only; not new physical construction, native readback, runtime identity or geographic ownership proof.",
    }


def all_line_rows(geometry, pieces):
    rows = copy.deepcopy(pieces["rows"])
    for index, feature in enumerate(geometry.get("undergroundWaterways", [])):
        row = catalog({"sq": geometry["sq"], "rivers": [feature], "streams": []})[
            "rows"
        ][0]
        old, new = row["id"], f"undergroundWaterways:{index}"
        row.update(id=new, field="undergroundWaterways", source_index=index)
        for clip in row["clips"]:
            clip["id"] = clip["id"].replace(old + ":", new + ":", 1)
        if not isinstance(feature, dict) or source_tag(feature, "brunnel") != "tunnel":
            row.update(
                status="unresolved",
                reason="underground collection lacks explicit tunnel evidence",
            )
        rows.append(row)
    return rows


def contract_parts(geometry, row, contracts):
    if not contracts:
        return [[] for _ in row["clips"]]
    feature = geometry[row["field"]][row["source_index"]]
    points = np.array([position(geometry["sq"], p) for p in feature["pts"]])
    parts = (
        [points]
        if len(points) == 1
        else [p for p, _, _ in clip_box(points, [-HALF, -HALF], [HALF, HALF])]
    )
    counts = [
        max(1, len(np.arange(0, float(arc(p)[-1]), 512))) if len(p) > 1 else 1
        for p in parts
    ]
    if len(counts) != len(row["clips"]) or sum(counts) != len(contracts):
        raise ValueError("Original sector contracts cannot bind complete clipped parts")
    result, offset = [], 0
    for count in counts:
        result.append([c["id"] for c in contracts[offset : offset + count]])
        offset += count
    return result


def polygon_catalog(geometry, inventory):
    entries = {e["id"]: e for e in inventory["entries"]}
    records, models = [], {}
    for field in ("lakes", "riverAreas", "oceans"):
        if not isinstance(geometry.get(field), list):
            records.append(
                {
                    "id": field,
                    "status": "unresolved",
                    "reason": "missing/invalid captured polygon collection",
                }
            )
            continue
        for index, feature in enumerate(geometry[field]):
            record = {"id": f"{field}:{index}", "field": field, "source_index": index}
            try:
                record["source_sha256"] = digest(feature)
                rings = [
                    micro([position(geometry["sq"], p) for p in ring])
                    for ring in feature["rings"]
                ]
                if not rings or any(len(r) < 3 for r in rings):
                    raise ValueError("Invalid polygon rings")
                mask = raster(geometry["sq"], [feature], polygons=True)
                scope = (
                    "excluded"
                    if source_tag(feature, "intermittent")
                    in (True, 1, "1", "yes", "true")
                    or source_tag(feature, "brunnel") == "tunnel"
                    else "perennial_surface"
                )
                outside = not mask.any() and any(
                    np.all(np.concatenate(rings)[:, a] > HALF * 1_000_000)
                    or np.all(np.concatenate(rings)[:, a] < -HALF * 1_000_000)
                    for a in (0, 1)
                )
                record.update(
                    status="outside_square" if outside else scope,
                    source_scope=scope,
                    inventory_status=entries.get(record["id"], {}).get(
                        "status", "unresolved"
                    ),
                    native_raster_nodes=int(mask.sum()),
                )
                models[record["id"]] = (rings, mask)
            except (
                KeyError,
                ValueError,
                TypeError,
                IndexError,
                AttributeError,
            ) as error:
                record.update(status="unresolved", reason=str(error))
            records.append(record)
    return records, models


def geometry_ledger(geometry, hydro, inventory, pieces, plan, floor, water, controls):
    """Enumerate source geometry before attaching any initial-water diagnostics."""
    rows = all_line_rows(geometry, pieces)
    entries = {e["id"]: e for e in inventory["entries"]}
    clips, raw_vertices = {}, defaultdict(list)
    for row in rows:
        row["inventory_status"] = entries.get(row["id"], {}).get("status", "unresolved")
        contracts = entries.get(row["id"], {}).get("contracts", [])
        row["contract_ids"] = [c["id"] for c in contracts]
        for clip, contract_ids in zip(
            row["clips"], contract_parts(geometry, row, contracts)
        ):
            feature = geometry[row["field"]][row["source_index"]]
            projected = defaultdict(list)
            for index, geographic in enumerate(feature["pts"]):
                projected[
                    tuple(coordinate(position(geometry["sq"], geographic)))
                ].append((index, tuple(geographic)))
            raw = []
            for point_index, p in enumerate(clip["points_xz"]):
                for source_index, geo in projected[tuple(p)]:
                    record = {
                        "clip_id": clip["id"],
                        "clip_vertex": point_index,
                        "source_vertex": source_index,
                        "role": "endpoint"
                        if point_index in (0, len(clip["points_xz"]) - 1)
                        else "interior_vertex",
                    }
                    raw_vertices[geo].append(record)
                    raw.append((geo, record))
            clips[clip["id"]] = {
                "row": row,
                "clip": clip,
                "micro": micro(clip["points_xz"]),
                "raw": raw,
                "contracts": contract_ids,
            }
    eligible = {
        c["id"]
        for r in rows
        if r["field"] == "streams" and r["status"] == "perennial_surface"
        for c in r["clips"]
    }
    if eligible != set(plan["clip_components"]):
        raise ValueError("Interface ledger omits or invents a mandatory stream part")
    polygons, polygon_models = polygon_catalog(geometry, inventory)
    relations = []
    endpoint_links = defaultdict(list)
    names = sorted(clips)
    for ai, a_name in enumerate(names):
        a = clips[a_name]
        for b_name in names[ai:]:
            b = clips[b_name]
            self_pair = a_name == b_name
            if not near_boxes(a["micro"], b["micro"]):
                continue
            hits = intersections(a["micro"], b["micro"], self_pair=self_pair)
            if self_pair and not hits:
                continue
            distance = 0.0 if hits else minimum_distance(a["micro"], b["micro"])
            if distance > 128:
                continue
            shared = (
                sorted({p for p, _ in a["raw"]} & {p for p, _ in b["raw"]})
                if not self_pair
                else []
            )
            native = (
                sorted(
                    {tuple(n) for n in a["clip"]["nodes_rc"]}
                    & {tuple(n) for n in b["clip"]["nodes_rc"]}
                )
                if not self_pair
                else []
            )
            relation = {
                "id": f"line-interface:{len(relations)}",
                "a_clip": a_name,
                "b_clip": b_name,
                "exact_captured_geographic_vertices": [list(p) for p in shared],
                "projected_1um_intersections": hits,
                "shared_native_nodes_rc": [list(n) for n in native],
                "minimum_projected_distance_m": distance,
                "classification": "captured_vertex_incidence"
                if shared
                else "projected_1um_segment_incidence"
                if hits
                else "native_vertex_only_contact"
                if native
                else "proximity_only",
                "hydraulic_connectivity": "unresolved",
            }
            relations.append(relation)
            if not self_pair:
                for own_name, own, other in [(a_name, a, b), (b_name, b, a)]:
                    for side, d in zip(
                        ("start", "end"),
                        point_distances(own["micro"][[0, -1]], other["micro"]),
                    ):
                        if d <= 128:
                            endpoint_links[(own_name, side)].append(
                                {"relation": relation["id"], "distance_m": d}
                            )
    body_relations = []
    for name in names:
        line = clips[name]
        for polygon_id, (rings, mask) in polygon_models.items():
            if not near_boxes(line["micro"], np.concatenate(rings)):
                continue
            hits = [
                {"ring": ri, **h}
                for ri, ring in enumerate(rings)
                for h in intersections(line["micro"], ring, closed_b=True)
            ]
            membership = [in_polygon(point, rings) for point in line["micro"]]
            distance = (
                0.0
                if hits or any(p != "outside" for p in membership)
                else min(
                    minimum_distance(line["micro"], ring, closed_b=True)
                    for ring in rings
                )
            )
            native = [n for n in line["clip"]["nodes_rc"] if mask[tuple(n)]]
            if distance <= 128 or native:
                body_relations.append(
                    {
                        "clip_id": name,
                        "polygon_id": polygon_id,
                        "projected_1um_boundary_incidence": hits,
                        "captured_path_vertex_membership": membership,
                        "native_nodes_in_polygon_raster": native,
                        "minimum_projected_distance_m": distance,
                        "classification": "projected_geometry_contact"
                        if distance == 0
                        else "native_raster_only_contact"
                        if native
                        else "proximity_only",
                        "hydraulic_connectivity": "unresolved",
                    }
                )
    direction = {d["clip"]: d for c in plan["components"] for d in c["directions"]}
    neighbors, owners = defaultdict(set), defaultdict(set)
    output_clips = []
    for name, record in clips.items():
        row, clip = record["row"], record["clip"]
        nodes = [tuple(n) for n in clip["nodes_rc"]]
        if name in eligible:
            for node in nodes:
                owners[node].add(name)
            for a, b in zip(nodes, nodes[1:]):
                neighbors[a].add(b)
                neighbors[b].add(a)
        endpoints = []
        for side, point, node, flag in [
            ("start", clip["points_xz"][0], nodes[0], clip["start_clipped"]),
            ("end", clip["points_xz"][-1], nodes[-1], clip["end_clipped"]),
        ]:
            endpoints.append(
                {
                    "side": side,
                    "xz_m": point,
                    "node_rc": list(node),
                    "source_clipped": flag,
                    "projected_square_boundary": max(abs(p) for p in point) == HALF,
                    "native_vertex_touches_square_boundary": any(
                        v in (0, 1080) for v in node
                    ),
                    "authored_floor_q": int(floor[node]),
                    "authored_depth_q": int(water[node]),
                    "literal_source_vertices": [
                        {"geographic": list(geo), **v}
                        for geo, v in record["raw"]
                        if v["clip_vertex"]
                        == (0 if side == "start" else len(clip["points_xz"]) - 1)
                    ],
                    "line_interfaces_within_128m": endpoint_links[(name, side)],
                    "boundary_stage_and_outlet_support": "unresolved",
                }
            )
        contact_controls = []
        node_positions = np.array([[c * 16 - HALF, HALF - r * 16] for r, c in nodes])
        for control in controls:
            p = np.array(control["encoded"]["position"])[[0, 2]]
            distances = np.linalg.norm(node_positions - p, axis=1)
            if distances.min() <= control["protection_radius_m"]:
                contact_controls.append(
                    {
                        "id": control["id"],
                        "source_radius_node_count": int(
                            np.sum(distances <= control["source_radius_model_m"])
                        ),
                        "protection_radius_node_count": int(
                            np.sum(distances <= control["protection_radius_m"])
                        ),
                        "minimum_node_distance_m": float(distances.min()),
                        "supply_attribution": "unresolved",
                    }
                )
        output_clips.append(
            {
                "id": name,
                "source_id": row["id"],
                "source_sha256": row["source_sha256"],
                "source_scope": row["status"],
                "contract_ids": record["contracts"],
                "endpoints": endpoints,
                "node_count": len(nodes),
                "provisional_direction": direction.get(name),
                "existing_control_proximity": contact_controls,
                "materialized_piece_specific_authored_support": "unresolved; grouped name/class summaries cannot bind source pieces",
                "native_admission": "unresolved",
            }
        )
    return {
        "line_rows": rows,
        "polygons": polygons,
        "clips": output_clips,
        "captured_geographic_vertex_incidence": [
            {
                "geographic": list(geo),
                "incidence": incident,
                "hydraulic_connectivity": "unresolved",
            }
            for geo, incident in sorted(raw_vertices.items())
            if len(incident) > 1
        ],
        "line_interfaces": relations,
        "body_interfaces": body_relations,
        "native_stream_branches": [
            {
                "node_rc": list(n),
                "neighbors_rc": [list(p) for p in sorted(neighbors[n])],
                "source_clips": sorted(owners[n]),
                "scope": "native-grid incidence only, not known hydraulic junction",
            }
            for n in sorted(owners)
            if len(neighbors[n]) > 2 or len(owners[n]) > 1
        ],
    }


def analyze(folder):
    source, physical = folder / "source", folder / "physical"
    stream_preflight(source)
    geometry, hydro, inventory, pieces, plan = [
        json.loads((source / n).read_text())
        for n in (
            "geometry.json",
            "hydrology.json",
            "inventory.json",
            "pieces.json",
            "stream-plan.json",
        )
    ]
    forcing = package_controls(source, physical)
    floor, water = [
        np.flipud(np.fromfile(source / n, "<u2").reshape(1081, 1081)).astype(np.int64)
        for n in ("terrain.u16", "water.u16")
    ]
    ledger = geometry_ledger(
        geometry, hydro, inventory, pieces, plan, floor, water, forcing["controls"]
    )
    initial = initial_natural_checks(inventory, np.flipud(water))
    checks = {c["id"]: c for c in initial["contracts"]}
    for clip in ledger["clips"]:
        clip["authored_initial_contracts"] = [checks[c] for c in clip["contract_ids"]]
    return {
        "schema": "polli.complete-source-stream-support-ledger/1",
        "policy": POLICY,
        **ledger,
        "forcing": forcing,
        "authored_initialization": initial,
        "inventory_sha256": sha(source / "inventory.json"),
        "full_probes_sha256": sha(source / "probes.json"),
        "definition_sha256": inventory["definition_sha256"],
        "geometry_scope": "Every captured source row/clip retained. Exact geographic equality is separate from projected1um rational incidence, nearest16m raster contact and128m proximity; none establishes hydraulics.",
        "initialization_scope": "Unchanged complete authored cohort attached after geometry enumeration, not new native observations or wet-selected probes.",
        "supply_outlet_junction_model": "unresolved; no integrated physical flow budget or piece-specific materialized support established",
        "new_physical_package": None,
        "native_observation": False,
        "stable_water_promise": "unknown",
    }


def stage(source, physical, output):
    if output.exists():
        raise ValueError("Use a fresh interface-ledger protocol directory")
    stream_preflight(source)
    package_controls(source, physical)
    output.mkdir(parents=True)
    shutil.copytree(source, output / "source")
    (output / "physical").mkdir()
    generation = json.loads((physical / "generation.json").read_text())
    for name in ["generation.json", *generation["physical_files_sha256"]]:
        shutil.copyfile(physical / name, output / "physical" / name)
    write(output / "ledger.json", analyze(output))
    old = json.loads((source / "freeze.json").read_text())
    closure = {
        **old["source_files_sha256"],
        **generation.get("source_files_sha256", {}),
        **{n: sha(ROOT / n) for n in NEW_SOURCES + DEFINITIONS},
    }
    freeze = {
        "schema": "polli.source-interface-ledger-protocol/1",
        "source_files_sha256": closure,
        "files_sha256": {
            str(p.relative_to(output)): sha(p)
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
        "definition_sha256": old["definition_sha256"],
        "panel_sha256": old["panel_sha256"],
        "new_physical_package": None,
        "native_observation": False,
        "holdout_inputs_accessed": False,
    }
    write(output / "freeze.json", freeze)
    preflight(output)
    ledger = json.loads((output / "ledger.json").read_text())
    return {
        "freeze_sha256": sha(output / "freeze.json"),
        "line_rows": len(ledger["line_rows"]),
        "clipped_parts": len(ledger["clips"]),
        "line_interfaces": len(ledger["line_interfaces"]),
        "body_interfaces": len(ledger["body_interfaces"]),
        "controls": len(ledger["forcing"]["controls"]),
        "initial_contract_status": dict(
            Counter(c["status"] for c in ledger["authored_initialization"]["contracts"])
        ),
    }


def preflight(folder):
    frozen = json.loads((folder / "freeze.json").read_text())
    if (
        frozen["schema"] != "polli.source-interface-ledger-protocol/1"
        or frozen["new_physical_package"] is not None
        or frozen["native_observation"]
        or frozen["holdout_inputs_accessed"]
    ):
        raise ValueError("Not an unqualified read-only interface protocol")
    old = json.loads((folder / "source/freeze.json").read_text())
    generation = json.loads((folder / "physical/generation.json").read_text())
    expected = {
        **old["source_files_sha256"],
        **generation.get("source_files_sha256", {}),
        **{n: sha(ROOT / n) for n in NEW_SOURCES + DEFINITIONS},
    }
    if frozen["source_files_sha256"] != expected:
        raise ValueError("Interface dependency closure changed")
    for name, expected_hash in frozen["source_files_sha256"].items():
        if sha(ROOT / name) != expected_hash:
            raise ValueError(f"Interface dependency changed: {name}")
    paths = {str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file()}
    if paths != set(frozen["files_sha256"]) | {"freeze.json"}:
        raise ValueError("Interface physical-file inventory changed")
    for name, expected_hash in frozen["files_sha256"].items():
        if sha(folder / name) != expected_hash:
            raise ValueError(f"Interface input/result changed: {name}")
    if any(frozen[k] != old[k] for k in ("definition_sha256", "panel_sha256")):
        raise ValueError("Interface definition/panel changed")
    if json.loads((folder / "ledger.json").read_text()) != analyze(folder):
        raise ValueError("Interface ledger does not replay")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("stage")
    for name in ("source", "physical", "output"):
        create.add_argument(name, type=Path)
    check = commands.add_parser("preflight")
    check.add_argument("folder", type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(
        json.dumps(
            globals()[command](**args) or {"status": "complete_ledger_replayed"},
            indent=2,
        )
    )
