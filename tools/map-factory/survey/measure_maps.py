"""Measure natural resources, trees and terrain placement in CS1 .crp maps.

Reads any CRP package format (4..12), locates manager sections by their shared
manager-name tag, and decodes NaturalResourceManager, TreeManager, TerrainManager,
WaterSimulation and GameAreaManager with the version gates of CS1 1.21.1-f9
(Assembly-CSharp c7f0e723...). Reusable pieces: read_any, parse_metadata,
data_version, decode, read_unique_string, parse_resources, parse_trees.

usage: python measure_maps.py MAPS_DIR OUT.json [--only NAME ...]
"""

import argparse
import glob
import json
import os
import struct
import sys

import numpy as np

RES = 512  # resource grid, 33.75 m cells
CELL = 33.75
HN = 1081  # terrain/water grid, 16 m
TREE_SLOTS = 262143  # TreeManager buffer minus slot 0
TREE_UNIT = 0.26367188  # TreeInstance.Position: m_posX * 270/1024 (game mode)


# ---------------------------------------------------------------- packaging
class Reader:
    def __init__(self, data, pos=0):
        self.data, self.pos = data, pos

    def take(self, n):
        v = self.data[self.pos : self.pos + n]
        if len(v) != n:
            raise ValueError("read past end")
        self.pos += n
        return v

    def number(self, fmt):
        return struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))[0]

    def string(self):  # .NET BinaryReader 7-bit length prefix, UTF-8
        size = 0
        for shift in range(0, 35, 7):
            b = self.number("B")
            size |= (b & 127) << shift
            if b < 128:
                return self.take(size).decode("utf8")
        raise ValueError("bad string length")


def read_any(data):
    """CRP index table; identical layout for package formats >= 2."""
    r = Reader(data)
    if r.take(4) != b"CRAP":
        raise ValueError("not a CRP")
    fmt = r.number("H")
    pkg = {"format": fmt, "name": r.string(), "author_encrypted": r.string()}
    pkg["version"], pkg["main"] = r.number("I"), r.string()
    count, start = r.number("i"), r.number("q")
    assets = []
    for _ in range(count):
        name, _checksum, kind = r.string(), r.string(), r.number("i")
        off, size = r.number("q"), r.number("q")
        assets.append(
            {
                "name": name,
                "kind": kind,
                "payload": data[start + off : start + off + size],
            }
        )
    return pkg, assets


def _meta_value(r, t):
    if t.endswith("[]"):
        n = r.number("i")
        return [_meta_value(r, t[:-2]) for _ in range(n)]
    if t in (
        "System.String",
        "System.DateTime",
        "ColossalFramework.Packaging.Package+Asset",
    ):
        return r.string()
    if t == "ModInfo":
        return (r.string(), r.number("Q"))
    return r.number(
        {
            "System.Boolean": "B",
            "System.Int32": "i",
            "System.UInt32": "I",
            "System.Single": "f",
        }[t]
    )


def parse_metadata(payload):
    """MapMetaData as written by ColossalFramework.Packaging (little-endian)."""
    r = Reader(payload)
    if r.number("B") != 0:
        raise ValueError("null metadata")
    typ = r.string()
    r.string()
    n = r.number("i")
    out = {"_type": typ.split(",")[0]}
    for _ in range(n):
        if r.number("B"):
            continue
        t, name = r.string().split(",")[0], r.string()
        out[name] = _meta_value(r, t)
    return out


def data_version(p):
    """DataSerializer.Deserialize header: two big-endian UInt16."""
    hi, lo = struct.unpack_from(">HH", p, 0)
    if lo <= 322 and hi <= 6:
        return lo
    if hi & 0x8000:
        return ((hi << 16) | lo) & 0x7FFFFFFF
    return (hi << 16) | lo


