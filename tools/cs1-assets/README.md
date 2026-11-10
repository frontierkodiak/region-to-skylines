# cs1-assets

Building assets for Cities: Skylines 1. `kit-house` takes one building from the
kudzu kit (PL-801, in the agentic-research-workbench repo) and writes the import
set the game's Asset Editor reads:

```sh
cd tools/cs1-assets
uv run cs1-assets kit-house --kit <workbench>/kudzu-kit --type craftsman --seed 0.31 \
    --width 10 --depth 11 --lot 2x2 --name KudzuCraftsman \
    --out ~/experiments/PL-880-asset-bridge/kit-house --preview
```

Then `cs1-harness asset build --src <out> --name KudzuCraftsman` turns it into a
`.crp` in the game (see `../cs1-harness/README.md`).

## What it writes

| File | What |
|:--|:--|
| `<name>.fbx` | the house, metres, origin at the lot centre on the ground, front facing the road |
| `<name>_lod.fbx` | the distant-view mesh: the roof's convex hull over walls dropped from its outline (about 35 triangles); UVs inside 0–1 |
| `<name>_d.png` | diffuse: one flat 16 px cell per kit palette ramp, darkened (× 0.58) so nothing passes about 140 RGB |
| `<name>_s.png` | specular: glass 235 (the game draws a fake interior behind it), roofs 8, the rest 25 |
| `<name>_i.png` | illumination: glass split by window into the two random night sets (255, 128), the rest 0 |
| `<name>_c.png` | colour-variation mask: black, so a template's colour variations leave the kit colours alone |
| `<name>_lod_d/_s/_c.png` | the same for the LOD, 64 px |
| `<name>.bake.json` | lot, size, triangle counts, materials; `asset build` checks the imported size against it |
| `preview-*.png` | `--preview`: Cycles renders of the house beside its LOD |

Main and LOD maps are each one resolution, as the game requires. No normal map
(the game's default is flat) and no alpha map (opaque).

## Steps

1. `export_kit.mjs` (Node) runs the kit's own `buildKit` on a rectangle footprint
   with the street on one side, and writes its flat-shaded triangles with
   palette ramp ids in the kit's local frame.
2. `cs1_assets/kit_bake.py` moves them onto the lot (Blender axes: Z up, the
   road at -Y), gives every face a small UV triangle inside its ramp's atlas
   cell (non-degenerate, so the game's tangents stay finite), paints the maps,
   and builds the LOD.
3. `cs1_assets/blender_fbx.py` runs in Blender 4.2 LTS with no UI. It builds both
   meshes (winding reversed for the game, below), exports each alone with "FBX
   All" scaling, -Z forward, Y up and Apply Transform, then re-imports the files
   and fails on any bounds difference.

## Coordinates, scale and winding

Seen in the game on blade (PL-880, 2026-11-10), not just read from settings:

- **Front.** The game's building frame has the road side at +Z. Blender's FBX
  export with -Z forward and Y up turns Blender -Y into FBX +Z, so a model whose
  front faces Blender's front view (-Y) faces the road. In game the garden walls
  and porch sit on the lot's road side and the chimney stays on the left seen
  from the street.
- **Scale.** "FBX All" writes metres with `UnitScaleFactor` 100. The game's
  importer reads that as centimetres: the house came in at 0.13 m wide. The
  Asset Editor's scale field must be 100, the value the creators' guide calls
  common. `<name>.bake.json` records `import_scale: 100`, and `cs1-harness asset
  build` uses it and fails if the imported size differs from the bake's.
- **Winding.** Moving the kit's frame (u, y up, w) onto Blender's (x, y, z up)
  swaps two axes, which is a reflection and turns every triangle inside out.
  `kit_bake.py` reverses the order back, and `blender_fbx.py` fails the export
  if the faces point inward on balance. Inward faces showed in game as an
  inside-out house, then as a black roof once culling was patched over: the
  game's importer itself behaves like any FBX importer.
- **Colour.** The game brightens a lot. Scaling the palette by 0.58 keeps
  clapboard near the guide's 140 ceiling; a soft cap that kept dark tones read
  washed out in game.
