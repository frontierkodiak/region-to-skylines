"""The one decoder and encoder for CS1's NetManager and BuildingManager sections.

The layouts follow `NetManager.Data.Serialize` and `BuildingManager.Data.Serialize`
in CS1 1.21.1-f9 (Assembly-CSharp SHA-256 c7f0e723...). Both maps and game saves
read through here: a save adds guide and milestone prefabs and objects, which a
map leaves at zero. The map writer (`network_writer`) and the offline save
reader (`tools/save-reader`, `cs1save.managers`) share these classes.

Encoding an unchanged section decodes back to the same records and the same
section length (the tests check this on the shipping template); the run-length
choices of the encoded arrays may differ from the game's, which the format
allows. `NetSection.add_*` appends nodes and segments, and
`BuildingSection.clone` adds buildings copied from an existing record.

Segments are written without lanes (`m_lanes = 0`): `NetAI.UpdateLanes`, which
`NetManager.Data.AfterDeserialize` calls for every segment, allocates a missing
lane chain and computes its curves, so a map needs no lane records.
"""

import struct

import numpy as np

from template import decode_array

LANES, NODES, SEGMENTS, BUILDINGS = 262144, 32768, 36864, 49152
CURRENT_VERSION = 121034
NET_OBJECTS = 18  # NetManager's fixed guide objects after the prefab guides


class Cursor:
    def __init__(self, data, offset):
        self.data, self.offset = data, offset

    def array(self, count, width):
        values, self.offset = decode_array(self.data, count, self.offset, width)
        return values

    def raw(self, size):
        value = self.data[self.offset : self.offset + size]
        if len(value) != size:
            raise ValueError("Truncated manager section")
        self.offset += size
        return bytes(value)

    def u(self, size):
        return int.from_bytes(self.raw(size), "big")

    def string(self):
        """DataSerializer.WriteUniqueString / WriteSharedString payload (raw bytes)."""
        start = self.offset
        if self.data[start] == 255:
            self.offset += 1
            return None, bytes(self.data[start : start + 1])
        head = self.u(3)
        chars, previous = [], 0x80
        if head & 0x800000:
            for byte in self.raw(head & 0x7FFFFF):
                previous = (previous + byte) & 0xFF
                chars.append(chr(previous))
        else:
            for _ in range(head):
                previous = (previous + self.u(2)) & 0xFFFF
                chars.append(chr(previous))
        return "".join(chars), bytes(self.data[start : self.offset])


def _signed(value, bits):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


# Per width: (close-delta limit or None, close field width, whether a single
# same/close value already ends a mixed run). Transcribed from ColossalFramework
# EncodedArray.{Byte,UShort,UInt,Int,ULong}.WriteImplementation; Int writes the
# same bytes as UInt.
_RULES = {
    1: (None, 0, False),
    2: (127, 1, False),
    4: (32767, 2, False),
    8: (2147483647, 4, True),
}


