"""Read-only escape ceilings versus complete source-defined water contracts.

Map-edge minimax is conditional raster topology, not a bank, hydraulic outlet,
flow capacity or a requirement that an open stream become a closed pond.
"""

import argparse
import copy
from collections import Counter
import heapq
import math
from pathlib import Path
import shutil

import numpy as np

from bank_authority import ROOT, load, sha, write
from coastal_floor_audit import grid
from local_supply_envelope import source_masks
from maintained_water_inventory import compile_inventory
from spill_port_topology import preflight as parent_preflight
from waterway_pieces import catalog, digest

POLICY = "complete-contract-conditional-escape-stage-v1"
METHOD = "diagnostics/stage_contracts.py"
TEST = "diagnostics/test_stage_contracts.py"
DESIGN = "calibration/pl1191-construction-v1/development/phase24-stage-policy.md"
DEFINITION = "2d72a80690d26c2f7de729e36d785c790451b4d28f6837fbf7b177af25ea4886"


def escape_field(floor, adjacency):
    """Minimize maximum floor along every path to ANY literal square-edge node."""
    floor = np.asarray(floor)
    if floor.ndim != 2 or floor.dtype.kind not in "iu" or adjacency not in (4, 8):
        raise ValueError("Quantized complete floor and explicit adjacency required")
    height, width = floor.shape
    flat = floor.ravel()
    cost = np.full(floor.size, 65536, np.int32)
    parent = np.full(floor.size, -1, np.int32)
    edge = np.zeros_like(floor, bool)
    edge[[0, -1]] = True
    edge[:, [0, -1]] = True
    heap = []
    for n in np.flatnonzero(edge):
        n = int(n)
        cost[n], parent[n] = int(flat[n]), n
        heapq.heappush(heap, (int(cost[n]), n))
    steps = [(-1, 0), (0, -1), (0, 1), (1, 0)]
    if adjacency == 8:
        steps += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    while heap:
        value, n = heapq.heappop(heap)
        if value != cost[n]:
            continue
        r, c = divmod(n, width)
        for y, x in steps:
            if not (0 <= r + y < height and 0 <= c + x < width):
                continue
            other = (r + y) * width + c + x
            candidate = max(value, int(flat[other]))
            if candidate < cost[other]:
                cost[other], parent[other] = candidate, n
                heapq.heappush(heap, (candidate, other))
    return cost.reshape(floor.shape), parent.reshape(floor.shape)


def nearby_nodes(point, shape):
    """Same float32 query coordinates and literal <=64m circle as frozen compiler."""
    x, z = (float(np.float32(v)) for v in point)
    cx, cz = int(np.rint((x + 8640) / 16)), int(np.rint((z + 8640) / 16))
    ys = np.arange(max(0, cz - 4), min(shape[0] - 1, cz + 4) + 1)
    xs = np.arange(max(0, cx - 4), min(shape[1] - 1, cx + 4) + 1)
    yy, xx = np.meshgrid(ys, xs, indexing="ij")
    circle = (xx * 16 - 8640 - x) ** 2 + (yy * 16 - 8640 - z) ** 2 <= 64**2
    return (yy[circle] * shape[1] + xx[circle]).astype(np.int64)


def merge_intervals(intervals):
    result = []
    for low, high in sorted({tuple(pair) for pair in intervals}):
        if low > high:
            continue
        if result and low <= result[-1][1] + 1:
            result[-1][1] = max(result[-1][1], high)
        else:
            result.append([int(low), int(high)])
    return result


