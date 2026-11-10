# Pre-bridge result — 2026-11-10

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
recovers roof equipment and facade depth. But warped openings, small holes,+baked photographic shading and inferred depth still require repair. The
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
