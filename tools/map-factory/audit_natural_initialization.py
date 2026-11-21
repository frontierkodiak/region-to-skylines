"""Read-only explanation of authored natural-water initialization failures."""

import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

from closed_storage_candidate import ROOT, sha
from region import raster


def audit(prepared, inventory_folder):
    geometry = json.loads((prepared / "geometry.json").read_text())
    hydro = json.loads((prepared / "hydrology.json").read_text())
    inventory = json.loads((inventory_folder / "inventory.json").read_text())
    initial = json.loads(
        (inventory_folder / "authored-initialization.json").read_text()
    )
    floor = (
        np.flipud(np.fromfile(prepared / "terrain.u16", "<u2").reshape(1081, 1081)) / 64
    )
    water = (
        np.flipud(np.fromfile(prepared / "water.u16", "<u2").reshape(1081, 1081)) / 64
    )
    old_labels, _ = ndimage.label(
        raster(geometry["sq"], geometry.get("lakes", []), polygons=True)
    )
    lakes = []
    for number, region in enumerate(ndimage.find_objects(old_labels), 1):
        local = old_labels[region] == number
        cells = int(local.sum())
        lakes.append(
            {
                "component": number,
                "cells": cells,
                "skipped_by_existing_eight_node_minimum": cells < 8,
                "initial_wet_cells": int(np.sum(water[region][local] > 0.1)),
                "floor_range_m": [
                    float(floor[region][local].min()),
                    float(floor[region][local].max()),
                ],
            }
        )
    failed = {c["id"] for c in initial["contracts"] if c["status"] == "fail"}
    failed_entries = []
    for entry in inventory["entries"]:
        contracts = [c["id"] for c in entry.get("contracts", []) if c["id"] in failed]
        if contracts:
            failed_entries.append(
                {
                    "id": entry["id"],
                    "field": entry.get("field"),
                    "name": entry.get("name"),
                    "support_status": entry["status"],
                    "reason": entry.get("reason"),
                    "contracts": contracts,
                }
            )
    unforced = [r for r in hydro["rivers"] if r.get("unforced_infeasible_stream")]
    return {
        "schema": "polli.natural-initialization-diagnosis/1",
        "source_files_sha256": {
            name: sha(ROOT / name)
            for name in [
                "audit_natural_initialization.py",
                "region.py",
                "maintained_water_inventory.py",
            ]
        },
        "input_files_sha256": {
            "prepared/" + name: sha(prepared / name)
            for name in ["geometry.json", "hydrology.json", "terrain.u16", "water.u16"]
        }
        | {
            "inventory/" + name: sha(inventory_folder / name)
            for name in ["inventory.json", "authored-initialization.json"]
        },
        "failed_contracts": len(failed),
        "failed_entries": failed_entries,
        "failures_by_field": dict(Counter(e["field"] for e in failed_entries)),
        "unforced_stream_profiles": unforced,
        "authored_short_reach_omissions": hydro["unmodeled_short_surface_reaches"],
        "existing_four_neighbour_lake_components": lakes,
        "mechanisms": [
            "Existing stream code rejects a global monotone profile above its bank ceiling, then explicitly disables excavation, initialization and control forcing for that profile.",
            "Existing lake code skips components below eight nodes. For retained components it caps stage below the lowest bank but does not excavate the lake interior; a floor above the capped stage starts dry.",
            "These are source-code/authored-grid mechanisms, not causal attribution of every native loss or geographic impossibility.",
        ],
        "new_native_observation": False,
        "stable_water_promise": "unknown",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("inventory_folder", type=Path)
    print(json.dumps(audit(**vars(parser.parse_args())), indent=2))
