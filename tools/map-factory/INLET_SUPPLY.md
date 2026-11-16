# Experimental inlet footprint bound

**The first native arm is rejected.** `inlet_supply.py` is a reproduction helper,
not a shipping rule. Ordinary
generation, every old fixture and all observation flags/masks/thresholds remain
unchanged. PR49's recorder landed at `e03442d`; its Opus/steward reviews approved
instrumentation only.

## Hypothesis

The existing footprint limiter protects local-stage channels from broad regulator
intakes, but deliberately exempts surface-to-tunnel inlets. The actual Trapicheiros
trace shows that exemption draining most of the approach reach. The experimental
rule applies the existing upper-channel footprint bound to **input-only,
bank-limited surface/tunnel boundaries**, also capping input by the sum of encoded
output capacities in the same upstream-to-downstream control chain.

The chain comes from existing control roles and ordering. Names/classes validate
chain coherence, never select a region or a desired result. Other control classes
remain unchanged. A proposal of zero rate blocks preparation; no inlet is removed.
The nearest upper-channel test retains the existing writer's0.125m margin and
uses the package-bound, actual native startup floor. No qualification probe enters
planning. This is an evidence-bound experiment, not a universal inflow estimate:
configured outputs are caps, not measured discharge, and imported startup storage
or transport can exceed them.

## What the current CPU replay establishes

All five exact landed packages are examined. The rule proposes70 input-rate
changes in Rio and one in Pittsburgh; Asheville, Innsbruck and Charleston have no
eligible changes. All heads, source positions/types/output rates, terrain/startup
water, networks, start, resources and every other simulation byte remain exact.
Three unchanged packages remain byte-identical. Two changed packages differ only
in encoded UInt24 input fields and the required metadata asset reference/checksums.

For Trapicheiros92, the control-chain output cap is1218; the profile bound is224.
Rate224 has a strict15.9867m radius and one grid node at this alignment. On the
actual old pre-input arrays it requests at most29 units, never hitting224. The old
373-unit peak belongs to a different129-node disk and cannot be treated as the
one-node demand. Using the supply cap alone gives nine nodes and a107-unit peak.

For oval inlet164, reducing to224 produces four positive early withdrawals,
52units total, where the original129-node kernel withdraws zero. The smaller
footprint removes negative dry-capacity terms as well as stream nodes. No future
pool-support invariance, flood safety or unchanged trajectory follows from these
fixed-preimage comparisons. A fresh complete native short must falsify those
claims; current map gates are not changed to make that short pass.

## Reproduce

Run with the factory uv environment. Supply a new output directory; existing
case outputs are never overwritten:

```bash
uv run --project tools/map-factory python tools/map-factory/inlet_supply.py \
  --repo "$PWD" --inputs /path/to/landed/shipping \
  --native /path/to/matching/full-native \
  --trace /path/to/rio/trace.jsonl --trace-case rio \
  --out /own/run/audit.json --build /own/run/new-inputs \
  --replay-rejected
```

Preparation verifies native cleanup/map identity, every planned input hash,
encoded source geometry/targets/rates, and patches no field except input rates.
The original package and receipts remain preserved. `generation.json` labels the
new artifacts `experimental_unqualified`; no old native receipt is relabelled.

## Actual rejected short

Source `e49de7d1d956609168392c5ba7f150ad4f16f48e`, Rio package
`947d31231e189235ae097fd0a437e86f210a221670a3521741bc31460c5fc1c6`,
actual5.054722 game minutes. All4256 observations/1556 flags remain. Required
wet-or-near is1556 atzero and1555 atfive, versus1545 before, with ten recovered
misses and no new misses. Those ten observations represent five unique nodes:
only two are natively wet; one has7/64m film and two have no water. This is not
complete wet continuity or a visible-success checkpoint.

Under the original flood mask, the prior full-run five-minute grid has179 flood
cells (0.045824km²); this short has474 (0.121344km²), against0.05. There are123
shared,351 new-only and56 old-only cells. The largest new connected cluster has
188 cells near Papa-Couve. Nearest-inlet association is not proof of causation;
its nearest changed inlet280 reports158 units against224 at the final sparse
read, not a demonstrated cap hit. Several other inputs do hit their caps in
the sparse samples. No atomic candidate source phases were recorded.

Two of40 frozen Rio pool calibrations are below bounds: component13 averages
31.560656 units against36.142623; component54 averages51.208333 against51.273810.
The supplied oval centre remains0.953125m deep. All initial grids, collected
terrain/floors,290 controls (apart from70 intended intake-rate edits), cameras
and8512 native sampler readings match their bindings. Cleanup is empty; normal
quit-grace termination is not a spontaneous crash.

No Asheville, other-map native or full run followed. No production writer,
shipping JS/Pyodide, active contract, observation, mask or threshold changed.
The new fixture records rejection; it is not an acceptance contract. Later
source changes only quarantine this helper and document evidence. The actual
native source remains `e49de7d`, not the later documentation head.

This short does not validate control-chain output caps as an estimate of arriving
water: the tested rule combines that cap with a tighter profile bound. A
supply-only cap has not run natively. Shrinking a rate also removes distributed
drainage coverage. A next design
must preserve that coverage/capacity while preventing withdrawal along a
supported approach; simply selecting the successful inlet or increasing a
global rate is not established. No second arm is prepared or queued.

Any justified native run must use the cs1-harness FIFO/silent private:57 lifecycle,
all4256 Rio observations/1556 required flags and actual zero/five opening+Areas
captures. Stop on a new passing-gate failure. No full sweep follows without the
required visible short result, complete Asheville short and proper shipping
Python/JS/Pyodide/versioned contract integration. Rio flood and Charleston's
correlation/extremes remain failed and unwaived.
