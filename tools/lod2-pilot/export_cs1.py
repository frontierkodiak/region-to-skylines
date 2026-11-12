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

# The game's lighting brightens and saturates. Measured on blade (PL-909): after the bake's
# x0.58, a texture value comes out about 2.5 times brighter, and its red-minus-blue spread
# over three times wider (brick texture 72,55,49 showed as 182,119,96, salmon). These are
# chosen backwards from the colour wanted on screen.
WALL_HEX = {"brick": "#67564c", "stone": "#7c7872", "siding": "#8d8881"}
GLASS_HEX = "#2f3b56"
STOREY = 3.0  # m between window rows
WINDOW = (1.0, 1.4)  # m wide, tall
SILL = 0.9  # m above each floor line
BAY = 2.6  # m between window centres along a wall
EDGE = 0.6  # m kept clear at wall ends and under the eave


def windows(tri: np.ndarray, kinds: list[str]) -> np.ndarray:
    """Plain window panes on the walls, so the game has glass to light at night.

    Wall triangles are grouped by the vertical plane they lie in. Each plane gets rows of
    panes at fixed storey heights from the ground and a fixed spacing along the wall,
    wherever a whole pane with its margin fits inside the wall. Panes sit 3 cm outside the
    wall and wind like it. Scene triangles wind clockwise seen from outside, so a wall's
    right-hand normal points into the building. This is a regular fill, not a reading of the real facade.
    """
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union

    walls = tri[np.array(kinds) == "wall"]
    nrm = np.cross(walls[:, 1] - walls[:, 0], walls[:, 2] - walls[:, 0])
    ln = np.linalg.norm(nrm, axis=1)
    keep = (ln > 1e-6) & (np.abs(nrm[:, 1]) < 0.05 * ln)
    walls, nrm = walls[keep], nrm[keep] / ln[keep, None]
    groups: dict[tuple, list[int]] = {}
    for i, (t, n) in enumerate(zip(walls, nrm)):
        ang = round(float(np.degrees(np.arctan2(n[2], n[0]))) / 3)
        off = round(float(t[0] @ n) / 0.1)
        groups.setdefault((ang, off), []).append(i)
    out = []
    for idx in groups.values():
        n = nrm[idx].mean(axis=0)
        n[1] = 0
        n /= np.linalg.norm(n)
        along = np.array([-n[2], 0.0, n[0]])
        origin = walls[idx[0]][0]
        face = unary_union([Polygon([((v - origin) @ along, v[1]) for v in walls[i]]).buffer(1e-4) for i in idx])
        if face.is_empty:
            continue
        a0, _, a1, top = face.bounds
        count = int((a1 - a0 - 2 * EDGE - WINDOW[0]) // BAY) + 1
        if count < 1:
            continue
        start = (a0 + a1) / 2 - (count - 1) * BAY / 2
        floor = 0.0
        while floor + SILL + WINDOW[1] + EDGE <= top:
            for k in range(count):
                c, y0 = start + k * BAY, floor + SILL
                pane = box(c - WINDOW[0] / 2, y0, c + WINDOW[0] / 2, y0 + WINDOW[1])
                if not face.contains(pane.buffer(EDGE * 0.5)):
                    continue
                q = [origin + along * a + np.array([0, y - origin[1], 0]) - n * 0.03
                     for a, y in ((c - WINDOW[0] / 2, y0), (c + WINDOW[0] / 2, y0), (c + WINDOW[0] / 2, y0 + WINDOW[1]), (c - WINDOW[0] / 2, y0 + WINDOW[1]))]
                for t in ([q[0], q[1], q[2]], [q[0], q[2], q[3]]):
                    t = np.array(t)
                    if np.cross(t[1] - t[0], t[2] - t[0]) @ n < 0:
                        t = t[::-1]
                    out.append(t)
            floor += STOREY
    return np.array(out).reshape(-1, 3, 3)


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
        t[..., 1] = np.maximum(t[..., 1], 0.0)
        panes = windows(t, arm["kind"])
        kinds = list(arm["kind"]) + ["glass"] * len(panes)
        t = np.vstack([t, panes]) if len(panes) else t
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
        ramp = np.repeat([{"roof": 1, "glass": 2}.get(k, 0) for k in kinds], 3)
        (out / f"{name}.kit.json").write_text(json.dumps({
            "source": {"pilot": "PL-909", "building": bid, "arm": "measured LoD2 (Roofer 1.0.0, 2017 USGS lidar)"},
            "frame": "kit-local: u right along the frontage, y up, w back from the street; metres",
            "triangles": len(p), "position": np.round(p, 4).reshape(-1).tolist(), "ramp": ramp.tolist(),
            "ramps": {"0": {"name": wall, "hex": WALL_HEX[wall]}, "1": {"name": "roof", "hex": "#55585e"},
                      "2": {"name": "glass", "hex": GLASS_HEX}},
            "windows": len(panes) // 2,
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