def common_stage(intervals, fraction):
    """Earliest quantized stage supporting ceil(fraction*n) DISTINCT points."""
    events = Counter()
    for point in intervals:
        for low, high in merge_intervals(point):
            events[low] += 1
            events[high + 1] -= 1
    required = math.ceil(fraction * len(intervals))
    count, maximum, first = 0, 0, None
    valid = []
    ordered = sorted(events.items())
    for index, (stage, delta) in enumerate(ordered):
        count += delta
        maximum = max(maximum, count)
        if first is None and count >= required and required:
            first = stage
        if count >= required and required and index + 1 < len(ordered):
            valid.append([stage, ordered[index + 1][0] - 1])
    return {
        "required_points": required,
        "maximum_simultaneous_points": maximum,
        "common_stage_intervals_q": merge_intervals(valid),
        "earliest_common_stage_q": first,
        "numeric_fit_only": first is not None,
    }


def compile_complete(geometry, hydro, inherited=None):
    """New additive compiler envelope; inherited contracts/points NEVER replaced."""
    inventory = (
        copy.deepcopy(inherited) if inherited else compile_inventory(geometry, hydro)
    )
    inventory["schema"] = "polli.stage-contract-source-inventory/4"
    inventory["inherited_schema"] = inherited.get("schema") if inherited else None
    inventory["source_geometry_sha256"] = digest(geometry)
    rows = {r["id"]: r for r in catalog(geometry)["rows"]}
    for entry in inventory["entries"]:
        if entry["id"] in rows:
            entry["source_piece_provenance"] = rows[entry["id"]]
            if rows[entry["id"]]["status"] == "outside_square":
                entry["status"] = "outside_square"
        # Every unsupported polygon remains unresolved; no bounding-box guess.
    inventory["coverage_complete"] = not any(
        e["status"] == "unresolved" for e in inventory["entries"]
    )
    inventory["stable_water_promise"] = "unknown"
    return inventory


def contract_model(contract, floor, initial, ceiling, own):
    engineered = contract["kind"] == "engineered"
    records, all_intervals, own_intervals = [], [], []
    for point in contract["points_xz"]:
        if engineered:
            coords = (np.asarray(point) + 8640) / 16
            aligned = np.all(np.abs(coords - np.rint(coords)) <= 1e-8)
            nodes = (
                np.array(
                    [int(round(coords[1])) * floor.shape[1] + int(round(coords[0]))]
                )
                if aligned
                else np.array([], np.int64)
            )
        else:
            nodes = nearby_nodes(point, floor.shape)
        if np.any(nodes < 0) or np.any(nodes >= floor.size):
            raise ValueError("Contract support outside square")
        minimum = 32 if engineered else 7  # >=.5m versus strictly >.1m on 1/64m grid
        lower = floor.ravel()[nodes].astype(np.int64) + minimum
        upper = np.minimum(ceiling.ravel()[nodes], 65535)
        feasible = lower <= upper
        authored = initial.ravel()[nodes]
        own_nodes = np.ones(nodes.size, bool) if engineered else own.ravel()[nodes]
        intervals = merge_intervals(zip(lower[feasible], upper[feasible]))
        limited = merge_intervals(
            zip(lower[feasible & own_nodes], upper[feasible & own_nodes])
        )
        all_intervals.append(intervals)
        own_intervals.append(limited)
        records.append(
            {
                "point_xz": point,
                "support_nodes": nodes.tolist(),
                "minimum_required_stage_q": int(lower.min()) if nodes.size else None,
                "conditional_stage_intervals_q": intervals,
                "own_source_raster_intervals_q": limited,
                "initial_wet": bool(np.any(authored >= minimum))
                if nodes.size
                else None,
                "exact_anchor_model": "grid-centred"
                if engineered and nodes.size
                else "not applicable"
                if not engineered
                else "unresolved off-grid API semantics",
            }
        )
    fraction = 1 if engineered else 0.95
    initial_values = [r["initial_wet"] for r in records]
    footprint_nodes = np.flatnonzero(own)
    footprint_intervals = merge_intervals(
        zip(
            floor.ravel()[footprint_nodes].astype(np.int64) + 64,
            np.minimum(ceiling.ravel()[footprint_nodes], 65535),
        )
    )
    optimistic = common_stage(all_intervals, fraction)
    restricted = common_stage(own_intervals, fraction)
    for model in (optimistic, restricted):
        intersections = merge_intervals(
            (max(a, c), min(b, d))
            for a, b in model["common_stage_intervals_q"]
            for c, d in footprint_intervals
        )
        model["same_stage_with_any_own_1m_source_intervals_q"] = (
            intersections if not engineered else None
        )
        model["same_stage_with_own_source_numeric_fit_only"] = (
            bool(intersections) if not engineered else None
        )
    return {
        "id": contract["id"],
        "kind": contract["kind"],
        "points": records,
        "original_contract_sha256": digest(contract),
        "initial_wet_points": sum(v is True for v in initial_values),
        "initial_unknown_points": sum(v is None for v in initial_values),
        "total_points": len(records),
        "required_points": math.ceil(fraction * len(records)),
        "optimistic_any_nearby_raster": optimistic,
        "restricted_own_source_raster": restricted,
        "scope": "conditional common-stage geometry only; not flowing-water refusal/admission or native retention",
    }


