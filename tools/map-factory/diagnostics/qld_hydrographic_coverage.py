"""Literal external-waterbody coverage of complete retained coastal geometry.

Coverage is a raster association diagnostic, NOT hydraulic or width authority.
No name/nearest-way join, source replacement, mask change or admission occurs.
"""

import argparse
from collections import Counter
import hashlib
from pathlib import Path
import shutil


from bank_authority import ROOT, load, sha, write
from qld_hydrographic_capture import complete_ids, preflight as source_preflight
from open_interface_authority import preflight as interface_preflight
from region import raster
from waterway_pieces import digest

POLICY = "complete-coastal-qld-area-coverage-v1"
FILES = (
    "diagnostics/qld_hydrographic_coverage.py",
    "diagnostics/test_qld_hydrographic_coverage.py",
    "calibration/pl1191-construction-v1/development/phase27-qld-coverage-policy.md",
)


def coverage(nodes, masks):
    """Keep each external body and every original walk occurrence, even zero."""
    result = {}
    for name, mask in sorted(masks.items()):
        result[name] = [i for i, (r, c) in enumerate(nodes) if mask[r, c]]
    hit = {i for values in result.values() for i in values}
    return {
        "walk_occurrences": len(nodes),
        "unique_nodes": len(set(map(tuple, nodes))),
        "covered_occurrences": len(hit),
        "per_external_body_occurrence_indices": result,
        "source_piece_identity_or_hydraulic_bank_authority": None,
    }


def verify_derived_layer(data, raw_ids, raw_batches):
    complete_ids(raw_ids, data["features"], data["objectIdField"])
    if data["objectIds"] != sorted(raw_ids) or data["features"] != [
        f for batch in raw_batches for f in batch
    ]:
        raise ValueError(
            "Derived source attributes/geometry differ from exact raw capture"
        )


def stage(interface, source, captured, output):
    interface_preflight(interface)
    source_preflight(source)
    if output.exists():
        raise ValueError("Fresh external-source coverage protocol required")
    receipt = load(captured / "receipt.json")
    if receipt["prospective_freeze_sha256"] != sha(source / "freeze.json"):
        raise ValueError("Wrong external-source capture")
    if {r["layer"] for r in receipt["complete_layers"]} != {62, 63}:
        raise ValueError("Partial source data, not zero water")
    for r in receipt["requests"]:
        if r["status"] != 200 or sha(captured / r["filename"]) != r["sha256"]:
            raise ValueError("Incomplete/changed public source response")
    for layer in (62, 63):
        data = load(captured / f"layer-{layer}-complete.json")
        ids = load(captured / f"layer-{layer}-ids.json")["objectIds"]
        batches = [
            load(captured / r["filename"])["features"]
            for r in receipt["requests"]
            if r["filename"].startswith(f"layer-{layer}-batch-")
        ]
        verify_derived_layer(data, ids, batches)
    output.mkdir(parents=True)
    shutil.copyfile(source / "source-geometry.json", output / "original-geometry.json")
    shutil.copytree(captured, output / "external-source")
    old = interface / "prior-results/low-coast-oceania.json"
    if load(old)["source_geometry_sha256"] != digest(
        load(source / "source-geometry.json")
    ):
        raise ValueError("External query frame differs from retained source graph")
    shutil.copyfile(old, output / "original-complete-graph.json")
    shutil.copyfile(
        interface / "review-thread.json", output / "PL1295-review-thread.json"
    )
    write(
        output / "all-six-case-bindings.json",
        {
            "cases": load(interface / "freeze.json")["cases"],
            "complete_case_inputs_freeze_sha256": sha(interface / "freeze.json"),
            "source_provider_scope": "Australian supplemental source; other five original cases retained, no substitution or inferred data",
        },
    )
    deps = dict(load(source / "freeze.json")["source_files_sha256"])
    for n in FILES:
        deps[n] = sha(ROOT / n)
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "source_files_sha256": deps,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "external_capture_counts_known": True,
            "coverage_outputs_not_yet_computed": True,
            "capture_counts_and_classifications_known": True,
            "new_physical_or_native": False,
        },
    )


