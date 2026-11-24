"""Real roads stage (PL-982): OSM highways, rail, flight and ship paths in a map.

`generate` runs main's own `generate.generate` (preparation, resources and the
native water admission) unchanged, then adds the roads:

1. `prepare_roads` builds the motorway, trunk and rail graph from the square's
   OSM data (`osm_highways`), shapes the final terrain onto it, picks a start
   tile at an open interchange, and adds a flight path on the region's runway
   axis and a ship lane for coastal squares (`transport_paths`). The graph goes
   into `hydrology.json`.
2. `write` replans resources with the roads and rail masked out, for the
   environment the main path chose, and writes the map through `paint`'s plan
   replay. `finish` then swaps the template's corridor network for the graph
   (`network_writer`) and updates the New Game connection counts and previews.

Off by default: the shipping writer, `generate.py` and the fixture contract
are unchanged.

```sh
uv run python real_roads.py PNG GEOMETRY OUTPUT --banks BANKS \
  --landcover landcover.u8.gz --evidence evidence.json
```
"""

import argparse
from collections import deque
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


def _road_access(graph):
    """Directed road reachability, excluding rail/air/ship and isolated markers."""
    nodes, edges = graph["nodes"], graph["edges"]
    forward, reverse = [[] for _ in nodes], [[] for _ in nodes]
    for edge in edges:
        if edge["kind"] in ("highway", "ramp"):
            forward[edge["a"]].append(edge["b"])
            reverse[edge["b"]].append(edge["a"])
    incoming = [i for i, n in enumerate(nodes) if n.get("outside") and forward[i]]
    outgoing = [i for i, n in enumerate(nodes) if n.get("outside") and reverse[i]]

    def reachable(seeds, links):
        seen, queue = set(seeds), deque(seeds)
        while queue:
            for neighbour in links[queue.popleft()]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)
        return seen

    arrive, leave = _stubs(graph)
    from_outside = reachable(incoming, forward)
    to_outside = reachable(outgoing, reverse)
    return {
        "incoming": incoming,
        "outgoing": outgoing,
        "arrive": [i for i in arrive if i in from_outside],
        "leave": [i for i in leave if i in to_outside],
    }


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


def road_eligibility(graph, start_tile):
    """Structural start access, not native pathfinding or a playability promise.

    No synthetic corridor is inferred when access is absent. The explicit
    no_outside_link fallback leaves the geographic counterexample intact.
    """
    access = _road_access(graph)
    nodes = graph["nodes"]
    arrivals = [i for i in access["arrive"] if _tile_of(nodes[i]["xyz"]) == start_tile]
    departures = [i for i in access["leave"] if _tile_of(nodes[i]["xyz"]) == start_tile]
    pairs = []
    for a in arrivals:
        for b in departures:
            pa, pb = np.asarray(nodes[a]["xyz"]), np.asarray(nodes[b]["xyz"])
            gap = float(np.hypot(*(pa - pb)[[0, 2]]))
            if gap <= 400:
                pairs.append((gap, a, b))
    reasons = []
    if not access["incoming"]:
        reasons.append("no_incoming_road_connection")
    if not access["outgoing"]:
        reasons.append("no_outgoing_road_connection")
    if not arrivals:
        reasons.append("no_outside_reachable_start_arrival")
    if not departures:
        reasons.append("no_start_departure_reaches_outside")
    if arrivals and departures and not pairs:
        reasons.append("start_arrival_departure_more_than_400m_apart")
    witness = min(pairs) if pairs else None
    return {
        "schema": 1,
        "status": "eligible" if witness else "no_outside_link",
        "fallback": "none" if witness else "explicit_no_outside_link",
        "reason_codes": reasons,
        "start_tile": start_tile,
        "incoming_road_nodes": len(access["incoming"]),
        "outgoing_road_nodes": len(access["outgoing"]),
        "reachable_start_arrivals": arrivals,
        "outside_reachable_start_departures": departures,
        "interchange": {
            "arrival": witness[1],
            "departure": witness[2],
            "gap_m": witness[0],
        }
        if witness
        else None,
        "scope": "Directed graph access only; native paths, buildability and first-hour play unverified",
    }


