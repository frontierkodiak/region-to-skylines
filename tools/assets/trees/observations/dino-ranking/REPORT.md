# Native genus judges: control audit and DINOv3 — November 27

**Neither recipe passes. Stop; no CMA-ES.** Genus identity is not measured
reliably by these recipes on these native views. This is a scoped failure to
qualify fitness, not proof that every model, reference set or resolution must
fail. The next fitness specification is measured crown shape, gap fraction
and leaf colour against qualified iNat targets, with Caleb's blind pairs as
the external check. That fitness is not implemented or tuned in this run.

| Anchor | BioCLIP close / gameplay | DINOv3 close / gameplay |
|---|---:|---:|
| American Elm | **1** / 12 | 16 / 11 |
| Kaiserlinde 16m | 8 / 10 | 6 / 7 |
| Bigleaf Linden | 13 / 5 | 5 / **1** |

Ranks are out of16; 1–4 pass. Both recipes pass1/6 checks, with different
individual successes. No anchor passes both distances. Equal-scoring
controls count against an anchor. Gleditsia lacks a vetted Workshop anchor
and remains untested natively, not qualified by its photo references.

## Control audit and BioCLIP recomputation

`control-audit.json` binds the accepted PL-1326 index at de93357 and the exact
15 prefab identities to their archived creator Workshop titles and source URLs.
The names describe plane, willow, ginkgo, alder, maple, cottonwood, gum,
birch, cherry, oak, beech, olive and pear, not elm or linden. This checks
creator-declared identities; it does not certify an artist's botanical fidelity.
No control needs exclusion for Tilia or Ulmus. Recomputing ranks using the
frozen probability vectors leaves every BioCLIP rank unchanged. No repeat
image encoding or new model/prompt was needed for that arithmetic check.
The other Tilia anchor is not a negative for either linden's pool.

## DINOv3 recipe, frozen before observing scores

Held `facebook/dinov3-vitl16-pretrain-lvd1689m`, revision
`ea8dc2863c51be0a264bab82070e3e8836b02d51`; weight SHA-256
`dcb2e45127cccbf1601e5f42fef165eea275c8e5213197e8dcf3f48822718179`.
ViT-L/16 gives a practical 303M-parameter FP32 local backbone. No model
variants, resolutions, crops, masks or aggregators were tried after scores.
The held model card and processor config are the loading/preprocessing source.
The standard official processor resizes the entire RGB frame to224×224 and
uses ImageNet mean/std; there is no ROI crop, fine-tuning or text prompt.
Unit-normalised pooled CLS vectors are compared by cosine similarity.

For each genus g, compute mean cosine to its reference photos, then subtract
half the sum of the two other genera's mean cosines. Each genus has equal
weight in the contrast despite unequal photo counts. This is not a probability.
Every anchor is ranked against the same15 true-other-declared-genus controls
using its own genus contrast. The cutoff remains4 of16. Distant frames are
excluded entirely from inference and scoring.

## Inputs and provenance

Reuse all36 close/gameplay frames from native-v1, with exact byte hashes and
single-instance receipts; no native slot was booked. The prior39-frame game
run, cleanup and CRP hashes remain in observations/native-ranking/.

References are the same12 untouched reserved iNat photos: Gleditsia3,
Tilia6, Ulmus3, from the frozen PL-1328 pilot (snapshot20261027). The private
held-out manifest matched its prior frozen SHA-256; Cabinet layout.object_path
resolved byte objects again on blade, and every byte hash passed before load.
The pilot is a frozen experiment cohort, not a registered Cabinet dataset ID;
the dataset-name lookup correctly returned no such dataset. No reference was
silently substituted. Source photos stayed on blade and are not redistributed.

These references have research-grade labels but incomplete whole-crown and
mask QA; some show parts of trees. The pool is small and unbalanced. Background,
pose, scale and reference-domain differences can explain failures, so do not
turn this experiment into a universal claim about genus recognition.

`ranking.json` records all36 per-genus mean cosines and margins, six ranks,
the12 photo identities/hashes, model/config/processor/scorer hashes, actual
processor settings and runtime versions. The executed scorer hash matches
`rank_dino.py`. Thirteen local tests and Ruff pass; separate readback verifies
the saved score arithmetic and native source hashes.

The free blade3090 ran FP32 inference in7.04s including load and48 image
encodings, excluding file-hash preflight. Its process exited and released the
opportunistic load. No shared service changed, no new game run, no paid calls.
Full compute/agent/review dollars remain unpriced, not $0 per accepted asset.

Reproduce in the held vision runtime: `rank_dino.py NATIVE_V1 PRIVATE_PHOTOS
NEW_RESULT --weights HELD_VITL16 --device cuda:0`. `dino_sheet.py` renders the
single comparison sheet from the frozen native images, audit and result.
The overall tree pipeline's quality, measured-target QA, human calibration,
native B/C snow/performance and full-cost gates remain open.
