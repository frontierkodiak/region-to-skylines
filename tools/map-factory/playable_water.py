"""Map-maker water: deep channels, local catchment supplies and contained shores.

The mapped planform remains the reference. Heights inside and immediately beside
water are authored for play; the measured terrain beyond that strip is untouched.
Capacity is a game setting scaled by map-local drainage area, not discharge.
"""

import heapq
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from catchment import local_catchment_area
from joint_surface import connected_surface
from prepare import pixel
from surface_water import surface_geometry

SPACING = 16
HALF = 8640
STEPS = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]


def raster(sq, features, polygons=False):
    image = Image.new("L", (1081, 1081))
    for feature in features:
        draw = ImageDraw.Draw(image)
        if polygons:
            layer = Image.new("L", image.size)
            painter = ImageDraw.Draw(layer)
            for i, ring in enumerate(feature["rings"]):
                if len(ring) >= 3:
                    painter.polygon(
                        [pixel(sq, p) for p in ring], fill=255 if i == 0 else 0
                    )
            image = Image.fromarray(np.maximum(np.asarray(image), np.asarray(layer)))
        elif len(feature["pts"]) >= 2:
            draw.line([pixel(sq, p) for p in feature["pts"]], fill=255)
    return np.asarray(image) > 0


def stage_tree(mask, desired, flat, sea_mask):
    """Drain each raster system toward its sea or lowest captured edge/end.

    A gentle minimum grade is an authored design, not an inferred flow direction.
    Closed captured systems retain a named terminal sink instead of an invented
    cross-country ditch. The returned outlet list makes that limitation visible.
    """
    shape = mask.shape
    labels, count = ndimage.label(mask, np.ones((3, 3)))
    stage = np.full(shape, np.nan)
    distance = np.zeros(shape)
    seen = np.zeros(shape, bool)
    parent = np.full(shape, -1, np.int64)
    order = []
    edge = np.zeros(shape, bool)
    edge[[0, -1], :] = True
    edge[:, [0, -1]] = True
    outlets = []
    queue = []
    for label, box in enumerate(ndimage.find_objects(labels), 1):
        if box is None:
            continue
        component = labels[box] == label
        sea = component & sea_mask[box]
        boundary = component & edge[box]
        candidates = sea if sea.any() else boundary if boundary.any() else component
        yy, xx = np.nonzero(candidates)
        values = desired[box][yy, xx]
        at = int(np.argmin(values))
        row, col = int(yy[at] + box[0].start), int(xx[at] + box[1].start)
        role = "sea" if sea.any() else "map_edge" if boundary.any() else "closed_sink"
        outlets.append({"row": row, "col": col, "role": role, "component": label})
        # All ocean cells share the chosen sea plane, without a graded ocean.
        starts = np.argwhere(sea) if sea.any() else np.array([[yy[at], xx[at]]])
        for y, x in starts:
            r, c = int(y + box[0].start), int(x + box[1].start)
            seen[r, c] = True
            stage[r, c] = desired[r, c]
            heapq.heappush(queue, (float(stage[r, c]), r, c))
    height, width = shape
    while queue:
        level, row, col = heapq.heappop(queue)
        order.append((row, col))
        for dy, dx in STEPS:
            r, c = row + dy, col + dx
            if not (0 <= r < height and 0 <= c < width):
                continue
            if not mask[r, c] or seen[r, c]:
                continue
            seen[r, c] = True
            parent[r, c] = row * width + col
            length = SPACING * math.hypot(dy, dx)
            grade = 0 if flat[r, c] else length * 0.001
            stage[r, c] = max(float(desired[r, c]), level + grade)
            distance[r, c] = distance[row, col] + length
            heapq.heappush(queue, (float(stage[r, c]), r, c))
    if count and not np.all(np.isfinite(stage[mask])):
        raise ValueError("Incomplete water-system stage tree")
    # Lower a bed sill rather than propagate it upstream as a raised water wall.
    # Caps flow downstream first; the forward pass restores the gentle grade.
    cap = desired.copy()
    for r, c in reversed(order):
        p = int(parent[r, c])
        if p >= 0:
            pr, pc = divmod(p, width)
            grade = 0 if flat[r, c] else SPACING * math.hypot(r - pr, c - pc) * 0.001
            cap[pr, pc] = min(cap[pr, pc], cap[r, c] - grade)
    for r, c in order:
        p = int(parent[r, c])
        if sea_mask[r, c]:
            stage[r, c] = desired[r, c]
        elif p < 0:
            stage[r, c] = max(8, cap[r, c])
        else:
            pr, pc = divmod(p, width)
            grade = 0 if flat[r, c] else SPACING * math.hypot(r - pr, c - pc) * 0.001
            stage[r, c] = max(8, cap[r, c], stage[pr, pc] + grade)
    return stage, distance, outlets


