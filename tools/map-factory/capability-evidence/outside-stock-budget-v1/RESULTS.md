# Outside graph validation and road budget intervention

The primary rule matches all **48 new stock request labels**. All three modes
remain **unqualified** because the first stock control stopped before its six
queries. Only 16 road requests have exact export/native field identity.

Increasing the requested budget does not resolve any of the four retained road
errors. One matched old-success request fails at 100000 and succeeds at 200000
and 1000000. This is a measured budget response, not an explanation of the four
errors or a universal search law. The old labels remain unchanged.

## Frozen population and rules

The source is `030db86ce470b972b6ef3462a2698744dff40ebb`. The primary is
`lane:any_lane:forbidden`; the reference is `weak_component`. Their parameters,
catalog, requests, predictions, and intervention cohort do not change after
outcomes. The fixed catalog contains the old nine geographic packages and two
stock controls, bound to accepted source `914c153687106197e5f3a745d3ff7e181181ea8a`.
No new native inventory enters that catalog.

There are 105 installed builtin packages. Blank CO, the two controls, and all ten
PL-1239 cases are excluded by the declared inventory and package hashes. Of the
92 remaining packages, 28 have supported inputs. Sixty-four abstain, including
23 retained NetManager decode errors. `read_any` container coverage is recorded
by the post-capture header-only recheck in `header-coverage.json`. All 92 eligible
packages passed through that reader during preparation. Decoder failures are not repaired.

| Selected package | Road requests | Ship requests | Air requests | Reason |
| --- | ---: | ---: | ---: | --- |
| CCP Map 1 | 8 | 2 | 2 | First road positive/negative, ship positive, air positive |
| DN Fisher Enclave | 8 | 8 | 2 | First ship negative |
| CL Roslyn Peninsula | 8 | 2 | 8 | First air negative |
| CCMP2 Desert Map 2 | 0 | 0 | 0 | First unsupported, metadata only |
| CCMP2 Euro Map 1 | 0 | 0 | 0 | Second unsupported, metadata only |

The two unsupported packages retain null predictions for all modes. They are
six null package-mode records, not invented requests or native negatives.
Selected-request prediction coverage is 48/48, with no unknown native labels.
Per-mode selected-package coverage is 3/5. Package-selection tags overlap and
must not be summed as independent samples.

## New stock labels

These are descriptive intent-to-test counts, not qualified capability claims.
Precision and recall concern exact literal requests, not geography or service.

| Rule | Mode | TP | FP | TN | FN | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Primary | Road | 12 | 0 | 12 | 0 | 1.00 | 1.00 |
| Primary | Ship | 8 | 0 | 4 | 0 | 1.00 | 1.00 |
| Primary | Air | 8 | 0 | 4 | 0 | 1.00 | 1.00 |
| Weak component | Road | 12 | 12 | 0 | 0 | 0.50 | 1.00 |
| Weak component | Ship | 8 | 0 | 4 | 0 | 1.00 | 1.00 |
| Weak component | Air | 8 | 0 | 4 | 0 | 1.00 | 1.00 |

Primary TP/TN counts by package and mode:

| Package | Road | Ship | Air |
| --- | --- | --- | --- |
| CCP Map 1 | 4/4 | 2/0 | 2/0 |
| DN Fisher Enclave | 4/4 | 4/4 | 2/0 |
| CL Roslyn Peninsula | 4/4 | 2/0 | 4/4 |

Ship and air have absent negative-class power on the indicated one-class
packages. Per-package, per-mode, overlapping selection-stratum, null, and
snapshot-matched counts are retained in `evaluation.json.gz` and `audit.json.gz`.

There are no primary disagreements. Every reference disagreement is a road false
positive: query IDs `001`, `006`, `007`, and `008` on each of `holdout-01` and
`holdout-02`, and `001`, `002`, `007`, and `008` on `holdout-03`.
Each is complete and released, with native failure
flags 8, no positions, and returned length 100000. The primary rejects these
requests using lane-direction grants; weak connectivity cannot represent that
restriction. Every request, effective argument, and result remains in the audit.

## Bridge and controls

All bridge mismatches are retained and inspected. Ship/air endpoint heights
change at opening; maximum vertical differences are 33.0291, 161.9355, and
8.02645 in the three selected packages. Horizontal coordinates do not change.
CL Roslyn Peninsula also changes four road prefabs from `Highway` to
`Highway Connection`: segments 428, 8772, 24652, and 35418. No lane, connectivity,
Invert, or outside-role mismatch is observed. Applying the unchanged rule to
opening-native fields changes none of the 48 classifications. That is a
post-outcome diagnostic, never a replacement pre-export prediction.

The strict snapshot-matched subset contains only the first two packages' 16
road requests: TP 8, TN 8, FP/FN 0. The other 32 requests fail exact bridge
identity; they are not silently admitted to that subset.

