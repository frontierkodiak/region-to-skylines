# Rail query-scoped reachability: measured result

A retrospective fit of one query-scoped rail reachability model to the accepted
PL-1215 native study. This is the corrected report (`rail-query-model-v2-corrected`)
after the review of PR81 head `97e0038`; the reviewed report and its frozen
artifacts are preserved at this prefix's root, and the correction record is
[`corrected/CORRECTION.md`](corrected/CORRECTION.md).

It does not complete PL-1119, does not fit a place-level railway promise, and
makes no geographic-accuracy, prevalence, "no rail" certificate, service or live
"yes" claim. The aggregate counts below were already known from the accepted
study; this work adds the model, the measured comparison and the offline bridge.

## What is being predicted

One selected literal-boundary request: `from=[segment,lane,offset]`,
`to=[segment,lane,offset]`, submitted to `PathManager.CreatePath` as
Train/All/`Vehicle|TransportVehicle|CargoVehicle`/seed 857/maxLength 100000. The
prediction is whether a **complete path whose returned first and last positions
equal the requested literal offsets** comes back.

Labels are exact successes, observed failures and Unknowns:

* exact success: complete, released, `success=true`, returned endpoints equal
  the request;
* observed failure: complete, released, `success=false`. This is a failure of
  that request/mode/flags/protocol, never a geographic negative;
* Unknown: incomplete, unreleased or endpoint-mismatched. Never scored.

The frozen primary set is 276 selected requests across eleven accepted
openings: 32 stock controls and 244 cohort. It resolves to **27 exact
successes** (25 distinct-edge, 2 same-edge) and **249 observed failures**, with
no Unknown rows. Pittsburgh selected 128 of its 240 candidate pairs; its 112
unqueried candidates stay unqueried. Charleston, Grand Canyon and Yosemite have
no directed candidate pair, so they contribute no request and are **unscored**;
an empty candidate list is not scored as absence.

## Freeze order and versions

The reviewed head `97e0038` froze `protocol.json`, `predictions.json`,
`evaluation.json`, `bridge.json`, `catalogs.json` and `integrity.json` at the
prefix root. Those six files are preserved byte-for-byte, and a test pins their
SHA-256 values. The corrected freeze is written beside them in `corrected/`:

1. `corrected/protocol.json` and `corrected/predictions.json` are written from
   each opening's frozen network snapshot and plan **before** the corrected
   evaluator opens any observation.
2. `evaluate.py --check` then binds every prediction to its plan request,
   observed row, package hash, snapshot hash, protocol hash and model sources
   before it scores anything.
3. `corrected/evaluation.json` and `corrected/bridge.json` record the result.

`model.py` has no path to an outcome, observation or old score, and a test
asserts that. The topology-only family was frozen and scored first in v1; the
junction family is a second labelled freeze added because the first failed to
separate the classes. Both are reported in full, and the fitted rule is a
hypothesis, not an adopted rule.

This is an already-observed cohort, not a blind or prospective holdout, so no
prediction here is a held-out accuracy estimate.

## Primary set, by opening

| Opening | Split | Selected | Candidates | Train segments | Exact success | Failure |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| AP Asanu Beach (stock-1) | stock | 8 | 8 | 217 | 8 | 0 |
| AP Hanami Bay (stock-2) | stock | 24 | 24 | 225 | 8 | 16 |
| Asheville | cohort | 12 | 12 | 761 | 2 | 10 |
| Innsbruck | cohort | 20 | 20 | 693 | 2 | 18 |
| Boston | cohort | 72 | 72 | 1180 | 4 | 68 |
| Charleston | cohort | 0 | 0 | 194 | unscored | unscored |
| Grand Canyon | cohort | 0 | 0 | 149 | unscored | unscored |
| Hong Kong | cohort | 6 | 6 | 713 | 0 | 6 |
| Pittsburgh | cohort | 128 | 240 | 2584 | 3 | 125 |
| Rio | cohort | 6 | 6 | 500 | 0 | 6 |
| Yosemite | cohort | 0 | 0 | 0 | unscored | unscored |

## Model

A directed reachability rule over `(segment, lane, node)` states. A path starts
by travelling along the requested source lane away from its boundary node,
alternates "travel a segment" with "continue at a node", and must arrive at the
target node along the requested target lane.

Corrected domain: only Train-capable records are consumed. A segment joins the
graph only when it has a Train lane of an accepted type; only those lanes are
traversable or continuable; the requested lane must be one of them. Lane
continuation is counted by ordinal among a segment's Train lanes, so raw lane
indexes are never renumbered. Segment `Invert` swaps the required travel bit,
following the accepted native planner. A crossing of a node is a straightest
disjoint pairing, and equal-turn candidates are represented as alternatives
rather than broken by allocation id.

