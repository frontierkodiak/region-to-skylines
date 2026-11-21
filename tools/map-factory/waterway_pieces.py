"""Exact captured-row/clip provenance; never infer scope from native wetness."""

import hashlib
import json

import numpy as np

from maintained_water_inventory import coordinate, position, source_tag
from natural_water_inventory import compile_natural_inventory
from osm_highways import clip_box

HALF = 8640


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def native_walk(points):
    """Ordered nearest16m vertices; retain returns/loops, not just a longest path."""
    result = []
    for a, b in zip(points[:-1], points[1:]):
        count = max(1, int(np.ceil(np.max(np.abs(b - a)) / 16)))
        for p in np.linspace(a, b, count + 1):
            node = [int(np.rint((HALF - p[1]) / 16)), int(np.rint((p[0] + HALF) / 16))]
            if not result or node != result[-1]:
                result.append(node)
    if not result and len(points):
        p = points[0]
        result.append(
            [int(np.rint((HALF - p[1]) / 16)), int(np.rint((p[0] + HALF) / 16))]
        )
    return result


def catalog(geometry):
    rows = []
    for field in ("rivers", "streams"):
        features = geometry.get(field)
        if not isinstance(features, list):
            rows.append(
                {
                    "id": field,
                    "field": field,
                    "status": "unresolved",
                    "reason": "missing or invalid source collection",
                    "clips": [],
                }
            )
            continue
        for index, feature in enumerate(features):
            row = {
                "id": f"{field}:{index}",
                "field": field,
                "source_index": index,
                "clips": [],
            }
            try:
                row["source_sha256"] = digest(feature)
                intermittent = source_tag(feature, "intermittent") in (
                    True,
                    1,
                    "1",
                    "yes",
                    "true",
                )
                tunnel = source_tag(feature, "brunnel") == "tunnel"
                points = np.array([position(geometry["sq"], p) for p in feature["pts"]])
                if (
                    points.ndim != 2
                    or points.shape[1] != 2
                    or not len(points)
                    or not np.isfinite(points).all()
                ):
                    raise ValueError("invalid captured waterway coordinates")
                pieces = (
                    [(points, False, False)]
                    if len(points) == 1 and np.max(np.abs(points)) <= HALF
                    else clip_box(points, [-HALF, -HALF], [HALF, HALF])
                )
                for clip_index, (piece, start, end) in enumerate(pieces):
                    row["clips"].append(
                        {
                            "id": row["id"] + f":clip:{clip_index}",
                            "points_xz": [coordinate(p) for p in piece],
                            "start_clipped": bool(start),
                            "end_clipped": bool(end),
                            "nodes_rc": native_walk(piece),
                        }
                    )
                if intermittent or tunnel:
                    row.update(
                        status="excluded",
                        reason="explicit underground"
                        if tunnel
                        else "explicit intermittent",
                    )
                elif not pieces:
                    row.update(
                        status="outside_square",
                        reason="finite source polyline has no in-square part",
                    )
                else:
                    row["status"] = "perennial_surface"
            except (
                ValueError,
                KeyError,
                TypeError,
                IndexError,
                AttributeError,
            ) as error:
                row.update(status="unresolved", reason=str(error))
            rows.append(row)
    return {
        "schema": "polli.waterway-source-piece-catalog/1",
        "rows": rows,
        "native_model": "nearest16m nodes on every independent square-clipped part; not hydraulic connectivity or geographic flow proof",
    }


def compile_piece_inventory(geometry, hydro, lake_plan, pieces, stream_plan):
    if pieces != catalog(geometry) or stream_plan["catalog_sha256"] != digest(pieces):
        raise ValueError("Piece plan does not bind exact captured geometry")
    expected = {
        c["id"]
        for r in pieces["rows"]
        if r["field"] == "streams" and r["status"] == "perennial_surface"
        for c in r["clips"]
    }
    if set(stream_plan["clip_components"]) != expected:
        raise ValueError("Stream plan omits or invents an in-square source part")
    inventory = compile_natural_inventory(geometry, hydro, lake_plan)
    inventory["schema"] = "polli.maintained-water-inventory/3"
    inventory["algorithm"] += (
        "; exact captured-row and independently clipped-part provenance; geometric proposals do not establish authored support"
    )
    rows = {r["id"]: r for r in pieces["rows"]}
    for entry in inventory["entries"]:
        if entry["id"] not in rows:
            continue
        row = rows[entry["id"]]
        entry["source_piece_provenance"] = row
        if row["field"] == "streams" and row["status"] == "perennial_surface":
            entry.update(
                status="unresolved",
                reason="precise geometric proposal only; materialized stream plan, supply and junction support unresolved",
            )
            entry["stream_components"] = sorted(
                {stream_plan["clip_components"][c["id"]] for c in row["clips"]}
            )
    inventory["coverage_complete"] = not any(
        e["status"] == "unresolved" for e in inventory["entries"]
    )
    return inventory
