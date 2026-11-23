# Query-scoped road, ship and air reachability model v1

A retrospective study of one narrow question on the accepted outside-v1 native
study (PL-1121 and its PL-1142 targeted repeat): given one literal-boundary
outside-connection request, does `PathManager.CreatePath` return a complete path
whose first and last positions equal the requested offsets?

The model sees only what a saved map contains before any query: segment and node
identity, endpoint positions, prefab, segment flags (including `Invert`, which
swaps which end counts as forward), and each lane's index, type, vehicle,
category and recorded direction. It never sees an outcome, a returned path, a
panel count or a request's own `endpoint_roles` metadata.

Rail already has separately reviewed research ([`../rail-query-model-v1`](../rail-query-model-v1)
and [`../rail-junction-fit-v1`](../rail-junction-fit-v1)); it is out of scope here
and is not re-fitted.

The measurements are the point. The report is [`RESULTS.md`](RESULTS.md), the
reproduction is [`REPRODUCE.md`](REPRODUCE.md).

## What was measured

876 retained road, ship and air native path rows across 17 openings of the nine
unchanged packages: the PL-1121 first attempts and the PL-1142 targeted second
attempts. 378 of them are literal boundary requests (342 on distinct map edges,
36 on one edge); 378 are offset-128 midpoint diagnostics; 64 are the earliest
collector version without a `position_kind` field; 28 are archived first-hour
player-run probes with no literal request; and 28 are placeholder rows where no
request was made.

Only the 378 literal boundary requests are scored. 102 of them are observed
successes and 276 observed failures. A failure is an observed failure of that
exact request under that exact protocol, never a statement that a place cannot
support a road, harbour or airport.

The model is a directed reachability rule over `(segment, lane, node)` states,
one instance per mode. Junction pairing is fixed to `all`. Three things stay
named hypotheses rather than assumptions: which lane continues onto which at a
node (`PAIRINGS`), whether a vehicle may reverse inside a node (`UTURNS`), and
where the length lower bound comes from.

## Result

| Rule | TP | FP | TN | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| always-fail | 0 | 0 | 249 | 93 | null | 0.000 |
| always-candidate | 93 | 249 | 0 | 0 | 0.272 | 1.000 |
| weak component (undirected) | 93 | 249 | 0 | 0 | 0.272 | 1.000 |
| **directed segment graph** | **93** | **19** | **230** | **0** | **0.830** | **1.000** |
| lane:any_lane (registered primary) | 93 | 19 | 230 | 0 | 0.830 | 1.000 |
| lane:index_same / orientation_index | 85 | 19 | 230 | 8 | 0.817 | 0.914 |
| lane:index_mirror / orientation_mirror | 59 | 8 | 241 | 34 | 0.881 | 0.634 |

Directed reachability reproduces every observed success and misses no failure in
230 of 249 negative cases. The 19 misses are all road requests in the two
targeted second openings, and every one is a native search-budget denial: the
returned result has `flags = 8` and `length = 100000`, exactly the protocol's
`maxLength`.

No pre-query length rule can separate them. Their undirected chord lower bound is
21.7–30.9 km, while observed successes reach 35.6 km; the largest lower bound of
any eligible request is 33 % of the cap. The lane-continuation hypotheses buy
nothing: `any_lane` and the segment-level graph predict identically, `index_same`
loses eight successes, and `index_mirror` trades 34 successes for 11 negatives.
The reversal hypothesis never changes a prediction on this evidence, because
re-entering a segment still has to satisfy that lane's direction grant.

## Per mode

| Mode | Eligible (primary) | Observed success | Observed failure | TP | FP | TN | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| road | 316 | 67 | 249 | 67 | 19 | 230 | 0 | 0.779 | 1.000 |
| ship | 16 | 16 | 0 | 16 | 0 | 0 | 0 | 1.000 (trivial) | 1.000 |
| air | 10 | 10 | 0 | 10 | 0 | 0 | 0 | 1.000 (trivial) | 1.000 |

Ship and air retained evidence is **one class**: every complete request
succeeded. Their precision is arithmetically 1 and carries no information, and
no rule in the frozen family can be distinguished on them. Only their
positive-consistency is checked. Their `no_lane` placeholders are unknown
coverage, not failures.

