"""Intentionally replace the Python/JavaScript reference fixtures from captures.

This is a fixture-authoring command, never part of verification. Review changed
hashes and native-game results before accepting an updated reference contract.
"""

import argparse
import gzip
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from generate import ROOT, generate

REGIONS = ["asheville", "innsbruck", "rio", "pittsburgh", "charleston"]


def freeze(inputs, output, resource_inputs=None):
    output.mkdir(parents=True, exist_ok=True)
    template = ROOT / "templates/native-corridors.crp"
    manifest = {
        "format": 1,
        "template": "templates/native-corridors.crp",
        "layout": "templates/native-corridors.json",
        "template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
        "native_template_origin": "PL-848 editor factory; region-to-skylines PR #1 at 4011a6b717e50bebd92f0b9caf8547a7a16e5c8c",
        "status": "byte reference; native qualification tracked separately in NATIVE_FINDINGS.md",
        "cases": [],
    }
    with tempfile.TemporaryDirectory(prefix=".freeze-", dir=output) as temporary:
        scratch = Path(temporary)
        for slug in REGIONS:
            case = output / slug
            case.mkdir(exist_ok=True)
            generated = scratch / slug
            result = generate(
                inputs / f"{slug}.png",
                inputs / f"{slug}-geometry.json",
                generated,
                inputs / f"{slug}-banks.f32",
                landcover=resource_inputs / slug / "landcover.u8.gz"
                if resource_inputs
                else None,
                evidence=resource_inputs / slug / "evidence.json"
                if resource_inputs
                and (resource_inputs / slug / "evidence.json").exists()
                else None,
            )
            shutil.copyfile(inputs / f"{slug}.png", case / "input.png")
            landmarks = inputs / f"{slug}-landmarks.json"
            if landmarks.exists():
                shutil.copyfile(landmarks, case / "landmarks.json")
            elif (case / "landmarks.json").exists():
                raise ValueError(f"Refusing to silently reuse stale {slug} landmarks")
            files = {
                "geometry.json": inputs / f"{slug}-geometry.json",
                "banks.f32": inputs / f"{slug}-banks.f32",
                "terrain.u16": generated / "terrain.u16",
                "water.u16": generated / "water.u16",
                "hydrology.json": generated / "hydrology.json",
            }
            for name, source in files.items():
                (case / (name + ".gz")).write_bytes(
                    gzip.compress(source.read_bytes(), compresslevel=9, mtime=0)
                )
            if resource_inputs:
                for name in ["landcover.u8.gz", "landcover.json", "evidence.json"]:
                    source = resource_inputs / slug / name
                    if source.exists():
                        shutil.copyfile(source, case / name)
                shutil.copyfile(generated / "plan.npz", case / "plan.npz")
                shutil.copyfile(generated / "resources.json", case / "resources.json")
            fixture = {
                "slug": slug,
                "expected_crp_sha256": result["package"]["sha256"],
                "expected_crp_bytes": result["package"]["bytes"],
                "expected_simulation_sha256": result["package"]["simulation_sha256"],
                "prepared_sha256": {
                    name: hashlib.sha256((generated / name).read_bytes()).hexdigest()
                    for name in ["terrain.u16", "water.u16"]
                },
                "files_sha256": {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(case.iterdir())
                    if p.is_file()
                },
            }
            if resource_inputs:
                fixture["resource_plan"] = "plan.npz"
                fixture["resource_knobs"] = result["resources"]["knobs"]
            manifest["cases"].append(fixture)
            print(json.dumps(fixture, ensure_ascii=False), flush=True)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("output", type=Path, nargs="?", default=ROOT / "fixtures")
    parser.add_argument(
        "--resource-inputs",
        type=Path,
        help="Per-region pinned landcover/evidence; freezes and checks resource plans too",
    )
    args = parser.parse_args()
    freeze(args.inputs, args.output, args.resource_inputs)
