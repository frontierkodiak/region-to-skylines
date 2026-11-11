# Experimental arbitrary-region CS1 map writer

The Python reference writes terrain, initialized water, natural sources and
terrain-following connection corridors into a native `.crp` template. It needs
no game DLLs at export time. **Five-region native qualification is in progress;
see [NATIVE_FINDINGS.md](NATIVE_FINDINGS.md). Do not make these the website default
until that check passes.**

The original PL-848 Asheville template passed ordinary **New Game** and city
play with `--disableMods --noWorkshop` on CS1 1.21.1-f9. That result does not
validate the new geographic transformations. The website and installer are
unchanged by this work.

## Generate a map

Run from this directory:

```sh
uv sync --locked
uv run python generate.py CAPTURE/asheville.png \
  CAPTURE/asheville-geometry.json OUTPUT \
  --banks CAPTURE/asheville-banks.f32
```

`OUTPUT` contains the `.crp`, prepared terrain and depth grids, hydrology and
corridor diagnostics, and `generation.json`. The generation receipt explicitly
records `in_game_verified: false`. It is not a playable-map certificate.

The matching geometry and uncarved elevations come from `capture.js`, evaluated
in a Playwright page on the application's origin. That function uses the real
browser elevation, smoothing, carving and height-fit code. It also reads OSM
motorway, trunk, rail and stream geometry from OpenFreeMap vector tiles.
Finish all three browser downloads before closing the page.

### Experimental explicit-ocean capture

The helper now classifies sea from actual OpenMapTiles `water` features whose
`class` is exactly `ocean`, not from edge-connected elevations below 3m.
`capture-ocean.js` preserves polygon holes, unions separately rasterized tile
polygons, and uses the unchanged terrain module's geographic/canvas frame.
Missing tiles do not become sea. No in-frame ocean evidence gives `sea=null`.
This is a capture-helper policy only: live `terrain.js` and its defaults are
unchanged. See [COAST_EVIDENCE.md](COAST_EVIDENCE.md) for results and limitations.

For a controlled recapture of frozen non-sea vectors on a private localhost
origin (not the deployed website):

```sh
uv run python recapture_coast.py FROZEN_CAPTURES COAST_INPUTS --only rio charleston
```

The runner owns a temporary HTTP server and named headless Playwright CLI
session and closes both in `finally`. It runs the browser ocean tests first.
Each case downloads PNG, banks, geometry/provenance, raw sampled DEM and the
exact sea mask; the runner hashes them into `capture.json`. The original
square, rivers, lakes, river areas, roads and streams are preserved exactly.
Derived sources are recomputed by the unchanged browser function; their old
and new hashes are reported, not silently treated as unchanged.

```sh
uv run python compare_coast.py BEFORE_PREPARED AFTER_PREPARED landcover.u8.gz inundation.json
```

This reports initial prepared-depth overlap with WorldCover built-up/forest
classes over the whole square and central 25 tiles. It uses bilinear sampling
from native-format 16m south-first nodes to 10m cell centres, with wet >0.1m.
It introduces no coastal exclusion mask or native acceptance threshold.

The geometry input contains:

- `sq`: `lon`, `lat`, clockwise `rotation`, horizontal `scale`, `name`, `slug`.
- `rivers` and `streams`: lines with `name`, geographic `pts`, optional `class`.
- `lakes` and `riverAreas`: polygons with geographic `rings`, holes after the
  outer ring.
- `roads`: lines with `class` (`motorway`, `trunk`, `rail`) and geographic `pts`.
- `seaLevel`: fitted sea height in game metres, or `null` inland.

Without `--banks`, preparation estimates bank heights with a local maximum
filter. The committed real-region fixtures use the actual uncarved elevations.

## Natural resources and trees

The resource stage writes trees, forest, fertile land, ore and oil, and the
New Game panel amounts. It's opt-in until it has been checked in game.

