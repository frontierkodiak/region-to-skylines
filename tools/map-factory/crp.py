"""A fingerprint-bound CS1 CRP map writer, not a generic save editor.

The native factory supplies consistent topology and serializer reference tables.
Known terrain, water, network geometry, building and resource fields are patched;
allocation IDs and all other payloads are preserved. No game DLLs are required.
"""

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

import numpy as np

N = 1081 * 1081


class Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def take(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError("Read outside input")
        value = self.data[self.pos : self.pos + count]
        self.pos += count
        return value

    def number(self, fmt):
        return struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))[0]

    def string(self):
        size = 0
        for shift in range(0, 35, 7):
            byte = self.number("B")
            size |= (byte & 127) << shift
            if byte < 128:
                return self.take(size).decode("utf8")
        raise ValueError("Invalid string length")


def string(value):
    data = value.encode("utf8")
    size = len(data)
    prefix = bytearray()
    while size >= 128:
        prefix.append((size & 127) | 128)
        size >>= 7
    return bytes(prefix) + bytes([size]) + data


def read_package(data):
    r = Reader(data)
    if r.take(4) != b"CRAP" or r.number("H") != 12:
        raise ValueError("Expected CRP package format 12")
    package = {k: r.string() for k in ["name", "author"]}
    package["version"], package["main"] = r.number("I"), r.string()
    count, start = r.number("i"), r.number("q")
    if not 0 < count <= 1000:
        raise ValueError("Unexpected asset count")
    assets = []
    for _ in range(count):
        name, checksum, kind = r.string(), r.string(), r.number("i")
        offset, size = r.number("q"), r.number("q")
        if offset < 0 or size < 0 or start + offset + size > len(data):
            raise ValueError("Asset range outside package")
        payload = data[start + offset : start + offset + size]
        if hashlib.md5(payload).hexdigest() != checksum:
            raise ValueError("Asset checksum mismatch")
        assets.append({"name": name, "kind": kind, "payload": payload})
    if r.pos != start:
        raise ValueError("Package directory length mismatch")
    return package, assets


def write_package(package, assets):
    prefix = b"CRAP" + struct.pack("<H", 12)
    prefix += string(package["name"]) + string(package["author"])
    prefix += struct.pack("<I", package["version"]) + string(package["main"])
    directory, offset = bytearray(), 0
    for a in assets:
        payload = a["payload"]
        directory.extend(string(a["name"]) + string(hashlib.md5(payload).hexdigest()))
        directory.extend(struct.pack("<iqq", a["kind"], offset, len(payload)))
        offset += len(payload)
    start = len(prefix) + 12 + len(directory)
    return (
        prefix
        + struct.pack("<iq", len(assets), start)
        + directory
        + b"".join(a["payload"] for a in assets)
    )


def decode_u16(data, count, offset=0):
    """Decode the game's delta/RLE array; reject runs past the expected length."""
    result = np.empty(count, dtype=np.uint16)
    i, previous, delta = 0, 0, 0
    while i < count:
        code = data[offset]
        offset += 1
        length = code - 127 if code >= 128 else (code & 63) + 1
        if i + length > count:
            raise ValueError("Encoded run exceeds array length")
        for _ in range(length):
            if code < 64:
                value = int.from_bytes(data[offset : offset + 2], "big")
                offset += 2
                delta = (value - previous + 32768) % 65536 - 32768
            elif code < 128:
                extra = struct.unpack_from("b", data, offset)[0]
                offset += 1
                delta = (delta + extra + 32768) % 65536 - 32768
                value = (previous + delta) % 65536
            else:
                value = (previous + delta) % 65536
            result[i] = value
            previous = value
            i += 1
    return result, offset


def encode_u16(values):
    """Literal runs are sufficient and deterministic; zero runs stay compact."""
    values = np.asarray(values, dtype=np.uint16).ravel()
    out = bytearray()
    i, previous, delta = 0, 0, 0
    while i < len(values):
        if values[i] == previous and delta == 0:
            end = i + 1
            while end < min(i + 128, len(values)) and values[end] == previous:
                end += 1
            out.append(128 + end - i - 1)
        else:
            end = min(i + 64, len(values))
            out.append(end - i - 1)
            out.extend(values[i:end].astype(">u2").tobytes())
            delta = (
                int(values[end - 1])
                - (int(values[end - 2]) if end - i > 1 else previous)
                + 32768
            ) % 65536 - 32768
            previous = int(values[end - 1])
        i = end
    return bytes(out)


def metadata_value(r, typename):
    if typename.endswith("[]"):
        count = r.number("i")
        if not 0 <= count <= 10000:
            raise ValueError("Invalid metadata array length")
        return [metadata_value(r, typename[:-2]) for _ in range(count)]
    if typename in [
        "System.String",
        "System.DateTime",
        "ColossalFramework.Packaging.Package+Asset",
    ]:
        return r.string()
    if typename == "ModInfo":
        return (r.string(), r.number("Q"))
    formats = {
        "System.Boolean": "B",
        "System.Int32": "i",
        "System.UInt32": "I",
        "System.Single": "f",
    }
    return r.number(formats[typename])


