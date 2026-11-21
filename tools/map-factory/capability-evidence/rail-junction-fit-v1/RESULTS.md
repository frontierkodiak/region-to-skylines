# Export-authored junction geometry: a rail junction-fit study v1

One bounded, off-game research question on the accepted PL-1215 native study:
**when a node connects the disjoint straightest continuation of its incident
Train segments, is "straightest" measured from the chord between node positions
(the accepted v2 rule) or from the authored endpoint tangents the game stores on
each segment?**

The accepted study fitted a junction rule that reproduces 271 of 276 selected
outcomes and leaves five errors, all inside Pittsburgh. Its report names the
straightest-continuation hypothesis but says the remaining errors show it is
not the native junction rule everywhere. This study tests the smallest
general explanation of those errors that the export can carry: the angle
measure, not the junction idea.

This does not complete PL-1119, does not fit a place-level railway promise, and
makes no geographic-accuracy, prevalence, rail-spawning, service or product
claim. It is retrospective fitting on an already-observed set, not a blind or
prospective holdout.

## What is frozen, and in what order

1. `manifest.json` - the predeclared design: the two measures, the junction
   kinds, the two lane-continuation pairings, the threshold grid
   `0,5,10,15,20,30,45,60,90,120,150,180` degrees, the rule list, the splits,
   the selection criterion and the label definitions. It pins the accepted
   prefix and the exact source revision.
