# Parametric tree trial (PL-1328)

Final evidence is native v8 with input set `inputs-v4`; see `REPORT.md`.
Gleditsia uses denser cutout clusters after the original distant crown failure.
This is an asset-generation and native-import experiment, not an exporter
palette or a Workshop release. It does not change map generation.
The decision, measured limits and outstanding acceptance gates are in
[`REPORT.md`](REPORT.md). The review gallery bundles the authored FBX/maps,
native CRPs and a SHA-256 manifest, not third-party asset meshes.

## Targets and routes

The PL-1327 Boston inventory has 7,625 Gleditsia, 4,747 Tilia and 3,689 Ulmus
records. They are planted-tree evidence, not an estimate of regional forest
abundance. PL-1326's draft ledger identifies no base-game Gleditsia or Ulmus.
Tilia has `mp9-YoungLinden` (about 7.2 m); the 15/22 m variants target an
unestablished mature size class. No fully reviewed Workshop pass is established.
This is thin established supply, not proof that Workshop has none. Tilia's
native specimens use YoungLinden as the comparison; the common performance
baseline remains Tree2. Other genera use a generic stock control, not a
claimed best Workshop match.

`generate.py` makes 9/15/22 m crown-envelope variants, with independent seeds,
and fails above 1,500 main triangles. Its `sand3d` route uses branches/wire;
`blender` is a hand-built branch-network control. `sapling` uses a deliberately
low-detail Weber–Penn skeleton. They share the atlas and crown algorithms,
but the 15 m Sand3D member uses seed 1329 while the single-height controls
use 1328. This is a comparison of candidate assets under a common envelope
and budget, not a seed-matched causal comparison of skeleton algorithms.
It is **not** a comparison against Sapling's best unmodified tree presets.

The three profiles encode broad macroforms, not validated botanical models.
Species/cultivar identity, leaf morphology, crown allometry and forest-grown
versus street-grown forms still need independent visual and botanical review.
The initial diffuse/alpha/colour maps are rasterised procedural textures,
not projected photographic textures. Normal maps are deliberately flat.

`run_trellis.py` re-tests TRELLIS.2 on the three 15 m procedural renders at
the same 1,500-triangle target. This is a reconstruction/control experiment,
not recovered real-specimen geometry. Its published weights were unchanged
on 2026-11-24. `convert_trellis.py` preserves the generated geometry and UVs,
uniformly normalises height, and emits diagnostic CS1 maps. It has no bark
segmentation: its all-leaf colour mask is explicitly **not snow-ready**.

No calibrated multi-view specimen set was available in this trial. No
photogrammetry result or cost is claimed. Commercial model services were not
called. The results do not rank every contemporary mesh-generation model.

For the retained TRELLIS controls, use the archive’s hash-bound
`reference-images/{Gleditsia,Tilia,Ulmus}-input.png` files. They are the original
15 m Sand3D previews; the revised dense Gleditsia preview is a new input, not
a reproduction of that control. In the frozen TRELLIS
runtime documented under `../bakeoff/environment`, run `run_trellis.py`
with positional `references output` and `--weights` / `--dino` paths.
Then run Blender with `--python convert_trellis.py -- "$RUN/trellis" "$RUN/inputs"`.
The source/weight revisions and measured model calls are in
`observations/trellis.json`.

## Reproduce

Use Blender 5.2.1 LTS. Keep outputs outside the repository. Clone the optional
libraries into task scratch, not this repository:

- Sand3D 1.7.0, commit `2a8ea5865012689a0504cac3c430809dc639ef82`
- Sapling, commit `b2c91a3d60ae0fca07f77009401b2b3f0c0d792a`

```sh
blender --background -t 2 --factory-startup --python-exit-code 1 \
  --python tools/assets/trees/generate.py -- --out "$RUN/inputs" \
  --sand3d-path "$SCRATCH/sand3d" --genus Gleditsia
# Repeat for Tilia and Ulmus. Defaults: heights 9, 15, 22; seeds 1328..1330.
# Controls: --route blender --heights 15, or
# --route sapling --sapling-path "$SCRATCH/sapling" --heights 15.

blender --background --python-exit-code 1 \
  --python tools/assets/trees/verify.py -- "$RUN/inputs" "$RUN/roundtrip.json"
```

Every import set has one FBX, 512px `_d`, `_a`, `_c`, `_n` PNGs, and a
hash-bound receipt. Procedural candidates also retain their Blender scene
and a transparent diagnostic preview. Those previews are **not** CS1 LODs.
Tree UVs may tile, unlike atlased building LOD UVs. Units are metres and the
ground pivot is applied before export. Native FBX import scale is 100.

## Native tree path

