"""Replace the template's corridor highway with a real road graph.

`apply_highways` takes a written map's simulation payload and a graph from
`osm_highways.build_highway_graph`, removes the template's road routes (their
nodes, segments, pillars and outside buildings), and adds the graph as native
nodes and segments. Outside connections and bridge pillars are copies of the
template's own native buildings, moved to the new node. Segments carry no lanes:
`NetAI.UpdateLanes` creates them when the map loads (see netcodec).

Prefab names are the vanilla ones a workshop map with pre-built highways uses
(7th Island Enhanced): Highway, HighwayRamp, Highway Bridge, HighwayRampElevated.
Node flags follow `NetNode.CalculateNode`; segment directions are unit tangents.
"""

import math

import numpy as np

import netcodec as nc
from template import manager_tag

CREATED, END, MIDDLE, BEND, JUNCTION = 0x1, 0x10, 0x20, 0x40, 0x80
MOVEABLE, OUTSIDE, ON_GROUND = 0x100, 0x400, 0x4000
ONE_WAY_OUT, ONE_WAY_IN = 0x400000, 0x1000000
SEGMENT_END = 0x40

PREFABS = {
    ("highway", "ground"): "Highway",
    ("highway", "bridge"): "Highway Bridge",
    ("ramp", "ground"): "HighwayRamp",
    ("ramp", "bridge"): "HighwayRampElevated",
    # Tunnels need portal (slope) segments; until then the road crosses the
    # ridge at ground level.
    ("highway", "tunnel"): "Highway",
    ("ramp", "tunnel"): "HighwayRamp",
    ("air", "ground"): "Airplane Path",
    ("ship", "ground"): "Ship Path",
    ("rail", "ground"): "Train Track",
    ("rail", "bridge"): "Train Track Elevated",
    ("rail", "tunnel"): "Train Track",
}
# Two-way transport paths: their outside nodes use a connection prefab and an
# Incoming|Outgoing outside building, as in 7th Island Enhanced.
CONNECTIONS = {
    "air": ("Airplane Connection Path", "Airplane Connection"),
    "ship": ("Ship Connection Path", "Ship Connection"),
    "rail": ("Train Connection Track", "Train Connection"),
}
TWO_WAY = {"air", "ship", "rail"}
GROUND_PREFABS = {"Highway", "HighwayRamp", "Train Track"}
ELEVATED_PREFABS = {
    "Highway Bridge": "HighwayBridgePillar",
    "HighwayRampElevated": "HighwayBridgePillar",
    "Train Track Elevated": "RailwayElevatedPillar",
}
DISABLE_ONLY_MIDDLE = 0x10000000
INCOMING_OUTGOING = 0xC0
# Native tunnels (7th Island Enhanced): a Slope segment joins the ground portal
# node to an Underground tunnel node; both ends are Junctions. Ramp tunnels stay
# ground segments inside the hillside until their prefab names are confirmed.
TUNNELS = {
    "highway": ("Highway Tunnel", "Highway Slope"),
    "rail": ("Train Track Tunnel", "Train Track Slope"),
}
UNDERGROUND = 0x80000
TEMPLATE_ROADS = {"Highway Elevated", "Highway Connection Elevated"}
TEMPLATE_RAIL = {"Train Track Elevated", "Train Connection Track Elevated"}


def section_start(data, name):
    tag = manager_tag(name)
    start = data.find(tag)
    if start < 0 or data.find(tag, start + 1) >= 0:
        raise ValueError(f"{name} tag is not unique")
    return start + len(tag)


def _template_roles(net, buildings):
    """Native prototypes: entry and exit Road Connections, a Train Connection,
    and the elevated highway and railway pillars."""
    names = net.prefabs.names
    roles = {}
    for node_id, record in net.nodes.items():
        building = record["building"]
        if (
            not building
            or names[net.node_prefab[node_id]] not in TEMPLATE_ROADS | TEMPLATE_RAIL
        ):
            continue
        prefab = buildings.prefab(building)
        flags = int(net.node_flags[node_id - 1])
        if prefab == "Road Connection":
            roles["entry" if flags & ONE_WAY_OUT else "exit"] = (node_id, building)
        else:
            roles.setdefault(prefab, (node_id, building))
    wanted = {
        "entry",
        "exit",
        "Train Connection",
        "HighwayBridgePillar",
        "RailwayElevatedPillar",
    }
    if not wanted <= set(roles):
        raise ValueError("Template lacks native connection or pillar prototypes")
    return roles


def _angle(direction):
    return math.atan2(direction[0], direction[2]) % (2 * math.pi)


