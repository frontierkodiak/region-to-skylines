"""Describe fixed native topology; never allocate nodes, segments or lane IDs.

The descriptor is bound to the complete template SHA-256. Only known vector
fields, the start tile and resource arrays are patched by the reference writer.
"""

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

import numpy as np


def decode_array(data, count, offset, width):
    """Read the native Byte/UShort/UInt/ULong delta/RLE representation."""
    values = np.empty(count, dtype=f"u{width}")
    previous, delta, i = 0, 0, 0
    mask = (1 << (8 * width)) - 1
    while i < count:
        if offset >= len(data):
            raise ValueError("Truncated encoded array")
        code = data[offset]
        offset += 1
        literal = code < (128 if width == 1 else 64)
        close = width > 1 and 64 <= code < 128
        length = (
            code - 127 if code >= 128 else (code + 1 if width == 1 else (code & 63) + 1)
        )
        if i + length > count:
            raise ValueError("Encoded array run exceeds its declared size")
        for k in range(length):
            if literal:
                if offset + width > len(data):
                    raise ValueError("Truncated encoded literal")
                value = int.from_bytes(data[offset : offset + width], "big")
                offset += width
                delta = (value - previous) & mask
            elif close:
                small = width // 2
                if offset + small > len(data):
                    raise ValueError("Truncated encoded delta")
                delta = (
                    delta
                    + int.from_bytes(data[offset : offset + small], "big", signed=True)
                ) & mask
                offset += small
                value = (previous + delta) & mask
            else:
                value = (previous + delta) & mask
            values[i + k] = value
            previous = value
        i += length
    return values, offset


def encode_array(values, width):
    """Deterministic literal/predictor runs; same policy as crp.encode_u16."""
    values = np.asarray(values, dtype=f"u{width}").ravel()
    result = bytearray()
    previous, delta, i = 0, 0, 0
    mask = (1 << (width * 8)) - 1
    while i < len(values):
        if int(values[i]) == previous and delta == 0:
            end = i + 1
            while end < min(i + 128, len(values)) and int(values[end]) == previous:
                end += 1
            result.append(127 + end - i)
        else:
            end = min(i + (128 if width == 1 else 64), len(values))
            result.append(end - i - 1)
            result.extend(values[i:end].astype(f">u{width}").tobytes())
            delta = (
                int(values[end - 1])
                - (int(values[end - 2]) if end - i > 1 else previous)
            ) & mask
            previous = int(values[end - 1])
        i = end
    return bytes(result)


def manager_tag(name):
    result, previous = bytearray([254]), 128
    result.extend((0x800000 | len(name)).to_bytes(3, "big"))
    for char in name.encode("latin1"):
        result.append((char - previous) & 255)
        previous = char
    return bytes(result)


def saved_camera(data, start_tile_offset):
    """Locate the native camera after the 25-tile array and guide reference.

    The caller binds the source to a complete template fingerprint. Queued
    guide objects write only their reference/type here, never their payload.
    """
    _, offset = decode_array(data, 25, start_tile_offset + 1, 1)
    reference = data[offset]
    offset += 1
    if reference == 254:
        shared_type = data[offset]
        offset += 1
        if shared_type == 254:
            length = int.from_bytes(data[offset : offset + 3], "big")
            if not length & 0x800000:
                raise ValueError("Expected Latin-1 guide type")
            offset += 3 + (length & 0x7FFFFF)
        elif shared_type == 255:
            raise ValueError("Guide object has a null type")
        else:
            offset += 1
    elif reference != 255:
        offset += 2
    buildable = struct.unpack_from(">4f", data, offset)
    if not all(np.isfinite(v) and -1 <= v <= 1 for v in buildable):
        raise ValueError("Unexpected native area flatness fields")
    offset += 16
    values = struct.unpack_from(">h7f", data, offset)
    if values[0] not in [-1, 0, 1, 2, 3, 10] or not all(np.isfinite(values[1:])):
        raise ValueError("Unexpected saved camera fields")
    return {"offset": offset, "bytes": data[offset : offset + 30].hex()}


