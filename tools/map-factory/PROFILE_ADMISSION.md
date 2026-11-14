# Rio profile-admission experiment: rejected

The opening scar disappears in actual zero- and five-minute game captures, but
the generic omission rule breaks the unchanged river-wetness gate. **Do not
promote it.** The shipping writer, its JavaScript packaging and all historical
fixture/qualification files remain byte-identical to main `cb5e2a1`.

## What the experiment establishes

The rule selects finite surface connectors whose two exact source endpoints
join explicit underground pieces, and whose uncarved-DEM profile cannot fit
the existing 3 m incision, 1 m headroom and 0.25 m freeboard bounds in either
direction. It does not select by region name, camera position or observation.

Unlike the previous rejected coupled arm, this replay removes both line and
attributable polygon incision. It keeps independently supported lake/retained
line contributions, source geometry, every frozen observation and the original
starting tile/horizontal network layout. Omitted reaches receive neither new
excavation, supply controls nor an artificial startup film.

Rio selects 14 routed connectors / 16 source pieces. Browser-cut restoration
raises 6,489 vertices and defers 57 polygon vertices. At the original opening
control `(-1200,3632)`, prepared ground becomes **93.3125 m**, matching the held
uncarved DEM at native precision, instead of the previous **86.953125 m** bed.
Starting tile remains **21**, and no horizontal network node moves.

| Evidence | Result |
| --- | --- |
| Actual untouched opening and actual Areas, zero/five minutes | Target connector is gone; its former bed is grassy. Other scars remain. |
| Fixed native observations, zero/five minutes | Former channel is genuinely uncarved dry ground, not a hidden water film. |
| Camera identity | Both epochs match the prior run's position, size, heading, render position and basis exactly. |
| Short native run | **5.033056 game minutes**; initial terrain/water match the candidate; final terrain is unchanged. |
| Unchanged required river probes, subsequent native startup | **1,301 / 1,556 wet or natively within 64 m = 83.6118%, below 95%.** |
| Prior required wet-throughout result | **1,531 / 1,556 = 98.39%**, passed. |
| Five-map generation | All five built with the same rule and retained layout. Only Rio's package changes from the currently shipped stream-only cohort. |
| Candidate Python/shipping-JS/Pyodide agreement | Asheville, Innsbruck, Rio and Pittsburgh verified; Charleston not verified. An incomplete-manifest first pass covered four cases; the subsequent five-case replay was cancelled after rejection. |
| Fresh 60-minute qualification | **None.** Rio was deliberately stopped after the first native sample proved an irreversible wet-throughout regression. Other four runs were not launched. |

Native candidate CRP SHA-256:
`8d0828ea83515db2aa4de2706ce047914555e35fd43d43b21c1b239e7998e3eb`.
Its initial terrain is `f162bb2cc4022a6a3e4a3eef8f8fccdb07c566b9d4db495ee27859f95c6238c4`;
initial water is `84d914048cbf833c37d2634c36f32160d6fdcabadedf58203ae2a0e47c1ad2c3`.
The short driver records head `5d207d2`; the clean rejected implementation
checkpoint and the subsequent startup evaluation are `76baf94`. Later source
changes quarantine the proposal, not a new package qualification.

The stopped evaluation's raw harness verdict says `error`; its generic triage
says `game-crash`. The operator issued `call quit` after proving the startup
regression. **That is an intentional stop, not evidence of a spontaneous crash.**
The separate startup audit binds the package, both native grids, every probe
identity and raw timeline to the numerical rejection. No raw receipt is edited.

Steam cloud sync blocked the first short attempt; no prompt was answered. Its
own log subsequently recorded a successful sync, and the retry loaded normally.
All three owned native attempts have empty cleanup receipts. No game, Steam,
display, bus, audio session or detached evaluator remains.

## Why this is not the next default

A failed *global gravity profile* does not establish that an already locally
regulated connector cannot retain water. This rule omits too much: it restores
the desired opening terrain but removes water at 230 more required locations
than the previously passing cohort. The full observed dry-name list remains in
the delivered startup audit. Do not fix that by deleting probes, treating these
rivers as exempt streams, reducing thresholds or selecting only the opening.

The next design must distinguish a supported local-stage channel from an
unsupported excavation **before** both line and polygon cuts, and retain
continuous native interpolation support and regulator headroom where it keeps
a wet channel. It must pass the complete frozen point cohort during the short
visible test before a full sweep. The current rule is a falsified premise, not
a narrowly missed tolerance.

The archived production proposal is
`fixtures/admission-rejected/production-proposal.patch`. It is review material,
not applied source. The builder refuses the restored default writer rather than
silently regenerating another implementation. Reproduce the experiment in a
separate worktree at immutable source `76baf94`, not by editing main.

## Charleston: bed modeling and reference resolution, not orientation

The separate diagnostic replays **73,441 identical 64 m sample positions**.
It does not change the original global check, its threshold or any mask.

| Contrast | Correlation |
| --- | ---: |
| Current prepared bed vs checker's zoom-13 surface DEM | **0.689014** |
| Browser input, before Python preparation, vs same DEM | **0.688253** |
| Restore only lake-polygon beds to uncarved heights, diagnostic only | **0.698731** |
| Uncarved fitted banks vs raw zoom-13 surface DEM | **0.570935** |
| Uncarved banks vs zoom-13 DEM with the same explicit ocean-bed model | **0.938942** |
| Uncarved banks vs capture's zoom-14 DEM with the same ocean-bed model | **0.998551** |
| Prepared bed vs raw zoom-14 DEM | **0.750050** |

Thus tidal-lake excavation is a substantial local error, but restoring it alone
does not fix the global correlation. The checker compares a deliberately
modeled underwater bed (including ocean fitting) with a surface DEM, at a
different resolution from capture. The same-ocean, same-resolution contrast
strongly supports correct source-frame alignment; it is **not** a replacement
acceptance score or proof of natural bathymetry. The earlier Charleston extreme
points and outside-water errors remain recorded in `TERRAIN_LIMITATIONS.md`.

Recommended follow-up: model tidal/coastal beds explicitly instead of using a
connected lake's minimum DEM height, and separately validate terrestrial
elevations against a matched-resolution independent reference. Keep the current
0.9 global failure visible until any replacement measurement contract is
explicitly reviewed; do not recast the diagnostic contrasts as passes.

## Reproduction and review evidence

The issue attachments carry the phone-readable native sheets, uncropped images,
exact input/observation receipts, aborted-run receipts and Charleston arrays.
No local path is a deliverable. To replay the numerical audit against those
downloaded directories:

```sh
uv run --project tools/map-factory python tools/map-factory/audit_admission_startup.py RUN PREPARED startup-audit.json
uv run --project tools/map-factory --with pyproj python tools/map-factory/diagnose_terrain_stages.py charleston PREPARED charleston-stages.json
```

The proposed writer passed 47 Python tests (two opt-in skips), including three
new admission tests; those tests did not substitute for the failed native gate.
The final quarantined tree passes all eight JavaScript tests and 44 writer
tests (two opt-in skips); the unchanged harness passed 113 tests, build and
doctor. Historical Rio flooding **0.060928 km²
against 0.05** and Charleston correlation **0.6890 against 0.9** are not newly
qualified or repaired. Strict-disableMods/menu, macOS, populated and long-term
behavior were not tested.