Length is the sum of segment chords, a lower bound on the native curve length.
It is relaxed shortest-first, checked on the opening and every later traversal,
and a path whose lower bound exceeds the protocol maximum is never a success.

Inputs are pre-query topology, geometry, lane direction bits, category, flags
and the request. No names, artifact ids, allocation ids or successful paths;
ids are graph references only, and tests rename every id, reorder segments and
reverse every segment orientation on a real frozen package without changing a
prediction.

Three unobservable native choices are named hypotheses:

* **lane continuation** — `any_lane`, `index_same`, `index_mirror`,
  `orientation_index` (lateral side preserved), `orientation_mirror`;
* **reversal** — `forbidden`, `deadend`, `allowed`, a real self-pair at the node;
* **junction** — `all`, `continuation` (disjoint straightest-first pairing),
  `single` (only the straightest pair).

## Measured result, all 276 selected queries

| Rule | TP | FP | TN | FN | Abstain | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| always-fail | 0 | 0 | 249 | 27 | 0 | null | 0.000 |
| always-candidate | 27 | 249 | 0 | 0 | 0 | 0.098 | 1.000 |
| weak_component | 27 | 198 | 51 | 0 | 0 | 0.120 | 1.000 |
| lane:any_lane:forbidden (= the component rule) | 27 | 198 | 51 | 0 | 0 | 0.120 | 1.000 |
| lane:orientation_index:forbidden (pre-registered primary) | 11 | 198 | 51 | 16 | 0 | 0.053 | 0.407 |
| lane:index_same:forbidden | 5 | 48 | 201 | 22 | 0 | 0.094 | 0.185 |
| lane:index_mirror:forbidden / orientation_mirror:forbidden | 0 | 0 | 249 | 27 | 0 | null | 0.000 |
| junction:single:any_lane | 24 | 4 | 245 | 3 | 0 | 0.857 | 0.889 |
| **junction:continuation:any_lane (fitted)** | **26** | **4** | **245** | **1** | **0** | **0.867** | **0.963** |
| junction:continuation:orientation_index | 10 | 4 | 245 | 17 | 0 | 0.714 | 0.370 |

All 28 rules are reported in `corrected/evaluation.json`, including every null
and every hypothesis that scores nothing; the table above lists each distinct
outcome. Coverage is 1.000 and abstention 0 for every rule on this set: no real package
produces more than one junction resolution, so the corrected tie representation
never had to abstain here. The abstention path exists for unresolved ties and
missing inputs and is covered by tests. Precision and recall are null, not zero,
when their denominator is empty; no always-fail percentage is headlined.

Two facts about the upper bound matter more than its score. **Every observed
success in this selected set is inside one weak Train component**, and all 51
selected cross-component requests failed. That is the one denial this
retrospective set supports without further assumptions; it is not a general
proof that such connections can never be joined natively. Reachability is
necessary and not sufficient here, and `always-candidate` is strictly dominated
by the component rule (same recall, better precision).

## The fitted rule and its groups

`junction:continuation:any_lane`: at a node, pair incident Train segments
straightest-first into disjoint pairs and connect only those; a Train lane
continues onto any Train lane of the connected segment; endpoint lanes must be
usable in the requested direction; no reversal at a node.

| Group | TP | FP | TN | FN | Abstain | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| stock controls | 16 | 0 | 16 | 0 | 0 | 1.000 | 1.000 |
| cohort | 10 | 4 | 229 | 1 | 0 | 0.714 | 0.909 |

Per opening, the fitted rule is exact on AP Asanu Beach, AP Hanami Bay,
Asheville, Innsbruck, Boston, Hong Kong and Rio. Charleston, Grand Canyon and
Yosemite have zero selected queries and are unscored. **All five errors are in
Pittsburgh**: four false positives and one false negative, listed below. That is
the honest boundary of the fit — the dense 16-outside-connection network is
where the export-only junction rule stops tracking the native one, and where a
112-candidate cap leaves coverage partial.

## Counterexamples, fitted rule

Every error with its exact request and the hashes of the raw files it is scored
against. Full detail is in `corrected/evaluation.json`.

| Kind | Query | From | To | Native result |
| --- | --- | --- | --- | --- |
| false positive | pittsburgh:54 | `[4506,0,255]` | `[5693,1,255]` | failed, flags 8, length 100000 |
| false positive | pittsburgh:166 | `[5093,1,0]` | `[5748,1,255]` | failed, flags 8, length 100000 |
| false positive | pittsburgh:220 | `[5693,0,255]` | `[4506,1,255]` | failed, flags 8, length 100000 |
| false positive | pittsburgh:252 | `[5748,0,255]` | `[5093,0,0]` | failed, flags 8, length 100000 |
| false negative | pittsburgh:232 | `[5693,0,255]` | `[5758,0,0]` | success, flags 4, length 21488.46 |

