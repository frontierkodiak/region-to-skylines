"""Read-only, standard-library audit of retained water-calibration failures.

No game launch, package rewrite, or simulation inference. Native arrays use
world z = row * 16 - 8640; exporter/image arrays use the opposite row order.
"""

import argparse
import array
from collections import Counter, deque
import hashlib
import json
import math
from pathlib import Path

N = 1081
CELL = 16


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def grid(path):
    values = array.array("H")
    values.frombytes(path.read_bytes())
    if __import__("sys").byteorder != "little":
        values.byteswap()
    if len(values) != N * N:
        raise ValueError(f"Invalid grid: {path.name}")
    return values


def neighbors(index):
    row, col = divmod(index, N)
    if row:
        yield index - N
    if row < N - 1:
        yield index + N
    if col:
        yield index - 1
    if col < N - 1:
        yield index + 1


def world(index):
    row, col = divmod(index, N)
    return col * CELL - 8640, row * CELL - 8640


def audit(root, square):
    slug = square["slug"]
    native, staged = root / "native" / slug, root / "staged" / slug
    paths = [
        staged / "hydrology.json",
        native / "report.json",
        native / "verdict.json",
        native / "reference-water.u16",
        native / "mapped-water.u8",
        native / "grids/t000-water-ground.u16",
    ]
    hydro, report, verdict = [json.loads(p.read_text()) for p in paths[:3]]
    sources = hydro["sources"]
    flood = next(c["value"] for c in verdict["checks"] if c["name"] == "no_flooding")
    worst = max(flood["grids"], key=lambda g: g["km2"])
    worst_path = native / "grids" / worst["grid"]
    paths.append(worst_path)
    reference, mask = grid(paths[3]), paths[4].read_bytes()
    if len(mask) != N * N or any(v not in (0, 1) for v in mask):
        raise ValueError("Invalid mapped mask")
    near = bytearray(N * N)
    offsets = [
        (y, x) for y in range(-8, 9) for x in range(-8, 9) if x * x + y * y <= 64
    ]
    for index, (depth, mapped) in enumerate(zip(reference, mask)):
        if depth <= 6 and not mapped:
            continue
        row, col = divmod(index, N)
        for dy, dx in offsets:
            if 0 <= row + dy < N and 0 <= col + dx < N:
                near[(row + dy) * N + col + dx] = 1
    water = grid(worst_path)
    far = {i for i, depth in enumerate(water) if depth > 32 and not near[i]}
    all_far = far.copy()
    components = []
    while far:
        queue = [far.pop()]
        for index in queue:
            for adjacent in neighbors(index):
                if adjacent in far:
                    far.remove(adjacent)
                    queue.append(adjacent)
        components.append(queue)
    spatial = []
    for component in sorted(components, key=len, reverse=True)[:4]:
        x = sum(world(i)[0] for i in component) / len(component)
        z = sum(world(i)[1] for i in component) / len(component)
        nearest = sorted(
            sources,
            key=lambda s: math.hypot(s["position"][0] - x, s["position"][2] - z),
        )[:3]
        spatial.append(
            {
                "cells": len(component),
                "centroid_world_xz": [round(x, 1), round(z, 1)],
                "nearest_controls": [
                    {
                        **s,
                        "centroid_distance_m": round(
                            math.hypot(s["position"][0] - x, s["position"][2] - z), 1
                        ),
                    }
                    for s in nearest
                ],
            }
        )
    floor = grid(paths[5])
    reservoirs = []
    for source in sources:
        if source["class"] != "reservoir":
            continue
        x, _, z = source["position"]
        row, col = round((z + 8640) / CELL), round((x + 8640) / CELL)
        center = row * N + col
        target = source["target"] * 64
        visited = {center} if floor[center] < target else set()
        queue = deque(visited)
        while queue:
            index = queue.popleft()
            for adjacent in neighbors(index):
                if adjacent not in visited and floor[adjacent] < target:
                    visited.add(adjacent)
                    queue.append(adjacent)
        ring = [
            floor[(row + dy) * N + col + dx] / 64
            for dy in range(-6, 7)
            for dx in range(-6, 7)
            if 36 <= dy * dy + dx * dx < 49 and 0 <= row + dy < N and 0 <= col + dx < N
        ]
        reservoirs.append(
            {
                "position": source["position"],
                "target_m": source["target"],
                "native_center_floor_m": floor[center] / 64,
                "nominal_96m_rim_min_floor_m": min(ring),
                "below_target_connected_cells": len(visited),
                "below_target_connected_flood_cells": len(visited & all_far),
                "below_target_max_reach_m": round(
                    max(
                        (math.hypot(world(i)[0] - x, world(i)[1] - z) for i in visited),
                        default=0,
                    ),
                    1,
                ),
                "interpretation": "Static four-neighbor floor connectivity below target, not actual flow or causal proof.",
            }
        )
    return {
        "slug": slug,
        "hashes": {str(p.relative_to(root)): sha(p) for p in paths},
        "labels": square["labels"],
        "source_classes": dict(Counter(s["class"] for s in sources)),
        "source_design_rate_sums_not_flux": {
            "intake": sum(s["capacity"] for s in sources),
            "output": sum(s.get("output_capacity", s["capacity"]) for s in sources),
        },
        "native_curve_13_samples": report["curve"],
        "native_water_summary": report["water"],
        "flood_grids": flood["grids"],
        "worst_flood_cells_recomputed": len(all_far),
        "worst_flood_km2_recomputed": round(len(all_far) * CELL * CELL / 1e6, 4),
        "components": spatial,
        "reservoir_floor_connectivity": reservoirs,
        "drying_evidence": {
            k: square.get(k)
            for k in [
                "required",
                "required_wet_end",
                "initialized_observations",
                "initialized_water_loss_end",
                "exact_point_wet_loss_end",
            ]
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    score = args.root / "staged/holdout-score.json"
    squares = json.loads(score.read_text())["squares"]
    print(
        json.dumps(
            {
                "holdout_score_sha256": sha(score),
                "limits": "Observed retained artifacts only; proximity and static connectivity do not establish source flux or causation.",
                "failures": [
                    audit(args.root, s)
                    for s in squares
                    if s.get("labels", {}).get("flood")
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
