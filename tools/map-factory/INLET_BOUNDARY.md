# Native boundary readback: capacity is not drainage

This is actual unchanged-package evidence, **not a new map policy or a qualified
relocation**. PR50's point-rate experiment remains rejected. No map/default,
head, source position/rate, terrain, startup water, observation or gate changed.

## Identity and capture

- Native source: `5a1e045d82eb5d3c54252c7a3c15246bf3acac50`, including PL-982's
  already-landed tools. No generation/road writer ran. Nineteen generation
  runtime files and all 351 previous factory fixtures are exact to `e03442df`.
- Exact landed Rio CRP:
  `4858f3eb7c80b146135e6861e474f7134990c24221dd4e1562e839f776facd40`.
- Engine `c7f0e723dfe867d10aef73f14268bcf9f5ea4bab1c5ce4987897ed27f46511a1`;
  Mono/Harmony pins match [the observer contract](../cs1-harness/TRACE.md).
- CPU planning request:
  `6465409f04a88ade8301277238d837b4def7ea0c7493862e15808e423d7a0ecf`.
  The run adds driver/runtime/input bindings, not different nodes or controls.
- Actual trace:
  `2aa80856116f5c546f8ad5692c4a3a54496914be4aee9d0d5d6d39ad5d2a8352`.

One disposable private `:57` session, **5.085000 game minutes**, records 287
completed updates at 364 nodes. Targets are natural inputs 92 and 280; all
touching sources are 89, 91, 92, 279 and 280. The pre-arm source catalog and
node set match. These IDs select a diagnostic, not production admission.

The original 3,432 instructions plus 27 inserted observer instructions retain
the exact strip-inverse digest. Source arithmetic replay matches **47,642 input
cells**, **522,340 source-phase cells** and **104,468 publication cells**, with
zero errors. The sealed prefix reaches the actual paused native endpoint and
zero/five grids. One unfinished unpublished tail remains explicit; the hook is
not live-unpatched. Disposable teardown removes it and has empty cleanup.

All 4,256 frozen observations / 1,556 required flags remain: required zero
1,556/1,556 and five 1,545/1,556, eleven shared misses, zero new/old-only misses.
All 290 controls, initial grids, collected raw terrain at zero/five, actual
hydraulic floors/targets and ten camera fields match. All 8,512 native sampler
readings replay exactly. Actual zero/five opening and Areas PNGs were inspected;
they show the unchanged partial baseline, **not a visible repair**. No other
map, changed package or sixty-minute run was launched.

The descriptive five-minute original-mask flood snapshot has 175 cells,
0.044800 km². It does not replace the failed 0.062464 km² full-run result or
constitute a controlled same-package flood-variance experiment.

## What the new atomic data resolves

### Papa-Couve is a source–sink balance, not spare drainage

Within the captured Papa-Couve region, every completed working update is
published, and the exact native depth-sum budget is:

```text
initial 786 + source279 output 106,902
            - inlet280 removal 105,790
            - net transport out 1,152 = final 746
```

Values are integer native depth-sum units, not a calibrated cubic-metres/second
discharge. Output is actual measured output, not the configured cap 3,022.
Source 279's full nine-node output and one-node input are captured. Input 280's
full 37-node input is captured; its peak nominal request is 368 and peak actual
cell-rounded removal 373. Neither inlet's old rate binds in this observation.
About 69.18% of inlet 280's removal occurs inside source 279's output footprint;
83.53% occurs on nodes at or above the inlet target.

A grid-aligned rate-224 input has one node. Its actual removal per update cannot
exceed 224, so 287 such updates can remove at most 64,288 units. That is less
than the old 105,790-unit removal. This bound explains the scale of the lost
drainage role; it **does not predict the rejected arm's changed supply, transport
or flood trajectory** and does not prove which changed inlet caused its flood.

### Capacity-preserving placement still discards that role

The preceding CPU audit found 70 Trapicheiros / 13 Papa-Couve sampled tunnel
positions that preserve the original capacity vectors and cover no newly
positive-depth node in six saved epochs. All 83 preserve their capacity at
every one of these 287 actual pre-input states: **16 units for 92, 321 for 280**.
No raw-floor approximation or compensating deeper floor is used.

