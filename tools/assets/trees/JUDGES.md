# External-judge protocol

Tripo D is shelved by lead direction on November 25. No credential or purchase
is required. TRELLIS remains a control. The previous Gemini preview preferences
are historical opinions, not validated fitness or pipeline acceptance.

## First gate: Workshop anchors, before optimisation

**November 26 direction supersedes the fallback below.** Use both reviewed
Tilia assets and American Elm from accepted PR103 `de93357`. There is no vetted
Gleditsia Workshop match; the lead explicitly permits held-out iNat photos as
its only anchor. Extract exact CRPs and render offline rather than occupy the
native slot. If the genus check fails, report the failure and stop; do not
continue with close-only fitness or measured-target optimisation by default.

The executed check is `anchor_probe.py`, reusing this module's frozen loader,
not its older strict three-native-anchor manifest CLI. It scored nine offline
projections plus twelve reserved photographs. Results: 4/9 and 12/12 correct,
respectively. See observations/anchor-test/REPORT.md for domain limitations.
No BioCLIP fitness views are admitted by this result. No optimisation started.

The remainder documents the earlier native protocol, not a claim that it ran:

`biological_judge.py` requires one vetted Workshop anchor for each of
Gleditsia, Tilia and Ulmus, with supply-review evidence, exact prefab and CRP
hash. Each needs hash-bound native single-target captures at camera sizes
52/140/550 (close/gameplay/billboard). Use the existing 1920×1080 camera/pitch
convention, fixed daylight and no HUD. Do not feed a two-genus comparison
frame to a classifier for one tree. Do not enlarge the gameplay crown to
make a failed distance pass. Native sessions must be short and may not hold
the slot while waiting on data, external judges or another agent.

The screen pins BioCLIP 2.5 revision `191d741545e4c741cdef4b22c6eb69c945c1e592`,
checks both held weight/config hashes, uses open_clip 3.2.0, freezes FP32
evaluation and records runtime versions, prompts, input hashes and scorer hash.
Its three-way softmax is conditional on these three genera, **not calibrated
biological confidence**. The prompts are fixed before viewing anchor scores.

Require all three anchor top-1 predictions correct at close range. If any
gameplay anchor fails, BioCLIP fitness is close-only. If close fails, exclude
BioCLIP fitness and use measured shape targets. A single asset per genus is
only a first smoke screen, not a statistical validation or teacher calibration.
Missing/unvetted anchors leave the gate closed; synthetic or stock substitutes
cannot open it.

Manifest shape:

```json
{"anchors":[{"genus":"Gleditsia","prefab":"exact loaded name",
"vetted":true,"review_evidence":"pinned supply review",
"crp_sha256":"64 hexadecimal characters",
"images":{"close":{"path":"native-close.png","sha256":"...",
"camera_size":52,"single_target":true}}}]}
```

All three genera and all three views are required. Relative image paths resolve
against the manifest. Never mark `single_target` for an ordinary paired shot.
The loader requires the existing local weight directory and never downloads
or trains a model. CPU is the safe default; choose a GPU only after checking
live placement. A blank-image runtime smoke produced one finite 1024-d vector
on blade CPU in 36.29 s including load/text encoding; it tested **zero anchors**.

## Reference inputs

Cabinet cohort `pl1328-tree-judge-ref-pilot-v1` is frozen to snapshot 20261027
by `reference-cohort.sql`: 32 candidate photos per genus, one photo per observer
within each genus, research grade and CC0/CC-BY/CC-BY-SA only. Cabinet's
observer-v1 split has 84 train, 6 val and 6 test photos; there are 90 observers.
All 96 downloaded large images passed SHA-256 readback, with zero identical
image bytes across splits. Photos remain in Cabinet, not this repo.

This is a **candidate reference pilot**, not qualified crown ground truth.
Whole-crown and leaf/bark mask QA are incomplete. Do not derive shape targets
from leaf close-ups, partial crowns, multiple trees or background vegetation.
Training and private held-out manifests are separate on blade; the optimiser
must receive only training references. No held-out image has been used for
program tuning in this increment. The held-out sample is small and unbalanced
(test: Gleditsia 3, Tilia 2, Ulmus 1); expand it if crown QA leaves no usable
genus references. Exact-byte checks do not establish near-duplicate freedom.

For approved crown masks, measure crown bounding-box width/height and gap
fraction within a frozen crown envelope. Measure leaf colour distributions
only through approved leaf masks, keeping illumination and background effects
explicit. Freeze the mask/envelope algorithm before optimisation.

PL-1327's accepted source is PR101 head
`3940613c28fde8720c40a1c0ff5b9899dd3eee00`. Its canopy input explicitly says
“Top-of-canopy area samples; COG overview pixels, not individual-tree heights”.
Use that as a regional height prior, not genus-specific stem-height truth.

## Optimisation and independent checks

Only after the anchor screen and reference QA: freeze a training-only fitness
capsule and run bounded CMA-ES over program/bake parameters. Restrict BioCLIP
to its admitted views; combine it with measured shape/colour targets. Bring
in a model for structural edits only after a measured plateau. No CMA-ES or
new structural optimisation has started yet.

DINOv3 nearest-neighbour scoring uses only the private held-out reference bank.
Do not feed its scores or Gemini held-out preferences back to the optimiser.
Gemini comparisons need order reversal and Workshop anchors, not merely
identity/empty sentinels. Neither judge is qualified until it ranks those
anchors sensibly. Prepare about six native gameplay blind pairs for Caleb;
report each judge's agreement against his answers, including ties/abstentions.
The existing A/B/C phone builder is not an anchor-inclusive teacher pack.

Lead's four New England Woods requirements are retained for the gated fitting
stage: stochastic card retention by represented coverage; projected card-area
matching; SSIM fitting of leaf/bark colour, contrast and translucency to a
full-detail render; mesh/billboard lighting continuity at the handoff. Audit
the current high-source leaf/bark materials before treating it as an SSIM
target. None of these new fitting stages is claimed complete. The linked
explainer returned HTTP 403 here; this list follows the supplied lead direction,
not an independent reading of that page.

No optimisation, judge agreement, native snow pass or full <$5 acceptance is
established by the runtime/cohort preparation.
