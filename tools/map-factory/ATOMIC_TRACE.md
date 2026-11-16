# Native source-step observations

This is a reusable, opt-in harness capability, not a map-policy change.
The lead's November16 decision permits hash-pinned observation calls in the
disposable Blade solver while preserving every original calculation, branch and
store. The earlier one-shot limit was explicitly removed. No installed original
DLL, global JIT option, terrain, control or gate is changed.

Operational API and limits: [native water tracing](../cs1-harness/TRACE.md).

## Actual observation

Native runtime/source checkpoint:
`e3fcaa12f6e1a47827c616d1c91efd9bbb975be4`.
Unchanged landed Rio package:
`4858f3eb7c80b146135e6861e474f7134990c24221dd4e1562e839f776facd40`.
Engine: `c7f0e723dfe867d10aef73f14268bcf9f5ea4bab1c5ce4987897ed27f46511a1`.

The actual5.053611-minute short retains all4,256 frozen observations and1,556
required flags. Required wet-or-near is1,556 atzero and1,545 atfive, with eleven
shared and zero new/old-only misses against the landed reference. Actual zero/five
opening and Areas PNGs, all290 controls, initial grids, collected terrain/floors,
ten camera fields and8,512 native sampler readings are bound and replayed exactly.
This is not a new60-minute qualification or a terrain repair.

Raw trace SHA256:
`1d3b151f9165f234ce07f7bd579c8ee2f49a1888857b86b03e9b5dea27f1b72b`.
It records286 complete updates, native steps0–285,370 nodes and native
sources91,92,163,164. Arithmetic checks cover74,074 target input-cell readings;
source-phase closure423,280 cells; publication105,820 cells. All match exactly.
Both the first and last published depth/floor snapshots also match the actual
zero/five grids at all370 recorded positions. Transport net change is observed
between phases, not independently reimplemented as face-flux equations.

The native thread remains inside one unpublished update when paused. Export
therefore uses memory-barrier-sealed completed records and an ordinary native
`BeginRead` endpoint checkpoint. The unfinished tail is explicit, not a missing
completed phase or a discarded map observation. No engine timing field is changed
to force an idle state. The hook remains loaded only until the disposable process
ends; its raw receipt says `unpatched:false`. Final process/Steam/unit cleanup is
empty. This must not be relabelled a live-unpatch result.

## What the solver actually did

IDs here are **native IDs**, not hydrology's zero-based source IDs.

| Source | Observed first-five-minute behaviour |
|---|---|
|92, Trapicheiros inlet (hydrology91)|Actual input in283/286 completed updates;3,920 total native depth-sum units removed. Output iszero, not proof of inactivity.|
|163, small pool regulator (hydrology162)|Input in28 updates,221 units removed; output in237 updates,530 units supplied. Its configured rate224 is not constant actual discharge.|
|164, Rio Comprido inlet (hydrology163)|Zero input/output in every one of the286 completed updates. Its actual capacity is1,134 units and availability remains negative. This is a bounded observation, not an all-time inactivity theorem.|

For source92's final update, actual pre-input water is24, dry capacity16,
availability8 and nominal request4. Cellwise rounding removes13, leaving11 in the
published grid. The committed input buffer is13. Recomputing an intake from the
post-input grid would instead see availability−5 and wrongly predict no input.
This is an actual native transaction, not the older21/11/10 inverse witness.

Source163 has a one-node source footprint at configured rate224; its target is
91.046875m. It sustains the genuine small pool. Source164's target is91.65625m
and it does not drain that pool during the traced window. Thus the remaining oval
investigation belongs at the dry bank/interpolation-support boundary, not at a
zero-output-based deletion of an allegedly inactive Trapicheiros intake.

## Fixed-state counterfactual, not a candidate

The independent replay uses each **actual pre-input** vector. Raising eligible
dry contributions already above a source target leaves that individual intake
kernel identical for identical depths. This does not prove transport, startup
surface heights or continuous native support invariant after a terrain change.

Restoring the never-rewetted held-bank family in source92's footprint removes its
16-unit dry capacity. On recorded pre-input vectors this changes total removal
in164/286 updates: **all changes increase withdrawal**, by485 units in aggregate,
at most9 in one update and none lower. Source164's
fixed-state removal remainszero; source163's footprint is unaffected. Clearing
water on those vectors is a separate mathematical counterfactual, not a proposal
to clear arriving water every step. No candidate grid or CRP was produced.

PL-1014's independent review redirects the next test to the inlet. Native92's
101.6m drain disk spans nearly the whole112m approach from native91;97.5% of its
withdrawal comes from above-target incoming-stream cells. Ten of the eleven shared
five-minute misses coincide with five terminal nodes. A smaller inlet footprint
is a testable hypothesis, not yet a qualified repair. The experimental
[inlet supply audit](INLET_SUPPLY.md) separates rate caps from footprint changes.

The recorded oval has eight still-carved pool nodes and eighteen shared-cell ring
vertices. Every ring vertex is above the regulated surface and shares a native
interpolation cell with the pool. Raising the ring invokes the already-observed
interpolation counterexample; no further oval trace is required to establish
that coupling. Genuinely wet native shore remains within the lead's accepted
visual criterion. Neither a minimum sustainable stream size nor a reservoir
benefit has been established by this observation.

## Tool validation history and limits

Four disposable launches were collected, with empty cleanup:

1. Menu-only failure: Unity's memory-loaded assembly has an empty `Location`.
2. Menu-only failure: a late package-reader import needed the factory's SciPy
   environment. Preparation now runs before acquiring the game slot.
3. Real5.091945-minute0/5 short and valid cohort, but no atomic export: the old
   idle requirement could not finish while the solver was paused. No trace from
   this attempt is claimed.
4. The completed-prefix observation above, including actual endpoint binding.

The last two owned games needed normal quit-grace termination, not spontaneous
crash recovery. Default builds compile out observer types and remove the optional
dependency; session cleanup removes the disposable installed mod. The runtime is
currently limited to the pinned engine, natural type1 sources,512 nodes,32
intersecting sources and512 update records. It is not generic facility-pump,
macOS, populated long-play or every-frame qualification.

No map-generation default or existing fixture/gate was changed. Rio flood remains
0.062464km² against0.05, numerically worse than0.061440 and the earlier0.060928;
no same-package variance explanation is proven. Charleston globalr0.6891 against
0.9 and extreme-point failures remain diagnosis-only: land reference/source
resolution disagreement is primary, bed synthesis secondary. Neither is waived.

After the native checkpoint, region planning moved from first-update initialization
to pre-arm preparation, and source positions gained lossless float reporting.
CPU checks reproduce all370 selected coordinates and the four touching source IDs
exactly, retain the inverse-IL/JIT proof and pass the synthetic read-only/prefix
fixture. No additional native game is claimed for that scheduling/reporting delta;
the proposed final source and actual native source remain separately identified.

Raw receipts, immutable trace and rerunnable audits are under the PL-912
`atomic-trace` artifact delivery. The repository includes the complete compressed
numeric trace and a minimal cleanup-receipt projection as an audit fixture, not
proprietary solver code. All original source snapshots and producer receipts are
preserved. The research index in `NATIVE_FINDINGS.md` points here.
