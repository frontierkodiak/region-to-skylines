# Experimental CS1 map-file prototype (PL-848)

These offline tools demonstrate a ready-to-play Asheville `.crp` without game
DLLs or a player-side companion mod. **They are not connected to the web app and
are not a generic arbitrary-region exporter.** The shipped heightmap workflow
is unchanged.

## What is implemented

- `prepare.py` conditions the two Asheville rivers to a connected descending
  profile and produces native-order terrain/depth grids from the exported PNG
  and the matching basemap water geometry.
- `crp.py` rebuilds a fingerprint-bound native template's terrain, water cells
  and natural sources, updates package checksums and metadata references, and
  removes the factory's mod references from map metadata.
- `verify.py` checks the real native package's byte-exact roundtrip, decoded
  heights, encoded-array edge values, a separate one-metre terrain change and
  refusal of the wrong template.

The template, layout and inputs are in the **PL-848 evidence attachment**, not
this repository. No proprietary game assembly or decompiled source is bundled.
The factory created the template with the installed game's serializer. It
followed OSM highway/rail alignments, selected native outside-connection and
bridge variants, and initialized the starting tile. The standalone writer
**preserves** its networks, buildings, lanes, resource maps, trees, starting
area and serializer reference tables. It cannot transplant those correctly to
a new region. The template has no forest/oil/ore/fertility and no map thumbnail;
those are remaining content work, not supported exports.

## Reproduce the bounded writer

From this directory, with the evidence archive extracted as `ARTIFACTS`:

```sh
uv sync --locked
uv run python verify.py ARTIFACTS
uv run python crp.py \
  ARTIFACTS/PL848-Asheville-template.crp ARTIFACTS/template-layout.json \
  ARTIFACTS/terrain.u16 ARTIFACTS/water.u16 ARTIFACTS/hydrology.json \
  ARTIFACTS/PL848-Asheville.crp
```

`terrain.u16` and `water.u16` are little-endian unsigned 16-bit arrays of
1081 × 1081 values, south to north, with 64 units per metre. Water values are
**depths**, not absolute surface levels. The CRP inner serializer uses big-endian
numbers; its enclosing package directory uses little-endian numbers. Layout
ranges include shared-string manager tags and are valid only for the exact
SHA-256-bound template. Ground-network terrain deltas are explicitly refused.

To reproduce the hydrology preparation (fixed Asheville fixture coordinates):

```sh
uv run python prepare.py ARTIFACTS/kudzu-asheville.png \
  ARTIFACTS/water-geometry.json ARTIFACTS
```

The output has a 3.5 m nominal channel depth, a descending hydraulic profile and
prefilled water. It lowers only a narrow corridor, but the maximum correction
in this fixture is 26.73 m. This is **not** a universally safe terrain-editing
rule. Rivers need continuity, bridge clearance and live flood checks; a source
at each edge plus the original fixed 10 m carve was insufficient.

## Verification scope

On worm's native CS1 1.21.1-f9, the offline output appeared in the ordinary
**New Game** list and started a normal city with starting-tile water, one road
connection each way and two rail connections each way. The native pathfinder
traversed every segment of both highway approaches and the boundary-to-boundary
rail route. The game was used to validate the result, not to run `crp.py`.

The prototype does not import a complete city, place services or demonstrate
population growth. It is not a long-duration water-stability certification or
a Windows/macOS compatibility test. See the PL-848 findings attachment for
final runtime checks and residuals.

## Direction

Direct `.crp` output is technically feasible. A production browser writer still
needs network/building/lane serializers, geographic resources and vegetation,
map previews, general starting-area selection, and hydraulic admission checks.
Keep a native factory as the serializer oracle and playable-map regression
harness. Do not make Workshop publication or a companion mod a prerequisite
for the player's downloaded map.
