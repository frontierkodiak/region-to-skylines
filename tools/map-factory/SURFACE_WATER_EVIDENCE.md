# Explicit underground waterway evidence — capture-only experiment

2026-11-11; base `fc286bcfe5b7ed067243d17205cdb2fa22dd521e`.
No native job, package, golden, hydrology/probe-policy adoption, website or installer change.

## Primary sources, then exact pinned evidence

The [official OpenMapTiles schema](https://openmaptiles.org/docs/schema/#waterway)
defines waterway `brunnel` as bridge/tunnel and `intermittent=1` as intermittent.
The [Rio municipal project account](https://prefeitura.rio/rio-faz-noticias/prefeitura-inaugura-maior-tunel-de-drenagem-urbana-do-pais-ao-fazer-desvio-do-rio-joana/)
(2019-04-25) describes the 3,412m Joana diversion: 2,400m tunnel plus 1,012m gallery,
including a route beneath Maracanã and Mangueira. This corroborates underground
infrastructure; **names or the article are not an exclusion predicate**.

The actual acceptance input is frozen geometry plus the 72 exact VT URLs and
SHA-256 values in corrected-coast `rio-provenance.json` / `ocean.tiles`, snapshot
`20261101_080013_pt`. Every tile's recorded SHA and HTTP status matched. All
**462** frozen pieces matched uniquely and exactly: **359 rivers + 103 streams**;
unknown **0**, ambiguous **0**. The old water request reports 81 tile jobs (its
500m margin differs from the coastal tile range); the pinned 72 nevertheless
suffice to reproduce every frozen piece. No other tile/snapshot was substituted.

| Frozen pieces | Explicit tunnel | Retained unlabelled | Bridge |
|---|---:|---:|---:|
| Rivers | 176 | 183 | 0 |
| Streams | 24 | 79 | 0 |

All 455 `intermittent=0` / 7 `intermittent=1` tags are preserved as evidence;
there is **no intermittent exclusion policy**. Retention is not proof that every
real underground segment was completely tagged in OSM.

### Mixed Desvio do Rio Joana pieces: no wholesale name removal

| Original river index | Tile14 x/y | VT feature ID | Feature index | Decision |
|---:|---|---:|---:|---|
| 179 | 6224/9263 | 4429433202 | 33 | explicit tunnel |
| 185 | 6224/9263 | 8009003602 | 40 | retain unlabelled |
| 186 | 6224/9263 | 8009003612 | 41 | explicit tunnel |
| 192 | 6224/9263 | 12126004852 | 48 | explicit tunnel |
| 193 | 6224/9263 | 12126004862 | 49 | retain unlabelled |
| 205 | 6225/9263 | 4429433202 | 18 | explicit tunnel |

Tile6224/9263 is the URL in the pinned provenance; feature/piece IDs, all
properties and exact coordinate arrays are archived in `waterway-evidence.json`.
IDs are VT IDs, not an invented promise about OSM object type.

## Implementation contract

`inspect_surface_water.py FROZEN_GEOMETRY PROVENANCE NEW_OUTPUT [--capture]`
uses an own ephemeral HTTP server and unique named headless Playwright session,
closed in `finally`. Without `--capture` it produces inspection evidence only.
It uses the managed CLI, rejects CLI error blocks, and requires a fresh output.

A task-local served copy of the exact `terrain.js` bytes appends only
`export {clipLine};`. The product file is never edited. River decoding reuses
that private native clipping function, native tile extent and the exact existing
five-decimal rounding/conversion. Stream decoding reuses the existing unrounded
`toGeoJSON` behavior. VectorTile2.0.3/Pbf4.0.1 match the original capture imports.

`matchFrozen()` matches class + **exact coordinate arrays** and verifies name;
name alone, proximity, reversed lines and flood positions never qualify. Missing,
duplicate/ambiguous matches, reused source pieces, unrecognized `brunnel`, changed
tile hash/status or missing source/evidence hash binding fail. Filtering never
joins adjacent pieces or bridges an excluded segment.

The optional surface policy keeps `sq`, roads, lakes and riverAreas unchanged;
all retained vector points and original ordering are checked unchanged. It adds:

- `brunnel` and `intermittent` (null means absent, not fabricated evidence).
- `sourceFeature`: `tile.{x,y,z,url,sha256}`, `feature_id`, `feature_index`,
  `line_index`, `piece_index`, original complete `properties`, `original_field`,
  `original_index`.
- `undergroundWaterways`: **all 200 excluded exact pieces**, with those fields,
  recovered `class`, original `name`/`pts`, and
  `exclusionReason="explicit waterway.brunnel=tunnel"`.
- `surfaceWaterPolicy`: source geometry/evidence SHA bindings, complete pinned
  tile receipts, original/retained/excluded counts, and explicit policy caveat.

Only `properties.brunnel === 'tunnel'` excludes a line. Bridges and unlabelled
pieces remain. Frozen water polygons are retained, not newly reclassified by
this waterway-only change. The capture does not simulate underground transport.

For `--capture`, the unchanged browser terrain pipeline starts from fresh raw
DEM, not the already tunnel-carved PNG. `capture.js` accepts explicit pinned
vector evidence, verifies hashes again, and reuses its existing explicit-ocean
rasterization and original carving/fitting/encoding. Surface-policy capture
requires those pinned tiles and never silently uses the latest planet template.

**Parent integration boundary:** Python `hydrology()` may otherwise group same-
name pieces, dilate them and route back across excluded gaps. It must consume
`undergroundWaterways` to preserve underground barriers and handle portals before
these inputs can become a candidate. Neither probes nor original historical
failing subsets were removed here. Original full vectors remain in the source
geometry and archived match evidence; no in-game verdict was changed.

## Controlled Rio recapture receipts

Final output root:
`/home/caleb/scratch/2026-11-11-pl857/surface-water/final-capture/`.
`rio/` contains six browser outputs and `capture.json`; root contains complete
match evidence, source/code hashes, browser log, controlled comparison and
cleanup receipt. No artifact was copied into another checkout or experiment.

- PNG: `611e19e2b2721f0215d1436e3073fff100875c8291a521310d39cdc2012135aa`
- Geometry: `22e33c7411c099e4ae2a86ec327aa130474f2439b69cbc816d72f54630ed9601`
- Raw DEM: `15495e06edf578c499ce4aef35dfd961fd51403ffebbc794d594f6a47a6fedf2`
- Banks: `0788db8fcb982828c858ee51e9d7c78fe98be0613ad9624140071ffe4db19a83`
- Sea mask: `873d084ca0a9ab622bc098de6b7787ca7bba7ab120d88804fffd7c3f0451b027`

Raw DEM, banks and sea mask are **byte-identical** to the corrected-coast originals.
Square unchanged: lon−43.205, lat−22.94, clockwise rotation0, scale1. Fit unchanged:
base−40, verticalScale0.9198811898929851; sea level86.7952475957194. No grid flip,
transpose, coordinate-sign change or second terrain generator was introduced.
Roads/lakes/riverAreas and retained vector points/order remain exact.

PNG comparison: 19,421 pixels raised, **zero lowered**; restoration footprint
4.971776km², maximum restoration7.7814m in the browser's existing game-height frame.
This is restoration of the old carve footprint, **not** measured flooding or a
new exclusion mask. The fresh PNG was reproduced byte-for-byte in independent
foreground recaptures. Geometry/provenance contain timestamps/session origins,
so their whole-file hashes are run-specific; the evidence and per-file bindings
are explicit. Every own browser/server cleanup receipt confirms closure.

## Checks and remaining work

Five real Node test cases cover tunnel vs unlabelled/bridge/intermittent, exact
piece retention/no join across gaps, unknown/duplicate/reversed/name-mismatched
matches, tile SHA/status and missing provenance bindings. Eleven existing ocean
checks also ran in the real isolated browser (including rotated-frame holes and
inland null behavior), not merely as a Node declaration. Changed Python passes
Ruff check/format; JS syntax checks and diff checks pass.

No Python preparation, portal/drainage simulation, resource regeneration, native
60-minute soak, panel/start-area judgment or golden acceptance was performed.
Website/installer and `terrain.js` remain unchanged. This is source-backed input
correction evidence, not proof that default rivers now survive a soak.
