"""Bounded observational flood regions; no solver or map-acceptance changes.

Uses the existing original-mask flood predicate. A region is diagnostic, not
an exemption from the whole-map gate. Transport is net local storage change,
not reconstructed flux through individual cell faces.
"""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path

import numpy as np

from . import verdict
from .watertrace import footprint

N = verdict.GRID_N


def flood_mask(depth_units, reference_units, mapped):
    expected = (reference_units / 64 > verdict.WET_M) | np.asarray(mapped, dtype=bool)
    near = verdict.dilate(expected, int(verdict.MAP_SOAK["flood_distance_m"] / verdict.CELL_M))
    return (depth_units / 64 > verdict.MAP_SOAK["flood_depth_m"]) & ~near


def components(mask):
    """Eight-connected diagnostic components; does not alter the gate mask."""
    remaining = set(map(tuple, np.argwhere(mask)))
    result = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        found, pending = [seed], deque([seed])
        while pending:
            z, x = pending.popleft()
            for dz in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    p = z + dz, x + dx
                    if p in remaining:
                        remaining.remove(p)
                        pending.append(p)
                        found.append(p)
        result.append(sorted(found))
    return sorted(result, key=lambda c: (-len(c), c[0]))


def source_footprint(control):
    nodes = set()
    for direction in ["input", "output"]:
        position, rate = control[direction], control[direction + "_rate"]
        if not rate:
            continue
        reach = int(np.ceil((0.4 * np.sqrt(rate) + 10) / 16)) + 1
        cx, cz = [int(round((position[i] + 8640) / 16)) for i in [0, 2]]
        z, x = np.mgrid[max(0, cz - reach) : min(N, cz + reach + 1), max(0, cx - reach) : min(N, cx + reach + 1)]
        xy = np.column_stack([x.ravel() * 16 - 8640, z.ravel() * 16 - 8640])
        inside = footprint(xy, position, rate)
        nodes.update((int(iz), int(ix)) for iz, ix in zip(z.ravel()[inside], x.ravel()[inside]))
    return nodes


def halo(nodes):
    return {
        (z + dz, x + dx)
        for z, x in nodes
        for dz in [-1, 0, 1]
        for dx in [-1, 0, 1]
        if 0 <= z + dz < N and 0 <= x + dx < N
    }


def close_region(seed, controls, max_nodes=512, max_sources=32):
    """Include complete footprints of every touching source to a fixed point."""
    region = halo(set(map(tuple, seed)))
    disks = [source_footprint(c) for c in controls]
    touched = set()
    while True:
        added = {i for i, disk in enumerate(disks) if disk & region} - touched
        if not added:
            break
        touched |= added
        for i in added:
            if controls[i]["type"] != 1:
                raise ValueError(f"unsupported touching source type at {i + 1}")
            region |= halo(disks[i])
        if len(region) > max_nodes or len(touched) > max_sources:
            raise ValueError(f"complete closure exceeds bounds: {len(region)} nodes / {len(touched)} sources")
    if not 0 < len(region) <= max_nodes or len(touched) > max_sources:
        raise ValueError(f"region exceeds bounds: {len(region)} nodes / {len(touched)} sources")
    return [[int(x * 16 - 8640), int(z * 16 - 8640)] for z, x in sorted(region)], [i + 1 for i in sorted(touched)]


def area_depth(mask, depth_units):
    values = depth_units[mask].astype(float) / 64
    z, x = np.nonzero(mask)
    return {
        "cells": int(mask.sum()),
        "area_km2": int(mask.sum()) * 0.000256,
        "max_depth_m": float(values.max()) if len(values) else 0,
        "mean_depth_m": float(values.mean()) if len(values) else 0,
        "bounds_xz": [
            int(x.min() * 16 - 8640),
            int(z.min() * 16 - 8640),
            int(x.max() * 16 - 8640),
            int(z.max() * 16 - 8640),
        ]
        if len(x)
        else None,
    }


def storage_budget(header, records, selected=None):
    """Exact local published budget, including delayed publications explicitly."""
    n = len(header["nodes"])
    selected = np.ones(n, bool) if selected is None else np.asarray(selected, dtype=bool)

    def cells(value):
        return np.asarray(value[: n * 4], dtype=np.int64).reshape(n, 4)[:, 0]

    initial = int(cells(records[0]["published"])[selected].sum())
    final = int(cells(records[-1]["published_end"])[selected].sum())
    transport, removed, supplied, unpublished = 0, 0, 0, 0
    sources = {}
    for r in records:
        # Only the working buffer that actually publishes can be telescoped
        # into the published endpoint budget. Never count an unpublished pass.
        if r["published_buffer"] != r["working_buffer"]:
            unpublished += 1
            continue
        transport += int((cells(r["transport"]) - cells(r["published"]))[selected].sum())
        for s in r["sources"]:
            take = int((cells(s["pre_cells"]) - cells(s["input_cells"]))[selected].sum())
            give = int((cells(s["post_cells"]) - cells(s["input_cells"]))[selected].sum())
            row = sources.setdefault(s["id"], {"removed": 0, "supplied": 0})
            row["removed"] += take
            row["supplied"] += give
            removed += take
            supplied += give
    residual = final - (initial + transport + supplied - removed)
    return {
        "units": "native depth-sum (1/64 m per grid node), not m3/s",
        "initial": initial,
        "final": final,
        "net_transport_in": transport,
        "source_input": removed,
        "source_output": supplied,
        "residual": residual,
        "closes": residual == 0,
        "unpublished_updates_excluded": unpublished,
        "sources": sources,
        "whole_face_flux_derived": False,
    }


