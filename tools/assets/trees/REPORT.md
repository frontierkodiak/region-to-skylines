# Native tree route trial — 2026-11-24

## Decision

Sand3D is a useful candidate **program layer**, not a finished tree library
or a proved <$5 asset. One authored system emits Gleditsia, Tilia and Ulmus
at 9/15/22 m; nine controls compare direct Blender, Sapling and TRELLIS at
15 m. All 18 packages loaded in a separate fresh native city on blade.
Keep this as an engineering proof and an inconclusive quality/cost experiment,
not an approved regional palette.

The procedural card routes retain more perforated, tree-like crowns in this
batch than the severely budgeted TRELLIS meshes. That visual judgment is not
a general verdict on image-to-3D. Card/atlas logic is shared across Sand3D,
Blender and Sapling; it cannot establish Sand3D as the best foliage generator.
Better foliage and botanical form, not fewer branch triangles, are the next
quality lever.

## Targets and native geometry

Pinned demand/supply evidence is in `selection.json`. Boston's planted-tree
inventory gives Gleditsia 14.66%, Tilia 9.12%, Ulmus 7.09%; these are urban
stem records, not regional forest shares. There is no identified base-game
Gleditsia/Ulmus match. Tilia has approximately 7.2 m YoungLinden, but mature
15/22 m supply is not established. Zero fully reviewed Workshop passes in the
pinned ledger does not mean none exist.

| Genus | Sand3D, each 9/15/22 m | Blender 15 m | Sapling 15 m | TRELLIS 15 m |
|---|---:|---:|---:|---:|
| Gleditsia | 518 | 570 | 1,114 | 1,339 |
| Tilia | 628 | 680 | 1,224 | 944 |
| Ulmus | 568 | 620 | 1,164 | 1,116 |

Numbers are native main-mesh triangles. Sapling export meshes have exactly
28 zero-area triangles each, removed by the native importer. Actual exported
FBX reimport verifies all 18: <=1,500 triangles, metre heights within 2 mm,
ground pivot, finite UVs and receipt hashes. Independent size seeds vary
layout, not only uniform scale; Sand3D 15 m uses seed 1329 and the controls 1328.
This is candidate-asset comparison, not a seed-matched skeleton study.

CS1 uses `Custom/Trees/Default`, 512px diffuse/alpha/leaf-bark/normal maps and
native camera-updated two-triangle billboards. There is no building `_lod.fbx`
or building `_s` convention. Initial textures are rasterised procedural maps,
not photographic or high-poly lighting bakes; normals are deliberately flat.
TRELLIS has opaque geometry and an all-leaf colour mask, not snow-ready bark.

Tilia specimens are beside YoungLinden; the others use generic stock Tree2.
These are available stock references, **not the best vetted Workshop tree**.
No Workshop mesh, texture or package is redistributed.

## Distant foliage survival

The original Gleditsia cutouts failed the distant view across all three
procedural routes: mostly trunks remained. Other genera and opaque TRELLIS
retained crowns. A two-triangle LOD mesh and a screenshot file were therefore
not sufficient evidence of usable foliage.

The shared Gleditsia atlas now uses 480 small leaf blades instead of 115,
without changing geometry, seeds or triangle counts. Leaf-UV mean alpha rose
from 0.343–0.363 to 0.690–0.713. A BOX-filter proxy loses all old coverage at
2×2/1×1 with cutoff 128, while the new masks retain it. That proxy alone is
not a native pass: **native v8 visibly retains crowns in all five revised
Gleditsia assets**, including all three Sand3D sizes and both controls.
The before/after contact sheets preserve the actual, magnified native pixels.

The retained Gleditsia TRELLIS control reconstructs the pre-density-fix
reference, not the repaired input image. This limits causal model comparisons;
it remains a same-genus, same-height/budget candidate control.

## Native fixture and frame screening

V8 used source `2348a9e2c3456401e55b50594042a813a60d2583`, input set
`inputs-v4`, and the exact final C# DLL hash in `native-v8-summary.json`.
Five changed assets were reimported serially; thirteen byte-identical packages
were retained. All 18 were checked in a separate fresh Grand River process
with `--noWorkshop`, paused at noon. Automatic post-pair checking reports
exactly two TreeManager instances. All 90 captures and empty owned teardown
are recorded. Later changes are analysis/report data, not runtime code.

At the original 139,362 tree positions, each of six candidates has one
A/B/A at camera sizes 180/500, 120 warmup and 120 measured frames per arm.
HUD state is explicitly hidden in every window. Forest photographs are taken
outside the timed window. Raw p95 wall-frame ms are **candidate / mean of
stock A1/A2 p95s**:

