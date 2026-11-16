"""Decoders for individual manager blocks, transcribed from each manager's
Data.Serialize in CS1 1.21.1-f9 (save format 121034).

Each parser starts just after the block's opening tag and must stop exactly
before its closing tag; save.read_save checks that. Arrays keep the game's
buffer indices (index 0 is the unused null item).
"""

import numpy as np

from . import codec
from .stream import FormatError

GRID = 1081
N_CELLS = GRID * GRID
LANES = 262144
NODES = 32768
SEGMENTS = 36864
BUILDINGS = 49152
BLOCKS = 49152
TREES = 262144
PROPS = 65536
DISTRICTS = 128
PARKS = 128
LINES = 256

# Every vanilla manager in 1.21.1-f9 (SimulationManager registration order).
KNOWN = {
    "GameAreaManager",
    "TerrainManager",
    "WaterSimulation",
    "InstanceManager",
    "NetManager",
    "BuildingManager",
    "CitizenManager",
    "TransferManager",
    "NaturalResourceManager",
    "ImmaterialResourceManager",
    "ElectricityManager",
    "WaterManager",
    "ZoneManager",
    "PropManager",
    "TreeManager",
    "WeatherManager",
    "VehicleManager",
    "TransportManager",
    "EconomyManager",
    "DistrictManager",
    "EventManager",
    "DisasterManager",
    "InfoManager",
    "AudioManager",
    "StatisticsManager",
    "UnlockManager",
    "MessageManager",
    "GuideManager",
    "PathManager",
    "ErrorManager",
}


def prefab_names(s):
    """PrefabCollection<T>.EndSerialize: the name of each referenced prefab index."""
    return [s.unique_string() for _ in range(s.u16())]


def prefab_block(s, count):
    """PrefabCollection<T>.BeginSerialize .. EndSerialize around `count` references."""
    indices = s.encoded("u16", count)
    names = prefab_names(s)
    for i in np.unique(indices):
        if i >= len(names) or names[i] is None:
            raise FormatError(f"prefab index {i} has no name")
    return indices, names


def records(s, dtype, count):
    """`count` fixed-size big-endian records, as a numpy structured array."""
    dtype = np.dtype(dtype)
    raw = s.take(dtype.itemsize * count)
    return np.frombuffer(raw, dtype=dtype, count=count)


def objects(s, count):
    return [s.object() for _ in range(count)]


def camera_view(s):
    return {
        "mode": s.i16(),
        "position": s.vec3(),
        "size": s.f32(),
        "angle": s.vec2(),
        "height": s.f32(),
    }


# GameAreaManager --------------------------------------------------------------


def game_area(s):
    out = {"area_count": s.u8(), "start_tile": s.u8()}
    out["area_grid"] = s.encoded("u8", 25)
    objects(s, 1)
    out["buildable_area"] = [s.f32() for _ in range(4)]
    out["camera"] = camera_view(s)
    return out


# TerrainManager / WaterSimulation ---------------------------------------------


def terrain(s):
    raw = s.encoded("u16", N_CELLS)
    deltas = s.encoded("u16", int(np.count_nonzero(raw)))
    out = {"raw_heights": raw.reshape(GRID, GRID), "block_deltas": deltas}
    out["dirt_buffer"] = s.i32()
    objects(s, 3)
    return out


def water_simulation(s):
    depth = s.encoded("u16", N_CELLS)
    wet = depth != 0
    pollution = s.encoded("u16", int(wet.sum()))
    grid = wet.reshape(GRID, GRID)
    vx = grid.copy()
    vx[:, :-1] |= grid[:, 1:]
    vz = grid.copy()
    vz[:-1, :] |= grid[1:, :]
    s.encoded("i16", int(vx.sum()))
    s.encoded("i16", int(vz.sum()))
    sources = []
    for _ in range(s.u16()):
        sources.append(
            {
                "input_position": s.vec3(),
                "output_position": s.vec3(),
                "type": s.u16(),
                "target": s.u16(),
                "water": s.u24(),
                "pollution": s.u24(),
                "input_rate": s.u24(),
                "output_rate": s.u24(),
                "flow": s.u24(),
            }
        )
    waves = s.u16()
    s.take(24 * waves)
    out = {"depth": depth.reshape(GRID, GRID), "pollution_cells": int(np.count_nonzero(pollution))}
    out.update(sources=sources, waves=waves, sea_level=s.f32())
    s.i8(), s.i8()
    out["water_frame"] = s.u32()
    return out


# InstanceManager ----------------------------------------------------------------

