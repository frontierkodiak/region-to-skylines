"""Build a read-only, source-bound corpus from all native run-registry entries.

Populated/saved-city data is excluded before opening report contents. Existing
receipts, original thresholds and flood-reference variants are never rewritten.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from crp import read_package
from water_diagnostics import bind_sources, decode_water
from water_risk import measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_outcome(report, verdict):
    minutes = float(report.get("game_minutes") or 0)
    full = minutes >= 60
    checks = {c["name"]: c for c in verdict["checks"]}
    flood, endpoint = checks.get("no_flooding", {}), checks.get("probes_wet_end", {})
    throughout = checks.get("probes_wet_throughout", {})
    fv = flood.get("value")
    # Preserve the original verdict even if its displayed area was rounded.
    flood_label = (
        True
        if flood.get("status") == "fail" and isinstance(fv, dict) and "worst_km2" in fv
        else False
        if full and flood.get("status") == "pass"
        else None
    )
    ev, tv = endpoint.get("value") or {}, throughout.get("value") or {}
    required = ev.get("required", 0)
    missing = ev.get("wet", required) < required or tv.get(
        "wet_throughout", required
    ) < tv.get("required", required)
    required_loss = (
        True
        if required and missing
        else False
        if full and required and endpoint.get("status") == "pass"
        else None
    )
    points = report.get("points") or []
    initialized = [p for p in points if p.get("wet_start") is True]
    isolated_loss = sum(
        not p.get("wet_end") and not p.get("wet_within_64m_end") for p in initialized
    )
    exact_loss = sum(not p.get("wet_end") for p in initialized)
    dry_label = (
        True
        if required_loss or isolated_loss
        else False
        if full and initialized and required_loss is False
        else None
    )
    return {
        "labels": {"flood": flood_label, "drying": dry_label},
        "original_dry_gate_failed": endpoint.get("status") == "fail"
        or throughout.get("status") == "fail",
        "flood_reference": fv.get("reference") if isinstance(fv, dict) else None,
        "flood_worst_km2": fv.get("worst_km2") if isinstance(fv, dict) else None,
        "required": required,
        "required_wet_end": ev.get("wet"),
        "required_water_loss": required_loss,
        "initialized_observations": len(initialized),
        "initialized_water_loss_end": isolated_loss,
        "exact_point_wet_loss_end": exact_loss,
        "original_native_water_failures": [
            c["name"]
            for c in checks.values()
            if c["name"] in ["no_flooding", "probes_wet_end", "probes_wet_throughout"]
            and c["status"] == "fail"
        ],
    }


def extract(registry):
    latest = {}
    for line in registry.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            latest[row["path"]] = row
    rows, coverage = [], []
    for original in latest.values():
        directory = Path(original["path"])
        native_minutes = float(original.get("metrics", {}).get("game_minutes") or 0)
        item = {
            "run_id": original["id"],
            "run_path_sha256": hashlib.sha256(str(directory).encode()).hexdigest(),
            "minutes": native_minutes,
        }
        try:
            if (original.get("metrics", {}).get("population_end") or 0) > 0 or str(
                original.get("map") or ""
            ).startswith("save "):
                item.update(
                    run_id="populated-or-saved-city", status="excluded_nonempty_city"
                )
                continue
            report = json.loads((directory / "report.json").read_text())
            verdict = json.loads((directory / "verdict.json").read_text())
            minutes = float(report.get("game_minutes") or 0)
            item["minutes"] = minutes
            if minutes < 5:
                item["status"] = "incomplete_under_five_minutes"
                continue
            outcome = native_outcome(report, verdict)
            item["native_outcome"] = outcome
            package = Path(
                report.get("session", {}).get("map", {}).get("source", "/nonexistent")
            )
            if not package.is_file():
                item["status"] = "input_package_unavailable"
                continue
            digest = sha(package)
            if digest != original.get("map_sha256"):
                item["status"] = "input_package_hash_mismatch"
                continue
            prepared = package.parent
            hydro = json.loads((prepared / "hydrology.json").read_text())
            terrain = np.fromfile(prepared / "terrain.u16", "<u2").reshape(1081, 1081)
            water = np.fromfile(prepared / "water.u16", "<u2").reshape(1081, 1081)
            for name in ["terrain.u16", "water.u16"]:
                initial = directory / "grids" / ("t000-" + name)
                if not initial.is_file() or sha(prepared / name) != sha(initial):
                    raise ValueError(
                        "initial source/native grid binding missing or inconsistent"
                    )
            _, assets = read_package(package.read_bytes())
            decoded = decode_water(
                next(a["payload"] for a in assets if a["kind"] == 52)
            )
            bind_sources(decoded, hydro)
            if not np.array_equal(decoded["depth"].reshape(1081, 1081), water):
                raise ValueError("package water differs from preparation")
            full = minutes >= 60
            # Group names are validation/report labels, never predictor inputs.
            group = (
                str(original.get("map") or "")
                .split(" - Ready to Play")[0]
                .split(" (")[0]
            )
            run_id = str(directory).split("/experiments/", 1)[-1]
            data = {
                "run": run_id,
                "package_sha256": digest,
                "group": group,
                "minutes": minutes,
                "complete_60": full,
                "features": measure(terrain, water, hydro),
                **outcome,
                "input_hashes": {
                    name: sha(prepared / name)
                    for name in ["terrain.u16", "water.u16", "hydrology.json"]
                },
                "receipt_hashes": {
                    name: sha(directory / name)
                    for name in ["report.json", "verdict.json"]
                },
                "encoded_controls_bound": True,
            }
            rows.append(data)
            item.update(status="included", group=group, labels=data["labels"])
        except (OSError, ValueError, KeyError, TypeError, StopIteration) as error:
            item.update(
                status="unavailable_or_inconsistent", reason=type(error).__name__
            )
        finally:
            coverage.append(item)
    return rows, coverage


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    rows, coverage = extract(args.registry)
    for name, data in [("rows.json", rows), ("coverage.json", coverage)]:
        (args.out / name).write_text(json.dumps(data, indent=2) + "\n")
    print(
        json.dumps(
            {
                "rows": len(rows),
                "coverage": dict(Counter(c["status"] for c in coverage)),
            }
        )
    )
