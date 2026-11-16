# Experimental inlet footprint bound

`inlet_supply.py` is an opt-in falsification helper, not a shipping rule. Ordinary
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
  --out /own/run/audit.json --build /own/run/new-inputs
```

Preparation verifies native cleanup/map identity, every planned input hash,
encoded source geometry/targets/rates, and patches no field except input rates.
The original package and receipts remain preserved. `generation.json` labels the
new artifacts `experimental_unqualified`; no old native receipt is relabelled.

Any justified native run must use the cs1-harness FIFO/silent private:57 lifecycle,
all4256 Rio observations/1556 required flags and actual zero/five opening+Areas
captures. Stop on a new passing-gate failure. No full sweep follows without the
required visible short result, complete Asheville short and proper shipping
Python/JS/Pyodide/versioned contract integration. Rio flood and Charleston's
correlation/extremes remain failed and unwaived.