INSTANCE_TYPES = {
    1: "Building",
    2: "Vehicle",
    3: "District",
    4: "Citizen",
    5: "NetNode",
    6: "NetSegment",
    7: "ParkedVehicle",
    8: "TransportLine",
    9: "CitizenInstance",
    10: "Prop",
    11: "Tree",
    12: "Event",
    13: "NetLane",
    14: "BuildingProp",
    15: "NetLaneProp",
    16: "Disaster",
    17: "Lightning",
    18: "RadioChannel",
    19: "RadioContent",
    20: "Park",
}


def instance(s):
    names = []
    for _ in range(s.u32()):
        key = s.u32()
        names.append(
            {
                "type": INSTANCE_TYPES.get(key >> 24, key >> 24),
                "index": key & 0xFFFFFF,
                "name": s.unique_string(),
            }
        )
    groups = []
    for _ in range(s.u32()):
        groups.append((s.u32(), s.object()))
    return {"names": names, "groups": len(groups)}


# NetManager --------------------------------------------------------------------
# Decoded by the shared codec (tools/map-factory/netcodec.py), which the map
# writer also encodes with; this function only shapes its records for the city.


def net(s):
    section = codec.netcodec.NetSection(s.data, s.pos, objects=codec.StreamObjects(s))
    s.pos = section.end
    node_ids = np.array(sorted(section.nodes), dtype=np.int64)
    segment_ids = np.array(sorted(section.segments), dtype=np.int64)
    nodes = [section.nodes[i] for i in node_ids]
    segs = [section.segments[i] for i in segment_ids]
    names = section.prefabs.names
    trees = iter(section.trees.indices)
    return {
        "node_ids": node_ids,
        "node_flags": section.node_flags[node_ids - 1],
        "node_flags2": section.node_flags2[node_ids - 1],
        "node_position": np.array([r["position"] for r in nodes], dtype=np.float32).reshape(-1, 3),
        "node_segments": [r["segments"] for r in nodes],
        "node_building": np.array([r["building"] for r in nodes], dtype=np.uint16),
        "node_elevation": np.array([r["elevation"] for r in nodes], dtype=np.uint8),
        "node_build_index": np.array([r["build_index"] for r in nodes], dtype=np.uint32),
        "node_prefab": [names[section.node_prefab[i]] for i in node_ids],
        "segment_ids": segment_ids,
        "segment_flags": section.segment_flags[segment_ids - 1],
        "segment_flags2": section.segment_flags2[segment_ids - 1],
        "segment_start_node": np.array([r["start_node"] for r in segs], dtype=np.int64),
        "segment_end_node": np.array([r["end_node"] for r in segs], dtype=np.int64),
        "segment_start_direction": np.array([r["start_direction"] for r in segs], dtype=np.float32).reshape(-1, 3),
        "segment_end_direction": np.array([r["end_direction"] for r in segs], dtype=np.float32).reshape(-1, 3),
        "segment_build_index": np.array([r["build_index"] for r in segs], dtype=np.int64),
        "segment_name_seed": np.array([r["name_seed"] for r in segs], dtype=np.int64),
        "segment_condition": np.array([r["condition"] for r in segs], dtype=np.uint8),
        "segment_prefab": [names[section.segment_prefab[i]] for i in segment_ids],
        "segment_tree_prefab": [section.trees.names[next(trees)] if r["tree"] else None for r in segs],
        "live_lanes": section.live_lanes,
        "name_modified_count": section.name_modified_count,
    }


# ZoneManager --------------------------------------------------------------------

ZONE_BLOCK = np.dtype(
    [
        ("build_index", ">u4"),
        ("position", ">f4", 3),
        ("angle", ">f4"),
        ("valid", ">u8"),
        ("shared", ">u8"),
        ("occupied1", ">u8"),
        ("occupied2", ">u8"),
        ("zone1", ">u8"),
        ("zone2", ">u8"),
        ("segment", ">u2"),
    ]
)

ZONES = {
    0: "Unzoned",
    1: "Distant",
    2: "ResidentialLow",
    3: "ResidentialHigh",
    4: "CommercialLow",
    5: "CommercialHigh",
    6: "Industrial",
    7: "Office",
    15: "None",
}


def zone(s):
    flags = s.encoded("u32", BLOCKS - 1)
    ids = np.flatnonzero(flags) + 1
    blocks = records(s, ZONE_BLOCK, len(ids))
    demand = [s.i8() for _ in range(6)]
    good_area = [s.i16() for _ in range(8)]
    objects(s, 13)
    return {
        "block_ids": ids,
        "block_flags": flags[ids - 1],
        "blocks": blocks,
        "demand": dict(
            zip(
                [
                    "residential",
                    "commercial",
                    "workplace",
                    "actual_residential",
                    "actual_commercial",
                    "actual_workplace",
                ],
                demand,
            )
        ),
        "good_area_found": good_area,
    }


