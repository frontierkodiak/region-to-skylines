# Start and surface-water checks

`real_roads.generate` computes `start-capabilities.json` from the final prepared
terrain, initial water and directed authored graph **before CRP serialization**.
The check is read-only and advisory. Real connections remain opt-in, no source
square is moved, no route is synthesized and no default/promise is promoted.
PL-1119 owns the single capability ledger and browser integration; this module
supplies compatible `start` and `water` fragments, not a second live inventory.

```sh
uv run --project tools/map-factory python tools/map-factory/surface_intake.py \
  /absolute/prepared-map --out /absolute/new-prediction.json
```

`surface_intake.assess_surface` adds the fixed-load surface witness to the base
`start_capabilities.assess` geometric report; it is the assessment used by the
exporter. Running `start_capabilities.py` alone leaves compound water service
unknown and reports only an initialized channel candidate.

## Definitions and scope

- **Start:** an explicit contiguous dry, low-slope footprint in the current
  starting tile, near a directed incoming/outgoing authored road pair, with a
  fixed ordered Basic Road plan. The native oracle constructs that exact plan
  and asks the native car pathfinder for both directions to outside edges.
- **Water:** a usable clean surface intake with sustained capacity at a stated
  starting demand, and safe downstream sewage disposal. An initialized wet
  route is only a candidate. The final model predicts `likely` when it also
  finds nearby provisional banks and can declare a fixed load witness; absent
  witnesses stay unknown. This is a forecast, not established service. Only
  the native experiment can support placement, quantity and cleanliness at the
  stated demand and horizon. Groundwater
  first-hour service is separate evidence, never a positive surface-water row.

The geometric limits are provisional model choices, **not recovered game
constants**: a384m square footprint sampled at16m; depth at most0.1m, slope at
most15%, relief at most8m; road clearance24m; center lattice64m; hookup lengths
40–512m with8m water samples. The road grid is the declared288m4x4 test fixture,
not a universal requirement for every playable city. Curvature, obstacles,
between-sample terrain and the native placement tool can falsify a likely plan.

### Version2: fitting counterexamples

Version1's three positive fitting predictions produced one accepted native
start (Pittsburgh) and two native collision rejections (Innsbruck/Charleston).
These are retained false positives, not failed geography or player regressions.
Version2 uses the exported endpoint tangents instead of straight endpoint
chords for the junction heading. It screens candidate links against unrelated
authored network corridors and orders the paired stubs by sampled clearance
from the other ramp. All decisions are frozen on CPU, never selected by a
native retry or a square name. It can therefore select another authored pair
or abstain, without changing a map, start tile or the qualified player.

Corridors use nominal4m chord-based samples on a cubic with one-third-chord control
length. That curve length and the24m clearance are **provisional geometric
approximations**, not recovered engine collision constants or prefab widths.
The two deliberately joined stub segments are excluded from the unrelated
corridor screen; their junction legality is still a native question. No angular
proxy veto, grading, collision bypass or default promotion is introduced.

The finite search returns unknown if it finds no plan. Missing graphs are
unknown. A through-road without dangling ramp stubs is unknown, not a negative.
`not_possible_here` is used only when the current authored road graph lacks a
required incoming or outgoing outside anchor—never geographical impossibility
or a claim about every possible generator. No check emits `promised`.

Water candidates require an initialized wet route in prepared upstream-to-
downstream order, at least1m deep and320m apart, with an initial surface drop.
This is not a simulated velocity, clean-water, salinity, capacity or sewage
transport certificate. Nominal source capacities and native velocity counters
are not converted to m³/s. Native quality samples retain raw units.

## Native witness oracle

Run `uv run python -m cs1_harness.capability --help` in `tools/cs1-harness`.
Supply an immutable prediction with an added exact CRP `artifact_sha256`, its
model digest, the compiled oracle DLL digest, map/probe files and a new output
directory. This is a **distinct DLL/oracle series**, not the qualified4a4 player.

The controller uses the existing fair queue, fresh offline/carbon guards and
normal session cleanup. It validates model, map, witness and DLL identities,
then uses a fresh paused empty city. It resolves each declared hookup to exactly
one matching native road end within2m, executes the ordered plan with the
existing guarded native NetTool calls, and retains every partial step, error,
node and actual pose. Native terrain snapping is recorded, not replaced with
another site. There is no site search, alternate order, bridge retry, grading,
forced funds, direct-buffer road creation or groundwater substitution.

Successful construction settles for256 simulation frames, then uses the
existing native inbound/outbound car path observer. Placement and path results
are separate. Native readbacks of the model's footprint predicates are also
separate: a predicate mismatch leaves unattempted tool placement unscored.
Setup, binding, controller, resource, timeout and cleanup faults are
unscored. A native rejection is a negative for the specified witness, not for
all sites on Earth. Point water samples alone do not score sustained service.

The separate `--mode surface` oracle uses one shore snap at each frozen anchor,
normal facility/pipe construction, conditional native auxiliary power, and
spatial consumer water/sewage APIs. It applies 1000 native units per 256 frames
through two minutes of loaded settling and sixty scored minutes. Full raw
cycles, facility-side auxiliary state and timing must qualify before a service
label is scored. Quantity shortfalls and polluted deliveries remain failures;
an auxiliary/setup fault is unscored, not hydrology incapability. Both stock
references support this fixed quantity fixture; Cliffside Bay's 733 polluted
deliveries remain a clean-service failure. No population, SI-rate, power
generation or indefinite-capacity equivalence is claimed.

The original eight are fitting data. Freeze the model code/parameters and all
prediction/witness digests **before native results from the three registered
holdouts**. Evidence rows need separate exporter `source_sha`, oracle source/
DLL/game-assembly identities, exact map/input hashes, split and raw evidence
hashes. Nulls remain unscored; do not combine fitting and held-out accuracy or
different oracle types. The archived player-only baseline remains unchanged.
