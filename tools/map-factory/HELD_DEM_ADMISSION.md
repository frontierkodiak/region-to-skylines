# Held-DEM local-stage experiment

Experimental, not the default and not native qualification. The first generic
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

Only a bounded Rio zero/five-minute diagnostic is being prepared. It retains
all 4,256 frozen native observations, including 1,556 required points, and the
actual untouched opening/Areas cameras. No full soak or other map is authorized
by passing that short diagnostic alone. No acceptance contract, historical
fixture or old qualification has been rewritten for this experiment.

## Reproduction

```sh
uv run --project tools/map-factory python tools/map-factory/probe_held_dem_design.py REFERENCE_RUNS PLANS
uv run --project tools/map-factory python tools/map-factory/package_held_dem_design.py PLANS INPUTS --only rio
```

The packager refuses newly unsupported model points or a failed physical
preflight for the selected maps. Its default selects all five, so the current
Pittsburgh result prevents a full-cohort package build. `--only rio` is an
explicit diagnostic subset, not qualification of the remaining maps.

The experimental writer changes source fingerprints. The two source-contract
JS tests correctly reject the old default contract while these hooks are
present; the other six JS tests and 44 writer tests (two opt-in skips) pass.
Do not update the accepted source hashes merely to make this prototype green.
It must either earn new qualification and a reviewed contract or be quarantined
with the default source restored. Charleston's corrected, diagnostic-only
reference attribution is in `PROFILE_ADMISSION.md`.
