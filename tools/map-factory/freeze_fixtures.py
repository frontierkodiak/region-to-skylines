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


def freeze(inputs, output):
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
            )
            shutil.copyfile(inputs / f"{slug}.png", case / "input.png")
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
            fixture = {
                "slug": slug,
                "expected_crp_sha256": result["package"]["sha256"],
                "expected_crp_bytes": result["package"]["bytes"],
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
            manifest["cases"].append(fixture)
            print(json.dumps(fixture, ensure_ascii=False), flush=True)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("output", type=Path, nargs="?", default=ROOT / "fixtures")
    args = parser.parse_args()
    freeze(args.inputs, args.output)
