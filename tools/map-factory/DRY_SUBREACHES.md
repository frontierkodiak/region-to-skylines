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

PL-996 subsequently corrected this attribution: the guard is not proof of an
active intake constraint at this particular oval. See the review correction
below. The distinct Trapicheiros intake91 counterexample remains valid.

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

## Fresh shipping verification · November 16

The shipping writer at **`d5b4a8db0fbc2ae8697422c3e19da1ca5933f3b1`**
was clean for all five actual full runs. Complete Python/Pyodide builds agree
byte-for-byte for all five shipping and all five reference-resource packages,
including Charleston. The browser's dependency list and npm package include
the replay module and input-bound registry. This proposes a shipping change;
accepted main remains `cb5e2a1` until review and landing.

| Map | Fresh game minutes | Required wet-or-near throughout | Remaining failed check |
| --- | ---: | ---: | --- |
| Rio | 60.134448 | 1,531 / 1,556 | flooding |
| Asheville | 60.118892 | 1,261 / 1,261 | none |
| Innsbruck | 60.080003 | 694 / 694 | none |
| Pittsburgh | 60.099170 | 1,799 / 1,799 | none |
| Charleston | 60.146670 | 2,208 / 2,214 | terrain ground truth |

All **30,982 observations / 7,524 required flags** remain unchanged. No required
endpoint or sampled-throughout point is newly lost, and no previously passing
gate fails. Throughout means the thirteen recorded epochs, not every frame.
The unchanged 95% gate is not the stronger pointwise comparison. Both are
recorded. Actual zero/five opening and Areas, selection panel, and sixty-minute
start/overview images were viewed for every map. Rio/Asheville also have the
preceding dedicated short runs; these were not substituted for full runs.

Initial grids and encoded controls match in every run. Every collected raw
terrain dump (zero/five) is exact; there is **no sixty-minute raw terrain dump**.
Measured hydraulic floor equals its target at zero/five. Full original floor
reference exists only for Rio; the other maps' candidate floor is observed,
not declared byte-identical to an unmeasured original full grid. Every encoded
terrain edit is non-deepening, original hydrology/resource arrays are retained,
and all five cleanup receipts are empty.

### Remaining failures and visible limit

Rio flooding is **0.061440 km² against 0.05**, versus the reference maximum
0.060928. Under the identical original flood mask, 45 minutes has 240 cells
versus 238: 224 shared, 16 new-only, 14 old-only. This is not a newly passing
gate or an unchanged numerical result. Full coordinates/depths are retained
in the evidence bundle. Charleston's actual global correlation is **0.6891
against 0.9**; the old extreme-point failures remain. No check or mask changed.
The corrected diagnosis remains source/reference resolution disagreement on
land first, synthetic beds second; matched-reference land and separate-bed
measurement is a steward proposal, not acceptance.

The protected dry Rio Comprido intake basin described above remains visible.
It is not called wet, uncarved, or fixed. The dry-neck improvement and retained
wet opening earn a partial result, **not the claim that every dry bed is gone**.
The steward and Opus must judge this remaining hydraulic-control boundary from
the actual images and intake evidence before landing. No arbitrary head,
reservoir, removed control guard or threshold waiver is proposed here.

`fixtures/active.json` selects a new, explicitly `partial_not_accepted`, versioned
contract under `fixtures/contracts/pl912-native-dry-subreach-v1/`. It binds the
nineteen-file runtime closure, actual game-engine hash, ten complete parity
builds, exact five shipping packages and fresh native receipts. All 147 old
fixture/contract files remain byte-exact `cb5e2a1`; the old `current.json`,
manifest and qualification ledger remain historical. Offline reference-resource
variants share physics but did not receive five extra native package runs.
Strict disableMods/menu, macOS and populated long-term behavior are not newly
qualified. PR42 remains draft; this evidence does not accept PL-912.

## PL-996 review and current-main integration

Opus independently replayed the five native verdicts/audits, confirmed all
nineteen runtime bindings and approved the **partial** baseline except for a
landing blocker: PL-989 had merged to main at `3b5b4c9`, changing the paint
report and resource-plan API. A clean textual merge would crash on the removed
`theme` field. Main was no longer `cb5e2a1`; that earlier statement describes
the old snapshot only.

The branch merges current main without rewriting the reviewed or rejected
history. Runtime checkpoint `e5a3d74` preserves `environment` and `biome` when
replaying the resource plan. The real Rio generation/staging test now runs by
default; it also caught old callers treating `load_plan`'s new tuple as a grid
dictionary. All callers now unpack the plan and preserve its environment.

