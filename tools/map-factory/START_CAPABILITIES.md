# Start capability runtime (PL-1210)

`capabilities.py PREPARED --out report.json` now executes the Start check. The
existing `prepared_input` adapter adds `start_input`: full 1081×1081 terrain and
water-depth arrays in metres, south-first, at 16 m spacing, with the current
`hydrology.json` start tile. The authored graph remains the existing `graph`
field. Place input and physical writers are unchanged.

`start_model.py:evaluate_start` and browser `start-model.js:evaluateStart` read
that same normalized input. Both are deterministic and read no labels, place
names or archived outcomes. An unsupported/missing grid, graph or tile abstains.
Only missing incoming/outgoing directions in the **current authored graph**
produces a plan-scoped negative. An exhausted finite search stays Unknown.

## Relationship to PL-1078

The active model is `pl1210-start-port-v1`, a Start-only port of
`9a4aad77101fbdb0190c7ceaa11ec643065bec56`, not a new water model. The footprint
predicates, parameters, two-stub search, cubic corridors, clearance ordering and
27-step construction plan are preserved. Geometry helper ASTs are checked
against the archived source without executing the archived predictor. Missing
start tiles now abstain instead of raising. A Python-only witness hash has moved
out of the pure result into the prepared report's binding.

Prepared reports bind the ledger, active Python/JS/adapter and road/CRP helper
sources, all three complete physical inputs (hydrology binds graph and tile),
the witness when present, and the exact CRP when the prepared folder contains
one. The binding does **not** transfer native agreement. Every active result is
unscored. No place-name matching or historical model-agreement reuse exists.
The archived source, predictions, observations, splits and failures stay frozen.

The original 2/3 Start fitting result is positive-witness agreement, not overall
accuracy. No positive regional-holdout Start prediction means **not estimable**.
The model can miss native collisions (Charleston); paths are post-construction
sampled passenger paths, not spawning, freight or continuous service.

## Live footprint approximation

`captureEstimate` reuses its one capture and initial depth pass. `liveFootprint`
uses the full 16 m capture grid: depth ≤0.1 m, gradient magnitude ≤0.15, relief
≤8 m, across a 384×384 m footprint. Centers are tested every 64 m in the central
1,920 m square, with the original 32 m tile margin. It is not the buildable
sample fraction. A partial/nonfinite/coarse grid or no sampled witness stays
Unknown, never a geographic No.

Capture rows run north-first; result coordinates use north-positive game z.
The capture has no authored graph or selected future start tile. This version
omits authored-network obstruction and all hookup work. Its candidate is only
terrain/depth opportunity, not a legal/connected start. Banks-minus-bed and the
coastal sea-level estimate are not finished/simulated water.

The existing eight-icon row is unchanged. The Land explanation and a linked
footprint readout show the candidate separately, with **Hookup: Unknown**.
Reset/error/cancellation clear the old readout. Stock comparisons for this
predicate/fidelity are **Not comparable**; the game's buildableArea is not a
substitute.

## Verification

- `npm test`
- `uv run --project tools/map-factory python -m unittest discover -s tools/map-factory -p test_start_model.py -v`
- `uv run --project tools/map-factory python -m unittest discover -s tools/map-factory -p test_capabilities.py -v`
- `uvx ruff check tools/map-factory/{start_model,test_start_model,capabilities}.py`
- `node build.mjs`

Real retained grids and constructed geometry are separate in the tests. Browser
proof runs Chromium and WebKit on blade's official Playwright 1.65 image, never
carbon's screen. No game/native collection, raw study regeneration, physical
package rebuild, stable-water work, certificate additions, public landing or
Shelf publication is part of this change.
