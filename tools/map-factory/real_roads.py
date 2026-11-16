"""Real roads stage (PL-982): OSM highways, flight and ship paths in a ready map.

Runs between the standard preparation and the map write, without changing
either, so the shipping writer and its fixture contract stay byte-identical:

1. `prepare_roads` builds the motorway/trunk graph from the square's OSM roads
   (`osm_highways`), grades the prepared terrain under it, picks a start tile
   the highways reach, and adds an air path on the region's runway axis and a
   ship lane for coastal squares (`transport_paths`). The graph goes into
   `hydrology.json`.
2. `write` plans resources around the new roads, writes the map with the
   standard writer, then `finish` swaps the template's corridor highway for the
   graph (`network_writer`) and updates the New Game connection counts.

```sh
uv run python real_roads.py PNG GEOMETRY OUTPUT --banks BANKS \
  --landcover landcover.u8.gz --evidence evidence.json
```
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

import resources as R
from crp import patch_metadata, read_package, write_map, write_package
from network_writer import apply_highways
from osm_highways import build_highway_graph
from region import prepare
from surface_water import surface_geometry
from transport_paths import air_path, merge, ship_path

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "templates/native-corridors.crp"
LAYOUT = ROOT / "templates/native-corridors.json"
GRID = 1081


def _grid(path):
    """A prepared u16 grid (south-first on disk) as north-first metres."""
    return (
        np.flipud(np.fromfile(path, dtype="<u2").reshape(GRID, GRID)).astype(float) / 64
    )


def _stubs(graph):
    """Dangling one-way ends: where traffic arrives (exit ramps) and leaves."""
    nodes, edges = graph["nodes"], graph["edges"]
    starts, ends = [0] * len(nodes), [0] * len(nodes)
    for e in edges:
        if e["kind"] in ("highway", "ramp"):
            starts[e["a"]] += 1
            ends[e["b"]] += 1
    arrive = [
        i
        for i, n in enumerate(nodes)
        if ends[i] == 1 and not starts[i] and not n.get("outside")
    ]
    leave = [
        i
        for i, n in enumerate(nodes)
        if starts[i] == 1 and not ends[i] and not n.get("outside")
    ]
    return arrive, leave


def _tile_of(xyz):
    x, z = xyz[0], xyz[2]
    tx, tz = int(np.floor(x / 1920 + 2.5)), int(np.floor(z / 1920 + 2.5))
    if (
        0 <= tx < 5
        and 0 <= tz < 5
        and abs(x - (tx - 2) * 1920) < 900
        and abs(z - (tz - 2) * 1920) < 900
    ):
        return tz * 5 + tx
    return None


def choose_start(graph, ground, depth, current):
    """Keep the standard start tile if a player can join the highways there.

    Otherwise take the most central buildable tile holding both an exit-ramp
    stub (traffic in) and an on-ramp stub (traffic out)."""
    arrive, leave = _stubs(graph)
    nodes = graph["nodes"]
    has = {}
    for kind, ids in [("arrive", arrive), ("leave", leave)]:
        for i in ids:
            tile = _tile_of(nodes[i]["xyz"])
            if tile is not None:
                has.setdefault(tile, set()).add(kind)
    usable = {t for t, kinds in has.items() if kinds == {"arrive", "leave"}}
    if current in usable:
        return current, "standard start tile reaches the highways"
    dy, dx = np.gradient(ground, 16)
    buildable = (np.hypot(dx, dy) < 0.15) & (depth < 0.25)
    options = []
    for tile in usable:
        x, z = tile % 5, tile // 5
        col, row = 540 + (x - 2) * 120, 540 - (z - 2) * 120
        land = float(buildable[row - 60 : row + 60, col - 60 : col + 60].mean())
        if land > 0.15:
            options.append((np.hypot(x - 2, z - 2) - land, tile))
    if not options:
        return (
            current,
            "no buildable start tile holds both ramp directions; standard tile kept",
        )
    return min(options)[1], "moved to the most central tile with exit and on-ramp stubs"


def seat(ground, depth, graph, bed=14.0, reach=40.0):
    """Shape the terrain onto the graded road profiles, in place.

    Within `bed` metres of a ground road or rail the terrain equals the road's
    height; it blends back to the land by `reach`. The nearest road wins where
    corridors overlap. Mapped water and a two-cell margin stay untouched, which
    is where the graph already uses bridges."""
    nodes, edges = graph["nodes"], graph["edges"]
    open_ends = {}
    for e in edges:
        if e["structure"] != "tunnel":
            for end in ("a", "b"):
                open_ends.setdefault(e[end], set()).add(e["kind"])
    target = np.zeros_like(ground)
    centre = np.zeros(ground.shape, bool)
    for e in edges:
        if e["kind"] not in ("highway", "ramp", "rail") or e["structure"] == "bridge":
            continue
        # A tunnel's portal (slope) segment cuts its approach; its interior doesn't.
        if e["structure"] == "tunnel" and not any(
            e["kind"] in open_ends.get(e[end], ()) for end in ("a", "b")
        ):
            continue
        a, b = np.asarray(nodes[e["a"]]["xyz"]), np.asarray(nodes[e["b"]]["xyz"])
        steps = int(np.ceil(np.hypot(*(b - a)[[0, 2]]) / 4)) + 1
        for t in np.linspace(0, 1, steps):
            x, y, z = a + (b - a) * t
            col, row = int(round((x + 8640) / 16)), int(round((8640 - z) / 16))
            if 0 <= row < GRID and 0 <= col < GRID:
                target[row, col] = y
                centre[row, col] = True
    if not centre.any():
        return {"cells": 0}
    distance, (rows, cols) = ndimage.distance_transform_edt(
        ~centre, return_indices=True
    )
    distance *= 16
    weight = np.clip((reach - distance) / (reach - bed), 0, 1)
    weight = weight * weight * (3 - 2 * weight)
    weight[ndimage.binary_dilation(depth > 0.1, iterations=2)] = 0
    change = (target[rows, cols] - ground) * weight
    ground += change
    return {
        "cells": int((weight > 0).sum()),
        "max_cut_m": float(max(0.0, -change.min())),
        "max_fill_m": float(max(0.0, change.max())),
        "bed_m": bed,
        "reach_m": reach,
    }


def prepare_roads(output, geometry):
    """Add the road graph to an already prepared region directory."""
    data, _ = surface_geometry(json.loads(Path(geometry).read_text()))
    hydro = json.loads((output / "hydrology.json").read_text())
    ground, depth = _grid(output / "terrain.u16"), _grid(output / "water.u16")
    graph = build_highway_graph(data, ground, depth, rail=True)
    # Overlapping OSM pieces can leave two segments between the same nodes,
    # which the game's tools never build; keep the first.
    seen, edges = set(), []
    for e in graph["edges"]:
        key = frozenset((e["a"], e["b"]))
        if key not in seen:
            seen.add(key)
            edges.append(e)
    graph["report"]["duplicate_segments_dropped"] = len(graph["edges"]) - len(edges)
    graph["edges"] = edges
    start, why = choose_start(graph, ground, depth, hydro["start_tile"])
    air, air_report = air_path(data, ground)
    ship, ship_report = ship_path(data, ground, depth, start, hydro["sea_level_m"])
    merge(graph, air, ship)
    report = {**graph["report"], **air_report, **ship_report}
    report["seat"] = seat(ground, depth, graph)
    if start != hydro["start_tile"]:
        hydro["start_tile"] = start
        hydro["start_area"] = {
            **hydro.get("start_area", {}),
            "index": start,
            "x": start % 5,
            "z": start // 5,
        }
    report.update(
        {
            "start_tile": start,
            "start_tile_reason": why,
            "start_tile_nodes": sum(
                1 for n in graph["nodes"] if _tile_of(n["xyz"]) == start
            ),
        }
    )
    hydro.update(
        {
            "highways": {"nodes": graph["nodes"], "edges": graph["edges"]},
            "highway_report": report,
        }
    )
    (output / "hydrology.json").write_text(json.dumps(hydro, indent=2) + "\n")
    np.floor(np.flipud(ground) * 64 + 0.5).clip(0, 65535).astype("<u2").tofile(
        output / "terrain.u16"
    )
    return report


def preview_assets(assets, crp, hydro):
    """Redraw the New Game preview images with the real roads and rail."""
    from map_metadata import preview_image, texture_payload

    nodes = hydro["highways"]["nodes"]
    positions = {f"h{i}": n["xyz"] for i, n in enumerate(nodes)}
    routes = [
        {
            "kind": "rail" if e["kind"] == "rail" else "road",
            "nodes": [f"h{e['a']}", f"h{e['b']}"],
        }
        for e in hydro["highways"]["edges"]
        if e["kind"] in ("highway", "ramp", "rail")
    ]
    terrain = np.fromfile(crp.parent / "terrain.u16", dtype="<u2")
    depth = np.fromfile(crp.parent / "water.u16", dtype="<u2")
    image = preview_image(
        terrain, depth, {"node_positions": positions}, {"routes": routes}
    )
    fields = {}
    for field, suffix, size in [
        ("imageRef", "Snapshot", (400, 224)),
        ("steamPreviewRef", "SteamPreview", (1800, 1008)),
    ]:
        asset = next(
            a for a in assets if a["kind"] == 3 and a["name"].endswith("_" + suffix)
        )
        asset["payload"] = texture_payload(
            asset["name"], image.resize(size, Image.Resampling.LANCZOS)
        )
        fields[field] = (
            "ColossalFramework.Packaging.Package+Asset, ColossalManaged, "
            "Version=0.3.0.0, Culture=neutral, PublicKeyToken=null",
            hashlib.md5(asset["payload"]).hexdigest(),
        )
    return fields


def finish(crp, hydro):
    """Swap the written map's corridor highway for the graph, in place."""
    package, assets = read_package(crp.read_bytes())
    simulation = next(a for a in assets if a["kind"] == 52)
    raw = (
        np.fromfile(crp.parent / "terrain.u16", dtype="<u2")
        .reshape(GRID, GRID)
        .astype(float)
        / 64
    )

    def ground_height(x, z):
        col = min(GRID - 1.001, max(0.0, (x + 8640) / 16))
        row = min(GRID - 1.001, max(0.0, (z + 8640) / 16))
        c, r = int(col), int(row)
        fc, fr = col - c, row - r
        top = raw[r, c] * (1 - fc) + raw[r, c + 1] * fc
        bottom = raw[r + 1, c] * (1 - fc) + raw[r + 1, c + 1] * fc
        return top * (1 - fr) + bottom * fr

    data, report = apply_highways(
        simulation["payload"], hydro["highways"], ground_height
    )
    simulation["payload"] = data
    fields = {
        "incomingRoads": ("System.Int32", report["incoming_roads"]),
        "outgoingRoads": ("System.Int32", report["outgoing_roads"]),
    }
    for kind, count in [
        ("PlanePath", report["plane_paths"]),
        ("ShipPath", report["ship_paths"]),
        ("TrainTracks", report["train_tracks"]),
    ]:
        if count:
            fields["incoming" + kind] = ("System.Int32", count)
            fields["outgoing" + kind] = ("System.Int32", count)
    fields.update(preview_assets(assets, crp, hydro))
    checksum = hashlib.md5(data).hexdigest()
    for a in assets:
        if a["kind"] == 100:
            a["payload"] = patch_metadata(a["payload"], checksum, fields=fields)
    result = write_package(package, assets)
    read_package(result)
    crp.write_bytes(result)
    return {
        "sha256": hashlib.sha256(result).hexdigest(),
        "bytes": len(result),
        "simulation_sha256": hashlib.sha256(data).hexdigest(),
        "highways": report,
    }


