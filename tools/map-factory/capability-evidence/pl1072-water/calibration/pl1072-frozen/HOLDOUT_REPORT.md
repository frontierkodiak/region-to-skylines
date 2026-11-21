# PL-1072 independent-geography water calibration

**Recommendation: keep exporter release held. No safe cleared class was established.**

The frozen study is complete, not a successful safety qualification. The candidate remains a comparator; the deployed-product screen is assessed separately. No threshold, place, package or probe was repaired against these outcomes.

## Coverage and definitions

30 fixed purposive squares: 28 complete empty-map native soaks of at least 60 game minutes; two original capture failures remain unknown.

- `lake-shore-south-america`: no buildable start tile.
- `low-coast-africa`: fitted-network-position validation failed.

Flood labels use the original no-flooding gate: more than 0.05 km² deeper than 0.5 m beyond frozen initial/mapped-water references and 128 m exclusions. Drying uses the frozen full `water_risk_corpus.native_outcome` definition, including initialized optional-water loss and required endpoint/throughout losses. Grid thinning, skipped required checks, input warnings and image appearance are not substituted for these labels.

## Full holdout metrics

Rates include exact two-sided 95% Clopper–Pearson intervals. TP/FP/TN/FN are square counts.

| Target | TP / FP / TN / FN | Precision [95% CI] | Recall [95% CI] | Specificity [95% CI] |
|---|---|---|---|---|
| flood | 1 / 4 / 18 / 5 | 1/5 = 20.0% [0.5%, 71.6%] | 1/6 = 16.7% [0.4%, 64.1%] | 18/22 = 81.8% [59.7%, 94.8%] |
| drying | 27 / 1 / 0 / 0 | 27/28 = 96.4% [81.7%, 99.9%] | 27/27 = 100.0% [87.2%, 100.0%] | 0/1 = 0.0% [0.0%, 97.5%] |

| Target | Always-warn precision / base target failure rate [95% CI] | Always-warn recall [95% CI] | Target-rule cleared risk [95% CI] |
|---|---|---|---|
| flood | 6/28 = 21.4% [8.3%, 41.0%] | 6/6 = 100.0% [54.1%, 100.0%] | 5/23 = 21.7% [7.5%, 43.7%] |
| drying | 27/28 = 96.4% [81.7%, 99.9%] | 27/27 = 100.0% [87.2%, 100.0%] | not estimable (n=0) |

Target-rule risk reductions below are descriptive arithmetic from those saved rates, not a new score or fit; relative reductions have no confidence interval.

- flood: absolute risk reduction -0.31 percentage points; relative risk 1.014; relative risk reduction -1.45%. Negative reduction means higher observed risk among target-rule clears.
- drying: absolute/relative risk reduction not estimable.

## Base versus cleared risk

| Screen | Base either-target failure risk [95% CI] | Cleared count | Cleared risk | Absolute / relative reduction |
|---|---|---:|---|---|
| Combined candidate rules | 28/28 = 100.0% [87.7%, 100.0%] | 0 | not estimable | not estimable / not estimable |
| Deployed product | 28/28 = 100.0% [87.7%, 100.0%] | 0 | not estimable | not estimable / not estimable |

Zero clearance is not zero risk or evidence of a safety improvement. Flood-only target-rule clearance is not combined or deployed-product clearance.

## Stratum and world-region counts

Each row gives scored n; TP/FP/TN/FN; native-positive count. Full per-group intervals remain in `holdout-score.json`.

### Intended water setting

| Group | Flood: n; TP/FP/TN/FN; positive | Drying: n; TP/FP/TN/FN; positive |
|---|---|---|
| dry_upland | 6; 0/0/3/3; 3 | 6; 5/1/0/0; 5 |
| lake_shore | 5; 1/0/4/0; 1 | 5; 5/0/0/0; 5 |
| low_coast | 5; 0/4/1/0; 0 | 5; 5/0/0/0; 5 |
| lowland_river | 6; 0/0/5/1; 1 | 6; 6/0/0/0; 6 |
| mountain_river | 6; 0/0/5/1; 1 | 6; 6/0/0/0; 6 |

### World region