```sh
uv run python landcover.py GEOMETRY_JSON landcover.u8.gz   # ESA WorldCover 10 m, about 3 s
uv run python evidence.py GEOMETRY_JSON evidence.json      # USGS MRDS deposits (mostly US)
uv run python generate.py PNG GEOMETRY_JSON OUTPUT --banks BANKS \
  --landcover landcover.u8.gz --evidence evidence.json
# or, on an already prepared region or fixture:
uv run python paint.py fixtures/asheville fixtures/asheville/landcover.u8.gz OUTPUT \
  --evidence fixtures/asheville/evidence.json
uv run python verify_resources.py                          # frozen bytes and native rules
```

- **Trees** follow WorldCover tree cover, grouped into stands and glades. The
  default is 180k trees, under the editor's 250k cap. Only original-release
  prefabs the map theme loads are used, so the Temperate template gets no
  conifers.
- **Forest** bytes are derived from the trees with the game's own formula.
- **Fertile land** comes from crop and pasture on flat, dry ground.
- **Ore and oil** come from MRDS deposits. In `balanced` mode, the default,
  ore, oil and fertile land are topped up to the official maps' median New
  Game shares, where shipped maps put them. `real` uses evidence only.

`paint.py` also writes `resources.png` (an overlay preview),
`resources.json` (amounts, invented patches, evidence used) and `plan.npz`
(grids and trees, which `--plan` replays through the encoders alone). The
WorldCover bucket has no CORS headers, so a browser port needs a same-origin
proxy for it. [CONVENTIONS.md](CONVENTIONS.md) ranks what players expect and
records what this tool does about each. `survey/` holds the shipped-map and
community research behind the defaults.

### Experimental compound resource qualification

`qualify_resources.py` combines existing prepared terrain/water/hydrology with
explicit WorldCover inputs. It does not launch the game or promote a map:

```sh
uv run python qualify_resources.py PREPARED_ROOT RESOURCE_INPUTS CANDIDATES STAGING
```

Each root contains the five region directories. Resource inputs contain
`landcover.u8.gz`, `landcover.json` and `geometry.json`; optional `evidence.json`
must match the pinned PR24 fixture exactly. The input receipt binds geometry,
land cover and the original pinned sampler. Prepared packages must match their
generation receipts. The qualification source must be committed and clean so
the resulting receipts identify exact source.

The tool uses PL-902's unchanged balanced defaults: WorldCover-based forest and
fertility with explicitly labelled **convention top-ups**, not invented MRDS or
crop evidence. No MRDS evidence is inferred for a region without an evidence
file. It repeats planning, replays `plan.npz`, independently decodes the managers
with the survey reader, and checks exact resource/tile totals, tree/forest
consistency, terrain/water/network preservation, previews, blank author,
mode-2 north-facing camera and the resource-path buildable score.

Each candidate's `generation.json` binds its package, frozen plan, resource
report and source inputs. `qualification.json` summarizes offline results.
`soak.py --prepared CANDIDATES` replays `plan.npz` through the same resource
encoder when present. If a receipt declares resources but the plan is missing,
or the bound plan/package differs, staging fails instead of silently producing
an unpainted map. Staging without resource plans retains the existing behavior.
Generated probes retain separate panel, actual-startup/Areas, geographic
`ground_truth` and optional `landmark_expectations` contracts.

These compound packages are **unverified experimental integration**, not native
resource acceptance or PL-902 closeout. In particular, adding resources cannot
repair Rio R4's failing flood gate. Do not freeze these packages as finals.
The original PR24 expected resource CRP hashes in `fixtures/resources.json`
are deliberately retained: compound previews/camera change the bytes, so the
old checksum assertions in `verify_resources.py` are not an acceptance gate
for these new packages. Use its independent decoder checks, not `--freeze`.

## Verify the frozen fixtures

Resource-bearing reference authoring also accepts
`freeze_fixtures.py CAPTURE OUTPUT --resource-inputs PINNED_RESOURCES`, where
each resource directory contains its pinned `landcover.u8.gz`, provenance and
optional `evidence.json`. It freezes the deterministic plan, knobs and resource
report alongside terrain/water inputs. `verify_regions.py OUTPUT` independently
reprepares geography, replans resources, compares the plan and complete CRP,
and decodes trees/resource totals. `soak.py` replays the same resource plan.
Writing a byte fixture is **not** native acceptance; rejected hydraulic
candidates must not be promoted merely because their checksum reproduces.

