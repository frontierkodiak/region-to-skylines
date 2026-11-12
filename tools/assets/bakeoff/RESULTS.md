# Native CS1 result — 2026-11-11

**Use procedural A as the baseline for repeated city stock, with hybrid C as a
selective material finish. Do not use untouched image-to-3D B1 as stock.**
The native comparison does **not** establish the lead's blanket hypothesis
that C wins ordinary buildings. C improves close-view surface detail, but A/C
remain near-tied at gameplay distance, and C's very bright roof texture can
hide form. This refines the earlier provisional C recommendation below.

[Native game comparison and QA CRPs](https://blade.tailc29f0.ts.net/shelf/asheville-asset-bakeoff-pl881/cs1/)
contains eight side-by-side views and all 72 original game frames. Contact
sheets are matched pixel crops, enlarged without retouching; clicking a gallery
image opens its original full frame. The original Blender study is preserved
separately and is not used as in-game proof.

## What CS1 changed

| Target | Manual native-render finding |
| --- | --- |
| Bungalow | B1 has the more convincing porch/dormer silhouette, including useful inferred rear detail. A/C's little dormer is too simplified; a texture pass cannot fix it. B1 remains narrower under the uniform envelope fit and needs topology repair. |
| Lexington storefront | A/C retain clean, solid openings. C's brick detail is useful close up; A is crisp at gameplay distance. B1's facade is visibly see-through and distorted, despite successful packaging. |
| Hillcrest-style row | A/C preserve a coherent, controllable repeated row. C adds material detail but washes out some roof contrast in direct daylight. B1's front openings/porches are broken and its fitted row is much shorter. |

The unchanged B main FBXs have 715 / 2,818 / 3,594 boundary edges after an
analysis-only coincident-vertex weld, versus zero boundary edges for A/C.
The B diffuse maps are RGB, with no alpha channel: this is not a designed
transparency mask. `main_topology.py` and `main-topology.json` bind the counts
to actual FBX hashes. Non-manifold intersections also exist in the procedural
kit; this is not a claim that those joined solids are production-clean topology.

All candidates retain limitations. A/C have sparse or blank rear elevations;
low porch slabs admit the map's decorative grass. Metre envelopes are study
assumptions, not surveys. B's uniform envelope fit changes the occupied width
as well as its shape; different apparent size is not evidence of the real
building's dimensions. No County-derived facts were used as scoring truth.

## Native verification

Nine uniquely named CRPs passed separate editor-build and fresh paused-city
checks. Each was placed at **x=0, z=300** on the same original PL848 Asheville
map, saved under a new harness city name, reloaded and checked again. Original
saves were preserved; all 18 session cleanup receipts are empty. Names, x/z,
lot cells and completed state survived for all nine. **Strict vertical placement
preservation is 7/9:** A-apartment and C-storefront rose 0.302 m on reload
(from 90.6508 to 90.9531 m); the other seven did not move. The source of this
height adjustment is unresolved. Reload images remain available; these two
packages are not certified for centimetre-stable vertical placement. The
architectural comparison uses relative cameras and the same x/z, but initial
ground height was not identical in those two fresh-city loads.

- Authored body bounds agree with the source within the stated 3% + 5 cm
  tolerance; original FBX roundtrips were checked to 2 mm. Lots are 2×3,
  2×3 and 4×3 eight-metre cells. Templates are ResidentialLow,
  CommercialLow and ResidentialHigh respectively; these are visual QA
  fixtures, not balanced service/capacity assignments.
- Native main triangle counts are 716 / 728 / 1,016 for both A and C, and
  5,699 / 7,883 / 11,756 for B1. CS1 adds basement triangles to the unchanged
  authored meshes. All remain under the study's 6k / 8k / 12k budgets.
- Custom LODs remain 96 / 72 / 68 triangles for A/C and 160 / 178 / 222
  for B1. Main maps are 1024², LOD maps 256²; the loaded native shader is
  `Custom/Buildings/Building/Default`, with DXT5 `_MainTex`, `_XYSMap` and
  `_ACIMap`. All normal maps are deliberately neutral.
- Primary close/gameplay cameras are 45 m / 25° and 120 m / 40°, at
  1280×720 on blade's RTX 2080 Ti. Natural LOD captures use **1.05× each
  asset's own maximum switch distance**, not a shared comparison distance.
  They show distant native silhouettes, not detailed close-up LOD quality.
- Night-close and night-LOD captures are genuinely native and dark. They do
  **not demonstrate functional window illumination** in these unserviced,
  manually completed, paused buildings. B's `_i` and `_c` maps deliberately
  disable those effects; A/C's authored masks alone are not proof of behavior.
- Each city check logs the same three serialization message types, repeated
  three times: missing `ServicePointGroupPanel`, `HotelGroupPanel`,
  `RaceGroupPanel`. These are preserved in the native manifest, not hidden
  behind an `ok` return. No enabled user mods or embedded asset mods were
  reported. This run does not certify a warning-free city runtime.

The first real editor import stopped before saving because the bridge's size
guard mistook CS1's basement/culling bounds (down to −16 m) for authored
height. The corrected harness records authored and renderer bounds separately,
retains the basement, and passes the unchanged body. The failed receipt is
preserved in `first-native-import.json`; it is not counted as a successful CRP.

## Native advisory judge

Resident Clef-Flash, NF4 weights with FP16 compute, scored all **18 exact
full-frame** close/gameplay screenshots against the original real references.
All image/reference/request/model hashes and complete probabilities are kept.
Its uncalibrated 0–4 reference-fidelity expectations were:

| Target / view | A | B1 | C |
| --- | ---: | ---: | ---: |
| Bungalow close | 2.90 | 2.59 | 2.87 |
| Bungalow gameplay | 2.24 | 2.70 | 2.33 |
| Storefront close | 3.16 | 2.70 | 3.40 |
| Storefront gameplay | 2.56 | 2.73 | 2.41 |
| Row close | 2.70 | 2.98 | 3.27 |
| Row gameplay | 2.40 | 1.90 | 2.37 |

The broken B1 storefront still receives 2.73 at gameplay distance; B1's
damaged row outranks A close up. Those are reasons not to automate acceptance
from this score. Small buildings occupy few pixels in full frames, and the
service downsamples to its declared 147,456-pixel budget. No confidence interval,
statistical superiority or independent human consensus is implied. Total
measured judge HTTP time was 13.9 s, not a new model-loading charge.

## Native source and accounting

- Original authoring/design source: `82336461fec711a70e3fbba40987e1805af668d4`.
  Corrected bridge inputs: `0d382c977747dd8e5ede55d5593fec2df7f76b5a`.
  No design regeneration, target substitution or texture-byte change.
- Primary harness: `a1d01a6cddd8cddf069915676a64d779a6f7430e`, integrating
  bridge `6b5b3429e568495013fae149679cc308d4e15e77`, scoped templates,
  gameplay camera and the measured basement fix; game assembly 1.21.1-f9.
  Compiled mod SHA256 starts `08b78db1827f3d7c`.
- Map SHA256: `b8507bf6e4c00f2336eb2051daed8785a6912a56ad594161e1e09a32ef0c94f4`.
  Input manifest SHA256: `f8a2fe2af3451a318bcfa1666142f31ee4a268cb9fca5a7da4a90a58f05670de`.
  Full exact receipts and hashes are in `results/game/` and the native gallery.
- The nine-pair batch took **55.9 min**, including **12.0 min of recorded
  slot/preflight wait**. The remaining **43.8 min** include boot, editor/city
  load, screenshots, save/reload and cleanup—not model inference. Individual
  editor import/save jobs took 15.4–16.0 s; see the per-asset timing receipt.
  The earlier 15-minute lock-only attempt launched no game; the failed native
  basement diagnostic is separate from this successful batch.
- Whole-card peaks were 10,821 MiB, 124.1 W and 55°C beside an 8,000-MiB
  starting resident allocation. End-of-check game allocations were about
  2,814–2,818 MiB; a separate per-process peak was not logged. Existing
  SAM/Clef workers were preserved. No new external 3D or image-generation
  calls were made for native testing.

| Asset | Model + original prepare s | Editor job s | Native build s | Native check s |
| --- | ---: | ---: | ---: | ---: |
| A-bungalow | 0.9 | 15.7 | 122.2 | 169.9 |
| B-bungalow | 32.4 | 15.8 | 121.2 | 171.7 |
| C-bungalow | 1.0 | 15.8 | 122.3 | 168.7 |
| A-storefront | 0.8 | 15.4 | 119.5 | 168.8 |
| B-storefront | 25.1 | 15.8 | 123.4 | 169.7 |
| C-storefront | 0.9 | 15.8 | 123.0 | 169.8 |
| A-apartment | 0.8 | 16.0 | 121.2 | 170.9 |
| B-apartment | 24.1 | 15.7 | 124.0 | 171.2 |
| C-apartment | 0.9 | 15.7 | 123.7 | 170.0 |

Native build/check columns exclude recorded slot/preflight wait but include
startup and teardown; the editor-job column is a subset of build, not an
additional cost. The model/prepare column excludes the one shared C atlas or
three B1 concept-image calls and one-time setup. It is not a full pipeline bill.

The original per-asset generation/preparation times and image-call costs remain
below. Native packaging is similar across arms and dominated by startup, not
their triangle count. Bridge re-export work was not separately timed. Exact
image-generation dollars, full authoring effort, electricity and subscription
allocation are unknown—not zero.

**Recommendation:** improve A's dormer, rear elevations and ground treatment
first; retain C for reviewed surface detail, not an automatic quality upgrade.
B1 is useful as a shape/reference proposal but needs real topology/semantic-map
work before stock use. None of these QA packs is certified for occupied night
lighting, zoning/growth, economics, long-running simulation, surveyed accuracy
or Workshop release. The landmark/prop half of the hypothesis remains untested.

A supplemental close-up forced-LOD / vanilla-night control at source
`8b87d60` compiled but did not run: its one 15-minute wait ended at 05:57:54
UTC with exit 75, behind PL-902 and PL-857 shared-slot work. No second race or
background waiter was left. Those prepared probes are not native evidence;
only the primary natural LOD and night captures are included in this verdict.

---

# Archived pre-bridge result — 2026-11-10

**Use C as the default for repeatable neighbourhood stock, provisionally.**
Its generated materials improve close views while keeping A's predictable
footprint, editable recipe and low triangle cost. At gameplay distance A and C
are close; this run does not establish a large perceptual improvement there.
The verdict still needs CS1's own renderer through PL-880.

The [private review page](https://blade.tailc29f0.ts.net/shelf/asheville-asset-bakeoff-pl881/)
contains close, gameplay, custom-LOD and night views, all real references and
the complete measurement table. `results/close-comparison.png` is the static
four-arm comparison; `results/measurements.json` holds exact measurements.

## What changed the conclusion

Direct-photo TRELLIS (B0) was not a fair stopping point for judging the method:
street trees and background came through, and the Lexington result was a thin
facade with vegetation fragments. A native-versus-rebaked GLB check showed the
bungalow's artifacts were already present before our texture conversion.

With clean, photo-informed concept inputs (B1), the same TRELLIS checkpoint,
seed and sampler produced much more recognizable buildings. The bungalow has
a richer porch/dormer silhouette than the simple recipe, and the storefront
recovers roof equipment and facade depth. But warped openings, small holes, baked photographic shading and inferred depth still require repair. The
Hillcrest model shrinks to 17.3 m width when uniformly fitted to its depth
envelope, versus C's 28.6-m modular segment. This is a scale-control problem,
not evidence that the real building is 17.3 m wide.

There is **no evidence here that B wins for landmarks or props**: none were
tested. Do not generalize this three-type, one-seed run to all image-to-3D
models. SUPRA-Tex, released in October, was surveyed but not run; its documented
3090 example exceeded the free shared memory available. Hunyuan3D-2mini's
untextured output was measured separately rather than compared as a finished
textured asset.

## Per-asset measured work

Times below are model generation/export plus Blender map/LOD/FBX preparation,
excluding preview rendering, image generation and one-time setup. They are wall
time, not GPU kernel time or human-equivalent authoring time.

| Target | A main / LOD tris | B1 main / LOD tris | C main / LOD tris | A / B1 / C prepare seconds |
| --- | ---: | ---: | ---: | ---: |
| Bungalow | 708 / 96 | 5,645 / 160 | 708 / 96 | 0.9 / 32.4 / 1.0 |
| Storefront | 720 / 72 | 7,783 / 178 | 720 / 72 | 0.8 / 25.1 / 0.9 |
| Hillcrest-style row | 1,000 / 68 | 11,658 / 222 | 1,000 / 68 | 0.8 / 24.1 / 0.9 |

Four preview renders added 8.4–10.1 seconds for A/C and 10.4–16.3 seconds for
B1. TRELLIS's one-time pipeline loading took 53.3 seconds for B1; its first
direct-photo run loaded in 89.6 seconds and incurred additional cold kernel
work (131.0 seconds for its first generated/exported asset). Native dependency
builds took about four minutes; downloading the 13-GiB checkpoint snapshot took
about 4.3 minutes. Those setup tasks overlapped other work and are not summed
into a fabricated per-asset total.

**Cost accounting:** A requires no image-generation calls; C used one shared
material-atlas call across three assets; B1 used one concept-image call per
asset. All four calls used the built-in subscription surface. Exact model,
billing and image-generation wall time were not exposed/measured, so no honest
dollar or complete end-to-end per-asset figure is available. 3D inference was
local on owned hardware, with no external 3D API spend; electricity and
subscription allocation were not costed. GPU memory was released after the
foreground model processes ended; resident SAM/Clef workers were preserved.

## Advisory judge and manual read

Clef-Flash's actual resident backend was NF4 with FP16 compute. Full probability
records, image hashes and identity are archived. Its 0–4 close-view expectations:

| Target | A | B0 direct photo | B1 clean concept | C |
| --- | ---: | ---: | ---: | ---: |
| Bungalow | 3.03 | 2.16 | 2.97 | 3.05 |
| Storefront | 3.31 | 2.69 | 3.23 | 3.34 |
| Hillcrest-style row | 3.09 | 1.95 | 2.87 | 3.19 |

These are not calibrated quality scores or confidence intervals. In particular,
the clearly unacceptable facade cutout still received a moderately high score.
My visual rejection of B0 and preference for the controlled C pipeline do not
come from a threshold. C's small numeric advantage over A does not establish
statistical superiority. A/C's gameplay scores are nearly tied, with A slightly
above C on the apartment example.

## Verified and remaining

- Twelve main candidates, twelve custom LODs and all five map files at both
  levels were generated; the import archive selects the nine A/B1/C candidates.
- All **24 actual FBX re-imports** passed mesh/material count, triangle/vertex
  budgets, metre-bound roundtrip, ground pivot, UV 0–1, closed outward LOD shells, map resolution/readability
  and 8-m-cell lot checks. All 192 archived artifact hashes and 24 judge/image
  bindings passed a separate audit.
- The private review page's four view controls each loaded all twelve actual
  images at 390-pixel width without horizontal overflow or JavaScript errors.
- Normal maps are deliberately neutral. B's specularity is conservative and
  its illumination/color-variation maps are zero: these disable effects rather
  than guess semantic windows. A/C have explicit window specularity/night maps.
- **Not verified:** CRP import, actual CS1 shaders or texture compression,
  physical game scale, native LOD switch, template behavior, place/save/reload,
  actual night behavior, exact surveyed correspondence, landmarks or props.

Keep the issue open for the PL-880 game-renderer gate. This is an evidence-backed
pre-bridge recommendation, not a claim of delivered playable asset packs.
