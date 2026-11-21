## Independent Sol fix verification — accepted

Exact source: `1f2d4f4d7bbff5daf16e9bd8a645ec4ed3864589` in `PL-1078-surface-oracle`. Bounded recheck of the two P2s from `7e22ef3`; no broader review, implementation, native/controller operation, held-out inspection, delegation or public mutation.

**Both findings are resolved.**

- **Auxiliary qualification:** the native fixture now checks facility-side electrical/disablement conditions, production enablement, normal completion, expected native pipe-node identity/connectivity, consumer pipe state and cash. A loaded auxiliary failure stops with service unscored and retains the failed cycle. Python checks every raw cycle and recomputes delivered/sewage/pollution totals instead of trusting only aggregate labels. The new tests distinguish an electrical warning hidden behind a powered grid from a genuine water-specific failure. `Active=false`/`WaterNotFound` are not blanket auxiliary exclusions.
- **Independent references:** stock-reference admission no longer imports or calls the product bank predictor. It freezes near-shore geometric anchors independently of product slope/freeboard eligibility, with declared separation and deterministic selection. Shared water is preferred but not required for plumbing calibration; quality and downstream relationship remain explicitly unpredicted. The steep-bank regression test covers the original coupling.

Verified the on-disk oracle DLL SHA256 is `c7ce8415192087acaaff28a6342f0db4d06a492cdb84159b7aedc15c4f033dae`. Inspected the changed code, documentation and tests; did not rerun the parent's reported 170 harness/8 focused tests or compile.

**No residual blocker from this fix set. Accepted for bounded native reference-fixture calibration.** Demand/units, supported capacity, actual shore placement and native surface service remain uncalibrated/unverified. This acceptance does not authorize hydrology-fault attribution, held-out success claims, promise promotion or a public merge. Keep auxiliary power and finite load/horizon caveats with any later observation.
