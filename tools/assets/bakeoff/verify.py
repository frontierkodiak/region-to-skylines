"""Re-import real exported FBX bytes and check the CS1 authoring contract."""

import argparse
import json
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    results = []
    for receipt_path in sorted(args.output.glob("*/receipt.json")):
        receipt = json.loads(receipt_path.read_text())
        folder = receipt_path.parent
        for level in ("main", "lod"):
            name = folder.name + ("_lod" if level == "lod" else "")
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.fbx(filepath=str(folder / (name + ".fbx")))
            meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
            assert len(meshes) == 1, (name, "single mesh", len(meshes))
            obj = meshes[0]
            obj.data.calc_loop_triangles()
            count = len(obj.data.loop_triangles)
            budget = receipt["spec"]["lod" if level == "lod" else "budget"]
            assert 0 < count <= budget, (name, "triangle budget", count, budget)
            assert len(obj.data.vertices) < 65536, (name, "vertex limit")
            assert count == receipt[level]["triangles"], (name, "roundtrip triangles")
            coords = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
            actual = [
                [min(c[a] for c in coords) for a in range(3)],
                [max(c[a] for c in coords) for a in range(3)],
            ]
            expected = receipt[level]["bounds_m"]
            error = max(
                abs(a - b) for av, bv in zip(actual, expected) for a, b in zip(av, bv)
            )
            assert error < 0.002, (name, "FBX metre scale", error)
            assert obj.location.length < 0.002, (
                name,
                "ground-centered pivot",
                list(obj.location),
            )
            assert (obj.scale - Vector((1, 1, 1))).length < 0.001, (
                name,
                "applied scale",
            )
            width, depth = (cell * 8 for cell in receipt["spec"]["lot"])
            assert (
                actual[0][0] >= -width / 2 - 0.002 and actual[1][0] <= width / 2 + 0.002
            ), (name, "lot width")
            assert (
                actual[0][1] >= -depth / 2 - 0.002 and actual[1][1] <= depth / 2 + 0.002
            ), (name, "lot depth")
            ground_tolerance = 0.05 if level == "lod" else 0.002
            assert abs(actual[0][2]) < ground_tolerance, (
                name,
                "ground level",
                actual[0][2],
            )
            uv = obj.data.uv_layers.active
            assert uv is not None, (name, "UV required")
            assert all(
                -0.0001 <= value <= 1.0001 for loop in uv.data for value in loop.uv
            ), (name, "UV 0-1")
            assert len(obj.data.materials) == 1, (name, "single material")
            if level == "lod":
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                closed = all(edge.is_manifold for edge in bm.edges)
                volume = bm.calc_volume(signed=True)
                bm.free()
                assert closed and volume > 0.001, (
                    name,
                    "closed outward LOD shell",
                    volume,
                )
            for channel in ("d", "n", "s", "c", "i"):
                path = folder / (name + "_" + channel + ".png")
                assert path.is_file(), (name, "missing texture", channel)
                image = bpy.data.images.load(str(path))
                size = 256 if level == "lod" else 1024
                assert tuple(image.size) == (size, size), (
                    name,
                    "texture dimensions",
                    channel,
                )
                assert len(image.pixels) == size * size * 4, (
                    name,
                    "readable texture",
                    channel,
                )
            results.append(
                {
                    "asset": name,
                    "triangles": count,
                    "budget": budget,
                    "max_bounds_error_m": error,
                    "lot_cells": receipt["spec"]["lot"],
                    "passed": True,
                }
            )
    assert results, "No exported assets found"
    (args.output / "verification.json").write_text(json.dumps(results, indent=2))
    print(
        f"PASS: {len(results)} actual FBX roundtrips, maps, scale, budgets, pivots, UVs and lot fit"
    )


if __name__ == "__main__":
    main()