def encode_exact(values, width):
    """EncodedArray.Write/EndWrite exactly as the game writes it.

    The writer keeps a 128-value window, flushes one run whenever the window is
    full and drains it at the end; each run is literal values, close deltas
    (half-width corrections to the previous delta) or a repeat of the last
    delta. Decoding is `template.decode_array`."""
    bits = 8 * width
    mask = (1 << bits) - 1
    limit, close_width, eager = _RULES[width]
    values = [int(v) & mask for v in np.asarray(values).ravel().tolist()]
    out = bytearray()
    state = {"index": 0, "prev": 0, "delta": 0}

    def flush(length):
        same = close = full = 0
        i, prev, delta = state["index"], state["prev"], state["delta"]
        while i < length:
            value = values[i]
            i += 1
            step = _signed(value - prev, bits)
            if step == delta:
                same += 1
                if limit is None:
                    # Byte: a repeat after literals ends the run at two.
                    if (full and same >= 2) or same >= 128:
                        break
                elif (
                    (full and same >= 1)
                    or (close and same >= (1 if eager else 2))
                    or same >= 128
                ):
                    break
            elif (
                limit is not None
                and -limit <= _signed(step - delta, 64 if width == 8 else 32) <= limit
            ):
                if same >= (1 if eager else 2):
                    break
                close += same + 1
                same = 0
                if (full and close >= (1 if eager else 2)) or close >= 64:
                    break
            else:
                if limit is None:
                    # Byte: no close runs; literals collect everything else.
                    if same >= 2:
                        break
                    full += same + 1
                    same = 0
                    if full >= 128:
                        break
                    prev, delta = value, step
                    continue
                if same >= 1 or close >= (1 if eager else 2):
                    break
                full += close + same + 1
                close = same = 0
                if full >= 64:
                    break
            prev, delta = value, step
        if full:
            full = min(full, 128 if limit is None else 64)
            out.append(full - 1)
            for _ in range(full):
                value = values[state["index"]]
                state["delta"] = _signed(value - state["prev"], bits)
                state["prev"] = value
                state["index"] += 1
                out.extend(value.to_bytes(width, "big"))
            return True
        if close:
            close = min(close, 64)
            out.append((close - 1) | 0x40)
            for _ in range(close):
                value = values[state["index"]]
                step = _signed(value - state["prev"], bits)
                correction = _signed(step - state["delta"], 8 * close_width)
                out.extend(correction.to_bytes(close_width, "big", signed=True))
                state["prev"], state["delta"] = value, step
                state["index"] += 1
            return True
        if same:
            same = min(same, 128)
            out.append((same - 1) | 0x80)
            state["prev"] = (state["prev"] + state["delta"] * same) & mask
            state["index"] += same
            return True
        return False

    for length in range(1, len(values) + 1):
        if length - state["index"] == 128:
            flush(length)
    while flush(len(values)):
        pass
    return bytes(out)


def unique_string(value):
    if value is None:
        return b"\xff"
    encoded = value.encode("latin1")
    result, previous = bytearray((0x800000 | len(encoded)).to_bytes(3, "big")), 0x80
    for byte in encoded:
        result.append((byte - previous) & 0xFF)
        previous = byte
    return bytes(result)


class PrefabTable:
    """PrefabCollection<T> Begin/EndSerialize: an index array, then a name table."""

    def __init__(self, cursor, count):
        self.indices = cursor.array(count, 2).astype(np.int64)
        size = cursor.u(2)
        self.names = [cursor.string()[0] for _ in range(size)]

    def encode(self):
        names = list(self.names)
        used = set(int(i) for i in self.indices)
        for i in range(len(names)):
            if i not in used:
                names[i] = None
        return (
            encode_exact(self.indices.astype(np.uint16), 2)
            + len(names).to_bytes(2, "big")
            + b"".join(unique_string(n) for n in names)
        )

    def index(self, name):
        """The table slot for `name`, appending one when the template lacks it."""
        if name in self.names:
            return self.names.index(name)
        self.names.append(name)
        return len(self.names) - 1


NODE_RECORD = ">3f"


class RawObjects:
    """DataSerializer objects and shared strings read straight from the bytes.

    A save keeps save-wide tables of shared strings, types and objects; a reader
    that needs them (cs1save) passes its own object with the same two methods,
    each taking (data, offset) and returning the new offset, so its tables stay
    whole. Maps only carry null objects and no shared strings here."""

    def object(self, data, offset):
        c = Cursor(data, offset)
        skip_object(c)
        return c.offset

    def shared_string(self, data, offset):
        c = Cursor(data, offset)
        head = c.u(1)
        if head == 255:
            return None, c.offset
        if head == 254:
            return c.string()[0], c.offset
        c.raw(1)  # a back-reference into the save-wide table
        return None, c.offset


