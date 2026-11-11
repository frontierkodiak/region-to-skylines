"""Prepare labelled diagnostics separating source output from initial land fill.

These are not release candidates. Native terrain, source positions/targets and
intake rates stay fixed. The noemit arm sets only output rates to zero; nofill
retains sources and ocean fill but removes water initially above sea level.
Shallow-head retains terrain, prefill, placement and both rates, and caps only
bank-limited source targets at one metre above the finished local grid bed.
Resource plans, when present, are replayed rather than replanned.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

from crp import write_map
from paint import load_plan
from resources import TREE_NAMES

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source, output, arm):
    receipt = json.loads((source / "generation.json").read_text())
    hydro = copy.deepcopy(json.loads((source / "hydrology.json").read_text()))
    original = source / (hydro["map_id"] + ".crp")
    assert digest(original) == receipt["package"]["sha256"]
    output.mkdir(parents=True, exist_ok=False)
    for name in ["terrain.u16", "water.u16", "geometry.json"]:
        shutil.copyfile(source / name, output / name)
    hydro["map_id"] += "-diagnostic-" + arm
    hydro["map_name"] += " (diagnostic " + arm + "; not a release)"
    if arm == "noemit":
        for control in hydro["sources"]:
            control["output_capacity"] = 0
    elif arm == "nofill":
        terrain = np.fromfile(source / "terrain.u16", dtype="<u2") / 64
        sea = hydro.get("sea_level_m") or 0
        depth = np.maximum(0, sea - terrain)
        np.floor(depth * 64 + 0.5).clip(0, 65535).astype("<u2").tofile(
            output / "water.u16"
        )
    else:
        terrain = (
            np.fromfile(source / "terrain.u16", dtype="<u2").reshape(1081, 1081) / 64
        )
        for control in hydro["sources"]:
            if not control.get("bank_limited"):
                continue
            ix = round((control["position"][0] + 8640) / 16)
            iz = round((control["position"][2] + 8640) / 16)
            control["target"] = float(min(control["target"], terrain[iz, ix] + 1))
        hydro["diagnostic_bank_limited_head_cap_m"] = 1
    (output / "hydrology.json").write_text(json.dumps(hydro, indent=2) + "\n")
    plan = receipt.get("resource_plan")
    resources = None
    if plan:
        assert digest(source / plan["file"]) == plan["sha256"]
        shutil.copyfile(source / plan["file"], output / "plan.npz")
        resources = (load_plan(output / "plan.npz"), TREE_NAMES)
    package = write_map(
        ROOT / "templates/native-corridors.crp",
        ROOT / "templates/native-corridors.json",
        output / "terrain.u16",
        output / "water.u16",
        output / "hydrology.json",
        output / (hydro["map_id"] + ".crp"),
        resources=resources,
    )
    result = {
        "package": package,
        "prefill": arm != "nofill",
        "diagnostic": arm,
        "base_map_sha256": digest(original),
        "release_candidate": False,
        "in_game_verified": False,
    }
    if plan:
        result["resource_plan"] = {
            "file": "plan.npz",
            "sha256": digest(output / "plan.npz"),
        }
    (output / "generation.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--arm", choices=["noemit", "nofill", "shallow-head"], required=True
    )
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output, args.arm), indent=2))
