# Native qualification · PL-857

## Current status · complete geographic rivers

The prior fitted-route-only probe plan was insufficient. Independent retained
source-river rasterization found Rio only573/1147central cells within64m of
water at minute60, and Pittsburgh2242/2461, despite green fitted-route probes.
Joana had0/184; a1.74km SawMillRun surface piece was dry. These are real visible
river omissions, not tunnel or minor-stream exceptions. Prior green totals
below are comparative history, **not complete river acceptance**.

Writer1c1f747 retains two-vertex surface river legs at every routing cutoff,
keeps streams' prior minimum, and initializes retained major-river geography
with a shallow bank-bounded film. Supplies remain shallow and locally bounded;
actual carved-bed crests, not verification points, determine added supplies.
`soak.py` independently stages every retained river raster cell. A separate
pyproj/source-segment audit checks full geographic coverage on saved native
grids, without the writer's routing or minimum-length policy. End-only wetness
is insufficient: PR8 also judges every observed five-minute sample.

Fresh `complete-river-candidates` packages (all previous full-package
qualification superseded) are:

| Region | Full CRP SHA-256 | New native qualification |
| --- | --- | --- |
| Asheville | `b66c5c6a3e1518797a52d866d5a5a1af35ce7a745bfc7da665afc86e76f03535` | Native 60-minute PASS and reviewed strict start; 1,736/1,736 central source-river cells near wet through all five grids; no distant spread |
| Innsbruck | `3ba5de0a2cd1477d64aa76bd81d1c3132999674282cc5aff4a24df066fb4a8c6` | Native 60-minute run active; reviewed strict start |
| Rio | `f60d9f4a4b2f222ffeb4fe5efb4b40cbbd90f74047f771e34090764f410c869a` | Rejected at 15 minutes: 0.155904 km2 distant spreading, max 3.859375 m; controlled intake/output/prefill diagnostics queued |
| Pittsburgh | `d32e51a49fa9d65e5a476927696337cf90aae42a202f64f75d6bba4fa9ff1fcd` | Native 60.0636-minute PASS; 2,461/2,461 central source-river cells near wet through all five grids; no distant spread; strict start queued |
| Charleston | `fcea76d840f6733b498fae79b82bb3a91324b600c6d1d906587de28dc247b667` | Native soak queued; strict start completed, images await review |

The later short-source footprint guards change only Rio/Pittsburgh; exact
rebuilds prove all other CRP bytes unchanged. Native geographic probes sample
every five game-minutes; the independent source-segment raster checks saved
grids at 0/15/30/45/60. "Near wet" means actual water within 64 m, not an exact
wetness claim. Pittsburgh's independent raster has 2,159/2,461 exact-wet cells
through all saved grids; all 2,461 are near wet. Exact dry subsets remain in
the evidence, along with physical edges and nonperennial minor streams.

The original short-reach Rio `5b533d62` failed too (0.175104 km2, max 4.546875 m).
Reducing footprint rates changed withdrawal as well as supply and moved some
flooding. `water_diagnostics.py` exports fingerprint-bound matched factors:
zero short output; sea-only initial water; and original portal intake with
bounded output retained. They are causal diagnostics, not qualified defaults.
No distributed intake field or invisible facility-source pump is adopted.

All five full hashes reproduce from newly frozen scratch fixtures; complete
region/resource verification and direct-generator/staging-integrity tests
pass. Scratch fixture authoring is not native acceptance and the old committed
goldens have not yet been promoted. Website/installer remain unchanged.

Charleston's original global DEM comparison remains failed. Native built and
forested land agree much better than the low-variance coastal-water aggregate;
the failed subset and tidal/wetland bed deformation must remain explicit.
Do not flip the grid or conceal those differences with a post-run mask.

## Surface-water qualification · 2026-11-11

### Historical surface-water comparison inventory

These are the resource-bearing `surface-final-candidates` packages, not the
older R3/R4 matrix below. Each native receipt binds the full CRP hash; all
source geometry hashes also independently match generation receipts. New
source-policy candidates remain separate until judged.

| Region | Full CRP SHA-256 | Current native result |
| --- | --- | --- |
| Asheville | `4409846c62af4cc336c13261f1590872f0685d0783c48eebae50f93284ed2251` | 60.0611 min; 28/28 playable and 59/59 nonboundary river probes exactly wet at every sample; no distant spread |
| Innsbruck | `97833522e5bf06c5f8f508ce49109db229fc941a029cd46f5a819c9c7ba12b66` | 60.0267 min; 33/33 playable and 91/91 nonboundary exactly wet at every sample; no distant spread |
| Rio | `117b4d16179853c19527891b55e431ec6559aa47c44add346bd2665024777555` | 60.1100 min; 235/244 exact end wet, 9 ever exact dry; all 3,172 required native64m neighbourhood observations wet; 0.014848km² maximum distant pool, up to2.0625m |
| Pittsburgh | `0e0673e898c13972b57923cbbb4221dbfc2bd3b745f50911288beb782f5eb8ce` | Queued; not yet qualified |
| Charleston | `8f5b5268f00aa7eb789727ea0f98753b4c90d62d23ddbdb8a9f6fa8c3dc25c2c` | Pending; not yet qualified |