class NetSection:
    """NetManager+Data from its tag through the fence tables; `end` marks where
    the unchanged remainder (guides, wetness, adjusted segments) begins."""

    def __init__(self, data, start, version=CURRENT_VERSION, objects=None):
        """Older versions (workshop maps) decode read-only, with Deserialize's
        gates, and stop after the main prefab table (`end` is None)."""
        objects = objects or RawObjects()
        self.version = v = version
        c = Cursor(data, start)
        self.lane_flags = c.array(LANES - 1, 2)
        live_lanes = np.flatnonzero(self.lane_flags)
        self.lane_next = [c.u(3) for _ in live_lanes]
        self.lane_reserved = [c.array(len(live_lanes), 1) for _ in range(3)]
        self.lane_last_reserve = c.array(len(live_lanes), 2)
        self.live_lanes = len(live_lanes)
        if v >= 115018:
            flags = c.array((NODES - 1) * 2, 4).reshape(-1, 2)
            self.node_flags, self.node_flags2 = flags[:, 0].copy(), flags[:, 1].copy()
        else:
            self.node_flags = c.array(NODES - 1, 4)
            self.node_flags2 = np.zeros_like(self.node_flags)
        node_ids = np.flatnonzero(self.node_flags) + 1
        n = len(node_ids)
        per = 2 if v >= 115000 else 1
        problems = c.array(n * per, 8).reshape(-1, per)
        wait = c.array(n, 1)
        counters = c.array(n * 2, 2).reshape(-1, 2)
        self.nodes = {}
        for k, node_id in enumerate(node_ids):
            position = struct.unpack(">3f", c.raw(12))
            segments = [c.u(2) for _ in range(c.u(1))]
            self.nodes[int(node_id)] = {
                "position": list(position),
                "segments": segments,
                "build_index": c.u(4),
                "building": c.u(2),
                "next_building_node": c.u(2),
                "lane": c.u(3),
                "lane_offset": c.u(1),
                "elevation": c.u(1),
                "height_offset": c.u(1),
                "connect_count": c.u(1),
                "event_route": c.u(2) if v >= 121007 else 0,
                "problems": [
                    int(problems[k, 0]),
                    int(problems[k, -1]) if per == 2 else 0,
                ],
                "max_wait": int(wait[k]),
                "counters": [int(counters[k, 0]), int(counters[k, 1])],
            }
        self.segment_flags = c.array(SEGMENTS - 1, 4)
        self.segment_flags2 = (
            c.array(SEGMENTS - 1, 4)
            if v >= 114012
            else np.zeros_like(self.segment_flags)
        )
        segment_ids = np.flatnonzero(self.segment_flags) + 1
        s = len(segment_ids)
        columns = {
            "problems": c.array(s * per, 8).reshape(-1, per),
            "traffic_lights": c.array(s * 2, 4 if v >= 115017 else 1).reshape(-1, 2),
            "fire": c.array(s, 1),
            "wetness": c.array(s, 1),
            "condition": c.array(s, 1),
            "noise_buffer": c.array(s, 2),
            "noise_density": c.array(s, 1),
            "attractiveness": c.array(s, 1) if v >= 121030 else np.zeros(s, int),
        }
        self.segments = {}
        for k, segment_id in enumerate(segment_ids):
            record = {
                "build_index": c.u(4),
                "modified_index": c.u(4),
                "lanes": c.u(3),
                "path": c.u(3),
                "start_direction": list(struct.unpack(">3f", c.raw(12))),
                "end_direction": list(struct.unpack(">3f", c.raw(12))),
                "start_node": c.u(2),
                "end_node": c.u(2),
                "blocks": [c.u(2) for _ in range(4)],
                "traffic_buffer": c.u(2),
                "traffic_density": c.u(1),
                "name_seed": c.u(2),
                "override_direction_limit": c.u(1) if v >= 113015 else 0,
                "tree": c.u(1) if v >= 114002 else 0,
                "left_fence": c.u(1) if v >= 120003 else 0,
                "right_fence": c.u(1) if v >= 120003 else 0,
                "event_route": c.u(2) if v >= 121005 else 0,
                "next_event_route_segment": c.u(2) if v >= 121005 else 0,
            }
            for name, column in columns.items():
                value = column[k]
                record[name] = [int(x) for x in value] if np.ndim(value) else int(value)
            if per == 1:
                record["problems"] = [record["problems"][0], 0]
            self.segments[int(segment_id)] = record
        self.guide_counts = (c.u(2), c.u(2))
        self.prefabs = PrefabTable(c, n + s + sum(self.guide_counts))
        self.node_prefab = {
            int(node_id): int(self.prefabs.indices[k])
            for k, node_id in enumerate(node_ids)
        }
        self.segment_prefab = {
            int(segment_id): int(self.prefabs.indices[n + k])
            for k, segment_id in enumerate(segment_ids)
        }
        # Games (not maps) list prefabs with an unused-guide and with a milestone.
        self.guide_prefabs = [int(i) for i in self.prefabs.indices[n + s :]]
        if v != CURRENT_VERSION:
            self.end = None
            return
        self.trees = PrefabTable(c, sum(r["tree"] for r in self.segments.values()))
        self.left_fences = PrefabTable(
            c, sum(r["left_fence"] for r in self.segments.values())
        )
        self.right_fences = PrefabTable(
            c, sum(r["right_fence"] for r in self.segments.values())
        )
        # The rest is kept as bytes for writing: the guide and milestone objects,
        # NetManager's own guides, wetness, name count and adjusted segments.
        tail = c.offset
        for _ in range(sum(self.guide_counts) + NET_OBJECTS):
            c.offset = objects.object(data, c.offset)
        self.wetness = (c.u(1), c.u(1))
        self.name_modified_count = c.u(3)
        self.adjusted_segments = c.array(c.u(3), 8)
        self.tail = bytes(data[tail : c.offset])
        self.end = c.offset

    def encode(self):
        if self.version != CURRENT_VERSION:
            raise ValueError("Only current-version sections are written")
        out = bytearray()
        lane_ids = np.flatnonzero(self.lane_flags)
        if len(lane_ids) != len(self.lane_next):
            raise ValueError("Lane arrays are inconsistent")
        out += encode_exact(self.lane_flags, 2)
        for value in self.lane_next:
            out += value.to_bytes(3, "big")
        for column in self.lane_reserved:
            out += encode_exact(column, 1)
        out += encode_exact(self.lane_last_reserve, 2)
        node_ids = sorted(self.nodes)
        flags = np.zeros((NODES - 1, 2), dtype=np.uint32)
        flags[:, 0], flags[:, 1] = self.node_flags, self.node_flags2
        if sorted(int(i) + 1 for i in np.flatnonzero(flags[:, 0])) != node_ids:
            raise ValueError("Node flags and records disagree")
        out += encode_exact(flags.ravel(), 4)
        records = [self.nodes[i] for i in node_ids]
        out += encode_exact(
            np.array([p for r in records for p in r["problems"]], dtype=np.uint64), 8
        )
        out += encode_exact(np.array([r["max_wait"] for r in records], np.uint8), 1)
        out += encode_exact(
            np.array([v for r in records for v in r["counters"]], np.uint16), 2
        )
        for r in records:
            out += struct.pack(">3f", *r["position"])
            out += bytes([len(r["segments"])])
            for segment in r["segments"]:
                out += segment.to_bytes(2, "big")
            out += r["build_index"].to_bytes(4, "big")
            out += r["building"].to_bytes(2, "big")
            out += r["next_building_node"].to_bytes(2, "big")
            out += r["lane"].to_bytes(3, "big")
            out += bytes(
                [
                    r["lane_offset"],
                    r["elevation"],
                    r["height_offset"],
                    r["connect_count"],
                ]
            )
            out += r["event_route"].to_bytes(2, "big")
        segment_ids = sorted(self.segments)
        if (
            sorted(int(i) + 1 for i in np.flatnonzero(self.segment_flags))
            != segment_ids
        ):
            raise ValueError("Segment flags and records disagree")
        out += encode_exact(self.segment_flags, 4)
        out += encode_exact(self.segment_flags2, 4)
        segs = [self.segments[i] for i in segment_ids]

        def column(name, width, dtype):
            values = [v for r in segs for v in np.atleast_1d(r[name])]
            return encode_exact(np.array(values, dtype=dtype), width)

        out += column("problems", 8, np.uint64)
        out += column("traffic_lights", 4, np.uint32)
        out += column("fire", 1, np.uint8)
        out += column("wetness", 1, np.uint8)
        out += column("condition", 1, np.uint8)
        out += column("noise_buffer", 2, np.uint16)
        out += column("noise_density", 1, np.uint8)
        out += column("attractiveness", 1, np.uint8)
        for r in segs:
            out += r["build_index"].to_bytes(4, "big")
            out += r["modified_index"].to_bytes(4, "big")
            out += r["lanes"].to_bytes(3, "big") + r["path"].to_bytes(3, "big")
            out += struct.pack(">6f", *r["start_direction"], *r["end_direction"])
            out += r["start_node"].to_bytes(2, "big") + r["end_node"].to_bytes(2, "big")
            for block in r["blocks"]:
                out += block.to_bytes(2, "big")
            out += r["traffic_buffer"].to_bytes(2, "big")
            out += bytes([r["traffic_density"]])
            out += r["name_seed"].to_bytes(2, "big")
            out += bytes(
                [
                    r["override_direction_limit"],
                    r["tree"],
                    r["left_fence"],
                    r["right_fence"],
                ]
            )
            out += r["event_route"].to_bytes(2, "big")
            out += r["next_event_route_segment"].to_bytes(2, "big")
        out += self.guide_counts[0].to_bytes(2, "big")
        out += self.guide_counts[1].to_bytes(2, "big")
        self.prefabs.indices = np.array(
            [self.node_prefab[i] for i in node_ids]
            + [self.segment_prefab[i] for i in segment_ids]
            + self.guide_prefabs,
            dtype=np.int64,
        )
        out += self.prefabs.encode()
        for table in [self.trees, self.left_fences, self.right_fences]:
            out += table.encode()
        return bytes(out + self.tail)

    # ------------------------------------------------------------ editing
    def remove(self, node_ids):
        """Release nodes and every segment touching them."""
        node_ids = set(node_ids)
        for segment_id in [
            s
            for s, r in self.segments.items()
            if r["start_node"] in node_ids or r["end_node"] in node_ids
        ]:
            record = self.segments.pop(segment_id)
            if record["lanes"]:
                self._release_lanes(record["lanes"])
            self.segment_flags[segment_id - 1] = 0
            self.segment_flags2[segment_id - 1] = 0
            del self.segment_prefab[segment_id]
            for node in [record["start_node"], record["end_node"]]:
                if node in self.nodes:
                    self.nodes[node]["segments"].remove(segment_id)
        for node_id in node_ids:
            del self.nodes[node_id]
            del self.node_prefab[node_id]
            self.node_flags[node_id - 1] = 0
            self.node_flags2[node_id - 1] = 0

    def _release_lanes(self, first):
        live = list(np.flatnonzero(self.lane_flags) + 1)
        position = {lane: k for k, lane in enumerate(live)}
        doomed, lane = [], first
        while lane:
            doomed.append(lane)
            lane = self.lane_next[position[lane]]
        keep = [k for k, lane in enumerate(live) if lane not in set(doomed)]
        self.lane_next = [self.lane_next[k] for k in keep]
        self.lane_reserved = [c[keep] for c in self.lane_reserved]
        self.lane_last_reserve = self.lane_last_reserve[keep]
        for lane in doomed:
            self.lane_flags[lane - 1] = 0

    def free_id(self, used, limit):
        for candidate in range(1, limit):
            if candidate not in used:
                return candidate
        raise ValueError("No free network slot")

    def add_node(self, prefab, position, flags, flags2=0, elevation=0, building=0):
        node_id = self.free_id(self.nodes, NODES)
        self.nodes[node_id] = {
            "position": [float(v) for v in position],
            "segments": [],
            "build_index": 0,
            "building": building,
            "next_building_node": 0,
            "lane": 0,
            "lane_offset": 0,
            "elevation": int(elevation),
            "height_offset": 0,
            "connect_count": 0,
            "event_route": 0,
            "problems": [0, 0],
            "max_wait": 0,
            "counters": [0, 0],
        }
        self.node_flags[node_id - 1] = flags
        self.node_flags2[node_id - 1] = flags2
        self.node_prefab[node_id] = self.prefabs.index(prefab)
        return node_id

    def add_segment(self, prefab, start, end, start_direction, end_direction, flags):
        if (
            len(self.nodes[start]["segments"]) >= 8
            or len(self.nodes[end]["segments"]) >= 8
        ):
            raise ValueError("A CS1 node joins at most eight segments")
        segment_id = self.free_id(self.segments, SEGMENTS)
        self.segments[segment_id] = {
            "build_index": 0,
            "modified_index": 0,
            "lanes": 0,
            "path": 0,
            "start_direction": [float(v) for v in start_direction],
            "end_direction": [float(v) for v in end_direction],
            "start_node": start,
            "end_node": end,
            "blocks": [0, 0, 0, 0],
            "traffic_buffer": 0,
            "traffic_density": 0,
            "name_seed": 0,
            "override_direction_limit": 0,
            "tree": 0,
            "left_fence": 0,
            "right_fence": 0,
            "event_route": 0,
            "next_event_route_segment": 0,
            "problems": [0, 0],
            "traffic_lights": [0, 0],
            "fire": 0,
            "wetness": 0,
            "condition": 255,
            "noise_buffer": 0,
            "noise_density": 0,
            "attractiveness": 0,
        }
        self.segment_flags[segment_id - 1] = flags
        self.segment_prefab[segment_id] = self.prefabs.index(prefab)
        self.nodes[start]["segments"].append(segment_id)
        self.nodes[end]["segments"].append(segment_id)
        return segment_id

    def prefab_name(self, index):
        return self.prefabs.names[index]


