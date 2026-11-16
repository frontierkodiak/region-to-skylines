"""Decoders for individual manager blocks, transcribed from each manager's
Data.Serialize in CS1 1.21.1-f9 (save format 121034).

Each parser starts just after the block's opening tag and must stop exactly
before its closing tag; save.read_save checks that. Arrays keep the game's
buffer indices (index 0 is the unused null item).
"""

import numpy as np

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

NODE_TAIL = [
    ("build_index", ">u4"),
    ("building", ">u2"),
    ("next_building_node", ">u2"),
    ("lane", ">u4"),
    ("lane_offset", "u1"),
    ("elevation", "u1"),
    ("height_offset", "u1"),
    ("connect_count", "u1"),
    ("event_route", ">u2"),
]

SEGMENT = np.dtype(
    [
        ("build_index", ">u4"),
        ("modified_index", ">u4"),
        ("lanes", "V3"),
        ("path", "V3"),
        ("start_direction", ">f4", 3),
        ("end_direction", ">f4", 3),
        ("start_node", ">u2"),
        ("end_node", ">u2"),
        ("block_start_left", ">u2"),
        ("block_start_right", ">u2"),
        ("block_end_left", ">u2"),
        ("block_end_right", ">u2"),
        ("traffic_buffer", ">u2"),
        ("traffic_density", "u1"),
        ("name_seed", ">u2"),
        ("override_direction", "u1"),
        ("has_tree", "u1"),
        ("has_left_fence", "u1"),
        ("has_right_fence", "u1"),
        ("event_route", ">u2"),
        ("next_event_route_segment", ">u2"),
    ]
)


def net(s):
    lane_flags = s.encoded("u16", LANES - 1)
    live_lanes = int(np.count_nonzero(lane_flags))
    s.take(3 * live_lanes)  # m_nextLane
    for _ in range(3):
        s.encoded("u8", live_lanes)  # reserved prev / next / frame
    s.encoded("u16", live_lanes)  # last reserve id

    node_flags = s.encoded("u32", 2 * (NODES - 1)).reshape(-1, 2)
    node_ids = np.flatnonzero(node_flags[:, 0]) + 1
    nn = len(node_ids)
    s.encoded("u64", 2 * nn)  # problems
    s.encoded("u8", nn)  # max wait time
    s.encoded("u16", 2 * nn)  # temp / final counters
    positions = np.empty((nn, 3), dtype=np.float32)
    node_segments = []
    building = np.empty(nn, dtype=np.uint16)
    elevation = np.empty(nn, dtype=np.uint8)
    build_index = np.empty(nn, dtype=np.uint32)
    for i in range(nn):
        positions[i] = s.vec3()
        node_segments.append([s.u16() for _ in range(s.u8())])
        build_index[i] = s.u32()
        building[i] = s.u16()
        s.u16(), s.u24(), s.u8()
        elevation[i] = s.u8()
        s.u8(), s.u8(), s.u16()

    seg_flags = s.encoded("u32", SEGMENTS - 1)
    seg_flags2 = s.encoded("u32", SEGMENTS - 1)
    segment_ids = np.flatnonzero(seg_flags) + 1
    ns = len(segment_ids)
    s.encoded("u64", 2 * ns)  # problems
    s.encoded("i32", 2 * ns)  # traffic light states
    s.encoded("u8", ns)  # fire coverage
    s.encoded("u8", ns)  # wetness
    condition = s.encoded("u8", ns)
    s.encoded("u16", ns)  # noise buffer
    s.encoded("u8", ns)  # noise density
    s.encoded("u8", ns)  # attractiveness
    seg = records(s, SEGMENT, ns)

    guides, milestones = s.u16(), s.u16()
    info, info_names = prefab_block(s, nn + ns + guides + milestones)
    has_tree = seg["has_tree"] != 0
    tree_info, tree_names = prefab_block(s, int(has_tree.sum()))
    left = seg["has_left_fence"] != 0
    left_info, left_names = prefab_block(s, int(left.sum()))
    right = seg["has_right_fence"] != 0
    right_info, right_names = prefab_block(s, int(right.sum()))
    objects(s, guides + milestones + 18)
    s.u8(), s.u8()
    name_modified = s.u24()
    adjusted = s.u24()
    s.encoded("u64", adjusted)

    node_info = info[:nn]
    seg_info = info[nn : nn + ns]
    return {
        "node_ids": node_ids,
        "node_flags": node_flags[node_ids - 1, 0],
        "node_flags2": node_flags[node_ids - 1, 1],
        "node_position": positions,
        "node_segments": node_segments,
        "node_building": building,
        "node_elevation": elevation,
        "node_build_index": build_index,
        "node_prefab": [info_names[i] for i in node_info],
        "segment_ids": segment_ids,
        "segment_flags": seg_flags[segment_ids - 1],
        "segment_flags2": seg_flags2[segment_ids - 1],
        "segment_start_node": seg["start_node"].astype(np.int64),
        "segment_end_node": seg["end_node"].astype(np.int64),
        "segment_start_direction": seg["start_direction"].astype(np.float32),
        "segment_end_direction": seg["end_direction"].astype(np.float32),
        "segment_build_index": seg["build_index"].astype(np.int64),
        "segment_name_seed": seg["name_seed"].astype(np.int64),
        "segment_condition": condition,
        "segment_prefab": [info_names[i] for i in seg_info],
        "segment_tree_prefab": tree_names_for(has_tree, tree_info, tree_names),
        "live_lanes": live_lanes,
        "name_modified_count": name_modified,
    }


