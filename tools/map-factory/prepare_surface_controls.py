"""Freeze plumbing/load references on the two registered stock packages.

These are fixture controls, NOT surface-capability model predictions. The
stock water quality and upstream relationship remain unpredicted. Selection
uses decoded geometry only, before a new native run; packages are not edited.
"""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

from prepare_start_controls import prepare as prepare_panels
from start_capabilities import assess, digest
from surface_intake import LOAD, bank_candidate
from survey.craft_anatomy import read_package
from survey.measure_maps import (
    data_version,
    parse_start_tile,
    parse_terrain,
    parse_water,
)


def control_banks(ground, depth, tile):
    """Nearest wet shoreline, then a separated point on the same wet component."""
    wet = depth >= 1
    labels, _ = ndimage.label(wet)
    distance = ndimage.distance_transform_edt(wet) * 16
    row, col = np.indices(wet.shape)
    x, z = col * 16 - 8640, row * 16 - 8640
    cx, cz = (tile % 5 - 2) * 1920, (tile // 5 - 2) * 1920
    mask = wet & (distance <= 64) & (abs(x - cx) < 800) & (abs(z - cz) < 800)
    coords = np.argwhere(mask)
    sizes = np.bincount(labels[mask].ravel())
    ordered = sorted(
        coords.tolist(),
        key=lambda p: (
            -int(sizes[labels[p[0], p[1]]]),
            (p[1] * 16 - 8640 - cx) ** 2 + (p[0] * 16 - 8640 - cz) ** 2,
            p,
        ),
    )
    selected = []
    for r, c in ordered:
        if selected:
            first_r, first_c, _ = selected[0]
            if (
                labels[r, c] != labels[first_r, first_c]
                or np.hypot(r - first_r, c - first_c) * 16 < 640
            ):
                continue
        anchor = [c * 16 - 8640, 0, r * 16 - 8640]
        bank = bank_candidate(
            ground, depth, anchor, float(ground[r, c] + depth[r, c]), tile
        )
        if bank is not None:
            selected.append((r, c, bank))
            if len(selected) == 2:
                break
    return selected


def prepare(cohort, stock, output):
    output.mkdir(parents=True, exist_ok=False)
    panel_rows = prepare_panels(cohort, stock, output / "panels")
    rows = []
    for control, panel in zip(cohort["controls"], panel_rows):
        package = stock / control["filename"]
        raw = package.read_bytes()
        if hashlib.sha256(raw).hexdigest() != control["sha256"]:
            raise ValueError("Stock source changed: " + control["filename"])
        _, assets = read_package(raw)
        data = next(a["payload"] for a in assets if a["kind"] == 52)
        ground, depth = parse_terrain(data), parse_water(data)
        _, tile = parse_start_tile(data, data_version(data))
        folder = output / "prepared" / panel["slug"]
        folder.mkdir(parents=True)
        for name, a in [("terrain.u16", ground), ("water.u16", depth)]:
            np.floor(a * 64 + 0.5).clip(0, 65535).astype("<u2").tofile(folder / name)
        (folder / "hydrology.json").write_text(
            json.dumps({"start_tile": tile, "samples": {}}) + "\n"
        )
        report = assess(folder)
        model = {
            "id": "surface-stock-load-reference-v1",
            "parameters": asdict(LOAD),
            "source_sha256": {
                n: hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                for n in [
                    "prepare_surface_controls.py",
                    "surface_intake.py",
                    "start_capabilities.py",
                ]
            },
        }
        model["sha256"] = digest(model)
        report.update(
            {
                "model": model,
                "artifact_sha256": control["sha256"],
                "split": "fixture_control",
                "square": {"stock_map": control["name"]},
                "source_sha": None,
                "scope": "Stock package reference, not an exporter/model accuracy row",
            }
        )
        selected = control_banks(ground, depth, tile)
        if len(selected) != 2:
            rows.append(
                {"slug": panel["slug"], "status": "no_supported_control_witness"}
            )
            continue
        facilities = []
        for (r, c, bank), prefab in zip(selected, ["Water Intake", "Water Outlet"]):
            facilities.append(
                {
                    "prefab": prefab,
                    "anchor": bank["water_anchor"],
                    "model_bank_candidate": bank["bank"],
                    "placement": "one_native_shore_snap",
                    "shore_snap_radius_m": LOAD.shore_snap_radius_m,
                }
            )
        consumer = [
            (
                facilities[0]["model_bank_candidate"][i]
                + facilities[1]["model_bank_candidate"][i]
            )
            / 2
            for i in range(3)
        ]
        witness = {
            "schema": 1,
            "start_tile": tile,
            "facilities": facilities,
            "consumer_point": consumer,
            "load": asdict(LOAD),
            "auxiliary_power": "fixed native supply, fixture control only",
            "channel_route": {
                "intake_water_point": facilities[0]["anchor"],
                "outlet_water_point": facilities[1]["anchor"],
                "direction_basis": "Reference only: no initial cleanliness/downstream prediction",
            },
        }
        report["capabilities"]["water"].update(
            {
                "predicted": None,
                "level": "unknown",
                "reason": "stock_load_reference_not_a_capability_prediction",
                "witness": witness,
                "witness_sha256": digest(witness),
            }
        )
        prediction = output / f"{panel['slug']}.json"
        prediction.write_text(json.dumps(report, indent=2) + "\n")
        rows.append(
            {
                "slug": panel["slug"],
                "status": "prepared",
                "map": str(package),
                "probes": panel["probes"],
                "prediction": str(prediction),
                "model_sha256": model["sha256"],
                "prediction_sha256": hashlib.sha256(
                    prediction.read_bytes()
                ).hexdigest(),
            }
        )
    (output / "controls.json").write_text(json.dumps(rows, indent=2) + "\n")
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["cohort", "stock", "output"]:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(json.loads(args.cohort.read_text()), args.stock, args.output),
            indent=2,
        )
    )