| 15 m candidate | Camera size 180 | Camera size 500 |
|---|---:|---:|
| Gleditsia / blender | 30.6 / 35.9 | 30.3 / 32.0 |
| Gleditsia / sand3d | 30.9 / 33.5 | 30.8 / 31.6 |
| Gleditsia / sapling | 30.9 / 33.4 | 30.7 / 31.6 |
| Gleditsia / trellis | 30.8 / 33.1 | 31.0 / 31.5 |
| Tilia / sand3d | 30.6 / 33.6 | 30.8 / 31.3 |
| Ulmus / sand3d | 31.1 / 34.3 | 30.4 / 31.3 |

These small negative differences do **not** establish speedups. One repeat,
unattributed CPU/GPU/capture limiting, different crown extents and fixed
candidate scale versus stock random scale preclude performance certification
against PL-1326's proposed bar. This is not per-triangle GPU cost. Untimed
sizes/routes have no performance pass.

Discarded or superseded observations remain identified:

- V5 timings are invalid: `UpdateTree` only queued updates while paused,
  leaving distant groups stale. Explicit renderer invalidation and a
  RenderManager flush fix retargeting; actual forest pixels verify it.
- V6's first A1 per zoom had a different HUD state because the screenshot
  helper restores it. Its post-hoc B/A2 screening is historical, not mixed
  with v8. Old Gleditsia masks additionally fail crown retention.
- A suspected deletion-cache defect was not established. A live count of two
  trees and `FinalizeTree`'s existing invalidation contradicted that premise;
  a duplicate pre-release mark was removed. Low background vegetation is not
  evidence of phantom TreeManager instances. V7's explicit HUD reset was
  verified before v8 exercised the final runtime combination.

## Time and dollars

| Work | Observed time | Boundary |
|---|---:|---|
| Current procedural generation + preview | 3.73–8.43 s/asset | excludes Blender startup, shared setup and review |
| Repaired-batch warm native build | median 14.32 s/asset | four warm builds; excludes first launch and queue |
| Repaired five-asset editor batch | 1167.44 s | includes slot wait; not production throughput |
| Initial 18-asset editor batch | 1,461.90 s | includes shared queue, setup and cold launch |
| TRELLIS shared cold setup | 230.50 s | excludes earlier runtime/model preparation |
| TRELLIS Gleditsia/Tilia/Ulmus | 54.93 / 91.32 / 54.18 s | per-asset inference + mesh export, excludes setup/conversion |

TRELLIS inference alone took 49.48/74.30/45.27 s on the held 3090, peak Torch
allocation 2.63/6.87/4.83 GiB (not whole-card peaks), then released its load.
No commercial image/mesh-generation API call was made. That is **not a
zero-dollar full-cost result**. Codex authoring/review tokens are explicitly
uncosted in Multica; this producer run cannot appear in terminal usage until
it exits. Subscription allocation, hardware rates, review/rework and a
quality-accepted yield are not established. Full dollars stay null.

`accepted asset cost = (shared development + failed attempts)/accepted count
 + per-asset model/compute + native build compute + review/rework labour`.

Report marginal production and amortised R&D separately. At a hypothetical
$60/hour review rate, five minutes uses the $5 budget before compute; this is
sensitivity arithmetic, not a measured rate or duration. Internal guidance
calls held GPUs free capacity, not a fully allocated accounting rate. Its
API-equivalent priors do not price this Codex subscription run. No <$5 claim.

## Verification and remaining gates

C# build, 170 harness tests, full harness/tree Ruff/format, real native doctor,
18 FBX roundtrips, eighteen loaded CRPs, actual near/gameplay/distant views,
all five repaired crowns, common-HUD timing and empty teardown are verified.
Desktop 1440/mobile 390 gallery checks cover all native cards/images, filters,
view changes, no JS errors or horizontal overflow; the headless shell closes.

Native template import logs contain 163 mesh-readability errors before authored
FBX selection; the fresh city reports three missing stock panel assemblies.
These are preserved, not represented as warning-free imports. V8 whole-card
sample peaks are 10821 MiB, 157.66 W, 77°C, with 8146 MiB pre-existing use and a
1576 MiB menu game reading (not continuous game peak). Observed power.limit
is 200 W; it was never changed. Exact sources and per-run context are retained.

Botanical identity, leaf morphology/allometry, best-market comparison,
snow/wind qualification, renderer-limited performance and full-cost acceptance
remain open. No calibrated multi-view specimen set was available, so no
photogrammetry result is claimed. Commercial models were not called; this
is not a ranking of every current generator or Sapling's best presets.
Reproduction/source/license details are in `README.md`; next gates in `NEXT.md`.