## Offline bridge

The nine unchanged cohort packages were read as saved `.crp` exports at their
frozen locators with the existing owned readers (`crp.py`, `netcodec.py`,
`network_writer.section_start`), read-only, never rebuilt, recaptured or
repaired. Every model-used field was derived and compared with the native
snapshot of the same opening:

| Field | Checked | Agree |
| --- | ---: | ---: |
| segment present | 6774 | 100 % |
| start / end node | 6774 | 100 % |
| prefab name | 6774 | 100 % |
| node position | 6774 | 100 % |
| lane index, type, vehicle, category, travel bits | 6774 | 100 % |
| Invert predicate | 6774 | 100 % |
| Outside predicate | 6750 nodes | 100 % |

The bridge also compares a canonical digest of exactly the records the model
consumes — Train-capable segments and their incident nodes with every field above
— and the digests are identical for all nine packages. All 244 cohort requests
receive the same prediction from export bytes as from the native snapshot. The
prefab lane template catalog and the integer flag-name catalog are hash-bound
observed tables, not export bytes on their own; both are cross-validated
leave-one-package-out: every package's Train prefabs are found in the other
eight, and every lane, Outside and Invert field decodes correctly.

Two limits are reported rather than smoothed. The game recomputes
`OneWayIn`/`OneWayOut` on nodes at load, so a node flag value can name different
sets in the export and the snapshot; the model never uses those bits. Airplane
and ship path node positions are also recomputed at load and differ from the
export by hundreds of metres; the model uses only Train geometry, where all
positions match. The two stock controls are Steam-install copies in CRP package
format 8, which this bridge does not read, so they stay **native-snapshot
only**.

**Bridge status: established for the nine cohort packages** — the model is an
export-scoped model there, not a native-snapshot-only one.

## What this supports

* A rigid denial for the selected set: two outside rail endpoints in different
  Train components were never joined by a native path here — 51 of 51 observed
  failures. This is a retrospective statement about that set.
* Reachability (same component, direction-compatible endpoint lanes) is
  necessary for success in this set, and the direction/lane-index refinements of
  the first family add nothing on their own.
* A compact deterministic junction hypothesis — a node continues only its
  disjoint straightest segment pairing — reproduces 271 of 276 selected
  outcomes from export-derivable fields, and all of them outside Pittsburgh.
* The fitted rule's inputs are export-derivable for the nine cohort packages.

## What is not established

* It is a retrospective fit on an already-observed cohort, not a blind holdout
  or a prospective result. The junction family was selected after the first
  family was scored, so the fitted rule is a hypothesis for native validation,
  not an accepted rule.
* The remaining Pittsburgh errors show the straightest-continuation hypothesis
  is not the native junction rule everywhere.
* Native lane-to-lane connectivity, junction behaviour, path cost and rejected
  pairs are still not observed directly; this study infers them from outcomes.
* The 51 cross-component failures do not establish a general native
  impossibility. An unpaused opening snapshot and an inferred junction rule
  cannot prove that such connections could never be joined.
* Opening graph precedes the unpaused queries and state may evolve. The 100000
  maximum path length, the 128-request cap, 112 Pittsburgh candidates left
  unqueried, dynamic-assembly exclusion, plugins, three DLC-panel errors and
  Pittsburgh's degraded strict teardown (separate later exit audit) all bound
  the claim.
* FILE identity is not memory attestation or strict no-mods. Actual rail
  service, train spawning, editor/gameplay parity, sustained gameplay and human
  play are **not verified**.

No old PL-1072/1078/v3 scorer, predictor, judge, outcome or refit was rerun,
relabelled or rewritten. No parent ledger, live model/UI, certificate, resource
or default rule, main branch, Shelf or production deployment changed, and no
browser or physical map rebuild was needed. PL-1191's water construction and
holdout work was not touched.

## Version history

| Version | Where | Result |
| --- | --- | --- |
| v1, reviewed | root JSON at `97e0038`, preserved byte-for-byte | fitted 26/4/245/1; primary 13/198/51/14; five executable-domain defects |
| v2, corrected | `corrected/` | fitted 26/4/245/1; primary 11/198/51/16; domain, tie, reversal, length and binding contracts fixed |

The v1→v2 delta is in [`corrected/CORRECTION.md`](corrected/CORRECTION.md). The
fitted rule's counts and counterexamples are unchanged; the primary and
`junction:*:orientation_index` rules lose two stock-control successes to the
`Invert` correction, which is the defect the reviewed head had.
