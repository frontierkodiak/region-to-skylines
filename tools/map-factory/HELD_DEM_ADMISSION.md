# Held-DEM local-stage experiment

**Rejected after the native short run.** Not the default or native qualification. The first generic
omission proposal remains rejected at `76baf94`; its reviewed quarantine is
`3db3a0f` (PR #42). This experiment tests Opus's PL-973 recommendation to retain
waterways while correcting the datum from which their floors are excavated.

## Rule

1. Use the existing first hydrology pass to identify bank-limited reaches.
2. Remove those source features' inherited browser line and attributable
   polygon cuts, replaying the existing smoothing kernel. Lakes and other
   independently retained features remain separate.
3. Keep the established waterway routes, starting tile and horizontal networks.
   Run ordinary bounded hydrology on the restored terrain. No new incision,
   freeboard, depth, capacity or probe threshold constant is introduced.
4. Retain every interpolation neighbor of the new potential wet floor. Restore
   additional Python excavation outside that support. The existing conservative
   continuous-floor guard checks this restoration, not equality to the OLD
   wet floor: the intended correction raises the old floor itself.

Absolute regulator targets can rise because their `bed + 1 m` datum rises.
This does not raise water over an unchanged old trench. That distinction still
needs the requested steward/lead review before any default promotion.

The stage field is a planning estimate, not a water simulation. It excludes
geographic startup film, includes modeled lakes, and attributes river polygons
to their nearest source line. Native observations decide whether water holds.

## Preflight and stop boundary

The same planner ran on all five maps. Rio's 1,556 required positions remain
supported in the planning field; minimum source-depth and continuous-floor
guards pass. Starting tile 21, all frozen waterway sample coordinates, and all
horizontal network nodes remain unchanged.

Pittsburgh is **not cleared**: its new plan leaves 59 Saw Mill Run points
unsupported that the original planning field supported. Another 310 required
points were already outside the original estimate, despite the prior native
run passing. Neither group is removed, exempted or called a native failure.
The 59 newly unsupported positions block the full five-map sweep.
Freezing the original routes did not remove this loss, so route movement alone
does not explain it. Full source-branch coverage and the new stage/floor field
still need diagnosis; the planner's warning is not an observed native failure.

The bounded Rio diagnostic ran **5.087222 game minutes** at source `a4b9653`,
package `0c08958566c656f21f575211e4a965c6d03e6cfd96b68cb8d9ed1e3c1360075b`.
All **4,256** frozen observations were retained. Required wet-or-within-64m
coverage was **1,556/1,556** at zero and **1,535/1,556 (98.65%)** at five minutes,
above the unchanged 95% gate. This is only two samples, not wet-throughout or
60-minute qualification. The matched baseline had **1,545/1,556** at five;
there are 10 shared, 11 new and 1 old-only dry positions.

**The player-visible requirement fails.** The actual opening still shows a
broad sandy channel, with only part of its width visibly wet. Areas retains
large dry-looking cuts. The opening control at `(-1200,3632)` rose from
86.953125 to **90.3125 m**, but native five-minute water is only **0.84375 m**
deep there. A bounded raised floor and one-metre nominal regulator depth did
not make the channel read as a wet stream. No full soak or other native map
was launched.

Every source control (337) matches the package; initial grids match exactly;
final terrain is unchanged. The camera position, size, angles and render basis
match the frozen baseline in opening and Areas at both epochs. These are raw
native captures, not a wetness inference. Cleanup is empty and the slot is free.

The corrected plan raises 32,883 Rio vertices but also lowers 87 (up to
1.53125 m versus the prior map); it is not a pointwise floor-raising operation.
Its additional channel incision is bounded by the existing 3m limit relative
to its input, but these changes must not be described as "beds only rise".
The same limitation affects 5 Asheville and 28 Pittsburgh vertices.

The experiment remains quarantined. Production `region.py` is restored exactly
to the accepted default. Its proposal is archived in
`fixtures/held-dem-rejected/production-proposal.patch`; replay immutable
`a4b9653` in a separate worktree. The experimental builders refuse the restored
writer. No historical fixture, acceptance threshold or qualification changed.

Before another game run, independently review the relationship between the
fitted stage and the later `bed + 1m` cap, the width of retained native
interpolation support, and full mapped-branch coverage (Saw Mill Run). Do not
assume that raising heads further will solve the image, or silently trade away
freeboard/flooding. The source's water/shore resource calculation also depends
on water surface and surrounding ground; its contribution to the visible sand
is not established by this run. It needs source-bound attribution, not a shader
or mask exemption.

## Reproduction

```sh
uv run --project tools/map-factory python tools/map-factory/probe_held_dem_design.py REFERENCE_RUNS PLANS
uv run --project tools/map-factory python tools/map-factory/package_held_dem_design.py PLANS INPUTS --only rio
```

The packager refuses newly unsupported model points or a failed physical
preflight for the selected maps. Its default selects all five, so the current
Pittsburgh result prevents a full-cohort package build. `--only rio` is an
explicit diagnostic subset, not qualification of the remaining maps.

The intermediate experimental writer changes source fingerprints, so two JS
source-contract tests correctly rejected it; they were not waived or rewritten.
The final quarantine restores the exact default source and re-runs all eight
JS tests and 44 writer tests (two opt-in skips). Charleston's corrected,
diagnostic-only reference attribution is in `PROFILE_ADMISSION.md`.
