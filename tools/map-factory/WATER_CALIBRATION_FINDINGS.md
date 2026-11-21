# Water-calibration findings: no demonstrated safe-square class

**Complete: 28 full native runs, two original capture failures retained unknown.**
The frozen one-shot score ran once on November 21. Both predictors fail
qualification; exporter release stays held. Full metrics, exact intervals,
always-warn comparisons and group counts are in
[the final report](calibration/pl1072-frozen/HOLDOUT_REPORT.md) and its
[verbatim score](calibration/pl1072-frozen/holdout-score.json).

| Target | TP / FP / TN / FN | Precision, exact 95% CI | Recall, exact 95% CI |
|---|---|---|---|
| Flood | 1 / 4 / 18 / 5 | 20.0% [0.5%, 71.6%] | 16.7% [0.4%, 64.1%] |
| Drying | 27 / 1 / 0 / 0 | 96.4% [81.7%, 99.9%] | 100% [87.2%, 100%] |

Flood-only clears fail at 5/23, 21.7% [7.5%, 43.7%], versus the base
6/28, 21.4% [8.3%, 41.0%]: no demonstrated risk reduction. Drying is exactly
always-warn, with specificity 0/1. The one drying-negative square, dry-upland
Asia, floods; it is not a both-target safe case. Every scored package fails at
least one frozen water target. Both combined candidate and deployed-product
clearance are empty; cleared risk and absolute/relative reductions are not
estimable. These are target outcomes, not a playability judgment.

**Reject both frozen predictors as qualified discriminators.** Keep the warning
guard and release hold; develop a general replacement with a new geography-
disjoint holdout. Do not promote the 3 m cutoff: its flags still agree with
1.5 m on all exports. No fit, threshold, probe, package or gate changed against
the new labels. Human-only checks remain **not verified**.

The result SHA256 is
`b42412a2e6575a462bc831505a5ed199d3592849964db4b30b5428787fae424b`.
Pre-score verification at `cc9d541` checked all 280 staged files, 21
source-equivalent writer files, 28 native binding sets and 1,260 absent recorded
PID numbers. The post-score audit checked 148 saved rate/interval records and
all native receipt hashes without invoking prediction, native outcomes or the
scorer again. The published score is a byte-identical copy of the fixed-path
one-shot output, not a second score.

PL-1075 independently reviewed preparation at `bb2a1ec` against `4a4ec21`.
Its regression, old-corpus refresh, frozen fit, and synthetic scoring attacks
reproduced. There was no blocking preparation defect. That preparation review
predates actual native scoring. The later producer delta fixes the declined-assessment crash,
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

## Native collection: Oceania and three mountain-river squares

The next frozen tranche completed on November 20, still using clean native
harness `6949182`. All four exceeded 60 game minutes. Required-water counts
below match at endpoint and for points wet throughout all 13 sampled epochs;
the unchanged gate requires at least 95%.

| Frozen square | Game minutes | Worst flood area, km² | Flood gate | Required water |
|---|---:|---:|---|---|
| Dry upland, Oceania | 60.014448 | 0.0000 | pass | 136/136, pass |
| Mountain river, North America | 60.141670 | 0.0108 | pass | 1/1, pass |
| Mountain river, South America | 60.146670 | 0.0000 | pass | 368/407, fail |
| Mountain river, Europe | 60.060003 | 0.0451 | pass | 833/842, pass |

| Square | Initialized wet monitored points | Exactly dry at end | No wet native neighbor within 64 m at end | Grid area dried / newly wet, km² |
|---|---:|---:|---:|---:|
| Oceania upland | 1947 | 395 | 164 | 0.87 / 0.00 |
| North American mountain river | 1523 | 262 | 141 | 0.55 / 0.38 |
| South American mountain river | 1973 | 344 | 141 | 0.50 / 0.02 |
| European mountain river | 2413 | 548 | 323 | 0.51 / 0.42 |

No nearby endpoint readings are unknown. These raw observations do not substitute
for the full frozen drying definition, and no interim model score was computed.
Passing the listed gates is not a safe-square or human-playability claim. The
South American required-water failure is retained, not repaired or retried.

