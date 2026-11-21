# Square capability model

The inventory is the root `capabilities.json`. Its generated page is
`capabilities.html` in a built preview. The issue tracker owns work and
acceptance; the ledger owns definitions, check locations, evidence and limits.

## Read a square

```sh
node capability-ledger.mjs
uv run --project tools/map-factory python tools/map-factory/capabilities.py \
  /path/to/prepared/export --out /path/to/capability-report.json
```

The check does not write a map or change its inputs. It binds the final native
terrain, initial water and hydrology by SHA-256, and resource plan/package when
present. It reports a deterministic authored-route/corridor witness, geometric
land estimate and comparable stock-map metrics. A planned route is not a native
path. `likely` is not a playable-map certificate, and an absent authored route
means absent **in this plan**, not impossible for every generator.

The initial ship model uses block-min depth on a 64 m grid, four-connected
components, a one-cell shore buffer, separated map-edge endpoints and central
25-tile access. These are provisional modelling choices in the ledger, not
recovered game constants. It does not change `transport_paths.py`, smooth a
route, run the water simulation or certify the generated ship spline. A narrow
route can be missed by conservative coarsening. Version 2 keeps the corridor and
authored route as separate witnesses: either can support a candidate, but neither
proves native navigability. A coarse miss cannot veto an authored route, and a
missing graph cannot establish route absence. A final-plan negative requires
both checks to be present and negative; it is not global impossibility. Browser
negatives remain unknown. Native boundary fitting belongs to the connection
oracle study before any broader promise is promoted.

Version 3 preserves explicit planner opt-outs: `highway_report.ship` or `.air`
equal to `off` becomes `planner_enabled` false in the normalized input. That
capability stays unknown with reason `planner_disabled`, not a negative from an
unattempted planner. This also prevents a stale graph from overriding the opt-out.

The browser core and Python core consume the same normalized schema:

```json
{
  "schema": 1,
  "mode": "export",
  "graph": {"nodes": [], "edges": []},
  "grid": {"size": 2, "spacing_m": 64, "depth_m": [0, 0, 0, 0]},
  "buildable_fraction": 0
}
```

`mode=estimate` means approximate initial terrain/water and mapped transport,
not the final export. Missing graphs are unknown; an explicitly empty final
graph is a negative for authored routes. Missing runway or rail observations
never rule out synthetic routes. Version 4 can emit `promised` only for the narrow
scope `sampled_native_lane_paths_at_opening`, through the exact-context path
below. Geometry and retrospective agreement never promote a promise themselves.

## Against the stock maps, live

The preview adds an **Against stock maps** readout under the icon row. It reads the
one `capabilities.json` `stock_reference` (104 shipped maps, p25 / median / p75)
and the same metric definitions as `survey/measure_maps.py` and the prepared
report, so a square is never scored inside a second catalog:

| Measure | Definition |
|---|---|
| Terrain relief | highest minus lowest terrain over all 1081 x 1081 nodes, in metres |
| Central land slope | median terrain gradient at 16 m spacing over the central 25 tiles' dry samples, in percent |
| Central wet share | share of the central 25 tiles whose water depth is above 0.5 m |

`measureStockMetrics` (JavaScript) and `stock_metrics` (Python) are mirrored
cores; the Python parity test compares their definitions, values and bands on the
five committed prepared fixtures and on a dyadic rounding tie. Bands are strictly
below p25, inclusive typical, strictly above p75: they describe abundance and
interest, not a launch bar.

Pan-time input is the same capture the icon row already fetches, before the
writer's preparation. On the five committed fixtures it reproduces whole-map
relief within 1.1 m and the same band every time. It does **not** reproduce the
other two: Asheville's central land slope reads 11.7% (typical) where the prepared
export is 12.1% (above p75), and Pittsburgh's central wet share reads 0.090 (typical)
where the prepared export is 0.047 (below p25). The capture has carved-bed depth,
not the prepared water level, and it has not had the preparation's terrain edits.

So the live readout compares relief only and leaves central land slope and central
wet share **Not comparable**, naming the gap in each row's detail. Their
comparison is the prepared report's. The policy is `CAPTURE_STOCK` in
`capability-inputs.js`; the fidelity test fails if the measured evidence stops
supporting it. The readout clears on pan, a superseded or failed capture leaves no
band, and its rows take the same hover, keyboard focus and tap as the icons.

## Exact-export native qualification

`check` / `checkCapabilities` accept an optional `export_identity` containing the
exact CRP SHA-256, all three final terrain/water/hydrology hashes, and an explicit
`native_context`: all recorded game-assembly hashes, mod and collector hashes,
and the native protocol. The context must match the recorded controlled
NewGameFromMap/noWorkshop/non-inverted-traffic run, not a strict no-mods run.
Without that identity/context, results stay geometric candidates or Unknown.
Pan-time estimates never carry an export identity and cannot inherit historical
verification merely by sharing coordinates or a place name.

The running executable and game-assembly hashes must be recorded at launch;
the assemblies must agree with build-time references. The executable hash is
bound to the runtime receipt, not compared with a nonexistent build-time exe hash.
The runtime-identity receipt must be a committed repository-relative JSON file,
named by its SHA-256 under `capability-evidence/runtime-identities/`. Ledger
validation reads those bytes and checks their artifact, input and context bindings;
qualification reports expose the locator/hash. A digest with no receipt is rejected.
The v1 study only recorded build-time game hashes. Its nine complete ship/air
control sets remain **blocked qualification candidates**; entry/traffic state is
also unrecorded per run (launch flags alone only establish noWorkshop/noMods): no real certificate
is issued and no real export currently becomes `promised`. Tests of successful
promotion use explicitly constructed launch identities, not game observations.

