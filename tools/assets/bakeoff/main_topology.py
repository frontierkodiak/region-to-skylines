"""Diagnose native see-through geometry from the unchanged bridge main FBXs.

Run with Blender --background --python main_topology.py -- INPUTS OUTPUT_JSON.
Welding here is analysis-only and is never exported back to an asset.
"""

import hashlib
import json
import sys
from pathlib import Path

import bmesh
import bpy

inputs, output = map(Path, sys.argv[sys.argv.index("--") + 1 :])
rows = []
for folder in sorted(inputs.iterdir()):
    if not folder.is_dir():
        continue
    fbx = folder / (folder.name + ".fbx")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(fbx))
    objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    assert len(objects) == 1, folder.name
    bm = bmesh.new()
    bm.from_mesh(objects[0].data)
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.00001)
    rows.append(
        {
            "name": folder.name,
            "fbx_sha256": hashlib.sha256(fbx.read_bytes()).hexdigest(),
            "weld_distance": 0.00001,
            "original_vertices": before,
            "welded_vertices": len(bm.verts),
            "boundary_edges": sum(e.is_boundary for e in bm.edges),
            "nonmanifold_edges": sum(not e.is_manifold for e in bm.edges),
            "analysis_only_no_export": True,
        }
    )
    bm.free()
output.write_text(json.dumps(rows, indent=2))
print(json.dumps(rows, indent=2))
