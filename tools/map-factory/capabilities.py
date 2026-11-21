"""Deterministic capability checks on a prepared export, not a game emulator.

The small grid/graph core is mirrored in capability-model.js. The browser feeds
estimated initial water; this CLI reads the export's actual prepared grids.
Neither a plan nor a successful metadata round trip is native game evidence.
"""

import argparse
import gzip
from collections import deque
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from start_model import evaluate_start, digest as start_digest
from terrain_interest import TERRAIN_INTEREST_MEASURES, terrain_interest_metrics
from water_model import (
    MODEL as WATER_MODEL,
    evaluate_water,
    normalize_water_opportunity,
)

KINDS = {
    "road": {"highway", "ramp"},
    "rail": {"rail"},
    "ship": {"ship"},
    "air": {"air"},
}


def ship_corridor(depth, size, spacing, rules):
    """Four-connected deep corridor, with one-cell shore clearance.

    Bounds are modelling choices awaiting native calibration, not claimed game
    limits. Neighbours beyond the square are unknown but do not erode an entry.
    Tie breaking is row-major, then N/W/E/S. No smoothing can cross dry ground.
    """
    deep = [float(d) >= rules["min_initial_depth_m"] for d in depth]
    safe = [False] * len(deep)
    reach = rules["shore_clearance_cells"]
    for r in range(size):
        for c in range(size):
            i = r * size + c
            safe[i] = deep[i] and all(
                deep[y * size + x]
                for y in range(max(0, r - reach), min(size, r + reach + 1))
                for x in range(max(0, c - reach), min(size, c + reach + 1))
            )
    seen = set()
    half = (size - 1) * spacing / 2
    for seed, wet in enumerate(safe):
        if not wet or seed in seen:
            continue
        queue, border, central = deque([seed]), [], False
        seen.add(seed)
        while queue:
            cell = queue.popleft()
            r, c = divmod(cell, size)
            central |= (
                abs(c * spacing - half) <= rules["central_half_extent_m"]
                and abs(r * spacing - half) <= rules["central_half_extent_m"]
            )
            if r in (0, size - 1) or c in (0, size - 1):
                border.append(cell)
            for y, x in ((r - 1, c), (r, c - 1), (r, c + 1), (r + 1, c)):
                i = y * size + x
                if 0 <= y < size and 0 <= x < size and safe[i] and i not in seen:
                    seen.add(i)
                    queue.append(i)
        # Extremal pairs avoid a quadratic search over a long coastline.
        if len(border) < 2 or not central:
            continue
        extremes = [
            min(border, key=lambda i: (i % size, i)),
            max(border, key=lambda i: (i % size, i)),
            min(border),
            max(border),
        ]
        for a in extremes:
            for b in extremes:
                ar, ac = divmod(a, size)
                br, bc = divmod(b, size)
                if (
                    math.hypot(ar - br, ac - bc) * spacing
                    >= rules["min_endpoint_separation_m"]
                ):
                    return {
                        "candidate": True,
                        "endpoints": [a, b],
                        "clearance_m": spacing * reach,
                        "depth_m": rules["min_initial_depth_m"],
                    }
    return {
        "candidate": False,
        "endpoints": [],
        "clearance_m": spacing * reach,
        "depth_m": rules["min_initial_depth_m"],
    }


def network_access(graph, capability):
    """Reachability through the authored graph, not counts of outside markers."""
    nodes = graph.get("nodes", [])
    forward, reverse = [[] for _ in nodes], [[] for _ in nodes]
    for edge in graph.get("edges", []):
        if edge["kind"] not in KINDS[capability]:
            continue
        a, b = edge["a"], edge["b"]
        if (
            not isinstance(a, int)
            or not isinstance(b, int)
            or not 0 <= a < len(nodes)
            or not 0 <= b < len(nodes)
        ):
            raise ValueError("Invalid capability graph edge")
        forward[a].append(b)
        reverse[b].append(a)
        if capability != "road":
            forward[b].append(a)
            reverse[a].append(b)
    outside = {i for i, n in enumerate(nodes) if n.get("outside")}
    incoming = sorted(i for i in outside if forward[i])
    outgoing = sorted(i for i in outside if reverse[i])
    for seed in incoming:
        queue, seen = deque([seed]), {seed}
        while queue:
            i = queue.popleft()
            if i != seed and i in outside:
                return {
                    "candidate": True,
                    "incoming": len(incoming),
                    "outgoing": len(outgoing),
                    "endpoints": [seed, i],
                }
            for neighbour in forward[i]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)
    return {
        "candidate": False,
        "incoming": len(incoming),
        "outgoing": len(outgoing),
        "endpoints": [],
    }


