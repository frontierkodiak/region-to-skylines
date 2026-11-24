"""Budget-first parametric tree trial; run with Blender, not system Python."""

import argparse
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector


PROFILES = {
    "Gleditsia": {
        "width": 0.83,
        "base": 0.55,
        "depth": 0.34,
        "cards": 155,
        "atlas_leaves": 480,
        "green": (0.24, 0.33, 0.12),
    },
    "Tilia": {
        "width": 0.62,
        "base": 0.29,
        "depth": 0.68,
        "cards": 210,
        "atlas_leaves": 65,
        "green": (0.17, 0.29, 0.10),
    },
    "Ulmus": {
        "width": 0.87,
        "base": 0.47,
        "depth": 0.48,
        "cards": 180,
        "atlas_leaves": 65,
        "green": (0.20, 0.31, 0.12),
    },
}


def image(name, pixels, size, path):
    im = bpy.data.images.new(name, width=size, height=size, alpha=True)
    im.pixels.foreach_set(pixels.ravel())
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()
    return im


def atlas(genus, out, name, seed):
    """Rasterise a procedural twig/leaf cluster and a bark strip to one atlas."""
    import numpy as np

    n = 512
    rng = random.Random(seed)
    yy, xx = np.mgrid[0:n, 0:n] / n
    rgb = np.zeros((n, n, 4), dtype=np.float32)
    rgb[..., :3] = PROFILES[genus]["green"]
    rgb[..., 3] = 1
    alpha = np.zeros((n, n), dtype=np.float32)
    bark = xx > 0.80
    noise = np.random.default_rng(seed).uniform(-0.025, 0.025, (n, n))
    rgb[bark, :3] = np.clip(np.array([0.24, 0.19, 0.14]) + noise[bark, None], 0, 0.54)
    alpha[bark] = 1
    # Cluster density must survive alpha-test minification, not only the close view.
    count = PROFILES[genus]["atlas_leaves"]
    for k in range(count):
        cx, cy = rng.uniform(0.06, 0.74), rng.uniform(0.08, 0.92)
        if ((cx - 0.4) / 0.37) ** 2 + ((cy - 0.5) / 0.47) ** 2 > 1:
            continue
        angle = rng.uniform(-math.pi, math.pi)
        dx, dy = xx - cx, yy - cy
        u, v = (
            dx * math.cos(angle) + dy * math.sin(angle),
            -dx * math.sin(angle) + dy * math.cos(angle),
        )
        length = (
            rng.uniform(0.036, 0.075)
            if genus == "Gleditsia"
            else rng.uniform(0.060, 0.115)
        )
        width = length * (0.35 if genus == "Gleditsia" else 0.65)
        leaf = (u / length) ** 2 + (v / width) ** 2 < 1
        alpha[leaf] = 1
        shade = rng.uniform(0.70, 1.28)
        rgb[leaf, :3] = np.clip(
            np.array(PROFILES[genus]["green"]) * shade + noise[leaf, None], 0, 0.54
        )
        vein = leaf & (abs(v) < 0.0015)
        rgb[vein, :3] *= 0.77
    maps = {}
    maps["d"] = image("diffuse", rgb, n, out / f"{name}_d.png")
    for suffix, channel in (("a", alpha), ("c", bark.astype(float))):
        p = np.ones((n, n, 4), dtype=np.float32)
        p[..., :3] = channel[..., None]
        maps[suffix] = image(suffix, p, n, out / f"{name}_{suffix}.png")
    flat = np.ones_like(rgb)
    flat[..., :3] = (0.5, 0.5, 1)
    maps["n"] = image("normal", flat, n, out / f"{name}_n.png")
    return maps


def mesh_object(name, vertices, faces, uvs):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    layer = mesh.uv_layers.new()
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            layer.data[loop_index].uv = uvs[mesh.loops[loop_index].vertex_index]
    return ob


