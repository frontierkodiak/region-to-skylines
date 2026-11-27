"""Engineered receiving paths from source geometry and pre-water terrain.

D8 parents and channel trees specify authoring, not observed hydraulic flow.
No native outcomes, names, or replacement source geometry select these paths.
"""

from collections import deque

import numpy as np
from scipy import ndimage

from catchment import priority_flood_drainage

NEIGHBORS = [(-1, 0), (0, -1), (0, 1), (1, 0)]


def connect_channels(line, river_area, ocean, lakes, ground, spacing=16):
    """Join only bounded terrain-drainage gaps to existing mapped receivers.

    At most 2,048 m of D8 path, within 128 m of captured water geometry. A path
    must meet an already edge/sea-connected network: reaching an arbitrary map
    edge does not qualify. Unsupported reaches remain in the report, dry.
    """
    shape = line.shape
    edge = np.zeros(shape, bool)
    edge[[0, -1], :] = True
    edge[:, [0, -1]] = True
    network = line | river_area | ocean
    labels, count = ndimage.label(network, np.ones((3, 3)))
    receiving_ids = np.unique(labels[network & (edge | ocean)])
    receiving_ids = receiving_ids[receiving_ids != 0]
    fed = np.isin(labels, receiving_ids) & network
    near = ndimage.distance_transform_edt(~(network | lakes)) * spacing <= 128
    records, pending = [], []
    for identity, region in enumerate(ndimage.find_objects(labels), 1):
        local = (labels[region] == identity) & line[region]
        rr, cc = np.nonzero(local)
        if not len(rr):
            continue
        nodes = (rr + region[0].start) * shape[1] + cc + region[1].start
        record = {"source_component": identity, "mapped_line_nodes": len(nodes)}
        records.append(record)
        if identity in receiving_ids:
            record["route"] = "existing fed channel"
        else:
            pending.append((identity, nodes, record))
    drainage = (
        priority_flood_drainage(ground, spacing) if pending and fed.any() else None
    )
    added = np.zeros(shape, bool)
    if drainage is not None:
        height, raw = drainage.filled_elevation.ravel(), ground.ravel()
        while pending:
            left, changed = [], False
            for identity, nodes, record in pending:
                start = min(nodes, key=lambda i: (height[i], raw[i], int(i)))
                path, current, length = [], int(start), 0.0
                while current != -1 and length <= 2048:
                    if fed.ravel()[current]:
                        break
                    if not near.ravel()[current]:
                        current = -1
                        break
                    path.append(current)
                    parent = int(drainage.parent.ravel()[current])
                    if parent != -1:
                        r, c = divmod(current, shape[1])
                        pr, pc = divmod(parent, shape[1])
                        length += spacing * np.hypot(pr - r, pc - c)
                    current = parent
                if current != -1 and length <= 2048 and fed.ravel()[current]:
                    added.ravel()[path] = True
                    fed[labels == identity] = True
                    fed.ravel()[path] = True
                    record.update(
                        route="connected to fed channel",
                        connection_length_m=float(length),
                        connection_row_cols=[
                            list(divmod(i, shape[1])) for i in path + [current]
                        ],
                    )
                    changed = True
                else:
                    left.append((identity, nodes, record))
            pending = left
            if not changed:
                break
    for _, _, record in pending:
        record.update(route="dry ground/marsh", reason="no bounded receiving path")
    active = (line & fed) | added
    return active, records, None if drainage is None else drainage.area


def continuous_stage(mask, ceiling, receiving=None):
    """A variable, non-increasing receiving-tree potential under every ceiling.

    The lowest literal edge cell roots each component. Children drain toward
    parents. Upstream ceilings propagate to ancestors before any bed is cut;
    unlike independent local levels, no selected tree edge climbs downstream.
    """
    labels, _ = ndimage.label(mask)
    receiving = np.zeros_like(mask) if receiving is None else receiving
    result = ceiling.copy()
    rows, cols = mask.shape
    parent = np.full(mask.size, -2, dtype=np.int64)
    # Compensate float representation noise only, far below one native quantum.
    values = np.floor(np.maximum(0, ceiling).ravel() * 64 + 1e-9).astype(np.int64)
    reports = []
    for identity, region in enumerate(ndimage.find_objects(labels), 1):
        local = labels[region] == identity
        rr, cc = np.nonzero(local)
        indices = (rr + region[0].start) * cols + cc + region[1].start
        boundary = [
            int(i)
            for i in indices
            if i // cols in (0, rows - 1)
            or i % cols in (0, cols - 1)
            or receiving.ravel()[i]
        ]
        if not boundary:
            reports.append(
                {"component": identity, "status": "no literal receiving edge"}
            )
            continue
        root = min(boundary, key=lambda i: (values[i], i))
        parent[root] = -1
        queue, order = deque([root]), []
        while queue:
            current = queue.popleft()
            order.append(current)
            r, c = divmod(current, cols)
            for dr, dc in NEIGHBORS:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    neighbor = nr * cols + nc
                    if parent[neighbor] == -2 and labels[nr, nc] == identity:
                        parent[neighbor] = current
                        queue.append(neighbor)
        assert len(order) == len(indices)
        for current in reversed(order):
            if parent[current] != -1:
                values[parent[current]] = min(values[parent[current]], values[current])
        result.ravel()[indices] = values[indices] / 64
        reports.append(
            {
                "component": identity,
                "status": "continuous receiving tree",
                "nodes": len(order),
                "outlet_row_col": list(divmod(root, cols)),
                "lowered_stage_nodes": int(
                    (result.ravel()[indices] < ceiling.ravel()[indices]).sum()
                ),
                "stage_range_m": [
                    float(values[indices].min() / 64),
                    float(values[indices].max() / 64),
                ],
            }
        )
    return result, reports
