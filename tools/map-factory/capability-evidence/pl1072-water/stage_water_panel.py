"""Bind captured maps and predetermined observations without launching a game."""

import argparse
import json
from pathlib import Path
import shutil

import numpy as np

from crp import read_package
from refresh_water_risk import sha, write
from soak import (
    geographic_river_probes,
    mapped_water_reference,
    probes_for,
    world_references,
)
from water_diagnostics import bind_sources, decode_water
from water_risk import assess

ROOT = Path(__file__).resolve().parent


def input_power(rows):
    """Reject logically uninformative comparisons before spending game time."""
    prepared = [r for r in rows if r["status"] == "prepared"]
    drying = [
        r
        for r in prepared
        if r["prediction"]["risks"].get("drying", {}).get("level") == "flagged"
    ]
    cleared = [
        r["slug"]
        for r in prepared
        if r["prediction"]["status"] != "declined"
        and not any(
            r["prediction"]["risks"][k]["level"] == "flagged"
            for k in ("flood", "drying")
        )
    ]
    contrast = [
        r["slug"]
        for r in prepared
        if r["prediction"]["risks"].get("flood", {}).get("level")
        != r["deployed_prediction"]["risks"].get("flood", {}).get("level")
    ]
    always_warn = bool(prepared) and len(drying) == len(prepared)
    return {
        "prepared": len(prepared),
        "drying_flagged": len(drying),
        "drying_identical_to_always_warn_for_any_labels": always_warn,
        "drying_disposition": "rejected_as_discriminator"
        if always_warn
        else "requires_native_test",
        "rule_cleared_squares": cleared,
        "deployed_product_cleared_squares": [
            r["slug"] for r in prepared if r["deployed_prediction"]["status"] == "lower"
        ],
        "candidate_vs_deployed_flood_disagreements": contrast,
        "flood_threshold_change_identifiable": bool(contrast),
        "uses_native_labels": False,
    }


def stage(panel_path, frozen_path, captures, output):
    panel = json.loads(panel_path.read_text())
    freeze = json.loads((frozen_path / "freeze.json").read_text())
    model_path = frozen_path / "model.json"
    if (
        sha(panel_path) != freeze["panel_sha256"]
        or sha(model_path) != freeze["model_sha256"]
    ):
        raise ValueError("Frozen panel/model changed")
    model = json.loads(model_path.read_text())
    writer = json.loads(
        (ROOT / "fixtures/contracts/pl912-water-risk-v1/current.json").read_text()
    )["source_files_sha256"]
    for name, expected in writer.items():
        if sha(ROOT.parent.parent / name) != expected:
            raise ValueError(f"Current writer differs from its contract: {name}")
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for item in panel["squares"]:
        slug = item["sq"]["slug"]
        captured = captures / slug
        if not (captured / "capture.json").exists():
            failure = captured / "failure.json"
            if not failure.exists():
                raise ValueError(f"Square has not been attempted: {slug}")
            rows.append(
                {
                    "slug": slug,
                    "stratum": item["stratum"],
                    "world_region": item["world_region"],
                    "status": "capture_failed",
                    "failure_sha256": sha(failure),
                }
            )
            continue
        capture = json.loads((captured / "capture.json").read_text())
        if capture["source_files_sha256"] != writer:
            raise ValueError(f"Capture writer is not source-equivalent: {slug}")
        if capture["sq"]["slug"] != slug or any(
            capture[k] != freeze[k] for k in ("panel_sha256", "model_sha256")
        ):
            raise ValueError(f"Capture is not bound to this experiment: {slug}")
        if any(capture["sq"][k] != value for k, value in item["sq"].items()):
            raise ValueError(f"Captured square changed: {slug}")
        for name, expected in capture["files_sha256"].items():
            if sha(captured / "work" / name) != expected:
                raise ValueError(f"Captured work file changed: {slug}/{name}")
        source, folder = captured / "work/out", output / slug
        folder.mkdir()
        hydro = json.loads((source / "hydrology.json").read_text())
        geometry = json.loads((source / "geometry.json").read_text())
        package_name = hydro["map_id"] + ".crp"
        for name in [
            package_name,
            "terrain.u16",
            "water.u16",
            "hydrology.json",
            "geometry.json",
            "generation.json",
        ]:
            shutil.copyfile(source / name, folder / name)
        package = folder / package_name
        if sha(package) != capture["package_sha256"]:
            raise ValueError(f"Captured package mismatch: {slug}")
        terrain = np.fromfile(folder / "terrain.u16", "<u2").reshape(1081, 1081)
        water = np.fromfile(folder / "water.u16", "<u2").reshape(1081, 1081)
        _, assets = read_package(package.read_bytes())
        decoded = decode_water(next(a["payload"] for a in assets if a["kind"] == 52))
        bind_sources(decoded, hydro)
        if not np.array_equal(decoded["depth"].reshape(1081, 1081), water):
            raise ValueError(f"Package does not encode the measured water: {slug}")
        probes = probes_for(
            hydro, json.loads((ROOT / "templates/native-corridors.json").read_text())
        )
        geographic_river_probes(probes, geometry)
        # Optional observations cover retained water, including lakes and sea.
        # They do not change which ordinary river observations are required.
        for row, col in np.argwhere(water[::4, ::4] > 0) * 4:
            probes["points"].append(
                {
                    "name": f"initial-lattice:{row},{col}",
                    "x": int(col) * 16 - 8640,
                    "z": int(row) * 16 - 8640,
                    "required": False,
                }
            )
        for source in hydro["sources"]:
            if source.get("class") == "reservoir":
                x, _, z = source["position"]
                probes["points"].append(
                    {"name": "constructed-reservoir", "x": x, "z": z, "required": True}
                )
        mapped_water_reference(probes, geometry, folder)
        # The initial water is fixed BEFORE launch, rather than allowing a
        # delayed first native dump to silently absorb a startup flood.
        probes["reference_water"] = "water.u16"
        world_references(probes, geometry)
        write(folder / "probes.json", probes)
        assessment = assess(terrain, water, hydro, model)
        write(folder / "prediction.json", assessment)
        deployed = assess(terrain, water, hydro)
        if deployed != capture["runtime_assessment"]:
            raise ValueError(f"Captured deployed assessment does not reproduce: {slug}")
        write(folder / "deployed-prediction.json", deployed)
        rows.append(
            {
                "slug": slug,
                "status": "prepared",
                "stratum": item["stratum"],
                "world_region": item["world_region"],
                "package": package_name,
                "capture_sha256": sha(captured / "capture.json"),
                "capture_source_commit": capture["source_commit"],
                "files_sha256": {
                    p.name: sha(p) for p in sorted(folder.iterdir()) if p.is_file()
                },
                "prediction": assessment,
                "deployed_prediction": deployed,
                "points": len(probes["points"]),
            }
        )
        print(f"{slug}: {len(probes['points'])} probes", flush=True)
    manifest = {
        "schema": 1,
        "panel_sha256": freeze["panel_sha256"],
        "model_sha256": freeze["model_sha256"],
        "freeze_sha256": sha(frozen_path / "freeze.json"),
        "writer_source_files_sha256": writer,
        "input_power": input_power(rows),
        "squares": rows,
    }
    write(output / "staging.json", manifest)
    write(output / "input-power.json", manifest["input_power"])
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("panel", "frozen", "captures", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    stage(args.panel, args.frozen, args.captures, args.output)
