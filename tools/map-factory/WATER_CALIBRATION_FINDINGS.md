# Water-calibration findings: no demonstrated safe-square class

Latest collection: **5 of 28 exportable squares complete; 23 remain**, plus two
original capture failures. The full one-shot holdout score has not run.

PL-1075 independently reviewed preparation at `bb2a1ec` against `4a4ec21`.
Its regression, old-corpus refresh, frozen fit, and synthetic scoring attacks
reproduced. There was no blocking preparation defect. Actual native scoring
remains unverified. The later producer delta fixes the declined-assessment crash,
checks source equivalence, and records the limits below.

## Reject the drying discriminator

All 30 selected squares were attempted. Twenty-eight exported; the South American
lake-shore square has no buildable start, and the African low-coast square fails
the fitted-network-position check. Both remain in the panel, unscored. Neither
is a hydraulic outcome or a replacement opportunity.

The frozen drying rule flags **all 28 exports**, including all six intended
negative uplands. Its narrow-film clause alone fires on each. Therefore it is
identical to always-warn for **every possible set of future game labels**.
This is a logical rejection, not measured holdout precision or recall.

The combined candidate clears zero squares. The deployed app also warns on all
28. No game result can demonstrate a safer cleared set for either current rule
on this panel. **Reject the drying rule as a discriminator.** Retain its frozen
bytes only as a comparator; do not present it as a validated release model.
The existing warning guard remains in place while exporter release is held.

The native panel can still provide independent flood evidence and the missing
drying-negative training examples for a general replacement. It is not a test
that can qualify the present combined screen. A replacement learned from these
labels must use a new geography-disjoint holdout. Do not adjust cutoffs against
these inputs or repair selected squares.

## Do not promote the 3 m cutoff

Candidate and deployed flood flags agree on all 28 exports: five flag flooding.
No captured coastal freeboard lies between the two cutoffs, 1.5 m and 3 m.
Thus this panel can test the shared flood rule, but cannot identify the effect
of changing that cutoff. The candidate's improved old fit recovers one old Rio
case. It is not a reason to promote 3 m without independent contrasting evidence.
The deployed cutoff remains 1.5 m.

`stage_water_panel.input_power` reproduces these label-free conclusions in
`staged/input-power.json` before a game starts.

## Weighting and source identity

`freeze.json.old_training` contains **pooled run metrics**. Selection uses
equal-landscape macro rates. For the selected flood candidate, macro recall is
1.0 and macro specificity is 0.40; pooled specificity is 0.5135. These are old
training statistics, not new geographic validation.

The frozen panel's "equal-weight" estimand means equal weight per scored square,
not equal strata after exclusions. At most 28 squares can be scored; lake shore
and low coast each lose a cell. The European low-coast square has no ocean in
the captured data, leaving four actual coastal-branch examples. Report coverage
and per-stratum results; do not imply balanced strata or global prevalence.
The panel and model hashes remain exactly as frozen before capture.

Captures were made at `99702f1`, not the reviewed `bb2a1ec` or the final PR head.
All 21 bound writer-file hashes match those heads exactly; subsequent source
changes are experiment tools, tests, and documentation. Staging now verifies that
exact file set and its hashes. Scoring also rejects a different writer contract.
Source equivalence is not the same as claiming the capture ran at a later SHA.

## Native collection: first complete square

On November 20, `dry-upland-north-america` completed 60.062781 game minutes
on blade with clean, pinned harness `6949182`. Its simulation soak took
1066.053417 wall seconds, excluding queue and startup. Frozen package, initial
grids, probes, mapped-water mask, reference and per-run harness identity all
revalidate. Carbon was idle at launch, the read-only offline guard passed, and
owned game, Steam instances and transient units were empty after teardown.

The original no-flooding gate passed: worst excess area was 0.0031 km² against
0.05 km². The one required starter-reservoir probe passed at the end and at all
13 sampled epochs. Optional mapped water did change: wet area went from 2.03
to 1.28 km², with 0.94 km² dried and 0.19 km² newly wet at the native 0.1 m
threshold. Of 2409 initially wet monitored points, 608 were dry exactly at the
end and 137 had no natively wet neighbor within 64 m. These are observations
from one square, not an interim panel score or evidence of a safe cleared class.