def skip_object(c):
    """DataSerializer.WriteObject: null, a back-reference, or a new object whose
    payload is queued after the managers (only its shared type is inline)."""
    marker = c.u(1)
    if marker == 255:
        return
    if marker != 254:
        c.raw(2)
        return
    kind = c.u(1)
    if kind == 254:
        size = c.u(3)
        c.raw(size & 0x7FFFFF if size & 0x800000 else 2 * size)
    elif kind != 255:
        c.raw(1)


# BuildingManager's per-building columns after its guides, as (kind, name,
# values per building), in BuildingManager.Data.Serialize order. Derived twice
# from the game source (PL-982 writer, PL-984 save reader); the two agreed.
BUILDING_COLUMNS = (
    [("u64", "problems", 2)]
    + [
        ("u16", name, 1)
        for name in [
            "net_node",
            "sub_building",
            "water_source",
            "electricity_buffer",
            "water_buffer",
            "sewage_buffer",
            "heating_buffer",
            "garbage_buffer",
            "crime_buffer",
            "mail_buffer",
            "custom_buffer1",
            "custom_buffer2",
            "build_water_height",
        ]
    ]
    + [
        ("u8", name, 1)
        for name in [
            "production_rate",
            "water_pollution",
            "construct_state",
            "fire_intensity",
            "fire_damage",
            "production_state",
            "health",
            "child_health",
            "senior_health",
            "happiness",
            "citizen_count",
            "temp_import",
            "temp_export",
            "final_import",
            "final_export",
        ]
    ]
    + [("u8", "problem_timers", 11)]
    + [
        ("u8", name, 1)
        for name in [
            "level_up_progress",
            "width",
            "length",
            "education1",
            "education2",
            "education3",
            "children",
            "teens",
            "youngs",
            "adults",
            "seniors",
            "fire_hazard",
            "level",
        ]
    ]
    + [
        ("u32", "cargo_traffic_rate", 1),
        ("u32", "garbage_traffic_rate", 1),
        ("u16", "access_segment", 1),
        ("u16", "event_access_segment", 1),
        ("i32", "cash_buffer", 1),
        ("u16", "room_cost", 1),
        ("u16", "room_cost_target", 1),
        ("u16", "room_max", 1),
        ("u16", "room_used", 1),
    ]
    + [("u8", f"educated{i}_unemployed", 1) for i in range(4)]
    + [("u8", "all_unemployed", 1), ("u16", "event_route_index", 1)]
)
WIDTHS = {"u8": 1, "u16": 2, "u32": 4, "i32": 4, "u64": 8}
NET_NODE_COLUMN = 1  # m_netNode
BUILDING_GUIDES = 71
EFFECT_BYTES = 4 * 16 * 16  # temp/final monument effects and faculty bonuses


