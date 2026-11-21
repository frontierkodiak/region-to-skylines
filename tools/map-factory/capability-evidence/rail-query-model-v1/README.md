# Query-scoped rail reachability model v1

A retrospective study of one narrow question on the accepted PL-1215 native
study: given one literal-boundary rail request, does `PathManager.CreatePath`
return a complete path? The model sees only what a saved map export contains
before any query: segment and node identity, geometry, flags, lane categories,
lane travel bits, and the request parameters.

The measurements are the point. The report is [`RESULTS.md`](RESULTS.md); the
reproduction is [`REPRODUCE.md`](REPRODUCE.md).

## What was measured

The frozen primary set is 276 selected literal-boundary requests from the
accepted study: 32 stock-control and 244 cohort queries, 27 exact successes
(25 distinct-edge, 2 same-edge) and 249 observed failures. A failed request is
an observed failure for that exact request, mode, flags and protocol, never a
statement that a place has no railway.

The model is a directed reachability rule over `(segment, lane, node)` states.
Its three unobservable native choices are named hypotheses, not assumptions:

| Choice | Values | What it decides |
| --- | --- | --- |
| lane continuation | `any_lane`, `index_same`, `index_mirror`, `orientation_index`, `orientation_mirror` | which lane of one segment may continue onto which lane of the next at a node |
| reversal | `forbidden`, `deadend`, `allowed` | whether a train may reverse inside one node |
| junction | `all`, `continuation`, `single` | which incident segment pairs a node connects at all |

The topology-only family was frozen and scored first. It does not separate the
classes. The junction family asks whether a node connects only a disjoint
straightest-continuation pairing (as if a branching node passes straight
through and does not offer a turn). That family is reported in full, and its
best member is the study's fitted rule.

## Result

| Rule | TP | FP | TN | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| always-fail | 0 | 0 | 249 | 27 | null | 0.000 |
| always-candidate | 27 | 249 | 0 | 0 | 0.098 | 1.000 |
| weak component (= any-lane reachability) | 27 | 198 | 51 | 0 | 0.120 | 1.000 |
| primary, pre-registered lane rule | 13 | 198 | 51 | 14 | 0.062 | 0.481 |
| **fitted, straightest-continuation junction** | **26** | **4** | **245** | **1** | **0.867** | **0.963** |

All 27 observed successes are inside a weak component, and 51 of 51
cross-component requests fail. Reachability is necessary and not sufficient.
The fitted rule reproduces every query of both stock controls, Asheville,
Innsbruck, Boston, Hong Kong and Rio, and misses only inside Pittsburgh, where
its five errors are recorded with the exact request and raw hashes.

## Offline bridge

The nine unchanged cohort packages were read directly from their frozen `.crp`
exports. Every field the model uses is reproduced from export bytes and the two
hash-bound observed catalogs (prefab lane templates, integer flag names), with
100 % agreement on 6,774 Train segments and identical predictions on all 244
cohort requests. Both catalogs are cross-validated leave-one-package-out. The
two stock controls are Steam-install copies in an older package container
(format 8) and stay native-snapshot only.

## Files

| File | Purpose |
| --- | --- |
| `topology.py` | normalise a native snapshot or an export-derived package |
| `model.py` | pure prediction: no outcome, observation or old score is read |
| `predict.py` | freeze `protocol.json` and `predictions.json` |
| `evaluate.py` | score predictions against the frozen observation bytes |
| `bridge.py` | derive the model inputs from `.crp` bytes and compare |
| `packages.json` | frozen package locators and SHA-256 |
| `openings.json` | the frozen primary openings, splits and exclusions |
| `protocol.json`, `predictions.json` | freeze and input-only predictions |
| `evaluation.json` | measured confusion, groups and counterexamples |
| `bridge.json`, `catalogs.json` | bridge report and observed catalogs |
| `integrity.json` | SHA-256 of every input, output and source |
| `test_rail_query_model.py` | 26 tests: invariances, abstention, arithmetic, bridge |