New staged hydraulic requests include a hash-bound, unbuffered geographic
waterway mask (`mapped-water.u8`), in addition to the initial-water reference.
This distinguishes filling a mapped channel from flooding land beyond it.
The harness keeps its original initial-footprint-only metric as a diagnostic;
the depth/distance/area tolerances are unchanged. Mask provenance records the
geometry hash and fields, never a footprint inferred from the final wet grid.

```sh
uv run python verify_regions.py
```

The fixtures cover Asheville, Innsbruck, Rio de Janeiro, Pittsburgh and
Charleston, the flat coastal case. Verification checks their source hashes,
reproduces preparation, regenerates each package to its expected SHA-256,
decodes its actual terrain and water, and compares all unmodified network bytes
with the native template. It also checks initial sample wetness, start tiles,
earthwork limits and node-to-node grades. **It does not run CS1, simulate water,
query its pathfinder or prove New Game visibility.**

Each case includes the original browser heightmap and geometry, uncarved
elevations, prepared terrain and water, source and corridor parameters, and an
expected `.crp` checksum in `fixtures/manifest.json`. This separates the
JavaScript serializer parity test from the hydrology port: the serializer can
consume the frozen prepared grids directly.
`prepared_sha256` records the uncompressed terrain and depth checksums;
`files_sha256` records the distributed fixture-file checksums.
`expected_simulation_sha256` separately binds the native simulation payload,
so listing-only changes cannot silently invalidate or inherit hydraulic proof.

Fixture replacement is an explicit authoring operation, not part of the tests:

```sh
uv run python freeze_fixtures.py CAPTURE
```

Review changed bytes and the native-game result before accepting a new contract.
The original PL-848 bundle remains compatible with `verify.py` and the bounded
Asheville preparer in `prepare.py`.

## Native hydraulic soak

Explicit `brunnel=tunnel` waterways belong in `undergroundWaterways`, not
terrain-surface carving, source placement or surface-water reference masks.
Capture receipts preserve each excluded feature and exact tile/geometry
binding. `surface_water.py` also normalizes tagged direct inputs and rejects
conflicting visibility/source properties; bridge/intermittent tags are not
silently discarded. Hydrology keeps surface legs separate across underground
gaps and uses an output-free regulated drain at an entering surface portal.
This is not a native underground-water network or a promise that every short
mapped creek is perennial; modeled-reach omissions are explicit in hydrology.
Minor streams whose bank-bounded gravity profile is infeasible within the
existing incision limit retain their geometry, shallow startup fill, intake
and probes, but receive no sustained artificial output. Their dry observations
remain in the audit. This prevents pumping a creek across uphill terrain;
it does not reclassify a dry stream as a wet river or remove a failing probe.

Starting-tile selection requires at least256 initial vertices deeper than0.5m
before a tile receives water priority, not merely eight shallow creek pixels.
This is a preparation heuristic, not proof of sustained intake: native audits
still report the selected tile's actual end water/depth/volume. Otherwise the
explicit constructed reservoir fallback remains visible in the receipt.

Stage the five exact golden packages and all 14,615 committed waterway probes
without starting Steam:

```sh
uv run python soak.py ~/experiments/PL-857-soak
```

Add `--harness /path/to/checkout/tools/cs1-harness` to run each map for 60
game-minutes, serially in the foreground. `--only asheville` selects a subset;
`--game-minutes 10` permits an explicitly short diagnostic run. Use a fresh
output directory for each experiment. Each region waits up to 120 minutes for
the shared harness slot, without taking over another session. Steam account
conflicts retry after 30 minutes; no prompt is answered. This requires the
harness at `339cfe4` or later. Follow the issue's Steam reservation windows
before starting any native check.

Staging now also requests the native New Game panel check from harness PR #8.
It compares the selected listing's metadata and image instantiation with the
exact package, captures the real panel, and fails until that screenshot has
an explicit hash-bound visual review. Rejudge after reviewing it; do not
turn the review flag on automatically. This instrumented panel observation
does not replace the separate strict vanilla start.

