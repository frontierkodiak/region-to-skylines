"""Additive logical subset tightening of retained startup-support v1 outputs.

No new geometry, water, protections or native observations. V1 remains immutable.
"""

import argparse
import copy
from pathlib import Path
import shutil

from bank_authority import ROOT, load, sha, write
from startup_support_bound import aggregate, VIEWS

POLICY = "startup-support-logical-subset-ordering-v2"
FILES = (
    "diagnostics/startup_support_ordering.py",
    "diagnostics/test_startup_support_ordering.py",
    "calibration/pl1191-construction-v1/development/phase29-ordering-erratum.md",
)


def tighten(row):
    out = copy.deepcopy(row)
    changed = []
    for contract in out["contracts"]:
        for i, point in enumerate(contract["points"]):
            values = point["availability"]
            if values[VIEWS[1]] is False and values[VIEWS[2]] is None:
                values[VIEWS[2]] = False
                changed.append([contract["contract"]["id"], i])
        fraction = 1 if contract["contract"]["kind"] == "engineered" else 0.95
        contract["views"] = {
            v: aggregate([p["availability"][v] for p in contract["points"]], fraction)
            for v in VIEWS
        }
    if "summary" in out:
        from collections import Counter

        out["summary"]["views_natural_only"] = {
            v: dict(
                Counter(
                    c["views"][v]["status"]
                    for c in out["contracts"]
                    if c["contract"]["kind"] == "natural"
                )
            )
            for v in VIEWS
        }
    out["additive_subset_ordering_correction"] = {
        "policy": POLICY,
        "changed_unknown_to_false_points": changed,
        "reason": "b is a subset of a2; known a2 impossibility also bounds b",
        "masks_geometry_water_cohort_and_known_true_values_unchanged": True,
        "no_new_physical_or_native_outcomes": True,
    }
    return out


def stage(protocol, results, output):
    if output.exists():
        raise ValueError("Fresh additive correction protocol required")
    receipt = load(results / "receipt.json")
    if receipt["prospective_freeze_sha256"] != sha(protocol / "freeze.json"):
        raise ValueError("Wrong original protocol")
    for name, expected in receipt["files_sha256"].items():
        if sha(results / name) != expected:
            raise ValueError("Original results changed")
    output.mkdir(parents=True)
    shutil.copytree(results, output / "original-results")
    shutil.copyfile(protocol / "freeze.json", output / "original-freeze.json")
    deps = dict(load(protocol / "freeze.json")["source_files_sha256"])
    for name in FILES:
        deps[name] = sha(ROOT / name)
    for name, expected in deps.items():
        if sha(ROOT / name) != expected:
            raise ValueError("Original source changed")
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": load(protocol / "freeze.json")["cases"],
            "source_files_sha256": deps,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "original_outputs_known": True,
            "postanalysis_logical_correction_not_new_experiment": True,
        },
    )


def evaluate(protocol, output):
    freeze = load(protocol / "freeze.json")
    if freeze["policy"] != POLICY or output.exists():
        raise ValueError("Wrong policy or reused output")
    for root, key in ((ROOT, "source_files_sha256"), (protocol, "files_sha256")):
        for name, expected in freeze[key].items():
            if sha(root / name) != expected:
                raise ValueError(f"Changed bound source/input: {name}")
    output.mkdir(parents=True)
    for case in freeze["cases"]:
        write(
            output / f"{case}.json",
            tighten(load(protocol / "original-results" / f"{case}.json")),
        )
    write(
        output / "receipt.json",
        {
            "policy": POLICY,
            "input_freeze_sha256": sha(protocol / "freeze.json"),
            "files_sha256": {
                p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()
            },
            "new_physical_or_native": False,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("stage")
    for name in ("protocol", "results", "output"):
        p.add_argument(name, type=Path)
    p = sub.add_parser("evaluate")
    p.add_argument("protocol", type=Path)
    p.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "stage":
        stage(args.protocol, args.results, args.output)
    else:
        evaluate(args.protocol, args.output)


if __name__ == "__main__":
    main()
