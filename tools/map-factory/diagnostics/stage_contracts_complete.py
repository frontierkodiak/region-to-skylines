"""Add literal ocean-row support to the frozen v2 complete-contract CPU results.

The inherited envelope helper included oceans in its union, but not as individual
source masks. V2's optimistic contracts covered oceans; its own-source ocean
restriction/footprint support was incomplete. Preserve v2 and bind this correction
before new outputs. No thresholds, escape grids, contracts or physical bytes change.
"""

import argparse
from pathlib import Path
import shutil

import numpy as np

from bank_authority import ROOT, load, sha, write
from coastal_floor_audit import grid
from maintained_water_inventory import source_tag
from region import raster
from stage_contracts import contract_model
from stage_contracts_v2 import json_scalars, preflight as prior_preflight
from waterway_pieces import digest

POLICY = "complete-contract-conditional-escape-stage-v3-ocean-rows"
FILES = (
    "diagnostics/stage_contracts_complete.py",
    "diagnostics/test_stage_contracts_complete.py",
)


def ocean_masks(geometry):
    result = []
    for i, feature in enumerate(geometry.get("oceans", [])):
        if (
            source_tag(feature, "intermittent") in (True, 1, "1", "yes", "true")
            or source_tag(feature, "brunnel") == "tunnel"
        ):
            continue
        result.append(
            (
                f"oceans:{i}",
                np.flipud(raster(geometry["sq"], [feature], polygons=True)),
                digest(feature),
            )
        )
    return result


def stage(parent, results, output):
    prior_preflight(parent)
    receipt = load(results / "receipt.json")
    if receipt["input_freeze_sha256"] != sha(parent / "freeze.json"):
        raise ValueError("Prior results belong to another protocol")
    for name, value in receipt["result_files_sha256"].items():
        if sha(results / name) != value:
            raise ValueError(f"Prior CPU bytes changed: {name}")
    if output.exists():
        raise ValueError("Fresh v3 protocol required")
    output.mkdir(parents=True)
    shutil.copytree(parent, output / "prior-protocol")
    shutil.copytree(results, output / "prior-results")
    dependencies = dict(load(parent / "freeze.json")["source_files_sha256"])
    for name in FILES:
        dependencies[name] = sha(ROOT / name)
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": load(parent / "freeze.json")["cases"],
            "source_files_sha256": dependencies,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "prior_v2_outcomes_known": True,
            "new_physical_or_native": False,
            "correction_scope": "literal source-selected ocean row masks/1m footprint support only; all other results retained exact",
        },
    )


def preflight(folder):
    frozen = load(folder / "freeze.json")
    if frozen["policy"] != POLICY:
        raise ValueError("Wrong complete source-row policy")
    for root, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for name, value in frozen[key].items():
            if sha(root / name) != value:
                raise ValueError(f"Frozen bytes changed: {name}")
    prior_preflight(folder / "prior-protocol")


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh complete CPU output required")
    output.mkdir(parents=True)
    prior = folder / "prior-results"
    for path in sorted(prior.glob("*.i32")):
        shutil.copyfile(path, output / path.name)
    for slug in load(folder / "freeze.json")["cases"]:
        result = load(prior / f"{slug}.json")
        root = folder / "prior-protocol/input-v1"
        case = root / "parent/parent-protocol" / slug
        kind = load(case / "case.json")["kind"]
        source = case / "input"
        if result.get("models"):
            geometry = load(
                source
                / (
                    "physical/geometry.json"
                    if kind == "coastal"
                    else "source/geometry.json"
                )
            )
            inventory = load(root / "inventories" / f"{slug}.json")
            floor = grid(
                case / "current-floor.u16"
                if kind == "coastal"
                else source / "physical/terrain.u16"
            )
            initial = grid(source / "physical/water.u16")
            for model in result["models"]:
                ceiling = (
                    np.fromfile(
                        output / f"{slug}-adj{model['adjacency']}-escape.i32", "<i4"
                    ).reshape(floor.shape)
                    - 32
                )
                ocean_ids = set()
                for name, mask, source_hash in ocean_masks(geometry):
                    ocean_ids.add(name)
                    entry = next(e for e in inventory["entries"] if e["id"] == name)
                    for contract in entry.get("contracts", []):
                        row = contract_model(contract, floor, initial, ceiling, mask)
                        row.update(
                            source_entry=name, retained_support_status=entry["status"]
                        )
                        index = next(
                            i
                            for i, c in enumerate(model["contracts"])
                            if c["id"] == contract["id"]
                        )
                        # Optimistic nearby support is byte-for-value unchanged.
                        assert (
                            row["optimistic_any_nearby_raster"][
                                "common_stage_intervals_q"
                            ]
                            == model["contracts"][index][
                                "optimistic_any_nearby_raster"
                            ]["common_stage_intervals_q"]
                        )
                        model["contracts"][index] = row
                    nodes = np.flatnonzero(mask)
                    feasible = (
                        floor.ravel()[nodes].astype(np.int64) + 64
                        <= ceiling.ravel()[nodes]
                    )
                    model["source_footprints"].append(
                        {
                            "id": name,
                            "source_sha256": source_hash,
                            "source_nodes": int(nodes.size),
                            "conditional_1m_footprint_nodes": int(feasible.sum()),
                            "minimum_stage_for_any_1m_source_q": int(
                                floor.ravel()[nodes].min()
                            )
                            + 64
                            if nodes.size
                            else None,
                            "minimum_escape_ceiling_q": int(
                                ceiling.ravel()[nodes].min()
                            )
                            if nodes.size
                            else None,
                            "maximum_escape_ceiling_q": int(
                                ceiling.ravel()[nodes].max()
                            )
                            if nodes.size
                            else None,
                            "inlet_outlet_supply": None,
                        }
                    )
                model["literal_ocean_rows_added"] = sorted(ocean_ids)
                model["fit_counts"] = {
                    key: sum(c[key]["numeric_fit_only"] for c in model["contracts"])
                    for key in (
                        "optimistic_any_nearby_raster",
                        "restricted_own_source_raster",
                    )
                }
        write(output / f"{slug}.json", json_scalars(result))
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
        ("stage", ["parent", "results", "output"]),
        ("preflight", ["folder"]),
        ("evaluate", ["folder", "output"]),
    ):
        command = sub.add_parser(name)
        for argument in arguments:
            command.add_argument(argument, type=Path)
    args = vars(parser.parse_args())
    globals()[args.pop("command")](**args)
