# Canonical place reader (PL-1074)

`place_input.py PLACE OUTPUT` validates a `polli.place/0` directory through
the **real** `place_model` API and compiles terrain, water, transportation and
landcover into the existing map-factory inputs. It then calls `generate.generate`:
the existing hydrology, resource planning, native admission and CRP codecs.
It does not acquire data, install a map, or serialize a new real-road network.
**Actual real-road serialization remains PL-1066.** The template's connections
are still template connections, even where their boundary positions follow roads.

From the repository root, with Node and the repository's npm dependencies:

```sh
npm ci --ignore-scripts
uv run --project tools/map-factory \
  --with ../agentic-research-workbench/place-model \
  python tools/map-factory/place_input.py \
  ../agentic-research-workbench/place-model/places/amherst-center \
  /absolute/scratch/amherst-export
```

Supply polli-place-model 0.3 from the workbench's PL-1074 stack for the
transportation semantics and source-associated river-flowpath extensions. Old v0 directories can be upgraded with
`place rebuild-transportation-semantics MODEL`. No model
implementation is vendored and no editable dependency or private path is added
to the public project's lockfile. Any installation of that package providing
the documented API works; the sibling checkout is only an example dependency.

`OUTPUT` must be empty. `--inputs-only` compiles without running the generator.
The Python `preprocess(place, output)` function returns four paths, in order:

| Input | Encoding |
| --- | --- |
| `input.png` | 1081×1081 north-first 16-bit heightmap, 0…65535 → 0…1024 game m |
| `geometry.json` | Existing geometry codec plus canonical identity/properties and `placeInput` receipt |
| `banks.f32` | 1081×1081 north-first little-endian float32 uncarved fitted game heights |
| `landcover.u8.gz` | 1728×1728 north-first categorical WorldCover codes, at 10 game m cell centres |

The executable writes these under `OUTPUT/inputs` and writes its full receipt
to `OUTPUT/place-input.json` and stdout. After generation, it uses the existing
`water_risk.assess` and `water-risk.js` decision. Exit 5 retains inputs and the
risk report but exports **no CRP**. Only after accepting that exact report may
the caller rerun into a fresh directory with `--allow-water-risk`. Unavailable
or invalid checks cannot be overridden. Successful output is in
`OUTPUT/generated`. Input compilation alone does not run a water-risk screen.
No receipt claims game safety: native/harness/water qualification remain
downstream, including for a lower-risk screen.

## Frame, crop and elevation

The selected square is centred on the model extent, with its side equal to
the smaller extent dimension. For cell-sampled terrain the square is further
inscribed inside the sample-centre support: the outer half-cell has no elevation
sample and is not extrapolated. Vertex terrain uses both boundary vertices.
Grids are checked for covered samples before interpolation. Terrain is bilinear;
landcover is nearest categorical, never interpolated class values.

Canonical local coordinates are already metres. No horizontal unit conversion
is applied twice. Geography is computed from the manifest alone:

```text
source_east  = origin[0] + local_x / horizontal_unit_metres
source_north = origin[1] - local_z / horizontal_unit_metres
lon, lat    = transform(source_crs -> EPSG:4326, source_east, source_north)
game_x      = (local_x - crop_center_x) * 17280 / crop_side
game_z      = (crop_center_z - local_z) * 17280 / crop_side
```

CS1 z is **north-positive**. The PNG's top row is north; `region.prepare`
performs the existing flip to native south-first grids. There are 1081
vertices at 16 m, spanning 17,280 m, not 1081 cells.

`placeInput` reports the original extent, local crop, actual WGS84 crop corners,
source and game sides, both scale ratios, original frame, datum, source licenses
and manifest hash. A 2 km source becomes 17.28 game km: **8.64× horizontal
enlargement, not 1:1**. Amherst and Boston use their full 2×2 km extent.
Asheville's 6×8 km extent is cropped to `[-3000,-4000,3000,2000]`, a 6 km
square enlarged 2.88×. All of these are generic extent rules, not place switches.

The legacy geographic codec uses a local WGS84 approximation (`prepare.pixel`).
Target feature `pts`/`rings` deliberately use its **inverse**, so their target
pixels agree exactly with the canonical crop and sampled grids. These compatibility
lon/lat values are not survey coordinates; use `crop_corners_wgs84` and the
manifest CRS for actual geography. No arbitrary per-place rotation or origin
is used to hide projection differences.

Canonical elevations remain absolute in the source vertical datum. The display
adapter's `elevation_origin_metres` is retained but **not subtracted**. A tiny
Node codec bridge calls existing `CAPTURE` smoothing/carving, `fitHeights(auto)`
and PNG encoders, then calls `fitHeights` again on the uncarved grid for banks,
as `captureInputs` does. Its base and vertical scale are reported. No new
terrain-fitting or water-control policy is implemented. Coastal fitting retains
the existing policy's zero reference in the source datum; this is **not** a
measured tide or vertical-datum harmonization.

## Identity and semantic limits

- `roads` retains every canonical segment, even outside the crop. IDs,
  raw classes (including numeric classes) in `canonical_class`, widths in **source metres**,
  bridge/tunnel/level, provenance and the entire original connector list with
  unchanged linear `at` references survive. Lines are not clipped or split:
  their reference fractions therefore remain meaningful.