def road_layout(hydro):
    """The template layout plus the graph's road segments, for resource masks."""
    layout = json.loads(LAYOUT.read_text())
    positions = {f"h{i}": n["xyz"] for i, n in enumerate(hydro["highways"]["nodes"])}
    segments = [
        {"from": f"h{e['a']}", "to": f"h{e['b']}"}
        for e in hydro["highways"]["edges"]
        if e["kind"] in ("highway", "ramp")
    ]
    layout["segments"] = layout["segments"] + segments
    return layout, {
        **hydro,
        "node_positions": {**hydro.get("node_positions", {}), **positions},
    }


def write(output, landcover=None, evidence=None, knobs=None, geometry=None):
    """Write the map (with resources when land cover is given), then finish it."""
    import gzip

    from paint import preview, save_plan

    hydro = json.loads((output / "hydrology.json").read_text())
    crp = output / (hydro["map_id"] + ".crp")
    report = None
    if landcover is None:
        write_map(
            TEMPLATE,
            LAYOUT,
            output / "terrain.u16",
            output / "water.u16",
            output / "hydrology.json",
            crp,
        )
    else:
        knobs = knobs or R.Knobs()
        raw = np.fromfile(output / "terrain.u16", dtype="<u2").reshape(GRID, GRID)
        depth = np.fromfile(output / "water.u16", dtype="<u2").reshape(GRID, GRID)
        terrain = raw.astype(float) / 64
        lc = np.frombuffer(gzip.decompress(Path(landcover).read_bytes()), np.uint8)
        side = int(round(np.sqrt(lc.size)))
        lc = np.flipud(lc.reshape(side, side))
        layout, masked = road_layout(hydro)
        found = json.loads(Path(evidence).read_text())["evidence"] if evidence else []
        theme = R.theme_of(TEMPLATE.read_bytes())
        result = R.plan(terrain, depth, lc, layout, masked, found, knobs, theme)
        package = write_map(
            TEMPLATE,
            LAYOUT,
            output / "terrain.u16",
            output / "water.u16",
            output / "hydrology.json",
            crp,
            resources=(result, R.TREE_NAMES),
        )
        water, _ = R.water_cells(depth, raw)
        _, per_tile = R.area_totals(result, water)
        report = R.summary(result, per_tile, knobs)
        report.update({"theme": theme, "package": package})
        preview(result, terrain, depth, output / "resources.png")
        save_plan(result, output / "plan.npz")
        (output / "resources.json").write_text(json.dumps(report, indent=2) + "\n")
    return finish(crp, hydro), report