def join_nearby_water(water, forbidden, maximum_gap_m=160):
    """Author short confluences between captured pieces; never a cross-map canal."""
    labels, count = ndimage.label(water, np.ones((3, 3)))
    if count < 2:
        return water.copy(), []
    distance, nearest = ndimage.distance_transform_edt(~water, return_indices=True)
    owner = labels[tuple(nearest)]
    candidates = {}
    for dy, dx in [(0, 1), (1, 0)]:
        a = (slice(None, -1 if dy else None), slice(None, -1 if dx else None))
        b = (slice(dy, None), slice(dx, None))
        valid = (owner[a] != owner[b]) & (
            (distance[a] + distance[b] + 1) * SPACING <= maximum_gap_m
        )
        for r, c in np.argwhere(valid):
            rr, cc = int(r + dy), int(c + dx)
            start = (int(nearest[0, r, c]), int(nearest[1, r, c]))
            end = (int(nearest[0, rr, cc]), int(nearest[1, rr, cc]))
            left, right = int(labels[start]), int(labels[end])
            pair = tuple(sorted((left, right)))
            length = SPACING * math.hypot(start[0] - end[0], start[1] - end[1])
            if length <= maximum_gap_m and (
                pair not in candidates or length < candidates[pair][0]
            ):
                candidates[pair] = (length, start, end)
    parent = list(range(count + 1))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    result = water.copy()
    links = []
    for (left, right), (length, start, end) in sorted(
        candidates.items(), key=lambda x: (x[1][0], x[0])
    ):
        a, b = root(left), root(right)
        if a == b:
            continue
        path = source_walk(np.array([start[::-1], end[::-1]], float))
        if forbidden[tuple(path.T)].any():
            continue
        result[tuple(path.T)] = True
        parent[a] = b
        links.append({"from_rc": list(start), "to_rc": list(end), "length_m": length})
    return result, links


def section(distance_m, half_width_m, depth_m):
    """A broad thalweg with sloping sides, not a shallow painted water film."""
    return depth_m * np.maximum(0, 1 - (distance_m / (half_width_m + 16)) ** 2)


def capacity(area_km2, kind):
    minimum = 0.003 if kind == "stream" else 0.01
    return float(np.clip(0.008 * np.sqrt(max(0, area_km2)), minimum, 0.12))


