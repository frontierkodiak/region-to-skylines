"""Run inside Blender: build the baked meshes and export one FBX per object.

    blender -b --factory-startup -P blender_fbx.py -- MESH_JSON OUT_DIR [--preview]

Each object is exported alone, with Blender's default FBX axes (forward -Z, up Y), "Apply
Transform" (bake_space_transform) and FBX_SCALE_ALL, so the file holds the mesh in metres with
an identity node transform: CS1's importer reads mesh data and resets the node's scale.
Then each FBX is imported back and its bounds compared with the source, so a scale or axis
slip fails here rather than in the game.
"""

import json
import math
import pathlib
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1 :]
mesh_json, out_dir = pathlib.Path(argv[0]), pathlib.Path(argv[1])
preview = "--preview" in argv
spec = json.loads(mesh_json.read_text())


def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for item in list(block):
            block.remove(item)


def build(name, triangles, uvs):
    verts, faces, loops_uv = [], [], []
    for t, uv in zip(triangles, uvs):
        base = len(verts)
        verts.extend(t)
        faces.append((base, base + 1, base + 2))
        loops_uv.extend(uv)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    layer = me.uv_layers.new(name="UVMap")
    for i, loop in enumerate(me.loops):
        layer.data[i].uv = loops_uv[loop.index]
    for poly in me.polygons:
        poly.use_smooth = False
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    # Merge the per-face vertices only where position and UV agree: keeps flat shading and
    # the atlas cells, halves the vertex count.
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=1e-4, use_unselected=False, use_sharp_edge_from_normals=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    return ob


def bounds(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return lo, hi


def material(name, tex):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = bpy.data.images.load(str(tex))
    node.interpolation = "Closest"
    mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    return mat


report = {"objects": {}}
for name, obj in spec["objects"].items():
    clear()
    ob = build(name, obj["triangles"], obj["uvs"])
    want = bounds([ob])
    path = out_dir / f"{name}.fbx"
    ob.select_set(True)
    bpy.ops.export_scene.fbx(
        filepath=str(path),
        use_selection=True,
        object_types={"MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z",
        axis_up="Y",
        bake_space_transform=True,
        mesh_smooth_type="FACE",
        use_mesh_modifiers=True,
        add_leaf_bones=False,
        bake_anim=False,
        path_mode="STRIP",
        embed_textures=False,
    )
    clear()
    bpy.ops.import_scene.fbx(filepath=str(path))
    back = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    got = bounds(back)
    err = max(abs(a - b) for a, b in zip(want[0] + want[1], got[0] + got[1]))
    report["objects"][name] = {
        "fbx": path.name,
        "triangles": sum(len(o.data.polygons) for o in back),
        "vertices": sum(len(o.data.vertices) for o in back),
        "bounds_m": {"min": [round(v, 3) for v in want[0]], "max": [round(v, 3) for v in want[1]]},
        "reimport_error_m": round(err, 5),
        "objects_in_file": len(back),
    }
    if err > 1e-3 or len(back) != 1:
        raise SystemExit(f"{path.name}: re-import differs ({err:.4f} m, {len(back)} objects)")

if preview:
    # CS1-like look-down views: the main mesh (left) beside its LOD (right).
    clear()
    name = spec["name"]
    ob = build(name, spec["objects"][name]["triangles"], spec["objects"][name]["uvs"])
    ob.data.materials.append(material(name, out_dir / f"{name}_d.png"))
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 32
    scene.render.resolution_x, scene.render.resolution_y = 960, 640
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("w")
    world.color = (0.55, 0.62, 0.7)
    scene.world = world
    bpy.ops.mesh.primitive_plane_add(size=spec["lot"][0] * 16 + 24, location=(spec["lot"][0] * 4 + 2, 0, 0))
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 4
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    scene.collection.objects.link(sun)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    lod = build(f"{name}_lod", spec["objects"][f"{name}_lod"]["triangles"], spec["objects"][f"{name}_lod"]["uvs"])
    lod.data.materials.append(material(f"{name}_lod", out_dir / f"{name}_lod_d.png"))
    lod.location.x = spec["lot"][0] * 8 + 4
    for label, dist, pitch, yaw in (("front", 48, 35, -20), ("back", 70, 55, 200)):
        p, y = math.radians(pitch), math.radians(yaw)
        target = Vector((lod.location.x / 2, 0, 0))
        cam.location = target + dist * Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
        cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = 50
        scene.render.filepath = str(out_dir / f"preview-{label}.png")
        bpy.ops.render.render(write_still=True)
        report.setdefault("previews", []).append(f"preview-{label}.png")

(out_dir / "fbx-receipt.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
