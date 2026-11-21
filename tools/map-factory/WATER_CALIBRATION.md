# Independent water-risk calibration

**Completed study, not a live runbook.** The one-shot result is saved in
`calibration/pl1072-frozen/holdout-score.json`; see its `HOLDOUT_REPORT.md`.
The commands below record the historical protocol at study source `cc9d541`.
Do not rerun the completed cohort or score it again. Post-score main integration
uses a separate versioned metadata layer; it does not relabel the historical
captures or games as runs on the later tree. A replacement needs a new holdout.

PL-1072 owns this experiment. Integration owner: the producing agent. Destination:
`frontierkodiak/region-to-skylines` main, after independent review. The exporter
release on PL-912 remains on hold. No candidate cutoff is promoted by this study's
preparation commit.

**Input-only audit: drying is rejected as a discriminator.** It flags all 28
exportable new squares, so it cannot beat always-warn for any future labels.
The current combined check clears none. The 3 m versus 1.5 m flood cutoff also
has no contrasting case here. See [preparation findings](WATER_CALIBRATION_FINDINGS.md).
Keep the frozen model as a comparator, not a release candidate. Native labels
can support flood evaluation and a later general drying replacement; that
replacement needs a new independent holdout.

## Fixed panel

`water-calibration-panel.json` fixes 30 non-overlapping, 17.28 km squares before
input capture or game results. `water_calibration_panel.py` reproduces it.

The rule crosses five intended water settings with six world regions. Each cell
has a written geographic anchor. Two SHA256-derived offsets move its centre by
up to 3 km east and north. Rotation is zero, horizontal scale is one, and height
uses the ordinary automatic fit. No anchors are the five fixture regions.

The settings are dry upland, mountain river, lowland river, lake shore, and low
coast. Dry uplands are intended drying negatives: inland relief without a major
river. This is an expectation, not a label. The writer may add its normal starter
reservoir. Every selected square stays in the panel, including unexpected
terrain, unmapped water, capture failures, or a failed native run. No replacement
square or per-square repair is allowed.

Thirty squares expose gross failures such as always warning, while covering
several water settings outside the five old regions. They cannot establish a
rare-failure guarantee. The panel is purposive, not a random sample of global
land or future user choices. Its base rate and intervals describe this panel.
Report results by stratum and world region as well as pooled.

## Freeze before outcomes

1. Correct the narrow-film measurement. Sea neighbours remain wet even though
   sea is excluded from inland totals. A regression test reproduces the old bug.
2. Re-measure only the frozen old corpus after verifying its package, input, and
   native-receipt hashes. Preserve all old labels and masks. The active warning
   contract is refreshed without changing physical packages or historical tests.
3. Fit the flood candidate on the old 50 full runs only. Search the written 36
   cutoff pairs, maximising equal-region specificity at at least 90% macro recall.
   Record leave-one-old-region-out diagnostics. The candidate selects 3 m coastal
   freeboard and 0.01 km² emitter exposure. This is retrospective tuning.
4. Keep the corrected drying rule as an unvalidated comparator. The old corpus
   has no drying negatives, so fitting specificity would be fictitious.
5. Commit `calibration/pl1072-frozen/model.json`, `freeze.json`, and the panel
   before capture. Bind each capture to their hashes. Do not change them after
   observing any new game outcome. The candidate is separate from the deployed
   1.5 m coastal warning threshold.

## Preparation without a game

All output belongs under `~/experiments/PL-1072-water-calibration/` on blade.

```sh
npm ci --ignore-scripts
node tools/map-factory/capture-water-panel.mjs \
  tools/map-factory/water-calibration-panel.json \
  tools/map-factory/calibration/pl1072-frozen \
  ~/experiments/PL-1072-water-calibration/captures
```

The capture uses the page/CLI input and writer functions, not another terrain
generator. It archives inputs, work files, exact package bytes, assessment, and
source hashes. It neither installs a map nor starts Steam. Successful captures
are preserved on rerun. Failed squares remain visible in the panel.

```sh
uv run --locked --project tools/map-factory python tools/map-factory/stage_water_panel.py \
  tools/map-factory/water-calibration-panel.json \
  tools/map-factory/calibration/pl1072-frozen \
  ~/experiments/PL-1072-water-calibration/captures \
  ~/experiments/PL-1072-water-calibration/staged
```

Stage probes from the ordinary hydrology samples plus geographic river probes.
Also monitor every initially wet node on a fixed 64 m lattice, including a
constructed reservoir, without choosing points from outcomes. Freeze the mapped
water mask before launch with the existing `soak.mapped_water_reference` helper.
Freeze package, initial-grid, probe, mask, model, and panel hashes before any game.
Keep all samples and the original harness verdict definitions.

## Native measurements and one-shot scoring