# ---------------------------------------------------------------- encoding
def decode(data, count, offset, width, signed=False):
    """ColossalFramework EncodedArray (Byte/UShort/Short/UInt), vectorized per run.

    Codes >= 128 repeat the last delta (code-127 values). Codes below the
    literal limit (128 for Byte, 64 otherwise) carry code+1 (Byte) or
    (code&63)+1 full big-endian values. For width > 1, codes 64..127 carry
    (code&63)+1 signed half-width delta corrections.
    """
    out = np.empty(count, dtype=np.int64)
    mask = (1 << (8 * width)) - 1
    prev = delta = i = 0
    while i < count:
        code = data[offset]
        offset += 1
        if code >= 128:
            n = code - 127
            vals = prev + delta * np.arange(1, n + 1, dtype=np.int64)
        elif width == 1 or code < 64:
            n = code + 1 if width == 1 else (code & 63) + 1
            vals = np.frombuffer(
                data, dtype=f">u{width}", count=n, offset=offset
            ).astype(np.int64)
            offset += n * width
            before = prev if n == 1 else int(vals[-2])
            delta = (int(vals[-1]) - before) & mask
        else:
            n = (code & 63) + 1
            h = width // 2
            ex = np.frombuffer(data, dtype=f">i{h}", count=n, offset=offset).astype(
                np.int64
            )
            offset += n * h
            deltas = delta + np.cumsum(ex)
            vals = prev + np.cumsum(deltas)
            delta = int(deltas[-1]) & mask
        if i + n > count:
            raise ValueError("run exceeds array")
        vals &= mask
        out[i : i + n] = vals
        prev = int(vals[-1])
        i += n
    if signed:
        out = np.where(out >= 1 << (8 * width - 1), out - (1 << (8 * width)), out)
    return out, offset


def read_unique_string(data, offset):
    """DataSerializer.WriteUniqueString: 0xFF = null; else 24-bit header."""
    if data[offset] == 255:
        return None, offset + 1
    head = int.from_bytes(data[offset : offset + 3], "big")
    offset += 3
    c, chars = 0x80, []
    if head & 0x800000:
        for _ in range(head & 0x7FFFFF):
            c = (c + data[offset]) & 0xFF
            chars.append(chr(c))
            offset += 1
    else:
        for _ in range(head):
            c = (c + int.from_bytes(data[offset : offset + 2], "big")) & 0xFFFF
            chars.append(chr(c))
            offset += 2
    return "".join(chars), offset


def manager_tag(name):
    out, prev = bytearray([254]), 128
    out.extend((0x800000 | len(name)).to_bytes(3, "big"))
    for ch in name.encode("latin1"):
        out.append((ch - prev) & 255)
        prev = ch
    return bytes(out)


def section(data, name):
    tag = manager_tag(name)
    pos = data.find(tag)
    if pos < 0:
        raise ValueError(f"{name} tag not found")
    if data.find(tag, pos + 1) >= 0:
        raise ValueError(f"{name} tag not unique")
    return pos + len(tag)


# ---------------------------------------------------------------- managers
def parse_resources(data, v):
    """NaturalResourceManager.Data.Deserialize with its version gates."""
    o = section(data, "NaturalResourceManager")
    N = RES * RES
    g = {}
    g["ore"], o = decode(data, N, o, 1)
    if v < 22:
        _, o = decode(data, int((g["ore"] == 0).sum()), o, 1)
    g["oil"], o = decode(data, N, o, 1)
    if v < 22:
        _, o = decode(data, int((g["oil"] == 0).sum()), o, 1)
    g["sand"], o = decode(data, N, o, 1) if v >= 27 else (np.zeros(N, np.int64), o)
    g["forest"], o = decode(data, N, o, 1)
    tree, o = decode(data, int((g["forest"] != 0).sum()), o, 1)
    fert, o = decode(data, int((g["forest"] == 0).sum()), o, 1)
    g["tree"] = np.zeros(N, np.int64)
    g["tree"][g["forest"] != 0] = tree
    g["fertility"] = np.zeros(N, np.int64)
    g["fertility"][g["forest"] == 0] = fert
    g["water"], o = decode(data, N, o, 1) if v >= 22 else (np.zeros(N, np.int64), o)
    g["shore"], o = decode(data, N, o, 1) if v >= 223 else (g["water"].copy(), o)
    g["pollution"], o = decode(data, N, o, 1)
    if v >= 265:
        g["burned"], o = decode(data, N, o, 1)
        g["destroyed"], o = decode(data, N, o, 1)
    if v < 116:
        _, o = decode(data, int(((g["water"] != 0) | (v < 22)).sum()), o, 1)
    area = None
    if v >= 111:
        k = 10 if v >= 125 else 8
        a, o = decode(data, 81 * k, o, 4)
        names = [
            "tempOre",
            "tempOil",
            "tempForest",
            "tempFertility",
            "finalOre",
            "finalOil",
            "finalForest",
            "finalFertility",
            "tempWater",
            "finalWater",
        ][:k]
        area = {n: a[i * 81 : (i + 1) * 81].reshape(9, 9) for i, n in enumerate(names)}
    for k_ in list(g):
        g[k_] = g[k_].reshape(RES, RES)  # [z, x]
    return g, area