The original overall verdict is **fail**, solely for unreviewed startup images.
It remains immutable in the collection ledger. Subsequent producer inspection
of the actual opening, Areas and final overview PNGs passed the hash-bound
startup-view assessment in a separate sidecar; this is neither human nor
independent visual acceptance. No original verdict was rewritten.

One of 28 exportable squares is collected; 27 remain, alongside the two original
capture failures. Collection uses complete foreground tranches with cleanup
before each continuation. The one-shot holdout score has not run. Focused review
PL-1079 found collector adoption/receipt-order defects at `e8a4de3`; producer
`982fe3c` fixes those, validates per-run provenance and adds 12 collector tests.
The full writer/calibration suite passes 149 tests with one optional skip, plus
12 JavaScript tests. This does not claim an independent review of the fixes.

Curated receipts are attached to the PL-1072 result comment. Raw run receipts
remain in the experiment's `native/dry-upland-north-america-attempt-1` directory.
No cutoff, probe, package, frozen model or physical writer changed after observing
this outcome.

## Native collection: four-square dry-upland tranche

The next four squares completed on November 20 through the same clean native
harness `6949182`, in frozen panel order. All are empty-map runs over 60 game
minutes, not first-hour city-building trials. Flood area uses the original
0.05 km² gate. Required-water counts below are identical at endpoint and for
points wet throughout all 13 sampled epochs.

| Intended dry-upland square | Game minutes | Worst flood area, km² | Flood gate | Required water |
|---|---:|---:|---|---|
| South America | 60.035559 | 0.0850 | fail | 1/1, pass |
| Europe | 60.052225 | 0.1132 | fail | 1/1, pass |
| Africa | 60.061670 | 0.0000 | pass | 1635/1971, fail |
| Asia | 60.037503 | 0.2452 | fail | 50/50, pass |

| Square | Initialized wet monitored points | Exactly dry at end | No wet native neighbor within 64 m at end | Grid area dried / newly wet, km² |
|---|---:|---:|---:|---:|
| South America | 790 | 180 | 55 | 0.28 / 0.49 |
| Europe | 697 | 300 | 228 | 0.59 / 0.53 |
| Africa | 7069 | 1936 | 841 | 2.39 / 0.05 |
| Asia | 1255 | 279 | 0 | 0.57 / 0.42 |

These are per-square observations, not interim model accuracy or drying labels.
Exact thinning is not isolated loss; the full frozen outcome definition also
uses required-water endpoint/throughout evidence. No nearby endpoint values are
unknown in these four records. Grid changes use the separate 0.1 m wet threshold,
not the flood gate's deeper-than-0.5 m and 128 m exclusion definition.

All 280 staged files and all 21 writer files revalidate. Each native package,
initial grid, probe file, mask, reference and harness identity matches its frozen
binding; original report/verdict hashes still match the collection ledger.
Fresh carbon-idle and offline guards passed, all owned teardown receipts are
empty, and recorded game/session/waiter PIDs have exited. No failed water run was
retried to improve its result. The four original overall verdicts remain fail:
unreviewed startup images plus the native water failures shown above.

Actual opening, Areas and final overview PNGs were inspected for all four.
Hash-bound producer startup-view sidecars pass without rewriting the original
verdicts. Europe's close opening shows uninformative grassy terrain rather than
the entrance; the Areas view reveals the road approach and reservoir. This is
recorded image/state QA, not ideal composition or human playability acceptance.
Curated receipts and actual images are attached to the PL-1072 tranche result.

No physical writer, package, probe, model, cutoff or game gate changed. The
input-only rejection of the all-warn drying rule and the lack of a contrasting
1.5 m versus 3 m flood example remain unchanged. A safer cleared class has not
been demonstrated. Full cohort scoring waits for the remaining 23 exports;
both original capture failures stay missing, not safe negatives.

## Remaining work and release hold

At preparation closeout no new native game or holdout score existed. PL-1066
subsequently resolved the offline-evidence interpretation and explicitly released
the install on November 20 at 13:30 UTC. Collection resumes through its pinned
guarded harness, without changing the frozen writer or repeating the rejected
client-only experiment. The PL-912 exporter release hold remains justified;
there is no safe-square class to ship without a caveat.
