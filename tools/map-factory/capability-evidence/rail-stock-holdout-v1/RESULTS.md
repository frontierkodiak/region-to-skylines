# Frozen stock rail validation

Both frozen rules match 40 successful and 8 failed literal requests on the six
supported selected packages. **The study does not prefer tangent over chord.**
Their predictions were identical before any new native query.

## Request-scoped result

| Frozen rule | TP | FP | TN | FN | Precision | Recall | Request coverage | Unknown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tangent:continuation:any_lane | 40 | 0 | 8 | 0 | 1.0 | 1.0 | 48/48 | 0 |
| chord:continuation:any_lane | 40 | 0 | 8 | 0 | 1.0 | 1.0 | 48/48 | 0 |

The all-complete intent-to-test and predeclared snapshot-matched tables have
the same 48 rows. No completed request is discarded for a graph mismatch.
`evaluation.json` contains both tables, every package and selection stratum,
precision, recall, coverage, abstentions, nulls, and raw request results.

This is a deterministic stock selection within the old catalog's supported
domain, not blind global accuracy or geographic prevalence. The eight failed
requests belong to one package and are not independent package-level votes.
Each failure labels only its exact request and protocol. None establishes
geographic absence, service, spawning, a product promise, or a junction law.

## Every selected package

| Package | Stratum | Requests | Success | Complete failure | Capture |
| --- | --- | ---: | ---: | ---: | --- |
| MM Weaving Waters | pairing difference | 8 | 8 | 0 | complete |
| PU Narrow Passage | pairing difference | 8 | 0 | 8 | complete |
| CCP Map 2 | same pairing | 8 | 8 | 0 | complete |
| CCP Map 3 | same pairing | 8 | 8 | 0 | complete |
| CCP Map 4 | same pairing | 8 | 8 | 0 | complete |
| CCP Map 5 | same pairing | 8 | 8 | 0 | complete |
| AP Noyou Port | unsupported | 0 | null | null | metadata complete |
| CCMP2 Boreal Map 1 | unsupported | 0 | null | null | metadata complete |
| CCMP2 Boreal Map 2 | unsupported | 0 | null | null | metadata complete |
| CCMP2 Desert Map 1 | unsupported | 0 | null | null | metadata complete |

The pairing-difference stratum has TP=8 and TN=8. The same-pairing stratum has
TP=32. Both have FP=FN=0. Unsupported cases have no selected requests and null
rates. The negative-only PU Narrow Passage package also has null precision
and recall. Package support is 6/10, separate from 48/48 request coverage.

Only two packages meet the pairing-difference criterion, not four. All six
supported packages have eight candidates, so none is unqueried. Candidate
requests for unsupported inputs remain unknown, not zero. No case is replaced.
All strata have zero discordant predictions and no power to choose a rule.

## Native facts and field audit

All consumed fields agree exactly for 1,277 Train segments across the six
supported packages at opening and post-batch. This includes export-derived
tangents, literal node/segment identities, geometry, model-used flag facts,
prefabs, and eligible lane definitions. All 48 pre/post-query Train graph
digests match their opening digest. These are observations at the recorded
capture points, not an assertion about every intervening runtime state.

The 40 successful paths contain 8,336 distinct-segment transition occurrences.
The predeclared junction-pair audit finds none that either rule rejects.
Occurrences are not extra independent trials. This does not reproduce every
native pathfinding choice or resolve the retained Pittsburgh counterexample.
The optional Pittsburgh diagnostic was not run.

The public runtime fields report `m_maxTurnAngle=45` and
`m_maxTurnAngleCos=0.7071067690849304` for seven observed Train prefabs.
The public-field lookup for `m_overrideDirectionLimit` is unavailable and
remains null. `public-prefab-facts.json` retains these facts without fitting a
new turn rule or assigning unproved semantics to them.

The four unsupported cases stay unsupported. Their opening/post audits retain
8, 6, 14, and 44 field or presence mismatches respectively, including missing
catalog facts. Those are coverage gaps, not additional scored failures.
No new native graph or prefab catalog is fed back into a prediction.

## Controls and runtime context

The unchanged Asanu control has eight successful boundary requests out of
eight. Hanami has eight successes and sixteen complete failures out of 24.
Both reject the invalid Train-to-Car diagnostic. Their 36 diagnostic requests
and 32 boundary requests are separate from the 48 holdout requests.

All twelve openings have fresh launch/opening/post-batch process identities,
executable and loaded-assembly hashes, the new harness DLL, complete scoped
file inventories, plugin state, and opening/request/post-batch bindings.
Every opening records empty game, Steam-instance, and unit cleanup lists.
`native-verification.json` independently checks the process, request,
timestamp, endpoint, cleanup, and confusion-count chain.

The captures retain the dynamic exclusion `Anonymously Hosted DynamicMethods
Assembly`. They also retain three post-load serialization errors naming
`ServicePointGroupPanel`, `HotelGroupPanel`, and `RaceGroupPanel`. Zero enabled
mods is recorded, but is not strict no-mods proof. File identity is not
in-memory code attestation. The results apply to this recorded runtime context.

Blade's existing GPU settings are unchanged. `resource-journal.json` records
each opening, sampled VRAM, power, temperature, wall time, and cleanup. The
observed power limit is 200 W, matching current fleet knowledge. Peak sampled
total/game VRAM is 10,821/2,846 MiB, power 127.87 W, and temperature 53 C.
Total VRAM includes other residents. These are not performance benchmarks.

## Freeze, retention, and verification

The pre-query code commit is `5414c1ba8b6c66e6df2c5035924d4785be48373d`.
The freeze is dated 2026-11-21 21:51:01 UTC, SHA-256
`20dfb33d863deb4fd13abcbeb952a59e139f93910216771c74fd21c069935a18`.
No frozen source, protocol, catalog, feature, request, or prediction changes
after new native labels. The new DLL is
`7185c630657cdf480c2ed62be3830bb545a8b45e34cedb455375fa8fffe46357`.

`raw-integrity.json` binds 136 retained raw files by original and compressed
SHA-256. The primary batch is `raw/attempt-2/`. The earlier pre-launch slot
denial remains under `raw/stock-1/`; it is neither a native failure nor a vote.
The pre-native report and evaluation remain byte-for-byte under `history/`.
The earlier input-only JSON comparison correction remains archived separately.

All eleven new contract tests and all 171 harness tests pass. The metadata DLL
build, full input-only replay, final source/artifact checks, Ruff, whitespace,
and independent native verification pass. No old scorer or outcome study is
rerun. Raw proprietary CRPs and compiled DLLs remain outside Git. No prepared
input/CPU lineage or activation candidate is fabricated for stock packages.

The draft PR targets internal `PL-1142-native-v2`. No old study, UI, writer,
default, gate, ledger, certificate, or golden changes. No public merge or
production promotion is performed. PL-1119 remains incomplete.