def choose_start(graph, ground, depth, current):
    """The start tile where a player can most easily join the highways.

    Candidates hold an exit-ramp stub (traffic in) and an on-ramp stub (traffic
    out) within 400 m of each other: one interchange. They are ranked by how
    open the land is where those stubs end (no bridge or railway within 250 m),
    water in the tile, buildable ground around, then by centrality. A standard tile whose
    interchange is reasonably open stays."""
    access = _road_access(graph)
    arrive, leave = access["arrive"], access["leave"]
    nodes, edges = graph["nodes"], graph["edges"]
    dy, dx = np.gradient(ground, 16)
    buildable = (np.hypot(dx, dy) < 0.15) & (depth < 0.25)
    blockers = np.array(
        [
            (np.asarray(nodes[e["a"]]["xyz"]) + nodes[e["b"]]["xyz"])[[0, 2]] / 2
            for e in edges
            if e["kind"] == "rail" or e["structure"] == "bridge"
        ]
        or [[1e9, 1e9]]
    )
    best = {}
    for a in arrive:
        for b in leave:
            pa, pb = np.asarray(nodes[a]["xyz"]), np.asarray(nodes[b]["xyz"])
            tile = _tile_of(pa)
            if (
                tile is None
                or tile != _tile_of(pb)
                or np.hypot(*(pa - pb)[[0, 2]]) > 400
            ):
                continue
            mid = (pa + pb)[[0, 2]] / 2
            crowd = int((np.hypot(*(blockers - mid).T) < 250).sum())
            col, row = int((mid[0] + 8640) / 16), int((8640 - mid[1]) / 16)
            land = float(
                buildable[
                    max(0, row - 25) : row + 26, max(0, col - 25) : col + 26
                ].mean()
            )
            x, z = tile % 5, tile // 5
            tcol, trow = 540 + (x - 2) * 120, 540 - (z - 2) * 120
            water = depth[trow - 60 : trow + 60, tcol - 60 : tcol + 60] > 0.5
            score = (
                crowd > 1,
                int(water.sum()) < 256,
                land < 0.5,
                tile != current,
                np.hypot(x - 2, z - 2),
                crowd,
            )
            if tile not in best or score < best[tile][0]:
                best[tile] = (score, a, b)
    if not best:
        return (
            current,
            "no start tile holds an outside-reachable exit and on-ramp; standard tile kept",
        )
    # A standard tile whose interchange is reasonably open stays: the player
    # starts where the shipping writer would put them.
    if current in best and best[current][0][5] <= 3:
        tile = current
    else:
        tile = min(best, key=lambda t: best[t][0])
    score = best[tile][0]
    reason = f"interchange with {score[5]} bridge or rail pieces within 250 m"
    return tile, ("standard tile: " if tile == current else "moved: ") + reason


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
    # Ramp ends that wait for local roads open onto level ground at their height.
    arrive, leave = _stubs(graph)
    yy, xx = np.mgrid[-4:5, -4:5]
    disk = np.hypot(yy, xx) * 16 <= 60
    for i in arrive + leave:
        x, y, z = nodes[i]["xyz"]
        col, row = int(round((x + 8640) / 16)), int(round((8640 - z) / 16))
        rows, cols = row + yy[disk], col + xx[disk]
        keep = (rows >= 0) & (rows < GRID) & (cols >= 0) & (cols < GRID)
        rows, cols = rows[keep], cols[keep]
        free = ~centre[rows, cols]
        target[rows[free], cols[free]] = y
        centre[rows[free], cols[free]] = True
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


def grade_directions(graph):
    """Give road and rail end directions their grade (dy per horizontal metre).

    CS1 builds a segment's curve from its end directions; level directions
    flatten every node and steepen the middle of the segment to about 1.5 times
    its average grade. A through node takes the mean of its two segments'
    grades, so the directions on either side stay exactly opposite."""
    nodes, edges = graph["nodes"], graph["edges"]

    def slope(e):
        a, b = np.asarray(nodes[e["a"]]["xyz"]), np.asarray(nodes[e["b"]]["xyz"])
        run = float(np.hypot(*(b - a)[[0, 2]]))
        return (b[1] - a[1]) / run if run > 0 else 0.0

    touching = {}
    for k, e in enumerate(edges):
        if e["kind"] in ("highway", "ramp", "rail"):
            for end in ("a", "b"):
                touching.setdefault(e[end], []).append(k)
    for k, e in enumerate(edges):
        if e["kind"] not in ("highway", "ramp", "rail"):
            continue
        own = slope(e)
        for end, key, sign in (("a", "start_dir", 1), ("b", "end_dir", -1)):
            near = touching[e[end]]
            grade = own
            if len(near) == 2 and edges[near[0]]["kind"] == edges[near[1]]["kind"]:
                other = edges[near[1] if near[0] == k else near[0]]
                # The other segment's grade in this segment's travel direction.
                along = (
                    slope(other)
                    if (other["a"] == e[end]) == (end == "b")
                    else -slope(other)
                )
                grade = (own + along) / 2
            e[key] = [e[key][0], float(sign * grade), e[key][2]]


