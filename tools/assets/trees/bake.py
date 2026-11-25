"""Bake a high-detail leaf-cluster source onto retained Sand3D card geometry."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time

import bpy
from mathutils import Vector
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate import PROFILES, image, mesh_object


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = 0.9
    return mat


def cluster(genus, seed, program):
    """Curved, individually modelled leaves; the source is not a flat colour mask."""
    rng = random.Random(seed)
    vertices, faces, uvs = [], [], []
    count = int(program.get("leaves", 128 if genus == "Gleditsia" else 64))
    for i in range(count):
        angle = rng.uniform(-math.pi, math.pi)
        # Fill the same atlas footprint as A; preserve transparent cluster edges.
        r, t = math.sqrt(rng.random()), rng.uniform(0, math.tau)
        center = Vector(
            (
                0.395 + 0.36 * r * math.cos(t),
                0.5 + 0.46 * r * math.sin(t),
                rng.uniform(-0.025, 0.025),
            )
        )
        length = program.get("leaf_scale", 1) * (
            rng.uniform(0.065, 0.105)
            if genus == "Gleditsia"
            else rng.uniform(0.10, 0.16)
        )
        width = length * program.get(
            "width_ratio", 0.32 if genus == "Gleditsia" else 0.65
        )
        u, v = (
            Vector((math.cos(angle), math.sin(angle), 0)),
            Vector((-math.sin(angle), math.cos(angle), 0)),
        )
        start = len(vertices)
        vertices.append(center + Vector((0, 0, program.get("bulge", 0.024))))
        uvs.append((0, 0))
        segments = 12
        for k in range(segments):
            theta = math.tau * k / segments
            shape = 1 + (0.13 * math.cos(theta) if genus == "Tilia" else 0)
            point = (
                center
                + u * (length * math.cos(theta))
                + v * (width * math.sin(theta) * shape)
            )
            point.z += 0.007 * math.sin(theta * 3 + i)
            vertices.append(point)
            uvs.append((0, 0))
        for k in range(segments):
            faces.append((start, start + 1 + k, start + 1 + (k + 1) % segments))
    ob = mesh_object("high-detail-leaf-cluster", vertices, faces, uvs)
    for i in range(6):
        color = (
            np.array(PROFILES[genus]["green"])
            * (0.72 + i * 0.08)
            * program.get("color_gain", 1)
        )
        ob.data.materials.append(material(f"leaf-{i}", color))
    for poly in ob.data.polygons:
        poly.material_index = (poly.index // 12) % 6
        poly.use_smooth = True
    return ob


def bake_atlas(target, name, genus, seed, program):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = cluster(genus, seed, program)
    receiver = mesh_object(
        "atlas-receiver",
        [(0, 0, -0.15), (1, 0, -0.15), (1, 1, -0.15), (0, 1, -0.15)],
        [(0, 1, 2, 3)],
        [(0, 0), (1, 0), (1, 1), (0, 1)],
    )
    mat = material("bake-target", (0, 0, 0))
    receiver.data.materials.append(mat)
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    mat.node_tree.nodes.active = node
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 8
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.cage_extrusion = 0.35
    scene.render.bake.max_ray_distance = 0.6
    scene.render.bake.margin = 2
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    maps = {}
    for suffix, kind in (("d", "DIFFUSE"), ("n", "NORMAL"), ("a", "EMIT")):
        if suffix == "a":
            for source_mat in source.data.materials:
                nodes = source_mat.node_tree.nodes
                emission = nodes.new("ShaderNodeEmission")
                emission.inputs["Color"].default_value = (1, 1, 1, 1)
                source_mat.node_tree.links.new(
                    emission.outputs[0], nodes.get("Material Output").inputs["Surface"]
                )
        im = bpy.data.images.new(
            suffix, width=512, height=512, alpha=True, is_data=suffix != "d"
        )
        node.image = im
        bpy.ops.object.select_all(action="DESELECT")
        source.select_set(True)
        receiver.select_set(True)
        bpy.context.view_layer.objects.active = receiver
        bpy.ops.object.bake(type=kind)
        pixels = np.array(im.pixels[:], dtype=np.float32).reshape(512, 512, 4)
        pixels[..., 3] = 1
        bark = np.arange(512)[None, :] / 512 > 0.80
        if suffix == "d":
            # Linear bake colour is saved with an explicit numerical ceiling.
            pixels[..., :3] = np.minimum(pixels[..., :3], 140 / 255)
            pixels[:, bark[0], :3] = (0.24, 0.19, 0.14)
        elif suffix == "a":
            pixels[:, bark[0], :3] = 1
        else:
            pixels[:, bark[0], :3] = (0.5, 0.5, 1)
        maps[suffix] = image(
            suffix + "-final", pixels, 512, target / f"{name}_{suffix}.png"
        )
    mask = np.ones((512, 512, 4), dtype=np.float32)
    mask[:, :, :3] = np.arange(512)[None, :, None] / 512 > 0.80
    maps["c"] = image("leaf-bark-mask", mask, 512, target / f"{name}_c.png")
    # Restore source colours before saving the reusable high-detail source.
    for mat in source.data.materials:
        mat.node_tree.links.new(
            mat.node_tree.nodes.get("Principled BSDF").outputs[0],
            mat.node_tree.nodes.get("Material Output").inputs["Surface"],
        )
    cluster_vertices = [v.co.copy() for v in source.data.vertices]
    cluster_faces = [tuple(p.vertices) for p in source.data.polygons]
    return maps, cluster_vertices, cluster_faces


def build(baseline, out, label, program):
    started = time.perf_counter()
    original = json.loads((baseline / "receipt.json").read_text())
    old_name, genus = original["name"], original["genus"]
    if original["route"] != "sand3d" or original["nominal_height_m"] != 15:
        raise ValueError("B requires a retained 15m Sand3D baseline")
    name = f"Kudzu{genus}15{label}"
    target = out / name
    target.mkdir(parents=True, exist_ok=False)
    maps, cluster_vertices, cluster_faces = bake_atlas(
        target, name, genus, original["seed"], program
    )
    bpy.ops.wm.open_mainfile(filepath=str(baseline / f"{old_name}.blend"))
    tree = bpy.data.objects[old_name]
    tree.name = name
    # The UV split identifies leaves without changing A's branch/card topology.
    normals = [loop.vector.copy() for loop in tree.data.corner_normals]
    center = Vector(
        (0, 0, 15 * (PROFILES[genus]["base"] + PROFILES[genus]["depth"] / 2))
    )
    radii = Vector(
        (
            original["size_xyz_z_up_m"][0] / 2,
            original["size_xyz_z_up_m"][1] / 2,
            15 * PROFILES[genus]["depth"] / 2,
        )
    )
    leaf_faces = []
    for poly in tree.data.polygons:
        if all(
            tree.data.uv_layers.active.data[i].uv.x < 0.8 for i in poly.loop_indices
        ):
            leaf_faces.append(poly)
            poly.use_smooth = True
            for li in poly.loop_indices:
                point = tree.data.vertices[tree.data.loops[li].vertex_index].co - center
                normal = Vector(
                    tuple(point[i] / max(radii[i] ** 2, 0.01) for i in range(3))
                )
                normal.z += 0.025
                strength = program.get("soft_normals", 1)
                normals[li] = (
                    normal.normalized() * strength + normals[li] * (1 - strength)
                ).normalized()
    tree.data.normals_split_custom_set(normals)
    # Real full-tree source assembled from the same cards and branch skeleton.
    source_vertices = [v.co.copy() for v in tree.data.vertices]
    source_faces = [
        tuple(p.vertices) for p in tree.data.polygons if p not in leaf_faces
    ]
    for poly in leaf_faces:
        a, b, c, d = [tree.data.vertices[i].co for i in poly.vertices]
        middle, u, v = (a + c) / 2, (b - a) / 2, (d - a) / 2
        normal = u.cross(v).normalized()
        offset = len(source_vertices)
        source_vertices.extend(
            middle + u * ((p.x / 0.79 - 0.5) * 2) + v * ((p.y - 0.5) * 2) + normal * p.z
            for p in cluster_vertices
        )
        source_faces.extend(tuple(offset + i for i in face) for face in cluster_faces)
    high = mesh_object(
        "full-detail-source",
        source_vertices,
        source_faces,
        [(0, 0)] * len(source_vertices),
    )
    high.data.calc_loop_triangles()
    source_triangles = len(high.data.loop_triangles)
    tree.hide_render = True
    high.data.materials.append(material("high-source-green", PROFILES[genus]["green"]))
    bpy.ops.wm.save_as_mainfile(filepath=str(target / "high-source.blend"))
    bpy.data.objects.remove(high, do_unlink=True)
    tree.hide_render = False
    bpy.ops.object.select_all(action="DESELECT")
    tree.select_set(True)
    bpy.context.view_layer.objects.active = tree
    bpy.ops.export_scene.fbx(
        filepath=str(target / f"{name}.fbx"),
        use_selection=True,
        object_types={"MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        bake_space_transform=True,
        axis_forward="-Z",
        axis_up="Y",
        use_mesh_modifiers=True,
    )
    mat = material("baked-preview", (1, 1, 1))
    shader = mat.node_tree.nodes.get("Principled BSDF")
    for suffix, socket in (("d", "Base Color"), ("a", "Alpha"), ("n", "Normal")):
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(target / f"{name}_{suffix}.png"))
        output = tex.outputs["Color"]
        if suffix == "n":
            tex.image.colorspace_settings.name = "Non-Color"
            normal = mat.node_tree.nodes.new("ShaderNodeNormalMap")
            mat.node_tree.links.new(output, normal.inputs["Color"])
            output = normal.outputs["Normal"]
        mat.node_tree.links.new(output, shader.inputs[socket])
    tree.data.materials.clear()
    tree.data.materials.append(mat)
    bpy.context.scene.render.filepath = str(target / "billboard-preview.png")
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target / f"{name}.blend"))
    receipt = {
        **original,
        "name": name,
        "route": label,
        "program": program,
        "bake_program_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_triangles": source_triangles,
        "baseline_receipt_sha256": hashlib.sha256(
            (baseline / "receipt.json").read_bytes()
        ).hexdigest(),
        "textures": "selected-to-active diffuse, alpha and tangent normals; semantic leaf/bark c mask",
        "canopy_normals": "ellipsoid gradient, bark unchanged",
        "generation_and_preview_seconds": time.perf_counter() - started,
    }
    receipt["files"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in target.iterdir()
        if p.is_file()
    }
    (target / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {
                "name": name,
                "source_triangles": source_triangles,
                "seconds": receipt["generation_and_preview_seconds"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baselines", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--label", default="bake", choices=("bake", "c1", "c2"))
    parser.add_argument("--program", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    programs = (
        json.loads(args.program.read_text())
        if args.program
        else {g: {} for g in PROFILES}
    )
    limits = {
        "leaves": (16, 500),
        "leaf_scale": (0.1, 2),
        "width_ratio": (0.1, 1),
        "bulge": (0.001, 0.04),
        "color_gain": (0.5, 2),
        "soft_normals": (0, 1),
    }
    for genus in PROFILES:
        program = programs[genus]
        if set(program) - limits.keys() or any(
            not isinstance(v, (int, float))
            or not math.isfinite(v)
            or not limits[k][0] <= v <= limits[k][1]
            for k, v in program.items()
        ):
            raise ValueError(f"Invalid program for {genus}")
        if "leaves" in program and int(program["leaves"]) != program["leaves"]:
            raise ValueError("Leaf count must be integral")
        build(args.baselines / f"Kudzu{genus}15sand3d", args.out, args.label, program)