Run only on blade's disposable install. `native.py` uses the harness's FIFO
slot in the foreground. It imports serially in one Asset Editor process,
saves each CRP, tears that session down, then loads the local assets into a
fresh Grand River city in a separate game process. Inputs copied into game
folders are tracked and removed by session teardown. Never use `submit` to
orphan this trial, and never run the game on carbon.

```sh
cd tools/cs1-harness
uv run cs1-harness build
uv run ../assets/trees/native.py "$RUN/inputs" "$RUN/native" --build-only
uv run ../assets/trees/native.py "$RUN/inputs" "$RUN/native" --check-only
```

Use repeatable `--candidate <package-stem>` arguments to limit forest timing
without changing the complete fresh-city package-load check. `--repeats 1`
reproduces the screening scope; it is not certification. The final gallery
builder requires `--frames-native` so stale-cache v5 timing cannot silently
be reused when v6 specimen/build data is assembled with earlier receipts.
For the frozen v6 run only, also pass `--legacy-v6-ui`; its driver revision
predates explicit per-window UI-state recording. The builder rejects stale
render-group data and mismatched candidate/control UI or tree-count states.

Native import uses `{kind:"tree", template:"Tree2"}`. Building callers keep
the default `kind:"building"`. The existing building-only template lookup,
lot and basement logic must not be used for tree bounds. Importer-generated
vertex alpha encodes wind displacement by height. `_c` is black for leaves
and white for bark, **not** the building colour-variation convention. The
native tree shader packs normals, colour mask and transparency into
`_XYCAMap`. A template's material tint must be cleared or the imported
diffuse is multiplied by it.

The `VegetationOps.cs` operations originate in PL-1326, commit
`c676ceec7e71d713b5a34b630bb19b6b737915ec`. Retargeting now invalidates tree
renderers and flushes RenderManager updates while paused: `UpdateTree` alone
only queues deferred work and left distant stock-tree groups unchanged.
Pair creation uses the same flush. This is a correction, not unchanged reuse;
reconcile this file when merging PR103. Registration placement matches PR103.
The first native timing run (v5) is discarded for this stale-cache defect.
The render-corrected v6 run records forest screenshots after each timed arm, outside
the timing window. It screens six representative candidates, not every size/route. The first
A1 at each zoom has a different HUD state because the screenshot helper
restores it. Reported v6 comparisons therefore use only common-state B/A2
pairs; this is post-hoc screening, not performance certification. The final
driver explicitly hides the HUD before every arm; native v8 verifies this
with 36 common-state windows and a post-specimen count of two.

CS1 generates a camera-updated, two-triangle tree billboard itself. There
is no authored `_lod.fbx` in these tree import sets. Native distant captures,
not a building LOD or the Blender preview, are the LOD evidence.

Timing is a stock-count A/B/A **screening measurement**, with the same
positions and count but different crown extents and random-scale policies.
It does not isolate per-triangle GPU cost. The default three repeats of
120 frames at each zoom are less than PL-1326's proposed certification bar;
report drift and unresolved render limiting, not a performance pass.

## Sources and licenses

- [Experienced-author tree guide](https://cslmodding.info/asset/tree/): tree
  shader, wind, textures and native billboarding; inspected 2026-11-24.
- [Sand3D](https://github.com/Sandflow-ai/sand3d): Apache-2.0 library. These
  trial programs are newly written; no Nature dataset program or asset is
  redistributed. [Nature](https://huggingface.co/datasets/Sandflow/sand3d-nature)
  programs/assets are CC BY 4.0 and require Sandflow credit if adapted.
- [Sapling](https://projects.blender.org/extensions/add_curve_sapling):
  GPL-3.0-or-later external generator; not bundled here. The low-detail
  control changes its settings rather than copying its source or presets.
- [TRELLIS.2](https://github.com/microsoft/TRELLIS.2): MIT, pinned local
  runtime from PL-881. Environment recipe remains in `../bakeoff/environment`.
- Macroform references: [Gleditsia](https://www.dnr.state.mn.us/trees/honey-locust.html),
  [Ulmus](https://harvest.cals.ncsu.edu/plantguidedb/index.cfm?ViewPlantID=10764),
  [Tilia](https://hort.ifas.ufl.edu/database/documents/pdf/tree_fact_sheets/tilcora.pdf).

No Workshop asset is redistributed. Base-game comparison images do not
grant redistribution rights to the base-game meshes or textures.

The first sparse Gleditsia masks lost crowns at camera-size 550. Its shared
atlas now uses 480 leaf blades rather than 115, with unchanged geometry/seeds.
All five revised assets retain distant crowns in native v8. The crop/mip
audit is only a proxy; the actual native before/after witnesses are the gate.
TRELLIS Gleditsia retains its pre-density reference, not a newly matched image.