All 280 staged files, 21 writer files and nine completed native binding sets
revalidate. Every original report/verdict hash still matches its collection
receipt. All four fresh carbon/offline guards passed and teardown receipts are
empty; recorded owned session and waiter PIDs have exited. The foreground
collector returned after the full four-square tranche.

Actual opening, Areas and t060 PNGs were inspected for all four. Producer
hash-bound startup-view sidecars pass, separately from the original verdicts.
Some close opening views poorly frame the approach; that composition is
documented without changing it. The three original overall failures for startup
unreviewed alone and the South American failure for startup plus required-water
gates remain unchanged. No human or independent visual acceptance is claimed.

Nineteen exportable squares remain, alongside the two original capture failures.
No physical writer, package, point, mask, model, cutoff or game gate changed;
the all-warn drying rejection and non-identifiable flood cutoff comparison still
hold. The full one-shot score and PL-912 recommendation remain pending.

## Native collection: three mountain rivers and the first lowland river

The fourth tranche completed on November 20 through unchanged, clean harness
`6949182`. Each square completed more than 60 game minutes. The collector yielded
the shared install between squares through the FIFO queue. No failed water
verdict was repaired or retried.

| Frozen square | Game minutes | Worst flood area, km² | Flood gate | Required water |
|---|---:|---:|---|---|
| Mountain river, Africa | 60.149170 | 0.0000 | pass | 1660/1663, pass |
| Mountain river, Asia | 60.101670 | 0.1526 | fail | 1/1, pass |
| Mountain river, Oceania | 60.093336 | 0.0000 | pass | 227/227, pass |
| Lowland river, North America | 60.037781 | 0.0000 | pass | 843/843, pass |

Required-water counts match at endpoint and throughout all 13 sampled epochs;
the unchanged gate requires 95%. The flood limit is still 0.05 km² beyond the
frozen initial/mapped-water exclusion, deeper than 0.5 m and beyond 128 m.

| Square | Initialized wet monitored points | Exactly dry at end | No wet native neighbor within 64 m at end | Grid area dried / newly wet, km² |
|---|---:|---:|---:|---:|
| African mountain river | 4664 | 1083 | 59 | 1.14 / 0.02 |
| Asian mountain river | 2580 | 1263 | 658 | 2.16 / 0.38 |
| Oceanian mountain river | 5552 | 1224 | 651 | 2.15 / 0.41 |
| North American lowland river | 6154 | 497 | 361 | 1.65 / 0.09 |

Nearby endpoint readings are known for all monitored points. Grid changes use
the separate 0.1 m threshold. These are raw measurements, not interim drying
labels, model accuracy or evidence of a safe cleared class.

All 280 staged files, 21 writer files and thirteen native binding sets revalidate.
Original report/verdict hashes match the collection ledger. Fresh carbon/offline
guards passed, owned cleanup is empty, and all 580 recorded session/waiter PIDs
checked after collection are absent. The foreground collector exited zero after
all four results and teardown; no owned child remains active.

Actual opening, Areas and t060 PNGs were inspected for all four. Separate
hash-bound producer startup-view assessments pass; the original overall verdicts
remain fail: three solely startup-unreviewed, Asia also for flooding. Asia's close
opening poorly frames the approach. Oceania's final overview shows elevated rail
with angular supports across ridged terrain. These observations are retained,
not repaired or presented as geometry quality or human playability acceptance.

Fifteen exports remain, plus both original missing captures. Frozen inputs,
physical writer, models and native gates are unchanged. The all-warn drying
rejection, zero combined/deployed clearance and non-identifiable flood-cutoff
comparison remain. Full scoring and the PL-912 recommendation are still pending.

## Native collection: four more lowland rivers

The fifth tranche completed on November 20 through unchanged, clean harness
`6949182`. All four exceeded 60 game minutes in frozen order. The collector
respected FIFO handoffs with PL-1078 and PL-1121. Every water failure remains
retained once, without repair or a retry to improve its verdict.

| Lowland river | Game minutes | Worst sampled flood, km² | Flood gate | Required wet at end | Required wet at all 13 samples |
|---|---:|---:|---|---|---|
| South America | 60.136670 | 0.1152 | fail | 1/1, pass | 1/1, pass |
| Europe | 60.068892 | 0.0000 | pass | 6/6, pass | 6/6, pass |
| Africa | 60.015281 | 0.0000 | pass | 1059/1215, fail | 828/1215, fail |
| Asia | 60.140836 | 0.0338 | pass | 844/1410, fail | 791/1410, fail |

