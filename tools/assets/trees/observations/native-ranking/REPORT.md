# Native ranking gate — 2026-11-27 UTC

**Fail. Stop before CMA-ES.** Native inputs remove the previous offline
shader approximation, but BioCLIP still fails the requested ranking gate.
No prompt/crop search, structural edits, optimisation or DINO substitution
followed. This qualifies neither a fitness signal nor a generated asset.

| Anchor | Close rank | Gameplay rank |
|---|---:|---:|
| American Elm (Ulmus) | 1 — pass | 12 — fail |
| Kaiserlinde 16m (Tilia) | 8 — fail | 10 — fail |
| Bigleaf Linden (Tilia) | 13 — fail | 5 — fail |

Every pool has 16 trees: one anchor and the same 15 controls. Passing ranks
are 1–4. Controls tied with an anchor count against it. The other Tilia anchor
is not a negative. Gleditsia has no vetted Workshop anchor and remains
untested natively; the previous three held-out Gleditsia photos are not a
substitute for a native ranking result. No BioCLIP score uses distant views.

## Frozen sources and inputs

PL-1326 source: accepted PR103 `de93357178fe706f83eed58c53106618e0805c3a`.
`plan.json` froze selection before any native scores: near-art >=3, standalone
broadleaf assets, native heights 8–25 m, other labelled genera, genus diversity
first then closest to15 m. It contains exact prefab identities and CRP hashes.
There are seasonal controls; this is not a season-normalised biological trial.
Labels inherit PL-1326's name-based hypotheses, not botanical ground truth.

All CRPs were hash-checked and installed temporarily with --noWorkshop and
the read-only offline Steam guard. The accepted harness revision was compiled
in this task's isolated blade scratch checkout. `build.json` pins its DLL and
game-assembly hashes. No Workshop CRP, geometry or texture is redistributed.

## Native capture

One slot, 435.54 seconds including launch/teardown, on blade2080Ti.
Fresh Grand River city, paused at midday, day/night off, HUD hidden.
All trees use the same terrain point (0,300), random seed1326 and growth15.
Camera target is exact terrainY+8; distances52/140/550, pitch20/40/40,
yaw0, 1920×1080. Camera convergence was checked before screenshots.
Three anchors have three views; 15 controls have close/gameplay only:39 frames.
Single-tree palettes replace the unphotographed terrain-height pair, then
retarget flushes paused render groups. Every photographed fixture reports
exactly one instance. All39 retained PNG hashes were verified independently.
The supplied sheet crops the common centre only for display, not scoring.

The running controller used a same-byte output-path adapter because Driver.shot
writes stage/shots rather than the output root. Those links were materialised
after teardown and hash-checked. The retained executed-controller source and
adapter receipt document this; the committed controller copies directly.

`native-summary.json` records empty game/Steam/unit cleanup. Board sample
peaks:10821 MiB,131.29 W,68°C, including an existing resident workload.
The game's menu allocation was1622 MiB; its separate peak is unknown.
No shared service or power setting was changed.

## Scoring and limits

After releasing the slot, frozen BioCLIP2.5 ran FP32 on the free blade3090
in54.35 seconds, then exited. The same pinned weights/config and three prompt
templates as the earlier photo/offline check were reused without alteration.
Each full native frame receives the standard pinned preprocessing; the desired
genus's three-way softmax probability is ranked, not its top-1 label.
`ranking.json` retains all36 score vectors, ranks, hashes and loader identity.
Probabilities are conditional on Gleditsia/Tilia/Ulmus, not calibrated confidence.

The result rules out this frozen BioCLIP recipe as fitness on this bench,
not every possible BioCLIP recipe. Background, scale, pose and season remain
possible confounds; they were not tuned after observing scores.
Recommendation: qualify DINOv3 similarity on the same native pool before
any optimisation. Distant crown/colour targets still need whole-crown photo QA.

No paid API calls. GPU/agent/review allocations are unpriced, so this is not
a full dollars-per-asset claim. Eleven unit tests and Ruff pass; the real
native run and hash readback verify capture, not generated-tree quality.
PR106 already conflicts with main; this result does not claim integration or
merge readiness. The native harness used the exact accepted de93357 source,
not an unverified conflict resolution or the older branch's mod build.

Reproduction: build the exact accepted harness checkout, then run
`native_ranking.py plan.json NEW_OUT --harness ACCEPTED/tools/cs1-harness`.
After teardown, run `rank_native.py NEW_OUT NEW_RESULT --weights PINNED --device cuda:0`
in the held vision runtime with the isolated open_clip3.2.0 site.
`ranking_sheet.py RUN sheet.png --font FONT` builds the one-sheet result.
