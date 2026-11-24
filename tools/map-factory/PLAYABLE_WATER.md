# Water built for play

The November 23 owner decision allows deeper beds, wider channels, raised banks,
deep lakes and a coastal shelf. The mapped river/coast should remain recognizable;
land outside the water-authoring strip stays measured. This replaces the earlier
isolated-retrofit restriction, not the historical evidence or its labels.

## Construction

`region.hydrology` and the standalone `prepare.py` both use `playable_water.py`.
It authors every captured visible river/stream, lakes, river areas and ocean:

- Channels start 8 m deep, with 24–112 m half-width increasing with map-local
  contributing area. Sloping sides join the measured valley.
- A priority-flood D8 drainage model supplies local catchment area. Source
  capacity is a bounded `0.008 * sqrt(km²)` game setting, not measured discharge.
  Catchment beyond the captured square is unknown.
- Each chosen source gets an 8 m inlet pool (16 m for body controls) across
  the retained radius model, `10 + 0.4 * sqrt(encoded rate)`, with sloping sides.
  A nearby explicit underground gap limits the setting instead of being cut.
  Both the requested catchment setting and any geometric reduction are recorded.
- A source-space drainage tree chooses outlets at sea or the map edge where
  available. Short captured gaps up to 160 m can join; explicit underground gaps
  cannot. Closed captured components are recorded explicitly; an intake-only
  terminal is placed where the existing source-spacing rule permits it. These
  are **not** represented as real edge outlets, and a recorded terminal does
  not prove that a sink was placed or that its capacity is sufficient.
- Local surface limits prevent a high captured sill from raising a whole river
  or cutting an entire valley down. This can leave cascades; it is not a claim
  that all branches form one gently graded hydraulic reach.
- Lakes/river areas are deepened to at least 16 m, with body-level controls.
  Ocean gets an 8–24 m shelf. Existing deeper beds are retained.
- A 2 m shoreline barrier blends back to measured land over 64 m. No global
  sea-plane prefill is used. Terrain away from this strip is unchanged.

These are gameplay settings to test in the game, not a fitted physical model.
No old native qualification applies to this constructor.

### Joint surface correction

The complete channel widths, body margins and source-pool footprint are formed
before the final surface is solved. `joint_surface.py` contracts level lake/ocean
bodies, removes incompatible adjacent heads, and routes each component toward a
receiving port. The preferred descending grade is 1 m/km; a 2% maximum fitted
grade is an engineering choice for this construction, not a measured game rule.
If necessary, a whole component is vertically compressed to fit the engine's
height range. No independent DEM clipping or flat source-disk reset follows.
Beds, initial depths and source targets all use that one quantized surface.
Immediate banks clear the maximum adjacent head, not merely the nearest one.

## Practitioner basis

[MB's mapping guide](https://steamcommunity.com/sharedfiles/filedetails/?id=1782964859)
recommends a roughly 30 m wide, at least 8 m deep starting river, gentle slope,
small capacity settings and replenishment along the river.
[Rolfil](https://steamcommunity.com/sharedfiles/filedetails/?id=598419805)
distinguishes source capacity from target level and describes shaping beds,
tributaries and outlets together. These are practitioner starting points, not
universal capacity guarantees. Reusable notes and other primary examples are in
[the shared authoring reference](https://github.com/polli-labs/knowledge/blob/main/data/cs1-water-authoring.md).

## Fixed comparison

`calibration/pl1191-construction-v1/gameplay-water/eight-squares.json` fixed the
five fixtures and the three remaining named presets before implementation:
Asheville, Innsbruck, Rio, Pittsburgh, Charleston, Grand Canyon, Hong Kong and
Yosemite. The extra three are development comparisons, not an unseen holdout.
Inputs are shared between before and after. Baseline openings are short runs;
changed maps receive 60 game-minutes with saved grids every 5 minutes.

The first native constructor attempt is retained separately: Asheville completed
60 minutes with drying; Innsbruck was interrupted and cleaned up after a CPU
check found sources straddling shallow/dry footprint cells. The inlet-pool
correction is a new physical construction, not a rerun to repair reporting.
That correction also failed Asheville: local surface seams and below-head banks
remained. Full-field checks found this defect on every prepared square. The
joint-surface revision keeps source locations and packed rates fixed while
changing their targets and the coupled bed/bank geometry; failed attempts remain
separate evidence.

The existing full source inventory and old probes remain. Unsupported inventory
rows stay visible. Compiled-only startup success is not complete source coverage.
Flooding, drying and resemblance are reported separately; one verdict per square
goes to the existing Stable water capability row. Old studies are not rescored.
