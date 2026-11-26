"""Private CRP-to-Blender input extraction; never publish the extracted assets."""

import argparse
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import re
import struct

from PIL import Image

from biological_judge import sha256


def extract(reference, reader, out):
    source = reference["crp_containers"][0]
    path = Path(source["local_path"])
    if sha256(path) != source["sha256"]:
        raise ValueError("Anchor differs from accepted handback")
    catalog = reader.crp(path)
    root_name = reference["loaded_prefab"].split(".", 1)[1]
    prefab = next(p for p in catalog["prefabs"] if p["name"] == root_name)
    selected = max(prefab["meshes"], key=lambda m: m["triangles"])
    if selected["triangles"] != reference["native"]["main"]["triangles"]:
        raise ValueError("Extracted mesh is not the native main mesh")
    raw = path.read_bytes()
    r = reader.Reader(raw)
    r.take(6)
    r.string()
    r.string()
    r.number("I")
    r.string()
    count, start = r.number("i"), r.number("q")
    entries = {}
    for _ in range(count):
        name, checksum, kind = r.string(), r.string(), r.number("i")
        offset, size = r.number("q"), r.number("q")
        entries[checksum] = (name, kind, raw[start + offset : start + offset + size])
    p = reader.Reader(entries[selected["checksum"]][2])
    p.number("B")
    p.string()
    p.string()
    arrays = []
    for width, fmt in [
        (12, "fff"),
        (16, "ffff"),
        (8, "ff"),
        (12, "fff"),
        (16, "ffff"),
        (32, None),
        (64, None),
    ]:
        _, data = p.array(width)
        arrays.append(list(struct.iter_unpack("<" + fmt, data)) if fmt else None)
    faces = []
    for _ in range(p.number("i")):
        _, data = p.array(4)
        indices = [i[0] for i in struct.iter_unpack("<i", data)]
        faces.extend([indices[i : i + 3] for i in range(0, len(indices), 3)])
    target = out / reference["workshop_id"]
    target.mkdir(parents=True, exist_ok=False)
    texture_refs = {}
    root_payload = entries[prefab["root_checksum"]][2]
    material_payloads = [
        body
        for checksum, (_, kind, body) in entries.items()
        if kind == 2 and checksum.encode() in root_payload
    ]
    for prop in ("_MainTex", "_XYCAMap"):
        for body in material_payloads:
            position = body.find(prop.encode())
            if position < 0:
                continue
            matches = re.findall(rb"[0-9a-f]{32}", body[position:])
            texture_hash = next(
                (
                    h.decode()
                    for h in matches
                    if h.decode() in entries and entries[h.decode()][1] == 3
                ),
                None,
            )
            if texture_hash:
                q = reader.Reader(entries[texture_hash][2])
                q.number("B")
                q.string()
                texture_name = q.string()
                q.number("B")
                if catalog["format"] >= 6:
                    q.number("i")
                image_bytes = q.take(q.number("i"))
                im = Image.open(BytesIO(image_bytes)).convert("RGBA")
                im.save(target / (prop + ".png"))
                texture_refs[prop] = {
                    "name": texture_name,
                    "checksum": texture_hash,
                    "size": im.size,
                }
                break
        if prop not in texture_refs:
            raise ValueError(f"Cannot bind {prop} to this prefab's material")
    result = {
        "prefab": reference["loaded_prefab"],
        "crp_sha256": source["sha256"],
        "mesh": selected,
        "vertices": arrays[0],
        "uv": arrays[2],
        "normals": arrays[3],
        "faces": faces,
        "textures": texture_refs,
    }
    (target / "geometry.json").write_text(json.dumps(result))
    return {
        "prefab": result["prefab"],
        "crp_sha256": result["crp_sha256"],
        "main_triangles": len(faces),
        "textures": texture_refs,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handback", type=Path)
    parser.add_argument("reader", type=Path, help="installed.py from accepted de93357")
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("supply_reader", args.reader)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    handback = json.loads(args.handback.read_text())["genera"]
    refs = [
        handback["Ulmus"]["reference"],
        handback["Tilia"]["best_intrinsic_size_match"],
        handback["Tilia"]["best_near_art_alternative"],
    ]
    rows = [extract(r, reader, args.out) for r in refs]
    (args.out / "receipt.json").write_text(
        json.dumps({"reader_sha256": sha256(args.reader), "anchors": rows}, indent=2)
    )
    print(json.dumps(rows))
