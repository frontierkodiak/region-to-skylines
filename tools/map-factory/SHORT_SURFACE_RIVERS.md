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