def parse_trees(data, v):
    """TreeManager.Data: flags, PrefabCollection<TreeInfo>, posX, posZ."""
    o = section(data, "TreeManager")
    flags, o = decode(data, TREE_SLOTS, o, 2)
    used = flags != 0
    n = int(used.sum())
    idx, o = decode(data, n, o, 2)
    count = int.from_bytes(data[o : o + 2], "big")
    o += 2
    names = []
    for _ in range(count):
        s, o = read_unique_string(data, o)
        names.append(s)
    px, o = decode(data, n, o, 2, signed=True)
    pz, o = decode(data, n, o, 2, signed=True)
    burning = int.from_bytes(data[o : o + 3], "big") if v >= 266 else 0
    return {
        "flags": flags[used],
        "prefab": idx,
        "names": names,
        "x": px * TREE_UNIT,
        "z": pz * TREE_UNIT,
        "burning": burning,
    }


def parse_terrain(data):
    o = section(data, "TerrainManager")
    raw, _ = decode(data, HN * HN, o, 2)
    return raw.reshape(HN, HN) / 64.0


def parse_water(data):
    o = section(data, "WaterSimulation")
    depth, _ = decode(data, HN * HN, o, 2)
    return depth.reshape(HN, HN) / 64.0


def parse_start_tile(data, v):
    o = section(data, "GameAreaManager")
    area_count = data[o]
    start = data[o + 1] if v >= 137 else 12
    return int(area_count), int(start)


# ---------------------------------------------------------------- statistics
TILE = np.minimum(
    8, (np.arange(RES) * 9) // 512
)  # NaturalResourceManager.SimulationStepImpl2
CENTRAL = (
    (TILE[:, None] >= 2)
    & (TILE[:, None] <= 6)
    & (TILE[None, :] >= 2)
    & (TILE[None, :] <= 6)
)
CELL_KM2 = CELL * CELL / 1e6


def tile_sums(grid):
    return np.bincount(
        (TILE[:, None] * 9 + TILE[None, :]).ravel(), weights=grid.ravel(), minlength=81
    ).reshape(9, 9)


def patches(mask):
    from scipy import ndimage

    lab, n = ndimage.label(mask)
    if n == 0:
        return {"count": 0}
    sizes = np.bincount(lab.ravel())[1:] * CELL_KM2
    return {
        "count": int(n),
        "median_km2": round(float(np.median(sizes)), 4),
        "p90_km2": round(float(np.percentile(sizes, 90)), 4),
        "max_km2": round(float(sizes.max()), 3),
        "n_ge_0p1km2": int((sizes >= 0.1).sum()),
    }


def hist(values):
    v = values[values > 0]
    if len(v) == 0:
        return {}
    return {
        "eq255": round(float((v == 255).mean()), 3),
        "ge192": round(float((v >= 192).mean()), 3),
        "64_191": round(float(((v >= 64) & (v < 192)).mean()), 3),
        "lt64": round(float((v < 64).mean()), 3),
        "mean": round(float(v.mean()), 1),
    }


