# Correction record: v2 after the review of PR81 head `97e0038`

The reviewed head `97e00389f4ad0eb30aa1ff1d775876c87f4ab27c` froze its
`protocol.json`, `predictions.json`, `evaluation.json`, `bridge.json`,
`catalogs.json` and `integrity.json` at this prefix's root. Those six files are
preserved byte-for-byte and their SHA-256 values are pinned in `predict.py`
(`REVIEWED_ARTIFACTS`) and asserted by the test suite. The corrected model,
predictions, evaluation and bridge are the **separately identified**
`rail-query-model-v2-corrected` freeze in this directory.

The corrected model reproduces the reviewed fitted confusion exactly
(TP 26 / FP 4 / TN 245 / FN 1) and keeps the same five Pittsburgh
counterexamples. The defects were in the executable contract, not in the native
labels; the correction changes one other rule's numbers, listed below.

## What the review required and what changed

1. **Train/direction domain.** `train_index` now keeps only segments with a
   Train-capable lane, and `lane_at`, `continues` and the request lookup see
   only Train lanes. Lane continuation is counted by ordinal among a segment's
   Train lanes, so raw lane indexes are never renumbered. `can_travel` applies
   segment `Invert` centrally, following the accepted native planner
   (`forward = (offset == 0) == source; if Invert: forward = not forward`).
2. **Allocation-ID tie-breaking.** `node_partnerings` no longer sorts by segment
   id. Equal-turn candidates (within `1e-6` degrees) are all represented as
   junction resolutions; a query is `success` or `no_path` only when every
   resolution agrees, otherwise it abstains. The enumeration is bounded by
   `MAX_ALTERNATIVES`; exceeding it abstains.
3. **Reversal and length hypotheses.** A reversal is a `(segment, segment)`
   self-pair at the node, so `deadend`/`allowed` can actually reverse and
   `forbidden` cannot. The length search is a relaxed shortest-first search on
   the chord lower bound: the opening traversal and every later traversal are
   checked against the maximum, and a longer first arrival at a state no longer
   blocks a shorter one. The lower bound is still reported as a lower bound, not
   as native path cost.
4. **Evaluation binding.** `evaluate.bind` requires the frozen plan request at
   `plan_index`, the observed row request, the package locator and SHA-256, the
   network-snapshot and query-freeze hashes, the protocol hash and the model
   source hashes. A mismatch raises `BindingError`; it is never scored. A
   present row with a missing or non-boolean `complete`, `released` or `success`
   also raises; a missing row (incomplete opening) stays Unknown. `--check`
   validates the bindings as well as reproducing the numbers.
5. **Reporting.** Cross-component failures are scoped to this retrospective
   selected-query set and are not called a general native impossibility proof.
   Zero-query packages are listed and unscored, not called exact. Pittsburgh's
   112 unqueried candidates stay separate.

The bridge now compares a canonical digest of exactly the records and fields the
model consumes (`bridge.model_input_digest`: Train-capable segments, endpoints,
prefab, Invert, Train lane index/direction/type/vehicle/category, and each
incident node's Outside predicate and position), instead of relying on a
Train-only field sample while the model consumed everything.

## Evidence: the contract fails on `97e0038` and passes on v2

The six `DomainContractTest` cases were copied onto an isolated checkout of
`97e0038` and run there, then run against this corrected tree:

| Case | `97e0038` | corrected |
| --- | --- | --- |
| Car-only middle segment | success (wrong) | no_path |
| `Invert` chain along the old direction | reachable (wrong) | no_path, and the inverted direction succeeds |
| Equal-angle junction, ids 11/12 renumbered | success, then no_path | abstain under both namings |
| Dead-end out-and-back, `deadend`/`allowed` | no_path (hypothesis unreachable) | success; `forbidden` still no_path |
| 100,001-unit single segment | success (wrong) | no_path |
| Length relaxation to a shorter alternative | 149,010 lower bound reported as success | success at 51,010 |

Logs: `evidence/domain-contract-at-97e.log` (5 failures, 1 error of 6) and
`evidence/domain-and-binding-contract-at-corrected.log` (12/12 pass). The
binding probe shows the difference directly:

```
97e:       {"evaluator": "scored the mutated request", "identical_rules": true}
corrected: {"evaluator": "BindingError", "message": "stock-1:0: frozen prediction request is not the plan request"}
```

Logs: `evidence/binding-probe-at-97e.log` and
`evidence/binding-probe-at-corrected.log`.

## Corrected arithmetic, all 276 selected queries

| Rule | TP | FP | TN | FN | Abstain | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| always-fail | 0 | 0 | 249 | 27 | 0 | null | 0.000 |
| always-candidate | 27 | 249 | 0 | 0 | 0 | 0.098 | 1.000 |
| weak_component | 27 | 198 | 51 | 0 | 0 | 0.120 | 1.000 |
| lane:any_lane:forbidden (= the component rule) | 27 | 198 | 51 | 0 | 0 | 0.120 | 1.000 |
| lane:orientation_index:forbidden (primary) | 11 | 198 | 51 | 16 | 0 | 0.053 | 0.407 |
| lane:index_same:forbidden | 5 | 48 | 201 | 22 | 0 | 0.094 | 0.185 |
| lane:index_mirror:forbidden | 0 | 0 | 249 | 27 | 0 | null | 0.000 |
| junction:single:any_lane | 24 | 4 | 245 | 3 | 0 | 0.857 | 0.889 |
| **junction:continuation:any_lane (fitted)** | **26** | **4** | **245** | **1** | **0** | **0.867** | **0.963** |
| junction:continuation:orientation_index | 10 | 4 | 245 | 17 | 0 | 0.714 | 0.370 |

Changes from the reviewed head: the primary rule moves from 13/14 to 11/16 and
`junction:*:orientation_index` moves by the same two successes, because `Invert`
now swaps the required travel bit. No other rule's counts change. Abstention is
0 on this set for every rule: no real package produces more than one junction
resolution under any mode, so the new tie representation never had to abstain
here. The mechanism is exercised by the constructed test instead.

Stock controls 16 / 0 / 16 / 0; cohort 10 / 4 / 229 / 1. The fitted rule is
exact on the two stock controls, Asheville, Innsbruck, Boston, Hong Kong and
Rio; Charleston, Grand Canyon and Yosemite have zero selected queries and are
unscored. All five fitted errors are in Pittsburgh, unchanged from the reviewed
head.

## Bridge

`bridge.json` reports `bridge_established` for the nine unchanged cohort
packages: every model-used field agrees 100 % on 6,774 Train segments, the
canonical model-input digests are identical for all nine, and all 244 cohort
requests predict identically from export bytes and from the native snapshot.
The two stock controls remain native-snapshot only (CRP package format 8).
