"""Compile an OSM node/way extract without inferring junctions from proximity.

This experimental starting-city input is separate from the shipping vector-tile
capture. Shared OSM node ids join roads. Crossings with different ids do not.
"""

import argparse
import hashlib
import itertools
import json
import math
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np

from osm_highways import HALF, Union, arc, clip_box, edge_name, sample
from prepare import pixel

ROAD_CLASSES = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
    "service",
    "road",
    "track",
}
ENDPOINT = "https://overpass-api.de/api/interpreter"


def bounds(sq):
    """WGS84 envelope of the rotated game square."""
    # The inverse of prepare.pixel, including the export's horizontal scale.
    a, e2 = 6378137, 0.00669437999014
    w = 1 - e2 * math.sin(math.radians(sq["lat"])) ** 2
    m = a * (1 - e2) / w**1.5
    n = a / math.sqrt(w) * math.cos(math.radians(sq["lat"]))
    angle = math.radians(sq["rotation"])
    corners = []
    for u in (-HALF, HALF):
        for v in (-HALF, HALF):
            x = (u * math.cos(angle) + v * math.sin(angle)) * sq["scale"]
            z = (-u * math.sin(angle) + v * math.cos(angle)) * sq["scale"]
            corners.append(
                (sq["lat"] + math.degrees(z / m), sq["lon"] + math.degrees(x / n))
            )
    lat, lon = zip(*corners)
    return min(lat), min(lon), max(lat), max(lon)


def query(sq):
    """Query the WGS84 envelope, including whole ways and their node ids."""
    bbox = ",".join(f"{v:.8f}" for v in bounds(sq))
    return f'[out:json][timeout:120];way["highway"]({bbox});out body;>;out skel qt;'


def capture(sq, output, endpoint=ENDPOINT):
    """Fetch once and retain the complete response for reproducible builds."""
    if Path(output).exists():
        raise FileExistsError(
            f"Extract already exists: {output}. Use a new output path."
        )
    request = urllib.request.Request(
        endpoint,
        data=urllib.parse.urlencode({"data": query(sq)}).encode(),
        headers={"User-Agent": "region-to-skylines/PL-1031 (OSM street import)"},
    )
    with urllib.request.urlopen(request, timeout=150) as response:
        osm = json.load(response)
    if osm.get("remark") or not osm.get("elements"):
        raise ValueError(f"Incomplete OSM response: {osm.get('remark', 'no elements')}")
    source = {"sq": sq, "endpoint": endpoint, "query": query(sq), "osm": osm}
    with Path(output).open("x") as stream:
        stream.write(json.dumps(source) + "\n")
    return source


def extract_pbf(sq, path, output):
    """Read a regional PBF when Overpass is unavailable. Requires pyosmium."""
    import osmium

    if Path(output).exists():
        raise FileExistsError(
            f"Extract already exists: {output}. Use a new output path."
        )
    points, ways = {}, []
    south, west, north, east = bounds(sq)
    processor = (
        osmium.FileProcessor(path)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter("highway"))
    )
    for obj in processor:
        if not obj.is_way() or "highway" not in obj.tags:
            continue
        if any(not n.location.valid() for n in obj.nodes):
            raise ValueError(f"PBF is not reference-complete at OSM way {obj.id}")
        if len(obj.nodes) < 2:
            continue
        lon, lat = zip(*((n.lon, n.lat) for n in obj.nodes))
        if max(lon) < west or min(lon) > east or max(lat) < south or min(lat) > north:
            continue
        xz = np.array([pixel(sq, (n.lon, n.lat)) for n in obj.nodes])
        xz = (xz - 540) * [16, -16]
        if not clip_box(xz, [-HALF] * 2, [HALF] * 2):
            continue
        ways.append(
            {
                "type": "way",
                "id": obj.id,
                "nodes": [n.ref for n in obj.nodes],
                "tags": dict(obj.tags),
            }
        )
        for n in obj.nodes:
            points[n.ref] = {"type": "node", "id": n.ref, "lon": n.lon, "lat": n.lat}
    with Path(path).open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    reader = osmium.io.Reader(str(path))
    try:
        timestamp = reader.header().get("osmosis_replication_timestamp")
    finally:
        reader.close()
    source = {
        "sq": sq,
        "pbf_sha256": digest,
        "osm": {
            "osm3s": {"timestamp_osm_base": timestamp},
            "elements": list(points.values()) + ways,
        },
    }
    with Path(output).open("x") as stream:
        stream.write(json.dumps(source) + "\n")
    return source