Ten fresh Python builds prove identical terrain, initial water, hydrology,
resource grids and tree positions to their previous PL-912 builds. The entire
simulation prefix before TreeManager is byte-identical after normalizing only
SimulationMetaData's environment. WaterSimulation is byte-identical without
normalization. Rio changes to Tropical, Innsbruck to North; the other three
shipping packages remain exactly their native-tested bytes. The new two
packages are **presentation deltas**, not newly sixty-minute-tested packages.

The versioned `pl912-biome-delta-v1` contract chains both PL-989's accepted
`fixtures/current.json` and the immutable PL-912 native-baseline contract.
It retains the five actual native package identities, engine hash, observations,
masks, thresholds and receipts; it does not relabel the new package hashes as
the old native runs. Fixture builds execute comparisons against saved native
WaterSimulation bytes and the original resource plans, not just declarations.
No predecessor contract is rewritten by this integration. A fresh merged Rio
zero/five opening+Areas short is required for the steward's visual judgment.

### Residual oval: corrected cause, still not fixed

Native Rio Comprido source163/native164 reports zero flow and zero buffered
withdrawal at all thirteen saved full-run epochs. Using the measured five-minute
floor, availability replay is about −2,000 depth units from five to sixty;
all wet surfaces in its footprint are below target. This is sampled evidence,
not an every-frame or universal inactivity claim. It must not be confused with
the **different**, demonstrably active Trapicheiros source91/native92.

The oval's dry point is also frozen by the native wet-patch guard independently
of its source radius. The adjacent strip still contains 0.16–0.52 m of startup
water at five minutes, then is dry at fifteen through sixty. Removing the intake
guard alone would not restore the point. Clearing that class changes the
five-minute transient-storage rule that repaired Papa-Couve; it is a separate
bounded unit, not an approved control-footprint exemption. Opus recommends the
steward land this partial baseline after the integration checks, retaining the
oval as genuine remaining work. No oval repair or complete PL-912 acceptance
is claimed. The old flood and Charleston failures remain recorded.

### Fresh merged Rio and source-pin ordering

The merged Tropical package `944dfe724e6758289cc0dd860c1591af8c732637281e8d4bd98f1e33160fbf4e`
ran at clean `621f685` for **5.041389 game minutes**. All 4,256 frozen observations
remain: required zero 1,556/1,556, five 1,545/1,556. All eleven five-minute misses
are shared with the reference; none is new. Actual opening and Areas at both
epochs were viewed. Native shore, visible water and the residual oval remain;
the Tropical palette is a presentation change, not a new channel repair.
Initial grids, final short terrain, all 290 controls, hydraulic floor and camera
bindings pass. Cleanup is empty. `fixtures/native-biome-short.json` binds the
raw frames and observations. It does not claim sixty-minute or later-head
native qualification.

A fresh capture of all five live presets exposed a binding-only drift:
Charleston's identical map-editor source pins arrived in a different order.
The input canonicalizer already treats unordered geographic collections this
way; it now also sorts that pin list. Pin **values** remain bound, and the
actual encoded WaterSimulation, grids, nodes and layout are independently bound.
No sparse terrain/water edit or target changes. A mutation test rejects changed
pin coordinates; the complete captured-Charleston export is a fixture regression.
This is not an exemption for physically different input data.

`pl912-biome-delta-v2` chains the prior presentation contract as well as PL-989
and the original PL-912 native ledger. It stores the actual native writer's
original registry and checks every migrated record's edits, targets and all
non-geometry bindings against those bytes. All ten packages remain identical
to the first biome integration, including the exact Rio short package. The
later binding-normalization head is not relabelled as the actual game head.
Future genuine basemap changes still get ordinary **unqualified** preparation;
the live input feed is not persistently monitored by this task.

Final local verification: 83 writer tests (one opt-in skip), eight quick JS
tests, and ten fixture tests executing eleven complete browser exports pass.
The extra export uses the actual newly captured Charleston geometry and
reproduces the native-tested full package exactly. All five freshly captured
PNG/banks/canonical geometry bindings match today. All 207 fixture files from
accepted main remain byte-exact; prior PL-912 versioned contracts and native
receipts are preserved. Only the active pointer advances.

`preflight_merge.py` checks Git's actual trial merge tree against the reviewed
runtime and predecessor contract hashes without changing a worktree or branch.
It rejects the real `b364232` + `3b5b4c9` counterexample that GitHub called clean.
Run it again against freshly fetched main immediately before landing; a clean
textual merge is not source-bound verification. It does not replace tests or
review. No self-merge or complete PL-912 acceptance is authorized by this check.