def apply_highways(data, graph, ground_height):
    """Return (new payload, report). `ground_height(x, z)` gives final terrain metres."""
    net_start = section_start(data, "NetManager")
    building_start = section_start(data, "BuildingManager")
    if not net_start < building_start:
        raise ValueError("Unexpected manager order")
    net = nc.NetSection(data, net_start)
    buildings = nc.BuildingSection(data, building_start)
    roles = _template_roles(net, buildings)
    names = net.prefabs.names

    # Prototype buildings are cloned before the template roads are removed. The
    # template railway goes too when the graph has real rail.
    replaced = TEMPLATE_ROADS | (
        TEMPLATE_RAIL if any(e["kind"] == "rail" for e in graph["edges"]) else set()
    )
    old_roads = [n for n in net.nodes if names[net.node_prefab[n]] in replaced]
    old_buildings = [
        net.nodes[n]["building"] for n in old_roads if net.nodes[n]["building"]
    ]
    nodes, edges = graph["nodes"], graph["edges"]
    touching = [[] for _ in nodes]
    for k, e in enumerate(edges):
        touching[e["a"]].append(k)
        touching[e["b"]].append(k)

    def tunnel_run_end(k, end):
        """Does edge k meet a non-tunnel edge of its kind at node `end`?"""
        node = edges[k][end]
        return any(
            edges[j]["structure"] != "tunnel"
            for j in touching[node]
            if j != k and edges[j]["kind"] == edges[k]["kind"]
        ) or nodes[node].get("outside")

    edge_prefab = []
    for k, e in enumerate(edges):
        if e["structure"] == "tunnel" and e["kind"] in TUNNELS:
            ends = [tunnel_run_end(k, "a"), tunnel_run_end(k, "b")]
            tunnel, slope = TUNNELS[e["kind"]]
            edge_prefab.append(
                PREFABS[(e["kind"], "ground")]
                if all(ends)
                else slope
                if any(ends)
                else tunnel
            )
        else:
            edge_prefab.append(PREFABS[(e["kind"], e["structure"])])
    below = {name for pair in TUNNELS.values() for name in pair}
    slopes = {pair[1] for pair in TUNNELS.values()}

    def node_kind(i):
        kinds = [edges[k]["kind"] for k in touching[i]]
        for kind in ["highway", "ramp", "rail", "air", "ship"]:
            if kind in kinds:
                return kind
        raise ValueError(f"Unknown network kind in {kinds}")

    def node_prefab(i):
        kind = node_kind(i)
        if kind in TWO_WAY and nodes[i].get("outside"):
            return CONNECTIONS[kind][0]
        if kind in ("air", "ship"):
            return PREFABS[(kind, "ground")]
        structures = {
            edges[k]["structure"] for k in touching[i] if edges[k]["kind"] == kind
        }
        if nodes[i].get("outside"):
            return PREFABS[(kind, "ground")]
        same = {edge_prefab[k] for k in touching[i] if edges[k]["kind"] == kind}
        if kind in TUNNELS and same <= below:
            return TUNNELS[kind][0]
        return PREFABS[(kind, "bridge" if structures == {"bridge"} else "ground")]

    # Paths treat a segment whose m_modifiedIndex is at or above their own build
    # index as changed since they were found (PathUnit.GetPosition). The
    # template's own networks already sit below the saved build counter, so
    # new networks reuse its oldest index rather than counting upwards.
    build_index = min(
        [r["build_index"] for r in net.nodes.values()]
        + [r["modified_index"] for r in net.segments.values()]
    )
    ids, clones, pillars = [], {}, 0
    for i, node in enumerate(nodes):
        prefab = node_prefab(i)
        count = len(touching[i])
        if count == 0:
            raise ValueError("Graph node joins no segment")
        if count > 8:
            raise ValueError("A CS1 node joins at most eight segments")
        starts = [k for k in touching[i] if edges[k]["a"] == i]
        ends = [k for k in touching[i] if edges[k]["b"] == i]
        kind = node_kind(i)
        flags = CREATED
        if (
            prefab in GROUND_PREFABS
            or kind in ("air", "ship")
            or (kind == "rail" and node.get("outside"))
        ):
            flags |= ON_GROUND
        if kind == "ship":
            flags |= DISABLE_ONLY_MIDDLE
        if prefab in below:
            flags |= UNDERGROUND
        portal = any(edge_prefab[k] in slopes for k in touching[i])
        if kind not in TWO_WAY:
            if starts:
                flags |= ONE_WAY_OUT
            if ends:
                flags |= ONE_WAY_IN
        if node.get("outside"):
            if count != 1:
                raise ValueError("An outside node must end exactly one segment")
            flags |= OUTSIDE
        elif portal:
            flags |= JUNCTION
        elif count == 1:
            flags |= END | MOVEABLE
        elif count == 2:
            a, b = touching[i]
            da = edges[a]["start_dir"] if edges[a]["a"] == i else edges[a]["end_dir"]
            db = edges[b]["start_dir"] if edges[b]["a"] == i else edges[b]["end_dir"]
            same = edges[a]["kind"] == edges[b]["kind"] and (
                kind in TWO_WAY or len(starts) == 1
            )
            dot = da[0] * db[0] + da[2] * db[2]
            flags |= (MIDDLE | MOVEABLE) if same and dot < -0.999 else BEND
        else:
            flags |= JUNCTION
        node_id = net.add_node(prefab, node["xyz"], flags)
        net.nodes[node_id]["build_index"] = build_index
        ids.append(node_id)
        x, y, z = node["xyz"]
        if node.get("outside"):
            k = touching[i][0]
            other = nodes[edges[k]["b"] if edges[k]["a"] == i else edges[k]["a"]]["xyz"]
            out = np.subtract(node["xyz"], other)
            out /= np.linalg.norm(out[[0, 2]])
            role = (
                "Train Connection"
                if kind == "rail"
                else "entry"
                if starts and kind not in TWO_WAY
                else "exit"
            )
            source = roles[role][1]
            offset = (
                buildings.record(source)["position"][1]
                - net.nodes[roles[role][0]]["position"][1]
            )
            if kind in ("air", "ship"):
                offset = 0.0
            building = buildings.clone(source, [x, y + offset, z], _angle(out), 0)
            if kind in TWO_WAY:
                buildings.set_prefab(building, CONNECTIONS[kind][1])
                buildings.flags[building - 1] |= INCOMING_OUTGOING
            clones[node_id] = building
        elif prefab in ELEVATED_PREFABS:
            k = touching[i][0]
            direction = (
                edges[k]["start_dir"] if edges[k]["a"] == i else edges[k]["end_dir"]
            )
            clones[node_id] = buildings.clone(
                roles[ELEVATED_PREFABS[prefab]][1],
                [x, float(ground_height(x, z)), z],
                _angle(direction),
                0,
            )
            pillars += 1
    for node_id, building in clones.items():
        net.nodes[node_id]["building"] = building

    segment_ids = []
    for e in edges:
        a, b = ids[e["a"]], ids[e["b"]]
        flags = CREATED
        if len(touching[e["a"]]) == 1 and not nodes[e["a"]].get("outside"):
            flags |= SEGMENT_END
        if len(touching[e["b"]]) == 1 and not nodes[e["b"]].get("outside"):
            flags |= SEGMENT_END
        segment_id = net.add_segment(
            edge_prefab[len(segment_ids)],
            a,
            b,
            e["start_dir"],
            e["end_dir"],
            flags,
        )
        segment_ids.append(segment_id)
        record = net.segments[segment_id]
        record["build_index"] = record["modified_index"] = build_index
        record["condition"] = 0
        record["name_seed"] = (segment_id * 2654435761) & 0xFFFF
        net.segment_flags2[segment_id - 1] = 0xC0

    net.remove(old_roads)
    for building in old_buildings:
        buildings.remove(building)

    def outside(kind):
        return [
            i
            for i, n in enumerate(nodes)
            if n.get("outside") and edges[touching[i][0]]["kind"] == kind
        ]

    roads = outside("highway") + outside("ramp")
    entries = sum(1 for i in roads if edges[touching[i][0]]["a"] == i)
    exits = len(roads) - entries
    net_bytes, building_bytes = net.encode(), buildings.encode()
    payload = (
        (
            data[:net_start]
            + net_bytes
            + data[net.end : building_start]
            + building_bytes
            + data[buildings.end :]
        )
        if net_start < building_start
        else None
    )
    report = {
        "nodes": len(nodes),
        "segments": len(edges),
        "bridge_pillars": pillars,
        "incoming_roads": entries,
        "outgoing_roads": exits,
        "plane_paths": len(outside("air")),
        "ship_paths": len(outside("ship")),
        "train_tracks": len(outside("rail")),
        "removed_template_nodes": len(old_roads),
        "removed_template_buildings": len(old_buildings),
        "network_prefabs": sorted(set(edge_prefab)),
        "segment_ids": segment_ids,
    }
    return payload, report


