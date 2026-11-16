"""Materialize CPU native-admission plans for short tests, not qualification.

Unchanged cases retain their exact old packages. Changed cases replay the same
resource plan and retain every source and network control. No fixture/default
file is written. Each plan is bound to its original prepared bytes.
"""

import argparse
import json
from pathlib import Path
import shutil

import numpy as np

from minor_stream_candidate import SLUGS, inspect_package
from native_admission import ROOT, read, sha
from paint import paint


def package(prepared, plans, output):
    if output.exists():
        raise ValueError("Use a fresh output directory")
    if {p.name for p in plans.iterdir() if p.is_dir()} != set(SLUGS):
        raise ValueError("The complete five-map CPU preflight is required")
    results = []
    for plan in sorted(p for p in plans.iterdir() if p.is_dir()):
        report = read(plan / "admission.json")
        for name, digest in report["planner_files_sha256"].items():
            if sha(ROOT / name) != digest:
                raise ValueError(f"{plan.name}: planner source changed for {name}")
        original = prepared / plan.name
        for name, digest in report["prepared_files_sha256"].items():
            if sha(original / name) != digest:
                raise ValueError(f"{plan.name}: stale plan for {name}")
        for name, digest in report["candidate_files_sha256"].items():
            if sha(plan / name) != digest:
                raise ValueError(f"{plan.name}: candidate plan changed for {name}")
        if (
            read(original / "generation.json")["package"]["sha256"]
            != report["binding"]["package_sha256"]
        ):
            raise ValueError(f"{plan.name}: package identity changed")
        target = output / plan.name
        shutil.copytree(original, target)
        changed = any(
            (plan / name).read_bytes() != (original / name).read_bytes()
            for name in ["terrain.u16", "water.u16"]
        )
        if changed:
            for name in ["terrain.u16", "water.u16", "hydrology.json"]:
                shutil.copyfile(plan / name, target / name)
            result = paint(target, None, target, plan=original / "plan.npz")
            # npz archive metadata is not a resource change. Prove arrays match
            # before retaining the original archive bytes for provenance.
            with np.load(original / "plan.npz") as a, np.load(target / "plan.npz") as b:
                if set(a.files) != set(b.files):
                    raise ValueError("Resource-plan fields changed")
                for name in a.files:
                    np.testing.assert_array_equal(a[name], b[name])
            shutil.copyfile(original / "plan.npz", target / "plan.npz")
            generation = read(target / "generation.json")
            generation.update(package=result["package"], in_game_verified=False)
            generation["native_admission"] = {
                "plan_sha256": sha(plan / "admission.json"),
                "status": "unqualified",
            }
            (target / "generation.json").write_text(
                json.dumps(generation, indent=2) + "\n"
            )
        shutil.copyfile(plan / "admission.json", target / "admission.json")
        hydro = read(target / "hydrology.json")
        if (original / "hydrology.json").read_bytes() != (
            target / "hydrology.json"
        ).read_bytes():
            raise ValueError("Existing hydrology controls, routes or layout changed")
        inspect_package(target)
        item = {
            "case": plan.name,
            "changed": changed,
            "package_sha256": sha(target / (hydro["map_id"] + ".crp")),
            "grids_sha256": {
                name: sha(target / name) for name in ["terrain.u16", "water.u16"]
            },
            "resource_plan_byte_exact": sha(target / "plan.npz")
            == sha(original / "plan.npz"),
            "hydrology_byte_exact": True,
            "native_qualification": False,
        }
        results.append(item)
        print(json.dumps(item), flush=True)
    (output / "packages.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["prepared", "plans", "output"]:
        parser.add_argument(name, type=Path)
    package(**vars(parser.parse_args()))