Asheville also includes four independent GNIS/AWS-DEM landmarks. Staging passes
them to harness PR #8's `terrain_landmarks` check, which samples native world
heights before any harness camera override. The harness records startup camera
heading; `world_observe` can read it again while actual Area Zoom is open.
Staging also requests the opt-in native opening/Areas-tool captures, with
explicit zero-degree yaw/render-heading expectations and a one-degree
tolerance. The game itself enters Area Zoom; no harness camera aim creates
that view. Both screenshots need a separate hash-bound visual review.
This guards geographic orientation separately from the writer's own grid
renderer. `landmark_expectations` carries the frozen absolute-height reference;
`ground_truth` also names the region and geographic landmarks for harness
PR #22's independent whole-map check. Its Cartesian rotation is the negative
of the browser's clockwise rotation. See `NATIVE_FINDINGS.md` for the actual
playtest-save comparison and still-pending live camera checks.
When authoring fixtures, supply `CAPTURE/asheville-landmarks.json` as well;
`freeze_fixtures.py` refuses to silently reuse an old landmark reference.

Each map is checked against the committed CRP checksum before launch. The
harness retains the timeline, native grids, screenshots, GPU measurements and
cleanup receipt. `hydraulic-summary.json` groups every probe by waterway, with
final wetness and any dry samples. This includes small streams, not just the
major rivers. Newly wet area is a flooding diagnostic, not a flooding verdict;
review the grids and screenshots as well.

A successful driver exit means the requested checks completed, not that the
map passed acceptance. Full native car and train route checks run at the start
and end when supported by the harness. Harness runs use `--noWorkshop` and a
disabled control mod, not strict `--disableMods`. Ordinary vanilla menu/city
starts require separate checks. PL-856's first 60-minute result used
the older PL-848 map (two sources), not the arbitrary-region Asheville fixture
(207 sources); do not treat that result as a soak of the new writer.

`--prepared DIR` tests explicitly staged candidates before replacing the golden
fixtures. It regenerates their packages and checks their generation-receipt
checksums. `generate.py --no-prefill` is a diagnostic sea-only initialization;
terrain, networks and source controls remain unchanged.

```sh
uv run python audit_soak.py RUN PREPARED GEOMETRY_JSON > audit.json
```

The audit compares native initial terrain, water and source controls with the
prepared inputs. It retains exact dry probes and separately counts water
within 64 m, never relabeling an exact failure as a pass. It splits map-boundary
and playable-envelope probes and measures spreading deeper than 0.5 m more
than 128 m from initial water or mapped water lines/polygons. Spreading and
grid-neighbourhood results cover saved grids only; newer harnesses additionally
retain native neighbourhood readings at every point sample. These thresholds
are diagnostics, not a proof that every river, stream or lake is perennial.

## Fixed topology, fitted coordinates

`templates/native-corridors.crp` is the editor-authored PL-848 template, not a
stock map or a copy of a city save. Its layout is bound to the entire package's
SHA-256. `template.py` derives and checks the descriptor from that exact source.
No proprietary game code or assemblies are included.

One authored topology supplies two one-way highway approaches and one
boundary-to-boundary railway. The writer preserves its allocation IDs, lane
chains, native prefabs, flags and outside-connection buildings. It updates
recorded node vectors, segment direction vectors, support and connection
building vectors and angles. The native `NetManager.AfterDeserialize` rebuilds
lane curves from those nodes. Native pathfinding checks are required for
transformed outputs, not inferred from topology preservation alone.

This replaces a proposed eight-file edge/rail template library with one
fingerprint-bound topology. Road entry is selected from real motorway or trunk
boundary crossings. Corridors follow the mapped alignments where connected;
terrain-following deck heights and blended earthworks fit the region. Missing
or disconnected alignments use a synthetic approach, recorded in the report.
The railway remains present in every map, even when its alignment is synthetic.
Node-to-node grade limits are 12% highway and 4% rail; these are not measurements
of the native curved deck's steepest tangent.
Rail alignments are smoothed until adjacent turns are at most 45°; a straight,
explicitly synthetic alignment is the fallback. Native testing found that a
108° mapped bend could preserve topology while blocking the full train path.

