# Native qualification · PL-857

**R3 candidate, qualification in progress (2026-11-10).** These fixtures are a
byte reference, not a five-region playable-map certificate. Only the selected
Innsbruck package has completed its prefilled 60-minute soak so far. The
website and installer are unchanged.

Runs use CS1 1.21.1-f9 on blade's RTX 2080 Ti at `05:00.0`. Its existing 150 W
cap and resident inference replica were left unchanged. Harness changes are
in [PR #8](https://github.com/frontierkodiak/region-to-skylines/pull/8).

## Current policy

- Rivers receive native level controls at both ends and fixed 2,048 m arc
  intervals. This represents catchment inflow absent from an endpoint-only
  simulation, independently of verification probe locations. Capacity is 0.8
  for mean gradients at most 0.5%, otherwise 0.2.
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

## Selected-package evidence so far

| Package | 60-minute prefilled soak | Ordinary vanilla city start |
| --- | --- | --- |
| Asheville | Pending | Verified |
| Innsbruck | Completed; details below | Verified |
| Rio de Janeiro | Pending | Pending |
| Pittsburgh | Pending | Pending |
| Charleston | Pending | Pending |

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
- Some highway mesh disappears in the wide harness view although native paths
  pass; the ordinary vanilla city view shows complete stubs. A multi-distance
  render/LOD inspection is pending. Do not infer a broken physical connection
  from that wide frame, or silently omit the visual issue.

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

The selected prefilled Asheville soak is pending, so a final R3 volume
comparison is not yet available. Prefill supplies immediate startup water;
the completed no-prefill run establishes that initialization is not the sole
source sustaining these river channels.

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
`--noWorkshop`; they are separate from the strict vanilla starts. Map previews
are black. No populated-city growth, cross-platform gameplay, stability beyond
60 minutes or qualification of every possible future region is claimed.