def terrain_fields(height, depth):
    """Per resource cell: slope %, height above nearest water surface, distance to water."""
    from scipy import ndimage

    wet = depth > 0.5
    gz, gx = np.gradient(height, 16.0)
    slope = np.hypot(gx, gz) * 100
    if wet.any():
        dist, (iz, ix) = ndimage.distance_transform_edt(~wet, return_indices=True)
        surface = height + depth
        above = height - surface[iz, ix]
        dist = dist * 16.0
    else:
        above = height - height.min()
        dist = np.full(height.shape, np.inf)
    # sample at resource-cell centres (nearest 16 m node)
    c = np.clip(
        np.floor(((np.arange(RES) - 256 + 0.5) * CELL + 8640) / 16 + 0.5).astype(int),
        0,
        HN - 1,
    )
    pick = np.ix_(c, c)
    land = ~wet[pick]
    h = height[pick]
    pct = np.zeros_like(h)
    ref = land & CENTRAL  # percentile against the playable 25 tiles' land
    if ref.any():
        order = np.sort(h[ref])
        pct = np.searchsorted(order, h) / len(order) * 100
    return {
        "slope": slope[pick],
        "above": above[pick],
        "dist": dist[pick],
        "land": land,
        "wet": wet[pick],
        "pct": pct,
    }


def placement(field, mask):
    sel = mask & field["land"]
    if not sel.any():
        return None
    out = {}
    for k in ["slope", "above", "dist", "pct"]:
        v = field[k][sel]
        v = v[np.isfinite(v)]
        out[k] = round(float(np.median(v)), 1) if len(v) else None
    out["wet_share"] = round(float((mask & field["wet"]).sum() / max(mask.sum(), 1)), 3)
    return out


