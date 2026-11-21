"""Source-selected static/minimax coastal paths and sampled head/velocity evidence."""

import argparse
from collections import deque
import heapq
import json
from pathlib import Path
import shutil

import numpy as np

from bank_authority import ROOT, load, sha, write
from coastal_floor_audit import decoded_package, grid, source_domains
from region import raster

POLICY = "coastal-boundary-corridor-witness-v1"
DESIGN = (
    "calibration/pl1191-construction-v1/development/phase16-coastal-witness-policy.md"
)


def neighbors(i, width, size):
    if i >= width:
        yield i - width
    if i % width:
        yield i - 1
    if i % width + 1 < width:
        yield i + 1
    if i + width < size:
        yield i + width


def routes(floor, seeds, sea_q):
    """Return exact shortest sub-sea paths and distinct minimax raster witnesses."""
    width, size = floor.shape[1], floor.size
    flat = floor.ravel()
    parent = np.full(size, -1, np.int32)
    queue = deque(int(i) for i in np.flatnonzero(seeds & (floor < sea_q)))
    for i in queue:
        parent[i] = i
    while queue:
        i = queue.popleft()
        for j in neighbors(i, width, size):
            if parent[j] < 0 and flat[j] < sea_q:
                parent[j] = i
                queue.append(j)
    spill = np.full(size, 65536, np.int32)
    steps = np.full(size, size + 1, np.int32)
    minimax = np.full(size, -1, np.int32)
    heap = []
    for i in np.flatnonzero(seeds & (floor < sea_q)):
        i = int(i)
        spill[i], steps[i], minimax[i] = int(flat[i]), 0, i
        heapq.heappush(heap, (int(flat[i]), 0, i))
    while heap:
        cost, distance, i = heapq.heappop(heap)
        if cost != spill[i] or distance != steps[i]:
            continue
        for j in neighbors(i, width, size):
            candidate = max(cost, int(flat[j])), distance + 1
            if candidate < (spill[j], steps[j]):
                spill[j], steps[j], minimax[j] = *candidate, i
                heapq.heappush(heap, (*candidate, j))
    return parent, minimax, spill


def path_to_root(node, parent):
    if parent[node] < 0:
        return None
    result = [int(node)]
    while parent[result[-1]] != result[-1]:
        result.append(int(parent[result[-1]]))
        if len(result) > parent.size:
            raise ValueError("Parent cycle")
    return result


def envelope(values):
    values = np.asarray(values)
    values = values[np.isfinite(values)]
    return (
        {
            "count": int(values.size),
            "min": float(values.min()),
            "median": float(np.median(values)),
            "max": float(values.max()),
        }
        if values.size
        else {"count": 0, "min": None, "median": None, "max": None}
    )


def aligned_node(point, width):
    x, z = float(point["x"]), float(point["z"])
    c, r = round((x + 8640) / 16), round((z + 8640) / 16)
    if not (0 <= r < width and 0 <= c < width):
        return None
    return (
        r * width + c
        if max(abs(x - (c * 16 - 8640)), abs(z - (r * 16 - 8640))) <= 0.001
        else None
    )


def signed_velocity(velocity, node, parent, width):
    target = int(parent[node])
    if target < 0 or target == node:
        return None
    dr, dc = target // width - node // width, target % width - node % width
    if abs(dr) + abs(dc) != 1:
        raise ValueError("Nonadjacent velocity projection")
    return float(velocity[0]) * dc + float(velocity[2]) * dr