CL Roslyn Peninsula (`holdout-03`) also has opening-to-post-batch height drift
on seven air segments (17396, 20340, 21466, 26056, 29446, 32716, 35098) and two
ship segments (9993, 31169). On 17 of its 18 queries, the pre-query all-mode
fingerprint differs from the opening fingerprint. Pre/post-query fingerprints
differ on `holdout-03/air/002`, `holdout-03/air/007`, and
`holdout-03/road/006`. This is separate from the `budget-01` air-height drift
reported below. All 18 `holdout-03` requests remain outside the strict subset;
the descriptive label counts are unchanged.

The first Asanu opening fails because the collector treats the native MetaBool
string `"False"` as a Python boolean. It stops before `PathManager.CreatePath`.
The opening and six Unknown planned controls are retained, without retry.
The guard correction precedes every new path request. Hanami completes all six
controls: an exact positive and invalid-vehicle rejection for each mode.
The frozen all-controls completion requirement still fails for every mode.

The original frozen scorer also omits the RPC transport's `ok=true` field.
`analysis/frozen-scorer-failure.log` preserves its failure. The separate,
post-control scorer requires exactly the frozen body keys plus `ok=true`.
`analysis/source-fix.json` and `analysis/schema-fix.diff.gz` bind that correction.
It changes no rule, request, native row, label, threshold, or qualification gate.

## Retained-road intervention

All rows below are new, correlated observations on unchanged CRP bytes. Their
immutable old labels are retained separately. Budgets are requested `maxLength`
floats passed to the public API, not metres or measured search work.

| Old request | Old label | 100000 | 200000 | 1000000 |
| --- | --- | --- | --- | --- |
| Pittsburgh 151 | failure | no_path | no_path | no_path |
| Hong Kong 167, matched control | success | no_path | success | success |
| Pittsburgh 037 | failure | no_path | no_path | no_path |
| Pittsburgh 197, matched control | success | success | success | success |
| Pittsburgh 201 | failure | no_path | no_path | no_path |
| Pittsburgh 057, matched control | success | success | success | success |
| Pittsburgh 093 | failure | no_path | no_path | no_path |
| Pittsburgh 147, matched control | success | success | success | success |

Every recorded non-budget constructor argument is equal within its three-budget
group. Failed path-unit length fields track the requested budgets; no API-entry
clamp is observed. Internal limits and cost units remain unidentified. Successful
returned paths/lengths can vary even when their labels do not.

Seven groups keep the all-mode graph fingerprint unchanged throughout. The
Pittsburgh 093 million-budget row does not: two air-segment endpoint heights
change during it. Full opening/post-batch road fields are identical, but separate
per-query road-only snapshots were not retained. This row fails the stricter
all-mode constancy check and is not described as a clean single-variable trial.
The changing fields, fingerprints, frames, and contexts are preserved.

The four retained errors remain unexplained. The matched Hong Kong request's
new 100000 failure does not overwrite its old success. No additional error
selection, retry, named-place rule, or model refit follows these outcomes.

## Verification and limits

Nine openings are retained: eight complete and the pre-query control failure.
There are 84 planned query IDs: 78 observed and six Unknown controls. Every
observed request has consistent handles, flags, release state, and exact positive
endpoints. All 45 observed game/collector/driver/auditor/GPU-monitor PID/start
identities are gone; the harness slot is free. Cleanup receipts are additional
evidence, not substitutes for identity coverage.

The new DLL is launch-bound in each opening. Twenty-five phase inventories bind
the executable, required assemblies, DLL, declared file trees, and plugin state.
Each records the excluded anonymous dynamic-method assembly; none has an
unresolved loaded-assembly entry. This is file identity, not memory attestation
or strict no-mods. Retained historical serialization errors, the 23 new-reader decode errors, and
the collector/scorer schema failures remain limitations. The old launch receipt's "no monitor"
caption is stale after the auditor addition; auditor-launch/completion records,
not that caption, establish actual process coverage.

All 105 raw files reconstruct byte-for-byte from their retained gzip members.
Scoring replay is byte-identical; audit replay differs only in creation time.
Seven study tests and the strict wire-schema test pass. `JOURNAL.md` records
measured GPU samples and their limits.

The holdout is prospective relative to the frozen requests, while the older fit
remains retrospective. Requests, reciprocal pairs, lanes, and repeated openings
are correlated. Stock packages have no invented physical-input/CPU lineage;
old exports retain only their exact CRP and old CPU receipts. There is no
geographic-negative oracle, sustained-navigation claim, app adoption, certificate,
public merge, Shelf page, or manual deployment. The existing Vercel integration
posts automatic preview statuses on branch pushes; those are not native proof.
No deployment command was issued and no preview was opened. Full PL-1119 remains incomplete.
