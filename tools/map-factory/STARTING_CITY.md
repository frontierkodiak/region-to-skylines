# Starting Asheville: street pilot

PL-1031's deliverable remains a city grown and saved by the game. This is an
experimental physical-network importer, not that save. The shipping exporter,
website, CLI package, water controls, and frozen fixtures do not adopt it.

## Capture a reproducible street source

Run these commands from `tools/map-factory`. Use your task's scratch directory
for the output files. `geometry.json` must have the prepared map's exact `sq`.

```sh
uv run python osm_streets.py geometry.json streets.json
```

If Overpass is unavailable, use a reference-complete regional PBF. The
[Geofabrik North Carolina extract](https://download.geofabrik.de/north-america/us/north-carolina.html)
contains OSM data without contributor account fields.

```sh
uv run --with osmium==4.3.2 python osm_streets.py geometry.json streets.json \
  --pbf north-carolina.osm.pbf
```

The resulting JSON retains node ids, complete ways, tags, the square, snapshot
time, and the PBF hash or Overpass query. Capture refuses to overwrite it.
Partial Overpass responses and incomplete way references fail instead of
silently losing roads. Builds read this frozen source and make no requests.

## Build a bounded candidate

```sh
uv run python real_roads.py input.png geometry.json OUTPUT --banks banks.f32 \
  --landcover landcover.u8.gz --evidence evidence.json --streets streets.json \
  --street-scope playable
uv run python street_preview.py OUTPUT street-preview.png
uv run python verify_streets.py OUTPUT streets.json
```

`playable` retains **all supported motor roads inside the central 25 tiles**,
including mapped driveways and parking aisles. Highways and rail continue to
the full terrain's edge. Local roads cropped at the 25-tile boundary end there;
they do not get false outside-connection buildings.

The default `--street-scope all-motor` requests the full 17.28 km square.
It currently exceeds the native network budget for Asheville. It fails, rather
than trimming roads to fit. A failed final write leaves `.crp.unfinished`, not
a ready-named `.crp`. Discard that incomplete output directory.

Shared OSM node ids determine junctions. Geometric crossings and nearby
endpoints never create one. Direction, roundabouts, disconnected roads, and
parallel routes survive. Ground streets use `Basic Road` or `Oneway Road`.
Their bridge and tunnel variants come from the stock prefab catalogue.
Native load still has to qualify their flags, pillars, lanes, and routing.

Degree-two chains use a provisional cubic curve model with a sampled 4 m
symmetric geometric error and source arc length at most 256 m. This is **not
an established error bound on the game's actual curves**. The source way set
is checked before and after compression. Shape nodes can disappear, but
junctions, dead ends, direction changes, and structure transitions remain.

The report accounts for excluded non-motor, area, and future road classes.
It does not model road widths, lane counts, access restrictions, turn
restrictions, or street names. It does not create native zone blocks.
Those blocks must be created through the game before the zoning milestone.

## Current checkpoint

The November 16, 2026 OSM snapshot contains 22,411 highway ways in this square,
17,906 of them supported motor-road ways. The full-square curve model still
exceeds CS1's 32,767 node and 36,863 segment slots, before reserving rail and
other retained networks. No full-square map or native qualification is claimed.

The central-25-tile pilot retains 8,753 motor-road ways. Its decoded package,
coverage report, source extract, and offline comparison accompany the issue.
The image is a curve-model preview, not a game screenshot.

Two existing repository gates also fail on untouched main `5a1e045`:
`npm test` and `npm run test:fixtures` encounter a stale short-test binding for
`native_opening_diagnostic.py`. The file hashes to `885199ba…`; the recorded
binding expects `c122cdec…`. This work does not repair or relax that water-test
contract. Scoped road tests and the shared save-reader tests are separate checks.

## Before this can become a starting-city save

1. Finish the higher-priority PL-912 water blockers. Do not claim or compete
   for a game slot during that work or Caleb's play.
2. Regenerate from the accepted water baseline. Qualify the exact street
   package in the disposable blade install: load, local-to-outside paths,
   bridges, tunnels, terrain clearance, water preservation, soak, and reload.
   The current package cannot inherit the old water or road receipts.
3. Resolve the full-square network budget without silently removing roads.
   The playable pilot does not complete the full-street milestone.
4. Add native zone blocks and real city zoning, districts and names, service
   buildings, utility connections, and ART routes through the game APIs.
5. Let the city grow, check population and jobs, and ask the game to save it.
   Qualify that save by reloading it. No offline citizen or household writer
   is proposed.
