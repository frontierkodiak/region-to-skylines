"""Re-export the pinned study scenes for PL-880 without regenerating geometry or textures.

Run with Blender --background --python-exit-code 1 --python bridge_inputs.py --
<experiment> <destination>. Original outputs and preview/judge receipts stay untouched.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import bpy


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    manifest = {
        "source_revision": "82336461fec711a70e3fbba40987e1805af668d4",
        "assets": [],
    }
    for method in ("A", "B", "C"):
        root = args.experiment / ("outputs-clean" if method == "B" else "outputs")
        for target in ("bungalow", "storefront", "apartment"):
            name = method + "-" + target
            source = root / name
            out = args.destination / name
            out.mkdir(parents=True, exist_ok=True)
            receipt = json.loads((source / "receipt.json").read_text())
            scene_path = source / (name + ".blend")
            bpy.ops.wm.open_mainfile(filepath=str(scene_path))
            for suffix in ("", "_lod"):
                obj = bpy.data.objects[name + suffix]
                bpy.ops.object.select_all(action="DESELECT")
                obj.hide_set(False)
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.transform_apply(
                    location=False, rotation=True, scale=True
                )
                bpy.ops.export_scene.fbx(
                    filepath=str(out / (obj.name + ".fbx")),
                    use_selection=True,
                    object_types={"MESH"},
                    global_scale=1.0,
                    apply_unit_scale=True,
                    apply_scale_options="FBX_SCALE_ALL",
                    bake_space_transform=True,
                    axis_forward="-Z",
                    axis_up="Y",
                    bake_anim=False,
                    use_triangles=True,
                    add_leaf_bones=False,
                    path_mode="STRIP",
                )
                for channel in ("d", "n", "s", "c", "i"):
                    p = source / (obj.name + "_" + channel + ".png")
                    shutil.copy2(p, out / p.name)
                    assert digest(p) == digest(out / p.name)
            (out / (name + ".bake.json")).write_text(
                json.dumps(
                    {
                        "lot_cells": receipt["spec"]["lot"],
                        "size_m": receipt["main"]["dimensions_m"],
                        "import_scale": 100,
                    },
                    indent=2,
                )
            )
            receipt["bridge_export"] = {
                "source_scene_sha256": digest(scene_path),
                "source_receipt_sha256": digest(source / "receipt.json"),
                "change": "FBX_SCALE_ALL + baked axis transform only; all texture bytes unchanged",
            }
            receipt["files"] = {
                p.name: digest(p)
                for p in sorted(out.iterdir())
                if p.name != "receipt.json"
            }
            (out / "receipt.json").write_text(json.dumps(receipt, indent=2))
            manifest["assets"].append(
                {
                    "name": name,
                    "files": {p.name: digest(p) for p in sorted(out.iterdir())},
                }
            )
    (args.destination / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("BRIDGE_INPUTS_COMPLETE", len(manifest["assets"]), flush=True)


if __name__ == "__main__":
    main()