def _oneway(tags):
    value = tags.get("oneway")
    if value is None:
        return int(
            tags.get("junction") == "roundabout" or tags["highway"] == "motorway"
        )
    if value in ("yes", "1", "true"):
        return 1
    if value in ("no", "0", "false"):
        return 0
    if value in ("-1", "reverse"):
        return -1
    raise ValueError(f"Unsupported time-dependent/unknown oneway={value}")


def _simplify(points, tolerance=1.0):
    """Keep bends to one metre while discarding redundant shape nodes."""
    keep, pending = {0, len(points) - 1}, [(0, len(points) - 1)]
    while pending:
        a, b = pending.pop()
        if b <= a + 1:
            continue
        d = points[b] - points[a]
        t = np.clip((points[a + 1 : b] - points[a]) @ d / max(d @ d, 1e-12), 0, 1)
        gap = np.linalg.norm(points[a + 1 : b] - points[a] - t[:, None] * d, axis=1)
        k = int(gap.argmax()) + a + 1
        if gap.max() > tolerance:
            keep.add(k)
            pending.extend(((a, k), (k, b)))
    return points[sorted(keep)]


def _points(points, minimum):
    points = _simplify(points)
    lengths = arc(points)
    wanted = set(lengths)
    for a, b in itertools.pairwise(lengths):
        wanted.update(np.linspace(a, b, max(2, math.ceil((b - a) / 80) + 1)))
    wanted.update(np.linspace(0, lengths[-1], minimum + 1))
    ordered = sorted(wanted)
    wanted = [ordered[0]]
    for distance in ordered[1:]:
        if distance - wanted[-1] > 1e-6:
            wanted.append(distance)
    wanted[-1] = lengths[-1]
    return np.column_stack([np.interp(wanted, lengths, points[:, k]) for k in (0, 1)])


def _curve_gap(points, line):
    delta = np.diff(line, axis=0)
    relative = points[:, None, :] - line[None, :-1, :]
    t = np.clip(
        np.sum(relative * delta, axis=2) / np.maximum(np.sum(delta**2, axis=1), 1e-12),
        0,
        1,
    )
    return np.linalg.norm(relative - t[:, :, None] * delta, axis=2).min(axis=1)