def measure(path):
    raw = open(path, "rb").read()
    pkg, assets = read_any(raw)
    meta_asset = next(a for a in assets if a["kind"] == 100)
    meta = parse_metadata(meta_asset["payload"])
    sim = next(a for a in assets if a["kind"] == 52)
    data = sim["payload"]
    v = data_version(data)
    rec = {
        "file": os.path.basename(path),
        "display": sim["name"].rsplit("_Data", 1)[0],
        "package_format": pkg["format"],
        "data_version": v,
    }
    keep = [
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
    ]
    rec["meta"] = {k: meta.get(k) for k in keep}
    area_count, start = parse_start_tile(data, v)
    sx, sz = start % 5, start // 5
    rec["start_tile"] = {"index": start, "x": sx, "z": sz, "area_count": area_count}
    g, area = parse_resources(data, v)
    st = (TILE[:, None] == sz + 2) & (TILE[None, :] == sx + 2)
    height = parse_terrain(data)
    depth = parse_water(data)
    field = terrain_fields(height, depth)
    res = {}
    for k in ["ore", "oil", "fertility", "forest", "sand"]:
        grid = g[k]
        pos = grid > 0
        ts = tile_sums(grid)
        central_ts = ts[2:7, 2:7]
        r = {
            "cells": int(pos.sum()),
            "km2": round(float(pos.sum() * CELL_KM2), 2),
            "sum": int(grid.sum()),
            "central_km2": round(float((pos & CENTRAL).sum() * CELL_KM2), 2),
            "central_sum": int(grid[CENTRAL].sum()),
            "central_share_of_area": round(
                float((pos & CENTRAL).sum() / CENTRAL.sum()), 4
            ),
            "central_share_of_land": round(
                float(
                    (pos & CENTRAL & field["land"]).sum()
                    / max((CENTRAL & field["land"]).sum(), 1)
                ),
                4,
            ),
            "start_km2": round(float((pos & st).sum() * CELL_KM2), 3),
            "central_tiles_with": int((central_ts > 0).sum()),
            "central_tiles_ge5pct": int(
                (central_ts >= 0.05 * 255 * (CENTRAL.sum() / 25)).sum()
            ),
            "hist": hist(grid),
            "patches": patches(pos),
            "patches_central": patches(pos & CENTRAL),
        }
        r["central_fraction_of_cells"] = round(
            float((pos & CENTRAL).sum() / max(pos.sum(), 1)), 3
        )
        if k != "sand":
            r["placement"] = placement(field, pos & CENTRAL)
            r["placement_saturated"] = placement(field, (grid >= 192) & CENTRAL)
        res[k] = r
    rec["resources"] = res
    land = field["land"]
    rec["baseline"] = placement(field, CENTRAL.copy())
    rec["baseline_full_map"] = placement(field, np.ones_like(land))
    rec["water_central_share"] = round(
        float((~land & CENTRAL).sum() / CENTRAL.sum()), 4
    )
    if area is not None:
        fin = {
            k: int(area["final" + k][2:7, 2:7].sum())
            for k in ["Ore", "Oil", "Forest", "Fertility"]
        }
        if "finalWater" in area:
            fin["Water"] = int(area["finalWater"][2:7, 2:7].sum())
        rec["area_final_central"] = fin
    # trees
    t = parse_trees(data, v)
    created = (t["flags"] & 3) == 1
    names = t["names"]
    counts = np.bincount(t["prefab"][created], minlength=len(names))
    inside = (np.abs(t["x"]) < 4800) & (np.abs(t["z"]) < 4800)
    rec["trees"] = {
        "total": int(created.sum()),
        "slots_used": int(len(t["flags"])),
        "central": int((created & inside).sum()),
        "prefabs": {
            (names[i] if i < len(names) else f"#{i}"): int(c)
            for i, c in sorted(enumerate(counts), key=lambda x: -x[1])
            if c
        },
        "grow_state": {
            int(s): int(c)
            for s, c in zip(
                *np.unique((t["flags"][created] >> 8) & 15, return_counts=True)
            )
        },
        "single_flag_share": round(float(((t["flags"][created] & 0x10) != 0).mean()), 3)
        if created.any()
        else None,
        "burning": t["burning"],
    }
    # forest vs TreesModified prediction
    cx = np.clip((t["x"][created] / CELL + 256).astype(int), 0, 511)
    cz = np.clip((t["z"][created] / CELL + 256).astype(int), 0, 511)
    per_cell = np.bincount(cz * 512 + cx, minlength=RES * RES).reshape(RES, RES)
    pred = np.minimum(per_cell * 60, 255)
    f = g["forest"]
    rec["forest_check"] = {
        "exact_match_share": round(float((pred == f).mean()), 5),
        "forest_cells_without_trees": int(((f > 0) & (per_cell == 0)).sum()),
        "tree_cells_without_forest": int(((f == 0) & (per_cell > 0)).sum()),
        "mismatch_cells": int((pred != f).sum()),
        "trees_per_forest_cell_median": float(np.median(per_cell[per_cell > 0]))
        if (per_cell > 0).any()
        else None,
        "forest_cells_saturated_share": round(float((f[f > 0] == 255).mean()), 3)
        if (f > 0).any()
        else None,
    }
    # fertility: does it avoid forest and sit next to water?
    rec["fert_forest_overlap"] = int(((g["fertility"] > 0) & (f > 0)).sum())
    rec["ore_oil_overlap"] = int(((g["ore"] > 0) & (g["oil"] > 0)).sum())
    rec["terrain"] = {
        "min": round(float(height.min()), 1),
        "max": round(float(height.max()), 1),
        "median_land_slope_pct": rec["baseline"]["slope"] if rec["baseline"] else None,
    }
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("maps")
    ap.add_argument("out")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.maps, "*.crp")))
    if a.only:
        files = [f for f in files if any(o in os.path.basename(f) for o in a.only)]
    out = []
    for f in files:
        try:
            rec = measure(f)
        except Exception as e:  # keep going; record the failure
            rec = {"file": os.path.basename(f), "error": f"{type(e).__name__}: {e}"}
        out.append(rec)
        print(
            rec.get("file"),
            rec.get("error") or rec["trees"]["total"],
            file=sys.stderr,
            flush=True,
        )
        json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
