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

## Runway capture and source contracts

`inputs.js` reads OpenMapTiles' `aeroway` layer, class `runway`, preserving all
line pieces. The longest captured endpoint axis supplies the existing
`geometry.airport` contract, with coordinate tie-breaks independent of tile
completion order and line direction. This is the longest **captured piece**, not
an assertion that a complete airport or its globally longest runway was seen.
No runway means `airport=null`; existing `transport_paths.py` fixture fallbacks
are not changed. A runway outside the captured tile footprint is not fetched.

This additive geometry changes the source-bound `inputs.js` contract. Historical
fixture files and fingerprints must not be rewritten to make tests pass. A
truthful contract adoption must independently demonstrate unchanged historical
shipping CRPs or explicitly qualify the changed output; CPU road exports from
unchanged fixture inputs alone do not prove that fresh recapture equivalence.

```sh
node --test test/runway-inputs.test.mjs
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
Resource/window-capture requirements in staged panel probes are retained; no
visual review is fabricated. Outer-ring counts describe map content, not proof
that vanilla can unlock or play 81 tiles.
