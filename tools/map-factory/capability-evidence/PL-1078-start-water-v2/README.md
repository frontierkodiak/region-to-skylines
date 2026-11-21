# Frozen start and water study

This is an immutable study snapshot, not a second capability inventory.
PL-1119 owns `capabilities.json`, the browser and ledger integration.

## Sources and ordering

The final 4a4 player passed both registered first-hour stock controls. The
original eight were then rerun and frozen before any capability implementation:
3/8 first-hour passes, 2/8 strict full-map passes. Historical 1/8 is unqualified;
the observed difference is player work, not exporter-rule improvement.

All eleven regenerated CRPs, terrain/water grids and resource plans at exporter
`56bd3ca582db7de026f9669b5fa42b6640fefef8` match the pre-rule baseline byte-for-byte.
Every water-risk warning remains. Final assessment
`83fa0ec27324dd4c4db8c6342e9600f76c3ddc41` changes oracle-protocol metadata on the
same final inputs. It does not change a map or the qualified player.

`predictions.json` was frozen before any holdout native outcome. Its SHA-256 is
`fd3875416400e1d13cf94f3bd77a75e1c34da1f2ba5481a7ee5f7abec2679087`; combined
model SHA-256 is `bb2684981f33f5e578c2d9e1a3fba30e4bbab57e0fea332235c1d0e50e30e604`.
The original eight are fitting data; the three hash/offset-selected regional
holdouts are not a global random sample. Do not rewrite predictions after results.

## Component interfaces

| Component | Implementation | Native meaning |
|:--|:--|:--|
| Start/site/hookup | `start_capabilities.start_witness` | Exact declared road construction, then sampled passenger-car paths to literal outside endpoints |
| Surface water | `surface_intake.assess_surface` | One declared native shore snap per anchor, checked facilities/pipes, fixed spatial consumer load |

The exporter writes advisory `start-capabilities.json` before serialization.
Limits and witness/model/input hashes travel with each capability fragment.
Missing finite-search witnesses stay unknown. Missing authored outside anchors
are negatives only for the present plan, not geography or every possible generator.
Neither component emits `promised`.

Start paths are **after the declared starter-road construction**. Do not import
them into a fresh-map outside-road certificate or infer freight, spawning,
continuous capacity or first-hour service from them. The archived v1 fitting
study in `../PL-1078-start-v1/` retains both collision false positives; do not mix
its model with current-model agreement. Group by model, oracle and fitting/holdout
role. A rejected witness is not proof that the square has no other legal plan.

The water load uses explicit auxiliary power, 1000 native water/sewage units per
256 simulation frames, two minutes of loaded settling and sixty scored minutes.
It is not a population or SI-rate conversion, a power-generation proof, an
indefinite-flow guarantee or a groundwater-based surface-water positive.
In raw cycle records, `loaded` marks the scored phase, not whether a request
was applied: `settling_has_load=true` and `settling_samples` separately retain
the same load during the unscored settling phase.

## Reference calibration

The first mixed-API diagnostic was interrupted and remains unscored under
`history/`. No hydrology fault is attributed to it.

The revised Cliffside Bay reference completed 60.0103 scored minutes. All 843
requests received full water and sewage quantities with healthy auxiliaries;
733 deliveries were polluted. Thus quantity support is positive, but clean
service is false. Reference anchors were selected geometrically and their
upstream/cleanliness relationship was unpredicted (`predicted=null`), so this is
not a model agreement score or a stock-map incapability claim. Cleanup is empty.
Foggy Hills completed 60.0119 scored minutes: all 843 requests received full
water and sewage quantities, with no polluted delivery or auxiliary fault.
Both references therefore support the fixed **quantity fixture**, while their
clean-service outcomes differ. `reference-controls/quantity-qualification.json`
retains both outcomes and binds the published raw cycles, selected runtime
receipts, telemetry and actual panel reviews. This is neither final-player
qualification (that used the unchanged 4a4 first-hour player) nor model accuracy.