def stage(parent, output):
    parent_preflight(parent)
    if output.exists():
        raise ValueError("Fresh protocol required")
    output.mkdir(parents=True)
    (output / "inventories").mkdir()
    shutil.copytree(parent, output / "parent")
    for slug in load(parent / "freeze.json")["cases"]:
        case = output / "parent/parent-protocol" / slug
        source = case / "input"
        kind = load(case / "case.json")["kind"]
        geometry = load(
            source
            / (
                "physical/geometry.json"
                if kind == "coastal"
                else "source/geometry.json"
            )
        )
        ledger = load(source / "ledger.json") if kind == "geographic" else None
        old = source / "source/inventory.json"
        inherited = (
            load(old)
            if old.exists()
            else ledger.get("source_contract_inventory")
            if ledger
            else None
        )
        hydro = (
            load(source / "physical/hydrology.json")
            if (source / "physical/hydrology.json").exists()
            else {}
        )
        inventory = compile_complete(geometry, hydro, inherited)
        if inherited and inventory["points"] != inherited["points"]:
            raise ValueError("Original contract point cohort changed")
        write(output / "inventories" / f"{slug}.json", inventory)
    dependencies = dict(load(parent / "freeze.json")["source_files_sha256"])
    for name in (METHOD, TEST, DESIGN):
        dependencies[name] = sha(ROOT / name)
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": load(parent / "freeze.json")["cases"],
            "definition_sha256": DEFINITION,
            "source_files_sha256": dependencies,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "complete_inventory_before_stage_outputs": True,
            "prior_outcomes_known": True,
            "new_native": False,
        },
    )


def preflight(folder):
    freeze = load(folder / "freeze.json")
    if freeze["policy"] != POLICY or freeze["definition_sha256"] != DEFINITION:
        raise ValueError("Wrong policy/definition")
    for root, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for name, expected in freeze[key].items():
            if sha(root / name) != expected:
                raise ValueError(f"Bound bytes changed: {name}")
    parent_preflight(folder / "parent")