def describe(template, layout, output):
    from crp import begin_tag_size, read_package

    original = template.read_bytes()
    spec = json.loads(layout.read_text())
    if hashlib.sha256(original).hexdigest() != spec["template_sha256"]:
        raise ValueError("Template fingerprint mismatch")
    _, assets = read_package(original)
    data = next(a["payload"] for a in assets if a["kind"] == 52)
    ranges = {r["type"]: r for r in spec["ranges"]}
    net = ranges["NetManager+Data"]
    offset = net["start"] + begin_tag_size(data, net["start"], "NetManager")

    def array(count, width):
        nonlocal offset
        values, offset = decode_array(data, count, offset, width)
        return values

    lane_count = int(np.count_nonzero(array(262143, 2)))
    offset += lane_count * 3
    for _ in range(3):
        array(lane_count, 1)
    array(lane_count, 2)
    flags = array(32767 * 2, 4).reshape(-1, 2)
    node_ids = np.flatnonzero(flags[:, 0]) + 1
    array(len(node_ids) * 2, 8)
    array(len(node_ids), 1)
    array(len(node_ids) * 2, 2)
    nodes = []
    for node_id in node_ids:
        start = offset
        position = list(struct.unpack_from(">3f", data, start))
        count = data[start + 12]
        if count > 8:
            raise ValueError("Unexpected native node segment count")
        building = int.from_bytes(
            data[start + 17 + 2 * count : start + 19 + 2 * count], "big"
        )
        nodes.append(
            {
                "id": int(node_id),
                "position": position,
                "offset": start,
                "building": building,
            }
        )
        offset += 30 + count * 2
    segment_ids = np.flatnonzero(array(36863, 4)) + 1
    array(36863, 4)
    array(len(segment_ids) * 2, 8)
    array(len(segment_ids) * 2, 4)
    for _ in range(3):
        array(len(segment_ids), 1)
    array(len(segment_ids), 2)
    for _ in range(2):
        array(len(segment_ids), 1)
    segments = []
    for segment_id in segment_ids:
        segments.append(
            {
                "id": int(segment_id),
                "direction_offset": offset + 14,
                "directions": list(struct.unpack_from(">6f", data, offset + 14)),
                "from": int.from_bytes(data[offset + 38 : offset + 40], "big"),
                "to": int.from_bytes(data[offset + 40 : offset + 42], "big"),
            }
        )
        offset += 63
    node_index = {n["id"]: n for n in nodes}
    if any(s["from"] not in node_index or s["to"] not in node_index for s in segments):
        raise ValueError("Native segment references an absent node")
    outgoing = {s["from"]: s["to"] for s in segments}
    incoming = {s["to"] for s in segments}
    routes = []
    for first in sorted(outgoing.keys() - incoming):
        ids = [first]
        while ids[-1] in outgoing:
            ids.append(outgoing[ids[-1]])
            if len(ids) > len(nodes):
                raise ValueError("Cyclic template route")
        outside = lambda node: (
            max(abs(node_index[node]["position"][axis]) for axis in [0, 2]) >= 8639
        )
        kind = (
            "rail"
            if outside(ids[0]) and outside(ids[-1])
            else "road_in"
            if outside(ids[0])
            else "road_out"
        )
        routes.append({"kind": kind, "nodes": ids})
    if sum(len(r["nodes"]) for r in routes) != len(nodes):
        raise ValueError("Template is not a collection of independent simple routes")
    buildings = []
    for n in nodes:
        if not n["building"]:
            continue
        x, _, z = n["position"]
        pattern = (
            re.escape(struct.pack(">f", x)) + b"...." + re.escape(struct.pack(">f", z))
        )
        hits = [
            m.start()
            for m in re.finditer(pattern, data, re.DOTALL)
            if not net["start"] <= m.start() < net["end"]
        ]
        if len(hits) != 1:
            raise ValueError("Outside-building position is not uniquely identifiable")
        pos = hits[0]
        buildings.append(
            {
                "id": n["building"],
                "node": n["id"],
                "offset": pos,
                "position": list(struct.unpack_from(">3f", data, pos)),
                "angle": struct.unpack_from(">f", data, pos + 12)[0],
            }
        )
    tag = manager_tag("GameAreaManager")
    start = data.find(tag)
    if start < 0 or data.find(tag, start + 1) >= 0:
        raise ValueError("Start-tile manager tag is not unique")
    spec.update(
        {
            "nodes": nodes,
            "segments": segments,
            "buildings": buildings,
            "routes": routes,
            "start_tile_offset": start + len(tag) + 1,
            "original_start_tile": data[start + len(tag) + 1],
            "camera": saved_camera(data, start + len(tag) + 1),
        }
    )
    output.write_text(json.dumps(spec, indent=2) + "\n")
    return {
        "nodes": len(nodes),
        "segments": len(segments),
        "buildings": len(buildings),
        "start_tile": spec["original_start_tile"],
        "sha256": spec["template_sha256"],
    }


def resource_replacements(data, spec, depth):
    """Update water/shore cells and tile totals, preserving other resources."""
    from crp import begin_tag_size

    span = next(r for r in spec["ranges"] if r["type"] == "NaturalResourceManager+Data")
    offset = span["start"] + begin_tag_size(
        data, span["start"], "NaturalResourceManager"
    )
    for _ in range(4):
        forest, offset = decode_array(data, 512 * 512, offset, 1)
    _, offset = decode_array(data, int(np.count_nonzero(forest)), offset, 1)
    _, offset = decode_array(data, int(np.count_nonzero(forest == 0)), offset, 1)
    water_start = offset
    _, offset = decode_array(data, 512 * 512, offset, 1)
    water_end = shore_start = offset
    _, offset = decode_array(data, 512 * 512, offset, 1)
    shore_end = offset
    for _ in range(3):
        _, offset = decode_array(data, 512 * 512, offset, 1)
    area_start = offset
    areas, area_end = decode_array(data, 81 * 10, offset, 4)
    # Resource cells are 33.75 m squares; the water grid's spacing is 16 m.
    sample = np.floor((np.arange(512) + 0.5) * 1080 / 512 + 0.5).astype(int)
    wet = depth.reshape(1081, 1081)[np.ix_(sample, sample)] > 0
    water = wet.astype(np.uint8) * 255
    nearby = wet.copy()
    nearby[1:, :] |= wet[:-1, :]
    nearby[:-1, :] |= wet[1:, :]
    nearby[:, 1:] |= wet[:, :-1]
    nearby[:, :-1] |= wet[:, 1:]
    shore = (nearby & ~wet).astype(np.uint8) * 255
    tile = np.minimum(8, np.floor((np.arange(512) + 0.5) * 9 / 512).astype(int))
    totals = np.bincount(
        (tile[:, None] * 9 + tile).ravel(), weights=water.ravel(), minlength=81
    ).astype(np.uint32)
    areas[8 * 81 : 9 * 81] = totals
    areas[9 * 81 : 10 * 81] = totals
    return [
        (water_start, water_end, encode_array(water, 1)),
        (shore_start, shore_end, encode_array(shore, 1)),
        (area_start, area_end, encode_array(areas, 4)),
    ], int(totals.reshape(9, 9)[2:7, 2:7].sum())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["template", "layout", "output"]:
        parser.add_argument(name, type=Path)
    print(json.dumps(describe(**vars(parser.parse_args())), indent=2))
