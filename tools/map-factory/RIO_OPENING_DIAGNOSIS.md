# Rio opening channel diagnosis

This is a CPU-only analysis of the accepted PL-926 archive, not a new native
run or qualification of PR #41. The source match is Rio Maracanã's short
surface leg near `x=-1504 to -1360 m, z=3456 to 3584 m` and the adjacent leg
near `x=-1312 to -560 m, z=3632 to 3696 m`. Tunnel pieces separate these legs.
Their shape and position match the right-edge channel in the opening view.
The archived camera does not record its field of view, so pixel-perfect
screen-to-ground attribution remains unverified.

## What the archived grids establish

The analysis verifies the archive's CRP identity against
`fixtures/native-qualification.json`, its initial terrain and water against
accepted hashes, and its opening PNG against the accepted view review.
The baseline CRP is
`d1c6238fd6bf2bc8b152212cb79029f89570b3df7052bd9ab30733ac1d5c7258`.

Two source-line cross-sections near the visible channel retain water through
the saved native grids, despite the sandy appearance:

| Native x,z (m) | Uncarved height (m) | Browser bed (m) | Prepared bed (m) | Initial depth (m) | Native 60-minute depth (m) |
| --- | ---: | ---: | ---: | ---: | ---: |
| -1280,3632 | 92.878 | 86.939 | 86.938 | 1.000 | 1.594 |
| -1200,3632 | 93.310 | 86.954 | 86.953 | 1.000 | 1.469 |

At `x=-1280, z=3648`, one cell north of the first sample, the native minute-60
depth is zero. At `z=3616`, one cell south, it is 2.953 m. A dry sample beside
the source line is therefore not proof that this whole excavated channel is
dry. Nor do these wet sections prove continuity along the entire reach.

The browser has already excavated nearly six metres at these source samples.
Python preparation changes their beds by less than 0.002 m. In `terrain.js`,
`carveWater` uses a minimum half-width of 2.5 native cells, or 40 m. Its
nominal minimum cut footprint is 80 m wide before smoothing, independent of
actual channel width. That explains why changing only Python's stream
excavation leaves this river-class scar intact.

## Why no new production classifier was chosen

The strongest explanation is an oversized excavated bank around a wet narrow
channel. A second explanation is shallow or transparent rendered water that
looks like exposed bed. Local dry gaps elsewhere in the visible reach also
remain possible. The existing opening capture and point samples do not
separate all three explanations.

The current source capture has no measured channel-width field. Polygon
absence cannot substitute for width: only 12.4% of Rio Maracanã's retained
source-line cells overlap a mapped river area, but the accepted Ohio River has
even less overlap, 6.7%. Treating polygon-poor rivers as minor streams would
risk actual major rivers. A bank-limited monotone fit likewise identifies a
DEM/model conflict, not a waterway's physical size.

For that reason, this continuation does not add a guessed small-river rule,
raise source heads, deepen incision, relabel rivers or remove probes. PR #41's
stream-only candidate remains partial and unqualified.

## Smallest matched native diagnostic after release

PL-933 acceptance and explicit PL-932 PM release remain prerequisites. Nothing
in this document authorizes a launch.

1. Load the exact current Rio candidate with the accepted silent harness and
   capture its untouched opening and actual Areas view while paused. Bind the
   sandy centre and both banks to native positions, with a readback of the
   actual camera projection or terrain-hit coordinates. The existing archived
   camera lacks the field-of-view value needed for exact pixel binding.
2. Sample exact water depth and velocity across the two cross-sections above,
   including `z=3600,3616,3632,3648,3664` at each x. Retain full native grids at
   minute zero and five and take the same fixed-camera images. The existing
   `water` op accepts these points and reports native depth and velocity.
3. If the visual scar is exposed excavated banks around a wet channel, compare
   a single terrain-only narrower-cut arm against that baseline for five game
   minutes. Use the same source geometry and uncarved DEM. A 24 m half-width is
   a diagnostic contrast to 40 m, not an inferred real width or new default.
   Keep source controls, initial water, network geometry and resource plan
   byte-identical. Do not change geographic masks or acceptance thresholds.
   If the centre itself is dry instead, first locate its crest and feeding
   control; do not treat the bank-width arm as a supply fix.

Changing `CAPTURE.riverHalfWidth` alone cannot construct the narrow arm because
`carveWater` enforces the 40 m floor. The diagnostic generator must explicitly
bypass that floor, then prove that only the terrain component changed.

This sequence first distinguishes wet rendered bed from genuinely dry cells.
The conditional two-arm comparison then isolates excavation width without
confounding source tuning. It does not replace any 60-minute qualification.
Every grid changed by PR #41 still requires a fresh native receipt.

## Reproduce the analysis without the game

From the repository root, use the accepted PL-926 archive as `NATIVE_ARCHIVE`:

```sh
uv run --project tools/map-factory --with matplotlib python tools/map-factory/diagnose_opening_channel.py "$NATIVE_ARCHIVE" "$DIAG_OUTPUT" --slug rio --waterway 'Rio Maracanã' --section-x-m -1280 -1200
```

The command writes `opening-diagnosis.json` and `opening-diagnosis.png`.
The JSON contains input hashes, camera data, source profiles, point series,
cross-sections and the five-region polygon-support catalog. The figure
combines the unchanged accepted screenshot with native-grid plots. Neither
artifact is a new game capture. The checked-in JSON is in
`fixtures/minor-stream-candidate/rio-opening-diagnosis.json`.

## Source and candidate checks

GitHub's main ref and `git ls-remote` both resolve to
`c6ab58a6b0ebc178310e1facdf636ec4b8c8731d`. The PM-mentioned `d750736` is an
ancestor of that commit, not a newer main. PR #41 already contains those
accepted harness fixes. No replacement branch or unrelated source was used.

All five candidates were regenerated. Their grids and compressed hydrology
fixtures are byte-identical to the first candidate, and their manifest values
are unchanged. This is fresh CPU reproduction, not a new terrain fix. The
accepted fixture history, PL-926 tunnel policy, masks and native failure
subsets remain unchanged.
