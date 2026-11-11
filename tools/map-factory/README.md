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

The geometry input contains:

- `sq`: `lon`, `lat`, clockwise `rotation`, horizontal `scale`, `name`, `slug`.
- `rivers` and `streams`: lines with `name`, geographic `pts`, optional `class`.
- `lakes` and `riverAreas`: polygons with geographic `rings`, holes after the
  outer ring.
- `roads`: lines with `class` (`motorway`, `trunk`, `rail`) and geographic `pts`.
- `seaLevel`: fitted sea height in game metres, or `null` inland.

Without `--banks`, preparation estimates bank heights with a local maximum
filter. The committed real-region fixtures use the actual uncarved elevations.

## Verify the frozen fixtures

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
This guards the geographic orientation separately from the writer's own grid
renderer. See the unresolved orientation gate in `NATIVE_FINDINGS.md`.
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
The native panel still needs to verify these new assets and values.

The stock `NewGamePanel` generates the proposed **city** name randomly; its
`MapMetaData` has no suggested-city-name field. Setting `mapName` controls the
map listing, not that editable city-name text box. An offline map cannot
override this behavior without changing the game or using a mod.

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