def source_pool(ground, depth, levels, forbidden, source, design_depth=None):
    """Give the chosen source a deep inlet pool and a sloping connection.

    The retained source-radius model is a packing/design constraint, not a
    discharge measurement. A tunnel gap can limit the setting; it is never cut.
    """
    col = round((source["position"][0] + HALF) / SPACING)
    row = round((HALF - source["position"][2]) / SPACING)
    requested = math.floor(source["capacity"] * 65535 + 0.5)
    radius = 10 + 0.4 * math.sqrt(requested)
    extent = math.ceil((radius + 32) / SPACING)
    region = np.s_[
        max(0, row - extent) : min(ground.shape[0], row + extent + 1),
        max(0, col - extent) : min(ground.shape[1], col + extent + 1),
    ]
    yy, xx = np.mgrid[region]
    distance = np.hypot(yy - row, xx - col) * SPACING
    excluded = forbidden[region]
    setting = requested
    if excluded.any():
        clearance = float(distance[excluded].min()) - 0.01
        setting = min(setting, max(0, math.floor((max(0, clearance - 10) / 0.4) ** 2)))
    if setting < requested:
        source["requested_capacity"] = source["capacity"]
        source["capacity"] = setting / 65535
        source["output_capacity"] = min(
            source.get("output_capacity", source["capacity"]), setting / 65535
        )
    radius = 10 + 0.4 * math.sqrt(setting)
    pool_depth = 16 if source["class"] in ["lake", "ocean"] else 8
    wanted = pool_depth * np.clip((radius + 32 - distance) / 32, 0, 1)
    allowed_pool = (wanted > 0) & ~excluded
    seed = np.zeros(allowed_pool.shape, bool)
    centre = (row - region[0].start, col - region[1].start)
    if not allowed_pool[centre]:
        raise ValueError("An emitting source centre is outside its permitted pool")
    seed[centre] = True
    pool = ndimage.binary_propagation(
        seed, structure=np.ones((3, 3)), mask=allowed_pool
    )
    if design_depth is not None:
        design_depth[region][pool] = np.maximum(
            design_depth[region][pool], wanted[pool]
        )
    target = source["target"]
    bed = ground[region]
    bed[pool] = np.minimum(bed[pool], np.maximum(0, target - wanted[pool]))
    levels[region][pool] = target
    depth[region][pool] = np.maximum(0, target - bed[pool])
    core = distance <= radius
    source["footprint_pool"] = {
        "radius_model_m": radius,
        "pool_core_depth_m": pool_depth,
        "requested_native_rate": requested,
        "native_rate": setting,
        "minimum_authored_core_depth_m": float(depth[region][core].min()),
        "tunnel_gap_cells_changed": int((pool & excluded).sum()),
        "disconnected_apron_cells_not_authored": int((allowed_pool & ~pool).sum()),
    }


def source_walk(points):
    """Capture the whole clipped line at native resolution, not clipped endpoints."""
    parts = []
    for a, b in zip(points[:-1], points[1:], strict=True):
        count = max(1, int(np.ceil(np.max(np.abs(b - a)))))
        parts.append(np.linspace(a, b, count + 1))
    if not parts:
        return np.empty((0, 2), dtype=int)
    xy = np.rint(np.concatenate(parts)).astype(int)
    xy = xy[(xy[:, 0] >= 0) & (xy[:, 0] <= 1080) & (xy[:, 1] >= 0) & (xy[:, 1] <= 1080)]
    return xy[:, ::-1]


def cover_component_emitters(
    ground,
    depth,
    levels,
    forbidden,
    channel,
    contributing,
    classes,
    sources,
    design_depth,
):
    """Supply unsupplied physical components using only planned source fields."""
    added = []
    while True:
        labels, _ = ndimage.label(channel, np.ones((3, 3)))
        supplied = set()
        for source in sources:
            if (
                math.floor(
                    source.get("output_capacity", source["capacity"]) * 65535 + 0.5
                )
                <= 0
            ):
                continue
            col = round((source["position"][0] + HALF) / SPACING)
            row = round((HALF - source["position"][2]) / SPACING)
            supplied.add(int(labels[row, col]))
        missing = [i for i in range(1, int(labels.max()) + 1) if i not in supplied]
        if not missing:
            return added
        component = missing[0]
        eligible = (labels == component) & (depth >= 1) & ~forbidden
        candidates = np.flatnonzero(eligible)
        if not len(candidates):
            raise ValueError(
                "An unsupplied physical component has no planned depth>=1m inlet"
            )
        if len(sources) >= 65535:
            raise ValueError("Component inlets exceed the UInt16 source-table count")
        chosen = int(candidates[np.argmax(levels.ravel()[candidates])])
        row, col = divmod(chosen, ground.shape[1])
        kind = {1: "stream", 2: "river", 3: "lake", 4: "ocean"}[int(classes[row, col])]
        area = float(contributing[row, col])
        setting = max(0.01, capacity(area, kind))
        source = {
            "name": "physical component fallback inlet",
            "class": kind,
            "role": "component_fallback_inlet",
            "position": [int(col * SPACING - HALF), 0, int(HALF - row * SPACING)],
            "target": float(levels[row, col]),
            "capacity": setting,
            "output_capacity": setting,
            "local_catchment_km2": area,
            "catchment_scope": "map-local priority-flood D8 model; outside-frame inflow unknown",
        }
        source_pool(ground, depth, levels, forbidden, source, design_depth)
        if source["output_capacity"] <= 0:
            raise ValueError(
                "A component fallback inlet has no permitted emission setting"
            )
        added.append(len(sources))
        sources.append(source)
        channel |= depth > 0


