# Short retained surface rivers

PL-857 fix, based on writer `518ac569a9fe8ab08cf8a3ae04d3bcc4dd224d13`.
Green fitted-route probes did not prove that every retained surface river was
modeled. Three 45-vertex gates discarded short names, components and routes,
including visible legs between explicit tunnels.

## Behavior

- Rivers now require two native vertices at each gate. Minor streams retain
  the existing 45-vertex modeling policy. Zero/one-cell islands remain explicit
  native-resolution omissions, not hidden or called modeled.
- Newly modeled short river routes use local bank-bounded stages, shallow
  one-metre channel/prefill/source heads and the existing regulator-footprint
  limits, not deep monotone heads propagated across short barriers. Source head
  is rechecked after corridor earthworks. Existing sea floors take precedence.
- Adaptive endpoint insets preserve upstream/downstream order on two-point
  reaches. One eligible interior point gets one control, not duplicates.
- Explicit tunnel barriers, non-injecting tunnel-inlet drains, independent
  bed-crest supply and individual 3 m channel/corridor excavation caps remain.
  New sources/summaries carry `short_surface_river` provenance.
- After hydraulic/lake passes, source-geographic initialization adds at most
  0.25 m water to retained major-river raster cells below the uncarved-bank
  ceiling. Existing deeper water/ocean wins. It raises no ground/banks, seeds
  no arbitrary probes and bridges no explicitly omitted tunnel.
- `geographic_river_prefill` reports mapped/film-added/unseeded cell counts,
  insufficient bank-clearance counts and every unseeded world position.
  Safe depth <=0.1 m remains an unseeded diagnostic. Coverage accounting now
  includes all nonempty masks, including short unmodeled streams.

This changes modeling/initialization, not acceptance thresholds or native
physics. Full source-geographic probes must prove sustained water and no
flooding. Never hide failures by reverting to fitted-route cohorts.

## Offline receipts

New unpainted candidates used exact frozen `surface-final-inputs` Rio/Pittsburgh
PNG, geometry and banks. Independent pyproj frame0/17,280 m full-line raster
coverage against prepared native-order water grids gives startup-only results:

| Case | River controls | Routed river samples | Central25 exact wet | Central25 within 64 m |
| --- | ---: | ---: | ---: | ---: |
| Rio | 76 → 288 | 742 → 1,676 | 468 → 940 / 1,147 | 594 → 1,147 / 1,147 |
| Pittsburgh | 42 → 63 | 246 → 361 | 1,731 → 2,173 / 2,461 | 1,769 → 2,461 / 2,461 |

All-map within64m: Rio3,035/3,035, Pittsburgh6,224/6,224. Exact-cell coverage:
2,669/3,035 and5,792/6,224. Different independent/writer raster conventions and
local routing remain visible in exact coverage. Writer reports one unseeded
Rio cell at world `(3600, 464)` with insufficient bank clearance; Pittsburgh0.
Do not hide it because nearby water exists.

Geometry is byte-identical; terrain/water and all four CRP assets (simulation,
metadata, two previews) changed. Rio start tile22→21; Pittsburgh12 unchanged.
Pittsburgh node positions are unchanged; Rio's changed with start placement.
New-versus-old terrain deltas can exceed3m because bounded hydrology/corridor
passes and placement differ; each individual excavation cap remains3m.
Every changed package requires fresh native/resource qualification. No prior
package hash/acceptance carries forward.

Behavior tests cover short tunnel-separated legs, two-vertex endpoint order,
one-cell omissions, unchanged short-stream modeling, post-corridor shallow
heads, ocean preservation, source-geographic film without route samples and
honest unsafe-bank omissions. No game/Steam/GPU/service actions were performed;
prepared-grid results are not native acceptance.

## Bounded short-source footprint correction

Native full-geography pilots exposed two distinct limits of shallow initial
water: portal intake can drain higher visible cells within its native footprint,
and broad prefill can incorrectly authorize a short supply to emit across an
omitted tunnel or into an adjacent lower valley. A one-metre head bound at the
source center does not bound the head over every lower cell in its radius.

For short sources only:

- Portal inlet withdrawal now uses the same high-bed clearance rule as other
  local-stage intake. Keep the original low target and **zero output**; retain
  a local sink without withdrawing from a neighboring higher visible reach.
- Output must fit the retained source-geographic channel envelope: the existing
  four-cell surface-line margin and genuine mapped lake/river-area polygons,
  excluding the existing explicit tunnel barriers. Global water/sea prefill
  does not enlarge that envelope. No surface or underground geometry is added.
- Capacity follows the native radius law, not a chosen rate multiplier:
  `radius = 10 + 0.4 * sqrt(encoded_rate)`. With nearest unsafe cell distance d,
  limit encoded rate to `floor((max(0, d-0.01-10)/0.4)^2)`, never above the
  requested rate. A cell 16 m away therefore bounds the rate to224/65535 and
  radius below16m. Intake/output remain independent; a zero-output portal
  remains zero. Existing bank ceilings/head bounds stay in force.
- Every short source records before/after encoded rates, radii and nearest
  unsafe intake/output cell distances in `short_source_footprint`. Summary
  `short_source_footprints` counts controls and intake/output reductions.
  Report zero rates honestly rather than moving controls or widening geometry.

Endpoint-crest additions are **deferred**, not included in this correction.
Some real endpoint/remainder cells may still dry; unchanged native probes and
full geographic cohorts must report them. The guard changes no terrain, initial
water, target, source position or source count. All five exact-input package
hashes must nevertheless be compared; any changed package needs a new pilot.

### Guard-only five-case comparison

All five cases were freshly generated from the same frozen source inputs and
compared against the exact `1c1f747` complete-river unpainted preparations:

| Case | CRP identity | Effective intake/output rate changes |
| --- | --- | ---: |
| Rio | changed | 60 / 60 |
| Pittsburgh | changed | 2 / 3 |
| Asheville | byte-identical | 0 / 0 |
| Innsbruck | byte-identical | 0 / 0 |
| Charleston | byte-identical | 0 / 0 |

In all five, geometry, terrain and initial water grids are byte-identical;
source counts, positions, targets and roles are identical; every non-short
source is unchanged. No non-portal short supply lost all output. Rio/Pittsburgh
simulation and metadata asset hashes changed; their two preview payloads did
not. Unchanged cases retain their exact CRP bytes, not manually restored hashes.
These are bounded offline receipts only; new native dry/flood results decide
whether the correction works. Endpoint crest additions remain deferred.