def generate(
    png, geometry, output, banks=None, landcover=None, evidence=None, knobs=None
):
    output.mkdir(parents=True, exist_ok=True)
    geometry_bytes = Path(geometry).read_bytes()
    snapshot = output / "geometry.json"
    snapshot.write_bytes(geometry_bytes)
    summary = prepare(png, snapshot, LAYOUT, output, banks)
    roads = prepare_roads(output, snapshot)
    package, report = write(output, landcover, evidence, knobs)
    receipt = {
        "preparation": summary,
        "real_roads": roads,
        "package": package,
        "resources": None
        if report is None
        else {
            **{k: report[k] for k in ["knobs", "trees", "unlockable", "placed"]},
            "prepared_geometry_sha256": hashlib.sha256(geometry_bytes).hexdigest(),
        },
        "source": {
            "inputs_sha256": {
                "geometry.json": hashlib.sha256(geometry_bytes).hexdigest()
            }
        },
        "in_game_verified": False,
    }
    if report is not None:
        receipt["resource_plan"] = {
            "file": "plan.npz",
            "sha256": hashlib.sha256((output / "plan.npz").read_bytes()).hexdigest(),
        }
    (output / "generation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    for name in ["png", "geometry", "output"]:
        parser.add_argument(name, type=Path)
    parser.add_argument("--banks", type=Path)
    parser.add_argument("--landcover", type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    receipt = generate(**vars(args))
    roads = receipt["real_roads"]
    print(
        json.dumps(
            {
                k: v
                for k, v in receipt["package"]["highways"].items()
                if k != "segment_ids"
            },
            indent=2,
        )
    )
    print(
        json.dumps(
            {
                k: roads.get(k)
                for k in ["outside", "air", "ship", "start_tile", "start_tile_reason"]
            },
            indent=2,
        )
    )
