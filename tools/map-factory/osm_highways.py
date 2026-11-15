"""OSM motorways and trunks -> a one-way node/segment graph CS1 can load.

Input roads are OpenMapTiles z14 tile fragments (class, ramp, oneway, brunnel,
layer). Fragments overlap by the tile buffer, so each is clipped back to its own
tile, then joined by endpoints. Two-way pieces become two right-hand one-way
carriageways. Ways are clipped to the 17.28 km square (outside nodes sit exactly
on the edge), resampled to 60-110 m segments with one shared tangent per middle
node, given a grade-limited profile and graded into the terrain. Pure numpy/scipy.
"""

import json
import math

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from prepare import pixel

HALF, SIZE, SPACING = 8640.0, 1081, 16.0
OFFSET = {"highway": 12.0, "ramp": 6.0}
GRADE = {"highway": 0.06, "ramp": 0.08}
TURN = {"highway": 30.0, "ramp": 45.0}
CUT_FILL, CLEARANCE, LAYER_CLEARANCE = 15.0, 8.0, 7.0


class Union:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, i):
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def join(self, a, b):
        self.parent[self.find(a)] = self.find(b)


def arc(pts):
    return np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]


def sample(grid, xz):
    xz = np.atleast_2d(xz)
    return ndimage.map_coordinates(
        grid,
        [540 - xz[:, 1] / SPACING, 540 + xz[:, 0] / SPACING],
        order=1,
        mode="nearest",
    )


def clip_box(pts, lo, hi):
    """Liang-Barsky per segment: inside pieces of a polyline, with the clip flags."""
    pieces, current = [], []
    for p, q in zip(pts[:-1], pts[1:]):
        t0, t1, d = 0.0, 1.0, q - p
        ok = True
        for axis in range(2):
            for sign, bound in [(-1, lo[axis]), (1, hi[axis])]:
                den = sign * d[axis]
                num = sign * (bound - p[axis])
                if abs(den) < 1e-12:
                    ok &= num >= 0
                elif den > 0:
                    t1 = min(t1, num / den)
                else:
                    t0 = max(t0, num / den)
        if not ok or t0 > t1:
            if current:
                pieces.append(current)
                current = []
            continue
        a, b = p + d * t0, p + d * t1
        if not current:
            current = [(a, t0 > 0)]
        current.append((b, t1 < 1))
        if t1 < 1:
            pieces.append(current)
            current = []
    if current:
        pieces.append(current)
    return [
        (np.array([v for v, _ in c]), c[0][1], c[-1][1]) for c in pieces if len(c) > 1
    ]


def source_tile(merc, buffer=64 / 4096):
    """The tile a fragment came from: it fits that tile plus the 64-unit buffer,
    and its clipped ends lie on that tile's buffer line. Pure buffer slivers of
    a neighbouring tile clip to nothing there, which is what drops them."""
    best, best_score = None, -1
    lo = np.floor(merc.min(axis=0) + buffer)
    hi = np.floor(merc.max(axis=0) - buffer)
    for tx in range(int(lo[0]) - 1, int(hi[0]) + 2):
        for ty in range(int(lo[1]) - 1, int(hi[1]) + 2):
            local = merc - [tx, ty]
            if local.min() < -buffer - 1e-4 or local.max() > 1 + buffer + 1e-4:
                continue
            ends = local[[0, -1]]
            on_line = np.abs(np.abs(ends - 0.5) - (0.5 + buffer)) < 1e-4
            core = np.all((local >= 0) & (local <= 1), axis=1).sum()
            score = (int(on_line.any(axis=1).sum()), int(core))
            if best is None or score > best_score:
                best, best_score = np.array([tx, ty], float), score
    return best