def preflight(folder):
    f = load(folder / "freeze.json")
    if f["policy"] != POLICY:
        raise ValueError("Wrong coverage policy")
    for base, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for n, value in f[key].items():
            if sha(base / n) != value:
                raise ValueError(f"Frozen source/method changed: {n}")


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh source-coverage output required")
    output.mkdir(parents=True)
    geometry = load(folder / "original-geometry.json")
    old = load(folder / "original-complete-graph.json")
    bodies = load(folder / "external-source/layer-63-complete.json")["features"]
    streams = load(folder / "external-source/layer-62-complete.json")["features"]
    masks = {}
    body_records = []
    for feature in bodies:
        attributes = feature["attributes"]
        name = f"OBJECTID:{attributes['objectid']}"
        try:
            rings = feature["geometry"]["rings"]
            mask = raster(geometry["sq"], [{"rings": rings}], polygons=True)
            masks[name] = mask
            body_records.append(
                {
                    "id": name,
                    "attributes": attributes,
                    "raster_nodes": int(mask.sum()),
                    "raster_u8_sha256": hashlib.sha256(
                        mask.astype("u1").tobytes()
                    ).hexdigest(),
                }
            )
        except (KeyError, TypeError, ValueError, IndexError) as error:
            body_records.append(
                {
                    "id": name,
                    "attributes": attributes,
                    "status": "unresolved_geometry",
                    "reason": str(error),
                }
            )
    groups = {}
    for record in body_records:
        attrs = record["attributes"]
        group = "|".join(
            str(attrs.get(k)) for k in ("feature_type", "function", "perenniality")
        )
        groups.setdefault(group, []).append(record["id"])
    pieces = [
        {
            "clip": name,
            "source_scope": clip["source_scope"],
            **coverage(clip["nodes_rc"], masks),
        }
        for name, clip in sorted(old["complete_source_topology"]["clips"].items())
    ]
    ports = []
    for component in old["components"]:
        recipe = component["conditional_variable_stage_plan"]
        if recipe["status"] != "unresolved_open_port_lateral_or_exterior_bank":
            continue
        own = {
            tuple(old["complete_source_topology"]["nodes"][i]["node_rc"])
            for i in component["graph_node_ids"]
        }
        bank = {
            (r + y, c + x) for r, c in own for y in (-1, 0, 1) for x in (-1, 0, 1)
        } - own
        inside = sorted(n for n in bank if 0 <= n[0] <= 1080 and 0 <= n[1] <= 1080)
        ports.append(
            {
                "component": component["id"],
                "source_clips": component["source_clips"],
                "full_in_square_bank_union": coverage(inside, masks),
                "raw_classified_bank_membership": {
                    key: coverage(inside, {n: masks[n] for n in names if n in masks})
                    for key, names in sorted(groups.items())
                },
                "external_floor_stage_or_capacity": None,
                "physical_admission": False,
            }
        )
    result = {
        "policy": POLICY,
        "prospective_freeze_sha256": sha(folder / "freeze.json"),
        "all_external_waterbodies": body_records,
        "all_original_clipped_line_parts": pieces,
        "all_19_coastal_open_port_components": ports,
        "network_records": len(streams),
        "network_raw_classification_counts": {
            key: dict(Counter(str(f["attributes"].get(key)) for f in streams))
            for key in ("feature_type", "function", "perenniality")
        },
        "polygon_raw_classification_counts": {
            key: dict(Counter(str(f["attributes"].get(key)) for f in bodies))
            for key in ("feature_type", "function", "perenniality")
        },
        "metadata_accepted_as_old_source_authority": False,
        "original_source_mask_or_geometry_changed": False,
        "qualification": "unknown; polygon coverage is not a surveyed bank/correspondence/capacity certificate",
    }
    write(output / "coverage.json", result)
    write(
        output / "receipt.json",
        {
            "prospective_freeze_sha256": sha(folder / "freeze.json"),
            "coverage_sha256": sha(output / "coverage.json"),
            "new_physical_or_native": False,
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest="command", required=True)
    for n, args in (
        ("stage", ["interface", "source", "captured", "output"]),
        ("preflight", ["folder"]),
        ("evaluate", ["folder", "output"]),
    ):
        q = s.add_parser(n)
        for a in args:
            q.add_argument(a, type=Path)
    args = vars(p.parse_args())
    globals()[args.pop("command")](**args)