def digest(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def valid_native_context(context):
    if not isinstance(context, dict):
        return False
    assemblies = context.get("game_assemblies", {})
    protocol = context.get("protocol", {})
    return (
        isinstance(assemblies, dict)
        and digest(assemblies.get("Assembly-CSharp.dll"))
        and digest(assemblies.get("UnityEngine.dll"))
        and all(digest(value) for value in assemblies.values())
        and digest(context.get("mod_sha256"))
        and digest(context.get("collector_sha256"))
        and digest(context.get("runtime_game_sha256"))
        and context.get("runtime_game_assemblies") == assemblies
        and isinstance(protocol, dict)
        and protocol.get("entry") == "NewGameFromMap"
        and protocol.get("no_workshop") is True
        and protocol.get("strict_disable_mods") is False
        and protocol.get("inverted_traffic") is False
    )


def valid_native_identity_ref(ref):
    return (
        isinstance(ref, dict)
        and digest(ref.get("sha256"))
        and ref.get("file")
        == f"tools/map-factory/capability-evidence/runtime-identities/{ref['sha256']}.json"
    )


def qualify_exact_export(report, identity, ledger):
    """Qualify sampled native paths only, under an explicit exact environment."""
    if (
        report["mode"] != "export"
        or not isinstance(identity, dict)
        or not valid_native_context(identity.get("native_context"))
    ):
        return report
    artifact = identity.get("artifact_sha256", "")
    if not digest(artifact):
        return report
    inputs = identity.get("inputs_sha256", {})
    if (
        not isinstance(inputs, dict)
        or set(inputs) != {"terrain.u16", "water.u16", "hydrology.json"}
        or not all(digest(value) for value in inputs.values())
    ):
        return report
    controls = {"boundary_0", "boundary_1", "midpoint_0", "midpoint_1"}

    def canonical(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    capabilities = dict(report["capabilities"])
    for certificate in ledger.get("native_path_certificates", []):
        key = certificate["capability"]
        if (
            key not in ("ship", "air")
            or capabilities[key]["level"] != "likely"
            or certificate.get("scope") != "sampled_native_lane_paths_at_opening"
            or set(certificate.get("controls", {})) != controls
            or not all(certificate["controls"][control] is True for control in controls)
            or not certificate.get("evidence")
            or certificate.get("blocked_by")
            or not valid_native_identity_ref(
                certificate.get("runtime_identity_evidence")
            )
            or not digest(certificate.get("observation_sha256"))
            or not any(
                e.get("sha256") == certificate["observation_sha256"]
                for e in certificate["evidence"]
            )
            or certificate["artifact_sha256"] != artifact
            or canonical(certificate.get("inputs_sha256"))
            != canonical(identity.get("inputs_sha256"))
            or canonical(certificate.get("native_context"))
            != canonical(identity.get("native_context"))
        ):
            continue
        capabilities[key] = {
            **capabilities[key],
            "level": "promised",
            "reason": "exact_export_sampled_native_paths",
            "qualification": {
                name: certificate[name]
                for name in (
                    "scope",
                    "observed_at",
                    "artifact_sha256",
                    "native_context",
                    "runtime_identity_evidence",
                    "observation_sha256",
                    "evidence",
                    "limitations",
                )
            },
        }
    return {**report, "capabilities": capabilities}


def _round(value, places):
    return round(value, places) if math.isfinite(value) else None


def deposit_evidence(deposits, central_half):
    """Recorded deposits inside the square, split by kind.

    A missing record is not geographic absence, so this evidence never becomes a
    negative; it only ever names what a source actually recorded.
    """
    available = isinstance(deposits, dict) and deposits.get("status") == "available"
    records = deposits.get("records", []) if available else []
    if not isinstance(records, list):
        records = []
    summary = {
        "ore": {"records": 0, "central": 0, "central_weight": 0.0},
        "oil": {"records": 0, "central": 0, "central_weight": 0.0},
        "wells": 0,
    }
    for record in records:
        if record.get("kind") == "well":
            summary["wells"] += 1
            continue
        kind = (
            "oil"
            if record.get("kind") == "oil"
            else "ore"
            if record.get("kind") == "ore"
            else None
        )
        x, z = record.get("x"), record.get("z")
        if (
            kind is None
            or not isinstance(x, (int, float))
            or not isinstance(z, (int, float))
        ):
            continue
        if not (math.isfinite(x) and math.isfinite(z)):
            continue
        summary[kind]["records"] += 1
        if abs(x) <= central_half and abs(z) <= central_half:
            summary[kind]["central"] += 1
            weight = record.get("weight", 1)
            summary[kind]["central_weight"] += (
                weight
                if isinstance(weight, (int, float)) and math.isfinite(weight)
                else 1
            )
    for kind in ("ore", "oil"):
        summary[kind]["central_weight"] = _round(summary[kind]["central_weight"], 3)
    deposits_recorded = summary["ore"]["records"] + summary["oil"]["records"]
    return {
        "status": "available" if available else "unavailable",
        "source": deposits.get("source") if isinstance(deposits, dict) else None,
        "records": deposits_recorded,
        "wells": summary.pop("wells"),
        **summary,
    }


def place_evidence(grid, place, rules):
    """Vegetation and resource potential from place evidence.

    Mirrored in capability-model.js:placeEvidence. Every node is the same lattice
    as the depth grid; weights, class sets, slope cuts and thresholds come from
    the ledger's model_rules.place. Pure Python floats and loops, so the two
    cores accumulate in the same order and print the same rounded values.
    """
    size, spacing = grid["size"], grid["spacing_m"]
    total = size * size
    landcover = place.get("landcover") if isinstance(place, dict) else None
    values = (
        landcover.get("values")
        if isinstance(landcover, dict) and landcover.get("status") == "available"
        else None
    )
    if values is not None:
        if len(values) != total or any(
            not (isinstance(value, int) and not isinstance(value, bool))
            or value < 0
            or value > 255
            for value in values
        ):
            raise ValueError(
                "Land-cover evidence must match the capability grid as 0-255 classes"
            )
    terrain = place.get("terrain_m") if isinstance(place, dict) else None
    if not isinstance(terrain, list):
        terrain = None
    if terrain is not None:
        if len(terrain) != total or any(
            not isinstance(value, (int, float)) or not math.isfinite(value)
            for value in terrain
        ):
            raise ValueError(
                "Terrain evidence must match the capability grid as finite metres"
            )
    half = (size - 1) * spacing / 2
    central_half = rules["central_half_extent_m"]
    gx = gz = None
    if terrain is not None:
        gx, gz = [0.0] * total, [0.0] * total
        for r in range(size):
            r0, r1 = max(0, r - 1), min(size - 1, r + 1)
            dz = spacing if r in (0, size - 1) else 2 * spacing
            for c in range(size):
                c0, c1 = max(0, c - 1), min(size - 1, c + 1)
                dx = spacing if c in (0, size - 1) else 2 * spacing
                i = r * size + c
                gz[i] = (terrain[r1 * size + c] - terrain[r0 * size + c]) / dz
                gx[i] = (terrain[r * size + c1] - terrain[r * size + c0]) / dx
    forest = set(rules["forest_classes"])
    vegetated = set(rules["vegetated_classes"])
    crop = set(rules["crop_classes"])
    weight_of = {int(k): v for k, v in rules["tree_weight"].items()}
    fertile_of = {int(k): v for k, v in rules["fertile_weight"].items()}
    counts = {}
    central_land = covered = tree_cover = vegetated_nodes = crop_nodes = 0
    tree_sum = fertile_sum = 0.0
    for r in range(size):
        if abs(half - r * spacing) > central_half:
            continue
        for c in range(size):
            if abs(c * spacing - half) > central_half:
                continue
            i = r * size + c
            if not grid["depth_m"][i] < rules["land_depth_m"]:
                continue
            central_land += 1
            if values is None:
                continue
            cls = values[i]
            weight, fertile = weight_of.get(cls, 0), fertile_of.get(cls, 0)
            if cls != 0:
                covered += 1
            counts[cls] = counts.get(cls, 0) + 1
            if cls in forest:
                tree_cover += 1
            if cls in vegetated:
                vegetated_nodes += 1
            if cls in crop:
                crop_nodes += 1
            if gx is not None:
                axis = max(abs(gx[i]), abs(gz[i]))
                tree_sum += weight * min(
                    1.0,
                    max(
                        0.0,
                        (rules["tree_slope_limit_percent"] / 100 - axis)
                        / (rules["tree_slope_taper_percent"] / 100),
                    ),
                )
                slope = math.sqrt(gx[i] * gx[i] + gz[i] * gz[i]) * 100
                flat = min(
                    1.0,
                    max(
                        0.0,
                        (rules["fertile_slope_none_percent"] - slope)
                        / (
                            rules["fertile_slope_none_percent"]
                            - rules["fertile_slope_full_percent"]
                        ),
                    ),
                )
                fertile_sum += fertile * flat
            else:
                tree_sum += weight
                fertile_sum += fertile
    return {
        "grid": {
            "size": size,
            "spacing_m": spacing,
            "central_half_extent_m": central_half,
            "central_land_nodes": central_land,
        },
        "landcover": {
            "status": "available" if values is not None else "unavailable",
            "source": landcover.get("source") if values is not None else None,
            "fidelity": landcover.get("fidelity", "unspecified")
            if values is not None
            else None,
            "cell_m": landcover.get("cell_m") if values is not None else None,
            "sample_m": landcover.get("sample_m") if values is not None else None,
            "tiles": landcover.get("tiles", [])
            if values is not None and isinstance(landcover.get("tiles"), list)
            else [],
            "coverage_of_central_land": _round(covered / central_land, 4)
            if central_land
            else None,
            "class_counts": {str(cls): counts[cls] for cls in sorted(counts)},
        },
        "deposits": deposit_evidence(
            place.get("deposits") if isinstance(place, dict) else None, central_half
        ),
        "vegetation": {
            "tree_suitability": _round(tree_sum / central_land, 4)
            if central_land
            else None,
            "tree_cover_share_of_central_land": _round(tree_cover / central_land, 4)
            if central_land
            else None,
            "vegetated_share_of_central_land": _round(vegetated_nodes / central_land, 4)
            if central_land
            else None,
            "slope_screened": gx is not None,
            "slope_limit_percent": rules["tree_slope_limit_percent"],
            "candidate_min": rules["tree_suitability_min"],
        },
        "fertility": {
            "suitability": _round(fertile_sum / central_land, 4)
            if central_land
            else None,
            "crop_share_of_central_land": _round(crop_nodes / central_land, 4)
            if central_land
            else None,
            "slope_full_percent": rules["fertile_slope_full_percent"],
            "slope_none_percent": rules["fertile_slope_none_percent"],
            "candidate_min": rules["fertile_suitability_min"],
        },
        "balanced_top_up": "not_evidence",
    }


def place_capabilities(grid, place, rules):
    """The two candidate levels, never a native promise or a place-evidence No."""
    evidence = place_evidence(grid, place, rules)
    central_land = evidence["grid"]["central_land_nodes"]
    coverage = evidence["landcover"]["coverage_of_central_land"] or 0
    landcover_ok = (
        evidence["landcover"]["status"] == "available"
        and central_land > 0
        and coverage >= rules["landcover_min_coverage"]
    )
    suitability = evidence["vegetation"]["tree_suitability"]
    if evidence["landcover"]["status"] != "available":
        trees = {"level": "unknown", "reason": "no_landcover_evidence"}
    elif central_land == 0:
        trees = {"level": "unknown", "reason": "no_central_land"}
    elif not landcover_ok:
        trees = {"level": "unknown", "reason": "landcover_coverage_incomplete"}
    # The candidate threshold is not an impossibility boundary: a coarse
    # overview, a 90 percent covered window or a thin patch can all read low.
    # Only the export plan's own empty tree list can say No.
    elif suitability >= rules["tree_suitability_min"]:
        trees = {"level": "likely", "reason": "vegetation_suitability_candidate"}
    elif suitability > 0:
        trees = {"level": "unknown", "reason": "tree_support_below_candidate_threshold"}
    else:
        trees = {"level": "unknown", "reason": "no_tree_support_in_sampled_landcover"}
    deposits, fertile = evidence["deposits"], evidence["fertility"]["suitability"]
    crop = evidence["fertility"]["crop_share_of_central_land"] or 0
    central_deposit = deposits["status"] == "available" and (
        deposits["ore"]["central"] > 0 or deposits["oil"]["central"] > 0
    )
    if central_deposit:
        resources = {"level": "likely", "reason": "recorded_deposit_in_central_tiles"}
    elif landcover_ok and fertile >= rules["fertile_suitability_min"]:
        resources = {"level": "likely", "reason": "fertile_land_suitability_candidate"}
    elif deposits["status"] == "available" and deposits["records"] > 0:
        resources = {
            "level": "unknown",
            "reason": "recorded_deposit_outside_central_tiles",
        }
    elif landcover_ok and (fertile > 0 or crop > 0):
        resources = {
            "level": "unknown",
            "reason": "fertile_cover_below_candidate_threshold",
        }
    elif landcover_ok and deposits["status"] == "available":
        resources = {
            "level": "unknown",
            "reason": "no_recorded_deposit_or_fertile_cover",
        }
    elif landcover_ok:
        resources = {"level": "unknown", "reason": "deposit_evidence_unavailable"}
    elif deposits["status"] == "available":
        resources = {"level": "unknown", "reason": "landcover_evidence_unavailable"}
    else:
        resources = {"level": "unknown", "reason": "no_place_evidence"}
    return {
        "evidence": evidence,
        "resources": {**resources, "evidence": evidence},
        "trees": {**trees, "evidence": evidence},
    }


def place_measures(evidence):
    """The values the exporter report carries, beside the final plan's own."""
    return {
        "tree_suitability": evidence["vegetation"]["tree_suitability"],
        "tree_cover_share_of_central_land": evidence["vegetation"][
            "tree_cover_share_of_central_land"
        ],
        "vegetated_share_of_central_land": evidence["vegetation"][
            "vegetated_share_of_central_land"
        ],
        "landcover_coverage_of_central_land": evidence["landcover"][
            "coverage_of_central_land"
        ],
        "crop_share_of_central_land": evidence["fertility"][
            "crop_share_of_central_land"
        ],
        "fertile_land_suitability": evidence["fertility"]["suitability"],
        "recorded_ore_central_weight": evidence["deposits"]["ore"]["central_weight"],
        "recorded_oil_central_weight": evidence["deposits"]["oil"]["central_weight"],
    }


def evidence_definitions(ledger):
    """Measure definitions come from the one ledger, never a second catalog."""
    return {
        metric_id: metric["definition"]
        for capability in ledger["capabilities"]
        for metric_id, metric in capability.get("evidence_metrics", {}).items()
    }


def check(data, ledger):
    """Assess normalized geometry; only exact-context native receipts qualify paths."""
    if data.get("schema") != 1 or data.get("mode") not in ("export", "estimate"):
        raise ValueError("Expected capability input schema 1 and export/estimate mode")
    grid = data.get("grid")
    if grid:
        n, spacing = grid["size"], grid["spacing_m"]
        if (
            not isinstance(n, int)
            or n < 2
            or not math.isfinite(spacing)
            or spacing <= 0
        ):
            raise ValueError("Invalid capability grid")
        if len(grid["depth_m"]) != n * n or any(
            not math.isfinite(d) or d < 0 for d in grid["depth_m"]
        ):
            raise ValueError("Invalid capability depths")
    result = {}
    for key in KINDS:
        if data.get("planner_enabled", {}).get(key) is False:
            result[key] = {"level": "unknown", "reason": "planner_disabled"}
            continue
        graph = data.get("graph")
        witness = network_access(graph, key) if graph is not None else None
        if key == "ship":
            corridor = (
                ship_corridor(
                    grid["depth_m"], n, spacing, ledger["model_rules"]["ship"]
                )
                if grid
                else None
            )
            route = witness is not None and witness["candidate"]
            broad = corridor is not None and corridor["candidate"]
            absent = (
                data["mode"] == "export"
                and witness is not None
                and not route
                and corridor is not None
                and not broad
            )
            level = (
                "likely"
                if route or broad
                else "not_possible_here"
                if absent
                else "unknown"
            )
            if route:
                reason = (
                    "authored_ship_route"
                    if broad
                    else "authored_ship_route_corridor_unconfirmed"
                )
            elif broad:
                reason = (
                    "initial_deep_corridor_no_authored_route"
                    if witness is not None
                    else "initial_deep_corridor"
                )
            elif absent:
                reason = "no_authored_ship_route_or_initial_deep_corridor"
            else:
                reason = (
                    "no_corridor_in_estimate"
                    if data["mode"] == "estimate" and grid
                    else "ship_feasibility_not_established"
                )
            result[key] = {"level": level, "reason": reason}
            if corridor is not None:
                result[key]["witness"] = corridor
            if witness is not None:
                result[key]["authored_route"] = witness
        elif witness is not None:
            result[key] = {
                "level": "likely" if witness["candidate"] else "not_possible_here",
                "reason": "authored_edge_to_edge_route"
                if witness["candidate"]
                else "no_authored_edge_to_edge_route",
                "witness": witness,
            }
        else:
            observation = data.get("transport", {}).get(key)
            result[key] = {
                "level": "likely" if observation else "unknown",
                "reason": "mapped_candidate_not_routed"
                if observation
                else "transport_not_established",
            }
    for key in ("water", "start", "buildable", "resources", "trees", "water_risk"):
        result[key] = {"level": "unknown", "reason": "not_evaluated"}
    if (
        data.get("start_input") is not None
        or data.get("planner_enabled", {}).get("start") is False
    ):
        result["start"] = evaluate_start(data)
    result["water"] = (
        normalize_water_opportunity(data.get("water_opportunity"))
        if data["mode"] == "estimate"
        and data.get("planner_enabled", {}).get("water") is not False
        else evaluate_water(data)
    )
    buildable = data.get("buildable_fraction")
    if buildable is not None and math.isfinite(buildable) and 0 <= buildable <= 1:
        result["buildable"] = {
            "level": "likely"
            if buildable > 0
            else "not_possible_here"
            if data["mode"] == "export"
            else "unknown",
            "reason": "dry_low_slope_samples",
            "fraction": buildable,
        }
    if data.get("place") is not None:
        if not grid:
            raise ValueError("Place evidence needs a capability grid")
        if not ledger.get("model_rules", {}).get("place"):
            raise ValueError("Ledger lacks place evidence rules")
        place = place_capabilities(grid, data["place"], ledger["model_rules"]["place"])
        result["resources"] = place["resources"]
        result["trees"] = place["trees"]
    return qualify_exact_export(
        {
            "schema": 1,
            "model": ledger["model"],
            "mode": data["mode"],
            "capabilities": result,
        },
        data.get("export_identity"),
        ledger,
    )


# Mirrored in capability-model.js STOCK_MEASURES. Same definitions as
# survey/measure_maps.py: 1081 nodes, 16 m gradient, central 25-tile mask and
# 0.5 m wet threshold. The two terrain-shape measures live in
# terrain_interest.py so the stock survey and this report import one function.
# Strings are asserted equal across both cores by the Python/JavaScript parity
# test.
STOCK_MEASURES = {
    "terrain_relief_m": "highest minus lowest terrain over all 1081 x 1081 nodes, in metres",
    "terrain_roughness_percent": TERRAIN_INTEREST_MEASURES["terrain_roughness_percent"][
        "definition"
    ],
    "central_terrain_diversity_m": TERRAIN_INTEREST_MEASURES[
        "central_terrain_diversity_m"
    ]["definition"],
    "median_land_slope_percent": "median terrain gradient at 16 m spacing over the central 25 tiles' dry samples, in percent",
    "wet_central_fraction": "share of the central 25 tiles whose water depth is above 0.5 m",
}


def stock_metrics(ground, depth, field=None):
    """The five stock measures on 1081-square terrain/water metre grids.

    `field` is an already-computed `survey.measure_maps.terrain_fields` when the
    caller needs it for something else; the values are identical either way. The
    two terrain-shape measures read terrain only and need no water mask.
    """
    if ground.shape != (1081, 1081) or depth.shape != (1081, 1081):
        raise ValueError("Stock measures need 1081-square terrain and water grids")
    from survey.measure_maps import CENTRAL, terrain_fields

    field = terrain_fields(ground, depth) if field is None else field
    land = CENTRAL & field["land"]
    values = {
        "terrain_relief_m": round(float(ground.max() - ground.min()), 1),
        "wet_central_fraction": round(
            float((CENTRAL & field["wet"]).sum() / CENTRAL.sum()), 4
        ),
        "median_land_slope_percent": round(float(np.median(field["slope"][land])), 1)
        if land.any()
        else None,
    }
    values.update(terrain_interest_metrics(ground))
    return values


def stock_band(value, metric):
    if metric is None or value is None or not math.isfinite(value):
        return "not_comparable"
    return (
        "below_p25"
        if value < metric["p25"]
        else "above_p75"
        if value > metric["p75"]
        else "typical"
    )


LANDCOVER_SOURCE = (
    "ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data "
    "(2021) processed by ESA WorldCover consortium"
)
EVIDENCE_SOURCE = "USGS MRDS, MSHA Mines, NETL WELLS (tools/map-factory/evidence.py)"


def _landcover_nodes(raw, size):
    """Sample the writer's 1728-square north-first 10 m classes at the grid nodes.

    Node r stands at game z = half - r * spacing, which is native row
    6.4 * r; the containing 10 m cell is floor(). This is the same lattice the
    pan-time reader samples the WorldCover overviews at.
    """
    native = 1728
    out = []
    for r in range(size):
        row = min(native - 1, int(math.floor(6.4 * r)))
        base = row * native
        for c in range(size):
            out.append(int(raw[base + min(native - 1, int(math.floor(6.4 * c)))]))
    return out


def _read_input(folder, name):
    """Fixture layers ship gzipped; prepared folders usually do not."""
    direct, packed = folder / name, folder / (name + ".gz")
    if direct.exists():
        return direct.read_bytes()
    if packed.exists():
        return gzip.decompress(packed.read_bytes())
    raise FileNotFoundError(direct)


def place_input(folder, size=271):
    """The place-evidence block the shared model reads, from committed inputs.

    Land cover comes from the writer's own landcover.u8.gz; deposits from the
    exporter's evidence.json. Missing inputs stay explicitly unavailable rather
    than becoming zeros, so the model can tell "not recorded" from "absent".
    """
    import gzip

    place = {
        "deposits": {"status": "unavailable", "source": EVIDENCE_SOURCE, "records": []}
    }
    landcover_path = folder / "landcover.u8.gz"
    if landcover_path.exists():
        raw = gzip.decompress(landcover_path.read_bytes())
        if len(raw) != 1728 * 1728:
            raise ValueError("Land cover must be the writer's 1728-square grid")
        ground = np.frombuffer(_read_input(folder, "terrain.u16"), dtype="<u2")
        ground = ground.reshape(1081, 1081).astype(float) / 64
        place["terrain_m"] = [
            float(ground[1080 - 4 * r, 4 * c]) for r in range(size) for c in range(size)
        ]
        place["landcover"] = {
            "status": "available",
            "fidelity": "prepared_landcover_10m",
            "source": LANDCOVER_SOURCE,
            "cell_m": 10.0,
            "sample_m": 10.0,
            "tiles": [],
            "values": _landcover_nodes(raw, size),
        }
    evidence_path = folder / "evidence.json"
    if evidence_path.exists():
        found = json.loads(evidence_path.read_text()).get("evidence", [])
        place["deposits"] = {
            "status": "available",
            "source": EVIDENCE_SOURCE,
            "records": [
                {
                    key: record[key]
                    for key in ("kind", "x", "z", "weight")
                    if key in record
                }
                for record in found
            ],
        }
    return place


def evidence_inputs(folder):
    """Bind every place-evidence file the report consumed, present or missing.

    Kept out of `inputs_sha256`: a native path certificate binds exactly the
    three physical inputs, and an evidence file must never be folded into an
    old receipt. A missing file keeps explicit provenance rather than silence.
    """
    bound = {}
    for key, name in (("landcover", "landcover.u8.gz"), ("deposits", "evidence.json")):
        path = folder / name
        present = path.exists()
        bound[key] = {
            "file": name,
            "status": "present" if present else "missing",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
            if present
            else None,
        }
    return bound


def prepared_input(folder):
    """Read final south-first grids; conservatively block-min to north-first 64 m."""
    depth = (
        np.fromfile(folder / "water.u16", dtype="<u2").reshape(1081, 1081).astype(float)
        / 64
    )
    ground = (
        np.fromfile(folder / "terrain.u16", dtype="<u2")
        .reshape(1081, 1081)
        .astype(float)
        / 64
    )
    hydro = json.loads((folder / "hydrology.json").read_text())
    start_input = {
        "fidelity": "prepared_16m_south_first",
        "tile": hydro.get("start_tile"),
        "terrain_m": ground.ravel().tolist(),
        "depth_m": depth.ravel().tolist(),
    }
    depth = np.flipud(depth)
    coarse = np.zeros((271, 271))
    for r in range(271):
        for c in range(271):
            coarse[r, c] = depth[
                r * 4 : min(1081, r * 4 + 4), c * 4 : min(1081, c * 4 + 4)
            ].min()
    dy, dx = np.gradient(ground, 16)
    central = np.s_[240:840, 240:840]
    dry = (np.flipud(depth) < 0.25) & (np.hypot(dx, dy) < 0.15)
    return {
        "schema": 1,
        "mode": "export",
        "graph": hydro.get("highways"),
        "start_input": start_input,
        "water_plan": {"samples": hydro.get("samples")},
        "planner_enabled": {
            key: False
            for key in ("ship", "air")
            if hydro.get("highway_report", {}).get(key) == "off"
        },
        "grid": {"size": 271, "spacing_m": 64, "depth_m": coarse.ravel().tolist()},
        "buildable_fraction": float(dry[central].mean()),
        "place": place_input(folder),
    }


STOCK_HELPER_FILE = "tools/map-factory/terrain_interest.py"
STOCK_READER_FILE = "tools/map-factory/survey/measure_maps.py"


def stock_measure_sources():
    """The files the stock measures actually execute, resolved from the imports."""
    import survey.measure_maps as measure_maps
    import terrain_interest

    return {
        "helper": (STOCK_HELPER_FILE, Path(terrain_interest.__file__).resolve()),
        "reader": (STOCK_READER_FILE, Path(measure_maps.__file__).resolve()),
    }


def stock_measure_binding(ledger, ledger_bytes):
    """Current stock-measure algorithm bytes, validated against the declared study.

    The three physical inputs and the native/exact-export identity keep their own
    bindings. This block is only the measure dependency: the helper and the
    survey reader/predicate it consumes. The bytes are hashed from the modules
    actually imported, then checked against `capabilities.json`'s declared stock
    study. A changed, stale or missing dependency refuses the report instead of
    emitting a number under the old fingerprint.
    """
    study = ledger.get("stock_reference", {}).get("terrain_interest")
    if not study:
        raise ValueError("Stock measure study is missing from the capability ledger")
    declared = study.get("tool", {})
    bound = {}
    for key, declared_key in (("helper", "measure_source"), ("reader", "reader")):
        file, path = stock_measure_sources()[key]
        if not path.is_file():
            raise ValueError(f"Stock measure {key} dependency is missing: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = declared.get(declared_key, {}).get("sha256")
        if not expected:
            raise ValueError(
                f"Stock measure {key} is not declared in the ledger stock study"
            )
        if digest != expected:
            raise ValueError(
                f"Stock measure {key} bytes do not match the ledger's declared "
                f"study: {path} ({digest} != {expected})"
            )
        bound[key] = {"file": file, "sha256": digest, "validated": True}
    return {
        "version": study.get("version"),
        "status": "validated_against_ledger_stock_study",
        "ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        "artifact": study.get("artifact"),
        "artifact_sha256": study.get("artifact_sha256"),
        "rows_sha256": study.get("rows_sha256"),
        "source_sha256": bound,
    }


def assess_prepared(folder, native_context=None):
    ledger_bytes = (
        Path(__file__).resolve().parents[2] / "capabilities.json"
    ).read_bytes()
    ledger = json.loads(ledger_bytes)
    stock_binding = stock_measure_binding(ledger, ledger_bytes)
    report = check(prepared_input(folder), ledger)
    report["model_sha256"] = hashlib.sha256(ledger_bytes).hexdigest()
    report["tool_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["stock_measures"] = stock_binding
    report["inputs_sha256"] = {
        name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
        for name in ("terrain.u16", "water.u16", "hydrology.json")
    }
    report["evidence_inputs"] = evidence_inputs(folder)
    report["scope"] = (
        "Initial export geometry. An explicit matching native context can qualify only recorded exact-export sampled lane paths at opening. Native service, hydraulics, start hookups and game tool placement are not certified."
    )
    from survey.measure_maps import CENTRAL, terrain_fields

    ground, depth = [
        np.fromfile(folder / name, dtype="<u2").reshape(1081, 1081).astype(float) / 64
        for name in ("terrain.u16", "water.u16")
    ]
    field = terrain_fields(ground, depth)
    land = CENTRAL & field["land"]
    values = stock_metrics(ground, depth, field)
    plan_path = folder / "plan.npz"
    if plan_path.exists():
        with np.load(plan_path) as plan:
            for key in ("ore", "oil", "fertility", "forest"):
                values[f"{key}_central_land_fraction"] = round(
                    float(((plan[key] > 0) & land).sum() / max(int(land.sum()), 1)), 4
                )
            values["trees_total"] = int(plan["px"].size)
        report["inputs_sha256"]["plan.npz"] = hashlib.sha256(
            plan_path.read_bytes()
        ).hexdigest()
        for key in ("resources", "trees"):
            present = (
                values["trees_total"] > 0
                if key == "trees"
                else any(
                    values[f"{r}_central_land_fraction"] > 0
                    for r in ("ore", "oil", "fertility")
                )
            )
            current = report["capabilities"][key]
            report["capabilities"][key] = {
                "level": "likely" if present else "not_possible_here",
                "reason": "final_plan_present" if present else "final_plan_empty",
                **(
                    {"evidence": current["evidence"]} if current.get("evidence") else {}
                ),
            }
    packages = list(folder.glob("*.crp"))
    if len(packages) == 1:
        from soak import panel_expectations

        metadata = panel_expectations(packages[0])
        values["buildable_percent"] = metadata["buildableArea"]
        for key, native in zip(
            ("road", "rail", "ship", "air"),
            ("Roads", "TrainTracks", "ShipPath", "PlanePath"),
        ):
            values[f"incoming_{key}_entries"] = metadata["connections"][
                "incoming" + native
            ]
        report["artifact_sha256"] = hashlib.sha256(packages[0].read_bytes()).hexdigest()
    evidence = report["capabilities"]["trees"].get("evidence")
    if evidence:
        values.update(place_measures(evidence))
    definitions = {**STOCK_MEASURES, **evidence_definitions(ledger)}
    report["fidelity"] = "prepared_grids"
    report["metrics"] = {
        key: {
            "value": value,
            "band": stock_band(value, ledger["stock_reference"]["metrics"].get(key)),
            **({"definition": definitions[key]} if key in definitions else {}),
        }
        for key, value in values.items()
    }
    if "trees_total" in report["metrics"]:
        report["metrics"]["trees_total"]["basis"] = (
            "budgeted_export_plan_not_place_abundance"
        )
    start = report["capabilities"]["start"]
    start["binding"] = {
        "model": "pl1210-start-port-v1",
        "source_sha256": {
            name: hashlib.sha256(
                (Path(__file__).resolve().parents[2] / name).read_bytes()
            ).hexdigest()
            for name in (
                "start-model.js",
                "tools/map-factory/start_model.py",
                "tools/map-factory/real_roads.py",
                "tools/map-factory/crp.py",
                "tools/map-factory/capabilities.py",
            )
        },
        "ledger_sha256": report["model_sha256"],
        "inputs_sha256": {
            name: report["inputs_sha256"][name]
            for name in ("terrain.u16", "water.u16", "hydrology.json")
        },
        "artifact_sha256": report.get("artifact_sha256"),
        "witness_sha256": start_digest(start["witness"])
        if start.get("witness")
        else None,
        "agreement": "unscored_new_runtime",
    }
    water = report["capabilities"]["water"]
    water["binding"] = {
        "model": WATER_MODEL,
        "source_sha256": {
            name: hashlib.sha256(
                (Path(__file__).resolve().parents[2] / name).read_bytes()
            ).hexdigest()
            for name in (
                "capability-model.js",
                "water-model.js",
                "start-model.js",
                "tools/map-factory/water_model.py",
                "tools/map-factory/start_model.py",
                "tools/map-factory/real_roads.py",
                "tools/map-factory/capabilities.py",
            )
        },
        "ledger_sha256": report["model_sha256"],
        "tool_sha256": report["tool_sha256"],
        "inputs_sha256": {
            name: report["inputs_sha256"][name]
            for name in ("terrain.u16", "water.u16", "hydrology.json")
        },
        "artifact_sha256": report.get("artifact_sha256"),
        "witness_sha256": start_digest(water["witness"])
        if water.get("witness")
        else None,
        "agreement": "unscored_new_runtime",
    }
    return qualify_exact_export(
        report,
        {
            "artifact_sha256": report.get("artifact_sha256"),
            "inputs_sha256": {
                name: report["inputs_sha256"][name]
                for name in ("terrain.u16", "water.u16", "hydrology.json")
            },
            "native_context": native_context,
        },
        ledger,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--native-context",
        type=Path,
        help="Explicit expected game/mod/protocol context JSON; never inferred from coordinates",
    )
    args = parser.parse_args()
    context = (
        json.loads(args.native_context.read_text()) if args.native_context else None
    )
    args.out.write_text(
        json.dumps(assess_prepared(args.prepared, context), indent=2) + "\n"
    )
