"""Bake measured LoD2 buildings into Cities: Skylines import sets.

Reuses the PL-880 bridge: this writes each building in the kit-export format that
`cs1_assets.kit_bake.bake` reads (frontage along u, y up, w back from the street), then
runs that bake and its Blender FBX export. `cs1-harness asset build --src <out>/<name>
--name <name>` turns each set into a `.crp`. The long side of the outline's bounding
rectangle becomes the frontage; walls and roof get one flat colour each.

    uv run export_cs1.py --cs1-assets <region-to-skylines>/tools/cs1-assets 252585 417941
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

from common import EXP, read_json

WALL_HEX = {"brick": "#8a4c35", "stone": "#7c776b", "siding": "#dfd39a"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+", type=int)
    ap.add_argument("--cs1-assets", type=Path, required=True)
    ap.add_argument("--blender", default=str(Path.home() / ".cache/pl880/blender-4.2.9-linux-x64/blender"))
    ap.add_argument("--out", type=Path, default=EXP / "cs1")
    args = ap.parse_args()
    sys.path.insert(0, str(args.cs1_assets))
    from cs1_assets import kit_bake

    for bid in args.ids:
        scene = read_json(EXP / "buildings" / str(bid) / "scene.json")
        arm = scene["arms"]["lod2"]
        rect = np.array(Polygon(scene["ring"]).minimum_rotated_rectangle.exterior.coords)[:4]
        e0, e1 = rect[1] - rect[0], rect[2] - rect[1]
        long = e0 if np.hypot(*e0) >= np.hypot(*e1) else e1
        ang = math.atan2(long[1], long[0])
        c, s = math.cos(-ang), math.sin(-ang)
        t = np.array(arm["tri"], float).reshape(-1, 3, 3)
        u = t[..., 0] * c - t[..., 2] * s
        w = t[..., 0] * s + t[..., 2] * c
        y = np.maximum(t[..., 1], 0.0)
        u -= (u.max() + u.min()) / 2
        w -= w.min()
        p = np.stack([u, y, w], axis=-1)[:, [0, 2, 1]]  # scene triangles wind clockwise from outside; the kit's do not
        name = f"Lod2_{bid}"
        out = args.out / name
        out.mkdir(parents=True, exist_ok=True)
        wall = scene["wall"] if scene["wall"] in WALL_HEX else "siding"
        ramp = np.repeat([1 if k == "roof" else 0 for k in arm["kind"]], 3)
        (out / f"{name}.kit.json").write_text(json.dumps({
            "source": {"pilot": "PL-900", "building": bid, "arm": "measured LoD2 (Roofer 1.0.0, 2017 USGS lidar)"},
            "frame": "kit-local: u right along the frontage, y up, w back from the street; metres",
            "triangles": len(p), "position": np.round(p, 4).reshape(-1).tolist(), "ramp": ramp.tolist(),
            "ramps": {"0": {"name": wall, "hex": WALL_HEX[wall]}, "1": {"name": "roof", "hex": "#55585e"}},
        }))
        size = p.reshape(-1, 3).max(axis=0) - p.reshape(-1, 3).min(axis=0)
        lot = (math.ceil((size[0] + 0.5) / 8), math.ceil((size[2] + 2.5) / 8))
        if max(lot) > 4:
            print(bid, "does not fit a 4x4-cell lot:", np.round(size, 1))
            continue
        baked = kit_bake.bake(out / f"{name}.kit.json", out, name, lot)
        r = subprocess.run([args.blender, "-b", "--factory-startup", "--python-exit-code", "1", "-P",
                            str(args.cs1_assets / "cs1_assets" / "blender_fbx.py"), "--", str(out / f"{name}.mesh.json"), str(out), "--preview"],
                           capture_output=True, text=True)
        if r.returncode:
            print(bid, "blender failed:", (r.stdout + r.stderr)[-1500:])
            continue
        receipt = json.loads((out / f"{name}.bake.json").read_text())
        receipt["fbx"] = json.loads((out / "fbx-receipt.json").read_text())
        (out / f"{name}.bake.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(bid, name, "lot", lot, "size", [round(float(v), 1) for v in baked.size], "triangles", baked.main_triangles, "lod", baked.lod_triangles)


if __name__ == "__main__":
    main()
