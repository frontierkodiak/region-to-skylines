# Native tree route trial — 2026-11-24

## Decision

Keep Sand3D programs as a candidate **parametric layer**, not as a finished
tree library. The new program produces nine native assets across three crown
profiles and three sizes without decimation. Its engineering path works;
botanical fidelity, best-in-market appearance and the full <$5 cost do not
yet pass acceptance. Do not ship these prototypes as the regional palette.
Native v7 additionally verified the explicit HUD-reset driver and all 18
specimen pairs. A suspected background-deletion defect was not established:
the live TreeManager had exactly two instances, and the engine's
`FinalizeTree` already invalidates deleted groups. An extra pre-release
invalidation call was redundant and was removed; no phantom-tree fix is claimed.

In this batch the procedural leaf-card routes retain a more tree-like,
perforated canopy than TRELLIS reconstruction after a 1,500-triangle budget.
That is a visual judgment of the supplied specimens, not a general verdict
on image-to-3D. The same procedural card/texture algorithm is shared across
Sand3D, direct Blender and Sapling, so it cannot establish Sand3D as the
best foliage generator. The visible next bottleneck is foliage/shape quality,
not another reduction in branch triangles.

## Why these genera

Pinned demand and supply evidence is in `selection.json`. Boston's planted
tree inventory gives Gleditsia 14.66%, Tilia 9.12%, Ulmus 7.09%; these are
urban inventory records, not forest canopy shares. There is no identified
base-game Gleditsia/Ulmus match. Tilia has the approximately 7.2 m
`mp9-YoungLinden`, but mature 15/22 m supply is not established. The supply
ledger has no fully reviewed Workshop pass; that does not mean none exists.

## What was built and verified

| Genus | Sand3D, each 9/15/22 m | Blender 15 m | Sapling 15 m | TRELLIS 15 m |
|---|---:|---:|---:|---:|
| Gleditsia | 518 | 570 | 1,114 | 1,339 |
| Tilia | 628 | 680 | 1,224 | 944 |
| Ulmus | 568 | 620 | 1,164 | 1,116 |

Numbers are native main-mesh triangles. Sapling export meshes contain 28
zero-area triangles each; the native importer drops precisely those 28.
Actual FBX reimport validates all 18 exports: ground pivot, metre heights
(within 2 mm), finite UVs and the 1,500-triangle bound. Hash-bound receipts
identify the exact inputs and CRPs. Sizes use separate seeds, not only scale.

All 18 packages loaded in a separate, fresh Grand River city on blade's
disposable native CS1 install. All use `Custom/Trees/Default`, 512px texture
inputs and CS1's generated two-triangle, camera-updated billboard. There is
no building-style `_lod.fbx`; the native billboard is the tree LOD. Native
close, gameplay and billboard views exist for every candidate. Tilia is
beside YoungLinden; other genera are beside generic stock Tree2. These are
the available stock references, **not a claim to the best Workshop tree**.

The texture maps are rasterised procedural diffuse/alpha/colour maps with
flat normals, not a photographic or high-poly lighting bake. The tree shader
uses `_a`/`_c` conventions rather than building `_s` packing. TRELLIS preserves
its reconstructed UV texture but currently has opaque geometry and an
all-leaf colour mask: it is not snow-ready. No photographic quality is claimed.

Native editor diagnostics retain 163 template-mesh readability errors
(27 on the first import, eight on each subsequent import), before authored
FBX selection. All authored meshes are readable and their native counts are
recorded. The fresh city also reports three missing stock panel assemblies
(`ServicePointGroupPanel`, `HotelGroupPanel`, `RaceGroupPanel`). Neither is
silently relabelled a warning-free import.

## Native measurement correction

The first forest timing run, v5, is **invalid for comparing assets**. While
paused, `TreeManager.UpdateTree` queues updates but does not refresh distant
render groups. A forest screenshot exposed custom nearby crowns beside old
stock distant sprites. All v5 timing comparisons are discarded, not averaged
with later measurements.

The corrected harness invalidates tree renderers and flushes RenderManager's
pending groups on the simulation action while the city remains paused.
The follow-up v6 tests four 15 m Gleditsia routes plus Sand3D Tilia/Ulmus, with
one A/B/A sequence at each camera size (180 and 500), 120 warmup frames and
120 measured frames per arm, at the original 139,362 stock tree positions.
It captures the actual forest after every timed arm, outside the timing window.
V6 used driver revision `2e0897353ca0b8c439d2beaaf47e8ec9513de75f`.
The screenshot helper restores the HUD, so the first A1 at each zoom was
HUD-hidden while B and A2 were HUD-visible. The reported comparisons use
**only B/A2**, with matching HUD state, for every candidate. This is a
post-hoc screening choice, not a clean preregistered A/B/A study. Native v7
verified the explicit HUD reset in all six focused timing windows; those
windows remain separate from the v6 screening table.
Completed observations retain the raw windows and diagnostic flags; a
pending render-update flag is not treated as proof of a valid frame.