The existing flood limit remains 0.05 km²; required-water retention is 95%.
Endpoint recovery does not erase an earlier sampled loss. Africa and Asia have
different endpoint and throughout-sample counts, so neither endpoint snapshot
can substitute for the all-sample result. This is sampled evidence, not an
every-frame guarantee.

| Square | Initialized wet monitored points | Exactly dry at end | No wet native neighbor within 64 m at end | Grid area dried / newly wet, km² |
|---|---:|---:|---:|---:|
| South American lowland river | 4123 | 261 | 125 | 0.50 / 24.61 |
| European lowland river | 4164 | 776 | 506 | 1.29 / 0.09 |
| African lowland river | 4420 | 982 | 555 | 1.75 / 8.47 |
| Asian lowland river | 8891 | 2657 | 1693 | 5.39 / 5.31 |

No nearby endpoint readings are unknown. Grid changes use the separate 0.1 m
threshold, not the flood gate's depth and reference exclusions. South America's
24.61 km² newly-wet grid area is not 24.61 km² of flood-gate failure. These raw
observations do not replace the full frozen drying definition; no interim labels
or model accuracy were computed.

All 280 staged files, 21 writer files and seventeen completed native binding
sets revalidate. Original report/verdict hashes match the collection ledger.
Fresh carbon and read-only offline guards passed; each owned cleanup is empty.
All 760 recorded session/waiter PIDs checked after collection are absent. The
foreground collector exited zero after all four results and teardown.

All twelve actual opening/Areas/t060 PNGs were inspected. Hash-bound producer
startup-view reviews pass in separate sidecars; original overall failures remain
unchanged: South America also fails flooding, Africa and Asia fail both required
water gates, and Europe fails solely for startup-unreviewed. Europe's and Africa's
close views poorly frame the road approach. This is image/state QA, not
water-safety, road-usability, human or independent acceptance.

Eleven exports remain, plus the two original missing captures. Frozen panel,
model, packages, probes, physical writer and native gates are unchanged. Drying
still equals always-warn, combined/deployed clearance is empty and the two flood
cutoffs have no contrasting case. Full scoring and the PL-912 recommendation
remain pending; exporter release is still held.

## Native collection: final lowland river and three lakes

The sixth tranche completed on November 21 UTC through unchanged, clean harness
`6949182`. All four exceeded 60 game minutes. The collector respected FIFO with
PL-1078, PL-1121 and PL-1142; no water failure was repaired or retried.

| Frozen square | Game minutes | Worst sampled flood, km² | Flood gate | Required wet at end | Required wet at all 13 samples |
|---|---:|---:|---|---|---|
| Lowland river, Oceania | 60.028892 | 0.0000 | pass | 1238/1357, fail | 1237/1357, fail |
| Lake shore, North America | 60.092225 | 0.0000 | pass | 251/251, pass | 251/251, pass |
| Lake shore, Europe | 60.085559 | 0.0627 | fail | 911/918, pass | 911/918, pass |
| Lake shore, Africa | 60.134448 | 0.0177 | pass | 443/448, pass | 443/448, pass |

The flood limit remains 0.05 km²; required-water retention remains 95%.
Oceania's endpoint and throughout counts differ, and endpoint recovery does not
erase earlier sampled loss. These are sampled observations, not every-frame
guarantees or interim model labels.

| Square | Initialized wet monitored points | Exactly dry at end | No wet native neighbor within 64 m at end | Grid area dried / newly wet, km² |
|---|---:|---:|---:|---:|
| Oceanian lowland river | 3535 | 1463 | 1046 | 2.27 / 0.01 |
| North American lake shore | 6575 | 1086 | 693 | 2.11 / 7.18 |
| European lake shore | 5809 | 1029 | 319 | 1.17 / 11.91 |
| African lake shore | 1202 | 282 | 140 | 0.42 / 11.77 |

No nearby endpoint readings are unknown. Grid changes use the separate 0.1 m
threshold, not the flood gate's deeper/masked measurement. The full frozen
drying definition, not these endpoint counts alone, supplies eventual labels.

