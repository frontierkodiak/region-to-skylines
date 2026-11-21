"""Supplementary public polygon coverage, never hydraulic/source identity."""

import argparse
from collections import Counter
from pathlib import Path

import numpy as np

from bank_authority import ROOT, STEPS8, TARGETS, load, sha, write
from maintained_water_inventory import position

SOURCE = "diagnostics/public_bank_coverage.py"
DESIGN = (
    "calibration/pl1191-construction-v1/development/phase13-public-polygon-policy.md"
)


def rings(parts):
    """Assemble only literal endpoint incidences, never nearest-endpoint joins."""
    pending = []
    for part in parts:
        if not part or any(p is None or "lon" not in p or "lat" not in p for p in part):
            raise ValueError("Missing public polygon geometry")
        points = [(p["lon"], p["lat"]) for p in part]
        if len(points) < 2:
            raise ValueError("Unsupported singleton polygon member")
        pending.append(points)
    result = []
    while pending:
        path = pending.pop(0)
        while path[0] != path[-1]:
            matches = [
                (i, reverse)
                for i, part in enumerate(pending)
                for reverse in (False, True)
                if part[-1 if reverse else 0] == path[-1]
            ]
            if len(matches) != 1:
                raise ValueError("Unclosed or ambiguous literal polygon incidence")
            i, reverse = matches[0]
            part = pending.pop(i)
            path.extend((part[::-1] if reverse else part)[1:])
        if len(set(path)) < 3:
            raise ValueError("Degenerate polygon")
        result.append(path)
    return result


def polygon(element):
    if element["type"] == "way":
        if not element.get("nodes") or element["nodes"][0] != element["nodes"][-1]:
            raise ValueError("Water-tagged way is not a closed polygon")
        return rings([element["geometry"]]), []
    if element["type"] != "relation" or element["tags"].get("type") != "multipolygon":
        raise ValueError("Unsupported public polygon type")
    groups = {"outer": [], "inner": []}
    for member in element["members"]:
        if member["type"] != "way" or member["role"] not in groups:
            raise ValueError("Unsupported multipolygon member/role")
        groups[member["role"]].append(member.get("geometry"))
    if not groups["outer"]:
        raise ValueError("No outer polygon")
    return rings(groups["outer"]), rings(groups["inner"])


def inside(points, ring):
    """Ray parity with explicit boundary uncertainty in projected metres."""
    points, ring = np.asarray(points, float), np.asarray(ring, float)
    hit, boundary = np.zeros(len(points), bool), np.zeros(len(points), bool)
    for a, b in zip(ring, ring[1:]):
        edge = b - a
        norm = float(edge @ edge)
        if norm == 0:
            continue
        t = np.clip((points - a) @ edge / norm, 0, 1)
        boundary |= np.linalg.norm(points - a - t[:, None] * edge, axis=1) <= 0.001
        if edge[1] != 0:
            crossing = ((a[1] > points[:, 1]) != (b[1] > points[:, 1])) & (
                points[:, 0] < a[0] + (points[:, 1] - a[1]) * edge[0] / edge[1]
            )
            hit ^= crossing
    return hit, boundary


def coverage(points, outer, inner):
    hit, boundary = np.zeros(len(points), bool), np.zeros(len(points), bool)
    for ring in outer:
        h, b = inside(points, ring)
        hit |= h
        boundary |= b
    for ring in inner:
        h, b = inside(points, ring)
        hit &= ~h
        boundary |= b
    return hit & ~boundary, boundary


