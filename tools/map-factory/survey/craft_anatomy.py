"""Static anatomy of CS1 .crp map packages (and identification of theme packages).

Reads exact package bytes only; nothing here runs or simulates the game. Every
field comes from the stored save state that the game deserializes on load:
TerrainManager raw heights, WaterSimulation cells and sources, NetManager nodes
and segments, NaturalResourceManager grids, TreeManager instances, GameAreaManager
start tile, and the package's MapMetaData / MapThemeMetaData. Version gates follow
CS1 Assembly-CSharp (DataSerializer.version), so older Workshop maps decode with
their own layout. A manager this reader cannot decode consistently is reported as
"unknown" with the reason, never as zeros.

usage: craft_anatomy.py [CRP ...] --out DIR [--contract CONTRACT.json]
                        [--workshop-root DIR]
With no CRP arguments it reads every *.crp under DIR/inputs. The contract
defaults to the shipping contract fixtures/active.json names.
"""

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure_maps import (  # noqa: E402  (reused, version-aware readers)
    CENTRAL,
    CELL_KM2,
    TILE,
    decode,
    data_version,
    parse_resources,
    parse_start_tile,
    parse_terrain,
    parse_trees,
    read_unique_string,
    section,
)

HN = 1081  # terrain/water nodes, 16 m spacing, node i at world (i - 540) * 16
CELL_M = 16.0
HALF = 8640.0
TILE_M = 1920.0
C25 = 4800.0  # central 5x5 tiles span |x|, |z| <= 4800 m
KIND_NAMES = {
    3: "texture",
    52: "serialized_data",
    100: "MapMetaData",
    101: "SaveGameMetaData",
    106: "MapThemeMetaData",
}
WATER_TYPE = {0: "none", 1: "natural", 2: "facility", 3: "cleaner"}
CHANNEL_MIN_DEPTH = 0.125  # m (8 raw units); thinner films are startup coverage only
BODY_RADIUS = 12  # 16 m cells; water inside a 25-cell (~400 m) disk is "open water"
SLOPE_THRESHOLDS = [1, 3, 6, 10, 15, 25]  # percent
SEA_TOLERANCE = (
    3.0  # m; saved Workshop ocean surfaces undulate about +-2 m around sea level
)


CAVEATS = [
    "Static storage only: stored depth, velocity and source counters are a save-time snapshot; "
    "nothing here predicts how water moves after load.",
    "m_flow and source rates are game-internal raw units per water step, not m3/s discharge.",
    "Channel width/depth are sampled on 16 m nodes; 16 m is the smallest resolvable width.",
    "Network classes are a keyword rule on NetInfo prefab names; segment lengths are node-to-node "
    "chords, not Bezier arc lengths.",
    "buildableArea is the editor's stored percentage; slope shares are measured independently.",
]


# ---------------------------------------------------------------- packaging
class Reader:
    def __init__(self, data, pos=0):
        self.data, self.pos = data, pos

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError("read past end")
        v = self.data[self.pos : self.pos + n]
        self.pos += n
        return v

    def num(self, fmt):
        return struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))[0]

    def string(self):
        size = 0
        for shift in range(0, 35, 7):
            b = self.num("B")
            size |= (b & 127) << shift
            if b < 128:
                return self.take(size).decode("utf8")
        raise ValueError("bad string length")


def read_package(raw):
    """CRP directory (formats 2..12 share it) with per-asset MD5 verification."""
    r = Reader(raw)
    if r.take(4) != b"CRAP":
        raise ValueError("not a CRP")
    pkg = {
        "format": r.num("H"),
        "name": r.string(),
        "author_field_bytes": len(r.string()),
    }
    pkg["version"], pkg["main"] = r.num("I"), r.string()
    count, start = r.num("i"), r.num("q")
    if not 0 < count <= 10000:
        raise ValueError("implausible asset count")
    assets, end = [], start
    for _ in range(count):
        name, checksum, kind = r.string(), r.string(), r.num("i")
        off, size = r.num("q"), r.num("q")
        if off < 0 or size < 0 or start + off + size > len(raw):
            raise ValueError("asset outside package")
        payload = raw[start + off : start + off + size]
        assets.append(
            {
                "name": name,
                "kind": kind,
                "bytes": size,
                "md5": checksum,
                "md5_ok": hashlib.md5(payload).hexdigest() == checksum,
                "payload": payload,
            }
        )
        end = max(end, start + off + size)
    if r.pos != start:
        raise ValueError("directory length mismatch")
    pkg["trailing_bytes"] = len(raw) - end
    return pkg, assets


def _meta_value(r, t):
    """One MetaData field as PackageDeserializer + PackageHelper read it."""
    if t.endswith("[]"):
        n = r.num("i")
        if not 0 <= n <= 100000:
            raise ValueError("bad metadata array length")
        return [_meta_value(r, t[:-2]) for _ in range(n)]
    if t in (
        "System.String",
        "System.DateTime",
        "ColossalFramework.Packaging.Package+Asset",
    ):
        return r.string()  # Package.Asset is its checksum string (package format >= 3)
    if t == "ModInfo":
        return [r.string(), r.num("Q")]
    if t == "DisasterProperties+DisasterSettings":
        return [r.string(), r.num("i")]
    fixed = {
        "System.Boolean": "B",
        "System.Byte": "B",
        "System.Int32": "i",
        "System.UInt32": "I",
        "System.UInt64": "Q",
        "System.Single": "f",
        "UnityEngine.Vector2": "2f",
        "UnityEngine.Vector3": "3f",
        "UnityEngine.Vector4": "4f",
        "UnityEngine.Color": "4f",
        "UnityEngine.Color32": "4B",
        "UnityEngine.Quaternion": "4f",
    }
    if t not in fixed:
        raise KeyError(t)
    v = struct.unpack("<" + fixed[t], r.take(struct.calcsize("<" + fixed[t])))
    return (
        v[0] if len(v) == 1 else [round(x, 5) if isinstance(x, float) else x for x in v]
    )


def parse_meta(payload):
    """Returns (fields, problems). Unknown field types stop decoding explicitly."""
    r = Reader(payload)
    if r.num("B") != 0:
        return {}, ["null metadata object"]
    typ = r.string().split(",")[0]
    r.string()
    n = r.num("i")
    out, problems = {"_type": typ}, []
    for i in range(n):
        if r.num("B"):
            continue
        t, name = r.string().split(",")[0], r.string()
        try:
            out[name] = _meta_value(r, t)
        except KeyError:
            problems.append(
                f"field {name!r} has unsupported type {t!r}; "
                f"{n - i - 1} later fields not decoded"
            )
            break
    if not problems and r.pos != len(payload):
        rest = payload[r.pos :]
        if any(rest):
            problems.append(f"{len(rest)} non-zero metadata bytes after last field")
        else:
            out["_zero_padding_bytes"] = len(rest)
    return out, problems


def next_tag(data, o, window=64):
    """First Latin-1 shared tag within `window` bytes after o: (gap, name)."""
    for k in range(window):
        name = tag_name_at(data, o + k)
        if name and name.isprintable():
            return {"gap_bytes": k, "name": name}
    return None


