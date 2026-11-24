"""Active PL-1210 Start-only port of PL-1078 9a4aad7.

Search/parameters preserved. Missing tile now abstains. Runtime binding and
capture approximation are new, unscored semantics; archived studies stay frozen.
"""

from dataclasses import dataclass
import hashlib
import json

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


def edge_curve(graph, edge):
    """Provisional cubic corridor, using the exported endpoint tangents.

    The one-third chord control length is a geometric approximation, not a
    recovered native collision rule. Native guarded placement remains the oracle.
    """
    a, b = [np.asarray(graph["nodes"][edge[k]]["xyz"])[[0, 2]] for k in ("a", "b")]
    length = np.linalg.norm(b - a)
    controls = [a, b]
    if "start_dir" in edge and "end_dir" in edge:
        controls = [
            a,
            a + np.asarray(edge["start_dir"])[[0, 2]] * length / 3,
            b + np.asarray(edge["end_dir"])[[0, 2]] * length / 3,
            b,
        ]
    t = np.linspace(0, 1, max(2, int(length / 4) + 1))[:, None]
    if len(controls) == 2:
        return a * (1 - t) + b * t
    a, c, d, b = controls
    return (
        a * (1 - t) ** 3 + 3 * c * (1 - t) ** 2 * t + 3 * d * (1 - t) * t**2 + b * t**3
    )


def outward_heading(graph, hook):
    edge = next(
        e
        for e in graph["edges"]
        if e["kind"] in ("highway", "ramp") and hook in (e["a"], e["b"])
    )
    key = "start_dir" if edge["a"] == hook else "end_dir"
    if key in edge:
        return -np.asarray(edge[key])[[0, 2]]
    other = edge["b"] if edge["a"] == hook else edge["a"]
    delta = (np.asarray(graph["nodes"][hook]["xyz"]) - graph["nodes"][other]["xyz"])[
        [0, 2]
    ]
    return delta / max(np.linalg.norm(delta), 1e-9)


def link_clearance(a, b, corridor):
    a, b = np.asarray(a)[[0, 2]], np.asarray(b)[[0, 2]]
    line = np.linspace(a, b, max(2, int(np.linalg.norm(b - a) / 4) + 1))
    return float(np.min(np.linalg.norm(line[:, None] - corridor[None, :], axis=2)))


def road_mask(graph):
    result = np.zeros((GRID, GRID), dtype=bool)
    for edge in graph["edges"]:
        # Elevated and underground networks can still obstruct a new footprint.
        if edge["kind"] in ("air", "ship"):
            continue
        points = edge_curve(graph, edge)
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
    graph, tile = hydro.get("highways"), hydro.get("start_tile")
    if type(tile) is not int or not 0 <= tile < 25:
        return {"level": "unknown", "reason": "missing_start_tile", "predicted": None}
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
    if not access["incoming"] or not access["outgoing"]:
        return {
            "level": "not_possible_here",
            "reason": "missing_authored_outside_road_direction",
            "predicted": False,
            "scope": scope,
            "witness": None,
        }
    if not arrivals or not departures:
        # Through-roads can have valid access without dangling ramp stubs.
        # This constructor supports a two-stub plan only, not every legal join.
        return {
            "level": "unknown",
            "reason": "no_supported_two_stub_witness",
            "predicted": None,
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
        heading = sum((outward_heading(graph, hook) for hook in hooks), np.zeros(2))
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
        # The two intended ramp junctions are allowed to meet the fixture.
        # Screen unrelated authored networks, including elevated corridors whose
        # pillars/clearance are unresolved; this can abstain conservatively.
        unrelated = [
            edge_curve(graph, e)
            for e in graph["edges"]
            if e["kind"] not in ("air", "ship")
            and not any(h in (e["a"], e["b"]) for h in hooks)
        ]
        nearby = [
            c
            for c in unrelated
            if np.min(np.linalg.norm(c - join_xz, axis=1)) < params.max_hookup_m + 400
        ]
        corridor = np.concatenate(nearby) if nearby else None
        if corridor is not None and any(
            link_clearance(p, join, corridor) < params.road_clearance_m for p in xyz
        ):
            continue

        # Native junction collision handling is order-sensitive. Freeze the
        # geometrically less obstructed stub first, before any native response.
        def first_clearance(hook):
            other = next(h for h in hooks if h != hook)
            e = next(
                e
                for e in graph["edges"]
                if other in (e["a"], e["b"]) and e["kind"] in ("highway", "ramp")
            )
            return link_clearance(
                graph["nodes"][hook]["xyz"], join, edge_curve(graph, e)
            )

        hooks = sorted(hooks, key=lambda h: (-first_clearance(h), h))
        xyz = [np.asarray(graph["nodes"][i]["xyz"]) for i in hooks]
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
            if (
                corridor is not None
                and link_clearance(join, corner, corridor) < params.road_clearance_m
            ):
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
                "scope": "Fixed 4x4 road grid, then clearance-ranked two-stub shared junction; no grading or bridge fallback",
                "ordering_basis": "Maximum sampled clearance from the other authored ramp corridor, then graph index; never native retries",
            }
            return {
                "level": "likely",
                "reason": "dry_footprint_and_directed_hookup_plan",
                "predicted": True,
                "scope": scope,
                "witness": witness,
                "subchecks": {
                    "dry_footprint": True,
                    "directed_outside_graph": True,
                    "native_placement": None,
                    "native_outside_path": None,
                },
                "limits": [
                    "16m footprint samples and 8m hookup water samples; between-sample terrain/collisions unresolved",
                    "Provisional length/slope/clearance limits, not recovered game constants",
                    "Cubic corridor uses authored tangents and one-third-chord control length; native curve/width/pillars can disagree",
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


def evaluate_start(data):
    """Read the shared capability input, never place names or native labels."""
    missing = {"level": "unknown", "predicted": None, "hookup": "unknown"}
    if data.get("planner_enabled", {}).get("start") is False:
        return {**missing, "reason": "planner_disabled"}
    native = data.get("start_input")
    if native is None:
        return {**missing, "reason": "missing_complete_start_grids"}
    if native.get("fidelity") != "prepared_16m_south_first":
        return {**missing, "reason": "unsupported_start_fidelity"}
    arrays = [
        np.asarray(native.get(k, []), dtype=float) for k in ("terrain_m", "depth_m")
    ]
    if any(a.size != GRID * GRID or not np.isfinite(a).all() for a in arrays):
        return {**missing, "reason": "missing_complete_start_grids"}
    if (arrays[1] < 0).any():
        raise ValueError("Negative start depth")
    result = start_witness(
        *(a.reshape(GRID, GRID) for a in arrays),
        {"highways": data.get("graph"), "start_tile": native.get("tile")},
    )
    return {
        **result,
        "hookup": "declared_plan" if result.get("predicted") else "unknown",
        "model": "pl1210-start-port-v1",
        "fidelity": native["fidelity"],
        "native_agreement": "unscored_new_runtime",
        "stock_comparison": "not_comparable",
    }