## Strata and groups

| Group | n | TP | FP | TN | FN |
| --- | ---: | ---: | ---: | ---: | ---: |
| distinct-edge boundary (primary) | 342 | 93 | 19 | 230 | 0 |
| same-edge boundary | 36 | 9 | 0 | 27 | 0 |
| PL-1121 first openings | 114 | 27 | 0 | 87 | 0 |
| PL-1142 targeted openings | 264 | 75 | 19 | 170 | 0 |
| asheville | 20 | 2 | 0 | 18 | 0 |
| boston | 24 | 6 | 0 | 18 | 0 |
| charleston | 24 | 6 | 0 | 18 | 0 |
| hong-kong | 102 | 11 | 6 | 85 | 0 |
| pittsburgh | 148 | 53 | 13 | 82 | 0 |
| rio | 24 | 15 | 0 | 9 | 0 |

Leave-one-package-out selection is estimable in all six packages that carry a
primary request. Every fold selects `directed_segment` on the other five and
scores its held-out package exactly as the pooled table does: no held-out fold
introduces a false negative, and the 19 false positives stay inside hong-kong and
pittsburgh.

## Not estimable here

- Junction pairing: the retained queries are two-endpoint reachability
  questions, so `continuation` and `single` pairings are not tested.
- Reversal permission: inert on this evidence.
- A native length, water-depth, width or grade threshold: none was swept.
- Geographic impossibility of any mode: not measured, and a failure here does
  not support it.
- Any service claim: no vehicle, passenger or cargo was observed using a
  connection.

## Offline bridge

Every field the model reads is recovered from all nine unchanged `.crp` packages
read-only, bound by SHA-256, plus a fixed prefab lane-template catalog and the
two observed flag-name catalogs. On 27,191 segments the bridge reproduces the
native segment id set, start and end nodes, prefab name and lane templates
exactly, and the per-mode model-input digests are identical. The `Outside` node
flag agrees on all 26,633 nodes. The two flag-name catalogs are cross-validated
leave-one-package-out; they cannot name one asheville-only and two
hong-kong-only node flag values, which does not affect any model input.

The bridge is not perfect in one respect it reports: airplane-path and some
movable segments have their own endpoint positions in the snapshot while the
save stores node centres, so 99.80 % of segments have a chord length within 2 %
and all are within 20 % (largest relative error 15.2 %). Chord length is used
only in the `maxLength` lower-bound check, which never binds, so this cannot
change a prediction.

## Layout

| Path | Purpose |
| --- | --- |
| `topology.py` | normalise a native snapshot or an export-derived package |
| `model.py` | pure prediction: no outcome, observation or old score is read |
| `inventory.py` | bind every retained request to its raw bytes and classify it |
| `predict.py` | freeze `protocol.json` and `predictions.json` |
| `evaluate.py` | bind and score the frozen predictions against labels |
| `bridge.py` | derive the model inputs from `.crp` bytes and compare |
| `bridge.json`, `catalogs.json` | bridge answer, field agreement and the fixed catalogs |
| `packages.json` | the nine package locators and SHA-256 |
| `inventory.json` | every retained request with eligibility and exclusions |
| `requests.json` | the label-free model inputs |
| `manifest.json` | source hashes, openings, counts and exclusions |
| `protocol.json`, `predictions.json`, `evaluation.json`, `integrity.json` | the freeze and its scored result |
| `test_outside_query_model.py` | 78 tests: domain, direction, `Invert`, allocation-id independence, abstention, binding, freeze, metrics, bridge |

## Order and hashes

Run `inventory.py`, then `bridge.py`, then `predict.py`, then `evaluate.py`.
`predict.py` reads only `requests.json` and the retained pre-query snapshots, and
`evaluate.py` refuses to run unless `protocol.json` already records the SHA-256
of the `predictions.json` on disk; a failed binding exits non-zero before any
report is written. Each freeze is committed before the evaluation code that
scores it, so the order in git shows the freeze rather than asserting it.
`integrity.json` re-checks every binding and hash and records the result.