Independently replaying each moved disk on each **old** pre-input array gives:

| Input | Actual original removal | Fixed-prestate moved-disk range |
|---|---:|---:|
| 92, Trapicheiros | 3,932 | 202–609 |
| 280, Papa-Couve | 105,790 | 47,542–75,970 |

These are separate frozen-state calculations, not changed-run trajectories.
For Papa-Couve, they discard 29,820–58,248 units of actual removal (28–55%)
without any observed new-only water. Retained-node removals are unchanged in
that replay. There is no evidence that unchanged terrain would route all this
released water to the new receiving cells. There is also no proof that it
cannot: a forward transport response is deliberately not synthesized here.

At Trapicheiros, one of the 70 positions exposes the saved-grid blind spot:
new-only node `(-2352,2112)` has up to eight units of pre-input water in two
updates. Its local transport contributes a net 15 units and earlier inlet 89
removes 15; the relocated-92 replay would additionally remove seven. A node
empty at every saved epoch is not necessarily empty at source time. Twenty
geometric positions overlap inlet 89, but this is a bounded observation, not
proof about unobserved future water in the others.

Inlet 89 is only partially captured (11/37 input nodes): its local removal is
8,563 versus global committed input counters summing to 38,680. Do not call
those partial cells a full replay of its kernel. The full captured Trapicheiros
region closes as `967 + 9,119 + 2,517 - 12,495 = 108` (initial + source output +
net transport - local inputs = final). Both regional budgets close exactly.

The terminal Trapicheiros profile also contains a low point followed by an
uphill dry tail: at z=2,112, native floors at x=-2,160/-2,176/-2,192 are
93.421875/94.15625/96.03125 m, while the existing input target is 93.671875 m.
Moving a disk does not by itself repair this receiving profile.

## Disposition and next falsifiable question

**Do not promote capacity equality into a safe-placement criterion or launch a
shifted-inlet arm from these numbers alone.** The actual conflict is now clear:
the existing supplied open-channel profile relies on removal on its approach;
the tested underground receiving disks do not carry equivalent water in the
recorded states. Preserving dry capacity alone does not preserve that drainage.
This rejects the shortcut, not all possible boundary designs.

The next bounded CPU/source hypothesis is **joint topology/profile admission**:
explicit surface/tunnel boundaries must define the modeled reaches before
raster component routing and before excavation/forcing are assigned. A tunnel
shorter than one native grid cell must not be silently bridged into a fabricated
source-to-receiver profile by rasterized visible endpoints. This remains a
hypothesis: first replay the original five geometries/routes and show whether
such a bridge actually explains the native-supported and dry subsets. Preserve
supported local-stage channels, continuous interpolation/startup supply and
all original observations. If that premise is false, discard it; do not force
an omission or another rate sweep.

A real implementation still needs source-bound five-map CPU falsification,
actual complete Rio/Asheville zero/five opening and Areas proof, justified
changed-package qualification, shipping Python/JS/Pyodide/contract integration,
then lead and steward review. No new supply, arbitrary heads, deeper floors,
probe/mask/threshold exemptions or issue acceptance follows here.

## Reproduction and limits

Run artifacts: `PL-912-boundary-readback` under the host experiment root.
`analyze_boundaries.py` calls the existing actual-trace audit, computes region
state budgets, and writes all 83 fixed-state results plus per-update records.
`verify_results.py` independently checks 47,642 actual cell removals with scalar
integer arithmetic, all 83 full-grid disk masks and 23,821 moved-disk/update
calculations, then independently closes both published storage budgets. No
tested product integer overflows occur in those calculations. Scripts must be
copied to an independent output root before replay; never overwrite receipts.

The ordinary build is restored: observer/Harmony symbols, reference, build
dependency and ephemeral installed mod are absent; the engine hash is unchanged.
No full-map late hydraulic-floor dump, every-frame map acceptance, minimum
stream size, reservoir benefit or same-package flood-variance experiment is
claimed. Existing Rio full flood **0.062464 km² vs 0.05**, Charleston **r 0.6891
vs 0.9/extremes**, dry banks/thinning and the native-pool shore call remain open.
PL-912 stays in progress, not accepted.
