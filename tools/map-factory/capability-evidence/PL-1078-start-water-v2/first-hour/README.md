# Frozen-player comparison

The checks are advisory: **no physical exporter improvement is demonstrated**. Both arms use the same maps, inputs, probes, qualified player and merged-PR58 judge. Every selected square and failure remains.

| Cohort / verdict | Before | Fresh repeat |
|---|---:|---:|
| Original eight, first hour | 3/8 | 3/8 |
| All eleven, first hour | 4/11 | 3/11 |
| All eleven, strict whole-map verdict | 3/11 | 2/11 |

Both stock controls passed the unchanged first-hour verdict with the final 4a4 player. The original eight were collected and frozen before any capability implementation. Historical 1/8 is an unqualified-player result, not the exporter baseline.

| Square | First hour before / repeat | Strict before / repeat | Retained finding |
|---|---|---|---|
| asheville | pass / pass | pass / pass | Completed full hour |
| innsbruck | pass / pass | pass / pass | Completed full hour |
| rio | fail / fail | fail / fail | System.Exception: no dry start-tile grid and hookup that pass native road placement checks |
| pittsburgh | fail / fail | fail / fail | Cs1Harness.ScenarioOps+PlacementRejected: Basic Road (-579.9, 60.0, 117.7) -> (-539.5, 68.2, 122.3) (elevation -6.834091 -> 0): TooShort, SlopeTooSteep |
| charleston | pass / pass | fail / fail | ground_truth |
| grand-canyon | fail / fail | fail / fail | System.Exception: no road hookup node in the start tile; map needs an accessible highway connection |
| hong-kong | fail / fail | fail / fail | System.Exception: no dry start-tile grid and hookup that pass native road placement checks |
| yosemite | fail / fail | fail / fail | System.Exception: no road hookup node in the start tile; map needs an accessible highway connection |
| grand-canyon-northeast | pass / fail | pass / fail | population_growth |
| rio-northeast | fail / fail | fail / fail | System.Exception: no road hookup node in the start tile; map needs an accessible highway connection |
| hong-kong-northeast | fail / fail | fail / fail | Cs1Harness.ScenarioOps+PlacementRejected: Basic Road (-2367.6, 115.8, 15.4) -> (-2317.8, 119.2, 98.1) (elevation 0 -> 0) [segment 831 HighwayRamp Created, Original, End; segment 867 Highway Created, Original; segment 868 Highway Created, Original; segment 872 Highway Created, Original; segment 873 Highway Created, Original]: ObjectCollision |

Grand Canyon northeast is the only first-hour pass/fail change. The repeat reached 385 residents (peak 540), but qualifying growth was first observed at minute 6.038; PR58 requires at least 50 new residents by minute 5, retained at the end. The full 60.0222-minute attempt is a failure, not retried or relabelled. Its before attempt passed. Identical treatment bytes prevent attributing this difference to a physical exporter change.

Charleston passes the first-hour check in both arms but fails independent DEM ground truth in both. Garbage, pollution, worker and other native warnings remain in the raw scenario and timeline evidence. Surface-water component results are separate: the player uses groundwater.

All 24 control/before/repeat cleanup receipts are empty. Actual available map-panel and startup PNGs were viewed and hash-reviewed. Seven newer normal runs retain pre-visual-review verdicts as well as final verdicts; the three earlier original-eight normal runs retain final reviewed verdicts only. Construction errors were not rejudged. No verdict threshold, player strategy or holdout model was changed.

## Evidence

`comparison.json` is the unchanged reporter output; `cases.csv` is a readable projection. `evidence-index.json` binds the three proof bundles and their full per-file manifests. The bundles are for attachment to the owning Multica issue and include lossless recovered reports/scenarios/timelines, verdicts, actual PNGs/reviews, telemetry and selected receipts. Full Steam/audio/launch logs are excluded. Whole-card telemetry is not game-only peak memory.

All 24 unchanged raw verdicts are also published under `verdicts/`.
`post-run-identity.json` audits their map/mod/query hashes, empty cleanup,
fresh carbon/offline guards and byte-identical merged-PR58 judge files.
`pre-rule-original-eight.json` is the exact earlier freeze, not a rebuilt baseline.
The audit is not launch-bound engine identity qualification or a runtime promise.

The capability study remains start fitting 2/3, water fitting 3/3, water regional holdout 1/2. These are positive-witness agreements, not first-hour scores, overall/global accuracy or runtime promises. Keep the two retained false positives and all unknowns.
