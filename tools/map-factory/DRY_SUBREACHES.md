# Dry subreaches and drained startup film · PL-912

This is the bounded implementation following Opus's PL-990 review of
`a0ff875`. Genuine water may retain CS1 native sandy shore. The target is dry
beds reading as broken water, under every existing gate. No reservoir, supply,
head change, deeper floor or rendering override is included. PL-979 owns the
broader hydraulics/workshop research.

## Corrections to the previous result

The previous short preserved sampled wetness but did not improve central
Areas. Sol incorrectly attributed that visual result to three deferred
pieces. Two are at the far western tile edge; the third is the intake's own
bed, inside its physical radius. Uncarving those does not fix the central view.

Type-1 sources reset their water buffer each source step, then add withdrawal.
The measured buffer of 10 is that step's withdrawal, not a cumulative total.
In the paused reference grid, intake91's wet cells contribute +11 units while
its own dry cell below target contributes −16. Raising that dry cell switches
availability from negative to positive. Both floor and water there must stay
fixed. Independent replay reproduces this counterexample. Most hydraulic-floor
offsets are near network nodes; proximity is not complete attribution proof.

Some early sand can outlive the startup water that produced its initial shore
stamp. Native shore changes by at most −2 or +5 per 1,024 frames. The compiled
shader was not read; PL-974's empirical texture cutpoint is a prediction tool,
not a gate or proof of visible success.

## One generic prepared-map rule

`native_subreaches.py` uses the exact reference package's native grids at five
minutes and every later saved epoch, plus source-bound supplementary shorts.
Startup film can be removed only where **no positive water depth** was seen
in any of those states. Observations and cameras never select cells.

- Eligible lines are existing modeled bank-limited river components and
  feasible streams. Independent major/other lines win overlaps.
- Dry line pixels form eight-connected components across feature boundaries.
  Water within 64 m does not by itself establish a visibly wet bed.
- Python-incision territory lies within three cells and strictly closer to a
  removed line than any retained line. Browser line/polygon cuts are replayed
  from masks, not feature IDs; retained ties and independent lake cuts win.
- Clear never-rewetted film, restore those cut contributions, never lower an
  existing encoded terrain vertex.

These guards freeze **both floor and startup water**: each source's separate
physical intake/output radius, network corridors, lake/ocean ring, and a ring
around measured hydraulic-floor offsets. Radii use encoded rates and native
float32 arithmetic, including dry below-target cells; no extra 32 m blanket.
Every control record remains exact.

Every later occupied-water vertex's one-cell ring also freezes terrain. This
conservatively contains all four-corner native sampling patches regardless of
floor and preserves the recorded flow interface. Where actual floor dumps
exist, `interpolation_support` is checked inside that guard. The other four
reference maps lack full floor dumps; raw-floor replay matches all their frozen
startup ground/surface/wet observations. This is not a full-grid hydraulic-floor
measurement for them. Terrain beside retained startup water is frozen too.

## First five-map CPU checkpoint `74e0e29`

| Map | Raised vertices | Startup cells cleared | Required startup wet-or-near, CPU projection |
| --- | ---: | ---: | ---: |
| Rio | 1,100 | 1,066 | 1,556 / 1,556 |
| Asheville | 7,244 | 5,428 | 1,261 / 1,261 |
| Innsbruck | 2,850 | 2,965 | 694 / 694 |
| Pittsburgh | 3,010 | 1,996 | 1,799 / 1,799 |
| Charleston | 1,249 | 8,731 | 2,214 / 2,214 |

All 30,982 observations and 7,524 required flags remain unchanged. No new
required startup miss is projected. Source-radius floors/water and retained
wet/startup interpolation patches stay exact. Maximum raises are 3 m except
Rio 7.421875 m and Pittsburgh 7.84375 m, removing existing browser cuts as well
as Python incision. Nothing deepens. Resource plans and original hydrology/layout
records remain exact in all five independently decoded packages.

This is an operator prepared-map experiment, **not a production/default or
shipping JS/Pyodide integration**. Exact packages, masks, bindings and the
independent cohort audit are in `fixtures/native-subreach-preflight.json` and
the issue's evidence bundle.

## Falsifiable visible checkpoint

Before launch, the forest-aware PL-974 model used the actual candidate's
encoded shore and terrain. At 18 shore-update sweeps it predicts 285 Rio
resource cells switching from sand-like to non-sand-like, 240 in Areas,
**none in the opening**. Three new sand-like cells are also predicted and
retained in the record. The opening should keep genuine water and native shore,
not become sand-free. All five prediction sheets explicitly mark CPU predictions
on reference images, never rendered candidate evidence.

First obtain actual Rio and Asheville zero/five opening **and Areas**, retaining
their complete frozen cohorts. Check exact grids, controls, cameras, final
terrain, native floor offsets and source flow/buffer regimes. Stop on a passing
gate regression or failure of the predicted visible change. Only then finish
generic Python/shipping JS/Pyodide integration and the evidence contract, prove
exact parity, and run one fresh 60-minute evaluation per map. Short warmups,
old hashes and texture predictions are not qualification.

Rio's original flood failure and Charleston's original correlation/extreme
failures remain. Charleston is diagnosis-only: DEM reference/source disagreement
first, synthetic beds second. No check/mask/threshold edits. PR42 stays draft
pending complete evidence and steward/Opus review.

## Actual first short and the wet-boundary repair

