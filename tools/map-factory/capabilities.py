"""Deterministic capability checks on a prepared export, not a game emulator.

The small grid/graph core is mirrored in capability-model.js. The browser feeds
estimated initial water; this CLI reads the export's actual prepared grids.
Neither a plan nor a successful metadata round trip is native game evidence.
"""

import argparse
from collections import deque
import hashlib
import json
import math
from pathlib import Path

import numpy as np

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
        "planner_enabled": {
            key: False
            for key in ("ship", "air")
            if hydro.get("highway_report", {}).get(key) == "off"
        },
        "grid": {"size": 271, "spacing_m": 64, "depth_m": coarse.ravel().tolist()},
        "buildable_fraction": float(dry[central].mean()),
    }


def assess_prepared(folder, native_context=None):
    ledger_bytes = (
        Path(__file__).resolve().parents[2] / "capabilities.json"
    ).read_bytes()
    ledger = json.loads(ledger_bytes)
    report = check(prepared_input(folder), ledger)
    report["model_sha256"] = hashlib.sha256(ledger_bytes).hexdigest()
    report["tool_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["inputs_sha256"] = {
        name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
        for name in ("terrain.u16", "water.u16", "hydrology.json")
    }
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
    values = {
        "terrain_relief_m": round(float(ground.max() - ground.min()), 1),
        "wet_central_fraction": round(
            float((CENTRAL & field["wet"]).sum() / CENTRAL.sum()), 4
        ),
        "median_land_slope_percent": round(float(np.median(field["slope"][land])), 1)
        if land.any()
        else None,
    }
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
            report["capabilities"][key] = {
                "level": "likely" if present else "not_possible_here",
                "reason": "final_plan_present" if present else "final_plan_empty",
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
    report["metrics"] = {
        key: {
            "value": value,
            "band": stock_band(value, ledger["stock_reference"]["metrics"].get(key)),
        }
        for key, value in values.items()
    }
    if "trees_total" in report["metrics"]:
        report["metrics"]["trees_total"]["basis"] = (
            "budgeted_export_plan_not_place_abundance"
        )
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
