"""Read-only pre-export start/hookup and surface-water witness checks.

Provisional geometric checks, not recovered game constants. No identity,
place name, native result or admission fingerprint enters the decisions.
Native grids are south-first, 16 m spacing, heights/depth in 1/64 metre.
"""

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

from real_roads import _road_access, _tile_of


@dataclass(frozen=True)
class Parameters:
    footprint_half_m: int = 192
    center_step_m: int = 64
    max_depth_m: float = 0.1
    max_slope: float = 0.15
    max_relief_m: float = 8
    min_segment_m: float = 40
    max_hookup_m: float = 512
    road_clearance_m: int = 24
    intake_depth_m: float = 1
    sewage_separation_m: float = 320


PARAMETERS = Parameters()
GRID, SPACING, HALF = 1081, 16, 8640


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def sample(grid, xz):
    p = np.asarray(xz)
    return ndimage.map_coordinates(
        grid,
        [(p[..., 1] + HALF) / SPACING, (p[..., 0] + HALF) / SPACING],
        order=1,
        mode="nearest",
    )


def position(ground, xz):
    return [float(xz[0]), float(sample(ground, np.asarray([xz]))[0]), float(xz[1])]


def road_mask(graph):
    result = np.zeros((GRID, GRID), dtype=bool)
    for edge in graph["edges"]:
        # Elevated and underground networks can still obstruct a new footprint.
        if edge["kind"] in ("air", "ship"):
            continue
        a, b = [np.asarray(graph["nodes"][edge[k]]["xyz"])[[0, 2]] for k in ("a", "b")]
        points = np.linspace(a, b, max(2, int(np.linalg.norm(b - a) / 8) + 1))
        ij = np.floor((points + HALF) / SPACING + 0.5).astype(int).clip(0, GRID - 1)
        result[ij[:, 1], ij[:, 0]] = True
    return result


