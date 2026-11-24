"""One authored surface on the complete physical water footprint.

This is a map-making profile, not inferred geographic flow or a hydraulic solver.
Lakes/ocean are level bodies; channels get a downhill route to the selected port.
"""

import heapq
import math

import numpy as np
from scipy import ndimage, sparse
from scipy.sparse.csgraph import dijkstra

SPACING = 16
MIN_GRADE = 0.001
MAX_GRADE = 0.02
HEAD_CEILING = 1021.0  # Leaves the authored2m bank below the terrain limit.


def connected_surface(mask, preferred, flat, ocean, sea_level):
    """Fit a continuous surface, then drain its depressions toward explicit ports.

    Preferred DEM heights are soft authoring targets. The Lipschitz minorant
    removes abrupt head seams without raising a low neighbouring water surface.
    A minimum-slope priority flood then joins each component to its receiving
    port. No independent local clipping or source-disk level reset follows.
    """
    if mask.ndim != 2 or not mask.any() or preferred.shape != mask.shape:
        raise ValueError(
            "A nonempty physical footprint and matching heights are required"
        )
    if not np.isfinite(preferred[mask]).all():
        raise ValueError("Preferred water heights must be finite")
    flat = flat & mask
    ocean = ocean & mask
    if ocean.any() and not (0 < sea_level < HEAD_CEILING):
        raise ValueError("The ocean plane needs positive depth and bank headroom")
    components, component_count = ndimage.label(mask, np.ones((3, 3)))
    bodies, body_count = ndimage.label(flat, np.ones((3, 3)))
    ids = np.full(mask.shape, -1, np.int32)
    ids[flat] = bodies[flat] - 1
    ordinary = mask & ~flat
    ids[ordinary] = body_count + np.arange(ordinary.sum(), dtype=np.int32)
    count = int(ids.max()) + 1

    desired = np.clip(preferred, 2, 1020).copy()
    tidal_ids = np.unique(components[ocean])
    if len(tidal_ids):
        desired[np.isin(components, tidal_ids)] = np.maximum(
            desired[np.isin(components, tidal_ids)], sea_level
        )
        desired[ocean] = sea_level
    preferred_node = np.full(count, np.inf)
    np.minimum.at(preferred_node, ids[mask], desired[mask])

    rows, cols, lengths = [], [], []
    for dy, dx in [(0, 1), (1, -1), (1, 0), (1, 1)]:
        a = (slice(0, -dy or None), slice(1, None) if dx < 0 else slice(0, -dx or None))
        b = (slice(dy, None), slice(0, -1) if dx < 0 else slice(dx, None))
        left, right = ids[a], ids[b]
        valid = (left >= 0) & (right >= 0) & (left != right)
        u, v = left[valid], right[valid]
        rows.extend([u, v])
        cols.extend([v, u])
        length = SPACING * math.hypot(dy, dx)
        lengths.extend([np.full(len(u), length), np.full(len(u), length)])
    row = np.concatenate(rows).astype(np.int64)
    col = np.concatenate(cols).astype(np.int64)
    length = np.concatenate(lengths)
    # A contracted body can touch a channel node several times. Keep the
    # shortest physical edge, not scipy's default sum of duplicate entries.
    key = row * count + col
    order = np.argsort(key, kind="stable")
    unique, first = np.unique(key[order], return_index=True)
    length = np.minimum.reduceat(length[order], first) if len(first) else length
    row, col = unique // count, unique % count
    graph = sparse.csr_matrix((length, (row, col)), shape=(count, count))
    source_row = np.concatenate([row, np.full(count, count)])
    source_col = np.concatenate([col, np.arange(count)])
    costs = np.concatenate([length * MAX_GRADE, preferred_node])
    fit_graph = sparse.csr_matrix(
        (costs, (source_row, source_col)), shape=(count + 1, count + 1)
    )
    fitted = dijkstra(fit_graph, directed=True, indices=count)[:count]

    edge = np.zeros(mask.shape, bool)
    edge[[0, -1], :] = True
    edge[:, [0, -1]] = True
    representatives = np.full(count, mask.size, np.int64)
    np.minimum.at(representatives, ids[mask], np.flatnonzero(mask))
    heights = np.full(count, np.inf)
    parent = np.full(count, -1, np.int32)
    queue = []
    outlets = []
    groups = []
    for component, box in enumerate(ndimage.find_objects(components), 1):
        own = components[box] == component
        nodes = np.unique(ids[box][own])
        receiving = ocean[box] & own
        boundary = edge[box] & own
        candidates = (
            receiving if receiving.any() else boundary if boundary.any() else own
        )
        choices = np.unique(ids[box][candidates])
        seeds = (
            choices if receiving.any() else [int(choices[np.argmin(fitted[choices])])]
        )
        role = (
            "sea"
            if receiving.any()
            else "map_edge"
            if boundary.any()
            else "closed_component"
        )
        for node in seeds:
            heights[node] = fitted[node]
            heapq.heappush(queue, (float(heights[node]), int(node)))
        root = int(seeds[0])
        locations = np.argwhere(candidates & (ids[box] == root))
        r, c = (
            int(locations[0, 0] + box[0].start),
            int(locations[0, 1] + box[1].start),
        )
        outlets.append({"row": r, "col": c, "role": role, "component": component})
        groups.append((nodes, float(fitted[root])))
    while queue:
        height, node = heapq.heappop(queue)
        if height != heights[node]:
            continue
        lo, hi = graph.indptr[node : node + 2]
        for neighbour, distance in zip(
            graph.indices[lo:hi], graph.data[lo:hi], strict=True
        ):
            proposed = max(
                float(fitted[neighbour]), height + MIN_GRADE * float(distance)
            )
            if proposed < heights[neighbour]:
                heights[neighbour] = proposed
                parent[neighbour] = node
                heapq.heappush(queue, (proposed, int(neighbour)))
    if not np.isfinite(heights).all():
        raise ValueError("A physical water component has no authored receiving port")

    # Fit a whole component into CS1's vertical range if necessary. A uniform
    # compression preserves junctions, lakes, ordering and the pinned sea plane.
    compression = []
    for nodes, base in groups:
        high = float(heights[nodes].max())
        factor = min(1.0, (HEAD_CEILING - base) / (high - base)) if high > base else 1.0
        heights[nodes] = base + factor * (heights[nodes] - base)
        compression.append(factor)
    quantized = np.floor(heights * 64 + 0.5 + 1e-8).astype(np.int32)
    adverse = int((quantized[parent[parent >= 0]] > quantized[parent >= 0]).sum())
    maximum_jump = int(np.abs(quantized[row] - quantized[col]).max()) if len(row) else 0
    result = np.full(mask.shape, np.nan)
    result[mask] = quantized[ids[mask]] / 64
    return result, {
        "method": "joint-physical-footprint-v1",
        "preferred_minimum_authored_grade": MIN_GRADE,
        "maximum_fitted_grade": MAX_GRADE,
        "physical_footprint_cells": int(mask.sum()),
        "model_components": component_count,
        "level_body_components": body_count,
        "packed_adverse_downstream_edges": adverse,
        "maximum_packed_adjacent_head_jump_m": maximum_jump / 64,
        "minimum_vertical_compression_factor": min(compression),
        "outlets": outlets,
        "scope": "Authored physical topology, not measured geographic communication, direction or capacity",
    }
