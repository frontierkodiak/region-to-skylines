"""Turn a kit building (export_kit.mjs JSON) into what the CS1 Asset Editor imports.

The kit colours faces by palette ramp, with no UVs or textures. CS1 wants a UV-mapped
mesh, texture maps named after it, and a low-detail LOD mesh whose UVs stay in 0-1. This
module writes:

- `<name>_d.png` diffuse: one flat cell per ramp, darkened to CS1's range (the guide asks for
  nothing brighter than about 140 RGB, because the game's lighting brightens everything);
- `<name>_s.png` specular: glass bright (the game draws a fake interior behind it), roofs
  near zero, the rest low;
- `<name>_i.png` illumination: glass split into the game's two random night-window sets
  (255 and 128), everything else dark;
- `<name>_c.png` colour-variation mask: black, so the template's colour variations leave the
  kit's colours alone;
- the same `_lod_` maps for the LOD mesh, all one resolution;
- `<name>.mesh.json`: both meshes in Blender coordinates for blender_fbx.py.

Blender coordinates: metres, Z up, the lot centred on the origin, the street side of the lot
at -Y (Blender's front view). Exported to FBX with Blender's default axes, -Y becomes the
building's front in CS1, which faces the road.
"""

from __future__ import annotations

import colorsys
import json
import pathlib
from dataclasses import dataclass

import numpy as np
from PIL import Image
from scipy.spatial import ConvexHull

CELL = 16  # texels per palette cell; keeps every 4x4 DXT block one colour down to mip 2
MAIN_SIZE = 256
LOD_SIZE = 64
GROUND = 0.3  # triangles entirely below this (m) are walks and paving, left out of the LOD

ROOFISH = ("roof", "Roof", "coping", "flatDark", "chimney")


@dataclass
class Baked:
    name: str
    out: pathlib.Path
    main_triangles: int
    lod_triangles: int
    size: tuple[float, float, float]
    lot: tuple[int, int]
    files: list[str]


