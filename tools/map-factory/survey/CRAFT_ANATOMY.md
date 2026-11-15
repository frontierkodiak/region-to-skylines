# Craft anatomy: what playable maps store (PL-979)

`survey/craft_anatomy.py` reads exact `.crp` bytes and reports what a map stores
at load time: terrain, startup water, water sources, channels, trees, resources,
the prebuilt network and the theme. It never runs the game. Theme packages are
identified as themes, not measured as maps.

## Re-run

```sh
uv run --project tools/map-factory python tools/map-factory/survey/craft_anatomy.py \
  --out "$HOME/experiments/PL-979-map-craft/anatomy" [CRP ...] [--prepared-root DIR]
```

With no CRP arguments it reads every `*.crp` under the output directory's
`inputs/`. An explicit output directory keeps run artifacts out of source. A shipping
package named `PL857-<region>.crp` must match `fixtures/current.json` (SHA-256
and byte count) or the run stops. `--prepared-root DIR` additionally compares
shipping packages with the generator inputs in `DIR/<region>/` (`terrain.u16`,
`water.u16`, `hydrology.json`). The run takes about 15 s for eight packages.
To add the next Workshop map, pass its path or copy it to
`anatomy/inputs/workshop/`.

## Outputs

- `anatomy/summary.json` holds one comparable row per package and the caveats.
- `anatomy/manifest.json` lists input SHA-256, bytes, role, contract match and
  per-asset MD5 checks.
- `anatomy/maps/<slug>/metrics.json` holds the full measurements.
- `anatomy/maps/<slug>/*.png` holds the diagrams (central 25 tiles in white,
  start tile in yellow):
  - `overview.png`: hillshade, sea-connected water (dark blue), inland water
    (light blue), water sources (red rings), network by class, outside nodes
    (white squares).
  - `channels.png`: 1081 px, one pixel per 16 m node. Channels are coloured by
    sampled width, red narrow to blue wide; open water is slate.
  - `trees.png`: tree density per 64 m square.
  - `resources.png`: the 512×512 resource grid.
- `anatomy/inputs/` holds byte copies of every input.

| Input | Source | SHA-256 |
| --- | --- | --- |
| PL857-{asheville,innsbruck,rio,pittsburgh,charleston}.crp | blade `~/experiments/PL-912-minor-streams/inputs/<region>/` | equal to `fixtures/current.json` shipping hashes (see manifest) |
| 7th Island Enhanced.crp | Workshop 1371511817 | `f5785b5e…0988` |
| Boulder Rapids v2.crp | Workshop 409024545 | `f8b0b44a…42e1` |
| Rhinestone Island V1%002E0%002E5.crp | Workshop 741034081 | `6929d83f…7714` |

The staged copies (`staged/maps/*`) carry the same hashes. No historical or
rejected packages were used.

## Decoding

Packages count as maps only with a kind-52 serialized payload and kind-100
MapMetaData. A kind-106 MapThemeMetaData package is a theme. A kind-52 payload
without kind 100 is reported as `not_a_map`. Version gates follow the game's
`Data.Deserialize` methods, read from the decompiled Assembly-CSharp on blade
(`~/scratch/2026-11-15-pl984-decompile`, not redistributed). Those gates cover
DataSerializer versions 206 (Boulder Rapids, 2015), 110025 (7th Island, 2018)
and 121034 (shipping).

- **WaterSimulation** is decoded to its last field: depth, pollution, both
  velocity arrays with their neighbour-mask counts, sources (pre- and post-v184
  layouts), waves (v259 and later), sea level, dispose rates and frame index. In
  every map the `InstanceManager` tag follows the decoded end exactly 2 bytes
  later, which confirms the byte alignment.
- **NetManager** is decoded through lanes, node and segment arrays, records, the
  NetInfo name table and, where present, the tree and fence tables. The
  node-problem array between v221 and v115000 depends on the save app version;
  the reader tries ULong first, falls back to UInt, and accepts a parse only if
  every check passes. The checks: each segment's endpoints exist and list that
  segment, each node's segment references exist, positions are finite, and
  prefab indices fall inside the name table. Any failure is reported as
  `"status": "unknown"` with a reason, never as zeros. All 7 maps decode.
- **Metadata** uses PackageDeserializer field records, including Vector3, Color
  and DisasterSettings. ModInfo is a string plus a UInt64. Zero padding after
  the last field is recorded, not flagged. A field stored as null has no name on
  disk, so absent keys read `null`. An undecodable type stops parsing and names
  itself.
- Terrain, resources, trees and the start tile reuse the readers in
  `measure_maps.py`.

### Verification against bytes

