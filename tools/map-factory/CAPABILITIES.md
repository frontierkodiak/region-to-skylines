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
| Terrain roughness | mean terrain gradient magnitude at 16 m spacing over all 1081 x 1081 nodes, in percent |
| Central height range | 90th minus 10th percentile of terrain height over the central 25 tiles' nodes, in metres |
| Central land slope | median terrain gradient at 16 m spacing over the central 25 tiles' dry samples, in percent |
| Central wet share | share of the central 25 tiles whose water depth is above 0.5 m |

`measureStockMetrics` (JavaScript) and `stock_metrics` (Python) are mirrored
cores, and both import the same two terrain-shape definitions from
`terrain_interest.py`; the Python parity test compares their definitions, values
and bands on the five committed prepared fixtures and on a dyadic rounding tie.
Bands are strictly below p25, inclusive typical, strictly above p75: they
describe abundance and interest, not a launch bar.

Pan-time input is the same capture the icon row already fetches, before the
writer's preparation. On the five committed fixtures, including the two
non-default height fits (Innsbruck 0.447x, Rio 0.920x), it reproduces whole-map
relief (within 1.1 m), terrain roughness (within 0.39 percentage points) and
central height range (within 0.5 m), with the same stock band every time. It does
**not** reproduce the other two: Asheville's central land slope reads 11.7%
(typical) where the prepared export is 12.1% (above p75), and central wet share
crosses a band on Charleston, Pittsburgh and Rio. The capture has carved-bed
depth, not the prepared water level, and it has not had the preparation's terrain
edits.

So the live readout compares relief and the two terrain-shape measures, and
leaves central land slope and central wet share **Not comparable**, naming the
typed reason in each row's detail. Their comparison is the prepared report's.
The policy is `CAPTURE_STOCK` in `capability-inputs.js`; the fidelity test fails
if the measured evidence stops supporting it. A capture that is not the full
1081-square terrain/depth pair is Not comparable as well, with reason
`capture_grid_fidelity_mismatch`.

### Terrain-shape interest, from the shipped maps

`terrain_interest.py` holds the two terrain-shape measures; `measureStockMetrics`
(JavaScript) and `stock_metrics` (Python) are their two readers. Both measure
terrain shape over all nodes, waterbeds included; neither reads a water mask, a
dry filter or a buildability threshold. Heights are quantized to the game's
1/64 m unit before measuring, and the central window is the same 25-tile node set
the land measures already use.

`survey/measure_terrain_interest.py` reads the 105 CRP files in the game's Maps
folder read-only, sorted and SHA-256'd, and writes the new
`survey/terrain-interest.json` artifact. It records the exact file names and
hashes, package and data versions, the reader and measure-source hashes, the one
exclusion (`CO.crp`, a blank editor system package), failures and all 104
measured rows. It never rewrites the historical basemap survey. Quartiles use the
ledger's linear `(n-1)*p` policy over the included rows.

`capability-ledger.mjs` re-derives the quartiles from the artifact's rows and
re-hashes all three bound tools, so a stale artifact or survey fails
`validateLedger` instead of being cited. `capabilities.json` carries the
definitions, source manifest, row digest, quartiles, comparability policy and the
measured evidence on the five committed squares; the ledger page serves the
artifact beside itself. The launch-bar proposal keeps both measures descriptive:
terrain roughness and central height range belong in the context shown at launch,
not in a pass/fail gate. A central flat-terrain share was measured and set aside
because it reads as buildability and sits close to a stock quartile at capture
fidelity.

A prepared report carries a separate `stock_measures` block, apart from the
three physical input hashes and the native/exact-export identity: the actual
`terrain_interest.py` helper and `survey/measure_maps.py` reader/predicate bytes
the report read, validated against `capabilities.json`'s declared stock study,
plus the ledger, artifact and row digests. Changing either dependency refuses
the report with the changed digest instead of returning a number under the old
fingerprint. The regression in `test_capabilities.py` starts a fresh interpreter
per case and mutates the real file in an isolated copy.

Regenerating the survey means the full command in `survey/README.md`, followed by
`node capability-ledger.mjs --refresh-stock`. The readout clears on pan, a superseded or failed capture leaves no
band, and its rows take the same hover, keyboard focus and tap as the icons.