The starting tile is selected inside the vanilla 25-tile area for water, road
access and buildable land. If no suitable tile has water, preparation adds an
explicitly labeled **constructed starter reservoir**. It does not claim that
reservoir came from OSM. Resource water/shore cells and tile totals are updated
for the new geography. Other resource types and trees remain the template's
empty maps.

## New Game listing

Every generated package has a blank author, rather than the template author's
account hash. It includes a 400 × 224 thumbnail and an 1,800 × 1,008 preview,
with native texture assets and metadata checksum references. The default is
a deterministic north-up rendering of the actual prepared terrain, initialized
water and fitted roads/rail. It is **not a game screenshot**, nor a claim that
every small creek remains wet. `crp.py --preview CAPTURE.png` can instead embed
a genuine map capture without changing the simulation payload.

Water amounts describe the central 25 unlockable resource tiles, not the whole
81-tile simulation. The buildable percentage is recomputed from the final
terrain with the installed game's weighted-flatness score and water fraction.
It is not the fraction below a particular slope threshold. CS1's inspected
flatness API composes two +2 tile offsets; the writer preserves that native
quirk. The current Asheville candidate scores 70%, not the template's 74%.
The resource-painted Asheville native panel now verifies both resolved images,
the hidden blank author, resource amounts and73% buildable. The earlier
unpainted candidate scored70%; resource painting supplies native water coverage
instead of the fallback estimate. Exact-package regional qualification is
tracked in `NATIVE_FINDINGS.md`, not implied by metadata decoding.

The stock `NewGamePanel` generates the proposed **city** name randomly; its
`MapMetaData` has no suggested-city-name field. Setting `mapName` controls the
map listing, not that editable city-name text box. An offline map cannot
override this behavior without changing the game or using a mod.

The writer now supplies a north-facing start camera centred on the starting
tile. Its native saved-view mode must be **2** (`NewGameFromMap`), rather than
the editor/load-game modes, which the game ignores on a fresh map start.
Position, angle and zoom are fingerprint-bound patches, not a UI mod. The
fields are byte-verified. Native Asheville opening and actual GameAreaTool
Area Zoom headings both verify0°; independent terrain landmarks and1,600 native
world samples confirm north-up geography. A fresh pointer-neutral check is
queued to verify opening centring separately: an earlier harness pointer position caused edge
scrolling. No geographic grid flip is introduced.

Air availability requires a real `FlightPathAI` network and native outside
connection buildings. AVL's location alone does not supply those objects.
The fixed topology has road and rail only: plane and ship counts remain
honestly zero. Adding air needs a freshly authored native template and bound
descriptor; setting only the metadata flag would advertise a nonexistent
connection. Resource painting and real tree-cover inputs belong to PL-902;
they are not fabricated by the listing writer.

## Water and terrain limits

Water surfaces come from a monotone fit to uncarved elevations, not a running
minimum of the already carved bed. Terrain-aware routing can move around DEM
obstructions inside the mapped corridor. The channels start filled. Streams
start at no more than 0.25 m depth with 0.01 capacity controls. River capacity is
0.8 for mean profile gradients at most 0.5%, otherwise 0.2. These are game
regulator capacities, not calibrated discharge rates. River reach controls
supply tailwater and remove excess at missing mapped continuations. River
controls are spaced at 2,048 m arc intervals as well as the two ends;
this represents catchment inflow omitted from an endpoint-only simulation,
independently of the verification probe positions. Creek
outlets instead have zero output capacity and a target below their local bed;
they withdraw excess without introducing a second spring. Creek controls are
omitted within 96 m of mapped major rivers to avoid drawing down a receiving
river. This does not join disconnected mapped fragments. Lake targets are
capped below the lowest
surrounding uncarved bank or actual prepared ground, so an interior DEM
percentile cannot continuously flood an outlet. Some mapped lakes consequently
receive no inland regulator.

If the monotone profile would rise above local banks, the preparation instead
caps that reach at uncarved banks minus 0.25 m (or sea level), adds 512 m
controls and terrain-derived crest/trough controls, then limits input/output
footprints independently against final ground. Feasible profiles retain the
2,048 m policy exactly. This bank-bounded revision follows a failed Rio soak;
it remains a native-test candidate, not a proven buried-waterway simulation.