def fragments(geometry):
    """Tile-clipped fragments in game metres with per-segment attributes."""
    sq, z = geometry["sq"], geometry.get("zoom", 14)
    n = 2**z
    result, tunnels = [], 0
    for road in geometry.get("roads", []):
        cls = road.get("class")
        if cls not in ("motorway", "trunk", "motorway_link", "trunk_link"):
            continue
        ll = np.asarray(road["pts"], float)
        if len(ll) < 2:
            continue
        merc = np.column_stack(
            [
                (ll[:, 0] + 180) / 360 * n,
                (1 - np.arcsinh(np.tan(np.radians(ll[:, 1]))) / np.pi) / 2 * n,
            ]
        )
        tile = source_tile(merc)
        tunnels += road.get("brunnel") == "tunnel"
        # Lines that fit no tile (not tile-clipped input) are used whole.
        pieces = [(merc, 0, 0)] if tile is None else clip_box(merc, tile, tile + 1)
        for piece, _, _ in pieces:
            lon = piece[:, 0] / n * 360 - 180
            lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * piece[:, 1] / n))))
            px = np.array([pixel(sq, p) for p in zip(lon, lat)])
            xz = np.column_stack(
                [(px[:, 0] - 540) * SPACING, (540 - px[:, 1]) * SPACING]
            )
            keep = np.r_[True, np.linalg.norm(np.diff(xz, axis=0), axis=1) > 0.05]
            xz = xz[keep]
            if len(xz) < 2:
                continue
            if road.get("oneway") == -1:
                xz = xz[::-1]
            m = len(xz) - 1
            result.append(
                {
                    "pts": xz,
                    "kind": "ramp"
                    if road.get("ramp") == 1 or cls.endswith("_link")
                    else "highway",
                    "oneway": road.get("oneway") in (1, -1),
                    "bridge": np.full(m, road.get("brunnel") == "bridge"),
                    "tunnel": np.full(m, road.get("brunnel") == "tunnel"),
                    "layer": np.full(m, int(road.get("layer") or 0)),
                    "cls": cls.replace("_link", ""),
                }
            )
    return result, tunnels


def split_at(frag, cut_arcs):
    s = arc(frag["pts"])
    out, start = [], 0.0
    for c in sorted(cut_arcs) + [s[-1]]:
        keep = (s > start + 1e-6) & (s < c - 1e-6)
        pa, pb = (
            np.interp([start, c], s, frag["pts"][:, 0]),
            np.interp([start, c], s, frag["pts"][:, 1]),
        )
        pts = np.vstack([[pa[0], pb[0]], frag["pts"][keep], [pa[1], pb[1]]])
        seg = np.clip(
            np.searchsorted(s, (arc(pts)[:-1] + arc(pts)[1:]) / 2 + start) - 1,
            0,
            len(s) - 2,
        )
        piece = dict(frag, pts=pts)
        for k in ("bridge", "tunnel", "layer"):
            piece[k] = frag[k][seg]
        out.append(piece)
        start = c
    return out


def join_touching(frags):
    """Split a line where another fragment's dangling end touches it (<= 4 m)."""
    ends = np.array([f["pts"][e] for f in frags for e in (0, -1)])
    near = cKDTree(ends).query_ball_point(ends, 2.0)
    dense, owner, along = [], [], []
    for i, f in enumerate(frags):
        s = arc(f["pts"])
        t = np.linspace(0, s[-1], max(2, int(s[-1] / 2) + 1))
        dense.append(
            np.column_stack(
                [np.interp(t, s, f["pts"][:, 0]), np.interp(t, s, f["pts"][:, 1])]
            )
        )
        owner.append(np.full(len(t), i))
        along.append(t)
    dense, owner, along = np.vstack(dense), np.concatenate(owner), np.concatenate(along)
    tree, cuts = cKDTree(dense), {}
    for k, p in enumerate(ends):
        if len(near[k]) > 1:
            continue
        f = k // 2
        best = None
        for j in tree.query_ball_point(p, 4.0):
            g = owner[j]
            length = arc(frags[g]["pts"])[-1]
            if g == f or along[j] < 4 or along[j] > length - 4:
                continue
            d = np.linalg.norm(dense[j] - p)
            if best is None or d < best[0]:
                best = (d, g, along[j], dense[j])
        if best:
            _, g, a, q = best
            if all(abs(a - c) > 2 for c in cuts.get(g, [])):
                cuts.setdefault(g, []).append(a)
            frags[f]["pts"][0 if k % 2 == 0 else -1] = q
    out = []
    for i, f in enumerate(frags):
        out.extend(split_at(f, cuts[i]) if i in cuts else [f])
    return out


def reverse(f):
    return dict(
        f, pts=f["pts"][::-1], **{k: f[k][::-1] for k in ("bridge", "tunnel", "layer")}
    )