- For all five shipping maps, the decoded terrain and water arrays are
  bit-identical to the generator's `terrain.u16` and `water.u16`. Sources
  (x/z, target, input and output rates), sea level, start tile and all 288
  network node positions also match `hydrology.json`.
- Every asset MD5 in every package matches its directory entry.
- Tree positions fall within ±8640 m and all prefab indices are within their
  name tables.
- An independent axis-run check confirms the channel widths. At every ridge
  sample the wet run along x or z is at least the EDT width in 99.1–100% of
  samples; medians are equal for axis-aligned channels (3 = 3 cells for
  Asheville).
- The overlays were inspected by eye: sources sit at stream heads and channel
  ends, outside nodes sit on the map edge, and routes follow the decoded nodes.

## Definitions

- **Grid**: node `i` is at world `(i − 540)·16 m`. Arrays are `[z, x]`. The
  central 25 tiles span |x|, |z| ≤ 4800 m. The start tile comes from
  GameAreaManager.
- **Startup coverage**: stored depth > 0, ≥ 0.5 m and ≥ 2 m, reported for the
  full map, the central 25 tiles and the start tile. **Sea-connected** water
  has a surface within 3 m of the stored sea level and is 8-connected to the
  border. The 3 m margin is needed because saved Workshop oceans undulate about
  ±2 m (Boulder Rapids p1–p99 runs 38.1–41.1 m around 40 m).
- **Channels**: water at least 0.125 m deep, outside open water. Open water is
  the opening of that mask by a 12-node-radius disk (roughly 400 m across),
  plus shoreline nodes within 2 nodes of it whose bank distance is at most 2.5
  nodes. Components are 8-connected; those under 4 nodes are dropped and
  counted. Width is sampled on the ridge of the bank-distance transform (EDT
  equal to its 3×3 maximum) as `(2·EDT − 1)·16 m`, so the narrowest
  resolvable channel is 16 m. Depth and surface are sampled on the same ridge
  nodes. `ridge_length_m` is ridge samples × 16 m: even-width plateaus
  double-count and diagonals under-count, so treat it as ±40%. The width
  histogram's top bin `13` means 13 cells or more.
- **Water sources** keep their raw fields: type, input and output positions,
  `m_target`/64 as the target surface in metres, and raw `m_inputRate`,
  `m_outputRate`, `m_water`, `m_pollution` and `m_flow`. Behaviour comes from
  `WaterSimulation`'s step code. Each step a natural source drains stored depth
  above max(target, terrain) within `sqrt(inputRate)·0.4 + 10` m, capped by
  the input rate and half the excess. It fills nodes whose terrain is below
  target within `sqrt(outputRate)·0.4 + 10` m, capped by the output rate and
  half the deficit. `m_flow` is the amount added in the last step and is reset
  every step. It is a counter, not discharge, and no unit conversion to m³/s is
  claimed.
- **Slope**: the central-difference gradient of raw heights over 16 m, on dry
  nodes (depth exactly 0). Results are cumulative shares under 1/3/6/10/15/25%.
  The metadata `buildableArea` is the editor's stored percentage, reported
  beside the slope shares and never mixed with them.
- **Trees**: created instances only. Clustering in the central 25 tiles uses
  the nearest-neighbour distance, the Clark–Evans R (no edge correction), the
  occupied share of 100 m cells, and the share of trees in the densest 10% of
  cells.
- **Network class** is a keyword rule on NetInfo names. Segment length is the
  chord between nodes, not the Bezier arc. Outside nodes carry flag `0x400`.
  Metadata in/out counts are editor-stored, and one two-way outside node can
  count as both in and out, so the two need not be equal.

## Results