def highway_paths(graph, segment_ids, start_tile, limit=2):
    """Native car-path probes over the real highways, as [segment, lane, offset].

    From each entry at the map edge to the nearest exit-ramp stub in the start
    tile, from start-tile on-ramp stubs out to the edge, and one through route
    between two different edges. Routes are found by hop count on the directed
    graph; the native pathfinder may legitimately choose another, so no
    expected segments are asserted.
    """
    nodes, edges = graph["nodes"], graph["edges"]
    out_edges = [[] for _ in nodes]
    in_degree, out_degree = [0] * len(nodes), [0] * len(nodes)
    for k, e in enumerate(edges):
        if e["kind"] in ("highway", "ramp"):
            out_edges[e["a"]].append(k)
            out_degree[e["a"]] += 1
            in_degree[e["b"]] += 1
    x0, z0 = (start_tile % 5 - 2) * 1920, (start_tile // 5 - 2) * 1920

    def in_start(i):
        x, _, z = nodes[i]["xyz"]
        return abs(x - x0) < 900 and abs(z - z0) < 900

    def reachable(first_edge):
        seen, order, queue = {first_edge}, [first_edge], [first_edge]
        while queue:
            k = queue.pop(0)
            for nxt in out_edges[edges[k]["b"]]:
                if nxt not in seen:
                    seen.add(nxt)
                    order.append(nxt)
                    queue.append(nxt)
        return order

    entries = [
        k
        for k, e in enumerate(edges)
        if nodes[e["a"]].get("outside") and e["kind"] == "highway"
    ]
    exits = {
        k
        for k, e in enumerate(edges)
        if nodes[e["b"]].get("outside") and e["kind"] == "highway"
    }
    arrive = {
        k
        for k, e in enumerate(edges)
        if in_degree[e["b"]] == 1
        and out_degree[e["b"]] == 0
        and not nodes[e["b"]].get("outside")
        and in_start(e["b"])
    }
    leave = [
        k
        for k, e in enumerate(edges)
        if out_degree[e["a"]] == 1
        and in_degree[e["a"]] == 0
        and not nodes[e["a"]].get("outside")
        and in_start(e["a"])
    ]

    def probe(name, a, b):
        return {
            "name": name,
            "from": [segment_ids[a], 0, 128],
            "to": [segment_ids[b], 0, 128],
            "rail": False,
            "expected_segments": [],
        }

    paths, through = [], None
    for entry in entries:
        edge = nodes[edges[entry]["a"]]["outside"]
        order = reachable(entry)
        stub = next((k for k in order if k in arrive), None)
        if (
            stub is not None
            and len([p for p in paths if p["name"].endswith("start")]) < limit
        ):
            paths.append(probe(f"highway:{edge}-in-to-start", entry, stub))
        if through is None:
            far = next(
                (
                    k
                    for k in reversed(order)
                    if k in exits and nodes[edges[k]["b"]]["outside"] != edge
                ),
                None,
            )
            if far is not None:
                through = probe(
                    f"highway:{edge}-in-to-{nodes[edges[far]['b']]['outside']}-out",
                    entry,
                    far,
                )
    for stub in leave:
        order = reachable(stub)
        out = next((k for k in order if k in exits), None)
        if out is not None:
            paths.append(
                probe(
                    f"highway:start-to-{nodes[edges[out]['b']]['outside']}-out",
                    stub,
                    out,
                )
            )
            if (
                len([p for p in paths if p["name"].startswith("highway:start")])
                >= limit
            ):
                break
    if through is not None:
        paths.append(through)
    # Real rail: one train path between the two farthest-apart rail edges.
    rail = [k for k, e in enumerate(edges) if e["kind"] == "rail"]
    ends = [
        k
        for k in rail
        if nodes[edges[k]["a"]].get("outside") or nodes[edges[k]["b"]].get("outside")
    ]
    if len(ends) >= 2:
        neighbours = {}
        for k in rail:
            for end in ("a", "b"):
                neighbours.setdefault(edges[k][end], []).append(k)
        seen, queue = {ends[0]}, [ends[0]]
        while queue:
            k = queue.pop(0)
            for end in ("a", "b"):
                for nxt in neighbours[edges[k][end]]:
                    if nxt not in seen:
                        seen.add(nxt)
                        queue.append(nxt)
        far = [k for k in ends[1:] if k in seen]
        if far:
            paths.append(
                {
                    "name": "rail:real",
                    "from": [segment_ids[ends[0]], 1, 128],
                    "to": [segment_ids[far[-1]], 1, 128],
                    "rail": True,
                    "expected_segments": [],
                }
            )
    return paths
