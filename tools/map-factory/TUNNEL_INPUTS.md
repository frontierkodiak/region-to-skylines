# Keep buried rivers out of surface inputs

PL-926 traces Rio's Papa-Couve regression to excavation before the Python
writer sees the inputs. `inputs.js` passed every river to `carveWater`, including
explicit `brunnel=tunnel` pieces. Python's later `surface_geometry` exclusion
prevented new surface water and earthworks on those pieces, but could not undo
the channel already cut into `input.png`.

Both the old canvas capture and the shipping software rasterizer excavated
tunnels. The rasterizer change altered the continuity and depth of that
erroneous cut. At the inlet, the uncarved bank is unchanged at 122.7717 m, while
the input bed changes from 117.2049 to 115.8455 m. In the native south-first
prepared grids, the inlet cell changes from 117.203125 to 115.84375 m.
The inlet target follows that bed down by 1.359375 m.

The earlier claim that the prepared corridor was byte-identical is false in
the native coordinate frame. Between `5f6ef13`'s fixture and `45c3e53`'s fixture,
1,265 terrain cells change by up to 7.25 m inside
`700 <= x <= 1400, 1808 <= z <= 3300`. Those bounds describe the diagnosis,
not an acceptance mask. The old and new source counts are 304 and 305.

## A terrain-only native counterfactual

The matched baseline is exact native package `3bf4326d2ee5…`. A second package,
`48419511b9ed…`, replaces only its prepared terrain with terrain from the corrected
input rule. Its entire serialized `WaterSimulation` is byte-identical, including
all 305 controls, the initial depth grid, zero velocities, sea level and frame.
Networks, resources, listing fields, previews and geographic probes remain fixed.
The simulation checksum reference changes to bind the new terrain.

Both complete ten-minute native runs. Initial native terrain, water and source
controls match their declared inputs, and both leave empty owned-session cleanup.
The same shipping initial-water union geographic footprint defines distant
spread in both arms.

| At the last ten-minute grid | Shipping terrain | Corrected terrain only |
| --- | ---: | ---: |
| Whole-map distant water | 0.108544 km² | 0.028416 km² |
| Central 25-tile distant water | 0.039680 km² | 0.001280 km² |
| Distant water in the Papa-Couve diagnostic window | 0.036352 km² | 0 |
| Maximum depth there | 5.65625 m | 0 |

This isolates the terrain defect without crediting changed source controls or
initial water. It is a short causal diagnostic, not a 60-minute qualification.

A third ten-minute arm restores only the inlet's old 117.453125 m target on
the shipping terrain. All other controls and the initial water stay fixed.
That increases corridor spread from 0.036352 to 0.080896 km² and maximum depth
from 5.65625 to 6.640625 m. Restoring the old target does not repair the
regression.

The complete matched matrix uses the shipping initial water in every arm.
"Other inputs" includes the prepared terrain and all controls except the inlet;
it is not restricted to geographically distant changes. Every arm passes exact
initial native grid/control audits and leaves empty cleanup.

| Other inputs | Inlet target m | Last-grid distant water km² | Papa-Couve window km² |
| --- | ---: | ---: | ---: |
| Shipping | 116.09375 | 0.108544 | 0.036352 |
| Shipping | 117.453125 | 0.153088 | 0.080896 |
| Old fixture | 116.09375 | 0.041472 | 0 |
| Old fixture | 117.453125 | 0.041472 | 0 |
| Corrected terrain, shipping controls | 116.09375 | 0.028416 | 0 |

These are ten-minute diagnostics. The final row is the byte-identical
WaterSimulation counterfactual above, not a different source-policy candidate.
The [frozen results](fixtures/tunnel-input-diagnostics.json) retain full hashes,
source counts, each saved grid and the exact target/control bindings.

## The input rule

`carveSurfaceWater` excludes only explicit river `brunnel=tunnel` pieces from
the upstream surface excavation. The full geographic input is retained for
Python's portal handling and independent audits. Visible crossings, bridges,
intermittent rivers, lakes and river areas keep their existing behavior.
The regression test exercises the original excavation and checks that a real
surface crossing still gets carved.

No source rate, incision depth, acceptance threshold or expected-water mask is
tuned. Minor-stream policy remains PL-912. This models surface water at tunnel
portals, not transport through a buried pipe.

The rule changes Rio, Innsbruck and Pittsburgh terrain and water grids.
Asheville and Charleston reproduce their existing full shipping packages exactly.
Full qualification and remaining failures are recorded in
[NATIVE_FINDINGS.md](NATIVE_FINDINGS.md).

## The separate western flood failure remains

The corrected exact shipping package `d1c6238fd6bf…` completes 60.1156 native
game-minutes. Its maximum distant spread is 0.062464 km², against the unchanged
0.05 km² limit, with a maximum depth of 2.734375 m. The shipping result was
0.120320 km² and 7.140625 m. This remains a failed flood check, not a pass.
It is also above the original PL-857 fixture's 0.050432 km² result.

The original shipping expected-water mask gives 0.120320 to 0.057600 km² over
the same saved-grid schedule. The mapped-water mask is byte-identical. The
improvement therefore does not depend on changing that reference. No distant
water remains in the Papa-Couve diagnostic window in any of the five saved
grids. Central 25-tile spread falls from 0.050176 to 0.001536 km² under each
run's own reference. The starting tile retains zero distant spread.

The larger remaining pools are west of the central 25 tiles, around game
`x=-5.2 km, z=1.6 km` and `x=-7.6 km, z=3.2 km`. These are near the western
Joana/Jacó and Jacaré sectors, not the Papa-Couve tunnel. Their feeding controls
are not isolated by this experiment. Existing minor-channel dryness and the
western failure are retained instead of retuning controls to clear the limit.
The site's notice now describes about 3 m of flooding outside the starting tile.