def concat(a, b):
    return dict(
        a,
        pts=np.vstack([a["pts"], b["pts"][1:]]),
        **{k: np.concatenate([a[k], b[k]]) for k in ("bridge", "tunnel", "layer")},
    )


def chain(frags):
    """Join fragments through degree-2 compatible endpoints into ways with end ids."""
    ends = np.array([f["pts"][e] for f in frags for e in (0, -1)])
    u = Union(len(ends))
    for a, b in cKDTree(ends).query_pairs(2.0):
        u.join(a, b)
    ids = [u.find(i) for i in range(len(ends))]
    at = {}
    for k, c in enumerate(ids):
        at.setdefault(c, []).append(k)

    def through(c, k):
        if len(at[c]) != 2:
            return None
        other = at[c][0] if at[c][1] == k else at[c][1]
        f, g = frags[k // 2], frags[other // 2]
        if other // 2 == k // 2 or f["kind"] != g["kind"] or f["oneway"] != g["oneway"]:
            return None
        if f["oneway"] and (k % 2) == (other % 2):
            return None
        return other

    seen, ways = set(), []
    for start in range(len(frags)):
        if start in seen:
            continue
        seen.add(start)
        way, a, b = frags[start], 2 * start, 2 * start + 1
        for forward in (True, False):
            k = b if forward else a
            while (o := through(ids[k], k)) is not None and o // 2 not in seen:
                seen.add(o // 2)
                g = frags[o // 2] if (o % 2 == 0) == forward else reverse(frags[o // 2])
                far = o + 1 if o % 2 == 0 else o - 1
                way = concat(way, g) if forward else concat(g, way)
                k = far
            if forward:
                b = k
            else:
                a = k
        way["ends"] = [ids[a], ids[b]]
        ways.append(way)
    positions = {c: ends[at[c]].mean(axis=0) for c in at}
    return ways, positions


def contract(ways, positions):
    """Merge junction ids joined by a way shorter than 40 m."""
    while True:
        degree = {}
        for w in ways:
            for c in w["ends"]:
                degree[c] = degree.get(c, 0) + 1
        short = next(
            (
                w
                for w in ways
                if arc(w["pts"])[-1] < 40
                and w["ends"][0] != w["ends"][1]
                and all(degree[c] >= 3 for c in w["ends"])
            ),
            None,
        )
        if short is None:
            break
        a, b = short["ends"]
        positions[a] = (positions[a] + positions[b]) / 2
        ways[:] = [w for w in ways if w is not short]
        for w in ways:
            w["ends"] = [a if c == b else c for c in w["ends"]]
    ways[:] = [
        w for w in ways if w["ends"][0] != w["ends"][1] or arc(w["pts"])[-1] > 200
    ]
    for w in ways:
        w["pts"][0], w["pts"][-1] = positions[w["ends"][0]], positions[w["ends"][1]]
    return ways


def carriageways(ways):
    """Two-way pieces -> two one-way carriageways offset to the right of travel."""
    degree = {}
    for w in ways:
        for c in w["ends"]:
            degree[c] = degree.get(c, 0) + 1
    out = []
    for w in ways:
        if w["oneway"]:
            out.append(w)
            continue
        for v in (w, reverse(dict(w, ends=w["ends"][::-1]))):
            pts, s = v["pts"], arc(v["pts"])
            t = np.gradient(pts, axis=0)
            t /= np.maximum(np.linalg.norm(t, axis=1), 1e-9)[:, None]
            taper = np.ones(len(pts))
            if degree[v["ends"][0]] > 1:
                taper *= np.clip(s / 60, 0, 1)
            if degree[v["ends"][1]] > 1:
                taper *= np.clip((s[-1] - s) / 60, 0, 1)
            right = np.column_stack([t[:, 1], -t[:, 0]])
            out.append(
                dict(
                    v, pts=pts + right * OFFSET[v["kind"]] * taper[:, None], oneway=True
                )
            )
    return out


def edge_name(p):
    return {(0, 1): "east", (0, -1): "west", (1, 1): "north", (1, -1): "south"}[
        (int(abs(p[1]) > abs(p[0])), int(np.sign(p[np.argmax(np.abs(p))])))
    ]


def clip_square(ways, positions):
    out, next_id = [], max(positions, default=0) + 1
    lo, hi = np.array([-HALF, -HALF]), np.array([HALF, HALF])
    for w in ways:
        s = arc(w["pts"])
        for pts, cut_a, cut_b in clip_box(w["pts"], lo, hi):
            length = arc(pts)[-1]
            if (
                length < 1
                or (not (cut_a or cut_b) and length < 20)
                or (cut_a and cut_b and length < 300)
            ):
                continue
            seg = np.clip(_project(w["pts"], pts), 0, len(s) - 2)
            piece = dict(
                w, pts=pts, **{k: w[k][seg] for k in ("bridge", "tunnel", "layer")}
            )
            ends, outside = list(w["ends"]), [None, None]
            for i, cut in ((0, cut_a), (1, cut_b)):
                if cut:
                    p = pts[0 if i == 0 else -1]
                    axis = int(abs(p[1]) > abs(p[0]))
                    p[1 - axis] = np.clip(p[1 - axis], -HALF + 200, HALF - 200)
                    p[axis] = math.copysign(HALF, p[axis])
                    ends[i], outside[i] = next_id, edge_name(p)
                    positions[next_id] = p.copy()
                    next_id += 1
            piece["ends"], piece["outside"] = ends, outside
            out.append(piece)
    return trim_ramp_portals(out)


def trim_ramp_portals(ways, near=60.0, trim=80.0):
    """A ramp leaving the square beside a highway portal stops short of the edge
    instead of making a second outside connection a few metres away."""
    portals = [
        w["pts"][0 if i == 0 else -1]
        for w in ways
        if w["kind"] == "highway"
        for i in (0, 1)
        if w["outside"][i]
    ]
    out = []
    for w in ways:
        for i in (0, 1):
            end = w["pts"][0 if i == 0 else -1]
            if w["kind"] != "ramp" or not w["outside"][i] or not portals:
                continue
            if min(np.linalg.norm(p - end) for p in portals) > near:
                continue
            s = arc(w["pts"])
            if s[-1] <= trim + 20:
                w = None
                break
            keep = (s > trim) if i == 0 else (s < s[-1] - trim)
            cut = trim if i == 0 else s[-1] - trim
            point = [np.interp(cut, s, w["pts"][:, k]) for k in range(2)]
            seg = np.flatnonzero(keep[:-1] | keep[1:])
            pts = (
                np.vstack([point, w["pts"][keep]])
                if i == 0
                else np.vstack([w["pts"][keep], point])
            )
            w = dict(
                w,
                pts=pts,
                **{k: w[k][seg[: len(pts) - 1]] for k in ("bridge", "tunnel", "layer")},
            )
            w["outside"] = [None if j == i else w["outside"][j] for j in (0, 1)]
            w["ends"] = [
                (-(id(w) % 10**9) - j) if j == i else w["ends"][j] for j in (0, 1)
            ]
        if w is not None:
            out.append(w)
    return out


def _project(orig, pts):
    """Original segment index nearest each clipped-piece segment midpoint."""
    tree = cKDTree((orig[:-1] + orig[1:]) / 2)
    return tree.query((pts[:-1] + pts[1:]) / 2)[1]


def components(ways):
    ids = sorted({c for w in ways for c in w["ends"]})
    index = {c: i for i, c in enumerate(ids)}
    u = Union(len(ids))
    for w in ways:
        u.join(index[w["ends"][0]], index[w["ends"][1]])
    groups = {}
    for w in ways:
        groups.setdefault(u.find(index[w["ends"][0]]), []).append(w)
    return list(groups.values())


def resample(w):
    """Dense smoothed 5 m curve, then node arcs with the turn limit."""
    s = arc(w["pts"])
    t = np.linspace(0, s[-1], max(2, int(np.ceil(s[-1] / 5)) + 1))
    dense = np.column_stack([np.interp(t, s, w["pts"][:, k]) for k in range(2)])
    seg = np.clip(np.searchsorted(s, t, side="right") - 1, 0, len(s) - 2)
    if len(t) > 8:
        raw, f = dense.copy(), t / t[-1]
        dense = ndimage.gaussian_filter1d(
            raw, 4 if w["kind"] == "highway" else 3, axis=0, mode="nearest"
        )
        dense += (raw[0] - dense[0]) * (1 - f)[:, None] + (raw[-1] - dense[-1]) * f[
            :, None
        ]
    t = arc(dense)
    tangent = np.gradient(dense, axis=0)
    tangent /= np.maximum(np.linalg.norm(tangent, axis=1), 1e-9)[:, None]
    count = max(1, math.ceil(t[-1] / 110))
    while True:
        cut = np.searchsorted(t, np.linspace(0, t[-1], count + 1))
        cut[-1] = len(t) - 1
        turns = [
            np.degrees(np.arccos(np.clip(np.dot(tangent[a], tangent[b]), -1, 1)))
            for a, b in zip(cut[:-1], cut[1:])
        ]
        if max(turns) <= TURN[w["kind"]] or t[-1] / (count + 1) < 40:
            break
        count += 1
    return dense, tangent, cut, seg, max(turns)


def build_highway_graph(geometry, ground, depth):
    original = ground.copy()
    frags, tunnels = fragments(geometry)
    report = {"osm_fragments": len(frags), "osm_tunnel_fragments": int(tunnels)}
    if not frags:
        return {"nodes": [], "edges": [], "report": dict(report, edges=0)}
    ways, positions = chain(join_touching(frags))
    ways = clip_square(carriageways(contract(ways, positions)), positions)
    kept, dropped = [], 0
    for group in components(ways):
        if (
            any(o for w in group for o in w["outside"])
            or sum(arc(w["pts"])[-1] for w in group) >= 2000
        ):
            kept.extend(group)
        else:
            dropped += 1
    report["components_dropped"] = dropped
    if not kept:
        return {"nodes": [], "edges": [], "report": dict(report, edges=0)}
    nodes, ends, edges, turn_violations = [], {}, [], 0
    for w in kept:
        dense, tangent, cut, seg, worst = resample(w)
        turn_violations += worst > TURN[w["kind"]]
        ids = []
        for k, i in enumerate(cut):
            end = 0 if k == 0 else 1 if k == len(cut) - 1 else None
            if end is not None and w["ends"][end] in ends:
                ids.append(ends[w["ends"][end]])
                nodes[ids[-1]]["tangents"].append((tangent[i], end))
                continue
            nodes.append(
                {
                    "xz": dense[i].copy(),
                    "tangents": [(tangent[i], end)],
                    "outside": w["outside"][end] if end is not None else None,
                }
            )
            ids.append(len(nodes) - 1)
            if end is not None:
                ends[w["ends"][end]] = ids[-1]
        s = arc(dense)
        for k, (a, b) in enumerate(zip(ids[:-1], ids[1:])):
            if a == b:
                continue
            sl = slice(cut[k], cut[k + 1] + 1)
            attr = seg[sl.start : sl.stop]
            edges.append(
                {
                    "a": a,
                    "b": b,
                    "kind": w["kind"],
                    "cls": w["cls"],
                    "xz": dense[sl],
                    "s": s[sl] - s[cut[k]],
                    "ta": tangent[cut[k]],
                    "tb": tangent[cut[k + 1]],
                    "bridge": w["bridge"][np.minimum(attr, len(w["bridge"]) - 1)],
                    "tunnel": w["tunnel"][np.minimum(attr, len(w["tunnel"]) - 1)],
                    "layer": w["layer"][np.minimum(attr, len(w["layer"]) - 1)],
                    "way": id(w),
                }
            )
    # A degree-2 pass-through node shares one tangent so CS1 classes it Middle.
    for n in nodes:
        arrive = [t for t, e in n["tangents"] if e == 1]
        depart = [t for t, e in n["tangents"] if e == 0]
        if len(n["tangents"]) == 2 and len(arrive) == len(depart) == 1:
            t = arrive[0] + depart[0]
            n["shared"] = t / max(np.linalg.norm(t), 1e-9)
    for e in edges:
        for key, end in (("ta", "a"), ("tb", "b")):
            if "shared" in nodes[e[end]]:
                e[key] = nodes[e[end]]["shared"]
    # Vertical profile: smoothed terrain, water clearance, OSM layers, grade-limited.
    surface = original + np.maximum(depth, 0)
    req = np.full(len(nodes), -1e9)
    by_way = {}
    for e in edges:
        by_way.setdefault(e["way"], []).append(e)
    for group in by_way.values():
        xz = np.vstack([e["xz"] for e in group])
        terrain = sample(original, xz)
        smooth = ndimage.gaussian_filter1d(terrain, 30, mode="nearest")
        r = np.maximum(smooth, terrain - CUT_FILL)
        wet = sample(depth, xz) > 0.3
        r[wet] = np.maximum(r[wet], sample(surface, xz[wet]) + CLEARANCE)
        layer = np.concatenate([e["layer"] for e in group])
        bridge = np.concatenate([e["bridge"] for e in group])
        lift = bridge & (layer > 0)
        r[lift] = np.maximum(r[lift], terrain[lift] + LAYER_CLEARANCE * layer[lift])
        tunnel = np.concatenate([e["tunnel"] for e in group])
        if tunnel.any() and not tunnel.all():
            idx = np.arange(len(r))
            r[tunnel] = np.interp(idx[tunnel], idx[~tunnel], r[~tunnel])
        k = 0
        for e in group:
            n = len(e["xz"])
            e["terrain"], e["req"], e["wet"] = (
                terrain[k : k + n],
                r[k : k + n],
                wet[k : k + n],
            )
            g, length = GRADE[e["kind"]], e["s"][-1]
            req[e["a"]] = max(req[e["a"]], float(np.max(e["req"] - g * e["s"])))
            req[e["b"]] = max(
                req[e["b"]], float(np.max(e["req"] - g * (length - e["s"])))
            )
            k += n
    a = np.array([e["a"] for e in edges])
    b = np.array([e["b"] for e in edges])
    slack = np.array([GRADE[e["kind"]] * e["s"][-1] for e in edges])
    h = req.copy()
    for _ in range(5000):
        before = h.copy()
        np.maximum.at(h, a, h[b] - slack)
        np.maximum.at(h, b, h[a] - slack)
        if np.array_equal(before, h):
            break
    # Structures and earthworks.
    mask, value, is_bridge = (
        np.zeros((SIZE, SIZE), bool),
        np.zeros((SIZE, SIZE)),
        np.zeros((SIZE, SIZE), bool),
    )
    bridges = 0
    for e in edges:
        u = e["s"] / max(e["s"][-1], 1e-9)
        e["h"] = h[e["a"]] + (h[e["b"]] - h[e["a"]]) * (3 * u**2 - 2 * u**3)
        above = float(np.max(e["h"] - e["terrain"]))
        below = float(np.max(e["terrain"] - e["h"]))
        why = (
            "tunnel"
            if e["tunnel"].mean() > 0.5 and below > 8
            else "water"
            if e["wet"].sum() >= 2
            else "height"
            if above > CUT_FILL + 5
            else "osm"
            if e["bridge"].mean() > 0.5 and above >= 3
            else None
        )
        e["structure"] = "tunnel" if why == "tunnel" else "bridge" if why else "ground"
        e["why"] = why
        bridges += e["structure"] == "bridge"
        rows = np.clip(np.round(540 - e["xz"][:, 1] / SPACING).astype(int), 0, SIZE - 1)
        cols = np.clip(np.round(540 + e["xz"][:, 0] / SPACING).astype(int), 0, SIZE - 1)
        mask[rows, cols] = True
        value[rows, cols] = e["h"]
        is_bridge[rows, cols] |= e["structure"] != "ground"
    distance, (ri, ci) = ndimage.distance_transform_edt(~mask, return_indices=True)
    distance *= SPACING
    t = np.clip((40 - distance) / 24, 0, 1)
    weight = np.where(distance <= 16, 1.0, t * t * (3 - 2 * t))
    weight[is_bridge[ri, ci]] = 0
    weight[ndimage.binary_dilation(depth > 0.1, iterations=6)] = 0
    target = np.clip(value[ri, ci], original - CUT_FILL, original + CUT_FILL)
    ground += (target - ground) * weight
    # Output.
    out_nodes = [
        {
            "xyz": [float(n["xz"][0]), float(h[i]), float(n["xz"][1])],
            "outside": n["outside"],
        }
        for i, n in enumerate(nodes)
    ]
    out_edges, grades, km = [], [], {"highway": 0.0, "ramp": 0.0}
    for e in edges:
        length = float(e["s"][-1])
        grades.append(abs(h[e["b"]] - h[e["a"]]) / max(length, 1e-9))
        km[e["kind"]] += length / 1000
        out_edges.append(
            {
                "a": e["a"],
                "b": e["b"],
                "kind": e["kind"],
                "structure": e["structure"],
                "start_dir": [float(e["ta"][0]), 0.0, float(e["ta"][1])],
                "end_dir": [float(-e["tb"][0]), 0.0, float(-e["tb"][1])],
                "osm_class": e["cls"],
                "ref": None,
                "length": length,
            }
        )
    degree = np.bincount(np.r_[a, b], minlength=len(nodes))
    residual = [
        abs(h[i] - sample(ground, n["xz"])[0])
        for i, n in enumerate(nodes)
        if all(
            edges[j]["structure"] == "ground"
            for j in np.flatnonzero((a == i) | (b == i))
        )
    ]
    report.update(
        {
            "nodes": len(out_nodes),
            "edges": len(out_edges),
            "junctions": int((degree >= 3).sum()),
            "max_degree": int(degree.max()),
            "dangling_ends": int(
                sum(
                    1
                    for i, n in enumerate(nodes)
                    if degree[i] == 1 and not n["outside"]
                )
            ),
            "outside": [
                {
                    "edge": n["outside"],
                    "direction": "in" if any(e["a"] == i for e in edges) else "out",
                    "kind": next(e["kind"] for e in edges if i in (e["a"], e["b"])),
                    "at": [round(n["xz"][0]), round(n["xz"][1])],
                }
                for i, n in enumerate(nodes)
                if n["outside"]
            ],
            "km": {k: round(v, 2) for k, v in km.items()},
            "max_grade": float(max(grades)),
            "bridges": bridges,
            "tunnels": sum(e["structure"] == "tunnel" for e in out_edges),
            "bridge_km": round(
                sum(e["length"] for e in out_edges if e["structure"] == "bridge")
                / 1000,
                2,
            ),
            "max_cut_m": float(np.maximum(original - ground, 0).max()),
            "max_fill_m": float(np.maximum(ground - original, 0).max()),
            "ground_node_residual_max_m": float(max(residual, default=0)),
            "turn_limit_violations": int(turn_violations),
            "min_segment_m": float(min(e["length"] for e in out_edges)),
            "max_segment_m": float(max(e["length"] for e in out_edges)),
        }
    )
    return {"nodes": out_nodes, "edges": out_edges, "report": report}


def load_fixture(root):
    import gzip
    from pathlib import Path

    root = Path(root)
    # Fixture grids are CS1-native south-first; this module works north-first.
    geometry = json.load(gzip.open(root / "geometry.json.gz"))

    def grid(name):
        raw = np.frombuffer(gzip.open(root / name).read(), "<u2")
        return raw.reshape(SIZE, SIZE)[::-1] / 64.0

    return (
        geometry,
        grid("terrain.u16.gz").astype(float),
        grid("water.u16.gz").astype(float),
    )


def plot(graph, ground, path):
    from PIL import Image, ImageDraw

    dy, dx = np.gradient(ground, SPACING)
    shade = np.clip(0.6 + (dx - dy) * 0.9, 0, 1) * 255
    image = Image.fromarray(shade.astype(np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(image)
    px = lambda p: (540 + p[0] / SPACING, 540 - p[2] / SPACING)  # noqa: E731
    colour = {
        ("highway", "ground"): (200, 30, 30),
        ("ramp", "ground"): (240, 150, 0),
        ("highway", "bridge"): (30, 90, 220),
        ("ramp", "bridge"): (90, 170, 255),
        ("highway", "tunnel"): (150, 0, 180),
        ("ramp", "tunnel"): (200, 90, 220),
    }
    for e in graph["edges"]:
        draw.line(
            [px(graph["nodes"][e["a"]]["xyz"]), px(graph["nodes"][e["b"]]["xyz"])],
            fill=colour[(e["kind"], e["structure"])],
            width=2,
        )
    for n in graph["nodes"]:
        if n["outside"]:
            x, y = px(n["xyz"])
            draw.ellipse([x - 7, y - 7, x + 7, y + 7], outline=(0, 160, 0), width=3)
    image.save(path)


if __name__ == "__main__":
    import sys

    geometry, ground, depth = load_fixture(sys.argv[1])
    graph = build_highway_graph(geometry, ground, depth)
    if len(sys.argv) > 2:
        plot(graph, ground, sys.argv[2])
    print(json.dumps(graph["report"], indent=1))