The shared `transportation_semantics` table, keyed by segment ID, owns normalized
mode/class. The adapter uses that class for target routing, mapping only explicit
rail/standard_gauge to the existing `rail` codec. It does not guess that an
unknown or narrow-gauge line is a native standard-gauge railway. Numeric source
street codes remain road/unknown upstream unless their source dictionary is known.
- `roadConnectors` retains every connector ID and provenance. Its x/z are
  game east/north metres under the reported transform. Coincident connectors
  remain distinct. Geometric crossings never create connectivity. Full
  `source_segment.properties` (including scoped level/bridge/tunnel rules)
  is retained in `sourceFeature.properties`; scalar summary flags do not
  replace those ranged rules. No class is promoted to motorway or rail.
- Hydrography retains canonical ID, kind, absolute height, provenance and
  `source_water.properties`. Multipart output retains the same ID plus a
  `part` index. Rings retain holes. LineStrings remain lines, never polygon
  exteriors reused as centrelines. Explicit tunnel/culvert/underground source
  evidence becomes the existing `brunnel=tunnel` exclusion; a negative level
  alone is not assumed underground. Intermittency and source grade survive.
- Known rivers become `rivers`; stream/canal/ditch/drain lines use the
  existing stream codec with their original `kind` retained. Only explicit
  `ocean` polygons become ocean masks. Known lake/pond/reservoir/basin areas
  use the existing lake codec. Generic water/surface/bay and river/canal
  areas use `riverAreas`, without lake flattening or reconstructed flow.
  Swimming pools and underground polygons are retained in
  `unmodeledHydrography` with reasons rather than becoming natural sources.
- Unknown water roles and unsupported geometries stop compilation. Landcover
  must use the existing WorldCover uint8 codes; no new legend is guessed.

### Source-associated river paths and enrichment

Optional `hydrography_flowpaths` records use explicit river-body foreign keys
validated by the shared model. They enter the existing river codec with full
canonical ID, body ID, source direction, provenance and multipart vertex order.
NHD raw feature properties survive in `sourceFeature.properties`. Missing names
use the body ID, not a guessed place name. No measured stage is invented.

The shared model's explicit `place enrich-nhd` command selects only NHD
StreamRiver areas and ArtificialPath lines joined by the original source FK.
It does not infer paths from Asheville's display triangles, import all small
streams, turn coastlines into rivers, infer endpoint connectivity or replace
Overture culverts. Coverage can honestly be empty. Pixel geometry is unchanged
by this metadata extension. The existing target hydrology, not source direction
alone, still controls water stage and supply.

The separate source-graph enrichment writer can replace an unclassified legacy
graph with a pinned Overture graph for the declared frame/extent and genuinely
rebuild its road meshes. Explicit motorway classes then reach this reader; no
numeric street-code lookup is introduced here. Other already-pinned graphs are
verified no-ops. This adapter never acquires data or consumes appearance meshes
as substitute semantic layers.

Still not expressed: a measured hydraulic network/stage/datum for all sources.
Boston's inferred DEM water height is not a measured tide. Non-WorldCover
landcover needs an explicit legend before this target can consume it.

## Verification

```sh
uv run --project tools/map-factory \
  --with ../agentic-research-workbench/place-model \
  python -m unittest discover -s tools/map-factory -p test_place_input.py -v
uvx ruff check tools/map-factory/place_input.py tools/map-factory/test_place_input.py
```

The tests use the real model validator/writers and exercise frame axes, projected
feet/nonzero origins, elevation offset, vertex/cell sampling, crops, grade and
connector identity, water holes/culverts, executable CLI and the existing generator.
They also compile the four committed models when the sibling directory is
available (`PLACE_MODEL_PLACES` can select another checkout). Generated test
artifacts live only in temporary directories. **Asheville source/derived data
is private; do not commit it or publish its target inputs.**

For a source-bound offline comparison of canonical DEM, fitted banks, input PNG
and prepared native terrain, see [terrain fidelity attribution](TERRAIN_FIDELITY.md).
It uses unchanged frozen terrain metrics, separates source/reference disagreement
from exporter edits, and does not replace native qualification.

## Opt-in source-faithful terrain experiment (PL-1244)

`--terrain-policy source-faithful-v2` selects the experimental correction.
The default remains `legacy`; the browser/CLI shipping capture and its byte
contracts are unchanged. The same rule applies to every place, with no city
names, per-place settings, source replacement or judge changes.

- Carving depth is the lesser of the existing 10 source metres and the greater
  of 3 game metres or 10% of the source's p5–p95 relief. Lake flattening may not
  exceed that same source-height cut budget. This is a candidate engineering
  rule, not a calibrated flow/depth guarantee.
- Existing below-sea terrain is retained. Explicit ocean polygons receive only
  a shallow 0.125–0.25 game-metre minimum with a 64 game-metre shoreline ramp
  and smooth transition. The 10 m ocean shelf is removed.
- Source low land is not raised to a fabricated +1 m shelf. Uncarved banks are
  the actual smoothed source elevations under the recorded affine fit.
- Receipts count coastal edits and cut-budget conflicts, and make no flood,
  bathymetry, sustained-wetness or native-qualification claim. In particular,
  retaining real low land can expose flooding that an invented shelf concealed.

The existing water-risk decision still runs and may refuse export. The
experimental policy does not accept, suppress or waive those warnings.
The frozen Charleston DEM failure remains a failure even when terracing improves.
