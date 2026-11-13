# PL-912 bounded native opening diagnostic

The bounded diagnostic is complete. The water/default task is not complete.
PR #41 remains draft. The 24 m width arm is rejected.

## Visible result

Asheville's current candidate removes the conspicuous western incision from
the actual opening. That area is grassy at zero and five minutes. A native
hit there is dry ground. The prepared-grid comparison at that hit rises by
about 1.56 m from the accepted fixture. The
French Broad centre is 2.48 m deep initially and 2.64 m at the endpoint.
Actual Areas views were captured too. Other minor-channel scars remain
visible outside the opening; this is not whole-map visual acceptance.

Rio's opening still looks sandy and broken. Native screen-to-terrain hits now
bind the visible centre, both banks and apparent gaps to exact world positions.
The camera reports a 45-degree field of view and a viewport of
`[0, 113.4, 1920, 966.6]` inside the 1920-by-1080 screenshot. Ignoring the
toolbar viewport would misplace the samples. The largest measured pixel
round-trip error is below 0.024 pixel. Camera poses at the screenshots and readbacks
match; the JSON records every comparison and raw native velocity.

The brown centre is not simply dry. Several apparent bank/gap pixels are wet
too. The real outer banks are dry. Colour alone does not identify water depth,
and a positive readback alone does not meet the visibly-wet-bed requirement.

## One width contrast, with the other simulation bytes fixed

The arm compares the browser's 40 m incision contribution with 24 m on the same
game-fitted uncarved DEM and source geometry. It retains later preparation.
It does not claim that the entire finished cross-section is 24 m wide or that
24 m is an observed physical width.

The carver is copied in memory for this diagnostic only. Its 40 m copy must
reproduce the production carver byte for byte. Its positive 24 m delta is
applied to finished terrain, bounded by the held DEM. No cell is lowered.
The production `terrain.js` and its width floor are unchanged.

`width_contrast.py` patches only the encoded terrain arrays in the source
package. Everything after those arrays is copied verbatim, including initial
water, source positions/targets/rates, networks, resources and saved camera.
The resource plan and geometry files are also byte-identical. Only the terrain
and simulation-checksum reference change. Reusing the ordinary writer would
have re-anchored source heights, invalidating this contrast.

The arm changes 36,655 terrain bytes across 29,538 cells, raising terrain by
at most 2.828125 m. It neither resolves the startup appearance nor preserves
all of the baseline's wet centre at five minutes:

| Native image location | Baseline depth at zero (m) | Baseline near five (m) | 24 m near five, same world point (m) |
| --- | ---: | ---: | ---: |
| Horizontal centre, (-1180.00, 3626.06) | 1.000 | 1.703 | 0.391 |
| Elbow centre, (-1309.28, 3581.16) | 0.922 | 0.984 | 0 |
| Diagonal centre, (-1408.15, 3503.74) | 0.969 | 0.938 | 0 |
| Apparent round gap, (-1366.05, 3625.79) | 2.063 | 0.781 | 0.703 |

The native target at source (-1200,3632) stays at 87.953125 m. Its bed rises
from 86.953125 m to 88.890625 m. The control therefore loses its head above the
bed. This supports rejecting a blanket narrowing that also raises the wet floor.
The experiment does not isolate every contributor to the later dry gaps.

The source attribution is Rio Maracanã. The horizontal centre lies 4.9 m from
its surface geometry. The throat is 3.6 m from a tunnel piece and 14.2 m from
an adjacent surface piece. Buffered excavation at short portal gaps therefore
needs attention alongside dry banks. This unit does not change PL-926's tunnel
policy or claim that every visible portal is resolved.

## Proposed next implementation

Keep the established wet thalweg and its control-relative bed elevations.
Restore only unsupported dry excavation margins, including buffered incision
encroaching on underground-only geometry. Derive that boundary from the
pre-export bank-bounded feasible stage and source visibility, not region names,
a guessed universal width, or observed native water as an acceptance mask.
If a reach cannot support a visibly wet footprint, leave it uncarved while
retaining its source geometry and probes.

Test the opening and actual Areas view before launching another full soak.
Do not compensate for the rejected arm by raising heads or deepening the bed.
This is a proposed next step for PM judgment, not an implemented/default fix.
The rejected arm remains diagnostic-only outside the candidate fixtures.

