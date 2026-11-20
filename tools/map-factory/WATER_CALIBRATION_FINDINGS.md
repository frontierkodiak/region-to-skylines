# Preparation findings: no demonstrated safe-square class

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

## Remaining blocker

No new native game or holdout score exists. PL-1066 is blocked on usable cached
offline Steam and has not released the test install. Its failed client-only
check is not repeated here. After that resolution and release, collect the
frozen panel's labels with the existing harness. The PL-912 exporter release
hold remains justified; there is no safe-square class to ship without a caveat.
