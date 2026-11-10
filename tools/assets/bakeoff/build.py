"""Blender batch: parametric A/C, normalized imported B, CS1 maps/LOD/FBX and matched renders."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import bpy
import bmesh
from mathutils import Matrix, Vector


TARGETS = {
    "bungalow": {"size": (10.5, 12.0, 7.0), "lot": (2, 3), "budget": 6000, "lod": 180},
    "storefront": {
        "size": (8.0, 15.0, 11.3),
        "lot": (2, 3),
        "budget": 8000,
        "lod": 180,
    },
    "apartment": {
        "size": (28.0, 10.0, 8.3),
        "lot": (4, 3),
        "budget": 12000,
        "lod": 240,
    },
}


def material(name, folder):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "SourceUV"
    for channel in ("d", "s", "c", "i"):
        tex = nodes.new("ShaderNodeTexImage")
        tex.name = channel
        tex.image = bpy.data.images.load(
            str(folder / f"{name}_{channel}.png"), check_existing=True
        )
        if channel != "d":
            tex.image.colorspace_settings.name = "Non-Color"
        mat.node_tree.links.new(uv.outputs["UV"], tex.inputs["Vector"])
    return mat


def piece(name, vertices, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    uv = mesh.uv_layers.new(name="SourceUV")
    period = {
        "siding": (1.5, 1.4),
        "brick": (1.6, 0.9),
        "roof": (2.0, 1.2),
        "stone": (1.5, 1.2),
    }.get(mat.name.split(".")[0], (1.0, 1.0))
    for poly in mesh.polygons:
        axis = max(range(3), key=lambda a: abs(poly.normal[a]))
        axes = (0, 1) if axis == 2 else ((0, 2) if axis == 1 else (1, 2))
        for loop in poly.loop_indices:
            co = mesh.vertices[mesh.loops[loop].vertex_index].co
            uv.data[loop].uv = (co[axes[0]] / period[0], co[axes[1]] / period[1])
    return obj


def box(name, center, size, mat):
    x, y, z = center
    a, b, c = (v / 2 for v in size)
    return piece(
        name,
        [
            (x - a, y - b, z - c),
            (x + a, y - b, z - c),
            (x + a, y + b, z - c),
            (x - a, y + b, z - c),
            (x - a, y - b, z + c),
            (x + a, y - b, z + c),
            (x + a, y + b, z + c),
            (x - a, y + b, z + c),
        ],
        [
            (0, 3, 2, 1),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
            (4, 5, 6, 7),
        ],
        mat,
    )


def gable(name, center, size, mat, ridge_along_y=True):
    x, y, z = center
    w, d, rise = size
    v = [
        (-w / 2, -d / 2, 0),
        (w / 2, -d / 2, 0),
        (0, -d / 2, rise),
        (-w / 2, d / 2, 0),
        (w / 2, d / 2, 0),
        (0, d / 2, rise),
    ]
    if not ridge_along_y:
        v = [(vy, vx, vz) for vx, vy, vz in v]
        faces = [(0, 1, 2), (5, 4, 3), (3, 4, 1, 0), (3, 0, 2, 5), (2, 1, 4, 5)]
    else:
        faces = [(2, 1, 0), (3, 4, 5), (0, 1, 4, 3), (5, 2, 0, 3), (5, 4, 1, 2)]
    return piece(name, [(vx + x, vy + y, vz + z) for vx, vy, vz in v], faces, mat)


def window(x, y, z, w, h, mats, side=False):
    size = (0.16, w, h) if side else (w, 0.16, h)
    box("window-frame", (x, y, z), size, mats["trim"])
    offset = (0.085, 0, 0) if side else (0, -0.085, 0)
    glass = (0.035, w - 0.14, h - 0.14) if side else (w - 0.14, 0.035, h - 0.14)
    box("glazing", (x + offset[0], y + offset[1], z), glass, mats["glass"])
    mullion = (0.045, w - 0.12, 0.045) if side else (w - 0.12, 0.045, 0.045)
    box("sash", (x + offset[0] * 1.4, y + offset[1] * 1.4, z), mullion, mats["trim"])


def geometry(name, mats, lod=False):
    if name == "bungalow":
        box("foundation", (0, 0, 0.45), (10.5, 12, 0.9), mats["stone"])
        box("body", (0, 0, 2.2), (10.5, 12, 2.6), mats["siding"])
        # Cross-gable roof with front dormer, broad full-width porch and front steps.
        gable("attic", (0, 0, 3.5), (12, 10.5, 3.2), mats["siding"], False)
        gable("roof", (0, 0, 3.55), (12.8, 11.4, 3.25), mats["roof"], False)
        box("porch", (0, -7, 0.55), (10.5, 2, 0.35), mats["stone"])
        box("dormer", (0, -2.35, 4.8), (4.7, 3.0, 1.4), mats["siding"])
        gable("dormer-roof", (0, -2.4, 5.5), (5.2, 3.5, 1.4), mats["roof"])
        box("chimney", (2.6, 1.8, 5.6), (0.8, 0.9, 2.6), mats["brick"])
        if lod:
            box("porch-roof", (0, -7, 3.3), (11, 2.7, 0.22), mats["roof"])
            return
        box("porch-roof", (0, -7, 3.3), (11, 2.7, 0.22), mats["roof"])
        for x in (-4.65, -1.6, 1.6, 4.65):
            box("post-base", (x, -7.7, 1.0), (0.65, 0.65, 0.7), mats["stone"])
            box("porch-post", (x, -7.7, 2.15), (0.20, 0.20, 2), mats["trim"])
        for x in (-3.3, 3.3):
            box("porch-handrail", (x, -7.7, 1.6), (2.55, 0.12, 0.12), mats["trim"])
            for dx in (-1, -0.6, -0.2, 0.2, 0.6, 1):
                box(
                    "porch-baluster",
                    (x + dx, -7.7, 1.17),
                    (0.05, 0.05, 0.75),
                    mats["trim"],
                )
        for step in range(4):
            box(
                "front-step",
                (0, -8.0 - step * 0.32, 0.55 - step * 0.13),
                (2.1, 0.36, 0.18),
                mats["stone"],
            )
        for x in (-3.2, 3.2):
            window(x, -6.1, 2.0, 1.6, 1.65, mats)
        for x in (-1.45, 0, 1.45):
            window(x, -3.9, 4.8, 1.05, 1.25, mats)
        for y in (-3, 0, 3):
            window(5.3, y, 2.2, 1.15, 1.6, mats, True)
        box("door", (0, -6.12, 1.8), (1.05, 0.18, 2.0), mats["door"])
    elif name == "storefront":
        box("brick-shell", (0, 0, 5.45), (8, 15, 10.9), mats["brick"])
        box("flat-roof", (0, 0, 10.99), (8, 15, 0.16), mats["roof"])
        for x in (-3.9, 3.9):
            box("parapet", (x, 0, 11.1), (0.2, 15, 0.4), mats["brick"])
        for y in (-7.4, 7.4):
            box("parapet", (0, y, 11.1), (8, 0.2, 0.4), mats["brick"])
        if lod:
            return
        for z in (3.6, 10.7, 11.3):
            box("cornice", (0, -7.6, z), (8.2, 0.35, 0.20), mats["trim"])
        for x in (-2.6, 0, 2.6):
            for z in (5.2, 8.4):
                window(x, -7.58, z, 1.9, 2.2, mats)
            window(x, -7.6, 1.8, 2.25, 2.65, mats)
            box("awning", (x, -8.05, 3.15), (2.55, 1.0, 0.16), mats["awning"])
        box("entry", (0, -7.75, 1.35), (1.0, 0.12, 2.6), mats["door"])
        for x in (-3.9, 3.9):
            box("pilaster", (x, -7.58, 5.5), (0.28, 0.22, 10.8), mats["brick"])
        for y in (-4, 0, 4):
            for z in (5.2, 8.4):
                window(4.05, y, z, 1.2, 2, mats, True)
    else:
        box("brick-shell", (0, 0, 3.3), (28, 10, 6.6), mats["brick"])
        gable("long-roof", (0, 0, 6.6), (10.8, 28.6, 1.7), mats["roof"], False)
        box("porch", (0, -5.9, 0.25), (28, 1.8, 0.5), mats["stone"])
        for x in (-10.5, 0, 10.5):
            gable("roof-cross-gable", (x, 0, 6.6), (5.6, 10.7, 1.65), mats["roof"])
        if lod:
            box("porch-roof", (0, -5.9, 3.2), (28.3, 2.2, 0.15), mats["roof"])
            return
        for x in (-10.5, -3.5, 3.5, 10.5):
            gable("entry-gable", (x, -5.7, 3.1), (3.5, 2.7, 1.0), mats["roof"])
            box("cream-fascia", (x, -5.06, 4.8), (5.6, 0.15, 1.6), mats["cream"])
            for dx in (-1.45, 1.45):
                box("post", (x + dx, -6.8, 1.8), (0.13, 0.13, 3.1), mats["trim"])
                window(x + dx, -5.16, 4.85, 1.15, 1.4, mats)
                window(x + dx, -5.12, 1.9, 1.0, 1.4, mats)
            box("door", (x, -5.13, 1.4), (1.0, 0.18, 2.3), mats["door"])
        for y in (-2, 2):
            for z in (1.9, 4.85):
                window(14.06, y, z, 1.15, 1.5, mats, True)


def join_meshes(name):
    bpy.ops.object.select_all(action="DESELECT")
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    return obj


def unwrap(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    obj.data.uv_layers.new(name="UVMap")
    obj.data.uv_layers.active = obj.data.uv_layers["UVMap"]
    obj.data.uv_layers["UVMap"].active_render = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(island_margin=0.015)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_main(obj, out, size=1024):
    unwrap(obj)
    mats = list(obj.data.materials)
    for channel in ("d", "s", "c", "i"):
        image = bpy.data.images.new(out.name + "_" + channel, width=size, height=size)
        if channel != "d":
            image.colorspace_settings.name = "Non-Color"
        for mat in mats:
            nodes = mat.node_tree.nodes
            emission = nodes.get("bake-emission") or nodes.new("ShaderNodeEmission")
            emission.name = "bake-emission"
            output = nodes.get("Material Output")
            mat.node_tree.links.new(
                nodes[channel].outputs["Color"], emission.inputs["Color"]
            )
            mat.node_tree.links.new(emission.outputs[0], output.inputs["Surface"])
            target = nodes.get("bake-target") or nodes.new("ShaderNodeTexImage")
            target.name = "bake-target"
            target.image = image
            nodes.active = target
        bpy.ops.object.bake(type="EMIT", margin=8)
        image.filepath_raw = str(out / (obj.name + "_" + channel + ".png"))
        image.file_format = "PNG"
        image.save()
    normal = bpy.data.images.new(obj.name + "_n", width=size, height=size)
    normal.generated_color = (0.5, 0.5, 1, 1)
    normal.colorspace_settings.name = "Non-Color"
    normal.filepath_raw = str(out / (obj.name + "_n.png"))
    normal.file_format = "PNG"
    normal.save()
    obj.data.uv_layers.remove(obj.data.uv_layers["SourceUV"])
    obj.data.materials.clear()
    obj.data.materials.append(packed_material(obj.name, out))
    for p in obj.data.polygons:
        p.material_index = 0


def packed_material(name, out):
    mat = bpy.data.materials.new(name + "-packed")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.75
    for channel in ("d", "s", "c", "i", "n"):
        tex = nodes.new("ShaderNodeTexImage")
        tex.name = channel
        tex.image = bpy.data.images.load(
            str(out / (name + "_" + channel + ".png")), check_existing=True
        )
        if channel != "d":
            tex.image.colorspace_settings.name = "Non-Color"
    links.new(nodes["d"].outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def lod_from_source(main, out, target):
    # Separate closed shells: authored A/C massing, inferred convex envelope for B.
    main.hide_set(True)
    if main.name.startswith("B-"):
        mesh = bpy.data.meshes.new(main.name + "-envelope")
        mesh.from_pydata([tuple(vertex.co) for vertex in main.data.vertices], [], [])
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.00001)
        bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
        unused = [vertex for vertex in bm.verts if not vertex.link_faces]
        bmesh.ops.delete(bm, geom=unused, context="VERTS")
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        bm.free()
        lod = bpy.data.objects.new(main.name + "-envelope", mesh)
        bpy.context.collection.objects.link(lod)
        lod.hide_set(False)
        bpy.context.view_layer.objects.active = lod
        lod.select_set(True)
        modifier = lod.modifiers.new("budget", "DECIMATE")
        lod.data.calc_loop_triangles()
        modifier.ratio = min(
            1, (target["lod"] - 2) / max(1, len(lod.data.loop_triangles))
        )
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        # Collapse can overshoot the physical envelope (observed: 39 cm below ground).
        # Keep the LOD inside the unchanged main mesh's authored metre bounds.
        bounds = [
            [f(vertex.co[axis] for vertex in main.data.vertices) for axis in range(3)]
            for f in (min, max)
        ]
        for vertex in lod.data.vertices:
            for axis in range(3):
                vertex.co[axis] = max(
                    bounds[0][axis], min(bounds[1][axis], vertex.co[axis])
                )
        for layer in list(lod.data.uv_layers):
            lod.data.uv_layers.remove(layer)
    else:
        mats = {
            k: material(k, ARGS.materials / main.name[0])
            for k in (
                "siding",
                "brick",
                "roof",
                "stone",
                "trim",
                "glass",
                "door",
                "awning",
                "cream",
            )
        }
        geometry(main.name[2:], mats, True)
        parts = [o for o in bpy.context.scene.objects if o.type == "MESH" and o != main]
        bpy.ops.object.select_all(action="DESELECT")
        for part in parts:
            part.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.object.join()
        lod = bpy.context.object
        for layer in list(lod.data.uv_layers):
            lod.data.uv_layers.remove(layer)
    lod.name = main.name + "_lod"
    unwrap(lod)
    lod.data.materials.clear()
    mat = bpy.data.materials.new(lod.name + "-bake")
    mat.use_nodes = True
    lod.data.materials.append(mat)
    for p in lod.data.polygons:
        p.material_index = 0
    main.hide_set(False)
    main_mat = main.data.materials[0]
    nodes = main_mat.node_tree.nodes
    emission = nodes.new("ShaderNodeEmission")
    output = nodes.get("Material Output")
    links = main_mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    for channel in ("d", "s", "c", "i"):
        links.new(nodes[channel].outputs["Color"], emission.inputs["Color"])
        links.new(emission.outputs[0], output.inputs["Surface"])
        image = bpy.data.images.new(lod.name + "_" + channel, width=256, height=256)
        if channel != "d":
            image.colorspace_settings.name = "Non-Color"
        node = mat.node_tree.nodes.get("target") or mat.node_tree.nodes.new(
            "ShaderNodeTexImage"
        )
        node.name = "target"
        node.image = image
        mat.node_tree.nodes.active = node
        bpy.ops.object.select_all(action="DESELECT")
        main.select_set(True)
        lod.select_set(True)
        bpy.context.view_layer.objects.active = lod
        bpy.ops.object.bake(
            type="EMIT",
            use_selected_to_active=True,
            cage_extrusion=0.45,
            max_ray_distance=1.4,
            margin=4,
        )
        image.filepath_raw = str(out / (lod.name + "_" + channel + ".png"))
        image.file_format = "PNG"
        image.save()
    links.new(bsdf.outputs[0], output.inputs["Surface"])
    normal = bpy.data.images.new(lod.name + "_n", width=256, height=256)
    normal.generated_color = (0.5, 0.5, 1, 1)
    normal.colorspace_settings.name = "Non-Color"
    normal.filepath_raw = str(out / (lod.name + "_n.png"))
    normal.file_format = "PNG"
    normal.save()
    lod.data.materials.clear()
    lod.data.materials.append(packed_material(lod.name, out))
    return lod


def export(obj, out):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.export_scene.fbx(
        filepath=str(out / (obj.name + ".fbx")),
        use_selection=True,
        object_types={"MESH"},
        global_scale=1.0,
        apply_unit_scale=True,
        axis_forward="-Z",
        axis_up="Y",
        bake_anim=False,
        use_triangles=True,
        add_leaf_bones=False,
        path_mode="STRIP",
    )


def metrics(obj):
    obj.data.calc_loop_triangles()
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    bounds = [
        [min(c[a] for c in coords) for a in range(3)],
        [max(c[a] for c in coords) for a in range(3)],
    ]
    uv = [v for loop in obj.data.uv_layers.active.data for v in loop.uv]
    return {
        "triangles": len(obj.data.loop_triangles),
        "vertices": len(obj.data.vertices),
        "bounds_m": bounds,
        "uv_range": [min(uv), max(uv)],
        "dimensions_m": [bounds[1][a] - bounds[0][a] for a in range(3)],
    }


def render_views(main, lod, out, spec):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 16
    scene.render.resolution_x = 768
    scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("neutral-sky")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.32, 0.39, 0.5, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    scene.world = world
    groundmat = bpy.data.materials.new("ground")
    groundmat.use_nodes = True
    groundmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (
        0.20,
        0.24,
        0.19,
        1,
    )
    ground = box("ground", (0, 0, -0.12), (100, 100, 0.2), groundmat)
    for x in (-spec["lot"][0] * 4, spec["lot"][0] * 4):
        box("lot-edge", (x, 0, 0.01), (0.06, spec["lot"][1] * 8, 0.03), groundmat)
    bpy.ops.object.light_add(type="SUN", location=(-10, -10, 20))
    sun = bpy.context.object
    sun.rotation_euler = (math.radians(25), math.radians(-20), math.radians(-30))
    sun.data.energy = 2.5
    sun.data.angle = 0.15
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    scene.camera = camera
    width = max(spec["size"][0], spec["size"][1])
    for view in ("close", "gameplay", "lod", "night"):
        camera.location = (width * 1.25, -width * 1.65, width * 1.15)
        aim = Vector((0, 0, spec["size"][2] * 0.35))
        camera.rotation_euler = (
            (aim - camera.location).to_track_quat("-Z", "Y").to_euler()
        )
        camera.data.ortho_scale = width * (1.6 if view in ("close", "night") else 5.0)
        lod.hide_render = view != "lod"
        main.hide_render = view == "lod"
        if view == "night":
            sun.data.energy = 0.08
            world.node_tree.nodes["Background"].inputs[1].default_value = 0.07
            bsdf = main.data.materials[0].node_tree.nodes.get("Principled BSDF")
            nodes = main.data.materials[0].node_tree.nodes
            main.data.materials[0].node_tree.links.new(
                nodes["i"].outputs["Color"], bsdf.inputs["Emission Strength"]
            )
            bsdf.inputs["Emission Color"].default_value = (1, 0.68, 0.28, 1)
        scene.render.filepath = str(out / (view + ".png"))
        bpy.ops.render.render(write_still=True)
    main.hide_render = False
    lod.hide_render = True
    ground.hide_render = True


def import_candidate(name):
    bpy.ops.import_scene.gltf(filepath=str(ARGS.generated / (name + ".glb")))
    obj = join_meshes("B-" + name)
    yaw = Matrix.Rotation(math.radians(ARGS.yaw_deg), 4, "Z")
    world = [yaw @ obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    low = Vector([min(v[a] for v in world) for a in range(3)])
    high = Vector([max(v[a] for v in world) for a in range(3)])
    extent = high - low
    scale = min(
        wanted / actual for wanted, actual in zip(TARGETS[name]["size"], extent)
    )
    center = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
    obj.matrix_world.identity()
    for vertex, position in zip(obj.data.vertices, world):
        vertex.co = (position - center) * scale
    obj.data.calc_loop_triangles()
    triangles = len(obj.data.loop_triangles)
    if triangles > TARGETS[name]["budget"]:
        mod = obj.modifiers.new("main-budget", "DECIMATE")
        mod.ratio = (TARGETS[name]["budget"] - 2) / triangles
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.data.uv_layers.active.name = "SourceUV"
    for mat in obj.data.materials:
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        bsdf = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
        base = bsdf.inputs["Base Color"]
        if not base.is_linked or base.links[0].from_node.type != "TEX_IMAGE":
            raise ValueError("Generated candidate lacks a base-color texture")
        diffuse = base.links[0].from_node
        diffuse.name = "d"
        uv = nodes.new("ShaderNodeUVMap")
        uv.uv_map = "SourceUV"
        links.new(uv.outputs["UV"], diffuse.inputs["Vector"])
        # PBR roughness is not CS1's specular/window semantic channel. No guessed windows.
        for channel, value in (("s", 0.04), ("c", 0), ("i", 0)):
            node = nodes.new("ShaderNodeRGB")
            node.name = channel
            node.outputs["Color"].default_value = (value, value, value, 1)
    return obj, {
        "raw_bounds": [list(low), list(high)],
        "uniform_scale": scale,
        "yaw_degrees": ARGS.yaw_deg,
        "rule": "Uniform fit inside the shared metre envelope; inferred aspect ratios preserved",
        "window_semantics": "No inferred illumination or color-variation mask; disabled, not guessed",
    }


def build(name, method):
    before = time.monotonic()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    out = ARGS.output / (method + "-" + name)
    out.mkdir(parents=True, exist_ok=True)
    normalization = None
    if method == "B":
        main, normalization = import_candidate(name)
    else:
        mats = {
            k: material(k, ARGS.materials / method)
            for k in (
                "siding",
                "brick",
                "roof",
                "stone",
                "trim",
                "glass",
                "door",
                "awning",
                "cream",
            )
        }
        geometry(name, mats)
        main = join_meshes(method + "-" + name)
    if ARGS.native_preview_only:
        lod = main.copy()
        lod.data = main.data.copy()
        bpy.context.collection.objects.link(lod)
        native = out / "native"
        native.mkdir(exist_ok=True)
        render_views(main, lod, native, TARGETS[name])
        return
    bake_main(main, out)
    lod = lod_from_source(main, out, TARGETS[name])
    export(main, out)
    export(lod, out)
    generated = time.monotonic() - before
    record = {
        "method": method,
        "target": name,
        "main": metrics(main),
        "lod": metrics(lod),
        "spec": TARGETS[name],
        "generation_seconds": generated,
        "normalization": normalization,
        "normal_map": "flat neutral tangent-space +X +Y; no invented relief",
        "lod_strategy": "B: closed convex-envelope retopology and source baking; A/C: authored low-poly shell",
        "renderer": "Blender 5.2.1 Cycles; CS1-like orthographic proxy, NOT Unity/CS1",
    }
    render_views(main, lod, out, TARGETS[name])
    record["render_seconds"] = time.monotonic() - before - generated
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(out / (main.name + ".blend")))
    record["files"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.iterdir()
        if p.is_file()
        and p.suffix not in (".blend", ".blend1")
        and p.name != "receipt.json"
    }
    (out / "receipt.json").write_text(json.dumps(record, indent=2))
    print("ASSET_COMPLETE", method, name, generated, flush=True)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--materials", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--method", choices=("A", "B", "C"), required=True)
parser.add_argument(
    "--generated", type=Path, help="Textured GLBs from run_trellis.py (required for B)"
)
parser.add_argument("--target", choices=tuple(TARGETS))
parser.add_argument(
    "--yaw-deg",
    type=float,
    default=0,
    help="Orient inferred B facade toward street (-Y)",
)
parser.add_argument(
    "--native-preview-only",
    action="store_true",
    help="Check imported B before rebaking",
)
ARGS = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
if ARGS.method == "B" and ARGS.generated is None:
    parser.error("B requires --generated")
for target_name in [ARGS.target] if ARGS.target else TARGETS:
    build(target_name, ARGS.method)