def compact(graph, tolerance=4.0):
    """Fit provisional native-style cubic curves through degree-two chains.

    Junctions, dead ends, direction changes and structure transitions stay.
    Every original edge belongs to exactly one output edge. The error bound is
    against a chord/3 control-point model, not a native curve qualification.
    """
    nodes, edges = graph["nodes"], graph["edges"]
    at = [[] for _ in nodes]
    for i, e in enumerate(edges):
        at[e["a"]].append(i)
        at[e["b"]].append(i)

    def through(i):
        if len(at[i]) != 2:
            return False
        a, b = (edges[k] for k in at[i])
        if any(a[k] != b[k] for k in ("kind", "structure", "layer")):
            return False
        return a["kind"] == "street" or (a["a"] == i) != (b["a"] == i)

    seen, chains = set(), []
    for seed, edge in enumerate(edges):
        if seed in seen:
            continue
        seen.add(seed)
        path, members = [edge["a"], edge["b"]], [seed]
        for forward in (True, False):
            while through(path[-1] if forward else path[0]):
                end = path[-1] if forward else path[0]
                candidates = [k for k in at[end] if k not in seen]
                if not candidates:
                    break
                k = candidates[0]
                seen.add(k)
                other = edges[k]["b"] if edges[k]["a"] == end else edges[k]["a"]
                if forward:
                    path.append(other)
                    members.append(k)
                else:
                    path.insert(0, other)
                    members.insert(0, k)
        chains.append((path, members))
    out_nodes, out_edges, retained = [], [], {}

    def node(i):
        if i not in retained:
            retained[i] = len(out_nodes)
            out_nodes.append(nodes[i])
        return retained[i]

    for path, members in chains:
        points = np.array([nodes[i]["xyz"] for i in path])[:, [0, 2]]
        length = arc(points)
        tangents = np.diff(points, axis=0)
        tangents /= np.maximum(np.linalg.norm(tangents, axis=1), 1e-12)[:, None]
        cuts = {0, len(path) - 1}
        if path[0] == path[-1]:
            cuts.update((len(path) // 3, 2 * len(path) // 3))
        if edges[members[0]]["structure"] == "tunnel":
            cuts.update((min(1, len(path) - 1), max(0, len(path) - 2)))
        pending = list(itertools.pairwise(sorted(cuts)))
        while pending:
            a, b = pending.pop()
            if b == a + 1:
                continue
            span = length[b] - length[a]
            chord = np.linalg.norm(points[b] - points[a])
            t = np.linspace(0, 1, max(33, math.ceil(span / 2) + 1))[:, None]
            p, q = (
                points[a] + tangents[a] * chord / 3,
                points[b] - tangents[b - 1] * chord / 3,
            )
            curve = (
                (1 - t) ** 3 * points[a]
                + 3 * (1 - t) ** 2 * t * p
                + 3 * (1 - t) * t**2 * q
                + t**3 * points[b]
            )
            shape = points[a : b + 1]
            errors = _curve_gap(shape, curve)
            reverse_errors = _curve_gap(curve, shape)
            worst = max(errors.max(), reverse_errors.max())
            if worst <= tolerance and span <= 256 and chord > 0.1:
                continue
            split = (
                (a + b) // 2
                if span > 256 or worst <= tolerance
                else a + int(errors.argmax())
                if errors.max() >= reverse_errors.max()
                else a
                + int(
                    np.linalg.norm(
                        shape - curve[reverse_errors.argmax()], axis=1
                    ).argmin()
                )
            )
            split = min(b - 1, max(a + 1, split))
            cuts.add(split)
            pending.extend(((a, split), (split, b)))
        for a, b in itertools.pairwise(sorted(cuts)):
            edge = dict(edges[members[a]])
            edge.update(
                a=node(path[a]),
                b=node(path[b]),
                length=float(length[b] - length[a]),
                start_dir=[float(tangents[a][0]), 0, float(tangents[a][1])],
                end_dir=[float(-tangents[b - 1][0]), 0, float(-tangents[b - 1][1])],
                osm_ways=sorted({edges[k]["osm_way"] for k in members[a:b]}),
            )
            out_edges.append(edge)
    unique, pairs = [], set()
    for e in out_edges:
        pair = frozenset((e["a"], e["b"]))
        if pair not in pairs:
            pairs.add(pair)
            unique.append(e)
            continue
        # The native tools do not create parallel segments with the same two
        # node ids. Keep both real routes by giving this curve its own middle.
        pa, pb = (np.array(out_nodes[e[k]]["xyz"])[[0, 2]] for k in ("a", "b"))
        chord = np.linalg.norm(pb - pa)
        p, q = (
            pa + np.array(e["start_dir"])[[0, 2]] * chord / 3,
            pb + np.array(e["end_dir"])[[0, 2]] * chord / 3,
        )
        mid = (pa + 3 * p + 3 * q + pb) / 8
        tangent = (p - pa) / 4 + (q - p) / 2 + (pb - q) / 4
        tangent /= max(np.linalg.norm(tangent), 1e-12)
        direction = [float(tangent[0]), 0.0, float(tangent[1])]
        ident = len(out_nodes)
        out_nodes.append(
            {
                "xyz": [float(mid[0]), 0.0, float(mid[1])],
                "outside": None,
                "osm_node": None,
            }
        )
        unique.extend(
            (
                dict(
                    e, b=ident, length=e["length"] / 2, end_dir=[-v for v in direction]
                ),
                dict(e, a=ident, length=e["length"] / 2, start_dir=direction),
            )
        )
    return {"nodes": out_nodes, "edges": unique}


def build_street_graph(source, sq, ground, depth, scope="all-motor"):
    """Return a road graph in the shared writer's format. Do not change grids.

    Connected and disconnected motor-road ways within the scope are retained. A
    coverage report accounts for other highway classes. Lane counts, road
    widths, private-access restrictions and turn restrictions are not simulated.
    """
    if source["sq"] != sq:
        raise ValueError(
            "OSM extract and prepared terrain must use the identical square"
        )
    osm = source["osm"]
    if osm.get("remark"):
        raise ValueError(f"Incomplete OSM response: {osm['remark']}")
    elements = {}
    for element in osm["elements"]:
        key = element["type"], element["id"]
        if key in elements and elements[key] != element:
            raise ValueError(f"Conflicting OSM element {key}")
        elements[key] = element
    coords = {}
    for (kind, ident), element in elements.items():
        if kind == "node":
            p = np.array(pixel(sq, (element["lon"], element["lat"])))
            coords[ident] = (p - 540) * [16, -16]
            if not np.isfinite(coords[ident]).all():
                raise ValueError(f"Invalid OSM node {ident}")
    if scope not in ("all-motor", "playable"):
        raise ValueError(f"Unknown street scope: {scope}")
    ways, excluded = [], Counter()
    for (kind, ident), element in sorted(elements.items()):
        if kind != "way":
            continue
        tags = element.get("tags", {})
        cls = tags.get("highway", "<missing>")
        if cls not in ROAD_CLASSES or tags.get("area") == "yes":
            excluded[cls if tags.get("area") != "yes" else "area=yes"] += 1
            continue
        if len(element["nodes"]) < 2 or any(n not in coords for n in element["nodes"]):
            raise ValueError(f"Missing nodes in OSM way {ident}")
        direction = _oneway(tags)
        ids = element["nodes"][:: -1 if direction == -1 else 1]
        ways.append((ident, ids, tags, bool(direction)))
    if not ways:
        raise ValueError("OSM extract contains no current motor roads")
    uses = Counter(n for _, ids, _, _ in ways for n in set(ids))
    nodes, edges, junctions = [], [], {}
    clipped, outside_only, zero_length = set(), set(), 0
    by_class = Counter()

    def add_node(point, key, outside=None):
        if key is not None and key in junctions:
            return junctions[key]
        index = len(nodes)
        nodes.append(
            {
                "xyz": [
                    float(point[0]),
                    float(sample(ground, point)[0]),
                    float(point[1]),
                ],
                "outside": outside,
                "osm_node": key,
            }
        )
        if key is not None:
            junctions[key] = index
        return index

    for ident, ids, tags, oneway in ways:
        half = (
            4800.0
            if scope == "playable"
            and not tags["highway"].startswith(("motorway", "trunk"))
            else HALF
        )
        cuts = {0, len(ids) - 1}
        cuts.update(i for i, n in enumerate(ids) if uses[n] > 1)
        # Closed ways need distinct intermediate nodes even without junctions.
        counts = Counter(ids)
        cuts.update(i for i, n in enumerate(ids) if counts[n] > 1)
        cuts = sorted(cuts)
        before = len(edges)
        for first, last in itertools.pairwise(cuts):
            original = np.array([coords[n] for n in ids[first : last + 1]])
            keep = np.r_[True, np.linalg.norm(np.diff(original, axis=0), axis=1) > 1e-6]
            original = original[keep]
            if len(original) < 2:
                zero_length += 1
                continue
            for piece, cut_a, cut_b in clip_box(original, [-half] * 2, [half] * 2):
                if arc(piece)[-1] < 1e-6:
                    zero_length += 1
                    continue
                tunnel = tags.get("tunnel", "no") not in ("no", "false", "0")
                bridge = tags.get("bridge", "no") not in ("no", "false", "0")
                points = _points(piece, 3 if tunnel else 2)
                refs = []
                for i, point in enumerate(points):
                    key, outside = None, None
                    if i in (0, len(points) - 1):
                        cut = cut_a if i == 0 else cut_b
                        if cut:
                            outside = edge_name(point) if half == HALF else None
                            clipped.add(ident)
                        else:
                            key = ids[first if i == 0 else last]
                    refs.append(add_node(point, key, outside))
                kind = (
                    ("ramp" if tags["highway"].endswith("_link") else "highway")
                    if oneway and tags["highway"].startswith(("motorway", "trunk"))
                    else "street_oneway"
                    if oneway
                    else "street"
                )
                for i, (a, b) in enumerate(itertools.pairwise(refs)):
                    d = points[i + 1] - points[i]
                    length = float(np.linalg.norm(d))
                    if a == b or length < 1e-6:
                        raise ValueError(f"Collapsed segment in OSM way {ident}")
                    d /= length
                    edges.append(
                        {
                            "a": a,
                            "b": b,
                            "kind": kind,
                            "structure": "tunnel"
                            if tunnel
                            else "bridge"
                            if bridge
                            else "ground",
                            "start_dir": [float(d[0]), 0.0, float(d[1])],
                            "end_dir": [float(-d[0]), 0.0, float(-d[1])],
                            "length": length,
                            "osm_way": ident,
                            "osm_class": tags["highway"],
                            "name": tags.get("name"),
                            "layer": int(tags.get("layer", "0")),
                        }
                    )
        if len(edges) == before:
            outside_only.add(ident)
        else:
            by_class[tags["highway"]] += 1
    if not edges:
        raise ValueError("No motor roads intersect the export square")
    before_nodes, before_edges = len(nodes), len(edges)
    expected_ways = {e["osm_way"] for e in edges}
    compressed = compact({"nodes": nodes, "edges": edges})
    nodes, edges = compressed["nodes"], compressed["edges"]
    represented_ways = {ident for e in edges for ident in e["osm_ways"]}
    if represented_ways != expected_ways:
        raise ValueError("Curve fitting changed the retained OSM way set")
    # Bridge clearance and a grade-limited approach on the connected graph.
    a = np.array([e["a"] for e in edges])
    b = np.array([e["b"] for e in edges])
    heights = sample(ground, np.array([n["xyz"] for n in nodes])[:, [0, 2]])
    for e in edges:
        pa, pb = (
            np.array(nodes[e["a"]]["xyz"])[[0, 2]],
            np.array(nodes[e["b"]]["xyz"])[[0, 2]],
        )
        xz = (
            pa
            + (pb - pa) * np.linspace(0, 1, max(3, math.ceil(e["length"] / 8)))[:, None]
        )
        wet = sample(depth, xz) > 0.3
        if e["structure"] == "bridge" or (wet.any() and e["structure"] != "tunnel"):
            e["structure"] = "bridge"
            target = sample(ground, xz) + max(7, e["layer"] * 7)
            target[wet] = np.maximum(target[wet], sample(ground + depth, xz[wet]) + 8)
            heights[[e["a"], e["b"]]] = np.maximum(
                heights[[e["a"], e["b"]]], target.max()
            )
    limits = np.array([0.06 if e["kind"] == "highway" else 0.12 for e in edges])
    slack = limits * np.array([e["length"] for e in edges])
    for _ in range(len(nodes)):
        before = heights.copy()
        np.maximum.at(heights, a, heights[b] - slack)
        np.maximum.at(heights, b, heights[a] - slack)
        if np.array_equal(before, heights):
            break
    else:
        raise ValueError("Street grade constraints did not converge")
    for i, n in enumerate(nodes):
        n["xyz"][1] = float(heights[i])
    for e in edges:
        xz = np.array([nodes[e[k]]["xyz"] for k in ("a", "b")])[:, [0, 2]]
        if (
            e["structure"] == "ground"
            and np.max(heights[[e["a"], e["b"]]] - sample(ground, xz)) > 5
        ):
            e["structure"] = "bridge"
        grade = float((heights[e["b"]] - heights[e["a"]]) / e["length"])
        e["start_dir"][1], e["end_dir"][1] = grade, -grade
    degree = np.bincount(np.r_[a, b], minlength=len(nodes))
    if degree.max() > 8:
        raise ValueError(
            f"OSM junction exceeds CS1's eight-segment limit: {degree.max()}"
        )
    components = Union(len(nodes))
    for e in edges:
        components.join(e["a"], e["b"])
    sizes = Counter(components.find(i) for i in range(len(nodes)))
    return {
        "nodes": nodes,
        "edges": edges,
        "report": {
            "source": "OpenStreetMap node/way extract",
            "attribution": "© OpenStreetMap contributors (ODbL)",
            "osm_base": osm.get("osm3s", {}).get("timestamp_osm_base"),
            "motor_ways_in_extract": len(ways),
            "motor_ways_in_square": sum(by_class.values()),
            "ways_outside_scope": len(outside_only),
            "boundary_clipped_ways": len(clipped),
            "excluded_highway_classes": dict(sorted(excluded.items())),
            "street_scope": scope,
            "represented_osm_ways": len(represented_ways),
            "ways_by_class": dict(sorted(by_class.items())),
            "zero_length_spans": zero_length,
            "nodes": len(nodes),
            "edges": len(edges),
            "length_km": sum(e["length"] for e in edges) / 1000,
            "connected_components": len(sizes),
            "largest_component_nodes": max(sizes.values()),
            "native_qualified": False,
            "curve_model": "provisional chord/3 cubic, 4m sampled symmetric geometric error, <=256m source arc",
            "before_curve_fit": {"nodes": before_nodes, "edges": before_edges},
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Capture full OSM topology for a prepared square"
    )
    parser.add_argument("geometry", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--endpoint", default=ENDPOINT, help="Overpass interpreter URL")
    parser.add_argument(
        "--pbf",
        type=Path,
        help="read a regional OSM PBF instead of Overpass (uv run --with osmium)",
    )
    args = parser.parse_args()
    try:
        sq = json.loads(args.geometry.read_text())["sq"]
        source = (
            extract_pbf(sq, args.pbf, args.output)
            if args.pbf
            else capture(sq, args.output, args.endpoint)
        )
    except (OSError, ValueError) as error:
        parser.exit(1, f"Street capture failed: {error}\n")
    print(
        json.dumps(
            {"output": str(args.output), "elements": len(source["osm"]["elements"])}
        )
    )