def mono_hash(value):
    """Unity Mono's UTF-16 string hash (verified against native MapMetaData)."""
    result = 0
    encoded = value.encode("utf-16-le")
    for (char,) in struct.iter_unpack("<H", encoded):
        result = (result * 31 + char) & 0xFFFFFFFF
    return result if result < 0x80000000 else result - 0x100000000


def patch_metadata(payload, checksum, label=None, water_amount=None):
    r = Reader(payload)
    if r.number("B") != 0 or not r.string().startswith("MapMetaData,"):
        raise ValueError("Expected MapMetaData object")
    r.string()
    count = r.number("i")
    result = bytearray(payload[: r.pos])
    for _ in range(count):
        start = r.pos
        if r.number("B"):
            result.extend(payload[start : r.pos])
            continue
        typename, name = r.string().split(",")[0], r.string()
        value_start = r.pos
        metadata_value(r, typename)
        result.extend(payload[start:value_start])
        if name == "assetRef":
            result.extend(string(checksum))
        elif name == "mods":
            result.extend(struct.pack("<i", 0))
        elif name == "mapName" and label is not None:
            result.extend(string(label))
        elif name == "publishedHash" and label is not None:
            result.extend(struct.pack("<i", mono_hash(label)))
        elif name == "waterAmount" and water_amount is not None:
            result.extend(struct.pack("<I", water_amount))
        else:
            result.extend(payload[value_start : r.pos])
    if r.pos != len(payload):
        raise ValueError("Metadata not completely consumed")
    return bytes(result)


def water_payload(depth, sources, frame, sea_level=35.0):
    wet = depth.reshape(1081, 1081) > 0
    vx = wet.copy()
    vx[:, :-1] |= wet[:, 1:]
    vz = wet.copy()
    vz[:-1, :] |= wet[1:, :]
    data = encode_u16(depth)
    for count in [wet.sum(), vx.sum(), vz.sum()]:
        data += encode_u16(np.zeros(int(count), dtype=np.uint16))
    data += struct.pack(">H", len(sources))
    for s in sources:
        position = list(s["position"])
        data += struct.pack(
            ">6fHH", *position, *position, 1, math.floor(s["target"] * 64 + 0.5)
        )
        rate = math.floor(s["capacity"] * 65535 + 0.5)
        for value in [0, 0, rate, rate, 0]:
            data += value.to_bytes(3, "big")
    return data + struct.pack(">HfbbI", 0, sea_level, 0, 0, frame)


def begin_tag_size(data, offset, expected):
    if data[offset] != 254:
        raise ValueError("Expected a new shared manager-name tag")
    size = int.from_bytes(data[offset + 1 : offset + 4], "big")
    if size & 0x800000 == 0:
        raise ValueError("Expected Latin-1 manager-name tag")
    size &= 0x7FFFFF
    value, previous = [], 128
    for byte in data[offset + 4 : offset + 4 + size]:
        previous = (previous + byte) & 255
        value.append(chr(previous))
    if "".join(value) != expected:
        raise ValueError("Manager tag does not match its layout entry")
    return size + 4