class BuildingSection:
    """BuildingManager+Data after its tag; per-building columns kept generically."""

    def __init__(self, data, start, objects=None):
        objects = objects or RawObjects()
        c = Cursor(data, start)
        self.flags = c.array(BUILDINGS - 1, 4)
        self.flags2 = c.array(BUILDINGS - 1, 4)
        self.ids = [int(i) + 1 for i in np.flatnonzero(self.flags)]
        n = len(self.ids)
        self.guide_counts = (c.u(2), c.u(2))
        self.prefabs = PrefabTable(c, n + sum(self.guide_counts))
        self.guide_prefabs = [int(i) for i in self.prefabs.indices[n:]]
        self.prefabs.indices = self.prefabs.indices[:n]
        guides_start = c.offset
        for _ in range(sum(self.guide_counts) + BUILDING_GUIDES):
            c.offset = objects.object(data, c.offset)
        c.raw(32)
        self.guides = bytes(data[guides_start : c.offset])
        self.columns = [
            (WIDTHS[kind], per, c.array(n * per, WIDTHS[kind]).reshape(n, per))
            for kind, _, per in BUILDING_COLUMNS
        ]
        # Service vehicle choices: (building, vehicle prefab name, raw bytes).
        self.selections = []
        for _ in range(2):
            rows = []
            for _ in range(c.u(2)):
                key, at = c.u(2), c.offset
                value, c.offset = objects.shared_string(data, c.offset)
                rows.append((key, value, bytes(data[at : c.offset])))
            self.selections.append(rows)
        self.records = [c.raw(24) for _ in range(n)]
        self.effects = c.raw(EFFECT_BYTES)
        self.race = [c.u(1) for _ in range(n)]
        self.race_table = PrefabTable(c, sum(self.race))
        self.end = c.offset

    def encode(self):
        out = bytearray(encode_exact(self.flags, 4) + encode_exact(self.flags2, 4))
        out += self.guide_counts[0].to_bytes(2, "big")
        out += self.guide_counts[1].to_bytes(2, "big")
        indices = self.prefabs.indices
        self.prefabs.indices = np.concatenate(
            [indices, np.array(self.guide_prefabs, dtype=np.int64)]
        )
        out += self.prefabs.encode() + self.guides
        self.prefabs.indices = indices
        for width, _, values in self.columns:
            out += encode_exact(values.ravel(), width)
        for selection in self.selections:
            out += len(selection).to_bytes(2, "big")
            for key, _, raw in selection:
                out += key.to_bytes(2, "big") + raw
        out += b"".join(self.records) + self.effects + bytes(self.race)
        out += self.race_table.encode()
        return bytes(out)

    def clone(self, source_id, position, angle, net_node):
        """Add a building copied from `source_id`, returning its new ID."""
        if any(self.race):
            raise ValueError("Editing a section with race-team buildings")
        k = self.ids.index(source_id)
        taken = set(self.ids)
        new_id = next(i for i in range(1, BUILDINGS) if i not in taken)
        at = int(np.searchsorted(self.ids, new_id))
        self.ids.insert(at, new_id)
        self.flags[new_id - 1] = self.flags[source_id - 1]
        self.flags2[new_id - 1] = self.flags2[source_id - 1]
        self.prefabs.indices = np.insert(
            self.prefabs.indices, at, self.prefabs.indices[k]
        )
        self.columns = [
            (width, per, np.insert(values, at, values[k], axis=0))
            for width, per, values in self.columns
        ]
        self.columns[NET_NODE_COLUMN][2][at] = net_node
        record = bytearray(self.records[k])
        if record[21:24] != b"\0\0\0":
            raise ValueError("A cloned building must own no citizen units")
        record[4:20] = struct.pack(">4f", *position, angle)
        self.records.insert(at, bytes(record))
        self.race.insert(at, self.race[k])
        return new_id

    def remove(self, building_id):
        if any(self.race):
            raise ValueError("Editing a section with race-team buildings")
        k = self.ids.index(building_id)
        self.ids.pop(k)
        self.flags[building_id - 1] = 0
        self.flags2[building_id - 1] = 0
        self.prefabs.indices = np.delete(self.prefabs.indices, k)
        self.columns = [
            (width, per, np.delete(values, k, axis=0))
            for width, per, values in self.columns
        ]
        self.records.pop(k)
        self.race.pop(k)

    def set_prefab(self, building_id, name):
        k = self.ids.index(building_id)
        self.prefabs.indices[k] = self.prefabs.index(name)

    def column(self, name):
        """One per-building column by name, rows in `ids` order."""
        for (kind, column, per), (_, _, values) in zip(BUILDING_COLUMNS, self.columns):
            if column == name:
                values = values.astype(np.int64)
                if kind == "i32":
                    values = np.where(values >= 1 << 31, values - (1 << 32), values)
                return values if per > 1 else values[:, 0]
        raise KeyError(name)

    def net_node(self, building_id):
        return int(self.columns[NET_NODE_COLUMN][2][self.ids.index(building_id), 0])

    def set_net_node(self, building_id, node):
        self.columns[NET_NODE_COLUMN][2][self.ids.index(building_id), 0] = node

    def prefab(self, building_id):
        return self.prefabs.names[
            int(self.prefabs.indices[self.ids.index(building_id)])
        ]

    def record(self, building_id):
        raw = self.records[self.ids.index(building_id)]
        x, y, z, angle = struct.unpack(">4f", raw[4:20])
        return {"position": [x, y, z], "angle": angle}
