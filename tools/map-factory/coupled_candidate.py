"""Build ONE coupled source-deferral arm; original default candidates stay held."""

import argparse
import functools
import json
import shutil
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image
import region
import inspect
from generate import generate

ROOT = Path(__file__).resolve().parent


def build(source, trace, output):
    if "coupled_portals" not in inspect.signature(region.hydrology).parameters:
        raise RuntimeError(
            "Rejected arm: full replay requires experimental commit 2182494, not default generation"
        )
    output.mkdir(parents=True, exist_ok=False)
    command = subprocess.run(
        [
            "node",
            str(ROOT / "coupled-input.mjs"),
            str(source),
            str(trace),
            str(output / "browser-delta.f32"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    original = (
        np.asarray(Image.open(ROOT / "fixtures/rio/input.png"), dtype=float)
        * 1024
        / 65535
    )
    banks = np.fromfile(source / "banks.f32", dtype="<f4").reshape(1081, 1081)
    delta = np.fromfile(output / "browser-delta.f32", dtype="<f4").reshape(1081, 1081)
    heights = np.maximum(original, np.minimum(banks, original + delta))
    encoded = np.floor(heights * 65535 / 1024 + 0.5).clip(0, 65535).astype(np.uint16)
    Image.fromarray(encoded).save(output / "input.png")
    region.hydrology = functools.partial(region.hydrology, coupled_portals=True)
    result = generate(
        output / "input.png",
        source / "source-geometry.json",
        output,
        source / "banks.f32",
        landcover=ROOT / "fixtures/rio/landcover.u8.gz",
        evidence=ROOT / "fixtures/rio/shipping-evidence.json",
    )
    for name in ["banks.f32", "source-geometry.json"]:
        shutil.copyfile(source / name, output / name)
    report = {
        "experimental_coupled": True,
        "browser": json.loads(command.stdout),
        "generation": result,
    }
    (output / "coupled-receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["browser"]), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("trace", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    build(a.source, a.trace, a.output)