def analyze(folder, slug, output):
    case = folder / "parent/parent-protocol" / slug
    source = case / "input"
    inventory = load(folder / "inventories" / f"{slug}.json")
    kind = load(case / "case.json")["kind"]
    old_result = load(folder / "parent/parent-results" / f"{slug}.json")
    result = {
        "case": slug,
        "inventory_sha256": sha(folder / "inventories" / f"{slug}.json"),
        "complete_entry_status_counts": dict(
            Counter(e["status"] for e in inventory["entries"])
        ),
        "contract_count": sum(
            len(e.get("contracts", [])) for e in inventory["entries"]
        ),
        "all_source_entries_and_original_cohort_retained": True,
        "no_physical_or_native_change": True,
        "physical_admission": False,
        "promise": "unknown",
    }
    if old_result["domains"] is None:
        return {
            **result,
            "original_base_refusal": old_result["original_base_refusal"],
            "floor": None,
            "contracts": None,
            "source_footprints": None,
        }
    physical = source / "physical"
    geometry = load(
        source
        / ("physical/geometry.json" if kind == "coastal" else "source/geometry.json")
    )
    rows, masks, _ = source_masks(geometry)
    mask_index = {r["id"]: mask for r, mask in zip(rows, masks)}
    floor_path = (
        case / "current-floor.u16" if kind == "coastal" else physical / "terrain.u16"
    )
    floor, initial = grid(floor_path), grid(physical / "water.u16")
    result.update(
        floor=old_result["floor"],
        package_sha256=old_result["package_sha256"],
        initial_sha256=sha(physical / "water.u16"),
        full_original_probes_sha256=sha(physical / "probes.json"),
        serialized_sea_m=old_result["sea_m"],
        boundary_capacity_and_flow_direction=None,
        lateral_water_land_authority="unresolved; source raster is not surveyed width/bank",
        models=[],
    )
    for adjacency in (4, 8):
        print(f"{slug}: {adjacency}-adjacent complete-square escape field", flush=True)
        spill, parent = escape_field(floor, adjacency)
        stem = f"{slug}-adj{adjacency}"
        spill.astype("<i4").tofile(output / f"{stem}-escape.i32")
        parent.astype("<i4").tofile(output / f"{stem}-parent.i32")
        ceiling = spill - 32
        contracts, footprints = [], []
        for entry in inventory["entries"]:
            own = mask_index.get(entry["id"], np.zeros_like(floor, bool))
            for contract in entry.get("contracts", []):
                row = contract_model(contract, floor, initial, ceiling, own)
                row.update(
                    source_entry=entry["id"], retained_support_status=entry["status"]
                )
                contracts.append(row)
        for row, mask in zip(rows, masks):
            nodes = np.flatnonzero(mask)
            if row["status"] != "perennial_surface":
                continue
            feasible = (
                floor.ravel()[nodes].astype(np.int64) + 64 <= ceiling.ravel()[nodes]
            )
            footprints.append(
                {
                    "id": row["id"],
                    "source_sha256": row.get("source_sha256"),
                    "source_nodes": int(nodes.size),
                    "conditional_1m_footprint_nodes": int(feasible.sum()),
                    "minimum_stage_for_any_1m_source_q": int(floor.ravel()[nodes].min())
                    + 64
                    if nodes.size
                    else None,
                    "minimum_escape_ceiling_q": int(ceiling.ravel()[nodes].min())
                    if nodes.size
                    else None,
                    "maximum_escape_ceiling_q": int(ceiling.ravel()[nodes].max())
                    if nodes.size
                    else None,
                    "inlet_outlet_supply": None,
                }
            )
        result["models"].append(
            {
                "adjacency": adjacency,
                "contracts": contracts,
                "source_footprints": footprints,
                "escape_i32_sha256": sha(output / f"{stem}-escape.i32"),
                "parent_i32_sha256": sha(output / f"{stem}-parent.i32"),
                "fit_counts": {
                    key: sum(c[key]["numeric_fit_only"] for c in contracts)
                    for key in (
                        "optimistic_any_nearby_raster",
                        "restricted_own_source_raster",
                    )
                },
            }
        )
    return result


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh CPU results required")
    output.mkdir(parents=True)
    for slug in load(folder / "freeze.json")["cases"]:
        write(output / f"{slug}.json", analyze(folder, slug, output))
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "input_freeze_sha256": sha(folder / "freeze.json"),
            "result_files_sha256": {
                p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()
            },
            "new_physical_or_native": False,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, arguments in (
        ("stage", ["parent", "output"]),
        ("preflight", ["folder"]),
        ("evaluate", ["folder", "output"]),
    ):
        command = sub.add_parser(name)
        for argument in arguments:
            command.add_argument(argument, type=Path)
    args = vars(parser.parse_args())
    globals()[args.pop("command")](**args)
