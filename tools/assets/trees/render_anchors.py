"""Offline anchor views. Extracted pixels/meshes remain private; renders are evidence."""

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
import numpy as np


def render(directory, out):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    data = json.loads((directory / "geometry.json").read_text())
    points = [(x, -z, y) for x, y, z in data["vertices"]]
    normals = [Vector((x, -z, y)) for x, y, z in data["normals"]]
    faces = data["faces"]
    if normals:
        agreement = sum(
            (Vector(points[b]) - Vector(points[a]))
            .cross(Vector(points[c]) - Vector(points[a]))
            .dot(normals[a])
            for a, b, c in faces
        )
        if agreement < 0:
            faces = [list(reversed(f)) for f in faces]
    mesh = bpy.data.meshes.new("anchor")
    mesh.from_pydata(points, [], faces)
    mesh.update()
    tree = bpy.data.objects.new("anchor", mesh)
    bpy.context.collection.objects.link(tree)
    uv = mesh.uv_layers.new()
    for loop in mesh.loops:
        u, v = data["uv"][loop.vertex_index]
        uv.data[loop.index].uv = (u, 1 - v)
    if normals:
        for p in mesh.polygons:
            p.use_smooth = True
        mesh.normals_split_custom_set(
            [normals[loop.vertex_index] for loop in mesh.loops]
        )
    mat = bpy.data.materials.new("CS1-map-preview")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    shader.inputs["Roughness"].default_value = 0.9
    shader.inputs["Specular IOR Level"].default_value = 0
    diffuse = nodes.new("ShaderNodeTexImage")
    diffuse.image = bpy.data.images.load(str(directory / "_MainTex.png"))
    diffuse.image.colorspace_settings.name = "Non-Color"
    links.new(diffuse.outputs["Color"], shader.inputs["Base Color"])
    packed = nodes.new("ShaderNodeTexImage")
    packed.image = bpy.data.images.load(str(directory / "_XYCAMap.png"))
    packed.image.colorspace_settings.name = "Non-Color"
    cutoff = nodes.new("ShaderNodeMath")
    # The serialized XYCA alpha stores transparency, inverse of the source _a map.
    cutoff.operation = "LESS_THAN"
    cutoff.inputs[1].default_value = 0.5
    links.new(packed.outputs["Alpha"], cutoff.inputs[0])
    links.new(cutoff.outputs[0], shader.inputs["Alpha"])
    pixels = np.array(packed.image.pixels[:], dtype=np.float32).reshape(
        packed.image.size[1], packed.image.size[0], 4
    )
    xy = pixels[..., :2] * 2 - 1
    pixels[..., 1] = 1 - pixels[..., 1]
    pixels[..., 2] = np.sqrt(np.maximum(0, 1 - np.sum(xy * xy, axis=2))) / 2 + 0.5
    pixels[..., 3] = 1
    normal_im = bpy.data.images.new(
        "unpacked-XY", width=pixels.shape[1], height=pixels.shape[0], is_data=True
    )
    normal_im.pixels.foreach_set(pixels.ravel())
    normal_tex = nodes.new("ShaderNodeTexImage")
    normal_tex.image = normal_im
    normal = nodes.new("ShaderNodeNormalMap")
    links.new(normal_tex.outputs["Color"], normal.inputs["Color"])
    links.new(normal.outputs["Normal"], shader.inputs["Normal"])
    tree.data.materials.append(mat)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 16
    scene.cycles.transparent_max_bounces = 32
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = 0
    scene.world = bpy.data.worlds.new("world")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (
        0.18,
        0.18,
        0.18,
        1,
    )
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    light = bpy.data.lights.new("key", "SUN")
    light.energy = 2
    lamp = bpy.data.objects.new("key", light)
    scene.collection.objects.link(lamp)
    lamp.rotation_euler = (math.radians(30), math.radians(-25), math.radians(-30))
    camera = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    scene.collection.objects.link(camera)
    camera.data.sensor_fit = "VERTICAL"
    camera.data.sensor_height = 24
    camera.data.lens = 24 / (2 * math.tan(math.radians(45) / 2))
    scene.camera = camera
    target = Vector((0, 0, 8))
    out.mkdir(parents=True, exist_ok=False)
    for view, distance, pitch in [
        ("close", 52, 20),
        ("gameplay", 140, 40),
        ("billboard", 550, 40),
    ]:
        angle = math.radians(pitch)
        camera.location = target + Vector(
            (0, distance * math.cos(angle), distance * math.sin(angle))
        )
        camera.rotation_euler = (
            (target - camera.location).to_track_quat("-Z", "Y").to_euler()
        )
        scene.render.filepath = str(out / (view + ".png"))
        bpy.ops.render.render(write_still=True)
    (out / "receipt.json").write_text(
        json.dumps(
            {
                "prefab": data["prefab"],
                "crp_sha256": data["crp_sha256"],
                "triangles": len(faces),
                "field_of_view_vertical": 45,
                "views": {"close": 52, "gameplay": 140, "billboard": 550},
                "source": "offline mesh; native billboard shader is not reproduced",
                "exposure": 0,
                "blender": bpy.app.version_string,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inputs", type=Path)
    p.add_argument("out", type=Path)
    a = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    for d in sorted(a.inputs.iterdir()):
        if (d / "geometry.json").exists():
            render(d, a.out / d.name)
