"""Re-import the exported FBX bytes: budget, units, ground pivot, UVs and maps."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    rows = []
    for path in sorted(args.inputs.glob("*/receipt.json")):
        receipt = json.loads(path.read_text())
        name = receipt["name"]
        bpy.ops.wm.read_factory_settings(use_empty=True)
        fbx = path.parent / f"{name}.fbx"
        if hashlib.sha256(fbx.read_bytes()).hexdigest() != receipt["files"][fbx.name]:
            raise ValueError(f"{name}: changed FBX bytes")
        bpy.ops.import_scene.fbx(filepath=str(fbx))
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        if len(meshes) != 1:
            raise ValueError(f"{name}: expected one mesh, got {len(meshes)}")
        ob = meshes[0]
        ob.data.calc_loop_triangles()
        triangles = len(ob.data.loop_triangles)
        degenerate = sum(
            (ob.data.vertices[t.vertices[1]].co - ob.data.vertices[t.vertices[0]].co)
            .cross(
                ob.data.vertices[t.vertices[2]].co - ob.data.vertices[t.vertices[0]].co
            )
            .length_squared
            < 1e-16
            for t in ob.data.loop_triangles
        )
        if not 0 < triangles <= 1500 or triangles != receipt["main_triangles"]:
            raise ValueError(f"{name}: triangle budget/roundtrip: {triangles}")
        points = [ob.matrix_world @ v.co for v in ob.data.vertices]
        low = [min(p[i] for p in points) for i in range(3)]
        high = [max(p[i] for p in points) for i in range(3)]
        size = [b - a for a, b in zip(low, high)]
        error = max(abs(a - b) for a, b in zip(size, receipt["size_xyz_z_up_m"]))
        if error > 0.002 or abs(low[2]) > 0.002 or ob.location.length > 0.002:
            raise ValueError(f"{name}: unit/pivot error: {error}, bounds {low}/{high}")
        if len(ob.data.vertices) >= 65536:
            raise ValueError(f"{name}: native vertex limit")
        if not ob.data.uv_layers.active:
            raise ValueError(f"{name}: missing UVs")
        if not all(
            math.isfinite(v) for loop in ob.data.uv_layers.active.data for v in loop.uv
        ):
            raise ValueError(f"{name}: nonfinite UVs")
        # CS1 permits main-tree UV tiling. U must still select this atlas's bark/leaf columns.
        if not all(
            -0.0001 <= loop.uv.x <= 1.0001 for loop in ob.data.uv_layers.active.data
        ):
            raise ValueError(f"{name}: U outside this atlas's columns")
        for channel in ("d", "a", "c", "n"):
            texture = path.parent / f"{name}_{channel}.png"
            im = bpy.data.images.load(str(texture))
            if tuple(im.size) != (512, 512):
                raise ValueError(f"{name}: wrong {channel} resolution")
            if (
                hashlib.sha256(texture.read_bytes()).hexdigest()
                != receipt["files"][texture.name]
            ):
                raise ValueError(f"{name}: changed {channel} map")
        rows.append(
            {
                "name": name,
                "triangles": triangles,
                "zero_area_triangles": degenerate,
                "roundtrip_error_m": error,
                "fbx_sha256": hashlib.sha256(fbx.read_bytes()).hexdigest(),
            }
        )
    if not rows:
        raise ValueError("No assets verified")
    args.report.write_text(
        json.dumps({"passed": len(rows), "assets": rows}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
