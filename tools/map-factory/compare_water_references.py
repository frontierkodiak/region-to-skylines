"""Compare saved first-hour water outcomes; never rewrite historical labels."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np


def sampled_surfaces(folder, inventory):
    """Keep dry/missing samples separate; dry ground is not a water surface."""
    wanted = {
        name
        for entry in inventory["entries"]
        for contract in entry.get("contracts", [])
        if contract["kind"] == "natural"
        for name in contract["probe_names"]
    }
    initial, traces = None, []
    with (folder / "timeline.jsonl").open() as stream:
        for line in stream:
            sample = json.loads(line)
            if sample["kind"] != "sample":
                continue
            heads, dry, missing = {}, 0, 0
            seen = set()
            for point in sample["water"]["samples"]:
                name = point.get("name")
                if name not in wanted:
                    continue
                if name in seen:
                    raise ValueError("Ambiguous duplicate natural-point name")
                seen.add(name)
                surface = point.get("surface")
                depth = point.get("depth")
                if (
                    point.get("wet") is True
                    and isinstance(surface, (float, int))
                    and np.isfinite(surface)
                    and isinstance(depth, (float, int))
                    and np.isfinite(depth)
                    and depth > 0
                ):
                    heads[name] = surface
                elif point.get("wet") is False or (
                    isinstance(depth, (float, int))
                    and np.isfinite(depth)
                    and depth <= 0
                ):
                    dry += 1
                else:
                    missing += 1
            missing += len(wanted - seen)
            if initial is None:
                initial = heads
            changes = [
                head - initial[name] for name, head in heads.items() if name in initial
            ]
            traces.append(
                {
                    "label": sample["label"],
                    "wet_heads": len(heads),
                    "dry": dry,
                    "missing": missing,
                    "paired_initial_wet_heads": len(changes),
                    "delta_p10_p50_p90_m": np.percentile(changes, [10, 50, 90]).tolist()
                    if changes
                    else None,
                    "absolute_delta_p95_m": float(np.percentile(np.abs(changes), 95))
                    if changes
                    else None,
                }
            )
    return traces


def summarize(slug, kind, folder, outcome):
    report = json.loads((folder / "report.json").read_text())
    verdict = json.loads((folder / "verdict.json").read_text())
    natural = [c for c in outcome["contracts"] if c["kind"] == "natural"]
    by_sample = {}
    for contract in natural:
        for sample in contract["samples"]:
            row = by_sample.setdefault(sample["label"], Counter())
            for key in ["wet", "total", "missing"]:
                row[key] += sample[key]
    traces = [
        {
            "label": label,
            **dict(row),
            "fraction": row["wet"] / row["total"]
            if row["total"] and not row["missing"]
            else None,
        }
        for label, row in by_sample.items()
    ]
    valid = [row["fraction"] for row in traces if row["fraction"] is not None]
    flood = next(c for c in verdict["checks"] if c["name"] == "no_flooding")
    return {
        "square": slug,
        "kind": kind,
        "game_minutes": report["game_minutes"],
        "observation_complete": outcome["observation_complete"],
        "flood_km2": flood.get("value", {}).get("worst_km2"),
        "legacy_flood_status": flood["status"],
        "natural_contracts": len(natural),
        "natural_contract_states": dict(Counter(c["status"] for c in natural)),
        "natural_point_occurrence_fractions": traces,
        "minimum_point_occurrence_wet_fraction": min(valid)
        if len(valid) == len(traces) and valid
        else None,
        "raw_failed_checks": verdict["failed"],
        "panel_view_problems": {
            c["name"]: c.get("value", {}).get("problems", [])
            for c in verdict["checks"]
            if c["name"] in ["new_game_panel", "startup_views"]
        },
    }


def main(root, prior, observer, output):
    sys.path.insert(0, str(observer.resolve()))
    from maintained_water_inventory import feature_outcome

    plan = json.loads((root / "selection.json").read_text())
    rows = []
    for case in plan["cases"]:
        folder = root / "native" / (case["slug"] + "-attempt-1")
        if not (folder / "report.json").is_file():
            continue
        report = json.loads((folder / "report.json").read_text())
        if report["session"]["cleanup"] != {
            "game": [],
            "steam_instances": [],
            "units_active": [],
        }:
            continue
        inventory = json.loads(
            (root / "maps" / case["slug"] / "maintained-inventory.json").read_text()
        )
        with (folder / "timeline.jsonl").open() as stream:
            samples = [
                row for line in stream if (row := json.loads(line))["kind"] == "sample"
            ]
        outcome = feature_outcome(inventory, report, samples)
        row = summarize(case["slug"], case["kind"], folder, outcome)
        row["sampled_surface_traces"] = sampled_surfaces(folder, inventory)
        rows.append(row)
    for slug in [
        "asheville",
        "innsbruck",
        "rio",
        "pittsburgh",
        "charleston",
        "grand-canyon",
        "hong-kong",
        "yosemite",
    ]:
        folder = prior / "after-native-v7" / slug
        outcome = json.loads((folder / "maintained-feature-outcome.json").read_text())
        inventory = json.loads(
            (
                prior / "after-native-v7/maps" / slug / "maintained-inventory.json"
            ).read_text()
        )
        row = summarize(slug, "rejected-PR99", folder, outcome)
        row["sampled_surface_traces"] = sampled_surfaces(folder, inventory)
        rows.append(row)
    result = {
        "scope": "Reference comparison, no threshold choice or historical relabeling",
        "complete_reference_cases": sum(
            r["kind"] != "rejected-PR99" and r["observation_complete"] for r in rows
        ),
        "required_reference_cases": 5,
        "denominators": "Stock: all serialized initial-water bodies split into sectors. Export: original geographic contracts. Point occurrences are not unique area or global natural-water coverage.",
        "rows": rows,
    }
    output.write_text(json.dumps(result, indent=2) + "\n")
    for row in rows:
        print(
            row["kind"],
            row["square"],
            "flood",
            row["flood_km2"],
            "wet fraction",
            row["minimum_point_occurrence_wet_fraction"],
            "contracts",
            row["natural_contract_states"],
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["root", "prior", "observer", "output"]:
        parser.add_argument(name, type=Path)
    main(**vars(parser.parse_args()))