## Vegetation and resources, live

The Trees and Resources icons are a place-evidence candidate model, not the
export plan. Both cores read one normalized `place` block on the same 271-node
(64 m) lattice as the depth grid: `terrain_m`, `landcover.values`, and
`deposits.records`. `capability-model.js:placeCapabilities` and
`capabilities.py:place_capabilities` are mirrored; the Python parity test
compares them byte for byte on constructed evidence and both parsers on a real
MRDS response.

| Evidence | Read at pan time | Read at export |
|---|---|---|
| Land cover | ESA WorldCover 2021 v200, the overview nearest the 64 m lattice, bounded to 262144 pixels per tile, sampled at the lattice nodes | the writer's own 1728-square 10 m `landcover.u8.gz`, sampled at the same nodes |
| Deposits | USGS MRDS for the square's bounding box (the same browser reader the download path uses) | MRDS, MSHA Mines and NETL WELLS through `evidence.py` |
| Terrain | the capture heightmap, for the tree-brush slope screen | the prepared terrain |

Definitions and thresholds live in `capabilities.json:model_rules.place`; the
tree and fertile weights are asserted equal to `resources.TREE_WEIGHT` and
`FERTILE_WEIGHT`, and the slope cuts to `resources.py`'s own taper, so the live
model cannot drift from the writer silently.

- **Trees** weighs WorldCover classes by the writer's own tree weights and
  multiplies by the game tree-brush taper (full below 40 percent slope, zero at
  50 and above). It reports tree-cover share, vegetated share and a weighted
  suitability over the central 25 tiles' dry land. It does **not** report the
  exporter's planted tree count: 180,000 is a budget, not natural abundance.
- **Trees never assert a No from place evidence.** The 0.05 suitability level
  is a candidate threshold, not an impossibility boundary: a 90 percent covered
  window is not complete coverage, and a 74 m overview can miss thin patches.
  At or above it the icon is Maybe; below it, or with no tree-supporting cover
  in the sample, it stays Unknown with the measured scope named. Only the
  export plan's own empty tree list is a No, and that observation stays
  separate (`final_plan_empty`).
- **Resources** reports recorded deposits and fertile cover separately. A
  deposit record in the central tiles, or fertile land at or above the candidate
  threshold, makes a Maybe. The detail reports cropland share on its own, apart
  from the weighted crop, grass, wetland and shrub suitability, so grassland
  never reads as "crop cover". Below-threshold fertile support is Unknown, not
  absent. Balanced ore/oil top-ups fill each export to stock shares after this
  evidence is gathered; they are not evidence and never count here.
