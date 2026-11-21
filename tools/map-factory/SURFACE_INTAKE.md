# Fixed-load surface intake oracle

This extends the read-only start check with a provisional surface-water plan.
It does not alter terrain, water, source controls, package bytes, player
strategy or defaults. PL-1119 still owns the ledger/browser integration.

## Prediction

`surface_intake.assess_surface` requires a deep initialized directed channel
route, separated intake/outlet positions and nearby bank candidates. A lateral
wet path, sampled every8m within192m of the channel, moves each fixed water
anchor near its bank. The bank must be within50m of that anchor. The witness
declares **one native shore snap** at each recorded anchor, followed by native
checked placement. It never asks the oracle to try another point or radius.
Actual snapped poses and the prefab offset are recorded.

These limits are provisional model/search choices, not recovered game
constants. Missing candidates are unknown, not geographic negatives. The
writer initializes native water pollution to zero; that says nothing about
real-world salinity or later sewage transport. Initial surface drop and wet
storage cannot establish sustained capacity. Predictions are hypotheses to
score, not playable-map promises. No result promotes `promised`.

## Controlled native experiment

`uv run python -m cs1_harness.capability --mode surface ...` uses a separate
oracle DLL and fresh empty city. It places vanilla Water Intake and Water Outlet
through native checks, then builds the single declared pipe tree to a consumer
point. There is no direct building-completion flag, groundwater fallback,
water-source replacement, rerouting, city-growth policy or forced money.

Auxiliary electricity is explicitly held available through the native supply
API. This isolates pumping/hydrology; it is **not evidence that the map/player
can generate electricity**. Normal facility completion, native grid power,
budget, pipe setup and timing are recorded separately. Auxiliary/setup/resource
faults leave service unscored.

Every loaded cycle checks each facility's own electrical/enablement problems,
normal completion and exact declared pipe-node connectivity, plus the consumer
pipe and available cash. A loaded auxiliary failure stops the reference with
service null. `Active=false` and `WaterNotFound` alone do not invalidate the
fixture: insufficient water can be the observed hydraulic result. The Python
controller independently validates every raw cycle as well as its totals.

After2game-minutes of settling, the native consumer requests1000water units and
dumps1000sewage units every256simulationframes for60game-minutes. These are
native API units, **not m³/s or an asserted population equivalent**. Every cycle
records delivered quantity/pollution, accepted sewage, facility state and
source counters. A complete positive requires every requested quantity, no
polluted delivery, all scheduled cycles, valid auxiliary conditions and the
full horizon. Incomplete clocks/loops or cleanup cannot pass. The controller
independently checks the native job's claimed labels against its totals.

Placement, native shore snapping and full service remain distinct oracles.
A failed shore snap is not an attempted native tool placement. A failed fixed
witness is not proof that no other intake works on the square. A successful
hour is not an indefinite-capacity or whole-map guarantee.

## Reference controls and held-out scoring

`prepare_surface_controls.py` decodes the two already registered stock maps,
without changing their packages, and freezes two geometrically selected shore
anchors at least320m apart. A shared body is preferred, not required to test
the pipe fixture. These are fixture references, **not model predictions**;
quality/downstream relationship is unpredicted. Before attributing a service
shortfall to map hydrology, verify that this demand/plumbing/power fixture is
supported on the reference controls. Retain failed/dirty controls too. The
separate unchanged4a4first-hour player controls remain authoritative for its
benchmark; do not mix DLLs or reference-oracle outcomes into that rate.

The native load and any population interpretation are not calibrated yet.
Original8 are fitting data. Freeze model/parameter/witness digests before
native results on the registered3holdouts. Keep unknowns, model false positives,
native setup faults and held-out versus fitting scores separate. Exporter and
oracle source revisions are distinct. No public merge or default promotion.
