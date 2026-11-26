# BioCLIP first anchor check — 2026-11-26

**Stop: this screen does not qualify BioCLIP as optimisation fitness.**
No CMA-ES, prompt/crop search or new structural edits followed the scores.
This is a failed qualification on offline projections, not proof of failure
on native CS1 screenshots, and not a tree-quality or cost acceptance.

| Anchor (expected genus) | Close 52 | Gameplay 140 | Distant 550 |
|---|---|---|---|
| American Elm (Ulmus) | Ulmus .935 | Ulmus .935 | Tilia .827 |
| Kaiserlinde 16m (Tilia) | Ulmus .605 | Ulmus .711 | Tilia .415 |
| Bigleaf Linden (Tilia) | Tilia .527 | Ulmus .973 | Gleditsia .384 |

Cells show top prediction and its three-way conditional probability, **not
calibrated confidence**. Close 2/3, gameplay 1/3, distant 1/3: total 4/9.
The frozen reserved iNat photos pass 12/12: Gleditsia 3/3, Tilia 6/6, Ulmus 3/3.
Photo labels are research grade; whole-crown QA is incomplete. This small,
unbalanced photo result does not validate crown-shape scoring or real-world
generalisation. Reserved images were not fed to an optimiser.

## Source and extraction

Supply source: accepted PR103, `de93357178fe706f83eed58c53106618e0805c3a`.
Handback attachment `01a2150d-5629-76a5-aa11-aab52ac3fdee` on PL-1326.
`extraction.json` records full CRP hashes, texture bindings and main triangles:
Elm 2480, Kaiserlinde 2238, Bigleaf 1926. Exact CRPs and all directory entry
checksums were verified using that revision's `tools/vegetation/installed.py`.
Root-prefab material checksums select the textures, not adjacent subassets.
No geometry, texture, CRP or source-photo pixels are redistributed here.

## Rendering and native sanity check

Blender 5.2.1 LTS / Cycles 16 samples. Shared single-target recipe:
1920×1080, vertical FOV45, target height8, yaw0; distances52/140/550,
pitches20/40/40. Fixed sun/world; Standard display, exposure0.
Unity coordinates and normals converted, DDS V origin flipped, packed XY
normal reconstructed with flipped green, packed alpha inverted and clipped.
Diffuse uses a gamma-preview approximation, not a full CS1 tree shader.
The distant image projects the main mesh, **not CS1's generated billboard**.
This check did not rerender A/B/C candidates or establish photometric parity
with their prior previews.

Accepted native close frames from PL-1326 were hash-checked and visually
compared once for Elm and Kaiserlinde: silhouette, trunk and foliage holes
agree qualitatively. Offline colours/lighting remain noticeably different
and darker; there is no SSIM or shader-parity pass. Native paired frames were
not classifier inputs. No game session or native slot was used this run.
Earlier alpha/UV/material debugging renders were excluded before scoring;
`offline-v4` was frozen before any classifier outputs were seen.

## Scoring and reproducibility

`anchor_probe.py` uses the pinned loader in `biological_judge.py`: FP32 eval,
no gradients or TF32, open_clip3.2.0; exact weight/config hashes checked.
Three previously frozen templates per genus are averaged/normalised.
All inputs use ordinary full-frame model preprocessing (short-side224,
centre crop); display crops on the sheet never enter the scorer.
`results.json` retains every input hash, prediction, probability, scorer hash,
weight hash, prompt and runtime version. All 21 cases were scored once.

Private blade output: `~/experiments/PL-1328-anchor-test/`.
Private carbon output has the same relative home. The scorer ran on the free
blade3090 GPU (`GPU-61c6b838-a720-4447-5c43-1573ed78947b`), finishing load,
text and 21 image encodings in 58.01 seconds. It exited and released its model.
Final nine-image render log finished at 82.84 seconds; extraction, debugging
and agent review are additional, unpriced work. No paid API calls. **Not a
full dollars-per-asset estimate**, nor an accepted-asset yield.

Reproduce extraction with the exact reader from de93357, then:

```sh
python extract_anchors.py handback.json installed.py private-extracted
blender -b -t 4 --python render_anchors.py -- private-extracted offline-v4
python anchor_probe.py offline-v4 private-photo-paths.json results.json \
  --weights /path/to/pinned/weights --device cuda:0
python anchor_sheet.py RUN sheet.png --font /path/to/Arial.ttf
```

Use the existing shared vision runtime with the isolated open_clip3.2.0 site;
resolve the reserved photo byte objects through Cabinet layout.object_path.
Output paths must be new; do not overwrite a frozen score report.
The one sheet includes accepted native/offline comparisons to expose the
remaining rendering domain gap. Recommendation: do not optimise against this
screen. Lead must choose the next evaluation approach before work resumes.