def run(protocol, capture, output):
    if output.exists():
        raise ValueError("Retain every coverage result; use a fresh output")
    receipt = load(capture / "capture-receipt.json")
    if (
        receipt["status"] != "captured"
        or receipt["remark"]
        or sha(capture / "response.json") != receipt["response_sha256"]
        or sha(protocol / "freeze.json") != receipt["prospective_protocol_sha256"]
    ):
        raise ValueError("Expected complete hash-bound prospective public capture")
    frozen = load(protocol / "freeze.json")
    for name, expected in frozen["files_sha256"].items():
        if sha(protocol / name) != expected:
            raise ValueError(f"Frozen source changed: {name}")
    old = protocol / "input"
    plan = load(old / "port-plan.json")
    geometry = load(old / "input/source/geometry.json")
    elements = [
        e
        for e in load(capture / "response.json")["elements"]
        if e.get("tags", {}).get("natural") == "water"
        or e.get("tags", {}).get("waterway") == "riverbank"
    ]
    polygons, evidence = [], []
    for element in elements:
        item = {
            "type": element["type"],
            "id": element["id"],
            "version": element.get("version"),
            "timestamp": element.get("timestamp"),
            "tags": element["tags"],
        }
        try:
            outer, inner = polygon(element)
            projected = [
                [
                    np.array([position(geometry["sq"], p) for p in ring])
                    for ring in group
                ]
                for group in (outer, inner)
            ]
            polygons.append((item, projected))
            item.update(
                status="literal_rings_assembled",
                outer_rings=len(outer),
                inner_rings=len(inner),
            )
        except (ValueError, KeyError, TypeError) as error:
            item.update(status="unresolved_polygon", error=str(error))
        evidence.append(item)
    results = []
    for component in plan["components"]:
        if component["id"] not in TARGETS:
            continue
        nodes = set(map(tuple, component["nodes_rc"]))
        rim = {(r + y, c + x) for r, c in nodes for y, x in STEPS8} - nodes
        samples = sorted(nodes | rim)
        points = np.array([(c * 16 - 8640, 8640 - r * 16) for r, c in samples])
        contacts = []
        for item, (outer, inner) in polygons:
            wet, boundary = coverage(points, outer, inner)
            contacts.append(
                {
                    "type": item["type"],
                    "id": item["id"],
                    "covered_nodes_rc": [
                        list(n) for n, yes in zip(samples, wet) if yes
                    ],
                    "boundary_unknown_nodes_rc": [
                        list(n) for n, yes in zip(samples, boundary) if yes
                    ],
                }
            )
        results.append(
            {
                "id": component["id"],
                "source_provenance": component["source_provenance"],
                "original_reasons": component["reasons"],
                "channel_sample_nodes": len(nodes),
                "untouched_rim_sample_nodes": len(rim),
                "polygon_contacts": contacts,
                "source_piece_identity": "unresolved; this is contemporary coverage only",
                "new_admission": False,
            }
        )
    output.mkdir(parents=True)
    result = {
        "schema": "polli.public-bank-polygon-coverage/1",
        "scope": "contemporary literal polygon coverage at original native nodes, not hydraulic/source identity, bank floor or absence of natural water",
        "polygons": evidence,
        "components": results,
        "polygon_statuses": dict(Counter(p["status"] for p in evidence)),
        "new_admissions": 0,
        "stable_water_promise": "unknown",
    }
    write(output / "coverage.json", result)
    write(
        output / "freeze.json",
        {
            "schema": "polli.public-bank-polygon-coverage-freeze/1",
            "source_files_sha256": {
                name: sha(ROOT / name) for name in (SOURCE, DESIGN)
            },
            "source_protocol_sha256": sha(protocol / "freeze.json"),
            "public_capture_receipt_sha256": sha(capture / "capture-receipt.json"),
            "public_response_sha256": receipt["response_sha256"],
            "result_sha256": sha(output / "coverage.json"),
            "physical_package": None,
            "holdout_inputs_accessed": False,
        },
    )
    return {
        "polygon_statuses": result["polygon_statuses"],
        "new_admissions": 0,
        "freeze_sha256": sha(output / "freeze.json"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "capture", "output"):
        parser.add_argument(name, type=Path)
    import json

    print(json.dumps(run(**vars(parser.parse_args())), indent=2))