def zone_cells(zone_data):
    """Every zone cell the game uses: (x, z, zone code, block id, row, column).

    Cell (row i, column j) of a block sits at
    position + (j - 3.5) * 8 * (cos a, sin a) + (i - 3.5) * 8 * (sin a, -cos a),
    and its zone is the nibble at bit (i << 3) | ((j & 1) << 2) of zone1 (j < 2)
    or zone2, as ZoneBlock.GetZone reads it.
    """
    blocks = zone_data["blocks"]
    rows = (zone_data["block_flags"] >> 8) & 0xFF
    out = []
    for b, rec in enumerate(blocks):
        # Where two blocks overlap exactly, one copy of the cell is marked shared;
        # the game uses only valid cells that aren't (ZoneBlock, ZoneManager).
        valid = int(rec["valid"]) & ~int(rec["shared"])
        if not valid:
            continue
        a = float(rec["angle"])
        cx, cz = np.cos(a) * 8, np.sin(a) * 8
        rx, rz = cz, -cx
        px, _, pz = (float(v) for v in rec["position"])
        z1, z2 = int(rec["zone1"]), int(rec["zone2"])
        for i in range(min(int(rows[b]), 8)):
            for j in range(4):
                if not valid >> ((i << 3) | j) & 1:
                    continue
                word = z1 if j < 2 else z2
                code = (word >> ((i << 3) | ((j & 1) << 2))) & 0xF
                x = px + (j - 3.5) * cx + (i - 3.5) * rx
                zz = pz + (j - 3.5) * cz + (i - 3.5) * rz
                out.append((x, zz, code, int(zone_data["block_ids"][b]), i, j))
    return out


# TreeManager --------------------------------------------------------------------


def tree(s):
    flags = s.encoded("u16", TREES - 1)
    ids = np.flatnonzero(flags) + 1
    info, names = prefab_block(s, len(ids))
    x = s.encoded("i16", len(ids))
    z = s.encoded("i16", len(ids))
    burning = s.u24()
    s.take(5 * burning)
    return {
        "ids": ids,
        "flags": flags[ids - 1],
        "pos_x": x,  # stored shorts
        "pos_z": z,
        # TreeInstance.Position: shorts scaled by 0.26367188 m outside the asset editor
        "x": x.astype(np.float32) * np.float32(0.26367188),
        "z": z.astype(np.float32) * np.float32(0.26367188),
        "prefab_index": info,
        "prefab_names": names,
        "burning": burning,
    }


# BuildingManager --------------------------------------------------------------
# Decoded by the shared codec as well; these are the columns the city keeps.

KEEP_BUILDING = {
    "net_node",
    "sub_building",
    "level",
    "width",
    "length",
    "citizen_count",
    "construct_state",
    "access_segment",
    "happiness",
    "health",
    "production_rate",
    "fire_damage",
}


def building(s):
    section = codec.netcodec.BuildingSection(s.data, s.pos, objects=codec.StreamObjects(s))
    s.pos = section.end
    ids = np.array(section.ids, dtype=np.int64)
    out = {"ids": ids, "flags": section.flags[ids - 1], "flags2": section.flags2[ids - 1]}
    for name in KEEP_BUILDING:
        out[name] = section.column(name)
    place = np.frombuffer(b"".join(section.records), dtype=BUILDING_PLACE, count=len(ids))
    out.update(
        position=place["position"].astype(np.float32),
        angle=place["angle"].astype(np.float32),
        build_index=place["build_index"].astype(np.int64),
        base_height=place["base_height"],
        prefab=[section.prefabs.names[i] for i in section.prefabs.indices],
        vehicle_selection=[(key, value) for rows in section.selections for key, value, _ in rows],
    )
    return out


BUILDING_PLACE = np.dtype(
    [("build_index", ">u4"), ("position", ">f4", 3), ("angle", ">f4"), ("base_height", "u1"), ("citizen_units", "V3")]
)


PARSERS = {
    "GameAreaManager": game_area,
    "TerrainManager": terrain,
    "WaterSimulation": water_simulation,
    "InstanceManager": instance,
    "NetManager": net,
    "BuildingManager": building,
    "ZoneManager": zone,
    "TreeManager": tree,
}