def tree_names_for(mask, indices, names):
    out = [None] * len(mask)
    for j, i in zip(np.flatnonzero(mask), indices):
        out[j] = names[i]
    return out


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

# Per-building encoded arrays after the flags, in Serialize order, for buildings
# whose m_flags != 0. (kind, field, values per building)
BUILDING_ARRAYS = [
    ("u64", "problems", 2),
    ("u16", "net_node", 1),
    ("u16", "sub_building", 1),
    ("u16", "water_source", 1),
    ("u16", "electricity_buffer", 1),
    ("u16", "water_buffer", 1),
    ("u16", "sewage_buffer", 1),
    ("u16", "heating_buffer", 1),
    ("u16", "garbage_buffer", 1),
    ("u16", "crime_buffer", 1),
    ("u16", "mail_buffer", 1),
    ("u16", "custom_buffer1", 1),
    ("u16", "custom_buffer2", 1),
    ("u16", "build_water_height", 1),
    ("u8", "production_rate", 1),
    ("u8", "water_pollution", 1),
    ("u8", "construct_state", 1),
    ("u8", "fire_intensity", 1),
    ("u8", "fire_damage", 1),
    ("u8", "production_state", 1),
    ("u8", "health", 1),
    ("u8", "child_health", 1),
    ("u8", "senior_health", 1),
    ("u8", "happiness", 1),
    ("u8", "citizen_count", 1),
    ("u8", "temp_import", 1),
    ("u8", "temp_export", 1),
    ("u8", "final_import", 1),
    ("u8", "final_export", 1),
    ("u8", "problem_timers", 11),
    ("u8", "level_up_progress", 1),
    ("u8", "width", 1),
    ("u8", "length", 1),
    ("u8", "education1", 1),
    ("u8", "education2", 1),
    ("u8", "education3", 1),
    ("u8", "children", 1),
    ("u8", "teens", 1),
    ("u8", "youngs", 1),
    ("u8", "adults", 1),
    ("u8", "seniors", 1),
    ("u8", "fire_hazard", 1),
    ("u8", "level", 1),
    ("u32", "cargo_traffic_rate", 1),
    ("u32", "garbage_traffic_rate", 1),
    ("u16", "access_segment", 1),
    ("u16", "event_access_segment", 1),
    ("i32", "cash_buffer", 1),
    ("u16", "room_cost", 1),
    ("u16", "room_cost_target", 1),
    ("u16", "room_max", 1),
    ("u16", "room_used", 1),
    ("u8", "educated0_unemployed", 1),
    ("u8", "educated1_unemployed", 1),
    ("u8", "educated2_unemployed", 1),
    ("u8", "educated3_unemployed", 1),
    ("u8", "all_unemployed", 1),
    ("u16", "event_route_index", 1),
]
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

BUILDING_PLACE = np.dtype(
    [("build_index", ">u4"), ("position", ">f4", 3), ("angle", ">f4"), ("base_height", "u1"), ("citizen_units", "V3")]
)


def building(s):
    flags = s.encoded("u32", BUILDINGS - 1)
    flags2 = s.encoded("u32", BUILDINGS - 1)
    ids = np.flatnonzero(flags) + 1
    nb = len(ids)
    guides, milestones = s.u16(), s.u16()
    info, names = prefab_block(s, nb + guides + milestones)
    objects(s, guides + milestones + 71)
    s.take(32)  # last/current building problems
    out = {"ids": ids, "flags": flags[ids - 1], "flags2": flags2[ids - 1]}
    for kind, name, per in BUILDING_ARRAYS:
        values = s.encoded(kind, per * nb)
        if name in KEEP_BUILDING:
            out[name] = values
    vehicle_selection = []
    for _ in range(2):
        for _ in range(s.i16()):
            vehicle_selection.append((s.u16(), s.shared_string()))
    place = records(s, BUILDING_PLACE, nb)
    s.take(16 * 2 * 16 * 2)  # monument effects and faculty bonuses: (i32, vec3) x 64
    race = np.frombuffer(s.take(nb), dtype=np.uint8) != 0
    prefab_block(s, int(race.sum()))
    out.update(
        position=place["position"].astype(np.float32),
        angle=place["angle"].astype(np.float32),
        build_index=place["build_index"].astype(np.int64),
        base_height=place["base_height"],
        prefab=[names[i] for i in info[:nb]],
        vehicle_selection=vehicle_selection,
    )
    return out


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