def dry_centers(ground, depth, graph, tile, params=PARAMETERS):
    dz, dx = np.gradient(ground, SPACING)
    dry = (depth <= params.max_depth_m) & (np.hypot(dx, dz) <= params.max_slope)
    width = 2 * int(np.ceil(params.footprint_half_m / SPACING)) + 1
    clear = ndimage.minimum_filter(dry, size=width, mode="constant", cval=0)
    relief = ndimage.maximum_filter(ground, size=width) - ndimage.minimum_filter(
        ground, size=width
    )
    obstruction = ndimage.maximum_filter(
        road_mask(graph),
        size=width + 2 * int(np.ceil(params.road_clearance_m / SPACING)),
    )
    clear &= (relief <= params.max_relief_m) & ~obstruction
    tx, tz = tile % 5 - 2, tile // 5 - 2
    margin = 960 - params.footprint_half_m - 32
    offsets = np.arange(
        -int(margin // params.center_step_m) * params.center_step_m,
        margin + 1,
        params.center_step_m,
    )
    centers = []
    for z in offsets + tz * 1920:
        for x in offsets + tx * 1920:
            col, row = (
                int(round((x + HALF) / SPACING)),
                int(round((z + HALF) / SPACING)),
            )
            if clear[row, col]:
                centers.append([float(x), float(z)])
    return centers


def segment_clear(ground, depth, a, b, params=PARAMETERS):
    a, b = np.asarray(a), np.asarray(b)
    length = float(np.linalg.norm((b - a)[[0, 2]]))
    if not params.min_segment_m <= length <= params.max_hookup_m:
        return False
    if abs(b[1] - a[1]) / length > params.max_slope:
        return False
    xz = np.linspace(a[[0, 2]], b[[0, 2]], max(2, int(np.ceil(length / 8)) + 1))
    return bool(np.all(sample(depth, xz) <= params.max_depth_m))


def start_witness(ground, depth, hydro, params=PARAMETERS):
    graph, tile = hydro.get("highways"), hydro["start_tile"]
    if graph is None:
        return {
            "level": "unknown",
            "reason": "missing_authored_graph",
            "predicted": None,
        }
    access = _road_access(graph)
    arrivals = [
        n for n in access["arrive"] if _tile_of(graph["nodes"][n]["xyz"]) == tile
    ]
    departures = [
        n for n in access["leave"] if _tile_of(graph["nodes"][n]["xyz"]) == tile
    ]
    scope = "Current authored directed graph and current start tile only; not all possible generators"
    if not arrivals or not departures:
        return {
            "level": "not_possible_here",
            "reason": "no_authored_two_way_start_access",
            "predicted": False,
            "scope": scope,
            "witness": None,
        }
    centers = dry_centers(ground, depth, graph, tile, params)
    pairs = sorted(
        (
            float(
                np.linalg.norm(
                    (np.asarray(graph["nodes"][a]["xyz"]) - graph["nodes"][b]["xyz"])[
                        [0, 2]
                    ]
                )
            ),
            a,
            b,
        )
        for a in arrivals
        for b in departures
    )
    for gap, arrival, departure in pairs:
        if gap > 400:
            continue
        hooks = [arrival, departure]
        xyz = [np.asarray(graph["nodes"][i]["xyz"]) for i in hooks]
        heading = np.zeros(2)
        for hook, p in zip(hooks, xyz):
            e = next(
                e
                for e in graph["edges"]
                if e["kind"] in ("highway", "ramp") and hook in (e["a"], e["b"])
            )
            other = e["b"] if e["a"] == hook else e["a"]
            delta = (p - np.asarray(graph["nodes"][other]["xyz"]))[[0, 2]]
            heading += delta / max(np.linalg.norm(delta), 1e-9)
        if np.linalg.norm(heading) < 0.1:
            continue
        mean = np.mean(xyz, axis=0)
        approach = float(np.clip(gap * 0.75, 12, 96))
        while True:
            join_xz = mean[[0, 2]] + heading / np.linalg.norm(heading) * approach
            if (
                min(np.linalg.norm(p[[0, 2]] - join_xz) for p in xyz)
                >= params.min_segment_m
                or approach >= 160
            ):
                break
            approach += 8
        join = position(ground, join_xz)
        elevation = max(0.0, float(mean[1] - join[1]))
        join[1] += elevation
        if _tile_of(join) != tile or not all(
            segment_clear(ground, depth, p, join, params) for p in xyz
        ):
            continue
        for center in sorted(
            centers, key=lambda c: (np.linalg.norm(np.asarray(c) - join_xz), c)
        ):
            corner = position(
                ground,
                [
                    center[0] + (-144 if join[0] < center[0] else 144),
                    center[1] + (-144 if join[2] < center[1] else 144),
                ],
            )
            if not segment_clear(ground, depth, join, corner, params):
                continue
            points, steps = {}, []
            for z in range(4):
                for x in range(4):
                    points[f"g{x}{z}"] = position(
                        ground, [center[0] - 144 + x * 96, center[1] - 144 + z * 96]
                    )
            for z in range(4):
                for x in range(3):
                    steps.append(
                        {
                            "from": f"g{x}{z}",
                            "to": f"g{x + 1}{z}",
                            "prefab": "Basic Road",
                        }
                    )
            for x in range(4):
                for z in range(3):
                    steps.append(
                        {
                            "from": f"g{x}{z}",
                            "to": f"g{x}{z + 1}",
                            "prefab": "Basic Road",
                        }
                    )
            points["join"] = join
            bindings = {}
            for i, hook in enumerate(hooks):
                key = f"hook{i}"
                points[key] = list(map(float, xyz[i]))
                bindings[key] = {
                    "graph_node": hook,
                    "position": points[key],
                    "segments": 1,
                }
                steps.append(
                    {
                        "from": key,
                        "to": "join",
                        "prefab": "Basic Road",
                        "end_elevation": elevation if i == 0 else 0,
                    }
                )
            gx, gz = (
                (0 if join[0] < center[0] else 3),
                (0 if join[2] < center[1] else 3),
            )
            steps.append({"from": "join", "to": f"g{gx}{gz}", "prefab": "Basic Road"})
            witness = {
                "schema": 1,
                "start_tile": tile,
                "center_xz": center,
                "footprint_half_m": params.footprint_half_m,
                "points": points,
                "bindings": bindings,
                "steps": steps,
                "outside_graph_anchors": {
                    "incoming": access["incoming"],
                    "outgoing": access["outgoing"],
                },
                "scope": "Fixed 4x4 road grid, then ordered two-stub shared junction; no grading or bridge fallback",
            }
            return {
                "level": "likely",
                "reason": "dry_footprint_and_directed_hookup_plan",
                "predicted": True,
                "scope": scope,
                "witness": witness,
                "witness_sha256": digest(witness),
                "subchecks": {
                    "dry_footprint": True,
                    "directed_outside_graph": True,
                    "native_placement": None,
                    "native_outside_path": None,
                },
                "limits": [
                    "16m footprint samples and 8m hookup water samples; between-sample terrain/collisions unresolved",
                    "Provisional length/slope/clearance limits, not recovered game constants",
                ],
            }
    return {
        "level": "unknown",
        "reason": "no_witness_in_finite_plan_search",
        "predicted": None,
        "scope": scope,
        "dry_footprint_candidates": len(centers),
        "witness": None,
    }


def water_witness(ground, depth, hydro, params=PARAMETERS):
    tile = hydro["start_tile"]
    candidates = []
    for name, line in sorted(hydro.get("samples", {}).items()):
        p = np.asarray(line, dtype=float)
        if p.ndim != 2 or p.shape[0] < 2 or p.shape[1] != 3:
            continue
        xz = p[:, [0, 2]]
        depths = sample(depth, xz)
        surfaces = sample(ground, xz) + depths
        arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(xz, axis=0), axis=1))]
        inside = [
            i
            for i, v in enumerate(p)
            if _tile_of(v) == tile and depths[i] >= params.intake_depth_m
        ]
        for i in inside:
            downstream = [
                j
                for j in inside
                if arc[j] - arc[i] >= params.sewage_separation_m
                and np.all(depths[i : j + 1] >= params.intake_depth_m)
                and surfaces[i] > surfaces[j] + 1 / 64
            ]
            if not downstream:
                continue
            j = downstream[0]
            candidates.append(
                (
                    float(arc[j] - arc[i]),
                    name,
                    i,
                    j,
                    p[i].tolist(),
                    p[j].tolist(),
                    float(depths[i]),
                    float(surfaces[i] - surfaces[j]),
                )
            )
            break
    candidate = min(candidates) if candidates else None
    witness = (
        None
        if candidate is None
        else {
            "river": candidate[1],
            "intake_sample_index": candidate[2],
            "outlet_sample_index": candidate[3],
            "intake_water_point": candidate[4],
            "outlet_water_point": candidate[5],
            "along_route_separation_m": candidate[0],
            "initial_intake_depth_m": candidate[6],
            "initial_surface_drop_m": candidate[7],
            "direction_basis": "Prepared upstream-to-downstream channel route and initial surface drop; not simulated velocity",
            "bank_placement": None,
            "demand_native_units": None,
            "horizon_game_minutes": 60,
        }
    )
    return {
        "level": "unknown",
        "reason": "surface_flow_quality_and_sewage_service_unverified",
        "predicted": None,
        "witness": witness,
        "witness_sha256": digest(witness) if witness else None,
        "subchecks": {
            "initial_wet_downstream_route": bool(witness),
            "native_intake_placement": None,
            "clean_intake": None,
            "sustained_capacity": None,
            "sewage_downstream_safe": None,
        },
        "limits": [
            "Initial wet channel/nominal source capacity is not sustained intake capacity",
            "No salt/fresh or pollution inference from mapped water; no rate-unit conversion",
            "Groundwater service is separate, never a positive surface-water label",
        ],
    }


def assess(folder):
    folder = Path(folder)
    files = {
        name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
        for name in ["terrain.u16", "water.u16", "hydrology.json"]
    }
    arrays = []
    for name in ["terrain.u16", "water.u16"]:
        a = np.fromfile(folder / name, dtype="<u2")
        if a.size != GRID * GRID:
            raise ValueError(f"{name}: expected complete native 1081x1081 grid")
        arrays.append(a.reshape(GRID, GRID).astype(float) / 64)
    hydro = json.loads((folder / "hydrology.json").read_text())
    if type(hydro.get("start_tile")) is not int or not 0 <= hydro["start_tile"] < 25:
        raise ValueError("Missing/invalid current start tile")
    source = {
        name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ["start_capabilities.py", "real_roads.py"]
    }
    model = {
        "id": "start-surface-v1",
        "parameters": asdict(PARAMETERS),
        "source_sha256": source,
    }
    model["sha256"] = digest(model)
    return {
        "schema": 1,
        "mode": "export",
        "model": model,
        "inputs_sha256": files,
        "capabilities": {
            "start": start_witness(*arrays, hydro),
            "water": water_witness(*arrays, hydro),
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = assess(args.prepared)
    with args.out.open("x") as output:
        output.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
