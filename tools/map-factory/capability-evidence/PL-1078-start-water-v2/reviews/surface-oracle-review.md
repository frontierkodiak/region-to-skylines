## Independent Sol review — changes requested before capability-fault scoring

Exact source: `7e22ef3db2c27c683fce28253eb451406a6dc828` in `PL-1078-surface-oracle`, against `d5992e76ab8a160aeb9f2681a43b13b460f36b39`. Reviewed all ten changed files. No implementation, native/controller operation, delegation, public mutation or held-out outcome inspection performed.

### P2 — auxiliary validity must include facility-side electrical health

`tools/cs1-harness/mod/SurfaceFixture.cs:229`–`:272` defines auxiliary validity from completion, `CheckElectricity` at the grid cell, a nonzero pipe node and cash. It records but does not gate on the facility's native `Electricity`/`TurnedOff` problems or enablement. The supply call occurs immediately before the grid readback. A powered grid cell is not proof that the pump/outlet was electrically operational during the demand interval—the distinction already enforced by the first-hour checker.

Consequently, a fixture-power shortfall can leave `auxiliary_valid=true`, and a short water/sewage delivery can become a scored capability failure instead of an unscored auxiliary fault. Gate known electrical/disablement/resource/setup faults explicitly, retaining actual pipe-node identity/connectivity against the declared setup. Do **not** blanket-null every inactive facility or water-specific `WaterNotFound` problem: drying or inadequate water can be the actual capability outcome.

Parent accepted this finding and the distinction; the reviewed source remained unchanged during review.

### P2 — fixture-reference admission must not reuse the product bank predictor

`tools/map-factory/prepare_surface_controls.py:58` calls the same `surface_intake.bank_candidate` used by product predictions, including its provisional slope/freeboard/search constraints. That makes independent fixture calibration unavailable when this new predictor cannot find a bank, even though native shore placement may work. It is not an independent native positive-control selection rule.

The parent's completed CPU preparation returned no supported reference witnesses and identified this restriction on the steep vanilla shores. That is a CPU/model-selection failure, **not** a native or stock-map failure. Decouple reference-anchor selection from product eligibility: freeze near-shore geometric anchors on the chosen wet component, retain the one specified native snap/no native retry contract, and keep quality/downstream prediction null. Preserve the failed v1 reference preparation. Parent has proposed this correction; it is not yet present at the reviewed commit.

### Sound boundaries in the current implementation

- **Native operations:** demand uses public `WaterManager.TryFetchWater` and sewage uses `TryDumpSewage`; returned quantities are accumulated. Facility/pipe placement uses the existing guarded `Place`/`Link` paths, without completed flags, forced money, direct water-buffer edits or groundwater fallback. Source counters are read under `LockWaterSource` and unlocked with the unchanged snapshot.
- **Auxiliary power:** native `TryDumpElectricity` is an artificial but explicitly declared experimental input. It can support a conditional pumping/hydrology experiment; it does not prove the square can generate or deliver its own gameplay electricity. That limitation must remain with ledger observations, not only in prose.
- **Exact witness:** each recorded water anchor is projected to native terrain and receives one `GetShorePos` call at 50 m. There is no alternate anchor/radius/order loop. Returned shore pose/direction, offset and actual placed pose are retained. CPU lateral search is part of the pre-recorded model, not a native retry. All limits are provisional and absence remains unknown.
- **Thread handoff:** simulation-thread actions publish a completed record through `Interlocked`; the main-thread iterator updates `Job.Result` only after publication. This avoids serializing a dictionary while the simulation action is still modifying it.
- **Time/load qualification:** settling and load are frame-indexed; the run records due/actual frames and requires the expected load-cycle count, no qualified timing/auxiliary fault and the full horizon. Python independently rejects inconsistent totals/labels and a short horizon. This remains a cyclic sampled experiment, not a continuous-flow or SI-rate proof.
- **Labels:** shore-snap failure is distinct from unattempted tool placement; setup/resource/controller/cleanup faults stay null. Surface service cannot become positive from placement or initial wet pixels alone. Every native-unit/pollution counter remains raw; no population equivalent, salinity assertion or m³/s conversion is invented.
- **Isolation:** the controller retains fair queuing, offline/carbon checks, a fresh empty city and normal session cleanup. This separate oracle DLL does not rewrite the frozen 4a4 player baseline or tune its strategy. No ledger/browser/default/public merge change is included.

### Calibration and acceptance boundary

The fixed 1000 native units per nominal 256-frame cycle, two-minute settling interval, auxiliary power and 60-minute horizon are **not calibrated yet**. After the two fixes, the next appropriate use is bounded reference-fixture calibration, not immediate hydrology-fault attribution. Reference rows remain fixture controls (`predicted=null`), not product-model agreement scores; retain dirty/failed references and separate supported quantity, plumbing/power setup and cleanliness.

Even a future positive establishes clean delivered water and accepted sewage under the recorded load, auxiliary conditions and finite horizon—not indefinite capacity, real-world freshness, a native proof of downstream geography or a whole-map gameplay promise. Keep model source/witness digests and fitting/held-out roles frozen before held-out native results; no automatic `promised` promotion.

I inspected source and tests but did not rerun the parent's reported 168 harness/16 focused tests, compile, prepare stock artifacts or execute native APIs. Compilation verifies signatures, not fixture fairness or supported capacity. The full map suite, actual reference support, physical-byte preservation for this branch and native surface behavior remain unverified here. No additional material blocker was found in the bounded load, native placement or thread-publication path.