- **Never a No for resources.** MRDS has worldwide legacy records with a U.S.
  focus, uneven completeness and potentially outdated operating information
  ([USGS catalog](https://data.usgs.gov/datacatalog/data/USGS%3A5d712a5ae4b0c4f70cfd4e54)).
  The exporter's other sources are not queried live. A missing record is not
  absence. The live check returns `unknown` where it cannot tell, and the reason
  says what was sampled. The inherited `evidence.py` U.S.-only docstring is not
  a coverage guarantee; its MRDS query has no U.S. gate. Physical writer bytes
  and their historical contracts are unchanged by this metadata correction.
- **No stock comparison.** The 104-map catalog measures the game's planted
  forest bytes and budgeted tree counts. WorldCover tree cover is not either
  quantity, so no bridge is claimed and no stock band is attached. The ledger
  records this as the reason rather than showing a made-up band.

### What the pan-time read costs

Measured once per square on the five committed squares from carbon: three or
four HTTP range requests, 197 kB to 459 kB, 0.30 s to 0.95 s for land cover, and
one MRDS request at 0.19 s to 0.37 s. The chosen overview was 73.7 m per pixel at
four squares and 36.9 m at Rio. The read is bounded, cancellable, and runs in
`capability-evidence-worker.js`, which the view terminates on pan.

`captureEstimate` gives those optional reads a 15 s wall-clock budget. Every
parallel read gets its handler before the terrain capture is awaited, the
budget aborts the evidence controller (which terminates the worker and the
request), and the terrain-backed icons and stock rows still render with
unavailable evidence. A caller abort rejects once, with no unhandled evidence
rejection and no process or worker left behind.

### What it is worth

The 271-node lattice reproduces the central window's 10 m WorldCover shares
within 0.0022 absolute on all five committed squares for tree cover, crop cover
and vegetated share, while reading 2.4 percent of the cells. The overview read
used at pan time stayed within 0.036 of that 10 m tree-cover share, 0.003 on crop
and 0.011 on vegetated share, and found no no-data cells. The lattice check runs
in `test_capabilities.py`; the overview comparison needs the network and is
recorded in `CAPABILITIES.md` and the run receipt, not as a test.

Neither number makes this a plan or a native check. Patch coherence, the tree
budget, balanced top-ups, reserve size and gameplay remain outside it.

### Evidence input binding

`assess_prepared` reports `evidence_inputs`, one entry per place-evidence file
the report consumed: `landcover` (`landcover.u8.gz`) and `deposits`
(`evidence.json`), each with `status` `present` or `missing` and its SHA-256 when
present. They are kept out of `inputs_sha256`, whose three physical inputs are
what a native path certificate binds. Changing only land cover or only deposits
therefore moves its own binding and can move the Trees or Resources level,
without appearing to change the terrain, water or hydrology.

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

## Rail research evidence, kept separate

Three accepted rail research publications are carried as distinct typed studies
under the Rail capability: a query-scoped reachability fit, an export-tangent
junction fit and a frozen stock holdout. They are **evidence only**: no runtime
model, promise level, qualification gate, prepared input, physical writer or old
contract changes, and none is pooled with the directed-rail native study or with
each other. No research code runs as a product check.

Each publication is pinned by its own commit and keeps its own freeze, scope,
limits and sources. The ledger cites:

- `rail-query-model-v1`: fitted 26 TP / 4 FP / 245 TN / 1 FN over 276 selected
  literal requests, with stock controls 16/0/16/0 separate from the cohort's
  10/4/229/1. All attempts at retuning it are retrospective; no native junction
  law is identified.
- `rail-junction-fit-v1`: tangent continuation fits 27/0/249/0, but strict
  package-held-out selection is 10/4/229/1 (no improvement), and the tangent
  rule rejects two transitions on a real successful Pittsburgh path. Tangents
  are export-derived, not native-attested.
- `rail-stock-holdout-v1`: both frozen rules score 40 TP / 8 TN on 48 completed
  holdout requests. Their predictions were identical before any query, so the
  study does not prefer tangent over chord. Four unsupported packages stay
  metadata-only; the eight failures are one package's requests, not geographic
  absence.

Regression and bounds stay explicit: every null denominator stays null, every
unobserved or unsupported request stays Unknown, and no row becomes a rail
service, activation candidate or promise. The projection is regenerated from
archived bytes with:

```sh
python3 tools/map-factory/integrate_rail_research.py
python3 tools/map-factory/integrate_rail_research.py --check
```

The importer never runs the research models or the game. It re-checks each
publication's complete file scope through `capability-evidence/rail-research-sources.json`
(every file pinned by SHA-256 and Git blob id: files carried here byte for byte,
and bulk predictions/raw data linked as immutable blobs), then writes
`capability-evidence/rail-research-studies.json`, whose hash is pinned in
`rail-research.mjs`. `npm test` re-derives the same summary and refuses changed
evidence, a changed ledger binding or a changed source chain.

## Outside-connection query evidence, kept separate

One accepted publication, `outside-query-model-v1`, is carried as a single typed
study and referenced from **Road, Ship and Air**. It answers one retrospective,
query-scoped question: given one literal-boundary outside-connection request on
the accepted outside-v1 packages, does the native pathfinder return a complete
path whose returned endpoints equal the requested offsets? It is **evidence
only**: no runtime core, qualification gate, native certificate, physical
writer, default, input, promise level or old contract changes, and it is not
pooled with the native outside-v1/v2 studies or with any rail study. No
research code runs as a product check and no scorer, predictor or native run is
repeated.

All 876 retained rows are kept, with their exclusions and Unknowns: 342
distinct-edge primary, 36 same-edge, 378 correlated offset-128 midpoint repeats,
64 earliest-collector rows with no `position_kind`, 28 archived player probes and
28 unrequested rows. 820 rows carry a literal request and bind to their raw
entries; three openings failed before a network snapshot existed and stay
recorded as anomalies. A failure labels that exact request, never a place.

The ledger cites:

- Primary stratum, fitted and registered primary tied: 93 TP / 19 FP / 230 TN /
  0 FN on 342 distinct-edge requests. Same edge is 9/0/27/0. `directed_segment`
  and `lane:any_lane:forbidden` predict identically here, so the tie is not a
  proven equivalence; lane continuity buys nothing on this evidence.
- Road: 67/19/230/0 on 316 requests. Ship (16) and air (10) are one class only:
  every retained request succeeded, so their precision of 1 carries no
  information and no rule can be distinguished on them.
- Six package-held-out retrospective folds, all selecting `directed_segment`.
- Every false positive is a road failure in the two targeted second openings:
  all 19 return `flags = 8` and `length = 100000` and all remain **unexplained**.
  The sentinel is not proof of budget exhaustion, and chord length is not a
  native cost, grade, width, depth or SI conversion.

The corrected actual protocol is recorded per mode: `Car`/`PassengerCar`/
`Vehicle` for road, `Ship`+`Plane`/`All`/`Vehicle|TransportVehicle|CargoVehicle`
for ship and air, seed 857, maxLength 100000, literal offsets. No observation
date exists in the publication, so every observation date stays Unknown rather
than being replaced by the protocol timestamp or the publication date.

Regenerate from an exact publication checkout, then verify:

```sh
# `git archive` cannot serve this path: .gitattributes marks tools/** export-ignore,
# so an archive of the commit emits no files for it. Read the commit's tree instead.
git worktree add --detach /tmp/outside-src 030db86ce470b972b6ef3462a2698744dff40ebb
python3 tools/map-factory/integrate_outside_research.py --source \
  /tmp/outside-src/tools/map-factory/capability-evidence/outside-query-model-v1
python3 tools/map-factory/integrate_outside_research.py --check
git worktree remove /tmp/outside-src
```

The importer never runs the study's model, predictor, collector or the game. It
re-checks the publication's complete 21-file scope through
`capability-evidence/outside-research-sources.json` (every file pinned by
SHA-256, byte length and Git blob id), re-derives every table from the preserved
request rows, and refuses a changed binding. The 18 compact evidence and tool
files are carried byte for byte; the bulk frozen requests, frozen predictions
and retained inventory stay at the publication commit and are linked as
immutable blobs. Each linked hash is corroborated by at least two of the
publication's own carried documents and by the manifest pinned in
`outside-research.mjs`, so editing the source data and the manifest together
still fails. `npm test` re-derives the same summary and refuses changed
evidence, a changed ledger binding or a changed source chain.

## Outside-stock validation and road-budget limits, kept separate

One accepted publication, `outside-stock-budget-v1`, is carried as a second
typed study and referenced from **Road, Ship and Air**. It answers two separate
questions: whether the unchanged `lane:any_lane:forbidden` rule and the
`weak_component` reference predict new literal outside-connection requests on
stock packages never opened in the earlier cohorts, and whether eight old road
requests change under three requested `maxLength` floats. It is **evidence
only**: no runtime core, qualification gate, native certificate, physical
writer, default, input, promise level or old contract changes, and it is not
pooled with the outside-query, rail or native studies. No archived scorer,
collector, predictor or game run is repeated; only saved-label and count
arithmetic and integrity reconstruction happen here.

The frozen population stays recoverable: 105 installed builtin packages, 92
eligible after the declared exclusions (21 hashes), 28 supported, 64 abstaining
including 23 retained NetManager decode errors, and five fixed selections (three
queried packages and two metadata-only unsupported packages). All 84 planned
requests are preserved — 48 new stock, 12 controls and 24 budget rows — with 78
observed and the six Unknown controls left Unknown. Selection tags overlap and
are not summed as samples.

The primary rule matches all 48 stock labels: Road 12 TP / 0 FP / 12 TN / 0 FN,
Ship and Air 8/0/4/0 each, 28/0/20/0 in total. The weak reference is 12/12/0/0
on Road and identical to the primary on Ship and Air. That is descriptive
agreement on correlated requests, not qualification: all three modes remain
**unqualified** because the retained first Asanu control opening failed before a
query, and Hanami's six complete controls are separate. Only 16 road requests on
the first two packages have exact export/native field identity; the other 32
requests fail exact bridge identity and are not admitted to that subset.

The budget intervention is a separate correlated stratum, not a holdout and not
a rejudge. All four retained road errors fail at 100000, 200000 and 1000000; one
matched old-success request fails at 100000 and succeeds at both larger budgets.
Seven groups keep the all-mode graph fingerprint unchanged; the Pittsburgh 093
group's opening changed two air endpoint heights and retained no per-query
road-only snapshot, so it is not a clean single-variable trial. The requested
floats and the flags=8/length sentinel are not native-exhaustion, cost, metre or
SI proof, and all four error mechanisms remain Unknown.

Regenerate from an exact publication checkout, then verify:

```sh
# `git archive` omits tools/** via export-ignore; read the commit's tree instead.
git worktree add --detach /tmp/stock-src d745b14e3e207ee67f91033811958a2934fb38a4
python3 tools/map-factory/integrate_outside_stock.py --source \
  /tmp/stock-src/tools/map-factory/capability-evidence/outside-stock-budget-v1
python3 tools/map-factory/integrate_outside_stock.py --check
git worktree remove /tmp/stock-src
```

The importer never runs the study's scorers, audit, collectors or the game. It
re-checks the publication's exact 142-file scope through
`capability-evidence/outside-stock-sources.json` (every file pinned by SHA-256,
byte length and Git blob id), reconstructs the closed 141-member integrity table,
re-derives the saved population, request, label, bridge, control, intervention,
runtime and cleanup arithmetic, and refuses a changed binding. The 32 present
files are carried byte for byte (31 evidence files plus the integrity record);
the frozen plan, frozen feature dump, three preparation archives and 105 raw gzip
members stay at the publication commit and are linked as immutable blobs, never
shipped as archives. Linked raw files and reports are corroborated by the
retention and evaluation records, the frozen plan by the source-fix record, and
the four members declared only by the integrity record say so on the page.
`npm test` re-derives the same summary and refuses changed evidence, a changed
ledger binding, a changed derived fact or a changed source chain.

## A stopped outside-readiness study, kept Unknown

One accepted publication, `outside-readiness-stock-v2`, is carried as a third
typed evidence study and referenced from **Road, Ship and Air**. It is the
PL-1313 corrected-control continuation of the outside-query work, and its
outcome is **Unknown**: both control openings ran exactly as frozen and returned
the required labels, then the byte-backed readiness gate refused admission, so
zero holdout requests were issued and all six planned mode/class cells stay
Unknown. It is **evidence only**: no runtime model, admission repair, new
calibration score, qualification gate, native certificate, physical writer,
default, input, promise level or old contract changes, and it is not pooled with
the outside-query, outside-stock, rail or native studies. No archived collector,
driver, auditor, bundle builder, evaluator, reporter, scorer or game run is
repeated here.

The controls are real but are not holdout votes: six positive requests
succeeded, six invalid-vehicle requests failed, every row is complete and
released, the independent pre-request build index equals the request's
effective argument on all twelve rows, the opening graph equals the post graph
on both openings, each opening's three phase inventories agree (45 files, 11
roots, 7 plugins, 23 assemblies), and all ten owned PID/start identities are
gone after a post-exit audit. The frozen driver could not attest its own
absence; that audit closes cleanup only, not source binding.

The selection is frozen and tiny: rule `first_package_covering_six_strata`, a
25-package ordered eligible pool, one selected package (`PL Cavern Coast.crp`)
that covered all six cells, and six frozen holdout requests that were never
issued. Every planned cell stays Unknown. Predictions of success or no_path are
input hypotheses, not native labels; there is no holdout accuracy, precision or
recall, and those denominators are null and not estimable, never 0%.

The stop is structural and honestly recorded. `freeze.json` binds an 82-file
study-tree source manifest
(`03f7fb7c…f226d`). The accepted readiness contract requires
`frozen.source_files` to be exactly the versioned 30-file closure and requires
the runtime phase's `source_sha256` to equal its digest
(`561e4b52…54860`). Every closure file is present in the frozen tree with the
same hash, but the collector recorded the 82-file digest, so the two bindings
cannot both be true of one measured opening. Correcting the recorded binding
would rewrite a measured field; changing the closure would change the frozen
source digest and require new controls, which the no-retry rule forbids. Both
digests stay recorded, and `assemble_v2.py`, `finalize_v2.py` and `report_v2.py`
were written after the controls, sit outside the frozen measurement closure, and
measure and qualify nothing.

Regenerate from the exact producer worktree and the same-owner raw holding,
then verify:

```sh
python3 tools/map-factory/integrate_outside_readiness.py   --source ~/dev/frontierkodiak/region-to-skylines/PL-1313-stock-v2   --raw ~/experiments/PL-1313-stock-v2/raw
python3 tools/map-factory/integrate_outside_readiness.py --check
```

The importer never runs the study's tools or the game. It re-checks the
publication's exact 26-file scope through
`capability-evidence/outside-readiness-sources.json` (every file pinned by
SHA-256, byte length and Git blob id, with a separate pre-control record for the
20 files that existed at `bd00a4c`), verifies the 25 module member hashes,
re-derives the canonical 82-file and 30-file digests from the frozen map and the
two constant declarations it parses as data, checks all 51 retained raw hashes,
and refuses a changed binding. The 25 compact files are carried byte for byte
(including documentation, the frozen plan, the readiness bundle and every
study-local tool); the bulk frozen feature dump stays at the publication commit
as an immutable blob. Five small raw files are carried gzip-compressed so the
page can serve the observation windows and the verbatim refusal; every one
decompresses to its recorded original bytes. Licensed game and CRP bytes stay in
the same-owner private blade holding, are named by hash only, and are never
copied into the repository or attached to the issue. A fresh clone cannot
reproduce the full producer `check_study.py verify`: it expects the untracked
`.build/Cs1Harness.dll` and the original absolute staged-source path. That
limitation is reported, not presented as a geographic Unknown.

`npm test` re-derives the same summary, refuses changed evidence, a changed raw
byte, a changed ledger binding, a changed derived fact or a changed source
chain, and asserts that regenerating this producer never rewrites an unowned
ledger byte or the sibling studies.

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

## Frozen independent water study (PL-1072)

`water_risk.calibration_studies.pl1072-independent-geography` projects the
original saved score, freeze, model, pre-score receipt, audit and disposition
from publication `cd1aa8317205053895517bc2ac141a9f0240ee36`. The 5-square,
50-run calibration remains a separate historical seed. The new study has 30
purposive squares, 28 complete observations and two unknown capture failures.

`node water-calibration.mjs` imports these immutable bytes, never runs the
archived scorer or native-outcome code, and changes only the final water
capability. Exact original files and historical source tools are served under
`capability-evidence/pl1072-water/`. Constants pin their original hashes;
`capability-ledger.mjs` independently pins the projection tool, and build
validation compares the complete projection rather than an assembler boolean.
Intentional importer changes require updating `WATER_PROJECTION_SHA`, importing,
and refreshing the UI adoption pins. Neither capability core changes.

This is a failed qualification, not current-product calibration. Flood misses
five of six positives; drying equals always-warn and uses the original broad
optional-initialized-water label. Combined candidate and the frozen study’s
1.5 m deployed-screen comparator clear no squares: risk and reductions remain
null, displayed as NOT ESTIMABLE. The post-score sea-neighbour contract layer
is not imported. Observation dates absent from the score stay unknown; audit
and pre-score times are not native dates. Fresh-water intake, start policy,
human acceptance and playability are not qualified by this study.

`npm test` covers original byte mutations, coherent projection tampering,
counts/groups, null denominators and no live promotion. Static page/mobile and
HTTP evidence checks run via `test/water-calibration-browser.mjs` on blade in
the official Playwright 1.65 image, never carbon. No native run is implied.
