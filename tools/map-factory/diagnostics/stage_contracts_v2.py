"""Fresh protocol for typed JSON reporting of unchanged v1 stage mathematics.

V1's first CPU evaluation wrote escape grids but could not serialize a NumPy
integer. Keep its source/protocol/partial outputs intact; never reuse its plan
with edited code. This wrapper binds v1 and normalizes only numeric JSON scalars.
"""

import argparse
from pathlib import Path

import numpy as np

from bank_authority import ROOT, load, sha, write
import stage_contracts as original

POLICY = "complete-contract-conditional-escape-stage-v2-json"
FILES = ("diagnostics/stage_contracts_v2.py", "diagnostics/test_stage_contracts_v2.py")


def json_scalars(value):
    if isinstance(value, dict):
        return {key: json_scalars(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_scalars(item) for item in value]
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def stage(parent, output):
    if output.exists():
        raise ValueError("Fresh v2 protocol required")
    original.stage(parent, output / "input-v1")
    dependencies = dict(load(output / "input-v1/freeze.json")["source_files_sha256"])
    for name in FILES:
        dependencies[name] = sha(ROOT / name)
    write(
        output / "freeze.json",
        {
            "policy": POLICY,
            "cases": load(output / "input-v1/freeze.json")["cases"],
            "source_files_sha256": dependencies,
            "files_sha256": {
                str(p.relative_to(output)): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
            "correction": "typed JSON scalar normalization only; unchanged v1 geometry, contracts, thresholds and stage mathematics",
            "prior_outcomes_known": True,
            "new_physical_or_native": False,
        },
    )


def preflight(folder):
    freeze = load(folder / "freeze.json")
    if freeze["policy"] != POLICY:
        raise ValueError("Wrong stage v2 policy")
    for root, key in ((ROOT, "source_files_sha256"), (folder, "files_sha256")):
        for name, expected in freeze[key].items():
            if sha(root / name) != expected:
                raise ValueError(f"Bound bytes changed: {name}")
    original.preflight(folder / "input-v1")


def evaluate(folder, output):
    preflight(folder)
    if output.exists():
        raise ValueError("Fresh CPU results required")
    output.mkdir(parents=True)
    for slug in load(folder / "freeze.json")["cases"]:
        write(
            output / f"{slug}.json",
            json_scalars(original.analyze(folder / "input-v1", slug, output)),
        )
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
        ("stage", ["parent", "output"]),
        ("preflight", ["folder"]),
        ("evaluate", ["folder", "output"]),
    ):
        command = sub.add_parser(name)
        for argument in arguments:
            command.add_argument(argument, type=Path)
    args = vars(parser.parse_args())
    globals()[args.pop("command")](**args)