def cs1_colour(hex_colour: str) -> tuple[int, int, int]:
    """Kit ramp base colour, darkened and slightly desaturated for CS1's renderer."""
    n = int(hex_colour.lstrip("#"), 16)
    r, g, b = (n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s *= 0.85
    # The game's lighting brightens a lot: scale so clapboard #efe9d8 (239) lands near 139, the
    # guide's ceiling. Checked in game on blade (PL-880): a soft cap that kept dark tones washed
    # the grey roof out to near white.
    v = min(v, 1.0) * 0.58
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return round(r * 255), round(g * 255), round(b * 255)


def specular(name: str) -> int:
    if name.startswith("glass"):
        return 235
    if any(k in name for k in ROOFISH):
        return 8
    return 25


def illumination(name: str) -> int:
    return {"glassA": 255, "glassB": 128}.get(name, 0)


class Atlas:
    """Square texture of flat CELL x CELL cells, one per material key."""

    def __init__(self, size: int):
        self.size = size
        self.per_row = size // CELL
        self.keys: list[str] = []

    def cell(self, key: str) -> int:
        if key not in self.keys:
            if len(self.keys) >= self.per_row**2:
                raise ValueError(f"atlas {self.size}px is full")
            self.keys.append(key)
        return self.keys.index(key)

    def uv_box(self, key: str) -> tuple[float, float, float, float]:
        """Inner quarter of the cell in UV (u0, v0, u1, v1), clear of filtering at the edges."""
        i = self.cell(key)
        cx, cy = i % self.per_row, i // self.per_row
        x0, y0 = cx * CELL + CELL / 4, cy * CELL + CELL / 4
        x1, y1 = x0 + CELL / 2, y0 + CELL / 2
        # Image rows run down; UV v runs up.
        s = self.size
        return x0 / s, 1 - y1 / s, x1 / s, 1 - y0 / s

    def paint(self, colour_of) -> Image.Image:
        img = Image.new("RGB", (self.size, self.size), (0, 0, 0))
        px = img.load()
        for i, key in enumerate(self.keys):
            c = colour_of(key)
            c = (c, c, c) if isinstance(c, int) else c
            cx, cy = i % self.per_row, i // self.per_row
            for y in range(cy * CELL, (cy + 1) * CELL):
                for x in range(cx * CELL, (cx + 1) * CELL):
                    px[x, y] = c
        return img


def triangle_uvs(tri: np.ndarray, box: tuple[float, float, float, float]) -> np.ndarray:
    """A non-degenerate UV triangle for a flat face: its own plane projection, fitted into box.

    Every texel in the box is the same colour, so only the shape matters: it keeps tangents
    finite for the game's normal-map shader.
    """
    a, b, c = tri
    e1 = b - a
    n = np.cross(e1, c - a)
    if np.linalg.norm(n) < 1e-9 or np.linalg.norm(e1) < 1e-9:
        p = np.array([[0, 0], [1, 0], [0, 1]], float)
    else:
        x = e1 / np.linalg.norm(e1)
        y = np.cross(n / np.linalg.norm(n), x)
        p = np.array([[np.dot(v - a, x), np.dot(v - a, y)] for v in tri])
    p -= p.min(axis=0)
    span = p.max(axis=0)
    span[span < 1e-9] = 1
    p /= span.max()
    u0, v0, u1, v1 = box
    return np.column_stack([u0 + p[:, 0] * (u1 - u0), v0 + p[:, 1] * (v1 - v0)])


def window_set(centroid: np.ndarray) -> str:
    """Split glass into the game's two night-window sets, by window (1.5 m cells), not by triangle."""
    k = tuple(np.floor(centroid / 1.5).astype(int))
    return "glassA" if (hash(k) * 2654435761) & 1 else "glassB"


def lod_mesh(verts: np.ndarray, names: list[str], tris: np.ndarray):
    """The roof's convex hull on vertical walls dropped from its outline: a few dozen triangles.

    A plain hull of the whole house slopes from the eaves down to the porch floor; the roof
    over a prism keeps the silhouette a distant house has. Chimneys are left out. Without a
    pitched roof it falls back to the hull of everything above the ground pieces. Each face
    takes the material of the main faces it covers: the ramp with the most area among main
    triangles facing the same way within 0.6 m of its plane, else wall or roof.
    """
    roof = [i for i in range(len(tris)) if any(k in names[i] for k in ROOFISH) and "chimney" not in names[i]]
    if roof:
        top = verts[tris[roof]].reshape(-1, 3)
        pts = np.vstack([top, np.column_stack([top[:, :2], np.full(len(top), 0.05)])])
    else:
        keep = [i for i in range(len(tris)) if verts[tris[i]][:, 2].max() >= GROUND]
        pts = verts[tris[keep]].reshape(-1, 3)
    hull = ConvexHull(pts)
    faces, labels = [], []
    tri_pts = verts[tris]
    cent = tri_pts.mean(axis=1)
    nrm = np.cross(tri_pts[:, 1] - tri_pts[:, 0], tri_pts[:, 2] - tri_pts[:, 0])
    area = np.linalg.norm(nrm, axis=1) / 2
    nrm = nrm / np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    for simplex, eq in zip(hull.simplices, hull.equations):
        normal, offset = eq[:3], eq[3]
        if normal[2] < -0.9:
            continue  # the base, never seen
        a, b, c = pts[simplex]
        if np.dot(np.cross(b - a, c - a), normal) < 0:
            simplex = simplex[[0, 2, 1]]
        dist = np.abs(cent @ normal + offset)
        ok = (dist < 0.6) & (nrm @ normal > 0.5)
        score: dict[str, float] = {}
        for i in np.nonzero(ok)[0]:
            score[names[i]] = score.get(names[i], 0) + area[i]
        if score:
            label = max(score, key=score.get)
        else:
            label = "roof" if normal[2] > 0.3 else "wall"
        faces.append(pts[simplex])
        labels.append("glass" if label.startswith("glass") else label)
    return np.array(faces), labels


def bake(src: pathlib.Path, out: pathlib.Path, name: str, lot: tuple[int, int], margin: float = 1.0) -> Baked:
    data = json.loads(src.read_text())
    out.mkdir(parents=True, exist_ok=True)
    ramps = {int(k): v for k, v in data["ramps"].items()}
    p = np.array(data["position"], float).reshape(-1, 3, 3)  # kit-local (u, y, w)
    ramp = np.array(data["ramp"]).reshape(-1, 3)[:, 0]

    # Kit (u, y, w) -> Blender (x, y, z) = (-u, w + offset, y): front wall faces -Y. The kit
    # frame is a rotation of pixel-asheville's right-handed (x east, y up, z south), so this is
    # a rotation too: no mirror, and the kit's outward winding stays outward. (Mapping u to +x
    # is a reflection: the building came out as its mirror image, with the winding reversed.)
    width_m, depth_m = lot[0] * 8.0, lot[1] * 8.0
    tri = np.stack([-p[..., 0], p[..., 2], p[..., 1]], axis=-1)
    tri[..., 1] += -depth_m / 2 + margin - tri[..., 1].min()
    tri[..., 2] = np.where(tri[..., 2] < 0.05, 0.05, tri[..., 2])  # lift ground pieces off the lot
    lo, hi = tri.reshape(-1, 3).min(axis=0), tri.reshape(-1, 3).max(axis=0)
    if hi[0] > width_m / 2 or lo[0] < -width_m / 2 or hi[1] > depth_m / 2:
        raise ValueError(
            f"building ({hi[0] - lo[0]:.1f} x {hi[1] - lo[1]:.1f} m with walk) does not fit a "
            f"{lot[0]}x{lot[1]} lot ({width_m:.0f} x {depth_m:.0f} m)"
        )

    names = []
    for t, r in zip(tri, ramp):
        n = ramps[int(r)]["name"]
        names.append(window_set(t.mean(axis=0)) if n == "glass" else n)
    hexes = {ramps[r]["name"]: ramps[r]["hex"] for r in ramps}
    hexes["glassA"] = hexes["glassB"] = hexes.get("glass", "#2f3b56")

    atlas = Atlas(MAIN_SIZE)
    uvs = np.array([triangle_uvs(t, atlas.uv_box(n)) for t, n in zip(tri, names)])

    # LOD: hull faces, coloured from the main mesh. Walls/roof fallbacks take the commonest
    # wall and roof ramps of the main mesh.
    flat = tri.reshape(-1, 3)
    lod_tris, lod_names = lod_mesh(flat, names, np.arange(len(flat)).reshape(-1, 3))
    wall = max((n for n in names if not any(k in n for k in ROOFISH) and not n.startswith("glass")), key=names.count)
    roof = max((n for n in names if any(k in n for k in ROOFISH)), key=names.count, default=wall)
    lod_names = [{"wall": wall, "roof": roof}.get(n, n) for n in lod_names]
    hexes.setdefault("glass", hexes["glassA"])
    lod_atlas = Atlas(LOD_SIZE)
    lod_uvs = np.array([triangle_uvs(t, lod_atlas.uv_box(n)) for t, n in zip(lod_tris, lod_names)])

    files = []

    def save(img: Image.Image, suffix: str):
        path = out / f"{name}{suffix}.png"
        img.save(path)
        files.append(path.name)

    for a, lod in ((atlas, ""), (lod_atlas, "_lod")):
        save(a.paint(lambda k: cs1_colour(hexes[k])), f"{lod}_d")
        save(a.paint(specular).convert("L").convert("RGB"), f"{lod}_s")
        save(a.paint(lambda k: 0), f"{lod}_c")
        if not lod:
            save(a.paint(illumination), "_i")

    mesh = {
        "name": name,
        "lot": list(lot),
        "objects": {
            name: {"triangles": tri.tolist(), "uvs": uvs.tolist()},
            f"{name}_lod": {"triangles": lod_tris.tolist(), "uvs": lod_uvs.tolist()},
        },
    }
    (out / f"{name}.mesh.json").write_text(json.dumps(mesh))
    size = tuple(float(x) for x in hi - lo)
    receipt = {
        "source": data["source"],
        "name": name,
        "lot_cells": list(lot),
        "lot_m": [width_m, depth_m],
        "size_m": [round(s, 3) for s in size],
        "bounds_m": {"min": lo.round(3).tolist(), "max": hi.round(3).tolist()},
        "main_triangles": len(tri),
        "lod_triangles": len(lod_tris),
        "materials": atlas.keys,
        "lod_materials": lod_atlas.keys,
        "textures": {"main_px": MAIN_SIZE, "lod_px": LOD_SIZE},
        # Blender's "FBX All" writes metres with UnitScaleFactor 100; the game's importer reads
        # that as centimetres, so the Asset Editor's scale field must be 100 (seen in game,
        # PL-880, 2026-11-10). `cs1-harness asset build` takes it from here.
        "import_scale": 100,
        "files": files,
    }
    (out / f"{name}.bake.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return Baked(name, out, len(tri), len(lod_tris), size, lot, files)


def lot_from(text: str) -> tuple[int, int]:
    w, _, d = text.lower().partition("x")
    lot = int(w), int(d or w)
    if not all(1 <= c <= 4 for c in lot):
        raise ValueError("growable lots are 1-4 cells each way")
    return lot
