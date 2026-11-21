"""Read-only lateral-authority diagnostic; never changes banks or admits water."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

from stream_ports import ROOT, graph_profile, load, preflight as parent_preflight
from synthetic_source_response import channel
from waterway_pieces import catalog
from closed_storage_candidate import sha
from natural_storage_candidate import write

POLICY = "untouched-bank-authority-diagnostic-v1"
TARGETS = [f"stream-component:{i}" for i in (161, 162, 169, 187)]
STEPS4 = [(-1, 0), (0, -1), (0, 1), (1, 0)]
STEPS8 = [(r, c) for r in (-1, 0, 1) for c in (-1, 0, 1) if (r, c) != (0, 0)]
SOURCE = "diagnostics/bank_authority.py"
DESIGN = (
    "calibration/pl1191-construction-v1/development/phase13-bank-authority-policy.md"
)


def review_basis(receipt):
    if (
        receipt.get("schema") != "polli.pl1191-stream-port-recipe-review/1"
        or receipt.get("review_issue", {}).get("id")
        != "01a1ffce-a05d-724a-976c-0365a699c6b4"
        or receipt.get("claim_recommendation", {}).get("verdict") != "pass"
        or receipt.get("bound_source", {}).get("global_freeze", {}).get("sha256")
        != "41d271ce72d0812d8408d6b2bbc4f5531329f500ce4320f3bd4365a8dc00dee7"
    ):
        raise ValueError("Expected exact PL-1230 review receipt and reviewed freeze")


def corner_audit(nodes):
    """Single, non-iterated reviewer rule. Adjacency does not establish a bank."""
    own = set(map(tuple, nodes))
    adjacent = Counter((r + y, c + x) for r, c in own for y, x in STEPS4)
    added = sorted(n for n, count in adjacent.items() if count >= 2 and n not in own)
    old_rim = {(r + y, c + x) for r, c in own for y, x in STEPS8} - own
    if not set(added) <= old_rim:
        raise ValueError("Corner additions must be existing untouched rim nodes")
    return {
        "original_channel_nodes": len(own),
        "original_full_rim_nodes": len(old_rim),
        "proposed_added_nodes_rc": [list(n) for n in added],
        "retired_untouched_rim_nodes": len(added),
        "proposal_status": "prohibited_footprint_expansion" if added else "no_change",
        "bank_authority": "unknown; four-adjacency is not lateral source evidence",
        "new_channel_or_rim": None,
    }


def deficits(recipe):
    witnesses = recipe.get("witnesses")
    if witnesses is None:
        return {"count": 0, "max_m": 0.0} if recipe["status"] == "feasible" else None
    qs = [
        w["lower_potential_q"] - w["greatest_possible_potential_q"] for w in witnesses
    ]
    if not qs or min(qs) <= 0:
        raise ValueError("Expected positive unchanged refusal deficits")
    return {
        "count": len(qs),
        "min_m": min(qs) / 64,
        "median_m": float(np.median(qs)) / 64,
        "max_m": max(qs) / 64,
        "at_most_0_5m": sum(q <= 32 for q in qs),
    }


def synthetic_check():
    geometry, _, terrain, water, old = channel(
        load(ROOT / "templates/native-corridors.json")
    )
    clips = [
        c
        for r in catalog(geometry)["rows"]
        if r["field"] == "streams"
        for c in r["clips"]
    ]
    nodes = sorted({tuple(n) for c in clips for n in c["nodes_rc"]})
    indices = {n: i for i, n in enumerate(nodes)}
    edges = [
        (indices[tuple(a)], indices[tuple(b)])
        for c in clips
        for a, b in zip(c["nodes_rc"], c["nodes_rc"][1:])
    ]
    recipe = graph_profile(
        nodes, edges, np.full_like(terrain, 6400), np.zeros_like(water)
    )
    if recipe["status"] != "feasible":
        raise ValueError("Frozen synthetic recipe must remain feasible")
    materialized_floor, materialized_water = (
        np.full_like(terrain, 6400),
        np.zeros_like(water),
    )
    for node, bed, stage in zip(nodes, recipe["bed_q"], recipe["target_q"]):
        materialized_floor[node] = bed
        materialized_water[node] = stage - bed
    hashes = {}
    for name, actual, expected in (
        ("terrain.u16", materialized_floor, terrain),
        ("water.u16", materialized_water, water),
    ):
        actual_bytes = np.flipud(actual).astype("<u2").tobytes()
        expected_bytes = np.flipud(expected).astype("<u2").tobytes()
        if actual_bytes != expected_bytes:
            raise ValueError(
                "Materialized original recipe differs from frozen synthetic grid"
            )
        hashes[name] = hashlib.sha256(actual_bytes).hexdigest()
    if hashes != {
        "terrain.u16": "fa9d04b8d94e7504bb21c0fcd9b6842fb0a57056d4f1b9cd43e3b6e2e8763b7e",
        "water.u16": "96c1edce3a4bd19c22e1106f1a1e4770ddd319bc5195e5b122c0558eb8716e3c",
    }:
        raise ValueError(
            "Original recipe does not reproduce the frozen physical grid hashes"
        )
    if set(map(tuple, recipe["full_rim_rc"])) != set(map(tuple, old["rim_rc"])):
        raise ValueError("Original full rim changed")
    if (
        [c["position"][::2] for c in recipe["controls"]] != old["port_xz"]
        or [c["target_fixed"] for c in recipe["controls"]] != [6368, 6368, 6336]
        or [c["output_rate"] for c in recipe["controls"]] != [32, 32, 0]
        or any(c["intake_rate"] != 128 for c in recipe["controls"])
    ):
        raise ValueError("Original synthetic ports changed")
    return {
        "scope": "original recipe CPU byte replay, not a new native outcome or expanded-footprint qualification",
        "original_grid_bytes_exact": True,
        "grid_sha256": hashes,
        "original_ports": recipe["controls"],
        "reviewer_corner_rule": corner_audit(nodes),
    }


def analyze(folder):
    parent = folder / "input"
    plan = load(parent / "port-plan.json")
    geometry = load(parent / "input/source/geometry.json")
    result = {
        "policy": POLICY,
        "source_catalog_sha256": plan["source_catalog_sha256"],
        "eligible_clip_ids": plan["eligible_clip_ids"],
        "original_line_rows": plan["original_line_rows"],
        "original_polygon_rows": plan["original_polygon_rows"],
        "original_status": plan["status"],
        "original_complete_geographic_candidate": plan["complete_geographic_candidate"],
        "new_physical_package": None,
        "native_observation": False,
        "new_admissions": 0,
        "stable_water_promise": "unknown",
        "new_source_geometry": None,
        "original_probes_sha256": plan.get("full_original_probes_sha256"),
        "original_controls": plan.get("existing_controls_unchanged"),
    }
    if plan["status"] == "retained_base_refusal":
        result.update(
            components=None,
            lateral_authority=None,
            original_refusal=plan["original_refusal"],
        )
        return result, {"type": "FeatureCollection", "features": []}, None
    rows = {f"streams:{i}": row for i, row in enumerate(geometry["streams"])}
    features, components, target_points = [], [], []
    for component in plan["components"]:
        source = [
            {
                "row": name.rsplit(":clip:", 1)[0],
                "clip": name,
                "keys": sorted(rows[name.rsplit(":clip:", 1)[0]]),
            }
            for name in component["source_clips"]
        ]
        entry = {
            "id": component["id"],
            "source_provenance": component["source_provenance"],
            "source_clips": component["source_clips"],
            "source_fields": source,
            "original_recipe_status": component["recipe"]["status"],
            "unchanged_reasons": component["reasons"],
            "unchanged_guards": component["original_guards_unchanged"],
            "unchanged_deficits": deficits(component["recipe"]),
            "corner_diagnostic": corner_audit(component["nodes_rc"]),
            "physical_disposition": component["status"],
            "new_admission": False,
        }
        if (
            geometry["sq"]["slug"] == "lowland-river-south-america"
            and component["id"] in TARGETS
        ):
            if component["reasons"] != ["infeasible_bounds"]:
                raise ValueError(
                    "Review target no longer has its exact pure-bound refusal"
                )
            for name in component["source_clips"]:
                row = rows[name.rsplit(":clip:", 1)[0]]
                points = row["pts"]
                target_points.extend(points)
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": points},
                        "properties": {
                            "component": component["id"],
                            "clip": name,
                            "scope": "complete original source row, not measured bank/width; no new geometry",
                            "source_sha256": next(
                                p["source_sha256"]
                                for p in component["source_provenance"]
                                if p["clip"] == name
                            ),
                            "source_fields": sorted(row),
                            "corner_nodes_rc": entry["corner_diagnostic"][
                                "proposed_added_nodes_rc"
                            ],
                            "max_deficit_m": entry["unchanged_deficits"]["max_m"],
                        },
                    }
                )
        components.append(entry)
    query = None
    if target_points:
        # Read-only 4-target rectangle, 0.0015 degree margin declared in policy.
        coordinates = np.array(target_points)
        west, south = coordinates.min(axis=0) - 0.0015
        east, north = coordinates.max(axis=0) + 0.0015
        bbox = ",".join(f"{v:.8f}" for v in (south, west, north, east))
        query = f'[out:json][timeout:25];(nwr["waterway"]({bbox});nwr["natural"="water"]({bbox}););out meta geom;\n'
    result["components"] = components
    result["lateral_authority"] = (
        "source rows are centrelines; adjacency is not a captured width or bank"
    )
    return result, {"type": "FeatureCollection", "features": features}, query


def stage(source, output, review):
    if output.exists():
        raise ValueError("Use a fresh read-only bank-authority protocol")
    receipt = load(review)
    review_basis(receipt)
    parent_preflight(source)
    output.mkdir(parents=True)
    shutil.copytree(source, output / "input")
    shutil.copyfile(review, output / "review.json")
    report, features, query = analyze(output)
    write(output / "bank-audit.json", report)
    write(output / "source-authority-targets.geojson", features)
    if query:
        (output / "public-width-query.overpassql").write_text(query)
    previous = load(source / "freeze.json")
    dependencies = {
        **previous["source_files_sha256"],
        SOURCE: sha(ROOT / SOURCE),
        DESIGN: sha(ROOT / DESIGN),
    }
    write(
        output / "freeze.json",
        {
            "schema": "polli.bank-authority-protocol/1",
            "policy": POLICY,
            "source_files_sha256": dependencies,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "previous_protocol_sha256": sha(source / "freeze.json"),
            "definition_sha256": previous["definition_sha256"],
            "review_sha256": sha(review),
            "physical_package": None,
            "holdout_inputs_accessed": False,
        },
    )
    preflight(output)
    return {
        "freeze_sha256": sha(output / "freeze.json"),
        "components": len(report["components"] or []),
        "new_admissions": 0,
    }


def preflight(folder):
    frozen = load(folder / "freeze.json")
    if (
        frozen["schema"] != "polli.bank-authority-protocol/1"
        or frozen["policy"] != POLICY
        or frozen["physical_package"] is not None
    ):
        raise ValueError("Wrong read-only authority protocol")
    for name, value in frozen["source_files_sha256"].items():
        if sha(ROOT / name) != value:
            raise ValueError(f"Bound source changed: {name}")
    for name, value in frozen["files_sha256"].items():
        if sha(folder / name) != value:
            raise ValueError(f"Bound evidence changed: {name}")
    if (
        sha(folder / "input/freeze.json") != frozen["previous_protocol_sha256"]
        or sha(folder / "review.json") != frozen["review_sha256"]
    ):
        raise ValueError("Previous protocol/review changed")
    review_basis(load(folder / "review.json"))
    parent_preflight(folder / "input")
    report, features, query = analyze(folder)
    if report != load(folder / "bank-audit.json") or features != load(
        folder / "source-authority-targets.geojson"
    ):
        raise ValueError("Source-authority replay differs")
    if query and query != (folder / "public-width-query.overpassql").read_text():
        raise ValueError("Public query changed")


def fetch(folder, output):
    """Single public read. Capture failures retained; no source ownership inferred."""
    preflight(folder)
    if output.exists():
        raise ValueError("Retain every public capture; use a fresh output")
    query = folder / "public-width-query.overpassql"
    data = urllib.parse.urlencode({"data": query.read_text()}).encode()
    output.mkdir(parents=True)
    request = urllib.request.Request(
        "https://overpass-api.de/api/interpreter",
        data=data,
        headers={"User-Agent": "Polli-PL1191-development-bank-evidence/1"},
    )
    receipt = {
        "policy": POLICY,
        "prospective_protocol_sha256": sha(folder / "freeze.json"),
        "query_sha256": sha(query),
        "url": request.full_url,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "automatic_source_association": False,
        "new_admissions": 0,
    }
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read()
            receipt["http_status"] = response.status
            receipt["response_headers"] = dict(response.headers)
        (output / "response.json").write_bytes(raw)
        result = json.loads(raw)
        elements = result["elements"]
        receipt.update(
            status="captured_with_remark" if result.get("remark") else "captured",
            response_sha256=sha(output / "response.json"),
            remark=result.get("remark"),
            osm_metadata=result.get("osm3s"),
            element_count=len(elements),
            explicit_width_elements=[
                {"type": e["type"], "id": e["id"], "tags": e["tags"]}
                for e in elements
                if any(
                    k in e.get("tags", {})
                    for k in ("width", "est_width", "width:source")
                )
            ],
            polygon_candidate_ids=[
                {"type": e["type"], "id": e["id"]}
                for e in elements
                if e.get("tags", {}).get("natural") == "water"
                or e.get("tags", {}).get("waterway") == "riverbank"
            ],
        )
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as error:
        receipt.update(status="capture_failed", error=str(error))
        if isinstance(error, urllib.error.HTTPError):
            (output / "error-response.txt").write_bytes(error.read())
    receipt["ended_at"] = datetime.now(timezone.utc).isoformat()
    write(output / "capture-receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, arguments in (
        ("stage", ("source", "output", "review")),
        ("preflight", ("folder",)),
        ("fetch", ("folder", "output")),
    ):
        command = commands.add_parser(name)
        for argument in arguments:
            command.add_argument(argument, type=Path)
    commands.add_parser("synthetic")
    args = vars(parser.parse_args())
    command = args.pop("command")
    result = synthetic_check() if command == "synthetic" else globals()[command](**args)
    print(json.dumps(result or {"status": "replay_pass"}, indent=2))
