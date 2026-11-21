# Native collection deferred

The off-game study is frozen and replayed. **No new native query has run.**
All 48 holdout request labels remain Unknown. Precision and recall are null.
No result prefers either continuation rule.

The first stock-1 acquisition was denied on 2026-11-21 at 21:54:06 UTC.
PL-1074 acquired the shared slot between the readiness check and acquisition.
Its Charleston opening had about 18.5 minutes remaining at the next check.
The denial is retained in `raw/stock-1/observation.json.gz` with its driver log
and empty GPU sample. The collector and sampler both exited. No owned game,
Steam, display, or bus was started. No foreign process was stopped.

This is a scheduling denial, not an observed control failure or a no-path
label. There is no launch or cleanup identity to qualify. The unchanged control
requests still need a fresh opening. Any later attempt must retain this denial
and use a separate output directory. Do not retry a native control result into
a pass.

## Frozen selection

| Group | Packages | Requests | Complete observations |
| --- | ---: | ---: | ---: |
| Different junction pairing | 2 | 16 | 0 |
| Same junction pairing | 4 | 32 | 0 |
| Unsupported coverage cases | 4 | 0 | 0 |

Both rules give identical predictions for all 48 requests.
`selection-power.json` records zero rule-comparison power for every stratum.
The `zero_power` field inside the original freeze means an empty package
selection, not prediction disagreement. No stratum is empty, but none has a
discordant request.

`evaluation.json` retains every selected package and every missing request.
The two fixed rules each have TP=0, FP=0, TN=0, FN=0, and Unknown=48.
Those zeros are missing evidence, not measured accuracy. The snapshot-matched
subset is empty. Native fields, runtime facts, graph evolution, path
counterexamples, and cleanup qualification remain unverified.

## Verified off-game

- Exact accepted source and both named historical source commits are available.
- The inventory binds all 105 installed CRPs and excludes CO plus every old
  rail fitting/control package hash. The old catalog union has eleven packages.
- The ten selected packages and two controls have preserved CRP copies outside
  Git. Unsupported fields remain null or named missing inputs.
- Full input-only replay reproduces the inventory, features, selection, and all
  frozen predictions. No old scorer or outcome study was rerun.
- All eleven new contract tests and all 171 harness tests pass. Ruff and
  whitespace checks pass. The public-runtime metadata DLL compiles.
- The draft PR targets internal `PL-1142-native-v2`. The remote pre-query
  commit is `5414c1ba8b6c66e6df2c5035924d4785be48373d`.

The experiment has not yet met PL-1239's native acceptance criteria. PL-1119
also remains incomplete. No product rule, geographic absence, service, or
promise claim follows from this freeze.