The North American and African lakes also fail the unchanged terrain
ground-truth gate. North America's as-is correlation is 0.9997, but its best
alternative is 0.9751: separation 0.0246 is below the required 0.15. Africa's
as-is correlation is 0.8565, below 0.9; its highest DEM landmark reconstructs
78.2 m lower than the source. These non-water failures remain in the original
verdicts and curated evidence. Exact package/input/source bindings still match;
no gate was waived or square relabelled to repair these results.

All twelve actual opening/Areas/t060 PNGs were inspected. Separate hash-bound
producer startup-view reviews pass without changing the original overall
failures: Oceania also fails required water, Europe flooding, and both other
lakes ground truth. North America's opening shows fragmented-looking road
decks/support pieces. Europe's close view poorly frames the approach; Africa's
close/final views are dim and hazy, and the close view shows mainly trees.
These are retained image/state observations, not geometry quality, road
usability, human or independent acceptance.

All 280 staged files, 21 writer files and twenty-one native binding sets
revalidate. Every original report/verdict hash matches the collection ledger;
all sessions match the pinned mod hash. Fresh carbon/read-only offline guards
passed and owned cleanup is empty. The foreground collector exited zero after
all four results and teardown. Of 940 recorded session/waiter PID numbers, 939
are absent; one historical bwrap PID was reused by an unrelated root kernel
worker. The CPU-only verifier records positive kernel-thread/workqueue identity
and rejects live or unknown userspace identities; it does not waive an owned
process or change the native lifecycle guard. No process was killed for this
diagnosis. No owned child remains active.

Seven exports remain, plus both original capture failures. Frozen inputs,
physical writer, models and native gates are unchanged. Drying remains
always-warn, combined/deployed clearance is empty and the flood cutoffs have no
contrasting case. Full scoring and the PL-912 recommendation remain pending;
exporter release is still held.

## Native collection: final two lakes and first two coasts

The seventh tranche completed on November 21 UTC through unchanged, clean
harness `6949182`. All four exceeded 60 game minutes, with FIFO handoffs to
PL-1078 and PL-1142. No square was repaired or complete water failure retried.

| Frozen square | Game minutes | Worst sampled flood, km² | Flood gate | Required wet at end | Required wet at all 13 samples |
|---|---:|---:|---|---|---|
| Lake shore, Asia | 60.050836 | 0.0000 | pass | 381/381, pass | 381/381, pass |
| Lake shore, Oceania | 60.018892 | 0.0394 | pass | 200/200, pass | 200/200, pass |
| Low coast, North America | 60.097781 | 0.0079 | pass | skipped: no required cohort | skipped: no required cohort |
| Low coast, South America | 60.122503 | 0.0000 | pass | 135/230, fail | 135/230, fail |

The unchanged flood limit is 0.05 km²; required-water retention is 95%.
North America's null/skipped required-water checks are not 0/0 passes or safe
negatives. South America's endpoint and all-sample losses remain failures.
These are sampled measurements, not every-frame guarantees or interim labels.

| Square | Initialized wet monitored points | Exactly dry at end | No wet native neighbor within 64 m at end | Grid area dried / newly wet, km² |
|---|---:|---:|---:|---:|
| Asian lake shore | 1839 | 294 | 11 | 0.60 / 0.02 |
| Oceanian lake shore | 1411 | 461 | 230 | 0.63 / 0.40 |
| North American low coast | 57562 | 485 | 424 | 1.80 / 0.00 |
| South American low coast | 24950 | 1235 | 1134 | 2.17 / 0.01 |

No nearby endpoint readings are unknown. Grid deltas use the separate 0.1 m
threshold. They and the image appearance do not replace the deeper/masked flood
gate or the full frozen drying outcome. No subset score was computed.

North America's original verdict also fails terracing (metric 0.4477 versus
0.08) and terrain ground truth (as-is correlation 0.5265 versus 0.9; highest DEM
landmark reconstructs 32.6 m low). The original values and failures are retained
in curated evidence. Exact package/input/probe/reference/source bindings match;
no quality gate was waived or square relabelled to repair the result.