def write_map(template, layout, terrain, water, hydrology, output):
    original = template.read_bytes()
    spec = json.loads(layout.read_text())
    hydro = json.loads(hydrology.read_text())
    if hashlib.sha256(original).hexdigest() != spec["template_sha256"]:
        raise ValueError(
            "Template fingerprint mismatch; byte ranges are template-specific"
        )
    package, assets = read_package(original)
    simulation = next(a for a in assets if a["kind"] == 52)
    data = simulation["payload"]
    raw = np.fromfile(terrain, dtype="<u2")
    depth = np.fromfile(water, dtype="<u2")
    if len(raw) != N or len(depth) != N:
        raise ValueError("Expected terrain and depth grids of 1081 squared ushorts")
    ranges = {v["type"]: v for v in spec["ranges"]}
    tr, wr = ranges["TerrainManager+Data"], ranges["WaterSimulation+Data"]
    terrain_prefix = begin_tag_size(data, tr["start"], "TerrainManager")
    water_prefix = begin_tag_size(data, wr["start"], "WaterSimulation")
    old_raw, end = decode_u16(data, N, tr["start"] + terrain_prefix)
    delta, tail = decode_u16(data, int((old_raw != 0).sum()), end)
    if np.any(delta) or tail >= tr["end"]:
        raise ValueError("This writer requires a template without sculpting deltas")
    # Elevated factory networks do not sculpt terrain. This fixture requires no
    # detail-height deltas; a ground-network template needs its own delta policy.
    terrain_data = (
        data[tr["start"] : tr["start"] + terrain_prefix]
        + encode_u16(raw)
        + encode_u16(np.zeros(int(np.count_nonzero(raw)), dtype=np.uint16))
        + data[tail : tr["end"]]
    )
    sources = hydro["sources"]
    for s in sources:
        x, _, z = s["position"]
        if not (-8640 <= x <= 8640 and -8640 <= z <= 8640):
            raise ValueError("Water source is outside the map")
        if not (0 <= s["target"] < 1024 and 0 < s["capacity"] <= 1):
            raise ValueError("Invalid water-source target or capacity")
        i = math.floor((z + 8640) / 16 + 0.5) * 1081 + math.floor((x + 8640) / 16 + 0.5)
        s["position"][1] = float(raw[i] / 64)
    frame = int.from_bytes(data[wr["end"] - 6 : wr["end"] - 2], "big")
    water_data = (
        data[wr["start"] : wr["start"] + water_prefix]
        + water_payload(depth, sources, frame, hydro.get("sea_level_m", 35.0))
        + data[wr["end"] - 2 : wr["end"]]
    )
    replacements = [
        (tr["start"], tr["end"], terrain_data),
        (wr["start"], wr["end"], water_data),
    ]
    # The native template supplies topology, prefab references, flags, outside
    # buildings and lane IDs. Only recorded, fingerprint-bound vector positions
    # change. CS1's NetManager.AfterDeserialize rebuilds the lane curves.
    positions = hydro.get("node_positions", {})
    for record in spec.get("nodes", []):
        node_id = str(record["id"])
        if node_id not in positions:
            raise ValueError(f"Missing fitted position for template node {node_id}")
        start = record["offset"]
        expected = struct.pack(">3f", *record["position"])
        if data[start : start + 12] != expected:
            raise ValueError("Template position does not match recorded bytes")
        position = positions[node_id]
        if (
            len(position) != 3
            or not all(math.isfinite(v) for v in position)
            or not 0 < position[1] < 1024
            or abs(position[0]) > 8640.01
            or abs(position[2]) > 8640.01
        ):
            raise ValueError("Invalid fitted network position")
        replacements.append((start, start + 12, struct.pack(">3f", *position)))
    nodes = {n["id"]: n for n in spec.get("nodes", [])}
    neighbors = {}
    for segment in spec.get("segments", []):
        start = segment["direction_offset"]
        if data[start : start + 24] != struct.pack(">6f", *segment["directions"]):
            raise ValueError("Template direction does not match recorded bytes")
        a, b = [positions[str(segment[k])] for k in ["from", "to"]]
        length = math.hypot(b[0] - a[0], b[2] - a[2])
        if length < 1:
            raise ValueError("Degenerate fitted network segment")
        direction = [(b[0] - a[0]) / length, 0, (b[2] - a[2]) / length]
        replacements.append(
            (
                start,
                start + 24,
                struct.pack(">6f", *direction, *[-v for v in direction]),
            )
        )
        neighbors[segment["from"]] = segment["to"]
        neighbors[segment["to"]] = segment["from"]
    for building in spec.get("buildings", []):
        start, node_id = building["offset"], building["node"]
        if data[start : start + 16] != struct.pack(
            ">4f", *building["position"], building["angle"]
        ):
            raise ValueError("Template building does not match recorded bytes")
        position = list(positions[str(node_id)])
        position[1] += building["position"][1] - nodes[node_id]["position"][1]
        other = neighbors[node_id]
        old_a, old_b = nodes[node_id]["position"], nodes[other]["position"]
        new_a, new_b = positions[str(node_id)], positions[str(other)]
        turn = math.atan2(new_b[0] - new_a[0], new_b[2] - new_a[2]) - math.atan2(
            old_b[0] - old_a[0], old_b[2] - old_a[2]
        )
        angle = (building["angle"] + turn) % (2 * math.pi)
        replacements.append((start, start + 16, struct.pack(">4f", *position, angle)))
    water_amount = None
    if positions:
        from template import resource_replacements

        resources, water_amount = resource_replacements(data, spec, depth)
        replacements.extend(resources)
        start = spec["start_tile_offset"]
        if (
            data[start] != spec["original_start_tile"]
            or not 0 <= hydro["start_tile"] < 25
        ):
            raise ValueError("Invalid template start-tile descriptor")
        replacements.append((start, start + 1, bytes([hydro["start_tile"]])))
    for start, end, replacement in sorted(replacements, reverse=True):
        data = data[:start] + replacement + data[end:]
    simulation["payload"] = data
    checksum = hashlib.md5(data).hexdigest()
    for a in assets:
        if a["kind"] == 100:
            a["payload"] = patch_metadata(
                a["payload"], checksum, hydro.get("map_name"), water_amount
            )
    if "map_id" in hydro:
        package["name"] = hydro["map_id"]
        package["author"] = ""
    result = write_package(package, assets)
    read_package(result)
    output.write_bytes(result)
    regenerated = ["terrain", "water", "sources"]
    preserved = ["network_topology", "outside_connections", "lane_ids", "trees"]
    if positions:
        regenerated.extend(["network_geometry", "start_tile", "water_resources"])
        preserved.append("other_resources")
    else:
        preserved.extend(["network_geometry", "buildings", "resources"])
    if "map_id" in hydro or "map_name" in hydro:
        regenerated.append("map_identity")
    return {
        "output": str(output),
        "sha256": hashlib.sha256(result).hexdigest(),
        "bytes": len(result),
        "regenerated": regenerated,
        "preserved": preserved,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["template", "layout", "terrain", "water", "hydrology", "output"]:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(write_map(**vars(args)), indent=2))