def tag_name_at(data, o):
    """Latin-1 shared type/manager tag starting at o, if one starts there."""
    if o + 4 > len(data) or data[o] != 254:
        return None
    head = int.from_bytes(data[o + 1 : o + 4], "big")
    if not head & 0x800000 or (head & 0x7FFFFF) > 200:
        return None
    s, prev = [], 128
    for b in data[o + 4 : o + 4 + (head & 0x7FFFFF)]:
        prev = (prev + b) & 255
        s.append(chr(prev))
    return "".join(s)


# ---------------------------------------------------------------- managers
class Cursor:
    def __init__(self, data, o):
        self.d, self.o = data, o

    def arr(self, count, width, signed=False):
        if width == 8:
            return self.skip(count, 8)
        v, self.o = decode(self.d, int(count), self.o, width, signed)
        return v

    def skip(self, count, width):
        """Advance over an EncodedArray without values (bytes depend only on run codes)."""
        i, lit = 0, 128 if width == 1 else 64
        while i < count:
            code = self.d[self.o]
            self.o += 1
            if code >= 128:
                n = code - 127
            elif code < lit:
                n = code + 1 if width == 1 else (code & 63) + 1
                self.o += n * width
            else:
                n = (code & 63) + 1
                self.o += n * (width // 2)
            if i + n > count:
                raise ValueError("run exceeds array")
            i += n
        return None

    def be(self, fmt):
        v = struct.unpack_from(">" + fmt, self.d, self.o)
        self.o += struct.calcsize(">" + fmt)
        return v if len(v) > 1 else v[0]

    def u24(self):
        v = int.from_bytes(self.d[self.o : self.o + 3], "big")
        self.o += 3
        return v

    def names(self):
        n = self.be("H")
        out = []
        for _ in range(n):
            s, self.o = read_unique_string(self.d, self.o)
            out.append(s)
        return out


def parse_water(data, v):
    """WaterSimulation.Data.Deserialize, every version gate, to its last field."""
    c = Cursor(data, section(data, "WaterSimulation"))
    height = c.arr(HN * HN, 2).reshape(HN, HN)
    wet = height != 0
    pollution = np.zeros((HN, HN), np.int64)
    pollution[wet] = c.arr(wet.sum(), 2)
    if v >= 42:
        vx_mask = wet.copy()
        vx_mask[:, :-1] |= wet[:, 1:]
        vz_mask = wet.copy()
        vz_mask[:-1, :] |= wet[1:, :]
    else:
        vx_mask = vz_mask = wet
    vel = {}
    for k, m in (("x", vx_mask), ("z", vz_mask)):
        a = np.zeros((HN, HN), np.int64)
        a[m] = c.arr(m.sum(), 2, signed=True)
        vel[k] = a
    sources = []
    for _ in range(c.be("H")):
        s = {"input": list(c.be("3f"))}
        s["output"] = list(c.be("3f")) if v >= 184 else s["input"]
        s["type"] = c.be("H")
        if v < 184:
            rate = c.u24() if v >= 95 else c.be("H")
            rate = rate if s["type"] == 1 else 0
            s["input_rate"] = s["output_rate"] = rate
        s["target_raw"] = c.be("H")
        if v >= 184:
            for k in ("water", "pollution", "input_rate", "output_rate", "flow"):
                s[k] = c.u24()
        else:
            c.o += 15 if v >= 95 else 10
            s.update(water=0, pollution=0, flow=0)
        sources.append(s)
    waves = []
    if v >= 259:
        for _ in range(c.be("H")):
            w = {"type": c.be("H") if v >= 261 else int(c.be("B") != 0)}
            vals = c.be("6H3hHH")
            w.update(
                dict(
                    zip(
                        [
                            "minX",
                            "minZ",
                            "maxX",
                            "maxZ",
                            "origX",
                            "origZ",
                            "dirX",
                            "dirZ",
                            "delta",
                            "duration",
                            "currentTime",
                        ],
                        vals,
                    )
                )
            )
            waves.append(w)
    sea = c.be("f") if v >= 131 else 40.0
    if v >= 147:
        c.o += 2
    frame = c.be("I") if v >= 173 else None
    return {
        "depth": height / 64.0,
        "pollution": pollution,
        "vx": vel["x"],
        "vz": vel["z"],
        "sources": sources,
        "waves": waves,
        "sea_level": float(sea),
        "frame": frame,
        "end": c.o,
        "next_tag": next_tag(data, c.o),
    }


def parse_network(data, v, problem_variant=None):
    """NetManager.Data.Deserialize through the NetInfo/TreeInfo/fence name tables."""
    c = Cursor(data, section(data, "NetManager"))
    lane_flags = c.arr(262143, 2) if v >= 24 else np.zeros(0)
    nl = int(np.count_nonzero(lane_flags))
    c.o += nl * (3 + (2 if v < 48 else 0)) if v >= 24 else 0
    if v >= 163:
        for _ in range(3):
            c.arr(nl, 1)
    if v >= 206:
        c.arr(nl, 2)
    if v >= 115018:
        nf = c.arr(32767 * 2, 4).reshape(-1, 2)[:, 0]
    elif v >= 202:
        nf = c.arr(32767, 4)
    else:
        nf = np.concatenate([c.arr(16383, 4), np.zeros(32767 - 16383, np.int64)])
        if v < 60:
            nf = nf & ~0x400
    ids = np.flatnonzero(nf) + 1
    n = len(ids)
    if v >= 115000:
        c.arr(n * 2, 8)
        variant = "ulong2"
    elif v >= 221:
        variant = (
            problem_variant or "ulong1"
        )  # needs saveAppVersion >= 1.3.0 for ulong1
        c.arr(n, 8 if variant == "ulong1" else 4)
    elif v >= 61:
        c.arr(n, 4)
        variant = "uint"
    else:
        variant = "none"
    if v >= 86:
        c.arr(n, 1)
    if v >= 105:
        c.arr(n * 2, 2)
    nodes = []
    for nid in ids:
        x, y, z = c.be("3f")
        k = c.be("B")
        if k > 8:
            raise ValueError(f"node {nid} has {k} segments")
        segs = [c.be("H") for _ in range(k)]
        c.o += (4 if v >= 45 else 0) + (2 if v >= 6 else 0)
        building = int.from_bytes(data[c.o - 2 : c.o], "big") if v >= 6 else 0
        c.o += (2 if v >= 80 else 0) + (4 if v >= 48 else 0) + (1 if v >= 57 else 0)
        c.o += (1 if v >= 59 else 0) + (1 if v >= 80 else 0) + (2 if v >= 121007 else 0)
        nodes.append(
            {
                "id": int(nid),
                "flags": int(nf[nid - 1]),
                "pos": (x, y, z),
                "segs": segs,
                "building": building,
            }
        )
    sf = c.arr(36863 if v >= 222 else 32767, 4)
    sids = np.flatnonzero(sf) + 1
    m = len(sids)
    if v >= 114012:
        c.arr(36863 if v >= 222 else 32767, 4)
    if v >= 115000:
        c.arr(m * 2, 8)
    elif v >= 226:
        c.arr(m, 8)
    if v >= 115017:
        c.arr(m * 2, 4)
    elif v >= 103:
        c.arr(m * 2, 1)
    if v >= 185:
        c.arr(m, 1)
    if v >= 224:
        c.arr(m, 1)
    if v >= 229:
        c.arr(m, 1)
    if v >= 109007:
        c.arr(m, 2)
        c.arr(m, 1)
    if v >= 121030:
        c.arr(m, 1)
    segs, trees, lf, rf = [], 0, 0, 0
    for sid in sids:
        c.o += 4 + (4 if v >= 46 else 0) + (3 if v >= 24 else 0) + (3 if v >= 50 else 0)
        c.o += 24
        a, b = c.be("2H")
        c.o += (
            8
            + (3 if v >= 77 else 0)
            + (2 if v >= 312 else 0)
            + (1 if v >= 113015 else 0)
        )
        if v >= 114002:
            trees += c.be("B") != 0
        if v >= 120003:
            lf += c.be("B") != 0
            rf += c.be("B") != 0
        c.o += 4 if v >= 121005 else 0
        segs.append({"id": int(sid), "flags": int(sf[sid - 1]), "a": a, "b": b})
    guides = milestones = 0
    if v >= 128:
        guides, milestones = c.be("H"), c.be("H")
    names = []
    if v >= 19:
        idx = c.arr(n + m + guides + milestones, 2)
        names = c.names()
        for i, node in enumerate(nodes):
            node["info"] = int(idx[i])
        for i, s in enumerate(segs):
            s["info"] = int(idx[n + i])
    tables = {}
    if v >= 114002:
        c.arr(trees, 2)
        tables["segment_tree_names"] = c.names()
    if v >= 120003:
        c.arr(lf, 2)
        tables["left_fence_names"] = c.names()
        c.arr(rf, 2)
        tables["right_fence_names"] = c.names()
    return {
        "nodes": nodes,
        "segments": segs,
        "names": names,
        "lanes": nl,
        "problem_variant": variant,
        "end": c.o,
        **tables,
    }


def check_network(net):
    by = {nd["id"]: nd for nd in net["nodes"]}
    sb = {s["id"]: s for s in net["segments"]}
    issues = []
    for s in net["segments"]:
        for e in ("a", "b"):
            if s[e] not in by:
                issues.append(f"segment {s['id']} -> absent node {s[e]}")
            elif s["id"] not in by[s[e]]["segs"]:
                issues.append(f"node {s[e]} does not list segment {s['id']}")
    for nd in net["nodes"]:
        for sid in nd["segs"]:
            if sid not in sb:
                issues.append(f"node {nd['id']} -> absent segment {sid}")
        if not all(math.isfinite(p) and abs(p) < 20000 for p in nd["pos"]):
            issues.append(f"node {nd['id']} position {nd['pos']} out of range")
    k = len(net["names"])
    for e in net["nodes"] + net["segments"]:
        if e.get("info", 0) >= max(k, 1):
            issues.append(f"prefab index {e['info']} >= {k} names")
            break
    return issues


def net_class(name):
    n = (name or "").lower()
    if any(w in n for w in ("ship", "ferry")):
        return "ship"
    if any(
        w in n
        for w in ("airplane", "plane", "blimp", "helicopter", "aircraft", "flight")
    ):
        return "air"
    if any(w in n for w in ("train", "rail", "metro", "track", "monorail", "tram")):
        return "rail"
    if any(
        w in n for w in ("pipe", "power line", "powerline", "electricity", "water ")
    ):
        return "utility"
    if any(
        w in n
        for w in (
            "road",
            "highway",
            "avenue",
            "street",
            "oneway",
            "ramp",
            "lane",
            "boulevard",
            "gravel",
            "bridge",
            "elevated",
            "tunnel",
            "slope",
        )
    ):
        return "road"
    return "other"


# ---------------------------------------------------------------- geometry helpers
def node_index(w):
    return int(np.clip(np.floor(w / CELL_M + 540 + 0.5), 0, HN - 1))


AX = (np.arange(HN) - 540) * CELL_M
CENTRAL16 = (np.abs(AX)[:, None] <= C25) & (np.abs(AX)[None, :] <= C25)  # [z, x]


def tile_mask16(sx, sz):
    x0, z0 = -C25 + sx * TILE_M, -C25 + sz * TILE_M
    inx = (AX >= x0) & (AX <= x0 + TILE_M)
    inz = (AX >= z0) & (AX <= z0 + TILE_M)
    return inz[:, None] & inx[None, :]


def km2(cells):
    return round(float(cells) * CELL_M * CELL_M / 1e6, 3)


def stats(a, nd=2):
    a = np.asarray(a, float)
    a = a[np.isfinite(a)]
    if not len(a):
        return None
    q = np.percentile(a, [0, 1, 10, 50, 90, 99, 100])
    return {
        k: round(float(x), nd)
        for k, x in zip(["min", "p1", "p10", "p50", "p90", "p99", "max"], q)
    }


def relief(h, mask):
    s = stats(h[mask], 1)
    s["relief_p1_p99_m"] = round(s["p99"] - s["p1"], 1)
    s["std_m"] = round(float(h[mask].std()), 1)
    return s


# ---------------------------------------------------------------- measurements
def measure_water(height, w, start_mask):
    depth = w["depth"]
    surface = height + depth
    sea = w["sea_level"]
    out = {
        "sea_level_m": round(sea, 3),
        "stored_frame_index": w["frame"],
        "waves_stored": len(w["waves"]),
        "next_object_tag_after_water": w["next_tag"],
    }
    regions = {
        "full": np.ones_like(CENTRAL16),
        "central25": CENTRAL16,
        "start_tile": start_mask,
    }
    cover = {}
    for rname, rm in regions.items():
        cover[rname] = {
            f"depth_gt_{t}m": {
                "km2": km2((depth > t)[rm].sum()),
                "share": round(float((depth > t)[rm].mean()), 4),
            }
            for t in (0, 0.5, 2.0)
        }
    out["startup_coverage"] = cover
    wet = depth > 0
    near_sea = wet & (np.abs(surface - sea) <= SEA_TOLERANCE)
    lab, _ = ndimage.label(near_sea, structure=np.ones((3, 3)))
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    seaconn = np.isin(lab, border[border > 0])
    out["sea_connected_wet"] = {
        "definition": f"wet node, |surface - sea_level| <= {SEA_TOLERANCE} m, "
        "8-connected to the map border",
        "full_km2": km2(seaconn.sum()),
        "central25_km2": km2((seaconn & CENTRAL16).sum()),
    }
    out["inland_wet"] = {
        "full_km2": km2((wet & ~seaconn).sum()),
        "central25_km2": km2((wet & ~seaconn & CENTRAL16).sum()),
    }
    out["depth_wet_m"] = stats(depth[wet]) if wet.any() else None
    vm = np.hypot(w["vx"], w["vz"])
    out["stored_velocity_snapshot"] = {
        "nonzero_nodes": int((vm > 0).sum()),
        "magnitude_raw_wet": stats(vm[wet]) if wet.any() else None,
        "note": "raw Int16 velocity fields as saved; a static snapshot, not a flow claim",
    }
    out["stored_pollution_nonzero_nodes"] = int((w["pollution"] > 0).sum())
    return out, seaconn


def measure_sources(height, w, start, chan_lab):
    depth = w["depth"]
    out = []
    for i, s in enumerate(w["sources"]):
        x, y, z = s["input"]
        ix, iz = node_index(x), node_index(z)
        target = s["target_raw"] / 64.0
        sx, sz = start
        out.append(
            {
                "index": i,
                "type": WATER_TYPE.get(s["type"], s["type"]),
                "input_position": [round(p, 2) for p in s["input"]],
                "output_position": [round(p, 2) for p in s["output"]],
                "grid_xz": [ix, iz],
                "terrain_m": round(float(height[iz, ix]), 2),
                "startup_depth_m": round(float(depth[iz, ix]), 3),
                "target_surface_m": round(target, 3),
                "target_minus_terrain_m": round(target - float(height[iz, ix]), 3),
                "target_minus_sea_m": round(target - w["sea_level"], 3),
                "input_rate_raw": s["input_rate"],
                "output_rate_raw": s["output_rate"],
                "behaviour": (
                    "disabled"
                    if s["type"] == 0
                    else "fill+drain regulator"
                    if s["input_rate"] and s["output_rate"]
                    else "drain only"
                    if s["input_rate"]
                    else "fill only"
                    if s["output_rate"]
                    else "inert"
                ),
                "input_radius_m": round(math.sqrt(s["input_rate"]) * 0.4 + 10, 1)
                if s["input_rate"]
                else 0,
                "output_radius_m": round(math.sqrt(s["output_rate"]) * 0.4 + 10, 1)
                if s["output_rate"]
                else 0,
                "input_rate_norm": round(s["input_rate"] / 65535, 5),
                "stored_water_raw": s["water"],
                "stored_pollution_raw": s["pollution"],
                "stored_m_flow_raw": s["flow"],
                "in_central25": bool(abs(x) <= C25 and abs(z) <= C25),
                "in_start_tile": bool(
                    -C25 + sx * TILE_M <= x <= -C25 + (sx + 1) * TILE_M
                    and -C25 + sz * TILE_M <= z <= -C25 + (sz + 1) * TILE_M
                ),
                "edge_distance_m": round(float(HALF - max(abs(x), abs(z))), 1),
                "channel_id_within_2_cells": int(
                    chan_lab[max(iz - 2, 0) : iz + 3, max(ix - 2, 0) : ix + 3].max()
                ),
            }
        )
    rates = [s["input_rate_raw"] for s in out]
    summary = {
        "count": len(out),
        "by_type": {},
        "by_behaviour": {},
        "input_rate_raw_sum": int(sum(rates)),
        "output_rate_raw_sum": int(sum(s["output_rate_raw"] for s in out)),
        "rate_raw_values": sorted({s["input_rate_raw"] for s in out}),
        "in_central25": sum(s["in_central25"] for s in out),
        "within_480m_of_edge": sum(s["edge_distance_m"] <= 480 for s in out),
    }
    for s in out:
        summary["by_type"][s["type"]] = summary["by_type"].get(s["type"], 0) + 1
        summary["by_behaviour"][s["behaviour"]] = (
            summary["by_behaviour"].get(s["behaviour"], 0) + 1
        )
    summary["semantics"] = (
        "natural source per water step: drains stored depth above max(target, terrain) within "
        "input_radius (capped by input_rate and half the excess), fills cells whose terrain is "
        "below target within output_radius (capped by output_rate and half the deficit); "
        "radius = sqrt(rate)*0.4+10 m; rates in raw 1/64 m depth units per step. m_flow is the "
        "last step's added amount, reset every step: a counter, not discharge"
    )
    return summary, out


def measure_channels(height, depth, seaconn):
    """Channel = startup water (depth >= CHANNEL_MIN_DEPTH) outside every open-water disk.

    Open water: the morphological opening of the wet mask by a disk of BODY_RADIUS
    cells (all wet nodes covered by some fully-wet disk of that radius), plus wet
    nodes within 2 nodes of it whose bank distance is <= 2.5 nodes. Channel
    components are 8-connected; width is sampled on the ridge (local maxima) of
    the Euclidean distance from each wet node to the nearest node below the depth
    threshold: width_cells = 2 * EDT - 1, so a one-node-wide channel is 16 m.
    """
    wet = depth >= CHANNEL_MIN_DEPTH
    edt = ndimage.distance_transform_edt(wet)
    centers = edt >= BODY_RADIUS + 0.5
    body = (
        wet & (ndimage.distance_transform_edt(~centers) <= BODY_RADIUS)
        if centers.any()
        else np.zeros_like(wet)
    )
    if body.any():  # shoreline nodes the discrete disk misses belong to the open water
        body |= wet & (edt <= 2.5) & ndimage.binary_dilation(body, iterations=2)
    chan = wet & ~body
    lab, n = ndimage.label(chan, structure=np.ones((3, 3)))
    ridge = chan & (edt >= ndimage.maximum_filter(edt * chan, size=3) - 1e-6)
    surface = height + depth
    body_near = ndimage.binary_dilation(body, iterations=1)
    sea_near = ndimage.binary_dilation(seaconn, iterations=1)
    comps = []
    for k, sl in enumerate(ndimage.find_objects(lab), start=1):
        m = lab[sl] == k
        cells = int(m.sum())
        if cells < 4:
            continue
        r = ridge[sl] & m
        wd = (2 * edt[sl][r] - 1) * CELL_M
        dp = depth[sl][r]
        su = surface[sl][r]
        zz, xx = np.nonzero(m)
        cz = (zz + sl[0].start - 540) * CELL_M
        cx = (xx + sl[1].start - 540) * CELL_M
        comps.append(
            {
                "id": k,
                "cells": cells,
                "area_km2": km2(cells),
                "ridge_samples": int(r.sum()),
                "ridge_length_m": int(r.sum() * CELL_M),
                "width_m": stats(wd, 1),
                "depth_m": stats(dp, 2),
                "surface_m": {
                    "p5": round(float(np.percentile(su, 5)), 2),
                    "p95": round(float(np.percentile(su, 95)), 2),
                },
                "joins_open_water": bool((body_near[sl] & m).any()),
                "joins_sea": bool((sea_near[sl] & m).any()),
                "central25_share": round(
                    float(((np.abs(cx) <= C25) & (np.abs(cz) <= C25)).mean()), 3
                ),
                "bbox_m": [
                    round(float(cx.min())),
                    round(float(cz.min())),
                    round(float(cx.max())),
                    round(float(cz.max())),
                ],
            }
        )
    comps.sort(key=lambda c: -c["cells"])
    allr = ridge & chan
    summary = {
        "count": len(comps),
        "dropped_lt4_cells": int(n - len(comps)),
        "channel_km2": km2(chan.sum()),
        "open_water_km2": km2(body.sum()),
        "ridge_width_m_all": stats((2 * edt[allr] - 1) * CELL_M, 1)
        if allr.any()
        else None,
        "ridge_depth_m_all": stats(depth[allr]) if allr.any() else None,
        "ridge_width_hist_cells": {
            str(b): int(c)
            for b, c in zip(
                *np.unique(
                    np.minimum(np.rint(2 * edt[allr] - 1).astype(int), 13),
                    return_counts=True,
                )
            )
        }
        if allr.any()
        else {},
    }
    return summary, comps[:40], lab, body, chan


def measure_terrain(height, depth, start_mask):
    gz, gx = np.gradient(height, CELL_M)
    slope = np.hypot(gx, gz) * 100
    dry = depth == 0
    out = {
        "full_map": relief(height, np.ones_like(dry)),
        "central25": relief(height, CENTRAL16),
        "central25_dry_land": relief(height, CENTRAL16 & dry),
    }
    sl = {}
    for name, m in (
        ("central25", CENTRAL16 & dry),
        ("start_tile", start_mask & dry),
        ("full_map", dry),
    ):
        v = slope[m]
        sl[name] = {
            "dry_km2": km2(m.sum()),
            **{
                f"share_lt_{t}pct": round(float((v < t).mean()), 4) if len(v) else None
                for t in SLOPE_THRESHOLDS
            },
            "slope_pct": stats(v, 2),
        }
    out["dry_land_slope"] = sl
    out["slope_definition"] = (
        "central-difference gradient of TerrainManager raw heights/64 on "
        "the 16 m node grid; dry = stored water depth exactly 0"
    )
    return out, slope


def measure_trees(t, start):
    created = (t["flags"] & 3) == 1
    x, z = t["x"][created], t["z"][created]
    names = t["names"]
    pf = t["prefab"][created]
    sx, sz = start
    inc = (np.abs(x) <= C25) & (np.abs(z) <= C25)
    x0, z0 = -C25 + sx * TILE_M, -C25 + sz * TILE_M
    inst = (x >= x0) & (x < x0 + TILE_M) & (z >= z0) & (z < z0 + TILE_M)
    out = {
        "total": int(created.sum()),
        "central25": int(inc.sum()),
        "start_tile": int(inst.sum()),
        "density_per_km2": {
            "full": round(created.sum() / 17.28**2, 1),
            "central25": round(inc.sum() / 9.6**2, 1),
            "start_tile": round(inst.sum() / 1.92**2, 1),
        },
        "position_range_m": [
            round(float(np.abs(x).max()), 1),
            round(float(np.abs(z).max()), 1),
        ]
        if len(x)
        else None,
        "species": {},
    }
    counts = np.bincount(pf, minlength=len(names))
    for i in np.argsort(-counts):
        if counts[i]:
            out["species"][names[i] if i < len(names) and names[i] else f"#{i}"] = int(
                counts[i]
            )
    out["species_count"] = len(out["species"])
    if inc.sum() >= 10:
        pts = np.column_stack([x[inc], z[inc]])
        d, _ = cKDTree(pts).query(pts, k=2)
        nn = d[:, 1]
        expected = 0.5 / math.sqrt(len(pts) / (2 * C25) ** 2)
        g = np.zeros((96, 96), int)  # 100 m cells over central25
        np.add.at(
            g,
            (
                np.clip(((pts[:, 1] + C25) // 100).astype(int), 0, 95),
                np.clip(((pts[:, 0] + C25) // 100).astype(int), 0, 95),
            ),
            1,
        )
        top = np.sort(g.ravel())[::-1]
        out["clustering_central25"] = {
            "nn_distance_m": stats(nn, 1),
            "clark_evans_R": round(float(nn.mean() / expected), 3),
            "occupied_100m_cell_share": round(float((g > 0).mean()), 4),
            "trees_in_densest_10pct_cells_share": round(
                float(top[: len(top) // 10].sum() / top.sum()), 3
            ),
            "note": "Clark-Evans R < 1 clustered, ~1 random, > 1 regular; no edge correction",
        }
    return out


def measure_resources(g, area, start, land512):
    sx, sz = start
    st = (TILE[:, None] == sz + 2) & (TILE[None, :] == sx + 2)
    out = {}
    for k in ("ore", "oil", "sand", "fertility", "forest"):
        grid = g[k]
        pos = grid > 0
        out[k] = {
            "full_km2": round(float(pos.sum() * CELL_KM2), 2),
            "central25_km2": round(float((pos & CENTRAL).sum() * CELL_KM2), 2),
            "central25_share_of_area": round(
                float((pos & CENTRAL).sum() / CENTRAL.sum()), 4
            ),
            "central25_share_of_dry_land": round(
                float(
                    (pos & CENTRAL & land512).sum() / max((CENTRAL & land512).sum(), 1)
                ),
                4,
            ),
            "start_tile_km2": round(float((pos & st).sum() * CELL_KM2), 3),
            "start_tile_share": round(float((pos & st).sum() / st.sum()), 4),
            "central25_mean_intensity": round(float(grid[CENTRAL & pos].mean()), 1)
            if (pos & CENTRAL).any()
            else None,
        }
    if area is not None:
        out["area_final_central25_raw"] = {
            k[5:]: int(v[2:7, 2:7].sum())
            for k, v in area.items()
            if k.startswith("final")
        }
    out["grid_note"] = "NaturalResourceManager 512x512 cells of 33.75 m; values 0..255"
    return out


def measure_network(data, v, start):
    try:
        net = parse_network(data, v)
        issues = check_network(net)
        if issues and 221 <= v < 115000:
            alt = parse_network(data, v, "uint")
            if not check_network(alt):
                net, issues = alt, []
    except Exception as e:  # unsupported layout: explicit unknown
        return {"status": "unknown", "reason": f"{type(e).__name__}: {e}"}, None
    if issues:
        return {
            "status": "unknown",
            "reason": "consistency checks failed",
            "issues": issues[:10],
        }, None
    names = net["names"]
    by = {nd["id"]: nd for nd in net["nodes"]}

    def cls(e):
        return net_class(names[e["info"]] if e.get("info", -1) < len(names) else None)

    seg_by_class, length_by_class, prefabs = {}, {}, {}
    sx, sz = start
    central_segments = 0
    for s in net["segments"]:
        c = cls(s)
        pa, pb = by[s["a"]]["pos"], by[s["b"]]["pos"]
        chord = math.hypot(pa[0] - pb[0], pa[2] - pb[2])
        seg_by_class[c] = seg_by_class.get(c, 0) + 1
        length_by_class[c] = length_by_class.get(c, 0) + chord
        nm = names[s["info"]] if s.get("info", -1) < len(names) else None
        prefabs[nm] = prefabs.get(nm, 0) + 1
        mid = ((pa[0] + pb[0]) / 2, (pa[2] + pb[2]) / 2)
        central_segments += abs(mid[0]) <= C25 and abs(mid[1]) <= C25
    outside = {}
    for nd in net["nodes"]:
        if nd["flags"] & 0x400:
            c = cls(nd)
            outside[c] = outside.get(c, 0) + 1
    # connected components over segments
    parent = {nd["id"]: nd["id"] for nd in net["nodes"]}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for s in net["segments"]:
        parent[find(s["a"])] = find(s["b"])
    roots = {find(i) for i in parent}
    deg = (
        np.bincount([len(nd["segs"]) for nd in net["nodes"]], minlength=1)
        if net["nodes"]
        else []
    )
    out = {
        "status": "decoded",
        "nodes": len(net["nodes"]),
        "segments": len(net["segments"]),
        "lanes_allocated": net["lanes"],
        "components": len(roots),
        "node_degree_hist": {str(i): int(c) for i, c in enumerate(deg) if c},
        "segments_by_class": seg_by_class,
        "chord_length_km_by_class": {
            k: round(x / 1000, 2) for k, x in length_by_class.items()
        },
        "outside_nodes_by_class": outside,
        "segments_with_midpoint_in_central25": int(central_segments),
        "segment_prefabs": dict(sorted(prefabs.items(), key=lambda kv: -kv[1])),
        "problem_array_variant": net["problem_variant"],
        "consistency": "all segment endpoints exist and list the segment; all node segment "
        "refs exist; prefab indices within the NetInfo name table",
        "class_rule": "keyword match on NetInfo prefab name (net_class)",
    }
    return out, net


# ---------------------------------------------------------------- images
def hillshade(h):
    gz, gx = np.gradient(h, CELL_M)
    s = (-gx - gz) / np.sqrt(2)
    sh = 0.55 + 0.45 * np.tanh(s * 1.5)
    lo, hi = np.percentile(h, [1, 99])
    tint = np.clip((h - lo) / max(hi - lo, 1), 0, 1)
    rgb = (
        np.stack([0.55 + 0.35 * tint, 0.6 + 0.25 * tint, 0.45 + 0.2 * tint], -1)
        * sh[..., None]
    )
    return rgb


def to_img(rgb, size=540):
    im = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    return im.resize((size, size), Image.Resampling.BILINEAR)


def save_small(im, path, colors=96):
    im.quantize(colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(
        path, optimize=True
    )


def px(x, size=540):
    return (x / CELL_M + 540) * size / HN


def draw_frame(d, start, size=540):
    a, b = px(-C25, size), px(C25, size)
    d.rectangle([a, a, b, b], outline=(255, 255, 255))
    sx, sz = start
    x0, z0 = -C25 + sx * TILE_M, -C25 + sz * TILE_M
    d.rectangle(
        [px(x0, size), px(z0, size), px(x0 + TILE_M, size), px(z0 + TILE_M, size)],
        outline=(255, 220, 0),
        width=2,
    )


def overview_png(path, height, depth, seaconn, sources, net, start):
    rgb = hillshade(height)
    wet = depth > 0
    dn = np.clip(depth / 8.0, 0, 1)[..., None]
    water = np.where(seaconn[..., None], [0.1, 0.25, 0.6], [0.15, 0.45, 0.9])
    rgb = np.where(
        wet[..., None], (1 - 0.5 - 0.5 * dn) * rgb + (0.5 + 0.5 * dn) * water, rgb
    )
    im = to_img(rgb)
    d = ImageDraw.Draw(im)
    if net is not None:
        by = {nd["id"]: nd for nd in net["nodes"]}
        col = {
            "road": (60, 60, 60),
            "rail": (150, 40, 150),
            "ship": (0, 200, 200),
            "air": (230, 230, 230),
            "utility": (230, 140, 0),
            "other": (120, 120, 0),
        }
        for s in net["segments"]:
            c = net_class(
                net["names"][s["info"]]
                if s.get("info", -1) < len(net["names"])
                else None
            )
            pa, pb = by[s["a"]]["pos"], by[s["b"]]["pos"]
            d.line([px(pa[0]), px(pa[2]), px(pb[0]), px(pb[2])], fill=col[c], width=2)
        for nd in net["nodes"]:
            if nd["flags"] & 0x400:
                x, z = px(nd["pos"][0]), px(nd["pos"][2])
                d.rectangle([x - 3, z - 3, x + 3, z + 3], outline=(255, 255, 255))
    for s in sources:
        x, z = px(s["input_position"][0]), px(s["input_position"][2])
        d.ellipse([x - 4, z - 4, x + 4, z + 4], outline=(255, 0, 0), width=2)
    draw_frame(d, start)
    save_small(im, path)


def channels_png(path, height, chan_lab, body, chan, depth, start):
    edt = ndimage.distance_transform_edt(depth >= CHANNEL_MIN_DEPTH)
    ridge = chan & (edt >= ndimage.maximum_filter(edt * chan, size=3) - 1e-6)
    rgb = hillshade(height) * 0.8
    if ridge.any():  # colour every channel node by its nearest ridge sample's width
        _, (iz, ix) = ndimage.distance_transform_edt(~ridge, return_indices=True)
        edt = edt[iz, ix]
    width = np.clip((2 * edt - 1) / 12.0, 0, 1)
    ccol = np.stack([1 - width, 0.3 + 0.4 * width, width], -1)
    rgb = np.where(body[..., None], [0.2, 0.3, 0.55], rgb)
    rgb = np.where(chan[..., None], ccol, rgb)
    im = to_img(rgb, 1081)  # native resolution so single-node channels stay visible
    draw_frame(ImageDraw.Draw(im), start, 1081)
    save_small(im, path, 64)


def trees_png(path, height, depth, t, start):
    created = (t["flags"] & 3) == 1
    g = np.zeros((HN, HN))
    ix = np.clip(np.floor(t["x"][created] / CELL_M + 540 + 0.5).astype(int), 0, HN - 1)
    iz = np.clip(np.floor(t["z"][created] / CELL_M + 540 + 0.5).astype(int), 0, HN - 1)
    np.add.at(g, (iz, ix), 1)
    g = ndimage.uniform_filter(g, 4) * 16  # trees per 64 m square
    dn = np.clip(g / 20.0, 0, 1)[..., None]
    rgb = hillshade(height) * (1 - dn) + np.array([0.05, 0.4, 0.1]) * dn
    rgb = np.where(
        (depth > 0)[..., None], 0.5 * rgb + 0.5 * np.array([0.2, 0.4, 0.85]), rgb
    )
    im = to_img(rgb)
    draw_frame(ImageDraw.Draw(im), start)
    save_small(im, path)


def resources_png(path, g, start):
    rgb = np.full((512, 512, 3), 0.85)
    for k, c in (
        ("fertility", [0.75, 0.6, 0.2]),
        ("forest", [0.15, 0.55, 0.15]),
        ("sand", [0.95, 0.85, 0.5]),
        ("oil", [0.1, 0.1, 0.1]),
        ("ore", [0.55, 0.35, 0.65]),
    ):
        m = g[k] > 0
        a = (g[k] / 255.0)[..., None]
        rgb = np.where(m[..., None], (1 - a) * rgb + a * np.array(c), rgb)
    rgb = np.where((g["water"] > 0)[..., None], [0.3, 0.5, 0.9], rgb)
    im = Image.fromarray((rgb * 255).astype(np.uint8)).resize(
        (540, 540), Image.Resampling.NEAREST
    )
    draw_frame(ImageDraw.Draw(im), start)
    save_small(im, path)


# ---------------------------------------------------------------- per package
def slug_of(path):
    return Path(path).stem.replace("%002E", ".").replace(" ", "-").lower()


def theme_reference(ref, workshop_root):
    if not ref:
        return {"mapThemeRef": ref, "resolved": "none (built-in environment theme)"}
    out = {"mapThemeRef": ref}
    head = ref.split(".", 1)[0]
    if workshop_root and head.isdigit():
        d = Path(workshop_root) / head
        out["workshop_dir_present"] = d.is_dir()
        if d.is_dir():
            for f in sorted(d.glob("*.crp")):
                _, assets = read_package(f.read_bytes())
                th = [a for a in assets if a["kind"] == 106]
                if th:
                    meta, _ = parse_meta(th[0]["payload"])
                    out["resolved"] = {
                        "file": f.name,
                        "theme_name": meta.get("name"),
                        "environment": meta.get("environment"),
                    }
    out.setdefault("resolved", "not resolved locally")
    return out


def anatomy(path, out_dir, workshop_root, contract, prepared_root=None):
    raw = Path(path).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    pkg, assets = read_package(raw)
    slug = slug_of(path)
    rec = {
        "slug": slug,
        "file": Path(path).name,
        "sha256": sha,
        "bytes": len(raw),
        "package": {
            k: pkg[k] for k in ("format", "name", "version", "main", "trailing_bytes")
        },
        "assets": [
            {
                "name": a["name"],
                "kind": a["kind"],
                "kind_name": KIND_NAMES.get(a["kind"], "other"),
                "bytes": a["bytes"],
                "md5_ok": a["md5_ok"],
            }
            for a in assets
        ],
    }
    if not all(a["md5_ok"] for a in assets):
        rec["warnings"] = ["asset MD5 mismatch"]
    if slug in contract:
        exp = contract[slug]
        rec["contract"] = {
            "expected_sha256": exp["sha"],
            "expected_bytes": exp["bytes"],
            "match": sha == exp["sha"] and len(raw) == exp["bytes"],
        }
        if not rec["contract"]["match"]:
            raise ValueError(
                f"{slug}: hash does not match the --contract shipping hash"
            )
    kinds = {a["kind"] for a in assets}
    meta_assets = [a for a in assets if a["kind"] == 100]
    themes = [a for a in assets if a["kind"] == 106]
    sims = [a for a in assets if a["kind"] == 52]
    if themes and not meta_assets:
        meta, problems = parse_meta(themes[0]["payload"])
        rec["role"] = "map_theme"
        keep = [
            "name",
            "environment",
            "mapThemeRef",
            "timeStamp",
            "latitude",
            "longitude",
            "minTemperatureDay",
            "maxTemperatureDay",
            "rainProbabilityDay",
            "fogProbabilityDay",
            "northernLightsProbability",
            "grassDetailEnabled",
            "fertileDetailEnabled",
            "rocksDetailEnabled",
            "waterClean",
            "waterDirty",
            "waterUnder",
        ]
        rec["theme"] = {k: meta.get(k) for k in keep if k in meta}
        rec["theme"]["texture_assets"] = sum(a["kind"] == 3 for a in assets)
        rec["theme"]["texture_fields_set"] = sorted(
            k
            for k, val in meta.items()
            if k.endswith(("Asset", "Diffuse", "Normal", "Texture", "Palette")) and val
        )
        rec["theme"]["metadata_problems"] = problems
        rec["terrain"] = rec["water"] = rec["network"] = (
            "absent: a map theme carries no terrain"
        )
        return rec
    if not (meta_assets and sims):
        rec["role"] = "not_a_map"
        rec["reason"] = (
            (
                f"asset kinds {sorted(kinds)}; a kind-52 payload without kind-100 "
                "MapMetaData is not a map (e.g. a LUT/asset)"
            )
            if sims
            else f"asset kinds {sorted(kinds)}"
        )
        return rec
    rec["role"] = "map"
    meta, problems = parse_meta(meta_assets[0]["payload"])
    data = sims[0]["payload"]
    v = data_version(data)
    rec["data_version"] = v
    keys = [
        "mapName",
        "environment",
        "mapThemeRef",
        "builtin",
        "buildableArea",
        "maxResourceAmount",
        "oreAmount",
        "oilAmount",
        "forestAmount",
        "fertileLandAmount",
        "waterAmount",
        "incomingRoads",
        "outgoingRoads",
        "incomingTrainTracks",
        "outgoingTrainTracks",
        "incomingShipPath",
        "outgoingShipPath",
        "incomingPlanePath",
        "outgoingPlanePath",
        "timeStamp",
    ]
    missing = "unknown (not decoded)" if problems else None  # null fields carry no name
    rec["metadata"] = {k: meta.get(k, missing) for k in keys + ["mods"]}
    rec["metadata_problems"] = problems
    rec["theme"] = {
        "environment": meta.get("environment"),
        **theme_reference(meta.get("mapThemeRef"), workshop_root),
    }
    area_count, start_index = parse_start_tile(data, v)
    start = (start_index % 5, start_index // 5)
    rec["start_tile"] = {
        "index": start_index,
        "x": start[0],
        "z": start[1],
        "unlocked_area_count": area_count,
    }
    start16 = tile_mask16(*start)
    height = parse_terrain(data)
    w = parse_water(data, v)
    depth = w["depth"]
    checks = {
        "terrain_m_range": [float(height.min()), float(height.max())],
        "water_section_end": w["end"],
        "water_next_object_tag": w["next_tag"],
        "water_sources_decoded": len(w["sources"]),
    }
    rec["terrain"], _ = measure_terrain(height, depth, start16)
    rec["terrain"]["metadata_buildableArea"] = meta.get("buildableArea")
    rec["water"], seaconn = measure_water(height, w, start16)
    chs, comps, chan_lab, body, chan = measure_channels(height, depth, seaconn)
    rec["channels"] = {
        "definition": measure_channels.__doc__.strip().replace("\n    ", " "),
        "min_depth_m": CHANNEL_MIN_DEPTH,
        "open_water_disk_radius_cells": BODY_RADIUS,
        **chs,
        "largest": comps,
    }
    rec["water_sources"], rec["water_source_list"] = measure_sources(
        height, w, start, chan_lab
    )
    g, area = parse_resources(data, v)
    land512 = g["water"] == 0
    rec["resources"] = measure_resources(g, area, start, land512)
    t = parse_trees(data, v)
    rec["trees"] = measure_trees(t, start)
    tx, tz = t["x"], t["z"]
    checks["tree_positions_within_map"] = bool(
        len(tx) == 0 or (np.abs(tx).max() <= HALF + 1 and np.abs(tz).max() <= HALF + 1)
    )
    checks["tree_prefab_index_within_names"] = bool(
        len(t["prefab"]) == 0 or t["prefab"].max() < max(len(t["names"]), 1)
    )
    rec["network"], net = measure_network(data, v, start)
    rec["metadata_vs_network"] = {
        "metadata_in_out": {k: meta.get(k) for k in keys[11:19]},
        "outside_nodes_by_class": rec["network"].get(
            "outside_nodes_by_class", "unknown"
        ),
        "note": "metadata counts are what the editor stored; one two-way outside node can "
        "count as both incoming and outgoing, so they need not equal node counts",
    }
    rec["checks"] = checks
    if prepared_root:
        x = cross_check_prepared(
            slug, height, depth, w, net, start_index, prepared_root
        )
        if x:
            rec["prepared_cross_check"] = x
    d = out_dir / "maps" / slug
    d.mkdir(parents=True, exist_ok=True)
    overview_png(
        d / "overview.png", height, depth, seaconn, rec["water_source_list"], net, start
    )
    channels_png(d / "channels.png", height, chan_lab, body, chan, depth, start)
    trees_png(d / "trees.png", height, depth, t, start)
    resources_png(d / "resources.png", g, start)
    rec["images"] = sorted(p.name for p in d.glob("*.png"))
    return rec


def cross_check_prepared(slug, height, depth, w, net, start_index, root):
    """Compare decoded fields with the generator inputs that produced the package."""
    d = Path(root) / slug.removeprefix("pl857-")
    if not d.is_dir():
        return None
    out = {"prepared_dir": d.name}
    terrain = np.fromfile(d / "terrain.u16", dtype="<u2").reshape(HN, HN)
    water = np.fromfile(d / "water.u16", dtype="<u2").reshape(HN, HN)
    out["terrain_u16_identical"] = bool((np.rint(height * 64) == terrain).all())
    out["water_u16_identical"] = bool((np.rint(depth * 64) == water).all())
    h = json.loads((d / "hydrology.json").read_text())
    src = h["sources"]
    ok = len(src) == len(w["sources"])
    for a, b in zip(src, w["sources"]):
        ok &= (
            abs(a["position"][0] - b["input"][0]) < 1e-3
            and abs(a["position"][2] - b["input"][2]) < 1e-3
        )
        ok &= b["target_raw"] == math.floor(a["target"] * 64 + 0.5)
        ok &= b["input_rate"] == math.floor(a["capacity"] * 65535 + 0.5)
        ok &= b["output_rate"] == math.floor(
            a.get("output_capacity", a["capacity"]) * 65535 + 0.5
        )
    out["sources_identical"] = bool(ok)
    out["sea_level_identical"] = abs(h["sea_level_m"] - w["sea_level"]) < 1e-4
    out["start_tile_identical"] = h["start_tile"] == start_index
    if net is not None:
        by = {nd["id"]: nd["pos"] for nd in net["nodes"]}
        out["node_positions_identical"] = len(by) == len(h["node_positions"]) and all(
            int(k) in by and max(abs(p - q) for p, q in zip(by[int(k)], v)) < 0.01
            for k, v in h["node_positions"].items()
        )
    return out


def compact(rec):
    if rec["role"] != "map":
        return {
            k: rec.get(k)
            for k in ("slug", "file", "sha256", "role", "theme", "reason")
            if k in rec
        }
    n = rec["network"]
    return {
        "slug": rec["slug"],
        "role": "map",
        "sha256": rec["sha256"],
        "data_version": rec["data_version"],
        "environment": rec["metadata"]["environment"],
        "theme": rec["theme"].get("resolved"),
        "start_tile": [rec["start_tile"]["x"], rec["start_tile"]["z"]],
        "water_sources": rec["water_sources"]["count"],
        "source_rate_raw_sum": rec["water_sources"]["input_rate_raw_sum"],
        "sea_level_m": rec["water"]["sea_level_m"],
        "relief_full_m": rec["terrain"]["full_map"]["relief_p1_p99_m"],
        "relief_central25_m": rec["terrain"]["central25"]["relief_p1_p99_m"],
        "central25_dry_km2": rec["terrain"]["dry_land_slope"]["central25"]["dry_km2"],
        "central25_dry_share_lt_6pct": rec["terrain"]["dry_land_slope"]["central25"][
            "share_lt_6pct"
        ],
        "buildableArea_meta": rec["metadata"]["buildableArea"],
        "wet_km2_full": rec["water"]["startup_coverage"]["full"]["depth_gt_0m"]["km2"],
        "wet_share_central25": rec["water"]["startup_coverage"]["central25"][
            "depth_gt_0m"
        ]["share"],
        "channels": rec["channels"]["count"],
        "channel_km2": rec["channels"]["channel_km2"],
        "channel_width_p50_m": (rec["channels"]["ridge_width_m_all"] or {}).get("p50"),
        "trees": rec["trees"]["total"],
        "tree_species": rec["trees"]["species_count"],
        "clark_evans_R": rec["trees"]
        .get("clustering_central25", {})
        .get("clark_evans_R"),
        "ore_central25_km2": rec["resources"]["ore"]["central25_km2"],
        "oil_central25_km2": rec["resources"]["oil"]["central25_km2"],
        "fertility_central25_km2": rec["resources"]["fertility"]["central25_km2"],
        "forest_central25_km2": rec["resources"]["forest"]["central25_km2"],
        "network": n["status"],
        "network_segments": n.get("segments"),
        "outside_nodes": n.get("outside_nodes_by_class"),
        "meta_in_out": rec["metadata_vs_network"]["metadata_in_out"],
    }


def active_contract(fixtures):
    """The shipping contract fixtures/active.json names, else fixtures/current.json."""
    active = fixtures / "active.json"
    if active.exists():
        return fixtures / json.loads(active.read_text())["current"]
    return fixtures / "current.json"


def load_contract(path):
    c = json.loads(Path(path).read_text())
    cases = {
        f"pl857-{case['slug']}": {
            "sha": case["shipping"]["expected_crp_sha256"],
            "bytes": case["shipping"]["expected_crp_bytes"],
        }
        for case in c["cases"]
    }
    return cases, c.get("version")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("crp", nargs="*", type=Path)
    here = Path(__file__).resolve().parent
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--contract", type=Path, default=active_contract(here.parent / "fixtures")
    )
    ap.add_argument(
        "--workshop-root",
        type=Path,
        default=Path.home()
        / "Library"
        / "Application Support"
        / "Steam"
        / "steamapps"
        / "workshop"
        / "content"
        / "255710",
    )
    ap.add_argument(
        "--prepared-root",
        type=Path,
        help="DIR/<region>/{terrain.u16,water.u16,hydrology.json} generator inputs "
        "to cross-check shipping packages against",
    )
    a = ap.parse_args()
    files = a.crp or sorted((a.out / "inputs").rglob("*.crp"))
    contract, contract_version = load_contract(a.contract)
    a.out.mkdir(parents=True, exist_ok=True)
    records, manifest = [], []
    for f in files:
        rec = anatomy(f, a.out, a.workshop_root, contract, a.prepared_root)
        d = a.out / "maps" / rec["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "metrics.json").write_text(json.dumps(rec, indent=1) + "\n")
        records.append(rec)
        manifest.append(
            {
                "slug": rec["slug"],
                "file": str(f.relative_to(a.out) if f.is_relative_to(a.out) else f),
                "sha256": rec["sha256"],
                "bytes": rec["bytes"],
                "role": rec["role"],
                "contract_match": rec.get("contract", {}).get("match"),
                "assets_md5_ok": all(x["md5_ok"] for x in rec["assets"]),
            }
        )
        print(f"{rec['slug']}: {rec['role']}", file=sys.stderr)
    tool = Path(__file__).read_bytes()
    summary = {
        "tool": "survey/craft_anatomy.py",
        "tool_sha256": hashlib.sha256(tool).hexdigest(),
        "contract": {"file": a.contract.name, "version": contract_version},
        "caveats": CAVEATS,
        "maps": [compact(r) for r in records],
    }
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    (a.out / "manifest.json").write_text(
        json.dumps({"inputs": manifest}, indent=1) + "\n"
    )


if __name__ == "__main__":
    main()
