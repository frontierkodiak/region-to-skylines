"""Reference-only water cohorts from complete serialized stock water surfaces.

Stock packages do not contain our OSM feature inventory. Their saved water is
the authored reference, not a claim about every real-world waterway. Export
references keep their original, independent geographic contracts.
"""

from collections import defaultdict

import numpy as np
from scipy import ndimage


def stock_cohort(depth_q, definition_sha256):
    """Keep every saved >0.1 m body, with <=512 m sectors and 64 m probes.

    Native rows are south-first. Large body interiors use the historical
    body's >32 m erosion and 64 m lattice. Every thin/small component without
    an interior sample retains its deepest-in-mask-distance node, not omission.
    The saved input, never a new native outcome, selects this cohort.
    """
    depth = np.asarray(depth_q)
    if depth.ndim != 2 or depth.shape[0] != depth.shape[1]:
        raise ValueError("Expected square native depth grid")
    n = depth.shape[0]
    wet = depth >= 7
    labels, count = ndimage.label(wet, np.ones((3, 3)))
    entries, points = [], []
    for component, region in enumerate(ndimage.find_objects(labels), 1):
        local = labels[region] == component
        distance = ndimage.distance_transform_edt(np.pad(local, 1))[1:-1, 1:-1]
        rows, cols = np.nonzero(local & (distance > 2))
        rows, cols = rows + region[0].start, cols + region[1].start
        keep = (rows % 4 == 0) & (cols % 4 == 0)
        rows, cols = rows[keep], cols[keep]
        if not len(rows):
            r, c = np.unravel_index(np.argmax(distance), distance.shape)
            rows, cols = [r + region[0].start], [c + region[1].start]
        sectors = defaultdict(list)
        for row, col in zip(rows, cols):
            sectors[int(row) // 32, int(col) // 32].append((int(row), int(col)))
        contracts = []
        for (sr, sc), nodes in sorted(sectors.items()):
            identity = f"stock-body:{component}:sector:{sr}:{sc}"
            coords, names = [], []
            for i, (row, col) in enumerate(nodes):
                x, z = (col - n // 2) * 16, (row - n // 2) * 16
                name = f"{identity}:{i}"
                coords.append([x, z])
                names.append(name)
                points.append({"name": name, "x": x, "z": z})
            contracts.append(
                {
                    "id": identity,
                    "kind": "natural",
                    "points_xz": coords,
                    "probe_names": names,
                }
            )
        entries.append(
            {
                "id": f"stock-body:{component}",
                "status": "serialized_stock_water",
                "saved_wet_nodes": int(local.sum()),
                "contracts": contracts,
            }
        )
    assert len(entries) == count
    return {
        "schema": "stock-surface-reference-v1",
        "definition_sha256": definition_sha256,
        "coverage_complete": True,
        "coverage_scope": "Every component of serialized depth>=7q; not an OSM inventory",
        "entries": entries,
        "points": points,
    }