| | Asheville | Charleston | Innsbruck | Pittsburgh | Rio | 7th Island | Boulder Rapids |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| data version | 121034 | 121034 | 121034 | 121034 | 121034 | 110025 | 206 |
| theme / environment | Sunny, none | Sunny, none | Sunny, none | Sunny, none | Sunny, none | Tropical, Rhinestone Island | Sunny, none |
| relief p1–p99 full / central25 (m) | 406 / 296 | 29 / 17 | 831 / 771 | 171 / 164 | 629 / 613 | 972 / 826 | 879 / 456 |
| central25 dry land (km²) | 90.0 | 54.1 | 91.4 | 88.0 | 76.8 | 68.0 | 69.7 |
| … share < 6% slope | 0.19 | 0.96 | 0.36 | 0.27 | 0.21 | 0.25 | 0.34 |
| metadata buildableArea | 73 | 58 | 76 | 79 | 75 | 55 | 55 |
| startup wet, full map (km²) | 6.3 | 99.8 | 2.4 | 10.5 | 134.9 | 106.2 | 92.9 |
| startup wet share, central25 | 0.027 | 0.414 | 0.011 | 0.049 | 0.169 | 0.264 | 0.246 |
| stored sea level (m) | 0 | 90 | 0 | 0 | 86.8 | 33.8 | 40 |
| water sources (in central25) | 110 (36) | 45 (6) | 38 (18) | 73 (25) | 290 (137) | 12 (4) | 9 (6) |
| drain-only sources | 30 | 1 | 10 | 7 | 71 | 0 | 0 (1 disabled) |
| distinct raw rates | 655…52428 | 655…52428 | 655…52428 | 224…52428 | 224…52428 | 32767 | 33422, 65535 |
| channels / channel km² | 45 / 6.2 | 289 / 17.3 | 16 / 2.4 | 13 / 10.1 | 156 / 4.7 | 103 / 13.8 | 2 / 7.1 |
| ridge width p50 (m) | 48 | 48 | 48 | 48 | 48 | 56 | 156 |
| ridge depth p50 (m) | 0.25 | 2.0 | 2.25 | 4.9 | 1.0 | 11.7 | 20.1 |
| stored velocity (non-zero nodes) | 0 | 0 | 0 | 0 | 0 | 411,947 | 361,802 |
| trees (species) | 179,654 (4) | 179,868 (4) | 179,911 (4) | 179,428 (4) | 176,290 (5) | 246,489 (8) | 68,858 (6) |
| Clark–Evans R, central25 | 0.44 | 0.41 | 0.51 | 0.50 | 0.47 | 0.67 | 0.83 |
| ore / oil / fertile / forest, central25 (km²) | 8.5/6.0/6.7/18.2 | 7.5/4.4/17.5/15.9 | 9.9/4.7/19.5/23.7 | 8.8/5.9/4.2/23.5 | 9.6/5.7/2.7/21.3 | 19.3/6.8/8.4/33.0 | 14.2/13.0/9.1/32.6 |
| network segments | 285 | 285 | 285 | 285 | 285 | 3216 | 1735 |
| outside nodes road/rail/ship/air | 2/2/0/0 | 2/2/0/0 | 2/2/0/0 | 2/2/0/0 | 2/2/0/0 | 8/4/4/4 | 6/2/4/4 |
| metadata in+out road/rail/ship/plane | 1+1/2+2/0/0 | same | same | same | same | 4+4 each | 3+3/2+2/4+4/4+4 |

What stands out:

- **Water sources**: the Workshop maps use a handful of strong sources (9–12,
  raw rate 32767–65535) at river heads and the map edge. Shipping maps use
  38–290 sources, mostly weak (655) stream regulators, and 7–71 drain-only
  sinks. Both Workshop maps were saved after simulating, so they carry a
  velocity snapshot and their oceans sit about ±2 m off sea level. Shipping
  maps store zero velocity and an exactly flat sea.
- **Channels**: shipping channels are mostly 1–3 nodes wide (16–48 m). In
  Asheville the median ridge depth is 0.25 m, which is very shallow. Workshop
  rivers are much deeper (median 12–20 m) and wider (Boulder Rapids median
  156 m, a single river system).
- **Network**: every shipping map has one road and one rail route (3
  components, 285 segments, all elevated). The Workshop maps prebuild
  highways, rail, ship and air paths. 7th Island also has 5 "Castle Wall"
  segments classed `other` and 4 isolated degree-0 nodes.
- **Trees**: shipping maps are about 180k trees of 4–5 species, more clustered
  (R 0.41–0.51) than the Workshop maps (R 0.67–0.83). Pittsburgh's start tile
  has no trees.
- **Theme**: 7th Island's `mapThemeRef` is `741034081.Rhinestone Island V1.0.5`.
  It resolves locally to the Rhinestone Island package (Tropical; 22 textures,
  20 texture overrides; water colours, temperatures and weather probabilities
  in its metrics). Rhinestone Island is **a theme, not a map**: it has no
  terrain, water or network, and none is reported.

## Caveats

- Everything here is static storage. The depth, velocity and source counters
  are a save-time snapshot; nothing predicts how water moves after load or
  whether a channel stays wet.
- Source rates and `m_flow` are raw game units per water step. Neither is
  physical discharge.
- Shipping heights are a regenerated product. They match the generator inputs
  bit for bit, but no native in-game state is implied (see
  `CURRENT_FIXTURE_CONTRACT.md` for what is and isn't native-verified).
- BuildingManager (outside-connection buildings, prebuilt buildings) is not
  decoded.
- The network classes depend on prefab names; a modded network with an unusual
  name falls in `other`.