Only blade's disposable test install may run the games, and only after PL-1066
explicitly releases it. A free queue reading alone is not that release. Before
each launch check carbon for a running Cities process, respect reservations and
the harness queue, and use the existing foreground session lifecycle. Do not
alter Steam account configuration or proprietary installed code.

Run each map for at least 60 game minutes with the existing harness. Do not stop
on a water failure or repair the square. An infrastructure failure remains
unscored until a fresh attempt succeeds; preserve the failed attempt. Collect
cleanup receipts in the same foreground call. No game, waiter, browser, or server
may survive the turn.

For each prepared square, use its staged `.crp` and `probes.json` with:

```sh
uv run --locked --project tools/cs1-harness cs1-harness run \
  --map <staged-square.crp> --probes <staged-square/probes.json> \
  --game-minutes 60 --issue PL-1072 --no-live --no-record \
  --require-offline --wait-minutes 0 --retry-minutes 0 --out <native/square-slug>
```

The native phase uses a separate detached harness checkout at PL-1066's
`6949182ccf3f8bf066fd24372e1bcfc31c8512f1`. Its read-only offline guard accepts
the lead-approved combination of cached offline flags and failed
`login=false/offlineMode=true` syncs, while rejecting online state. Its `MAP_SOAK`,
flooding, required-point and throughout-water definitions are identical to this
study's original harness. Do not merge the other writer changes from that branch
into the frozen capture source.

`run_water_panel.py STAGING NATIVE HARNESS_DIR NATIVE_PLAN` automates this command
serially. The plan binds the immutable staging and harness revision. `--only SLUG`
can verify the first unit before the complete cohort; it does not remove the
other planned squares. Each fresh attempt has its own directory. Canonical
square paths are read-only aliases to collected complete attempts. Failed water
verdicts are retained as observations, not retried until they pass. Account and
lifecycle guard failures stop collection. Other failed attempts stay archived.
`--max-new N` bounds a foreground tranche without changing the panel. Existing
complete squares do not consume the limit. Arrange the next Multica run only
after the tranche returns and every owned child has ended. Never leave the
collector running when a turn exits, and score only after the whole panel has
been attempted.
The collector requires a non-error verdict and clean per-run harness identity;
it writes and flushes the collection receipt before creating a completed alias.
It accepts either a checkout root or its `tools/cs1-harness` project directory
and passes that project explicitly to uv.

An interrupted or guard-stopped attempt is not silently resumed. Verify that its
game and waiter have ended, inspect the teardown receipt, and classify the cause.
Preserve a failed attempt under `native-classified/` with its old/new paths and
reason in a classification JSON record before retrying the square. Do not remove
or overwrite its files, and never classify an active attempt. A complete attempt
with matching report/verdict hashes is retained, not rerun to improve its verdict.

Do not add `--notify` or `--wake`; the issue gets one consolidated result. A
nonzero native exit needs diagnosis before retry, not an ignored loop exit.
If all attempts fail, write `native/<slug>/failure.json` with the attempt paths
and reason. The scorer requires every planned square to have a capture, a capture
failure, a native report, or an explicit native failure. Short runs remain
unscored. Do not replace them with passing labels.

Score the frozen candidate once, after all planned runs have been attempted.
Flooding is the existing `no_flooding` failure at 0.05 km². Drying uses
`water_risk_corpus.native_outcome`, including initialized optional-water loss and
required-water endpoint/throughout loss. Exact-point thinning is separate.
Missing observations and incomplete runs remain unknown, never safe negatives.
Water that was absent initially cannot supply a drying-negative label.

Report confusion counts, precision, recall, specificity, and exact 95% binomial
intervals for each target. Compare with always-warn precision and recall on the
same scored squares. Report cleared-square count, base and cleared failure rates,
their intervals, and absolute/relative risk reduction. Report both target-rule
clearance and the actual app's stricter clearance, including out-of-range inputs
and content notes. No cleared squares means no demonstrated safety benefit.

```sh
uv run --locked --project tools/map-factory python tools/map-factory/score_water_panel.py \
  ~/experiments/PL-1072-water-calibration/staged \
  ~/experiments/PL-1072-water-calibration/native \
  ~/experiments/PL-1072-water-calibration/staged/holdout-score.json \
  tools/map-factory/calibration/pl1072-frozen \
  tools/map-factory/water-calibration-panel.json
```

The result path is fixed. The scorer refuses a second score, verifies frozen
inputs and native references, and replays the candidate predictions without
refitting. Candidate rule clearance and deployed-product clearance are separate.
The deployed-product result uses the captured 1.5 m model, not an unshipped 3 m
candidate described as the current app.

A predictor that matches always-warn or provides no demonstrated safer cleared
set is not accepted as a discriminator. Drop or rework it in a later development
round with a **new** holdout, never tune it on these 30 squares and call the result
independent. The final recommendation on PL-912 must distinguish this evidence
from a guarantee, and list human-only checks as not verified.
