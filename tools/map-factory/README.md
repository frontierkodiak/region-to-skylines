# Experimental arbitrary-region CS1 map writer

The Python reference writes terrain, initialized water, natural sources and
terrain-following connection corridors into a native `.crp` template. It needs
no game DLLs at export time. **The new arbitrary-region outputs are not yet
game-verified. Do not make them the website default until that check passes.**

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
output directory for each experiment. An occupied harness or Steam prompt stops
the command without taking over or answering it. Follow the issue's Steam
reservation windows before starting any native check.

Each map is checked against the committed CRP checksum before launch. The
harness retains the timeline, native grids, screenshots, GPU measurements and
cleanup receipt. `hydraulic-summary.json` groups every probe by waterway, with
final wetness and any dry samples. This includes small streams, not just the
major rivers. Newly wet area is a flooding diagnostic, not a flooding verdict;
review the grids and screenshots as well.

A successful driver exit means the requested checks completed, not that the
map passed acceptance. Harness runs use `--noWorkshop` and a disabled control
mod, not strict `--disableMods`. Ordinary vanilla menu/city starts and native
car paths still require separate checks. PL-856's first 60-minute result used
the older PL-848 map (two sources), not the arbitrary-region Asheville fixture
(207 sources); do not treat that result as a soak of the new writer.

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
lane curves from those nodes. This behavior is source-verified; the transformed
outputs still need a native pathfinding check.

This replaces a proposed eight-file edge/rail template library with one
fingerprint-bound topology. Road entry is selected from real motorway or trunk
boundary crossings. Corridors follow the mapped alignments where connected;
terrain-following deck heights and blended earthworks fit the region. Missing
or disconnected alignments use a synthetic approach, recorded in the report.
The railway remains present in every map, even when its alignment is synthetic.
Node-to-node grade limits are 12% highway and 4% rail; these are not measurements
of the native curved deck's steepest tangent.

The starting tile is selected inside the vanilla 25-tile area for water, road
access and buildable land. If no suitable tile has water, preparation adds an
explicitly labeled **constructed starter reservoir**. It does not claim that
reservoir came from OSM. Resource water/shore cells and tile totals are updated
for the new geography. Other resource types and trees remain the template's
empty maps.

## Water and terrain limits

Water surfaces come from a monotone fit to uncarved elevations, not a running
minimum of the already carved bed. Terrain-aware routing can move around DEM
obstructions inside the mapped corridor. The channels start filled, lakes have
local regulators, and sources are placed inside upstream reaches. Stream
capacity is 0.06 and river capacity 0.2. These are provisional class defaults,
not calibrated discharge rates.

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
population growth, long-duration stability and cross-platform behavior remain
unverified for these new outputs.

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
