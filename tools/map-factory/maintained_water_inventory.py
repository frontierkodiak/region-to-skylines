"""Compile source-only maintained-water contracts; never select from wet pixels.

The native 16 m geometry raster defines polygon components and the 32 m erosion.
Each captured polygon piece stays separate: names never merge denominators.
Lines are clipped before arc-length sectors; small bodies keep a point contract.
"""

import hashlib
import json
import math

import numpy as np
from scipy import ndimage

from maintained_water import ROOT
from osm_highways import arc, clip_box
from prepare import pixel
from region import raster

HALF = 8640
FIELDS = ("rivers", "streams", "lakes", "riverAreas", "oceans")
COMPILER_FILES = (
    "maintained_water_inventory.py",
    "maintained_water.py",
    "osm_highways.py",
    "prepare.py",
    "region.py",
    "surface_water.py",
    "pyproject.toml",
    "uv.lock",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def definition():
    path = ROOT / "maintained-water-definition.json"
    if (
        sha(path)
        != json.loads((ROOT / "outcome-freeze.json").read_text())["definition_sha256"]
    ):
        raise ValueError("Maintained-water definition differs from outcome freeze")
    return json.loads(path.read_text())


def position(sq, point):
    col, row = pixel(sq, point)
    return np.array([col * 16 - HALF, HALF - row * 16])


def coordinate(point):
    return [round(float(v), 6) for v in point]


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def small_body_point(sq, rings, labels, component, preferred_z):
    """Use an actual clipped polygon interior, including sub-node small ponds."""
    paths = [np.array([position(sq, p) for p in ring]) for ring in rings]
    levels = sorted(
        {
            -HALF,
            HALF,
            *(float(np.clip(p[1], -HALF, HALF)) for path in paths for p in path),
        }
    )
    midpoints = [(a + b) / 2 for a, b in zip(levels, levels[1:]) if a < b]
    for z in sorted(midpoints, key=lambda v: (abs(v - preferred_z), v)):
        crossings = []
        for path in paths:
            for a, b in zip(path, np.roll(path, -1, axis=0)):
                if (a[1] > z) != (b[1] > z):
                    crossings.append(
                        float(a[0] + (b[0] - a[0]) * (z - a[1]) / (b[1] - a[1]))
                    )
        crossings.sort()
        for left, right in zip(crossings[::2], crossings[1::2]):
            left, right = max(-HALF, left), min(HALF, right)
            if left >= right:
                continue
            x = (left + right) / 2
            # Match ImageDraw's positive pixel-coordinate truncation.
            row = int(np.floor((HALF - z) / 16))
            col = int(np.floor((x + HALF) / 16))
            if labels[row, col] == component:
                return coordinate([x, z])
    raise ValueError("raster component has no supported clipped polygon interior")


def line_contracts(sq, feature):
    points = np.array([position(sq, p) for p in feature["pts"]])
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError("invalid waterway coordinates")
    if len(points) == 1 and np.max(np.abs(points[0])) <= HALF:
        return [
            {
                "kind": "natural",
                "small_feature_point": True,
                "points_xz": [coordinate(points[0])],
            }
        ]
    contracts = []
    for piece, _, _ in clip_box(points, [-HALF, -HALF], [HALF, HALF]):
        piece = piece[np.r_[True, np.any(np.diff(piece, axis=0) != 0, axis=1)]]
        distance = arc(piece)
        length = float(distance[-1])
        if length == 0:
            contracts.append(
                {"kind": "natural", "length_m": 0, "points_xz": [coordinate(piece[0])]}
            )
            continue
        for start in np.arange(0, length, 512):
            end = min(float(start + 512), length)
            offsets = np.linspace(start, end, max(1, math.ceil((end - start) / 64)) + 1)
            planned = np.column_stack(
                [np.interp(offsets, distance, piece[:, axis]) for axis in (0, 1)]
            )
            contracts.append(
                {
                    "kind": "natural",
                    "length_m": end - float(start),
                    "points_xz": [coordinate(p) for p in planned],
                }
            )
    return contracts


def body_contracts(sq, feature):
    rings = feature["rings"]
    if not rings or any(len(r) < 3 for r in rings):
        raise ValueError("invalid water-body rings")
    projected = np.array([position(sq, p) for ring in rings for p in ring])
    if not np.isfinite(projected).all():
        raise ValueError("invalid water-body coordinates")
    mask = raster(sq, [feature], polygons=True)
    labels, count = ndimage.label(mask, np.ones((3, 3)))
    contracts = []
    for component, region in enumerate(ndimage.find_objects(labels), 1):
        local = labels[region] == component
        # Padding treats the square boundary as a boundary, even for full ocean.
        distance = ndimage.distance_transform_edt(np.pad(local, 1))[1:-1, 1:-1] * 16
        rows, cols = np.nonzero(local & (distance > 32))
        rows, cols = rows + region[0].start, cols + region[1].start
        chosen = (rows % 4 == 0) & (cols % 4 == 0)
        rows, cols = rows[chosen], cols[chosen]
        small = len(rows) == 0
        if small:
            # Choose the scanline nearest the deepest node, never a wet pixel.
            y, x = np.unravel_index(np.argmax(distance), distance.shape)
            points = [
                small_body_point(
                    sq, rings, labels, component, HALF - (y + region[0].start) * 16
                )
            ]
        else:
            points = [
                [int(x) * 16 - HALF, HALF - int(y) * 16] for y, x in zip(rows, cols)
            ]
        contracts.append(
            {
                "kind": "natural",
                "component": component,
                "small_feature_point": small,
                "points_xz": points,
            }
        )
    if not count:
        raise ValueError(
            "no native-raster component; subgrid or outside-square geometry unresolved"
        )
    return contracts


def source_tag(feature, name):
    source = feature.get("sourceFeature", {}).get("properties", {})
    if name in source and name in feature and source[name] != feature[name]:
        raise ValueError(f"{name} disagrees with source properties")
    return source.get(name, feature.get(name))


def waterway_support_issue(feature, field, hydro):
    """Old authored plans identify omissions by name/class, not source piece ID."""
    key = (
        feature.get("name") or "unnamed waterway",
        "river" if field == "rivers" else "stream",
    )
    modeled, omitted = hydro.get("rivers"), hydro.get("unmodeled_short_surface_reaches")
    if not isinstance(modeled, list) or not isinstance(omitted, list):
        return "missing authored surface-waterway support inventory"

    def same(row):
        return (row.get("name") or "unnamed waterway", row.get("class", "river")) == key

    if any(same(row) for row in omitted):
        return "authored plan omits a same-name/class reach; source-piece support unresolved"
    matching = [row for row in modeled if same(row)]
    if not matching or any(row.get("unforced_infeasible_stream") for row in matching):
        return (
            "no fully supported authored same-name/class waterway; contracts retained"
        )
    return None


def compile_inventory(geometry, hydro):
    definition()
    entries = []
    for field in FIELDS:
        if not isinstance(geometry.get(field), list):
            entries.append(
                {
                    "id": field,
                    "status": "unresolved",
                    "reason": "missing or invalid captured feature collection",
                }
            )
            continue
        for index, feature in enumerate(geometry[field]):
            if not isinstance(feature, dict):
                entries.append(
                    {
                        "id": f"{field}:{index}",
                        "status": "unresolved",
                        "reason": "invalid captured feature",
                    }
                )
                continue
            entry = {
                "id": f"{field}:{index}",
                "name": feature.get("name", ""),
                "field": field,
                "source_index": index,
            }
            try:
                intermittent = source_tag(feature, "intermittent")
                tunnel = source_tag(feature, "brunnel") == "tunnel"
                if intermittent in (True, 1, "1", "yes", "true") or tunnel:
                    entry.update(
                        status="excluded",
                        reason="explicit intermittent"
                        if not tunnel
                        else "explicit underground; not surface water",
                    )
                else:
                    contracts = (
                        line_contracts
                        if field in ("rivers", "streams")
                        else body_contracts
                    )(geometry["sq"], feature)
                    if not contracts:
                        entry.update(
                            status="unresolved",
                            reason="no clipped line contract; outside or unsupported geometry",
                        )
                    else:
                        entry.update(status="compiled", contracts=contracts)
                        if field in ("rivers", "streams"):
                            issue = waterway_support_issue(feature, field, hydro)
                            if issue:
                                entry.update(status="unresolved", reason=issue)
            except (ValueError, KeyError, TypeError, IndexError) as error:
                entry.update(status="unresolved", reason=str(error))
            entries.append(entry)
    # Captures already normalized by surface_geometry retain underground evidence.
    for index, feature in enumerate(geometry.get("undergroundWaterways", [])):
        valid = source_tag(feature, "brunnel") == "tunnel"
        entries.append(
            {
                "id": f"undergroundWaterways:{index}",
                "status": "excluded" if valid else "unresolved",
                "reason": "explicit underground; not surface water"
                if valid
                else "underground classification lacks source evidence",
            }
        )
    if "sources" not in hydro:
        entries.append(
            {
                "id": "authored:sources",
                "status": "unresolved",
                "reason": "missing authored water plan",
            }
        )
    for index, source in enumerate(hydro.get("sources", [])):
        kind = source.get("class")
        entry = {
            "id": f"authored:sources:{index}",
            "name": source.get("name", ""),
            "source_index": index,
        }
        if kind in {"river", "stream", "lake", "ocean"}:
            fields = {
                "river": ("rivers", "riverAreas"),
                "stream": ("streams",),
                "lake": ("lakes",),
                "ocean": ("oceans",),
            }[kind]
            captured = any(geometry.get(field) for field in fields)
            entry.update(
                status="natural_control" if captured else "unresolved",
                reason="natural contracts compiled independently from captured geometry"
                if captured
                else "authored natural control has no captured feature inventory",
            )
        elif kind in {"reservoir", "storage", "intake"}:
            try:
                x, _, z = source["position"]
                if not all(math.isfinite(v) and abs(v) <= HALF for v in (x, z)):
                    raise ValueError("invalid engineered anchor")
                entry.update(
                    status="compiled",
                    contracts=[{"kind": "engineered", "points_xz": [[x, z]]}],
                )
            except (ValueError, KeyError, TypeError) as error:
                entry.update(status="unresolved", reason=str(error))
        else:
            entry.update(
                status="unresolved", reason=f"unsupported authored water class: {kind}"
            )
        entries.append(entry)
    # Additional authored maintained bodies cannot silently bypass the compiler.
    for index, _ in enumerate(hydro.get("maintained_features", [])):
        entries.append(
            {
                "id": f"authored:maintained_features:{index}",
                "status": "unresolved",
                "reason": "additional authored feature requires an explicit supported contract",
            }
        )
    points = []
    for entry in entries:
        for sector, contract in enumerate(entry.get("contracts", [])):
            contract["id"] = f"{entry['id']}:{sector}"
            contract["probe_names"] = []
            for index, (x, z) in enumerate(contract["points_xz"]):
                name = f"maintained:{contract['id']}:{index}"
                contract["probe_names"].append(name)
                points.append({"name": name, "x": x, "z": z, "required": True})
    return {
        "schema": "polli.maintained-water-inventory/1",
        "definition_sha256": sha(ROOT / "maintained-water-definition.json"),
        "algorithm": "source geometry only; clipped line pieces <=512m with <=64m arc spacing; separate captured polygon-piece 8-neighbour native16m components; padded Euclidean >32m erosion; world64m lattice; small-polygon interior scanline fallback nearest deepest node; no name pooling or outcome filtering",
        "entries": entries,
        "points": points,
        "coverage_complete": not any(e["status"] == "unresolved" for e in entries),
        "stable_water_promise": "unknown",
    }


def observation_complete(report, samples):
    policy = definition()["native_observation"]
    try:
        minutes = [
            (r["stats"]["frame"] - report["start_frame"])
            / report["frames_per_game_minute"]
            for r in samples
        ]
        gaps = [b - a for a, b in zip(minutes, minutes[1:])]
        return bool(
            len(samples) >= policy["samples_min"]
            and report["game_minutes"] >= policy["game_minutes_min"]
            and all(math.isfinite(m) for m in minutes)
            and abs(minutes[0]) <= 0.001
            and minutes[-1] >= policy["game_minutes_min"]
            and all(0 < g <= policy["largest_gap_game_minutes_max"] for g in gaps)
            and len({r["label"] for r in samples}) == len(samples)
        )
    except (KeyError, TypeError, ZeroDivisionError):
        return False


def initial_natural_checks(inventory, water):
    """Inspect authored south-first depth nodes; not a native run or prefilter."""
    if water.shape != (1081, 1081):
        raise ValueError("Expected native 1081-square authored depth nodes")
    policy = definition()["thresholds"]
    rows = []
    for entry in inventory["entries"]:
        for contract in entry.get("contracts", []):
            if contract["kind"] != "natural":
                continue
            wet = 0
            for x, z in contract["points_xz"]:
                x, z = float(np.float32(x)), float(np.float32(z))
                cx, cz = int(np.rint((x + HALF) / 16)), int(np.rint((z + HALF) / 16))
                ys = np.arange(max(0, cz - 4), min(1080, cz + 4) + 1)
                xs = np.arange(max(0, cx - 4), min(1080, cx + 4) + 1)
                yy, xx = np.meshgrid(ys, xs, indexing="ij")
                nearby = (xx * 16 - HALF - x) ** 2 + (
                    yy * 16 - HALF - z
                ) ** 2 <= policy["natural_nearby_radius_m"] ** 2
                wet += bool(
                    np.any(
                        water[yy, xx][nearby] / 64
                        > policy["natural_depth_m_min_exclusive"]
                    )
                )
            total = len(contract["points_xz"])
            rows.append(
                {
                    "id": contract["id"],
                    "wet": wet,
                    "total": total,
                    "status": "pass"
                    if total
                    and wet / total >= policy["natural_fraction_per_feature_min"]
                    else "fail",
                }
            )
    return {
        "schema": "polli.authored-natural-initialization-check/1",
        "contracts": rows,
        "scope": "Exact authored initial-grid diagnostic only; no new native observation, historical rescore, holdout prefilter or maintained-water qualification.",
        "stable_water_promise": "unknown",
    }


def feature_outcome(inventory, report, samples):
    """Input identities are checked by the file-bound collector, not inferred here."""
    policy = definition()["thresholds"]
    if inventory["definition_sha256"] != sha(ROOT / "maintained-water-definition.json"):
        raise ValueError("Inventory uses a different definition")
    complete = observation_complete(report, samples)
    observations = []
    for row in samples:
        points = {}
        for p in row.get("water", {}).get("samples", []):
            points.setdefault(p.get("name"), []).append(p)
        observations.append((row["label"], points))
    results = []
    for entry in inventory["entries"]:
        for contract in entry.get("contracts", []):
            engineered = contract["kind"] == "engineered"
            key = "depth" if engineered else "max_depth_within_64m"
            threshold = (
                policy["storage_exact_depth_m_min"]
                if engineered
                else policy["natural_depth_m_min_exclusive"]
            )
            required = 1 if engineered else policy["natural_fraction_per_feature_min"]
            checks = []
            for label, observed in observations:
                wet, missing = 0, 0
                for name, (x, z) in zip(contract["probe_names"], contract["points_xz"]):
                    matches = observed.get(name, [])
                    values = [p.get(key) for p in matches]
                    if (
                        not values
                        or any(
                            not finite_number(p.get(axis))
                            or abs(p[axis] - wanted) > 0.001
                            for p in matches
                            for axis, wanted in (("x", x), ("z", z))
                        )
                        or any(
                            not finite_number(v) or (v < 0 and not engineered)
                            for v in values
                        )
                    ):
                        missing += 1
                    else:
                        depth = min(values)
                        wet += depth >= threshold if engineered else depth > threshold
                total = len(contract["points_xz"])
                status = (
                    "fail"
                    if total and (wet + missing) / total < required
                    else "unknown"
                    if missing or not total
                    else "pass"
                )
                checks.append(
                    {
                        "label": label,
                        "status": status,
                        "wet": wet,
                        "missing": missing,
                        "total": total,
                    }
                )
            states = {c["status"] for c in checks}
            status = (
                "fail"
                if "fail" in states
                else "pass"
                if complete and states == {"pass"}
                else "unknown"
            )
            results.append(
                {
                    "id": contract["id"],
                    "kind": contract["kind"],
                    "status": status,
                    "samples": checks,
                }
            )
    states = {r["status"] for r in results}
    status = (
        "fail"
        if "fail" in states
        else "pass"
        if inventory["coverage_complete"] and complete and states <= {"pass"}
        else "unknown"
    )
    return {
        "schema": "polli.maintained-water-feature-outcome/1",
        "status": status,
        "observation_complete": complete,
        "coverage_complete": inventory["coverage_complete"],
        "contracts": results,
        "stable_water_promise": "unknown",
        "scope": "Bound feature checks only; original flood and drying comparators, runtime identity and other acceptance remain separate.",
    }
