"""Diagnostic conversion of the tree-control reconstruction; no inferred bark mask."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate import image


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("out", type=Path)
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    for glb in sorted(args.source.glob("*.glb")):
        started = time.perf_counter()
        genus = glb.stem
        name = f"Kudzu{genus}15trellis"
        out = args.out / name
        prior = out / "receipt.json"
        if (
            prior.exists()
            and json.loads(prior.read_text())["source_sha256"]
            == hashlib.sha256(glb.read_bytes()).hexdigest()
        ):
            continue
        out.mkdir(parents=True, exist_ok=False)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(glb))
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        if len(meshes) != 1:
            raise ValueError(f"{genus}: expected one textured mesh")
        ob = meshes[0]
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        low = Vector([min(v.co[i] for v in ob.data.vertices) for i in range(3)])
        high = Vector([max(v.co[i] for v in ob.data.vertices) for i in range(3)])
        center = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
        scale = 15 / (high.z - low.z)
        for vertex in ob.data.vertices:
            vertex.co = (vertex.co - center) * scale
        ob.data.calc_loop_triangles()
        triangles = len(ob.data.loop_triangles)
        if triangles > 1500:
            raise ValueError(f"{genus}: generated budget overshoot: {triangles}")
        bsdf = next(
            n
            for n in ob.data.materials[0].node_tree.nodes
            if n.type == "BSDF_PRINCIPLED"
        )
        tex = bsdf.inputs["Base Color"].links[0].from_node.image
        tex.scale(512, 512)
        pixels = np.empty(512 * 512 * 4, dtype=np.float32)
        tex.pixels.foreach_get(pixels)
        pixels = pixels.reshape(512, 512, 4)
        pixels[..., :3] = np.minimum(pixels[..., :3], 140 / 255)
        image("diffuse", pixels, 512, out / f"{name}_d.png")
        for channel, value in (("a", 1), ("c", 0), ("n", (0.5, 0.5, 1))):
            data = np.ones_like(pixels)
            data[..., :3] = value
            image(channel, data, 512, out / f"{name}_{channel}.png")
        ob.name = name
        bpy.ops.export_scene.fbx(
            filepath=str(out / f"{name}.fbx"),
            use_selection=True,
            object_types={"MESH"},
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_ALL",
            bake_space_transform=True,
            axis_forward="-Z",
            axis_up="Y",
        )
        size = [
            max(v.co[i] for v in ob.data.vertices)
            - min(v.co[i] for v in ob.data.vertices)
            for i in range(3)
        ]
        receipt = {
            "name": name,
            "genus": genus,
            "route": "trellis",
            "nominal_height_m": 15,
            "main_triangles": triangles,
            "size_xyz_z_up_m": size,
            "conversion_seconds": time.perf_counter() - started,
            "semantic_limit": "All-leaf mask: no bark segmentation. Diagnostic, not snow-ready.",
            "alpha_policy": "Opaque mesh; no invented card alpha. Topology must carry gaps.",
            "source_sha256": hashlib.sha256(glb.read_bytes()).hexdigest(),
            "files": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in out.iterdir()
            },
        }
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
