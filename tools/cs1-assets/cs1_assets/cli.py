"""cs1-assets: make building assets the CS1 Asset Editor can import.

`kit-house` takes one building from the kudzu kit (PL-801), bakes CS1 texture maps and a LOD,
and writes `<name>.fbx`, `<name>_lod.fbx` and the `_d/_s/_i/_c` maps into one directory: the
layout the game's Addons/Import folder and `cs1-harness asset build` expect.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

from . import kit_bake

HERE = pathlib.Path(__file__).resolve().parent
BLENDER_DEFAULT = pathlib.Path.home() / ".cache/pl880/blender-4.2.9-linux-x64/blender"


def blender_exe(arg: str | None) -> str:
    for cand in (arg, os.environ.get("BLENDER"), shutil.which("blender"), str(BLENDER_DEFAULT)):
        if cand and pathlib.Path(cand).exists():
            return cand
    raise SystemExit("no Blender found: pass --blender, set BLENDER, or put blender on PATH (4.2 LTS tested)")


def cmd_kit_house(a) -> int:
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    raw = out / f"{a.name}.kit.json"
    node = [
        "node",
        str(HERE.parent / "export_kit.mjs"),
        "--kit",
        str(a.kit.resolve()),
        "--type",
        a.type,
        "--seed",
        str(a.seed),
        "--setback",
        str(a.setback),
        "--out",
        str(raw),
    ]
    for flag in ("width", "depth", "storeys", "variant"):
        if getattr(a, flag) is not None:
            node += [f"--{flag}", str(getattr(a, flag))]
    subprocess.run(node, check=True)
    baked = kit_bake.bake(raw, out, a.name, kit_bake.lot_from(a.lot))
    cmd = [
        blender_exe(a.blender),
        "-b",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "-P",
        str(HERE / "blender_fbx.py"),
        "--",
    ]
    cmd += [str(out / f"{a.name}.mesh.json"), str(out)] + (["--preview"] if a.preview else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-4000:] + r.stderr[-4000:])
        return r.returncode
    receipt = json.loads((out / f"{a.name}.bake.json").read_text())
    receipt["fbx"] = json.loads((out / "fbx-receipt.json").read_text())
    (out / f"{a.name}.bake.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: receipt[k] for k in ("name", "lot_cells", "size_m", "main_triangles", "lod_triangles")}))
    print(f"import set in {out}: {baked.name}.fbx, {baked.name}_lod.fbx and {len(baked.files)} texture maps")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="cs1-assets", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("kit-house", help="one kudzu-kit building to an importable FBX set")
    k.add_argument(
        "--kit", type=pathlib.Path, required=True, help="the kudzu-kit directory (agentic-research-workbench)"
    )
    k.add_argument(
        "--type", default="craftsman", help="kit type (craftsman, foursquare, queenAnne, ranch, millHouse...)"
    )
    k.add_argument("--seed", type=float, default=0.31)
    k.add_argument("--width", type=float, help="footprint along the street, m (default: the type's)")
    k.add_argument("--depth", type=float, help="footprint depth, m (default: the type's)")
    k.add_argument("--storeys", type=float)
    k.add_argument("--variant", type=int)
    k.add_argument("--setback", type=float, default=3, help="front walk length, m")
    k.add_argument("--lot", default="2x2", help="lot in 8 m cells, width x depth (growables: up to 4x4)")
    k.add_argument("--name", default="KudzuCraftsman", help="mesh and file name (no spaces or underscores)")
    k.add_argument("--out", type=pathlib.Path, required=True)
    k.add_argument("--blender", help="Blender executable (4.2 LTS tested)")
    k.add_argument("--preview", action="store_true", help="also render two Cycles previews")
    a = p.parse_args(argv)
    if "_" in a.name or " " in a.name:
        raise SystemExit("--name: no spaces or underscores (the game finds the LOD as <name>_lod)")
    sys.exit({"kit-house": cmd_kit_house}[a.cmd](a))


if __name__ == "__main__":
    main()