The prepared CLI computes package/input hashes itself. To request qualification,
pass `--native-context expected-context.json`; it does not automatically select
a context from the evidence. Changing package bytes, any prepared input, game,
mod, collector or protocol prevents promotion. Only ship/air receipts with all
four successful boundary/midpoint direction controls qualify. Missing, failed,
archived/player-modified or partially covered controls do not. The qualifier
also requires a current candidate; a disabled planner cannot be promoted.

This verifies the recorded sampled lane paths **at opening**, not continuous
ship clearance, sustained water, terminal service, landing or takeoff. No road
or rail certificate is issued from the present selected-pair study. Actual
water/start/hookup/intake qualification remains with its owning study.

The preview row clears the previous square at pan start, aborts superseded
requests and rejects late responses. A failed capture leaves Unknown, not stale
green icons. Hover, keyboard focus and tap expose the reason. Its water estimate
uses the input capture's explicit ocean geometry and bank-minus-bed excavation;
it is not the Python preparation's final water or a flow simulation.

`test/capability-browser.mjs` runs on blade in the matching official Playwright
container. Synthetic state/abort/error/layout checks are labelled separately
from real Boston capture and pan checks. Both Chromium and WebKit are required;
the script closes its browsers and local server in `finally`.

## Score the game, without conflating oracles

Each capability's `game_agreement` is an array of observations. A row includes
square settings, `observed_at`, `source_sha` (the exporter revision),
`artifact_sha256` (the exact CRP), `oracle`, `predicted`, `observed`, and an
`evidence` array with raw locators/hashes and limitations. Prediction and
observation may be null. Nulls are unscored, never passes. Record the model
revision/hash with predictions before scoring held-out cases.

Keep `native_panel`, `native_path`, actual service and sustained simulation
separate. A metadata count cannot substitute for a successful game path, and
an initial path cannot substitute for sustained water. The page groups scores
by oracle. Failed inputs, failed runs and missing labels stay visible.

PL-1121 owns the fixed nine-square outside-connection study: the five existing
fixtures, every remaining preset sorted by slug, and central Boston
(-71.057, 42.36), all at their frozen settings. Do not select new squares after
seeing outcomes. PL-1072 owns independent water calibration; PL-1078 owns legal
start/hookup/intake rules and a stock-qualified first-hour player. Fold their
results into this ledger rather than starting parallel live inventories.

## Compare interest, not just feasibility

The fixed v1 outside study is integrated by artifact hash from immutable PR64
source, not by place-name lookup. Regenerate it with:

```sh
uv run --project tools/map-factory python tools/map-factory/integrate_outside_evidence.py \
  /path/to/exact-PR64/tools/map-factory/capability-evidence/outside-v1 \
  --source-commit 4cef6fb620f403c603e597a46f3bb7d7e5feadb7
```

The committed v3 prediction snapshot remains byte-identical to the pre-import
freeze. Current geometry is unchanged; v4 adds evidence qualification, not a
native boundary fit. There are 11 fresh boundary witnesses and 25 unknown cells.
Eight have successful midpoint-only paths, four have only non-exhaustive failed
probes, and thirteen were not requested. Those thirteen are the model-negative
predictions. This is not accuracy; no native negative was established.
Same-role road pairs and generic rail failures cannot prove capability absence.
Diagnostic failures, access legs, archived player runs, panels and prepared-water
raster support remain distinct and cannot rescue one another into a global
verdict. The upstream 619 rows/98 retained raw files remain available unchanged.
All nine water-risk screens are warnings. No threshold or map was retuned.

`node capability-ledger.mjs --refresh-stock` reads the original 104-map survey
(excluding `CO.crp`) and records its hash, sample count, exact linear-interpolated
quartiles and metric units. A changed survey makes validation fail until this
explicit refresh. The historical prose table rounds some quartiles; the ledger
keeps the raw distribution's values.

Reports reuse the survey's central-land/water sampling for comparable resource
coverage, water coverage, terrain relief and median slope, plus total trees.
The tree count is budget-sensitive planted output, not the square's natural
tree abundance; its report records that basis and the page labels it explicitly.
An available CRP supplies its buildable bar and entry counts. The 15-percent
dry-low-slope area is a different measure: it is not compared to that bar.
Below p25 / typical / above p75 is descriptive; more relief, water or trees is
not always better. The ledger carries a launch-bar proposal, not launch approval.

## Verify source evolution

```sh
npm test
uv run --project tools/map-factory python -m unittest discover \
  -s tools/map-factory -p test_capabilities.py
npm run test:fixtures
node build.mjs
```

The UI-only adoption record lives under
`fixtures/contracts/pl1119-capability-ui-v1`. It archives the predecessor's
export-facing UI and pins current added files. All predecessor contracts,
physical writers, package goldens and native receipts remain byte-for-byte
unchanged. After an intentional UI/check change, run
`refresh_capability_ui.py`; it refuses to manufacture or replace a historical
source snapshot. This is source evolution, not new native qualification.