| Group | Flood: n; TP/FP/TN/FN; positive | Drying: n; TP/FP/TN/FN; positive |
|---|---|---|
| africa | 4; 0/0/4/0; 0 | 4; 4/0/0/0; 4 |
| asia | 5; 0/1/2/2; 2 | 5; 4/1/0/0; 4 |
| europe | 5; 1/0/3/1; 2 | 5; 5/0/0/0; 5 |
| north_america | 5; 0/1/4/0; 0 | 5; 5/0/0/0; 5 |
| oceania | 5; 0/1/4/0; 0 | 5; 5/0/0/0; 5 |
| south_america | 4; 0/1/1/2; 2 | 4; 4/0/0/0; 4 |

## Errors and limits

- flood misses: dry-upland-south-america, dry-upland-europe, dry-upland-asia, mountain-river-asia, lowland-river-south-america.
- flood false alarms: low-coast-north-america, low-coast-south-america, low-coast-asia, low-coast-oceania.
- flood unknown squares: lake-shore-south-america, low-coast-africa.
- drying misses: none.
- drying false alarms: dry-upland-asia.
- drying unknown squares: lake-shore-south-america, low-coast-africa.

Drying flags all 28 exports and is identical to always-warn for any labels: reject it as a discriminator. Both combined/deployed checks clear none. The 3 m candidate and 1.5 m deployed flood flags agree on every export; this panel cannot justify promoting 3 m. The European intended low-coast square has no captured ocean, leaving four actual coastal-branch examples.

The panel is purposive, not a random global sample. Intervals are conditional panel summaries, not global prevalence or rare-failure guarantees. Sampling every five game minutes does not prove every-frame retention. Endpoint recovery does not rescue earlier sampled required-water losses.

### Original non-water failures

All original reports and overall verdicts remain immutable. Producer startup-image sidecars do not rewrite those verdicts or establish independent/human quality acceptance.

| Square | Original failures other than startup/water |
|---|---|
| lake-shore-north-america | ground_truth |
| lake-shore-africa | ground_truth |
| low-coast-north-america | no_terracing, ground_truth |
| low-coast-europe | ground_truth |
| low-coast-asia | no_terracing, ground_truth |

Original overall fail verdicts: 28/28. Water labels describe the observed exported packages, not a terrain-fidelity or playability certificate. Actual screenshots and raw measurements retain visible wet-looking starts, deck gaps and terrain mismatches without repair.

## Disposition

Reject both frozen predictors as qualified discriminators. The shared flood rule misses five of six native floods, while its target-rule clears have no observed risk reduction over the base rate. Drying exactly matches always-warn. These are failed qualifications, not evidence for a caveat-free release.

Keep the exporter release hold and current warning guard. Do not ship a caveat-free safe-square class from this study. Develop a general replacement on development data only; any predictor learned from these labels requires a new geography-disjoint holdout. No fit or threshold change was made from this panel.

**Human-only checks: not verified.** No human visual/playability acceptance, longer-term guarantee or production deployment is claimed.

## Provenance

- One-shot result SHA256: `b42412a2e6575a462bc831505a5ed199d3592849964db4b30b5428787fae424b`.
- Pre-score receipt SHA256: `4ad563b6cb57cd6c4ce649c491d9610561046e70bc7b5183f2756772fe3dfecf`.
- Study source at pre-score verification: `cc9d541604ef05ddf49d08f73d7819f5cf931075`.
- Pinned clean harness: `6949182ccf3f8bf066fd24372e1bcfc31c8512f1`.
- Panel SHA256: `37d88f277973a709a61b496925bb911255bbeb201e863f61629377ca172c014e`.
- Frozen model SHA256: `233534080d1f063fd96d5ca62167c3e3e2292503961184ed70f63a348a89e23d`.
- Staging SHA256: `5b8da959bf43d46ab08edddf9b866011f72ab2dfaf88f48cda9609ed8e9d723c`.
- Verified 280 staged files, 21 source-equivalent writer files and 28 native binding sets before scoring.
- Read-only post-score audit checked 28 receipt sets and 148 rate/interval records without prediction or label regeneration.

Captures ran at `99702f1`; source equivalence does not relabel them as later runs. All owned native work was collected and cleaned up before scoring. Curated evidence excludes proprietary binaries, decompiled source, saves and raw Steam/account logs.