2. `freeze.py` - writes `protocol.json` (the design), `features.json` (the
   input-only inventory: package lineage, tangent precision, field agreement)
   and `predictions.json` (every rule's prediction for every selected query).
   It refuses to open an `observation.json.gz`; a test scans the predict path
   for one and exercises the freeze with a loader that raises.
3. `evaluate.py` - binds those three artifacts to the frozen plans, package
   bytes and observation bytes, then labels and scores them. The labels are
   read here for the first time.
4. `diagnose.py` - after the scores exist, explains the reference rule's five
   errors mechanically. It is not part of the prediction path.
5. `export_bridge.py` - audits what the study reads from the saved `.crp`
   exports, including the two stock controls in the older package container.

`predictions.json` records a `queries_sha256` over the predictions alone, so a
later change to documentation or diagnostics can be shown not to have moved a
single prediction.

## The rules

58 rules, every one reported. The families form a 2x2x2 comparison around the
accepted fitted rule:

| Dimension | Values |
| --- | --- |
| angle measure | `chord` (accepted v2), `tangent` (authored endpoint directions) |
| junction kind | `continuation` (accepted greedy disjoint straightest pairing), `turn` (every pair inside a threshold) |
| lane continuation | `any_lane` (accepted fitted), `orientation_index` (accepted lateral-side rule) |

plus the accepted frozen rules (`frozen:*`) and the three baselines, delegated
to the accepted model for the baseline comparison. The chord rules are an
independent reimplementation and reproduce the accepted predictions on all 276
queries exactly; a test asserts that.

The reachability core - Train-only domain, `Invert`-aware travel bits, raw lane
indexes, chord lower-bound length with shortest-first relaxation - is the
accepted `model._reach`, called unchanged.

## Result

Full set: 276 selected queries, 32 stock controls and 244 cohort, 27 exact
successes and 249 observed failures, no Unknowns.

| Rule | TP | FP | TN | FN | Precision | Recall | Balanced |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| accepted reference `frozen:junction:continuation:any_lane` | 26 | 4 | 245 | 1 | 0.867 | 0.963 | 0.973 |
| `chord:continuation:any_lane` (same rule, reimplemented) | 26 | 4 | 245 | 1 | 0.867 | 0.963 | 0.973 |
| **`tangent:continuation:any_lane` (the pre-registered counterpart)** | **27** | **0** | **249** | **0** | **1.000** | **1.000** | **1.000** |
| `chord:continuation:orientation_index` | 10 | 4 | 245 | 17 | 0.714 | 0.370 | 0.677 |
| `tangent:continuation:orientation_index` | 11 | 0 | 249 | 16 | 1.000 | 0.407 | 0.704 |
| `tangent:turn:15:any_lane` | 26 | 0 | 249 | 1 | 1.000 | 0.963 | 0.981 |
| `tangent:turn:20/30/45:any_lane` | 27 | 0 | 249 | 0 | 1.000 | 1.000 | 1.000 |
| `tangent:turn:60:any_lane` | 27 | 18 | 231 | 0 | 0.600 | 1.000 | 0.964 |
| `chord:turn:20:any_lane` | 20 | 0 | 249 | 7 | 1.000 | 0.741 | 0.870 |
| `chord:turn:30:any_lane` | 22 | 6 | 243 | 5 | 0.786 | 0.815 | 0.895 |
| `chord:turn:45:any_lane` | 23 | 10 | 239 | 4 | 0.697 | 0.852 | 0.906 |
| `chord:turn:90:any_lane` | 27 | 97 | 152 | 0 | 0.218 | 1.000 | 0.805 |

Stringent separation holds over a broad plateau - tangent turn 20, 30 and 45
degrees all score 27/0/249/0 - not at one knife-edge threshold. The chord
measure never reaches it. The paired comparison of the reference and its
tangent counterpart on identical requests: **5 queries corrected, 0 broken,
0 both wrong, 271 both right.** Stock controls 16/0/16/0 under both; cohort
10/4/229/1 under the reference and 11/0/233/0 under the tangent counterpart.

Abstention is zero everywhere on this set; the abstention paths exist for
unresolved ties, missing tangents and missing records and are covered by tests.

## Grouped retrospective validation

Strict leave-one-package-out over the six cohort packages that have queries:
the rule is selected on the other packages only, then evaluated on the held-out
package. Stock controls are never training rows and are evaluated as held-out
packages trained only on the cohort. Selection is by balanced accuracy among
rules that abstain on nothing in training, with a predeclared tie-break
(precision, recall, then name); every tied rule is recorded.

| Fold | Held out | Selected on training | Held-out result (selected) | Held-out result (fixed tangent counterpart) |
| --- | --- | --- | --- | --- |
| cohort:asheville | 12 | tangent:continuation:any_lane | 2/0/10/0 | 2/0/10/0 |
| cohort:innsbruck | 20 | tangent:continuation:any_lane | 2/0/18/0 | 2/0/18/0 |
| cohort:boston | 72 | tangent:continuation:any_lane | 4/0/68/0 | 4/0/68/0 |
| cohort:hong-kong | 6 | tangent:continuation:any_lane | 0/0/6/0 | 0/0/6/0 |
| cohort:pittsburgh | 128 | chord:continuation:any_lane | 2/4/121/1 | 3/0/125/0 |
| cohort:rio | 6 | tangent:continuation:any_lane | 0/0/6/0 | 0/0/6/0 |
| control:stock-1 | 8 | tangent:continuation:any_lane | 8/0/0/0 | 8/0/0/0 |
| control:stock-2 | 24 | tangent:continuation:any_lane | 8/0/16/0 | 8/0/16/0 |

The selection result is the honest counterweight to the perfect full-set score.
Five of the six cohort folds select the tangent rule, because Pittsburgh - the
only package with errors to separate the rules - is in their training set. In
the sixth fold Pittsburgh is held out, every rule that is perfect on the
remaining packages ties at balanced accuracy 1.0, and the predeclared tie-break
reaches the chord rule by name. So **pooled selected out-of-fold is
10/4/229/1, identical to the reference**, while the fixed, pre-registered
tangent counterpart scores **11/0/233/0** out of fold. The leave-one-package-out
procedure cannot demonstrate the tangent rule's advantage on the one package
that discriminates; the paired fixed-rule comparison does, and neither is a
blind estimate.

## Error mechanics

All five reference errors are in Pittsburgh, and all five trace to **two
junctions**. Of 2,550 nodes with at least two incident Train segments in
Pittsburgh, the chord and tangent continuation pairings differ at exactly two.
(Rio has four such nodes and no misprediction under either measure; the other
nine packages have none.)

**Node 3975** (segments 4064, 4065, 5913). By chord, 4064-4065 is the
straightest pair at 24.74 degrees and is connected. By authored tangent, that
pair is 51.23 degrees while 4064-5913 is 24.51, so the tangent pairing connects
4064-5913 and cuts 4064-4065. The reference rule's witness routes for the two
false positives `pittsburgh:166` and `pittsburgh:252` both cross that cut,
which removes both false positives.

**Node 5128** (segments 5211, 5478, 5740). By chord, 5211-5478 is the
straightest pair at 25.75 degrees. By authored tangent it is 51.73 degrees
while 5478-5740 is 15.22, so the tangent pairing connects 5478-5740 and cuts
5211-5478. The two false positives `pittsburgh:54` and `pittsburgh:220` both
route through it, and the false negative `pittsburgh:232` is a query whose
tangent-rule witness is a 220-crossing route whose **only** measure-differing
junction is 5128: the added 5478-5740 edge is what restores reachability.

One limit has to be stated with that. The false negative's native path is not
reproduced by either rule: it crosses node 5355 on 5877-5428, a pair that both
the chord and the tangent continuation pairings reject (the reference rejects
three of its 250 transitions, the tangent rule two). The tangent rule matches
the native *outcome* through a different route. So the perfect score is a
better fit, not an identified native junction law, and the continuation
hypothesis is still contradicted by that node.

## Offline bridge

Every rule's inputs for all 11 packages are export-derivable, and the two stock
controls in the older **format-8** container are now decoded rather than
conceded as native-snapshot-only. The container is read with
`survey/measure_maps.py:read_any` (formats 4-12), and each NetManager section is
decoded with the data version it declares - 121034 for the nine cohort exports,
114007 and 114009 for the two stock controls, both read-only.

| Field | Checked | Agree |
| --- | ---: | ---: |
| segment present | 7,216 | 100 % |
| start / end node | 7,216 | 100 % |
| prefab | 7,216 | 100 % |
| node position | 7,216 | 100 % |
| lane index, type, vehicle, category, travel bits | 7,216 | 100 % |
| `Invert` predicate | 7,216 | 100 % |
| `Outside` predicate | 7,198 nodes | 100 % |

That field table is in-sample for each package's own observed prefab and flag
catalogs; the audit's leave-one-package-out section reports the generalisation
limit, which is why the two stock controls are labelled
`export_derivable_with_own_catalog`. The canonical model-input digests of the
export-derived and native records are identical for all 11 packages, and the newly audited tangent table covers all
7,216 Train segments with none missing.

Two precision facts are reported rather than smoothed. Positions and tangents
are IEEE-754 binary32; the tangents' horizontal projection is unit to float32
(1.0 to within 1e-7 on the nine cohort exports and 7.3e-4 on one stock control) and carries a separate vertical component of up to 0.40, so the
turn angle uses the horizontal projection. Their horizontal direction differs
from the chord by a median of 0.16-0.98 degrees and a 90th percentile of
1.2-8.0 degrees per package, with a maximum up to 104.5 degrees where the
authored curve leaves the straight chord. `override_direction_limit` is 0 on
every segment in every package, so it carries no signal and no rule uses it.

The two stock controls need their **own** package's prefab lane template: a
leave-one-package-out catalog misses one Train prefab of the first and two of
the second. So their
lane fields are `export_derivable_with_own_catalog`; their tangents and all
segment and node topology are read directly from the export bytes. Yosemite has
no Train segment at all and is reported as `no_train_domain`, not as a pass.

## What this supports

* The accepted fitted rule's five errors are all explained by one modelling
  choice at two junctions: the junction angle was measured from chords, and the
  export carries the authored endpoint tangents that the game itself stores.
* With the authored tangents, the same compact continuation rule separates all
  276 selected outcomes, over a 20-45 degree plateau of the turn family, and
  breaks none of the 271 the accepted rule already got right.
* The two junctions that explain the five errors are the only two junctions in
  Pittsburgh where the two measures derive a different pairing.

## What this does not establish

* It is retrospective fitting on an already-observed cohort, not a blind or
  prospective result. The tangent counterpart was pre-registered, but its
  perfect score is not an out-of-sample accuracy estimate.
* The leave-one-package-out selection cannot prefer the tangent rule when the
  only discriminating package is held out; its pooled selected score equals the
  reference's.
* The tangent fields are export-derived, not native-attested: the accepted
  `networks.json` snapshots do not emit endpoint tangents. Nothing here claims
  a completed native bridge for them.
* Native lane-to-lane connectivity, junction behaviour and path cost remain
  unobserved. The false negative's native path crosses a junction both
  pairings reject, so the continuation hypothesis is still incomplete.
* No place has "no railway". A failed request is a failure of that exact
  request, mode, flags and protocol.
* The 100,000 maximum path length, the 128-request cap, 112 unqueried
  Pittsburgh candidates, dynamic-assembly exclusion, plugins, three DLC-panel
  errors and Pittsburgh's degraded strict teardown (separate later exit audit)
  all bound the claim.
* FILE identity is not memory attestation or strict no-mods. Rail service,
  train spawning, editor/gameplay parity and human play are not verified.

The accepted corrected numbers are retained and untouched: the fitted junction
rule is still 26/4/245/1 and the primary lane rule still 11/198/51/16, and the
six reviewed and six corrected artifacts keep their own hashes. This study adds
a new prefix; it does not re-score or overwrite them. No old PL-1072/1078/v3
scorer, predictor, judge, outcome or refit was rerun, relabelled or rewritten. No parent ledger, UI, contract, golden, default,
writer, main branch or Shelf changed. No game, browser, server or physical
rebuild was used.

## Version history

| Version | Where | Result |
| --- | --- | --- |
| v1 | this prefix | reference 26/4/245/1; tangent counterpart 27/0/249/0; pooled selected 10/4/229/1; pooled tangent counterpart 11/0/233/0 |
