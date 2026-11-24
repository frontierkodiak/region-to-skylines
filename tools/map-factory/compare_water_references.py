"""Compare saved first-hour water outcomes; never rewrite historical labels."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys


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
        rows.append(summarize(case["slug"], case["kind"], folder, outcome))
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
        rows.append(summarize(slug, "rejected-PR99", folder, outcome))
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