def analyze(folder, output):
    decoded = decoded_package(folder)
    geometry = load(folder / "physical/geometry.json")
    points = load(folder / "physical/probes.json")["points"]
    domains = source_domains(geometry)
    floor = grid(folder / "native/grids/ws000000-water-ground.u16")
    width = floor.shape[1]
    ocean = np.flipud(raster(geometry["sq"], geometry.get("oceans", []), polygons=True))
    edge = np.zeros_like(ocean)
    edge[[0, -1], :] = True
    edge[:, [0, -1]] = True
    boundary = edge & ocean
    sea_q = round(decoded["sea_level_m"] * 64)
    parent, minimax, spill = routes(floor, boundary, sea_q)
    feature_paths, union, static_nodes = [], set(), set()
    for entry, mask in domains:
        paths = []
        for node in np.flatnonzero(mask):
            node = int(node)
            static = path_to_root(node, parent)
            path = static if static is not None else path_to_root(node, minimax)
            if path is None:
                raise ValueError("No boundary seed for conditional raster witness")
            union.update(path)
            if static is not None:
                static_nodes.update(path)
            paths.append(
                {
                    "source_node": node,
                    "kind": "subsea_shortest"
                    if static is not None
                    else "minimax_not_hydraulic",
                    "nodes": path,
                    "maximum_floor_m": float(floor.ravel()[path].max()) / 64,
                    "minimum_spill_floor_m": int(spill[node]) / 64,
                    "ocean_crossings": [
                        i
                        for i, (a, b) in enumerate(zip(path, path[1:]))
                        if ocean.ravel()[a] != ocean.ravel()[b]
                    ],
                }
            )
        feature_paths.append({**entry, "paths": paths})
    nodes = np.array(sorted(union), np.int32)
    node_to_column = {int(n): i for i, n in enumerate(nodes)}
    sample_nodes = [aligned_node(p, width) for p in points]
    query_indices = {}
    for i, n in enumerate(sample_nodes):
        if n is not None:
            query_indices.setdefault(n, []).append(i)
    times, heads, depths, snapshots = [], [], [], []
    velocities = {"static": [], "minimax": []}
    with (folder / "native/timeline.jsonl").open() as stream:
        for line in stream:
            e = json.loads(line)
            if e.get("kind") != "water_study_snapshot":
                continue
            actual = e["samples"]
            if len(actual) != len(points) or any(
                s["name"] != p["name"]
                or max(abs(s["x"] - p["x"]), abs(s["z"] - p["z"])) > 0.001
                for s, p in zip(actual, points)
            ):
                raise ValueError("Complete frozen cohort differs")
            prefix = e["prefix"]
            if sha(folder / f"native/grids/{prefix}-water-ground.u16") != sha(
                folder / "native/grids/ws000000-water-ground.u16"
            ):
                raise ValueError(
                    "Actual floor changed; retain and explicitly revise the static question"
                )
            depth = grid(folder / f"native/grids/{prefix}-water.u16").astype(np.int32)
            head = floor.astype(np.int32) + depth
            signed_summaries = {}
            for kind, direction in (("static", parent), ("minimax", minimax)):
                projected = np.full(nodes.size, np.nan, np.float64)
                signed_all = []
                for n, ids in query_indices.items():
                    values = [
                        signed_velocity(actual[i]["velocity"], n, direction, width)
                        for i in ids
                    ]
                    values = [v for v in values if v is not None]
                    signed_all.extend(values)
                    if n in node_to_column and values:
                        projected[node_to_column[n]] = np.median(values)
                signed_summaries[kind] = envelope(signed_all)
                velocities[kind].append(projected)
            by_feature = []
            for (entry, mask), paths in zip(domains, feature_paths):
                connected_count = sum(
                    p["kind"] == "subsea_shortest" for p in paths["paths"]
                )
                by_feature.append(
                    {
                        "id": entry["id"],
                        "name": entry["name"],
                        "scope": entry["scope"],
                        "nodes": entry["native_nodes"],
                        "static_connected_source_nodes": connected_count,
                        "wet_nodes": int(np.count_nonzero(depth[mask] > 6.4)),
                        "all_node_H_m": envelope(head[mask] / 64),
                        "wet_only_H_m": envelope(head[mask & (depth > 6.4)] / 64),
                        "depth_sum_q": int(depth[mask].sum()) if mask.any() else None,
                    }
                )
            regions = {}
            for name, mask in (
                ("ocean_boundary", boundary),
                ("ocean_interior", ocean & ~edge),
                ("non_ocean", ~ocean),
            ):
                regions[name] = {
                    "nodes": int(mask.sum()),
                    "wet_nodes": int(np.count_nonzero(depth[mask] > 6.4)),
                    "all_node_H_m": envelope(head[mask] / 64),
                    "wet_only_H_m": envelope(head[mask & (depth > 6.4)] / 64),
                    "depth_sum_q": int(depth[mask].sum()),
                }
            snapshots.append(
                {
                    "prefix": prefix,
                    "minute": e["trigger_game_minute"],
                    "regions": regions,
                    "features": by_feature,
                    "full_cohort": len(actual),
                    "exact_grid_queries": sum(len(v) for v in query_indices.values()),
                    "signed_toward_grid_parent_api": signed_summaries,
                }
            )
            times.append(e["trigger_game_minute"])
            heads.append(head.ravel()[nodes])
            depths.append(depth.ravel()[nodes])
    if len(snapshots) != 61:
        raise ValueError("Expected complete frozen61capture question")
    output.mkdir(parents=True)
    for name, a, dtype in (
        ("route_nodes", nodes, "<i4"),
        ("head_q", heads, "<i4"),
        ("depth_q", depths, "<i4"),
        ("static_signed_velocity_api", velocities["static"], "<f8"),
        ("minimax_signed_velocity_api", velocities["minimax"], "<f8"),
        ("static_parent", parent, "<i4"),
        ("minimax_parent", minimax, "<i4"),
        ("spill_floor_q", spill, "<i4"),
    ):
        np.asarray(a, dtype=dtype).tofile(output / f"{name}.bin")
    write(
        output / "paths.json",
        {
            "width": width,
            "features": feature_paths,
            "velocity_query_indices": {
                str(n): query_indices.get(int(n), []) for n in nodes
            },
            "route_nodes": int(nodes.size),
            "static_route_union_nodes": len(static_nodes),
            "projection": "separate static/minimax parent fields; select the matching path kind; not known geographic flow",
        },
    )
    write(
        output / "result.json",
        {
            "schema": "polli.coastal-boundary-witness-result/1",
            "policy": POLICY,
            "prospective_freeze_sha256": sha(folder / "prospective-freeze.json"),
            "snapshots": snapshots,
            "route_profile_shape": [len(times), int(nodes.size)],
            "binary_layout": "native flat rc order; head/depth in1/64m; velocity API f64 NaN=unknown; shared-node profiles do not establish discharge",
            "physical_changes": False,
            "full_hour_acceptance": "incomplete/unknown",
            "stable_water_promise": "unknown",
        },
    )
    write(
        output / "receipt.json",
        {
            "files_sha256": {
                p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()
            }
        },
    )


