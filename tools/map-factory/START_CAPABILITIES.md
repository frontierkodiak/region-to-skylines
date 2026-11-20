# Start and surface-water checks

`real_roads.generate` computes `start-capabilities.json` from the final prepared
terrain, initial water and directed authored graph **before CRP serialization**.
The check is read-only and advisory. Real connections remain opt-in, no source
square is moved, no route is synthesized and no default/promise is promoted.
PL-1119 owns the single capability ledger and browser integration; this module
supplies compatible `start` and `water` fragments, not a second live inventory.

```sh
uv run --project tools/map-factory python tools/map-factory/start_capabilities.py \
  /absolute/prepared-map --out /absolute/new-prediction.json
```

## Definitions and scope

- **Start:** an explicit contiguous dry, low-slope footprint in the current
  starting tile, near a directed incoming/outgoing authored road pair, with a
  fixed ordered Basic Road plan. The native oracle constructs that exact plan
  and asks the native car pathfinder for both directions to outside edges.
- **Water:** a usable clean surface intake with sustained capacity at a stated
  starting demand, and safe downstream sewage disposal. An initialized wet
  route is only a candidate. The compound prediction stays unknown until
  placement, flow, quality, demand and horizon are supported. Groundwater
  first-hour service is separate evidence, never a positive surface-water row.

The geometric limits are provisional model choices, **not recovered game
constants**: a384m square footprint sampled at16m; depth at most0.1m, slope at
most15%, relief at most8m; road clearance24m; center lattice64m; hookup lengths
40–512m with8m water samples. The road grid is the declared288m4x4 test fixture,
not a universal requirement for every playable city. Curvature, obstacles,
between-sample terrain and the native placement tool can falsify a likely plan.

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
all sites on Earth. Water samples do not score sustained service.

The original eight are fitting data. Freeze the model code/parameters and all
prediction/witness digests **before native results from the three registered
holdouts**. Evidence rows need separate exporter `source_sha`, oracle source/
DLL/game-assembly identities, exact map/input hashes, split and raw evidence
hashes. Nulls remain unscored; do not combine fitting and held-out accuracy or
different oracle types. The archived player-only baseline remains unchanged.
