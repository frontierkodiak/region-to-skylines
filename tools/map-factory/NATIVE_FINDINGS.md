# Native qualification · PL-857

**Qualification in progress (2026-11-10).** The committed R4+listing fixtures are a
draft byte reference, not a five-region playable-map certificate. Asheville
and Innsbruck completed their prefilled 60-minute soaks; Rio **failed** the
flooding gate. A bank-bounded candidate awaits native tests for Rio and
Pittsburgh. Listing previews and recalculated metadata change every CRP hash,
and a mode-2 north-facing camera now changes the simulation payload too.
Asheville/Innsbruck hydraulic grids, controls and networks remain unchanged,
but the new camera is not covered by their old package checks. New assets need live
New Game checks; the website and installer are unchanged.

Runs use CS1 1.21.1-f9 on blade's RTX 2080 Ti at `05:00.0`. Its existing 150 W
cap and resident inference replica were left unchanged. Harness changes are
in [PR #8](https://github.com/frontierkodiak/region-to-skylines/pull/8).

## Current policy

- Rivers receive native level controls at both ends and fixed 2,048 m arc
  intervals. This represents catchment inflow absent from an endpoint-only
  simulation, independently of verification probe locations. Capacity is 0.8
  for mean gradients at most 0.5%, otherwise 0.2.
- Infeasible overbank river profiles use local bank-bounded stages with 512 m
  and terrain-derived controls, plus final-ground intake/output footprint
  limits. This revision is a pending candidate after the Rio failure below.
- Streams start at at most 0.25 m depth. Their upstream controls target the
  local bed plus 0.25 m; downstream controls target below the bed and have
  **zero output**, so they withdraw excess without introducing a second spring.
  Stream controls within 96 m of mapped major rivers are omitted.
- Lake targets stay below the lowest actual surrounding ground or uncarved
  bank. Some mapped lakes consequently have no inland regulator.
- Additional channel lowering and corridor cut/fill remain capped at 3 m
  relative to the browser export, which already includes its river carve.
- Railway turns are smoothed to at most 45°. This can produce tall viaducts:
  Asheville's maximum rail deck clearance is about 63 m.

`capacity` sets native withdrawal capacity and defaults output to the same
value. Optional `output_capacity` can be zero. Ports must preserve that zero,
not use a truthiness fallback. Natural sources affect a radius of
`10 + 0.4 * sqrt(rate)` metres; a target below the center cell alone does not
prevent injection into lower neighbouring cells.

### Terrain and network geometry

All five preparations reach the 3.0 m additional channel-lowering cap and the
3.0 m corridor cut/fill caps. These are changes relative to the browser export,
not a claim that total river carving from the original DEM is only 3 m.

| Region | Highway entry | Maximum road deck clearance | Maximum rail deck clearance |
| --- | --- | --- | --- |
| Asheville | West | 29.2 m | 62.8 m |
| Innsbruck | East | 15.9 m | 19.1 m |
| Rio de Janeiro | North | 23.0 m | 18.5 m |
| Pittsburgh | East | 62.6 m | 20.7 m |
| Charleston | North | 28.8 m | 29.3 m |

These are offline geometry measurements. Native path checks and city images
qualify reachability separately. Charleston's railway uses the straight
fallback instead of claiming to follow OSM. High bridge decks remain a visual
limitation. New offline-rendered preview assets are not yet native-verified.

## Native evidence so far

The detailed hashes below identify the **tested pre-listing R3 packages**.
Their terrain, initial water, source controls and network inputs still match
current Asheville and Innsbruck; their old starts do not certify the new
preview assets or north-facing camera. Whole simulation hashes now differ.

| Package | 60-minute prefilled soak | Ordinary vanilla city start |
| --- | --- | --- |
| Asheville | Prior R3 completed; same hydraulic inputs | Prior package verified; new listing/camera pending |
| Innsbruck | Prior R3 completed; same hydraulic inputs | Prior package verified; new listing/camera pending |
| Rio de Janeiro | R3 failed; revised candidate pending | Pending |
| Pittsburgh | Revised candidate pending | Pending |
| Charleston | Pending | Pending |

The latest metadata candidate adds checksum-resolvable 400 × 224 and
1,800 × 1,008 textures, blanks the package author in every write, and computes
water totals over central 25 resource tiles. The buildable score is recomputed
with the installed game's weighted flatness formula (Asheville: 70%). These
are offline facts, not a successful New Game panel trial. Resource painting is
separate PL-902 work. Air remains absent until a real flight-path topology is
authored; no misleading metadata-only connection is introduced. The native
New Game UI has no metadata field for a suggested city name.

### Asheville

CRP SHA-256:
`d534a39cbb9c86aa80793b3c4c857c8a31ca1e820b2ab4e48d86320f344c4aad`.

- 60.13 game-minutes. All 28 playable major-river probes are wet exactly at
  every five-minute sample, including startup and the end. All 59 nonboundary
  river probes remain wet exactly throughout. Two physical-edge points end dry.
- Initial native terrain, water and source controls match the prepared inputs.
  Both highway paths and the full rail path pass at start and end; cleanup is
  empty. The selected starting tile retains 691 wet native grid cells, including
  557 deeper than 0.5 m and about 586,000 m³ of water.
- No distant spreading meets the audit threshold in any saved grid. Reviewed
  end-of-soak start-tile and overview frames show the main rivers wet and the
  starter approaches intact. Minor streams are not all perennial.

### Innsbruck

CRP SHA-256:
`95395339e6b814343e3654c6fcd4ca498883e5f6819962a82105133fe82e6572`.

- 60.11 game-minutes. All 35 playable major-river probes are wet exactly at
  the end; two briefly dry exactly during the run, but all 455 native
  neighbourhood observations have water above 0.1 m within 64 m.
- All 90 nonboundary river probes are wet exactly at the end. One physical
  map-boundary point ends dry. Full-map and exact failures remain in the audit.
- Native initial terrain, water and all 147 source controls match the prepared
  inputs. Both 56-segment highway paths and the 173-segment rail path pass at
  the start and end. Teardown leaves no game, Steam, display, bus or sampler.
- Distant spreading reaches at most four grid cells (0.001024 km²), with
  maximum depth 0.703125 m, near a small creek. This is residual shallow
  pooling, **not a zero-flooding result**. No broad inundation appears in the
  reviewed start-tile and overview frames.
- Some highway mesh disappears at an intermediate harness zoom although native
  paths pass. A separate one-minute run confirms complete stubs at size 600,
  missing portions at size 1,800, and complete stubs again at size 3,000.
  The ordinary vanilla city view also shows complete stubs. All 285 native
  segments have matching render parts and LOD data; endpoint bounds are at
  the expected coordinates, and all six path checks pass. This is a
  zoom-dependent visual limitation, not evidence of a broken physical route.
  The underlying renderer/LOD cause is unresolved; it is not silently fixed
  by changing the map geometry.

The ordinary starts used actual `--disableMods --noWorkshop`, an absent control
socket, New Game listing/selection, the checksum-bound installed map and the
loaded city UI. Internal simulation asset names remain opaque template names;
the driver reads the expected name from each CRP rather than confusing it with
the user-visible region label.

### Prefill comparison

The selected R3 Asheville **no-prefill** package completed 60 minutes. Its
terrain and source controls are byte-identical to the prefilled candidate.
All 28 playable river probes start dry, become wet by minute 5 and stay wet at
every subsequent five-minute sample through minute 60. Final volume is
16.261 M m³. No distant spreading appears in saved grids against the **same**
prefilled expected footprint. Native paths and cleanup pass.

The matching prefilled run ends at 16.208 M m³ versus 16.261 M m³ without
prefill, a 0.33% difference. Their mean volumes over minutes 30–60 differ by
0.26%; both retain all 28 playable river probes wet throughout that late
window, with no distant spreading in saved grids. This is a one-region A/B,
not a no-prefill trial of all five regions.

Prefill supplies immediate startup water instead of waiting five minutes for
the channels to fill. It is retained for that startup benefit, not credited
for sustaining the rivers once the sources have settled.

### Rio failure and bank-bounded candidate

The R3 Rio package completed 60.10 minutes with exact input/control matches,
all native paths passing and empty cleanup, but only 323 of 342 playable
river probes wet at the end. Distant spreading reaches 1.651968 km² and
13.765625 m depth. This is a failed default, not a tolerated tiny pond.

The global monotone surface fit could raise water above local uncarved banks
to cross a terrain obstruction while respecting the incision cap: 16.57 m
on Desvio do Rio Joana and 11.25 m on Rio Carioca. Flood components lie near
those forced sources. Real underground drainage also exists here: the city's
[Joana diversion description](https://prefeitura.rio/rio-faz-noticias/prefeitura-inaugura-maior-tunel-de-drenagem-urbana-do-pais-ao-fazer-desvio-do-rio-joana/)
documents a tunnel and gallery. The frozen line geometry lacks coverage tags,
so individual dry probes are not silently reclassified as underground.

The revised candidate caps an infeasible river profile at local banks minus
0.25 m (or sea level), uses 512 m controls plus terrain-derived crests/troughs
on those reaches, and bounds independent native intake/output footprints
against final terrain and mapped water corridors. Feasible profiles retain
the original 2,048 m policy exactly. No region names or failing probe locations
are hard-coded. This is a controlled surface-channel approximation, not a
simulation of buried culverts. Native qualification is still required.

## What the calibration rejected

| Trial | Observation |
| --- | --- |
| Original arbitrary-region Asheville, 207 sources | At 10 minutes, volume rises to 80.28 M m³ and distant spreading reaches 0.522 km². This is not the older two-source PL-848 map. |
| Conservative streams and lake targets | At 10 minutes, distant spreading falls to 0.038 km² but is not eliminated. |
| R0 end controls and actual lake-rim limits | Asheville holds its playable rivers for 60 minutes; Innsbruck has 0.023 km² of shallow creek pooling. |
| R1 below-bed stream tails with larger symmetric capacity | Rejected early: natural source radius still injects into lower neighbours, and withdrawals draw down the Sill. |
| R2 true stream drains and 0.25 m initialization | Pooling shrinks to three cells, but endpoint-only forcing leaves intermittent dry gaps on the 21 km Inn. |
| R3 regularly spaced river controls | Selected candidate under five-region qualification; Innsbruck keeps nearby water throughout the full soak. |

The native pathfinder also isolated an original 108.22° rail bend: individual
chunks passed while the full route failed. The smoothed candidate passes the
complete native route. Topology preservation alone was not sufficient proof.

## Evidence definitions and limits

### Actual playtest-save orientation and pending camera verification

Caleb's actual carbon t=0 save (SHA-256 `8c2adc33…`) was decoded offline and
compared with independently fetched AWS DEM data using harness PR #22 at
`7ec997a`. In the original −0.905° clockwise frame, terrain correlation is
**0.9999 as-is**, versus at most 0.3906 for a wrong rotation/reflection.
Median absolute residual after vertical offset/scale fit is 0.6 m, p95 2.7 m.
The highest interior DEM point is only 1.6 m below that fit; the earlier 58 m
discrepancy was measured in the wrong geographic frame. No terrain transpose
or mirror fix is justified. This is actual game-save terrain, not the writer's
own rendering and not a live mod call.

The same save stores camera yaw 55.7° and pitch 26.32°, rather than a
north-facing view. A candidate now writes a fingerprint-bound native
`SavedCameraView` with NewGameFromMap mode 2, yaw 0°, pitch 60°, size 1,800,
and a terrain-height pivot at the selected tile's centre. Offline verification
decodes every candidate's fields. The first live start and actual Area Zoom
heading still need checking; no north-facing game screenshot is claimed.

Caleb's opening/Area Zoom views raised a possible 90° orientation error. The
writer's own north-up rendering cannot settle it. Four independent landmarks
are now frozen in `fixtures/asheville/landmarks.json`: Sunset Mountain,
Richmond Hill, Beaucatcher Mountain and Busbee Mountain. Coordinates come from
the [USGS GNIS landform service](https://carto.nationalmap.gov/arcgis/rest/services/geonames/MapServer/5);
fresh AWS Terrarium samples supply elevations, converted with the recorded
height-fit transform, not sampled from the prepared map.

Offline prepared heights differ by at most 1.85 m from those independent
expectations. A 12 m tolerance covers DEM/grid smoothing, while Sunset
Mountain alone differs by over 267 m under each of the seven wrong square
rotations/reflections tested offline. This is a discriminating fixture, **not
a native orientation verdict**. Harness PR #8 adds direct native world-height
sampling before camera overrides, startup camera observations, and a strict
`terrain_landmarks` verdict. Live sampling and Area Zoom heading remain pending.

The earlier PL-848 reproduction artifact is reachable by its original
`b8507bf6…` checksum. Its recorded geographic frame has rotation −0.905°,
whereas the current PL-857 Asheville capture is 0°. Do not apply the current
frame blindly to that older package, or claim its identity with Caleb's carbon
file without comparing bytes. Its original height-fit offset also needs to
be established before reusing an absolute-height reference.

Native-source inspection shows `NewGameFromMap` is mode 2. Normal saved
game/editor camera modes are 3/1 and are ignored by the camera reset in mode 2.
A matching mode-2 camera patch is now a byte-verified candidate, not yet a
live-verified start. Area Zoom selects a cardinal
heading from the current camera orientation, so its matching sideways view is
not independent proof of a terrain transpose. The grid remains unchanged;
only the independently identified camera default is being corrected.

`audit_soak.py` checks native initial terrain, water and source controls against
the tested inputs. Exact wetness means native depth above 0.1 m. Nearby-water
evidence uses a 64 m radius and never relabels an exact dry sample. The playable
envelope is the central 25-tile square (`|x|, |z| <= 4800 m`), not just the
starting tile. Physical map-edge probes are reported separately.

Spreading means water deeper than 0.5 m more than 128 m from the prepared
initial water footprint or mapped lines/polygons. Spatial flooding checks
cover saved grids at minutes 0, 15, 30, 45 and 60, not every frame. Exact and
native neighbourhood probes are sampled every five game-minutes.

Minor streams are **not all perennial**. Their failing subsets are retained in
the audits; the 14,615 initial waterway probes must not be presented as 14,615
sustained wet probes. Instrumented soaks use a disabled local control mod and
`--noWorkshop`; they are separate from the strict vanilla starts. New previews
need live validation. No populated-city growth, cross-platform gameplay, stability beyond
60 minutes or qualification of every possible future region is claimed.