## Start fitting observations

`fitting-start-observations.json` retains all 22 registered capability rows,
including unknowns and pending water/holdout outcomes, with the complete risk
records. Its three positive start predictions produced:

| Fitting square | Native construction | Matched literal outside paths | Agreement |
|---|---:|---|---|
| Innsbruck | 27/27 steps accepted | 1 inbound / 2 outbound | yes |
| Pittsburgh | 27/27 steps accepted | 8 inbound / 9 outbound | yes |
| Charleston | 26/27 steps accepted | not attempted | no |

Charleston's final `join -> g30` link collided with Basic Road segment 22296,
created by the earlier `g20 -> g30` grid step. The footprint predicates passed;
the provisional hookup geometry did not predict this self-plan collision.
The rejection is retained, not reclassified as bad geography or repaired by a
native fallback. Current positive-witness fitting agreement is **2/3**, versus
archived v1's 1/3; neither is held-out or overall classification accuracy.
All three cleanup receipts are empty and all nine actual panel/opening/Areas
captures were viewed and hash-reviewed. The qualified player is unchanged.

## Water fitting observations

All three frozen positive water witnesses completed the fixed load:

| Fitting square | Scored minutes / cycles | Water / sewage quantities | Polluted deliveries |
|---|---:|---:|---:|
| Asheville | 60.0083 / 843 | 843000 / 843000 | 0 |
| Innsbruck | 60.0053 / 843 | 843000 / 843000 | 0 |
| Pittsburgh | 60.0047 / 843 | 843000 / 843000 | 0 |

All have qualified auxiliaries/timing and empty cleanup. These are conditional
service agreements at the declared native-unit load and finite horizon, not
first-hour player scores, power-generation proofs or indefinite guarantees.
Raw recovered cycles, actual image reviews, selected receipt bindings and
telemetry are under `native-v2-surface/`. Positive-witness water fitting agreement
is **3/3**, not held-out or overall accuracy.

`fitting-observations.json` freezes all 22 registered rows after the six fitting
attempts. `fitting-decision.json` records the unchanged-model decision at
2026-11-21T06:51:04.486208Z, before any registered holdout native outcome. The
retained start counterexample does not trigger a named-square repair, new model
or promise. The two positive regional water holdouts will use the same model,
source, DLL and load protocol; Grand Canyon northeast remains unknown/unscored.

Held-out capability observations, held-out first-hour baseline attempts and the
fresh eleven-square candidate player arm remain pending. The latter will use
the immutable 4a4 player, not the capability DLL. Byte-identical candidate maps
mean any repeat-run difference cannot be attributed to physical exporter rules.

## Raw evidence and integration

`report_start_water.py` projects the frozen snapshot plus retained native/run
archive into ledger-compatible rows. It pins the snapshot, export receipt,
collector and DLL, keeps every registered square and risk record, and separates
positive-witness agreement by fitting/held-out role. It preserves the audited
collector's labels rather than changing the native or first-hour judges. A
returned-boundary audit can withhold an unsupported start-path success.
`export-identities-and-warnings.json` publishes exact selected identities and
complete risk records without publishing raw source inputs.

Large cycle JSON is gzip-compressed without changing its recovered bytes.
`summary.json` binds both compressed and decompressed hashes. Other public
evidence locators resolve relative to the containing study directory. Receipt
bindings are selected map/mod/cleanup/resource fields, not launch-time identity
certificates. Full Steam, audio and launch logs are retained privately, not
published. Build-time game hashes alone cannot support promise promotion.

PL-1119 can consume the capability fragments and run-bound observations by exact
artifact/input/model hashes. Preserve `predicted`/`observed` nulls, partial steps,
all warnings and fitting versus holdout roles. Keep archived player results,
surface service and native opening paths as distinct oracles. No default or
public landing is included here.