The first arm's Rio package
`f08d8793896a43a64a263f73aff47561136be8a7b547a76a7a1215279a6e2107`
ran at diagnostic head `30686b5` for 5.072778 game minutes. All 4,256 original
observations remained. Required zero was 1,556/1,556; five was 1,544/1,556
(99.2288%, unchanged 95% gate). It passes that published short gate, but the
stronger pointwise comparison finds one new five-minute miss, with all eleven
old misses shared. The opening stays wet; actual Areas shows the predicted
reduction in dry sandy stubs. This is partial improvement, not completion.

The new miss is `geography:Rio Papa-Couve [river] @585,314`, (720, 3616).
The reference is wet at five (about 0.48 m), then dry from ten through sixty.
The candidate keeps its central floor and 103/64 m startup depth, but clears
six neighbouring startup-water cells. The isolated pool starts with 316 depth
units across seven vertices in the reference and only 103 in the candidate.
It drains before five, leaving a dry shore-stamped spot. This is a transient
storage counterexample, not a new 95% threshold failure or a waived probe.

The first implementation froze **terrain** on every later water patch's ring,
but froze **startup water** only inside hard source/network/body guards. That
asymmetry changes the flow boundary. `3ad8f3d` freezes startup water throughout
the same existing native wet-patch guard, without reading a probe or changing
the guard's radius. The regression test preserves the complete local startup
pool while still clearing independent never-rewetted film.

| Corrected CPU preflight | Raised vertices | Startup cells cleared | Required startup projection |
| --- | ---: | ---: | ---: |
| Rio | 1,032 | 336 | 1,556 / 1,556 |
| Asheville | 6,953 | 3,786 | 1,261 / 1,261 |
| Innsbruck | 2,789 | 2,500 | 694 / 694 |
| Pittsburgh | 2,897 | 1,274 | 1,799 / 1,799 |
| Charleston | 1,156 | 2,335 | 2,214 / 2,214 |

Every guarded startup-water and floor value is exact in all five CPU audits;
all observations/flags remain. No floor lowers. The corrected Rio model
predicts 145 sand-like resource cells reducing and one increasing, not the
earlier 285/3 prediction. New exact package hashes are in the corrected
preflight record, not substituted into the old arm's receipts. Fresh native
verification is required before advancing. The first arm remains unpromoted.

## Corrected Rio actual short

Package `3b53842999af4dd23d68c037cb0b80287a45cd2d0c9843ba020a18ff043d1c9c`
ran at `3ad8f3d` for **5.093333 game minutes**. All 4,256 observations remain;
required zero is **1,556/1,556**, five **1,545/1,556 (99.2931%)**. The eleven
five-minute misses are exactly the reference's eleven: no new-only or old-only
miss. Papa-Couve's retained pool is wet at five, depth 0.484375 m. The transient
storage counterexample is repaired without changing any observation or gate.

Initial grids and all 290 controls match; final terrain is unchanged. The 54
native hydraulic-floor offsets match the reference exactly at both epochs;
floor equals target. All 8,512 native ground/surface/wet observations replay
exactly. All ten opening/Areas camera fields match. Actual zero/five sheets
show the retained wet opening and a reduction of dry sandy necks in Areas.
This is a visible short improvement, not a sand-free image or full acceptance.

Protected control basins remain unaltered. One visible sandy oval is inside
Rio Comprido intake163's physical radius, centred near (−416,3296). Dry ground
at (−448,3312) remains about 2.08 m below held banks, exactly as in the baseline;
nearby native water exists but that dry point is not declared wet. The inlet
footprint is intentionally outside the dry-reach restoration domain, not a
newly repaired stream. The raw images retain it for steward visual review.

No 60-minute result, shipping JS/Pyodide parity or new qualification is implied.
The original Rio flood and Charleston terrain failures are not waived.

## Corrected Asheville actual short

The same planner at `3ad8f3d`, package
`43a67e35b22facff7870f365e98cf8fef2d4ad1e4bd82fe5a20b52d7c877802f`,
ran for **5.078889 game minutes**. All 7,745 observations remain; all 1,261
required points are wet-or-near at both zero and five. There are no new misses.
All 110 controls, initial grids, final terrain and opening/Areas cameras match.
The 49 measured native hydraulic-floor offsets lie within the unchanged guard;
all 15,490 native ground/surface/wet readings replay exactly. Actual opening
and Areas frames retain the wet main river and show the dry-reach baseline.
Cleanup is empty. These are two sampled epochs, not wet-throughout acceptance.

## Shipping integration under verification

`wet_reach_admission.py` replays sparse, monotone edits selected by a physical
input fingerprint, never by region name, probe or camera. The fingerprint binds
the heightmap, canonical geographic features, banks, baseline grids, encoded
native water simulation, nodes, start tile and template/layout. Corrupt or
explicitly stale records fail before writing either grid. An unmatched input
keeps ordinary preparation and cannot inherit native qualification.

Resources are first planned on ordinary preparation. Admission then restores
terrain/removes independent startup film, and the same resource arrays and trees
are repacked; resource planning is not rerun on a different floor. The registry
is transformation data, not an acceptance ledger. Every generation receipt
continues to report `in_game_verified: false` and `native_qualified: false`.
Exact Python and shipping Pyodide package agreement, followed by fresh native
60-minute evidence, must bind any new versioned fixture contract. Historical
fixtures and their qualification records are retained unchanged.
