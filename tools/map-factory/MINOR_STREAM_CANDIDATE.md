# PL-912 CPU candidate

Historical CPU-stage notes below. Current byte conformance uses the explicit
[partial contract](CURRENT_FIXTURE_CONTRACT.md); fresh native evaluation is in
[PARTIAL_NATIVE_QUALIFICATION.md](PARTIAL_NATIVE_QUALIFICATION.md). The old accepted
files below remain history, not the current expected default bytes.

This candidate starts from `c6ab58a`, the accepted PL-926 main. It has no native
qualification. Do not merge or publish it as an accepted default yet.

## Rule and remaining defect

`region.hydrology` already rejects a minor stream's monotone profile when it
exceeds the uncarved bank ceiling by more than 1/64 m. Previously that stream
still received excavation, startup water and intake controls. The candidate
leaves such reaches uncarved, without startup water or controls. It retains
source geometry, reach sample groups and geographic acceptance masks.
Feasible streams, major rivers, incision limits and acceptance thresholds keep
their existing rules. The input tunnel exclusion from PL-926 is unchanged.

The CPU terrain comparison removes Asheville's conspicuous western creek cut.
Rio's opening neighborhood does not change. Its nearby canals are source
`rivers`, not the rejected `streams` this rule handles. This candidate therefore
does **not** establish a fix for Rio's opening scar. Diagnose that remaining
river-class channel rather than calling the stream-only rule a complete fix.
The [Rio opening diagnosis](RIO_OPENING_DIAGNOSIS.md) records the continuation:
two sampled source-line sections are already wet in the accepted native run,
and polygon absence cannot safely classify physical channel size. No further
production rule was selected without the matched native diagnostic.

## Candidate bytes

The compressed terrain, water and hydrology outputs are in
[fixtures/minor-stream-candidate](fixtures/minor-stream-candidate/manifest.json).
The manifest binds each shipping CRP and both grids, records changed byte and
cell counts against accepted fixtures, and lists network grades. All five maps
change. All five need fresh native receipts, not only Asheville and Rio.

| Region | Rejected reaches left uncarved | Changed terrain bytes | Changed water bytes |
| --- | ---: | ---: | ---: |
| Asheville | 93 | 111646 | 29601 |
| Innsbruck | 59 | 75075 | 21871 |
| Rio | 6 | 3979 | 1367 |
| Pittsburgh | 37 | 33364 | 7228 |
| Charleston | 11 | 5264 | 5828 |

Candidate generation asserts unchanged starting tiles, retained sample-group
keys and unchanged horizontal road and rail node coordinates. Node heights
adapt to restored ground. Additional cuts can change where overlapping feasible
reaches or network earthworks are recomputed. The incision limit is not raised.
No initially wet mapped river cell becomes dry. This is an initial-grid check,
not a prediction of flow or flooding.

The decoder checks the actual CRPs against the terrain and water files, node
positions, and template topology and lane bytes. Python and the shipping
JavaScript/Pyodide path reproduce all five full packages byte for byte.
PL-858 is complete and uses this same Python implementation through `mapgen.js`;
there is no separate JavaScript hydrology implementation to patch.

The accepted fixtures, `native-qualification.json` and `NATIVE_FINDINGS.md` stay
unchanged. Existing golden-fixture tests must not accept these new default
bytes until qualification. The candidate parity command below checks CPU
reproduction only and does not replace that gate.

## Reproduce without the game

Run from the repository root:

```sh
PL912_OUTPUT="$HOME/experiments/PL-912-minor-streams"
uv run --project tools/map-factory python tools/map-factory/minor_stream_candidate.py "$PL912_OUTPUT"
node tools/map-factory/verify-candidate.mjs "$PL912_OUTPUT"
uv run --project tools/map-factory python tools/map-factory/soak.py "$PL912_OUTPUT/staged" --prepared "$PL912_OUTPUT/inputs"
```

The first command generates shipping maps from verified pinned inputs, candidate
fixtures and `before-after.png`. The PNG shows prepared terrain and water around
the starting tiles. It is not a game capture. The third command stages maps and
probes without launching anything because it has no `--harness` argument.

Verification completed: 39 writer tests with two opt-in skips, six JavaScript
unit tests, nine input/evidence tests, static build, lint on changed Python,
actual CRP decoder checks, offline staging and five full-package Pyodide matches.
The regression test fails against the baseline on 1050 changed terrain cells
and passes against this candidate.
`FIXTURES=rio npm run test:fixtures` fails both accepted-golden comparisons on
the changed package length, 6143919 versus 6182876 bytes. The native record was
not rewritten to make that gate green. The other accepted-golden cases were
not run; candidate byte parity covers all five regions separately.

## Native work remains gated

The [bounded native diagnostic](NATIVE_OPENING_DIAGNOSTIC.md) is now complete
under a specific PM release. That release did not authorize the five-map
qualification sweep. The full soak command below still requires a future
explicit release; none of the candidate defaults is newly qualified.

Do not launch Steam or CS1 until PL-933 isolation is independently accepted and
the PL-932 PM explicitly releases the game work. Use the accepted silent harness
revision and the one harness queue slot, not an arbitrary checkout's launcher.
After that release, the foreground soak command is:

```sh
uv run --project tools/map-factory python tools/map-factory/soak.py "$PL912_OUTPUT/native" --prepared "$PL912_OUTPUT/inputs" --harness "$PL933_ACCEPTED_HARNESS" --game-minutes 60
```

Review actual untouched opening and actual Areas images, especially Asheville
and Rio. Retain initial and 60-minute grid receipts and all car and train paths.
If Rio still floods, identify the western pools' feed with matched short soaks
before retuning any controls. Rio's accepted 0.062464 km² flood failure and
Charleston's terrain-correlation failure remain in `NATIVE_FINDINGS.md`.
No CPU result here changes either finding. Verify complete owned-session
cleanup and leave no game, Steam, display or bus process behind.

## Bank-restoration follow-up

The post-diagnostic bank-restoration arm was rejected after native interpolation
raised a previously wet off-grid bed. It is quarantined, not a new default.
See [the failure and next correction](BANK_RESTORATION.md). Default candidate
writer/grids remain the `690d2b1` candidate; all five still need fresh full
qualification.
