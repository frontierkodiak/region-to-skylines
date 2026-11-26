# Query-scoped rail reachability model v1

A retrospective study of one narrow question on the accepted PL-1215 native
study: given one literal-boundary rail request, does `PathManager.CreatePath`
return a complete path? The model sees only what a saved map export contains
before any query: segment and node identity, geometry, flags, lane categories,
lane travel bits, and the request parameters.

The measurements are the point. The report is [`RESULTS.md`](RESULTS.md); the
reproduction is [`REPRODUCE.md`](REPRODUCE.md). This is the **corrected v2**
freeze after the review of PR81 head `97e0038`; the correction record is
[`corrected/CORRECTION.md`](corrected/CORRECTION.md).

## What was measured

The frozen primary set is 276 selected literal-boundary requests from the
accepted study: 32 stock-control and 244 cohort queries, 27 exact successes
(25 distinct-edge, 2 same-edge) and 249 observed failures. A failed request is
an observed failure for that exact request, mode, flags and protocol, never a
statement that a place has no railway. Charleston, Grand Canyon and Yosemite
have zero selected queries and are unscored.

The model is a directed reachability rule over `(segment, lane, node)` states.
It consumes only Train-capable records, applies segment `Invert` to the required
travel bit, and represents unresolved junction ties as alternatives instead of
comparing allocation ids. Its three unobservable native choices are named
hypotheses, not assumptions:

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
| primary, pre-registered lane rule | 11 | 198 | 51 | 16 | 0.053 | 0.407 |
| **fitted, straightest-continuation junction** | **26** | **4** | **245** | **1** | **0.867** | **0.963** |

Every observed success in the selected set is inside a weak Train component, and
all 51 selected cross-component requests fail; 198 same-component requests also
fail. The fitted rule reproduces every query of both stock controls, Asheville,
Innsbruck, Boston, Hong Kong and Rio, and misses only inside Pittsburgh, where
its five errors are recorded with the exact request and raw hashes.

## Offline bridge

The nine unchanged cohort packages were read directly from their frozen `.crp`
exports. Every field the model uses is reproduced from export bytes and the two
hash-bound observed catalogs (prefab lane templates, integer flag names), with
100 % agreement on 6,774 Train segments, identical model-input digests and
identical predictions on all 244 cohort requests. Both catalogs are
cross-validated leave-one-package-out. The two stock controls are Steam-install
copies in an older package container (format 8) and stay native-snapshot only.

## Layout and versions

| Path | Purpose |
| --- | --- |
| `topology.py` | normalise a native snapshot or an export-derived package |
| `model.py` | pure prediction: no outcome, observation or old score is read |
| `predict.py` | freeze `corrected/protocol.json` and `corrected/predictions.json` |
| `evaluate.py` | bind and score predictions against the frozen observation bytes |
| `bridge.py` | derive the model inputs from `.crp` bytes and compare |
| `packages.json` | frozen package locators and SHA-256 |
| `openings.json` | the frozen primary openings, splits, bridge scope and exclusions |
| `protocol.json`, `predictions.json`, `evaluation.json`, `bridge.json`, `catalogs.json`, `integrity.json` | the reviewed **v1** freeze at `97e0038`, preserved byte-for-byte |
| `corrected/` | the **v2** freeze: protocol, predictions, evaluation, bridge, catalogs, integrity, correction record and contract evidence |
| `test_rail_query_model.py` | 43 tests: invariances, domains, ties, reversals, length, abstention, binding, arithmetic, bridge |