def skeleton(height, genus, seed, route):
    rng = random.Random(seed)
    p = PROFILES[genus]
    if route == "sapling":
        result = bpy.ops.curve.tree_add(
            preset="small_maple",
            preset_pending=False,
            do_update=True,
            seed=seed,
            scale=height,
            scaleV=0,
            levels=2,
            branches=(0, 12, 0, 0),
            showLeaves=False,
            curveRes=(5, 3, 1, 1),
            bevel=True,
            bevelRes=0,
            makeMesh=True,
        )
        if result != {"FINISHED"}:
            raise RuntimeError(f"Sapling failed: {result}")
        objects = [
            o
            for o in bpy.context.scene.objects
            if o.type == "MESH" and not o.hide_render
        ]
        for ob in objects:
            layer = ob.data.uv_layers.active or ob.data.uv_layers.new()
            for li, loop in enumerate(ob.data.loops):
                co = ob.data.vertices[loop.vertex_index].co
                layer.data[li].uv = (
                    0.82 + 0.16 * (math.atan2(co.y, co.x) / math.tau + 0.5),
                    co.z / height,
                )
        return objects
    if route == "sand3d":
        import sand3d as s3d

        s3d.units("m")
        with s3d.facets(5, smooth=True):
            axes = s3d.branches(
                height * 0.75,
                height * 0.035,
                levels=2,
                children=3,
                angle=55 if genus != "Tilia" else 42,
                length_ratio=0.55,
                diameter_ratio=0.46,
                tip_ratio=0.16,
                jitter=0.18,
                seed=seed,
            )
            for axis in axes:
                s3d.wire("limb", axis.path, axis.d)
        objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        for ob in objects:
            layer = ob.data.uv_layers.active or ob.data.uv_layers.new()
            for li, loop in enumerate(ob.data.loops):
                co = ob.data.vertices[loop.vertex_index].co
                layer.data[li].uv = (
                    0.83 + 0.15 * (math.atan2(co.y, co.x) / (2 * math.pi) + 0.5),
                    co.z / height,
                )
        return objects
    vertices, faces, uvs = [], [], []

    def limb(a, b, r1, r2):
        axis = (Vector(b) - Vector(a)).normalized()
        u = axis.cross(Vector((0, 1, 0))).normalized()
        v = axis.cross(u)
        start = len(vertices)
        for point, radius in ((a, r1), (b, r2)):
            for i in range(6):
                t = i * math.tau / 6
                vertices.append(
                    Vector(point) + radius * (u * math.cos(t) + v * math.sin(t))
                )
                uvs.append((0.82 + 0.17 * i / 5, point[2] / height))
        for i in range(6):
            j = (i + 1) % 6
            faces.append((start + i, start + j, start + 6 + j, start + 6 + i))
        faces.extend(
            (
                tuple(start + i for i in reversed(range(6))),
                tuple(start + 6 + i for i in range(6)),
            )
        )

    fork = height * p["base"]
    limb((0, 0, 0), (0.04 * height, 0, height * 0.82), height * 0.023, height * 0.004)
    for k in range(12):
        t = k * 2.39996
        z = fork + rng.random() * height * p["depth"] * 0.65
        reach = height * p["width"] * 0.40 * rng.uniform(0.65, 1)
        end = (
            reach * math.cos(t),
            reach * math.sin(t),
            min(height * 0.94, z + height * 0.16),
        )
        limb((0.02 * height, 0, z - height * 0.12), end, height * 0.012, height * 0.002)
    return [mesh_object("branches", vertices, faces, uvs)]


def foliage(height, genus, seed):
    p, rng = PROFILES[genus], random.Random(seed + 77)
    vertices, faces, uvs = [], [], []
    for k in range(p["cards"]):
        # Even volume sampling, with a separate species-specific crown envelope.
        zt = rng.uniform(-1, 1)
        radial = math.sqrt(1 - zt * zt) * rng.random() ** 0.4
        angle = k * 2.399963
        width = height * p["width"] / 2
        if genus == "Tilia":
            radial *= 1 - 0.22 * zt
        center = Vector(
            (
                width * radial * math.cos(angle),
                width * radial * math.sin(angle),
                height * (p["base"] + p["depth"] * (0.5 + 0.47 * zt)),
            )
        )
        span = height * rng.uniform(0.10, 0.17)
        u = (
            Vector(
                (math.cos(angle), math.sin(angle), rng.uniform(-0.3, 0.3))
            ).normalized()
            * span
        )
        v = (
            Vector((-math.sin(angle) * 0.3, math.cos(angle) * 0.3, 1)).normalized()
            * span
        )
        start = len(vertices)
        vertices.extend(
            (center - u - v, center + u - v, center + u + v, center - u + v)
        )
        uvs.extend(((0, 0), (0.79, 0), (0.79, 1), (0, 1)))
        faces.append(tuple(start + i for i in range(4)))
    return mesh_object("foliage", vertices, faces, uvs)