def transport_overlap(mask, segments):
    """Conservative native segment-bounds overlap, not a path-blockage verdict."""
    z, x = np.nonzero(mask)
    points = np.column_stack([x * 16 - 8640, z * 16 - 8640])
    overlaps, nearest = [], None
    for segment in segments:
        center, size = segment.get("bounds_center"), segment.get("bounds_size")
        if center is None or size is None:
            raise ValueError("native transport segment is missing bounds")
        lo = np.array(center)[[0, 2]] - np.array(size)[[0, 2]] / 2
        hi = np.array(center)[[0, 2]] + np.array(size)[[0, 2]] / 2
        if len(points):
            delta = np.maximum(np.maximum(lo - (points + 8), (points - 8) - hi), 0)
            distance = float(np.linalg.norm(delta, axis=1).min())
            if nearest is None or distance < nearest["distance_m"]:
                nearest = {"segment": segment["id"], "prefab": segment["prefab"], "distance_m": distance}
            if distance == 0:
                overlaps.append({"segment": segment["id"], "prefab": segment["prefab"], "flags": segment["flags"]})
    return {
        "method": "16m flood-cell squares versus native horizontal segment bounds; conservative, not road flooding or blockage proof",
        "overlaps": overlaps,
        "nearest": nearest,
    }


def report(run, reference, mapped, plan, hydrology):
    """Re-audit collected native grids/trace, retaining the whole-map mask."""
    from .watertrace import audit

    def raw(path):
        return np.fromfile(path, "<u2").reshape(N, N)

    audit_result = audit(run / "atomic-trace/trace.jsonl", run / "session-receipt.json")
    if not audit_result["passes"]:
        raise ValueError(f"native source trace failed its audit: {audit_result['errors']}")
    header, *records = [json.loads(line) for line in (run / "atomic-trace/trace.jsonl").read_text().splitlines()]
    original, hydro = json.loads(plan.read_text()), json.loads(hydrology.read_text())
    ref = raw(reference)
    mask = np.fromfile(mapped, "u1").reshape(N, N).astype(bool)
    region = np.zeros((N, N), bool)
    nodes = np.array(header["nodes"])
    region[(nodes[:, 1] + 8640) // 16, (nodes[:, 0] + 8640) // 16] = True
    seed = np.zeros_like(region)
    for x, z in original["component_xz"]:
        seed[(z + 8640) // 16, (x + 8640) // 16] = True
    tile = hydro["start_area"]
    cx, cz = (tile["x"] - 2) * 1920, (tile["z"] - 2) * 1920
    yy, xx = np.mgrid[:N, :N]
    start = (abs(xx * 16 - 8640 - cx) < 960) & (abs(yy * 16 - 8640 - cz) < 960)
    epochs = []
    for label in ["t015", "t020"]:
        values = raw(run / f"grids/{label}-water.u16")
        flood = flood_mask(values, ref, mask)
        associated = np.zeros_like(flood)
        for component in components(flood):
            z, x = np.array(component).T
            if seed[z, x].any():
                associated[z, x] = True
        segments = json.loads((run / f"{label}-networks.json").read_text())["segments"]
        epochs.append(
            {
                "label": label,
                "whole_map": area_depth(flood, values),
                "traced_region": area_depth(flood & region, values),
                "original_component_cells": area_depth(flood & seed, values),
                "associated_current_components": area_depth(associated, values),
                "whole_map_flood_in_start_tile": area_depth(flood & start, values),
                "selected_flood_in_start_tile": area_depth(associated & start, values),
                "whole_map_transport_bounds": transport_overlap(flood, segments),
                "selected_transport_bounds": transport_overlap(associated, segments),
                "native_flood_flagged_segments": [s["id"] for s in segments if "Flooded" in s["flags"]],
            }
        )
    selected = seed[(nodes[:, 1] + 8640) // 16, (nodes[:, 0] + 8640) // 16]
    budgets = {
        "complete_region": storage_budget(header, records),
        "original_flood_component": storage_budget(header, records, selected),
    }
    # Net working-minus-published is transport-only only when all passes
    # publish. Otherwise earlier unpublished source work needs a carry model.
    if not all(r["working_buffer"] == r["published_buffer"] for r in records):
        raise ValueError("unpublished working passes require explicit source carry accounting")
    if not all(b["closes"] for b in budgets.values()):
        raise ValueError("published native storage budget does not close")
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [reference, mapped, plan, hydrology]}
    return {
        "format": 1,
        "diagnostic_not_native_map_qualification": True,
        "trace_audit": audit_result,
        "all_working_updates_published": True,
        "budgets": budgets,
        "epochs": epochs,
        "bindings": hashes,
        "start_tile": {"index": hydro["start_tile"], "bounds_xz": [cx - 960, cz - 960, cx + 960, cz + 960]},
        "source_ids": [s["id"] for s in header["sources"]],
        "limits": [
            "net local transport, not individual face flux or remote-source causality",
            "sampled five-minute window, not indefinite stability",
            "native segment bounds overlap is not path blockage",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["run", "reference", "mapped", "plan", "hydrology", "out"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = report(args.run, args.reference, args.mapped, args.plan, args.hydrology)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {"out": str(args.out), "trace_passes": result["trace_audit"]["passes"], "budgets": result["budgets"]}
        )
    )


if __name__ == "__main__":
    main()
