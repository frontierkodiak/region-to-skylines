"""Read factual mesh/texture inventory from blade's install without running Steam.

UnityPy reads built-in serialized objects. Existing CRP container readers in the
map-factory supply the directory layout; this reader adds strict range/checksum
validation and the installed PackageDeserializer's mesh/texture formats.
Only metadata is written, never meshes, textures, packages or account data.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
import re
import struct

import UnityPy

NATURAL = re.compile(
    r"\b(?:trees?|bush|shrub|grass|flower\w*|fern|hedge|reeds?|rocks?|boulder|pebble|moss|cactus|plant\w*|stump|logs?|leaf|leaves|coral)",
    re.I,
)


def natural_prop(name):
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).replace("_", " ")
    if re.search(r"logo|lamp|streetlight|sign|rock\s*wall|cage|roof|hologram|christmas", words, re.I):
        return False
    return bool(NATURAL.search(words))


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError("Read outside package")
        result = self.data[self.pos : self.pos + count]
        self.pos += count
        return result

    def number(self, fmt):
        return struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))[0]

    def string(self):
        size = 0
        for shift in range(0, 35, 7):
            byte = self.number("B")
            size |= (byte & 127) << shift
            if byte < 128:
                return self.take(size).decode("utf8")
        raise ValueError("Invalid string length")

    def array(self, width):
        count = self.number("i")
        return count, self.take(count * width)


def crp(path):
    raw = path.read_bytes()
    r = Reader(raw)
    if r.take(4) != b"CRAP":
        raise ValueError("Not a CRP")
    fmt = r.number("H")
    if not 2 <= fmt <= 12:
        raise ValueError(f"Unsupported CRP format {fmt}")
    package_name = r.string()
    r.string()  # encrypted author; not needed
    version, main = r.number("I"), r.string()
    count, start = r.number("i"), r.number("q")
    if not 0 < count <= 100000:
        raise ValueError("Invalid directory count")
    entries = []
    for _ in range(count):
        name, checksum, kind = r.string(), r.string(), r.number("i")
        offset, size = r.number("q"), r.number("q")
        if offset < 0 or size < 0 or start + offset + size > len(raw):
            raise ValueError("Invalid asset range")
        payload = raw[start + offset : start + offset + size]
        if hashlib.md5(payload).hexdigest() != checksum:
            raise ValueError("Asset checksum mismatch")
        entries.append((name, kind, payload))
    if r.pos != start:
        raise ValueError("Directory length mismatch")
    meshes, textures = [], []
    for name, kind, payload in entries:
        p = Reader(payload)
        # All assets begin with serialized type and null marker, before their
        # type-specific payload. Reject unknown layouts instead of guessing.
        if kind not in (3, 4):
            continue
        if p.number("B") != 0:
            raise ValueError("Null mesh/texture")
        typename = p.string().split(",")[0]
        if kind == 4 and typename == "UnityEngine.Mesh":
            mesh_name = p.string()
            n, vertices = p.array(12)
            xyz = list(struct.iter_unpack("<fff", vertices))
            for width in (16, 8, 12, 16, 32, 64):
                p.array(width)
            submeshes = p.number("i")
            indices = sum(p.array(4)[0] for _ in range(submeshes))
            if any(payload[p.pos :]) or indices % 3:
                raise ValueError("Mesh was not completely decoded")
            size = (
                [round(max(v[i] for v in xyz) - min(v[i] for v in xyz), 4) for i in range(3)]
                if n
                else [0, 0, 0]
            )
            meshes.append({"name": mesh_name, "triangles": indices // 3, "vertices": n, "size_m": size})
        elif kind == 3 and typename in ("UnityEngine.Texture2D", "ColossalFramework.Importers.Image"):
            texture_name = p.string()
            p.number("B")
            if fmt >= 6:
                p.number("i")
            image = p.take(p.number("i"))
            if image[:4] == b"DDS ":
                height, width = struct.unpack_from("<II", image, 12)
                encoding = image[84:88].decode("ascii", errors="replace")
            else:
                from io import BytesIO
                from PIL import Image

                with Image.open(BytesIO(image)) as im:
                    width, height, encoding = im.width, im.height, im.format
            textures.append({"name": texture_name, "width": width, "height": height, "encoding": encoding})
    components = sorted(
        {
            name.decode()
            for _, kind, payload in entries
            if kind == 1
            for name in re.findall(rb"(TreeInfo|PropInfo), Assembly-CSharp,", payload)
        }
    )
    return {
        "name": package_name,
        "main": main,
        "format": fmt,
        "version": version,
        "components": components,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "meshes": meshes,
        "textures": textures,
        "contains_assembly": any(k == 51 for _, k, _ in entries),
    }


def vector(v):
    return [v.x, v.y, v.z]


def unity_file(path, scripts):
    env = UnityPy.load(str(path))
    rows = []
    for obj in list(env.objects):
        if obj.type.name != "MonoBehaviour":
            continue
        header = obj.read(check_read=False)
        script = header.m_Script
        if script.m_PathID not in scripts or script.m_FileID == 0:
            continue
        if Path(obj.assets_file.externals[script.m_FileID - 1].path).name != "globalgamemanagers.assets":
            continue
        kind = scripts[script.m_PathID]
        go = header.m_GameObject.read()
        if kind == "PropInfo" and not natural_prop(go.m_Name):
            continue
        meshes, textures, shaders = [], [], []
        for component in go.m_Component:
            ptr = component.component
            if ptr.type.name == "MeshFilter":
                mesh = ptr.read().m_Mesh.read()
                size = [round(2 * v, 4) for v in vector(mesh.m_LocalAABB.m_Extent)]
                meshes.append(
                    {
                        "name": mesh.m_Name,
                        "size_m": size,
                        "triangles": sum(s.indexCount // 3 for s in mesh.m_SubMeshes if s.topology == 0),
                    }
                )
            elif ptr.type.name == "MeshRenderer":
                for material_ptr in ptr.read().m_Materials:
                    material = material_ptr.read()
                    if material.m_Shader:
                        shaders.append(material.m_Shader.read().m_Name)
                    for channel, texenv in material.m_SavedProperties.m_TexEnvs:
                        if texenv.m_Texture:
                            tex = texenv.m_Texture.read()
                            textures.append(
                                {
                                    "channel": channel,
                                    "name": tex.m_Name,
                                    "width": tex.m_Width,
                                    "height": tex.m_Height,
                                    "format": tex.m_TextureFormat,
                                }
                            )
        rows.append(
            {
                "name": go.m_Name,
                "kind": kind,
                "source_file": path.name,
                "path_id": obj.path_id,
                "meshes": meshes,
                "textures": textures,
                "shaders": shaders,
                "lod_triangles": None,
                "wind_observed": None,
                "season_observed": None,
                "snow_observed": None,
                "theme": None,
            }
        )
    return rows


def collect(game, workshop, out, base_cache=None):
    data = game / "Cities_Data"
    env = UnityPy.load(str(data / "globalgamemanagers.assets"))
    scripts = {o.path_id: o.read().m_ClassName for o in env.objects if o.type.name == "MonoScript"}
    scripts = {k: v for k, v in scripts.items() if v in ("TreeInfo", "PropInfo")}
    del env
    cached = json.loads(base_cache.read_text()) if base_cache else {}
    rows, receipts, failures = cached.get("base_prefabs", []), cached.get("files_inspected", []), []
    files = sorted(
        list(data.glob("*.assets")) + [p for p in data.glob("level*") if re.fullmatch(r"level\d+", p.name)]
    )
    for path in [] if base_cache else files:
        try:
            found = unity_file(path, scripts)
            rows.extend(found)
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            receipts.append(
                {"file": path.name, "bytes": path.stat().st_size, "sha256": digest, "matches": len(found)}
            )
            print(path.name, len(found), flush=True)
        except (ValueError, AttributeError, KeyError, OSError) as error:
            failures.append({"file": path.name, "error": str(error)})
            print("ERROR", path.name, str(error), flush=True)
        gc.collect()
    out.with_name("base-installed.json").write_text(
        json.dumps({"base_prefabs": rows, "files_inspected": receipts, "failures": failures}, indent=2) + "\n"
    )
    packages = []
    for path in sorted(workshop.glob("*/*.crp")):
        try:
            item = crp(path)
            if "TreeInfo" not in item["components"] and not (
                "PropInfo" in item["components"] and natural_prop(path.stem)
            ):
                continue
            packages.append({"workshop_id": path.parent.name, "file": path.name, **item})
        except (ValueError, struct.error, OSError) as error:
            failures.append({"file": str(path.relative_to(workshop)), "error": str(error)})
    result = {
        "schema_version": 1,
        "host": "blade",
        "unitypy_version": UnityPy.__version__,
        "assembly_sha256": hashlib.sha256((data / "Managed/Assembly-CSharp.dll").read_bytes()).hexdigest(),
        "scripts": scripts,
        "base_prefabs": rows,
        "workshop_packages": packages,
        "files_inspected": receipts,
        "failures": failures,
        "scope_note": "All root serialized .assets and levelN files, all TreeInfo and name-matched natural PropInfo; no DLC ownership claim; not a runtime loading test",
    }
    out.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--game", type=Path, required=True)
    p.add_argument("--workshop", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument(
        "--base-cache",
        type=Path,
        help="Reuse an explicit completed base scan while refreshing package metrics",
    )
    args = p.parse_args()
    collect(args.game, args.workshop, args.out, args.base_cache)