All three completed runs have exact initial native terrain/water/control
comparisons, six complete native paths, reviewed actual-window New Game panels,
reviewed untouched opening and real Areas-tool images, independent native DEM
comparison, and empty cleanup. Asheville's four named native landmark residuals
are -1.605/-0.335/-0.925/-1.629m; its actual current/target opening centre is
(-1920,0), native/render heading0°. No camera override precedes that observation.

Asheville and Innsbruck also have independently reviewed ordinary New Game
starts of these exact hashes with `--disableMods --noWorkshop` and no control
socket. Rio's strict start completed and awaits image review. Current native
listing scores are73%/76%/75% for these three; these are native weighted scores,
not geographic flat-land percentages. Exact misses, physical-edge points and
nonperennial minor streams remain in their audits rather than a total-only
headline. Rio's stable small built-up-area pool is not called zero flooding.

### Surface-water classification correction under qualification

The R4 hydraulic trials below forced underground waterways onto the surface.
The [OpenMapTiles schema](https://openmaptiles.org/docs/schema/) explicitly
marks waterway `brunnel=tunnel`. The [Rio municipality's description of the
Joana diversion](https://prefeitura.rio/rio-faz-noticias/prefeitura-inaugura-maior-tunel-de-drenagem-urbana-do-pais-ao-fazer-desvio-do-rio-joana/)
identifies a3.412km route made of2.4km tunnel and1.012km gallery. All72 pinned
Rio vector tiles match their original SHA; all462 frozen river/stream pieces
match exact coordinates/class/name, with zero unknown/ambiguous joins.176
river pieces and24 stream pieces are explicitly underground. DesvioJoana has
both underground and visible pieces: this is not a whole-name exclusion.

The corrected capture retains every excluded feature, properties, native
vector ID, original index, tile URL/hash and coordinate array. It re-carves
from the byte-identical raw DEM and uncarved banks, with the identical sea
mask, geographic frame and fit. No grid rotation or deep running-min incision.
The Python preparation separately normalizes explicit tunnel tags, prevents
short underground gaps from being re-routed/excavated as surface canals and
represents a visible reach entering a tunnel with an output-free drain.
Visible crossings take precedence over another waterway's underground mask.
Underground flow geometry itself is not simulated. Existing short modeled-
reach omissions are now listed, not silently represented as perennial water.
Old failing probes/packages remain historical evidence; new surface-only
packages require new exact-package native qualification and are not yet final.

The first corrected Rio15 trial (`2f9248de…98a00`) has236/244 playable surface
river probes exactly wet at end and all976 nearby readings wet. Exact grids/
controls, six paths, north-facing centred opening/actual Areas, actual-window
New Game review and independent terrain comparison pass. Mapped-corridor
spread falls to0.037888km², but a small residual pool reaches6.8125m; a passing
area threshold alone is not a zero-flood claim. Its nearest surface creek has
an infeasible16.5m overbank profile. Sustained output is now disabled for
infeasible **minor streams** only, retaining their initial fill, geometry,
intake and every probe/dry result. New packages require new native receipts;
the15minute package is not the final reference.

PR27 combines the writer, PR24's resource stage, explicit coastal ocean
evidence and the surface-only correction. The current native matrix uses
`surface-final-candidates` and `surface-final-five-60`; every changed package
is qualified separately. The following R4 matrix is historical and rejected
as a final inventory.
Website and installer remain unchanged. All five earlier R4 resource-bearing
packages had separately reviewed ordinary New Game/city starts with actual
`--disableMods --noWorkshop`, absent control socket and empty cleanup.

### Historical pre-tunnel R4 matrix — superseded

| Region | Historical CRP SHA-256 prefix | Native 60-minute result |
| --- | --- | --- |
| Asheville | `be8b24824972463b` | 28/28 playable river points exactly wet throughout; no distant spread |
| Innsbruck | `5859e371c1a0a7d3` | 34/35 exact end wet; all35 nearby wet throughout; four shallow distant cells |
| Rio | `bc1045d2b8a954d4` | Rejected: 336/342 exact end wet, all nearby wet, 0.353024km² distant flooding, up to4.328125m |
| Pittsburgh | `1acdfbb94ae5daf5` | 79/79 playable points exactly wet throughout; no mapped-corridor distant spread |
| Charleston | `3d6443ff5257fe83` | Rejected starter-water tile; 198/198 exact end wet, transient dry points and 0.115712km² maximum distant spread |

All completed rows have exact native initial grids/controls, six complete
native paths and empty cleanup. Pittsburgh's original first-water-only verdict
flags2.165km²; the independent mapped-corridor audit finds0. These references
are explicitly different, and archived requests are not rewritten. Nearby
water does not silently replace exact dry points. Minor streams are not all
perennial. This remains a draft, not a five-region certificate.

That historical listing matrix has buildable scores73/75/73/79/58. Forest derives exactly from
placed trees; fertile land follows WorldCover, with explicitly labelled
balanced game-convention top-ups. Ore/oil top-ups are not claims of real
deposits. Previews resolve and author is blank in the actual native listings.
The stock city-name field randomizes; it has no map suggested-name metadata.
Air/ship remain honestly absent; no fake metadata-only availability.

Current Asheville actual terrain samples independently match GNIS/DEM; the
1,600-point native comparison is north-up (r=.9999 versus strongest wrong.3727).
Fresh untouched opening and actual Areas tool headings are0 degrees, with
opening pivot exactly at selected tile centre(-1920,0). The player's old saved
terrain also independently matches at its original-.905-degree clockwise frame;
do not transpose/rotate the grid. These save and live observations are distinct.

Native resource-bar telemetry now observes all five actual progress values,
targets and animation states. A paired fresh Asheville capture reports the correct ore value0.4135:
Unity's screenshot draws it empty, but the actual game window at the same
selection shows it filled. PR8 now uses the ownership-checked X11 window as
primary panel evidence, retaining the unchanged Unity image separately. The
actual-window panel and opening/Areas images were manually reviewed and
hash-bound. Native numbers alone never substitute for image review.

### Rejected Rio causal diagnostics

At15minutes, removing only initial land fill leaves the same0.332032km² spill
as the prefilled baseline. Removing all natural output produces0 spill but
dries most rivers. Capping173 bank-limited targets to finished bed+1m retains
all initial inputs/rates/positions but gives only244/342 playable exact end wet,
38 with no64m water, and still0.094720km² spill up to4.015625m. None is a release
policy. The dominant residual Joana source has a downhill escape to off-channel
land beyond its finite safety footprint; local bed head alone cannot guarantee
a safe river. Stream spill also survives, so asymmetric river rates alone do
not explain the result.

## Historical pre-resource qualification notes

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

A read-only recheck of PL-891's completed native `t000-terrain.u16` from
PL-848 package `b8507bf6…` gives the same result in that corrected frame.
Its full grid is byte-identical to the terrain decoded from Caleb's save:
SHA-256 `293d639f53119e7c5903bbd618c6e3a23a1ec4e222dd4e040075a0e4fa9ad6b6`.
This ties the independent DEM comparison to a native game dump as well as the
save. It is not a new live landmark/camera call on the newer PL-857 package.

The same save stores camera yaw 55.7° and pitch 26.32°, rather than a
north-facing view. A candidate now writes a fingerprint-bound native
`SavedCameraView` with NewGameFromMap mode 2, yaw 0°, pitch 60°, size 1,000,
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

## Resource-painted Asheville · native 60 minutes (2026-11-11)

Exact candidate `be8b24824972463b7724ff8788c61d6fc93e5d011e343ed2190ddfa7ad0f3cc3`
completed60.0731 game-minutes in932.74 simulation wall seconds on blade,
`resources-north-asheville-60/asheville`. Native initial terrain/water and all
source controls match the frozen inputs. All28 playable major-river probes
and all59 nonboundary river probes stayed exactly wet at all13 five-minute
samples. Two physical-edge river probes have exact misses; these remain in
`input-audit.json`. Streams are not all perennial (837/1527 playable stream
probes end exactly wet); no all-waterway-perennial claim is made.

All five saved grids have0 distant spreading under the definition above.
All six full native car/train path checks pass; cleanup is empty. The native
1,600-point world-coordinate sampler and independent whole-grid DEM checks
both score r=.9999 as-is; the best incorrect sampler transform is.3727.
Four independent GNIS/DEM landmark errors range−.335 to−1.629m. No grid flip.

The actual native New Game panel was visually reviewed: the map preview is
present, author hidden, resource bars populated and buildable73%. Resource
amounts are forest4,128,915; fertile720,270; ore1,086,916; oil572,359;
water537,588, over max20,631,704. Balanced additions remain labelled map-craft
conventions, not geological/crop evidence. Air and ship remain honestly absent.
The stock editable city name remains random (Rockdale in this capture).

Opening and **actual** GameAreaTool/native AreasVisible views both face0°,
and both PNGs were reviewed/hash-bound. The opening pivot drifted to a corner
because the X11 pointer was at the game-window edge: this run proves heading,
not centring. PR8 parks that pointer without aiming the camera and a separate
same-package short check requires the selected tile centre within64m.
Peak GPU memory10,821 MiB total /2,821 above baseline8,000;136.59 W and54°C,
150 W cap unchanged. This is an instrumented map soak, **not** a strict
`--disableMods` start; the exact-package vanilla batch remains separate.

## Corrected coastal inputs · still experimental

`COAST_EVIDENCE.md` records why elevation-threshold sea classification corrupted
Charleston's low coastal land and the capture-only explicit-ocean correction.
The compound resource candidates are Rio `bc1045d2…bd137` and Charleston
`3d6443ff…56fba`. Old R4 Rio still fails its60-minute native flood check
(0.377600km² distant spreading); no acceptance is transferred to corrected
inputs. Matched no-emission and no-land-prefill diagnostics isolate causes
before another source-policy change. Charleston's independent prepared-grid
comparison still fails (r=.6893 at reference zoom13); it is retained, not
masked. No new coastal package is claimed accepted and no goldens are updated.
