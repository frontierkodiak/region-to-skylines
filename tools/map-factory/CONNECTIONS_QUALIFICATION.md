# Real-connections CPU cohort (PL-1066)

These are disposable qualification exports, not public shipping approval, native
playability evidence, or a connection-default change. No Steam/game invocation is
part of either command. Inputs, maps, probes and full water-risk reasons stay in
the external output root; no saves, credentials or proprietary binaries belong
in the repository.

## Selection, frozen before export

Use the five existing fixtures unchanged, plus **every PRESETS entry not in that
fixture set**, sorted by slug. At main `4a4ec21` this is Grand Canyon, Hong Kong
and Yosemite. Use their default centre, size and rotation. Do not substitute,
move, or retry squares based on results. The selection includes rugged dry,
subtropical coastal and mountain terrain, but is not a random or climate-balanced
sample and cannot establish global performance. A square without highways,
rail, an in-square captured runway, or a viable start interchange is a result.

The repository contains all five frozen shipping input sets. A local experiment
cache census found no raw `inputs/SLUG/{input.png,geometry.json,banks.f32}` for the
three selected fresh presets, so only those were fetched. Complete cached fresh
captures are reused and hash-checked, never silently recaptured. The selection is
written before capture and refuses changed cohort settings in the same root.

```sh
out=/home/caleb/experiments/PL-1066-qualification
node tools/map-factory/capture-connections.mjs "$out" --plan
node tools/map-factory/capture-connections.mjs "$out" --capture
uv run --project tools/map-factory python tools/map-factory/qualify_connections.py "$out"
```

Optional `--only SLUG...` runs a subset of the frozen cohort, not a different
selection. Use it to export fixture inputs while fresh captures are in progress;
never run two export processes against the same report simultaneously. Existing
exports are retained; regeneration requires a fresh output root.

## Screen every export

`qualify_connections.py` runs the landed `water_risk.assess` on the **final
real-roads-seated native-order terrain**, water and hydrology for every map,
without changed thresholds, per-square overrides or admission fingerprint edits.
`maps/SLUG/water-risk.json` retains all flags, reasons, notes, out-of-range inputs
and model/tool/input hashes; `cpu-report.json` includes the full same assessment.
A preparation/writer failure is retained, and any available grids are screened;
missing grids produce an explicit declined assessment, never a clear square.
Declined outputs do not retain an exported CRP. Warning outputs remain internal
test artifacts, not a bypass of the CLI's public-download review gate.

Successful exports are staged with `soak.stage_prepared`, without a harness.
The staged CRP must reproduce the export SHA; `new_game_panel` expectations are
read from that exact CRP (buildable percentage, all resources and all eight
incoming/outgoing connection counts). Existing fixture probes remain frozen;
fresh squares use explicitly labelled candidate samples plus geographic probes.
Neither probe construction nor metadata equality is native UI/pathfinding proof.

## Optional runway capture (capture only)

`captureInputs(sq, { includeRunways: true })` makes `inputs.js` read OpenMapTiles'
`aeroway` layer, class `runway`, preserving all
line pieces. The longest captured endpoint axis supplies the existing
`geometry.airport` contract, with coordinate tie-breaks independent of tile
completion order and line direction. This is the longest **captured piece**, not
an assertion that a complete airport or its globally longest runway was seen.
No runway means `airport=null`; existing `transport_paths.py` fixture fallbacks
are not changed. A runway outside the captured tile footprint is not fetched.

The option defaults to false. Default captures do not add any runway/airport
keys or provenance, including empty or null values; their byte compatibility
against the archived previous source is independently exercised with synthetic
providers. `capture-connections.mjs` explicitly enables the option for **new**
experimental captures and records it in the capture receipt. App/CLI captures
do not enable it. Real-road generation remains standalone Python tooling, not a
public app toggle or CLI option; `mapgen.js`/`web.py` still use the shipping writer.

The three original fresh qualification captures used the earlier prepared
`b67413b` patch. Both frozen eight-map cohorts retain their original source/input
identities unchanged. This new feature is not a recapture or native qualification
of either cohort, and its opt-in geometry is not claimed identical to that patch.