V6's retargeted forest screenshots visibly change at both zooms. The later
background-deletion hypothesis was rejected after checking the live instance
count and the engine's finalization path. Low background vegetation alone
is not a tree-cache correctness test.

Verification provenance: the final C# module has exactly the source hash of
the native v6 module. The final native driver has exactly the source hash
exercised in v7 (`4b4cdac`), which included a redundant pre-release group mark.
That mark duplicated `FinalizeTree`'s invalidation and was removed, restoring
the v6 C# source. The combined final head was not rerun after this rollback;
the per-module/source hashes and both native receipts are retained.

These wall-frame samples do not isolate the renderer limiter. One B/A2 pair,
stock random scales versus fixed authored scales, and different canopy
extents preclude certification against PL-1326's proposed performance bar.
Untimed sizes/routes have no performance pass. Do not infer frame cost from
triangle counts alone.

Raw p95 wall-frame milliseconds, **candidate / following stock control**,
at 139,362 tree positions; both windows have the HUD visible:

| 15 m candidate | Camera size 180 | Camera size 500 |
|---|---:|---:|
| Gleditsia / Sand3D | 35.2 / 36.2 | 35.2 / 36.1 |
| Gleditsia / Blender | 35.5 / 35.9 | **60.9 / 37.1** |
| Gleditsia / Sapling | 35.6 / 36.6 | 35.6 / 36.6 |
| Gleditsia / TRELLIS | 34.2 / 36.0 | 34.9 / 36.8 |
| Tilia / Sand3D | 42.1 / 38.2 | 33.7 / 35.6 |
| Ulmus / Sand3D | 37.2 / 40.3 | 33.5 / 36.4 |

The Blender wide-view +64% p95 anomaly is retained, not discarded as noise;
the Tilia close-view pair is +10.3%. A single pair cannot establish whether
these are repeatable renderer costs or transient effects. Nor do the small
negative differences establish a speedup. The raw windows and source hashes
are available for independent review; the performance verdict is inconclusive.

## Time and money

| Work | Observed time | What it excludes |
|---|---:|---|
| Procedural generation + preview | 3.73–10.29 s/asset | Blender startup, setup, author/reviewer labour |
| Warm native build driver | median 14.82 s/asset | First process launch, queue, batch setup |
| Native import job | 6.90–7.70 s/asset | Editor launch/save-driver overhead |
| Entire 18-asset editor batch | 1,461.90 s | Includes shared queue, not steady production throughput |
| TRELLIS shared cold setup | 230.50 s | Model/runtime preparation from the earlier bake-off |
| TRELLIS Gleditsia/Tilia/Ulmus | 54.93 / 91.32 / 54.18 s | Includes per-asset mesh export; excludes cold setup and conversion |

TRELLIS used the held RTX 3090 and released its load. Its inference-only
times were 49.48 / 74.30 / 45.27 s; peak Torch allocation was approximately
2.63 / 6.87 / 4.83 GiB, not whole-card or whole-process peak memory.
No commercial image/mesh-generation API call was made. That is **not a
zero-dollar full-cost result**. Multica records prior Codex tokens as
uncosted, and the current run's terminal usage is unavailable before exit.
No electricity/depreciation rate, subscription allocation or review-labour
rate was provided. `measurements.json` deliberately leaves full dollars null.

Use this accounting boundary when costing production:

`accepted asset cost = (shared development + failed attempts)/accepted count
 + per-asset model/compute + native build compute + review/rework labour`.

Report marginal production and amortised R&D separately. At a hypothetical
$60/hour review rate, five minutes alone uses the entire $5 budget before
compute; this is sensitivity arithmetic, not a rate or duration measured here.
The <$5 full-cost claim is therefore unestablished.

## Scope and next gate

This tests a newly authored Sand3D idiom, LLM-written Blender generation,
low-detail Sapling and the currently published TRELLIS.2 weights (unchanged
from the earlier building trial). It does not import Nature dataset meshes,
exhaust current commercial models, test photogrammetry without a calibrated
specimen set, or rank Sapling's best high-detail presets. No Workshop mesh,
texture or package is redistributed.

Before approving a palette: review the native specimens for actual genus
identity and foliage quality; compare against the best supply-ledger asset
once that lane has vetted imports; resolve snow/wind and renderer-limited
performance; price review/rework and amortised development. The reusable
generator/import harness is concrete progress, not a substitute for those
gates. Source/license and reproduction details are in `README.md`.
