# Bake-off journal

## 2026-11-10 — PL-881

This lane uses the pre-bridge Blender fallback while PL-880 builds native
packaging. It does not change the CS1 harness or start Steam.

- Real inputs: Norwood bungalow (PSABC), Lexington storefront (Stilfehler,
  Wikimedia Commons), current Hillcrest architecture (Housing Authority), and
  three USGS NAIP neighbourhood exports. Hillcrest's current form is two-story
  brick townhomes, not the generic three-story block initially imagined.
- Two real local model probes: Hunyuan3D-2mini shape-only and TRELLIS.2-4B
  textured generation. CPU-staged 512 TRELLIS worked without evicting SAM or
  Clef. SUPRA-Tex is newer but its published 3090 peak exceeds the free shared
  headroom; its absence is not a quality result.
- Raw street photos led to occluders and a thin facade. Added a separate clean
  concept control before drawing a conclusion; kept both branches of evidence.
- A successful Blender process was not evidence of success: Python exceptions
  initially returned shell status zero. Use `--python-exit-code 1` everywhere.
- Actual LOD images caught inward roof normals that file-format checks missed.
  Recomputed outward normals on each closed primitive, then retained dormer,
  chimney and cross-gables in low-poly silhouettes.
- Re-importing FBX caught scale/bounds issues and one 39-cm LOD collapse
  overshoot below ground. Bound inferred LOD vertices to the main envelope and
  count actual triangles, rather than accepting a nominal simplification target.
- The direct-photo bungalow looked the same with its native GLB material and
  after our CS1-map bake. Its photographic artifacts were not introduced by
  rebaking. The image-generation tool did not expose exact model/billing/time;
  report that gap instead of calling it free.
- The clean-input matte initially remained opaque because Pillow's flood fill
  silently failed on an array-backed read-only image. Copy to a mutable image
  first and assert that both foreground and background exist before GPU load.

Next gate: import the review pack with the PL-880 bridge, capture close,
gameplay, LOD and night in CS1 itself, and reassess the recommendation. No
claim here establishes that the game accepts or renders these assets correctly.

## 2026-11-10 — bridge continuation

Verified the exact original source above before continuing. PL-880's final
bridge is `6b5b3429e568495013fae149679cc308d4e15e77` (PR #10), used in an
isolated blade worktree. Its measured importer needs scale 100 for FBX All.
Re-exported the nine saved A/B1/C scenes with baked axis conversion and named
size/lot receipts, without changing generated designs or any map bytes.
All 18 new main/LOD FBX re-import checks passed. The original 48 Blender
previews, their hashes and Clef bindings remain historical evidence unchanged.

The final contact sheet also rejected direct-decimation LODs for B: they met
triangle counts but tore into fragments. Switched to closed convex-envelope
retopology and source baking, with a real re-imported manifold/volume check.
This conversion is explicit in B's cost and does not change its generated main
geometry. A separate receipt audit prevents reusing a judge score after even
an apparently identical rerender without checking its exact image hash.