def prepare_roads(output, geometry, air=True, ship=True):
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
    # Plane entries are unconditional; retain the old argument for CLI compatibility.
    air, air_report = air_path(data, ground)
    ship, ship_report = (
        ship_path(data, ground, depth, start, hydro["sea_level_m"])
        if ship
        else (None, {"ship": "off"})
    )
    merge(graph, air, ship)
    report = {**graph["report"], **air_report, **ship_report}
    report["seat"] = seat(ground, depth, graph)
    grade_directions(graph)
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
            "eligibility": road_eligibility(graph, start),
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
    """The template layout plus the graph's road and rail segments, for resource masks."""
    layout = json.loads(LAYOUT.read_text())
    positions = {f"h{i}": n["xyz"] for i, n in enumerate(hydro["highways"]["nodes"])}
    segments = [
        {"from": f"h{e['a']}", "to": f"h{e['b']}"}
        for e in hydro["highways"]["edges"]
        if e["kind"] in ("highway", "ramp", "rail")
    ]
    layout["segments"] = layout["segments"] + segments
    return layout, {
        **hydro,
        "node_positions": {**hydro.get("node_positions", {}), **positions},
    }


def write(
    output, landcover=None, evidence=None, knobs=None, environment=None, biome=None
):
    """Write the map around the roads, then finish it.

    With land cover, resources are planned with the roads and rail masked out
    (no trees or fields on them), for the environment the main path chose, and
    written by main's own `paint` plan replay. Returns (package, report)."""
    import gzip

    from paint import paint, save_plan

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
        lc = np.frombuffer(gzip.decompress(Path(landcover).read_bytes()), np.uint8)
        side = int(round(np.sqrt(lc.size)))
        lc = np.flipud(lc.reshape(side, side))  # landcover.py is north-first
        layout, masked = road_layout(hydro)
        found = json.loads(Path(evidence).read_text())["evidence"] if evidence else []
        result = R.plan(
            raw.astype(float) / 64, depth, lc, layout, masked, found, knobs, environment
        )
        save_plan(result, output / "plan.npz", environment, biome)
        report = paint(output, None, output, knobs=knobs, plan=output / "plan.npz")
        report.update({"environment": environment, "biome": biome})
        (output / "resources.json").write_text(json.dumps(report, indent=2) + "\n")
    return finish(crp, hydro), report


def generate(
    png,
    geometry,
    output,
    banks=None,
    landcover=None,
    evidence=None,
    knobs=None,
    air=True,
    ship=True,
):
    """Main's generation (preparation, resources, native admission), then roads.

    The road stage works on the final admitted terrain: admission evidence is
    bound to the exact shipping grids, so it is applied first and roads never
    seat into its water or margins. Resources are then replanned around the
    roads and the map rewritten and finished."""
    from generate import generate as generate_shipping

    receipt = generate_shipping(
        png,
        Path(geometry),
        output,
        banks,
        landcover=landcover,
        evidence=evidence,
        knobs=knobs,
    )
    roads = prepare_roads(output, output / "geometry.json", air, ship)
    resources = receipt.get("resources") or {}
    package, report = write(
        output,
        landcover,
        evidence,
        knobs,
        resources.get("environment"),
        resources.get("biome"),
    )
    receipt.update({"real_roads": roads, "package": package})
    if report is not None:
        receipt["resources"].update(
            {k: report[k] for k in ["knobs", "trees", "tree_budget", "unlockable"]}
        )
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
    parser.add_argument(
        "--no-air",
        action="store_false",
        dest="air",
        help="Deprecated: plane entries are always written",
    )
    parser.add_argument("--no-ship", action="store_false", dest="ship")
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
                for k in [
                    "eligibility",
                    "outside",
                    "air",
                    "ship",
                    "start_tile",
                    "start_tile_reason",
                ]
            },
            indent=2,
        )
    )