## Exact runs and limits

| Case | Native game minutes | Tested code head | CRP SHA-256 prefix |
| --- | ---: | --- | --- |
| Asheville candidate | 5.053056 | `da50f4e06ab659077dc82f283f96a4935b751feb` | `745b043a0b92` |
| Rio 40 m baseline | 5.013889 | `a73aa18f8c4894e6c879cbc303fd9d0a92c3ba13` | `4bc5628e6af2` |
| Rio 24 m diagnostic | 5.082222 | `da50f4e06ab659077dc82f283f96a4935b751feb` | `1dc38d543645` |

All three use the same native probe DLL, SHA-256
`b8ffb378a57c0e5303b5207f28601eeef0b8b9d6e3ae10b0caa0242f120221f6`.
The later head adds fixed-request replay and the width builder; it does not
change the native probe or production hydrology. Accepted silence main
`e5b21f2435c78cb94fb337a320ba5b70c095acc5` is integrated.

The summary in `fixtures/minor-stream-candidate/native-diagnostic.json`
contains full package/grid/image hashes, exact camera poses, all point and
velocity readbacks, the width recipe, GPU samples and cleanup receipts.
Both initial grids match their exact candidate/diagnostic packages. Native
terrain remains unchanged through the five-minute runs.

Three preliminary attempts stopped on driver problems: a Flatpak path alias,
a clock-field lookup and an overly strict 0.02-pixel assertion. All raw hits
are now retained, and all final bindings pass a half-pixel round-trip check. All six
session attempts fully cleaned up. The successful results above are not
inherited from the failed attempts.

Full opening and Areas screenshots are retained at zero and five minutes.
Native guide popups obscure part of the five-minute Areas view, so that view
alone does not establish unobstructed whole-tile coverage. No camera override
was used for these captures. Full car/train paths, 60-minute stability and the
other three regions were not tested in this unit. All five changed default
candidates still require fresh 60-minute receipts. Rio's accepted flood subset
and Charleston's terrain-correlation subset remain in `NATIVE_FINDINGS.md`.

## Reproduction and lifecycle

The PM release covered this bounded diagnostic only. A future run needs its
own applicable release and the normal free harness slot. From the repository
root, the recorded commands are:

```sh
uv run --project tools/cs1-harness cs1-harness build
uv run --project tools/cs1-harness cs1-harness doctor
uv run --project tools/cs1-harness python tools/map-factory/native_opening_diagnostic.py "$CANDIDATES/rio" "$OUT/rio-40" --interactive
uv run --project tools/map-factory python tools/map-factory/width_contrast.py "$CANDIDATES/rio" "$OUT/rio-24-input"
uv run --project tools/cs1-harness python tools/map-factory/native_opening_diagnostic.py "$OUT/rio-24-input" "$OUT/rio-24" --requests "$RIO_REQUESTS"
uv run --project tools/cs1-harness python tools/map-factory/native_opening_diagnostic.py "$CANDIDATES/asheville" "$OUT/asheville" --requests "$ASHEVILLE_REQUESTS"
```

The requests, receipts and zero/five-minute grids are delivered in the native
readback archive on PL-912. Raw view archives contain the original PNGs.
Montages add labels and cropping only, not synthetic or retouched game content.

Checks completed: installed-game build, doctor, 112 harness tests, harness lint
and format, and direct native projection, byte-identity and lifecycle checks.
The production candidate grids and writer inputs are unchanged, so the earlier
five-map Python/Pyodide parity result still applies. Accepted-golden tests were
not promoted or rerun for these diagnostic-only changes.

The full process-tree audio checks covered Steam, late webhelpers, Cities and
descendants, including resolved namespace socket identities and physical audio
file descriptors. No route violation occurred. Every session used Blade's
2080 Ti at 05:00.0 and private Xvfb :57. No :0, host mixer/service, permissions,
power settings, test tone or play-here operation was used.

Independent final cleanup found no game, Steam instance, marked audio process,
private display/bus socket, session state/environment/audio directory or active
harness unit. The slot is free. No owned work continues after this handback.