def component_outlet_intakes(channel, depth, levels, ports, sources):
    """Add intake-only controls without changing any authored physical field.

    Summed settings are a declared control budget, not measured discharge.
    An intake may cover partially dry cells: it has no emission permission.
    """
    labels, count = ndimage.label(channel, np.ones((3, 3)))
    if sorted(p["component"] for p in ports) != list(range(1, count + 1)):
        raise ValueError(
            "Receiving ports must name every final joint-profile component once"
        )
    members = [[] for _ in range(count + 1)]
    for index, source in enumerate(sources):
        col = round((source["position"][0] + HALF) / SPACING)
        row = round((HALF - source["position"][2]) / SPACING)
        component = int(labels[row, col])
        if not component:
            raise ValueError(
                "A planned control is outside the final physical footprint"
            )
        members[component].append(index)
    additions, summaries = [], []
    for port in ports:
        component = port["component"]
        r, c = port["row"], port["col"]
        if port["role"] not in ("sea", "map_edge", "closed_component"):
            raise ValueError("An intake needs a supported final receiving-port role")
        if int(labels[r, c]) != component:
            raise ValueError(
                "A receiving port disagrees with final physical component labels"
            )
        target = float(levels[r, c])
        receiving_depth = target - (levels - depth)
        candidates = np.argwhere(
            (labels == component) & (depth >= 1) & (receiving_depth >= 1)
        )
        if not len(candidates):
            raise ValueError(
                f"Final physical component {component} has no legal receiving-stage intake anchor "
                "with planned and receiving-stage depth>=1m"
            )
        distances = (candidates[:, 0] - r) ** 2 + (candidates[:, 1] - c) ** 2
        row, col = map(int, candidates[int(np.argmin(distances))])
        outputs = [
            float(sources[i].get("output_capacity", sources[i]["capacity"]))
            for i in members[component]
        ]
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in outputs):
            raise ValueError("A component emission setting is outside supported [0,1]")
        packed_sum = sum(math.floor(v * 65535 + 0.5) for v in outputs)
        budget = max(1, packed_sum)
        records = (budget + 65534) // 65535
        if len(sources) + len(additions) + records > 65535:
            raise ValueError(
                "Component outlet controls exceed the UInt16 source-table count"
            )
        first = len(sources) + len(additions)
        receiving = {
            "namespace": "joint_profile.outlets",
            "component": component,
            "row": int(r),
            "col": int(c),
            "role": port["role"],
        }
        for replica in range(records):
            raw_setting = min(65535, budget - replica * 65535)
            additions.append(
                {
                    "name": "engineered receiving-port intake",
                    "class": "intake",
                    "role": "engineered_outlet_intake",
                    "position": [
                        int(np.clip(col * SPACING - HALF, -HALF, HALF)),
                        0,
                        int(np.clip(HALF - row * SPACING, -HALF, HALF)),
                    ],
                    "target": target,
                    "capacity": raw_setting / 65535,
                    "output_capacity": 0,
                    "receiving_port": receiving.copy(),
                    "outlet_kind": "engineered_closed_component_drain"
                    if port["role"] == "closed_component"
                    else port["role"],
                    "intake_footprint": "partial wet coverage permitted; emission disabled",
                }
            )
        summaries.append(
            {
                "receiving_port": receiving,
                "source_indices": members[component],
                "intake_indices": list(range(first, first + records)),
                "anchor_rc": [row, col],
                "anchor_planned_depth_m": float(depth[row, col]),
                "anchor_depth_at_receiving_stage_m": float(receiving_depth[row, col]),
                "receiving_stage_m": target,
                "summed_requested_output_settings": math.fsum(outputs),
                "summed_output_settings": packed_sum / 65535,
                "summed_output_raw_settings": packed_sum,
                "summed_packed_output_settings": packed_sum / 65535,
                "declared_intake_settings": budget / 65535,
                "declared_intake_raw_settings": budget,
                "intake_records": records,
                "scope": "control-setting budget, not calibrated hydraulic capacity",
            }
        )
    sources.extend(additions)
    return summaries


