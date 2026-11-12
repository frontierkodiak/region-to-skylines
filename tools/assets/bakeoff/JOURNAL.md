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

The first native build attempt (A-bungalow) waited from 21:04:55 to 21:19:55
UTC for the shared harness lock and exited 75. It never launched CS1. The
active game belonged to PL-857's Innsbruck water soak; PL-891/PL-893 harness
work was also queued. No other agent's session was stopped. Native-game
verification of the inputs, scoped-template/gameplay-camera extension and
prepared batch/report helpers remains pending, not a passed acceptance gate.

The final contact sheet also rejected direct-decimation LODs for B: they met
triangle counts but tore into fragments. Switched to closed convex-envelope
retopology and source baking, with a real re-imported manifold/volume check.
This conversion is explicit in B's cost and does not change its generated main
geometry. A separate receipt audit prevents reusing a judge score after even
an apparently identical rerender without checking its exact image hash.

## 2026-11-11 — first native import and basement diagnostic

The playtest hold ended and the older checks cleared. Created the isolated
`PL-881-harness-native` worktree because PL-900 was using the previous
`PL-881-game-check` checkout. Integrated main `e971c27` into the pinned bridge
and scoped-template/gameplay-view extension; asset commands now use the registered-waiter helper,
per-process staging and explicit owning-issue metadata. Compilation, lint,
format and the real 2080 Ti doctor passed.

The first real import at harness `95c3206` stopped before saving: 11.4 × 6.9 ×
15.54 m became renderer bounds 11.4 × 22.9 × 15.54 m. Native
`BuildingInfoBase.CalculateGeneratedInfo` adds a basement skirt and extends
the renderer bounds down to -16 m. It marks original vertices alpha 0 and
generated basement vertices alpha 255. The source's 708 triangles became 716,
not a scaled 22.9-m house. `results/game/first-native-import.json` preserves
the failed probe and receipt hash.

Harness `a1d01a6` retains the game's basement, records authored-body metrics
separately from renderer bounds and total triangles, and applies the size guard
to that body. Source geometry and every input texture remain unchanged. Its
native retry is separate (`game-native`); the failed `game` output is preserved.
Do not count the diagnostic failure as a successful package or render check.

## 2026-11-11 — actual renderer comparison

Primary harness `a1d01a6cddd8cddf069915676a64d779a6f7430e` completed all nine
build/check pairs on blade's 2080 Ti at 1280×720, preserving the fixed inputs,
original PL848 map and (0,300) placement. All body dimensions, lot cells,
triangle budgets, custom-LOD/material metadata and completed building state
survived the native save/reload cycle. The final audit additionally found
A-apartment and C-storefront rising 0.302 m on reload; strict vertical
preservation is 7/9, not a clean height-placement pass. The cause remains
unresolved; x/z, lot cells and completed state persisted for all nine. All
18 cleanup receipts were empty.

The 55.9-minute batch includes 12.0 minutes of recorded slot/preflight wait.
Editor jobs were 15.4–16.0 s each. Whole-card peak was 10,821 MiB (8,000-MiB
resident baseline), 124.1 W, 55°C. Game allocation at check end was about
2,814–2,818 MiB, not a separately measured process peak. SAM/Clef remained.

Inspected eight nine-candidate contact sheets (72 unaltered native frames),
including rear elevations, natural distant LOD, night and reloaded views.
Clef scored 18 exact full frames in 13.9 s; image/reference/request/model
bindings passed a separate audit. All original 192 artifact hashes and 24
Blender judge bindings still pass. The native audit also reads back all nine
CRPs from the three delivered QA archives. No image generation was repeated.

Native rendering exposes B1's open/see-through storefront and broken row
openings. Analysis-only re-import/weld confirms 715 / 2,818 / 3,594 open main
boundary edges; inputs were not repaired or re-exported. A/C have zero open
boundary edges but still contain intersections and simplified rear elevations.
Night captures are dark, not proof of functioning windows in a paused,
unserviced fixture. The same three missing-panel serialization messages appear
in every city check and are retained in the manifest.

The result refines the earlier blanket C default: A is the baseline for repeated
gameplay stock; C is a selective close-view material pass, with no consistent
gameplay advantage established. B1's bungalow silhouette is a useful positive
counterexample, not evidence that the unrepaired method wins production stock,
landmarks or props. `RESULTS.md` keeps the original pre-bridge analysis dated
and separate. Exact native source, timing, shader, image, package and judge
receipts are committed under `results/game/`; the private gallery retains all
original frames and the old authoring packs.