All twelve actual opening/Areas/t060 PNGs were inspected. Separate hash-bound
producer startup-view reviews pass without rewriting original overall failures:
both lakes fail solely for startup-unreviewed, North America also for terracing
and ground truth, South America also for both required-water gates. Asia's views
are dim/hazy with angular terrain/rail-support features; Oceania's opening has
a road-deck gap. North America's final start area looks wet/submerged despite
the passing frozen flood gate; this is not dry-start acceptance or an override
of that gate. South America's final overview poorly frames the road. All are
retained without repair, geometry-quality, water-safety, human or independent
acceptance. A producer image/state review is not a playability pass.

All 280 staged files, 21 writer files and twenty-five completed native binding
sets revalidate. Original report/verdict hashes match the collection ledger;
all twenty-five sessions retain the pinned mod hash. Fresh carbon/read-only
offline guards passed and owned cleanup is empty. All 1,120 recorded session/
waiter PID numbers are now absent, including the formerly reused kernel-worker
number. Collector session 84522 exited zero and its final result was collected.
All four games needed normal quit-grace termination, not spontaneous-crash
recovery. No native lifecycle guard changed.

The CPU-only display helper now retains null/skipped water checks instead of
crashing on them; the unchanged frozen outcome function already handles nulls.
The curator retains non-water failures and persists verified delivery ZIPs under
the experiment output. Neither change alters native observations or labels.

Only the European, Asian and Oceanian low coasts remain, plus both original
capture failures. Frozen inputs, physical writer, models and native gates are
unchanged. Drying remains always-warn; combined/deployed clearance is empty and
the flood cutoffs have no contrasting case. Full one-shot scoring and the
PL-912 recommendation remain pending; exporter release stays held.

## Final native collection: last three coasts

Europe, Asia and Oceania completed in frozen order, taking coverage to 28/28
exports. All three have empty cleanup; collector exec14803 exited zero and was
collected. Both original capture failures remain missing, not native negatives.

| Low coast | Game minutes | Sampled flood km² | Required wet at end | Required wet at all 13 samples |
|---|---:|---:|---|---|
| Europe | 60.034448 | .0000, pass | 836/836, pass | 836/836, pass |
| Asia | 60.067781 | .0000, pass | 733/733, pass | 733/733, pass |
| Oceania | 60.108059 | .0003, pass | 987/1149, fail | 978/1149, fail |

Oceania's endpoint recovery does not rescue its earlier sampled losses.
Europe also fails DEM correlation (.8175 versus .9); Asia fails correlation
(.8191 versus .9) and terracing (.297 versus .08). All original failures remain
unchanged. Initialized/exact-dry/isolated-dry endpoint counts are 8838/472/319,
44808/660/596 and 26098/1666/979 respectively, with no unknown nearby endpoints.
Grid dried/newly-wet areas at .1 m are .79/9.15, 2.43/.02 and 3.73/.08 km²;
these are not the deeper, masked flood-gate areas.

All nine actual opening/Areas/t060 PNGs were inspected. Europe shows branching
water and sandy banks; Asia's opening does not frame a road approach, and its
final view shows a long narrow crossing. Oceania's final overview poorly frames
the road. Separate producer startup-view sidecars do not establish geometry,
terrain-fidelity, playability, independent or human acceptance. All twenty-eight
original overall verdicts remain fail. No square was repaired or rerun to pass.

All twenty-eight mod receipts match the pinned hash. Fresh launch carbon checks
and continuous read-only offline guards passed. Europe game1789310 and Oceania
game953568 needed normal quit-grace termination, not spontaneous-crash recovery;
Asia has no such forced-termination record. All owned games, Steam clients,
displays, buses, collectors and waiters ended before scoring. The local verifier
now retains its explicit waiter PID list automatically; no native guard changed.

The pre-score curator and verifier were not rerun after scoring. Their receipts
are historical pre-score evidence, while the final report and saved score are
the completed study result. VRAM increments remain baseline-subtracted estimates,
not sampled or causal game peaks.

## Review and release hold

At preparation closeout no new native game or holdout score existed. PL-1066
subsequently resolved the offline-evidence interpretation and explicitly released
the install on November 20 at 13:30 UTC. All 28 exportable cases have now completed
through its pinned guarded harness, without changing the frozen writer or
repeating the rejected client-only experiment. The study is delivered for normal
PR review and human acceptance, not exporter-release approval. The PL-912 release
hold remains justified; no safe-square class was established.