def hydrology(ground, banks, geometry):
    geometry, visibility = surface_geometry(geometry)
    sq = geometry["sq"]
    original = ground.copy()
    lines = geometry.get("rivers", []) + geometry.get("streams", [])
    line = raster(sq, lines)
    mapped_classes = np.zeros(ground.shape, np.uint8)
    mapped_classes[raster(sq, geometry.get("streams", []))] = 1
    mapped_classes[raster(sq, geometry.get("rivers", []))] = 2
    lakes = raster(sq, geometry.get("lakes", []), True)
    areas = raster(sq, geometry.get("riverAreas", []), True)
    ocean = raster(sq, geometry.get("oceans", []), True)
    mapped_classes[areas] = 2
    mapped_classes[lakes] = 3
    mapped_classes[ocean] = 4
    water = line | lakes | areas | ocean
    underground = raster(sq, geometry.get("undergroundWaterways", []))
    forbidden = ndimage.binary_dilation(underground, iterations=2) & ~water
    sources, samples, summaries = [], {}, []
    if not water.any():
        return np.zeros_like(ground), {
            "sources": [],
            "samples": {},
            "rivers": [],
            "sea_level_m": 0,
            "surface_water": visibility,
            "water_construction": "map-maker-v1",
            "outlets": [],
            "terrain_changed_cells": 0,
        }

    # Depression filling is a drainage MODEL only. It never changes land.
    contributing = local_catchment_area(banks, SPACING * sq.get("scale", 1)) / 1_000_000
    contributing = ndimage.maximum_filter(contributing, size=5)
    bank_level = ndimage.median_filter(banks, size=5)
    desired = np.clip(bank_level - 1.5, 2, 1020)
    sea = float(geometry.get("seaLevel") or 0)
    lake_labels, _ = ndimage.label(lakes, np.ones((3, 3)))
    for label, box in enumerate(ndimage.find_objects(lake_labels), 1):
        if box is None:
            continue
        own = lake_labels[box] == label
        level = float(np.clip(np.median(bank_level[box][own]) - 1.5, 2, 1020))
        desired[box][own] = max(sea, level) if sea else level
    desired[ocean] = sea
    water, links = join_nearby_water(water, forbidden)
    line |= water & ~(lakes | areas | ocean)
    stage, arc, outlets = stage_tree(water, desired, lakes | ocean, ocean)
    # A clipped/misconnected DEM branch must not drag a whole valley hundreds
    # of metres down. Keep channel surfaces in the local valley envelope;
    # replenishment supports separate cascades where the capture is imperfect.
    stage[water] = np.clip(stage[water], desired[water] - 12, desired[water] + 0.25)
    for label, box in enumerate(ndimage.find_objects(lake_labels), 1):
        if box is not None:
            own = lake_labels[box] == label
            stage[box][own] = desired[box][own]
    tidal = ndimage.binary_propagation(ocean, mask=water, structure=np.ones((3, 3)))
    stage[tidal] = np.maximum(stage[tidal], sea)

    # Original mapped open-water polygons keep their shapes. Channel width grows
    # with local catchment; reported width/rate settings remain authoring heuristics.
    line_distance, nearest_line = ndimage.distance_transform_edt(
        ~line, return_indices=True
    )
    local_area = (
        contributing[tuple(nearest_line)] if line.any() else np.zeros_like(ground)
    )
    half_width = np.clip(24 + 6 * np.sqrt(local_area), 24, 112)
    channel = (
        (line_distance * SPACING <= half_width) if line.any() else np.zeros_like(line)
    )
    body_margin = ndimage.binary_dilation(lakes | areas, iterations=1)
    channel |= water | body_margin
    channel &= ~forbidden
    _, nearest = ndimage.distance_transform_edt(~water, return_indices=True)
    level = stage[tuple(nearest)]
    channel_depth = 8 + np.clip(2 * np.log10(1 + local_area), 0, 8)
    depth = section(line_distance * SPACING, half_width, channel_depth)
    depth[~channel] = 0
    depth[body_margin & channel] = np.maximum(depth[body_margin & channel], 4)
    depth[lakes | areas] = np.maximum(depth[lakes | areas], 16)
    shore_distance = ndimage.distance_transform_edt(ocean) * SPACING
    depth[ocean] = np.clip(8 + shore_distance[ocean] * 0.06, 8, 24)
    design_depth = depth.copy()
    ground[channel] = np.minimum(
        original[channel], np.clip(level[channel] - depth[channel], 0, 1023)
    )
    depth[channel] = np.maximum(0, level[channel] - ground[channel])

    occupied = []

    def supply(row, col, name, kind, role, output=True, area=None):
        if not (4 <= row < ground.shape[0] - 4 and 4 <= col < ground.shape[1] - 4):
            return
        if not water[row, col] or depth[row, col] < 1:
            return
        if any((row - r) ** 2 + (col - c) ** 2 < 8**2 for r, c in occupied):
            return
        occupied.append((row, col))
        area = float(contributing[row, col]) if area is None else area
        setting = capacity(area, kind)
        sources.append(
            {
                "name": name,
                "class": kind,
                "role": role,
                "position": [int(col * 16 - HALF), 0, int(HALF - row * 16)],
                "target": float(stage[row, col]),
                "capacity": setting,
                "output_capacity": setting if output else 0,
                "local_catchment_km2": area,
                "catchment_scope": "map-local priority-flood D8 model; outside-frame inflow unknown",
            }
        )

    # Every original line is retained, including short visible streams. Sources
    # go at its upstream end in the AUTHORING tree, not at verification probes.
    for number, feature in enumerate(lines):
        points = np.asarray([pixel(sq, p) for p in feature["pts"]])
        if len(points) < 2:
            continue
        walk = source_walk(points)
        kind = "river" if number < len(geometry.get("rivers", [])) else "stream"
        summaries.append(
            {
                "name": feature.get("name") or "unnamed waterway",
                "class": kind,
                "source_row": number,
                "mapped_vertices": len(walk),
                "construction": "mapped raster channel"
                if len(walk)
                else "outside square",
            }
        )
        interior = walk[
            (walk[:, 0] >= 4)
            & (walk[:, 0] <= 1076)
            & (walk[:, 1] >= 4)
            & (walk[:, 1] <= 1076)
        ]
        if not len(interior):
            continue
        head = max(interior, key=lambda n: arc[tuple(n)])
        supply(
            int(head[0]),
            int(head[1]),
            feature.get("name") or f"waterway {number}",
            kind,
            "catchment_inlet",
        )
        key = f"{feature.get('name') or 'unnamed waterway'} [{kind}] #{number}"
        step = max(1, len(points) // 30)
        samples[key] = [
            [int(round(x) * 16 - HALF), 0, int(HALF - round(y) * 16)]
            for x, y in points[::step]
            if 0 <= x <= 1080 and 0 <= y <= 1080
        ]
    # Widely spaced replenishment follows the construction grid, independent of
    # sample points. This represents omitted lateral catchment, not per-node dams.
    for row in range(32, 1081, 64):
        for col in range(32, 1081, 64):
            box = line[max(0, row - 16) : row + 17, max(0, col - 16) : col + 17]
            if box.any():
                yy, xx = np.nonzero(box)
                at = int(np.argmin((yy - 16) ** 2 + (xx - 16) ** 2))
                supply(
                    row - 16 + int(yy[at]),
                    col - 16 + int(xx[at]),
                    "lateral catchment",
                    "river",
                    "lateral_inlet",
                )
    # Lakes/coastal shelf are maintained at their authored surface. These are
    # body controls, not fake geographic river discharges or new stream masks.
    for body, kind in [(lakes | areas, "lake"), (ocean, "ocean")]:
        labels, _ = ndimage.label(body, np.ones((3, 3)))
        for label, box in enumerate(ndimage.find_objects(labels), 1):
            if box is None:
                continue
            own = labels[box] == label
            yy, xx = np.nonzero(own)
            # One minimum control, then a320m lattice for large open bodies.
            at = int(np.argmin((yy - yy.mean()) ** 2 + (xx - xx.mean()) ** 2))
            locations = [(int(yy[at] + box[0].start), int(xx[at] + box[1].start))]
            locations += [
                (r, c)
                for r in range(box[0].start, box[0].stop, 20)
                for c in range(box[1].start, box[1].stop, 20)
                if labels[r, c] == label
            ]
            for r, c in locations:
                supply(
                    r,
                    c,
                    f"{kind} {label}",
                    kind,
                    "body_level",
                    area=max(4, float(own.sum()) * 256 / 1e6),
                )
    for port in outlets:
        if port["role"] == "closed_sink":
            supply(
                port["row"],
                port["col"],
                "captured terminal outlet",
                "river",
                "terminal_sink",
                output=False,
            )
    # Source flow must enter a bed at least as broad as its modeled footprint.
    # Select controls from the full mapped geometry first, not from dry probes.
    for source in sources:
        source_pool(ground, depth, level, forbidden, source, design_depth)
    channel |= depth > 0
    _, original_nearest = ndimage.distance_transform_edt(
        mapped_classes == 0, return_indices=True
    )
    fallback_inlets = cover_component_emitters(
        ground,
        depth,
        level,
        forbidden,
        channel,
        contributing,
        mapped_classes[tuple(original_nearest)],
        sources,
        design_depth,
    )
    # Emission cores are level inlet pools; the connecting reaches can descend
    # steeply outside them. A global gentle-grade cap would excavate mountains.
    flat_pools = lakes | ocean
    for source in sources:
        col = round((source["position"][0] + HALF) / SPACING)
        row = round((HALF - source["position"][2]) / SPACING)
        radius = source["footprint_pool"]["radius_model_m"]
        extent = math.ceil(radius / SPACING)
        region = np.s_[
            max(0, row - extent) : min(1081, row + extent + 1),
            max(0, col - extent) : min(1081, col + extent + 1),
        ]
        yy, xx = np.mgrid[region]
        flat_pools[region] |= (
            np.hypot(yy - row, xx - col) * SPACING <= radius
        ) & channel[region]
    # Extend source-derived valley heights across each expanded cross-section;
    # widened shoulders must not lift the stream to the adjacent hillside.
    preferred = desired[tuple(nearest)]
    level, joint_profile = connected_surface(channel, preferred, flat_pools, ocean, sea)
    head_q = np.zeros(ground.shape, np.int32)
    head_q[channel] = np.floor(level[channel] * 64 + 0.5).astype(np.int32)
    bed_q = np.minimum(
        np.floor(original[channel] * 64 + 0.5).astype(np.int32),
        head_q[channel] - np.ceil(design_depth[channel] * 64).astype(np.int32),
    ).clip(0, 65535)
    ground[channel] = bed_q / 64
    depth[channel] = (head_q[channel] - bed_q) / 64
    for source in sources:
        col = round((source["position"][0] + HALF) / SPACING)
        row = round((HALF - source["position"][2]) / SPACING)
        source["target"] = float(level[row, col])
        radius = source["footprint_pool"]["radius_model_m"]
        extent = math.ceil(radius / SPACING)
        region = np.s_[
            max(0, row - extent) : min(1081, row + extent + 1),
            max(0, col - extent) : min(1081, col + extent + 1),
        ]
        yy, xx = np.mgrid[region]
        core = np.hypot(yy - row, xx - col) * SPACING <= radius
        source["footprint_pool"]["minimum_authored_core_depth_m"] = float(
            depth[region][core].min()
        )
        if source["footprint_pool"]["minimum_authored_core_depth_m"] < 1:
            raise ValueError(
                "The joint profile leaves a source footprint shallower than1m"
            )
    outside_distance, near_water = ndimage.distance_transform_edt(
        ~channel, return_indices=True
    )
    near_level = level[tuple(near_water)]
    # An underground reach is not initialized as surface water. It is not a
    # prohibition on dry bank earthworks beside a mapped surface channel.
    bank_strip = ~channel & (outside_distance <= 4)
    blend = np.clip((5 - outside_distance) / 4, 0, 1)
    raised = near_level + 2.0
    ground[bank_strip] = np.maximum(
        ground[bank_strip],
        original[bank_strip]
        + blend[bank_strip] * np.maximum(0, raised[bank_strip] - original[bank_strip]),
    )
    rim = ~channel & (outside_distance <= 1.5)
    adjacent_head = ndimage.maximum_filter(np.where(channel, level, -np.inf), size=3)
    ground[rim] = np.maximum(ground[rim], adjacent_head[rim] + 2)
    ground[channel | bank_strip] = np.clip(ground[channel | bank_strip], 0, 65535 / 64)
    functional_components = component_outlet_intakes(
        channel, depth, level, joint_profile["outlets"], sources
    )
    changed = np.abs(ground - original) > 1 / 64
    return depth, {
        "sources": sources,
        "samples": samples,
        "rivers": summaries,
        "sea_level_m": sea,
        "surface_water": visibility,
        "water_construction": "map-maker-v5-component-supply-outlets",
        "joint_profile": joint_profile,
        "fallback_inlet_indices": fallback_inlets,
        "functional_water_components": functional_components,
        "unmodeled_short_surface_reaches": [],
        "authored_confluence_links": links,
        "channel_design": {
            "minimum_depth_m": 8,
            "half_width_m": [24, 112],
            "minimum_grade": 0.001,
            "bank_freeboard_m": 2,
            "shore_blend_m": 64,
            "lake_depth_m": 16,
            "shelf_depth_m": [8, 24],
        },
        "catchment_model": "map-local priority-flood D8 area; capacity setting=0.008*sqrt(km2), bounded by feature class, not calibrated discharge",
        "outlets": outlets,
        "outlets_scope": "pre-expansion stage_tree components; final ports use joint_profile.outlets",
        "terrain_changed_cells": int(changed.sum()),
        "maximum_cut_m": float(np.maximum(0, original - ground).max()),
        "maximum_bank_raise_m": float(np.maximum(0, ground - original).max()),
        "away_land_changed_cells": int(
            (changed & ~channel & (outside_distance > 4)).sum()
        ),
        "initialized_water_cells": int((depth > 0.1).sum()),
    }