def stage(prep, native, prior_result, review, output):
    if output.exists():
        raise ValueError("Use a fresh protocol; preserve prior attempts")
    output.mkdir(parents=True)
    shutil.copytree(prep / "physical", output / "physical")
    shutil.copyfile(prep / "native-plan.json", output / "parent-native-plan.json")
    shutil.copyfile(prior_result / "receipt.json", output / "parent-native-files.json")
    shutil.copyfile(review, output / "review.json")
    target = output / "native"
    (target / "grids").mkdir(parents=True)
    manifest = load(output / "parent-native-files.json")["native_files_sha256"]
    names = [
        "timeline.jsonl",
        "session-receipt.json",
        "harness-source.json",
        "verdict.json",
    ]
    names += [
        f"grids/ws{i:06d}-{field}.u16"
        for i in range(61)
        for field in ("water", "water-ground")
    ]
    for name in names:
        if sha(native / name) != manifest[name]:
            raise ValueError("Raw observation changed")
        shutil.copyfile(native / name, target / name)
    dependencies = {
        str(p.relative_to(ROOT)): sha(p)
        for p in ROOT.glob("*.py")
        if not p.name.startswith("test_")
    }
    for p in (ROOT / "diagnostics").glob("*.py"):
        if not p.name.startswith("test_"):
            dependencies[str(p.relative_to(ROOT))] = sha(p)
    for name in (DESIGN, "pyproject.toml", "uv.lock"):
        dependencies[name] = sha(ROOT / name)
    write(
        output / "prospective-freeze.json",
        {
            "policy": POLICY,
            "known_basis": "PL-1245 existing-data observations; not outcome-blind",
            "source_files_sha256": dependencies,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
        },
    )
    analyze(output, output / "analysis")
    return {
        "freeze_sha256": sha(output / "prospective-freeze.json"),
        "result_sha256": sha(output / "analysis/result.json"),
    }


def preflight(folder, output):
    frozen = load(folder / "prospective-freeze.json")
    if frozen["policy"] != POLICY:
        raise ValueError("Wrong witness policy")
    for name, expected in frozen["source_files_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Changed source: {name}")
    for name, expected in frozen["files_sha256"].items():
        if sha(folder / name) != expected:
            raise ValueError(f"Changed evidence: {name}")
    if output.exists():
        raise ValueError("Fresh replay output required")
    analyze(folder, output)
    if load(output / "receipt.json") != load(folder / "analysis/receipt.json"):
        raise ValueError("Full witness replay differs")
    return {"replay_pass": True, "result_sha256": sha(output / "result.json")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, arguments in (
        ("stage", ("prep", "native", "prior_result", "review", "output")),
        ("preflight", ("folder", "output")),
    ):
        sub = commands.add_parser(name)
        for argument in arguments:
            sub.add_argument(argument, type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps(globals()[command](**args), indent=2))