def build(out, genus, height, seed, route):
    started = time.perf_counter()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    name = f"Kudzu{genus}{int(height)}{route}"
    target = out / name
    target.mkdir(parents=True, exist_ok=False)
    maps = atlas(genus, target, name, seed)
    objects = skeleton(height, genus, seed, route) + [foliage(height, genus, seed)]
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    tree = bpy.context.object
    tree.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # Crown cards may overshoot the nominal envelope; normalise the actual vertices.
    zmin = min(v.co.z for v in tree.data.vertices)
    zmax = max(v.co.z for v in tree.data.vertices)
    factor = height / (zmax - zmin)
    for vertex in tree.data.vertices:
        vertex.co.z -= zmin
        vertex.co *= factor
    tree.data.update()
    tree.data.calc_loop_triangles()
    triangles = len(tree.data.loop_triangles)
    if triangles > 1500:
        raise ValueError(
            f"{name}: {triangles} triangles exceeds 1500; do not silently decimate"
        )
    # All import inputs: a single object, ground pivot, native metre orientation.
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
    material = bpy.data.materials.new("preview")
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    tex = material.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = maps["d"]
    mask = material.node_tree.nodes.new("ShaderNodeTexImage")
    mask.image = maps["a"]
    material.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    material.node_tree.links.new(mask.outputs["Color"], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.9
    tree.data.materials.clear()
    tree.data.materials.append(material)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 16
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.world = bpy.data.worlds.new("world")
    scene.world.color = (0.4, 0.4, 0.4)
    light = bpy.data.lights.new("key", "AREA")
    light.energy, light.shape, light.size = 2500, "DISK", height
    lamp = bpy.data.objects.new("key", light)
    scene.collection.objects.link(lamp)
    lamp.location = (height, -height, height * 1.5)
    lamp.rotation_euler = (
        (Vector((0, 0, height / 2)) - lamp.location).to_track_quat("-Z", "Y").to_euler()
    )
    camera = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    scene.collection.objects.link(camera)
    camera.location = (height * 1.4, -height * 2, height * 0.9)
    camera.rotation_euler = (
        (Vector((0, 0, height / 2)) - camera.location)
        .to_track_quat("-Z", "Y")
        .to_euler()
    )
    camera.data.type, camera.data.ortho_scale = "ORTHO", height * 1.15
    scene.camera = camera
    scene.render.filepath = str(target / "billboard-preview.png")
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target / f"{name}.blend"))
    bounds = [
        max(v.co[i] for v in tree.data.vertices)
        - min(v.co[i] for v in tree.data.vertices)
        for i in range(3)
    ]
    receipt = {
        "name": name,
        "genus": genus,
        "nominal_height_m": height,
        "seed": seed,
        "atlas_leaves": PROFILES[genus]["atlas_leaves"],
        "route": route,
        "main_triangles": triangles,
        "size_xyz_z_up_m": bounds,
        "scale_at_import": 100,
        "lod": "native CS1 camera-updated billboard; not a building LOD mesh",
        "textures": "512px diffuse/alpha/leaf-bark mask; deliberately flat normals",
        "generation_and_preview_seconds": time.perf_counter() - started,
        "blender": bpy.app.version_string,
        "files": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in target.iterdir()
            if p.is_file()
        },
    }
    (target / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: v for k, v in receipt.items() if k != "files"}), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--sand3d-path", type=Path)
    p.add_argument("--sapling-path", type=Path)
    p.add_argument(
        "--route", choices=("sand3d", "blender", "sapling"), default="sand3d"
    )
    p.add_argument("--genus", choices=list(PROFILES), default="Gleditsia")
    p.add_argument("--heights", type=float, nargs="+", default=[9, 15, 22])
    a = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if a.route == "sapling" and not a.sapling_path:
        p.error("--route sapling requires --sapling-path")
    if any(not math.isfinite(h) or h <= 0 or h != int(h) for h in a.heights):
        p.error("--heights must be positive whole metres (used in package names)")
    if len(set(a.heights)) != len(a.heights):
        p.error("--heights must be unique")
    if a.sand3d_path:
        sys.path.insert(0, str(a.sand3d_path / "src"))
    if a.route == "sapling":
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "bl_ext.pl1328.sapling_trial", a.sapling_path / "source" / "__init__.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        sys.modules["sapling_trial"] = module
        spec.loader.exec_module(module)
        module.register()
    for i, h in enumerate(a.heights):
        build(a.out, a.genus, h, 1328 + i, a.route)


if __name__ == "__main__":
    main()