In `hydrology.json`, `capacity` sets native withdrawal capacity and defaults
the injection capacity to the same value. Optional `output_capacity` overrides
injection, including **zero for a true drain**. Each becomes
`floor(capacity * 65535 + 0.5)`. A below-center-bed target alone is not drain-only:
CS1 acts on a radius of `10 + 0.4 * sqrt(rate)` metres and can inject into lower
neighbouring cells. The JavaScript port must preserve distinct input/output
rates. Existing inputs without `output_capacity` retain their original bytes.
Zero is intentional; a port must use a missing-value fallback, not a truthiness
fallback that replaces zero with the default capacity.

Additional channel lowering is capped at **3 m relative to the exported PNG**.
That PNG already includes the browser's river carve, normally 10 m. Corridor
cut and fill are separately capped at 3 m. Wet channels and their margins are
excluded from road earthworks. Reports include mapped-line wet coverage as well
as the samples, so a good sampled path cannot hide omitted geometry.

Coastal maps use the browser's fitted sea level, rather than the prototype's
fixed 35 m. Initial sea depth fills every below-sea cell, including disconnected
depressions, matching the inspected native reset behavior.

Initialized water does not establish hydraulic equilibrium. Buried waterways,
DEM artifacts, tidal geometry and disconnected tile fragments still need live
drainage and flooding checks. Native road admission, ordinary New Game listing,
population growth, five-region stability and cross-platform behavior remain
unverified. Completed per-region evidence is in `NATIVE_FINDINGS.md`.

## Binary conventions

| Input | Order and units |
| --- | --- |
| Browser PNG | North to south; unsigned 16-bit; 65535 = 1024 m |
| `banks.f32` | North to south; little-endian Float32; game metres |
| `terrain.u16` | South to north; little-endian unsigned 16-bit; 64 units/m |
| `water.u16` | Same order; **depth**, not absolute surface height; 64 units/m |
| Inner serializer | Big-endian numbers and native delta/RLE arrays |
| CRP directory | Little-endian numbers, .NET strings, MD5 asset checksums |

Fixture `.gz` files use gzip with a zero timestamp. The outer manifest uses
SHA-256. Map metadata gets a new package identity, map label, Unity Mono UTF-16
publication hash, simulation asset reference and resource water amount; factory
mod references are removed. New exports have an empty package author rather
than inheriting the template author's account hash. Serializer shared-string and object tables are
preserved. The writer refuses a mismatched template or descriptor.

Elevation: AWS Terrain Tiles. Geographic features: © OpenStreetMap contributors,
ODbL, via OpenFreeMap/OpenMapTiles. Capture provenance is frozen with each case.

## Experimental explicit underground-waterway capture

`inspect_surface_water.py FROZEN_GEOMETRY PROVENANCE NEW_OUTPUT --capture`
recovers exact pinned tile metadata and excludes only explicitly tunnel-tagged
line pieces from a fresh browser carve, retaining them as `undergroundWaterways`.
It leaves product terrain/defaults unchanged. See
[SURFACE_WATER_EVIDENCE.md](SURFACE_WATER_EVIDENCE.md) for source evidence, the
capture schema, Rio receipts and the mandatory downstream barrier/portal work.
These inputs are not an accepted ready-to-play map.

For frozen captures with no historical VT receipt, pass provenance `-` plus
`--first-observed`; only the fixed documented snapshot is allowed. Exact
metadata-equivalent buffer duplicates retain all provenance as a group, never an
arbitrary tile choice. `--capture --control` captures all original geometry for
separating historical PNG recapture drift from tunnel-only effects. The five-region
ledger and source-assurance distinctions are in `SURFACE_WATER_EVIDENCE.md`.

Prepared resource staging verifies the saved `resources.prepared_geometry_sha256`
before constructing mapped-water/world references. It archives those exact bytes
beside `staging.json` and binds them in the frozen probes. Missing or changed
resource geometry fails closed; legacy unpainted staging stays supported. See
[STAGING_GEOMETRY.md](STAGING_GEOMETRY.md) for the contract and offline identity tests.