The requested scope is: “Also capture aeroway=runway in inputs.js if it's still
missing.” Preservation constraints: historical contracts, fingerprints and
receipts stay untouched; both frozen eight-map cohorts remain immutable.
The `pl1066-optional-runways-v1` wrapper archives the exact previous water-risk
contract, active pointer and historical input source. It validates current live
sources and default-capture compatibility separately, then runs all predecessor
checks against their exact source identities. No historical receipt, fixture,
fingerprint, risk rule or native result is relabelled. Both Node fixture builds
and the Python verifier explicitly distinguish archived capture identity from
current compatibility proof; water-risk parity remains mandatory for all ten
reference/shipping byte builds. Synthetic capture equivalence is not live-data
recapture equivalence or native playability proof.

```sh
uv run --project tools/map-factory python -m unittest discover -s tools/map-factory -p test_qualify_connections.py
uv run --project tools/map-factory python -m unittest discover -s tools/map-factory -p test_real_roads.py
```

Render the shareable summary, CPU-only outer-ring content counts, and a manifest
of **unexecuted** native commands using the parent's first-hour-capable harness:

```sh
uv run --project tools/map-factory python tools/map-factory/report_connections.py "$out" \
  --harness-root /path/to/qualified/tools/cs1-harness
```

The manifest keeps the populated `--scenario first-hour --game-minutes 60
--sample-every 5` run separate from the ordinary empty-water calibration run.
It requires resolved Steam readiness and does not itself launch either command.
Both command variants include `--require-offline` and require the parent's
offline-guard-capable harness. That guard must check current Steam evidence,
including a fresh post-queue check on the owning host; wait/retry arguments do
not authorize replaying setup or trusting stale readiness from another host.
Resource/window-capture requirements in staged panel probes are retained; no
visual review is fabricated. Outer-ring counts describe map content, not proof
that vanilla can unlock or play 81 tiles.

## Structural road eligibility and explicit fallback

Real connections remain opt-in. Before ranking start tiles, `real_roads.py`
traverses the directed highway/ramp graph from incoming outside nodes, and
backwards from outgoing outside nodes. A start interchange must contain an
outside-reachable arrival stub and a departure stub that reaches outside, in the
same central-5x5 start tile and within the existing 400 m pairing distance.
Rail, air and ship routes cannot satisfy road access; boundary counts or nearby
but disconnected stubs are insufficient.

`real_roads.road_eligibility` reports `eligible` only for that structural graph
condition. It does not certify terrain buildability, native lane/path behavior,
utilities, first-hour growth or water safety. The CLI JSON, generation receipt
and CPU results prominently retain this state and its witness/reason codes.

For a square without this access, the generic fallback is the explicit
`no_outside_link` state, **not** an invented corridor. A blind straight corridor
on arbitrary mountains/water is not a qualified general solution. Keep the
square, its geometry, reasons and water warnings; do not move or replace it to
improve the cohort result. Internal test exports remain available so native
first-hour construction failure can be observed and reported honestly.

Absent real rail now removes the template railway and its outside buildings;
all native New Game transport counts, including zero, are overwritten from the
authored graph. Prepared probes likewise contain no template routes for a
real-connections package. The existing resource-mask convention is not changed.

### Requalify exact frozen inputs, never recapture

```sh
original=/home/caleb/experiments/PL-1066-qualification
candidate=/home/caleb/experiments/PL-1066-eligibility
uv run --project tools/map-factory python tools/map-factory/qualify_connections.py \
  "$candidate" --baseline "$original"
uv run --project tools/map-factory python tools/map-factory/report_connections.py "$candidate" \
  --harness-root /path/to/qualified/tools/cs1-harness
uv run --project tools/map-factory python -m unittest discover -s tools/map-factory \
  -p test_connection_eligibility.py
```

`--baseline` copies the exact frozen cohort and raw input files, refuses input
conflicts or using the original output as the candidate, and compares complete
CRP bytes plus terrain, water and resource-plan hashes. It never calls a network
capture. Every candidate still runs the unchanged landed water screen on its
final grids/controls, including unchanged packages. Original exports remain
untouched. A byte-identical CRP can reuse only evidence already bound to those
exact bytes; a changed CRP needs new package-bound native qualification. No
CPU comparison fabricates that evidence.
