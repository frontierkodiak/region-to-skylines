# Frozen stock rail holdout

PL-1239 tests the fixed tangent continuation rule against its chord reference.
The source is `49cf49516f4aa8b24a154d9923c1a6fd149bf1a3`.
The accepted query and native sources remain unchanged.

## Selection before native outcomes

The installed Maps directory contains 105 CRPs. Excluding blank CO and the two
previous stock controls leaves 102 packages. Every old rail selection uses the
same eleven package hashes recorded in the accepted `packages.json`.

| Stratum | Available | Selected | Requests |
| --- | ---: | ---: | ---: |
| Different chord and tangent pairing, distinct-edge request | 2 | 2 | 16 |
| Same pairing, distinct-edge request | 33 | 4 | 32 |
| Unsupported or no distinct-edge pair | 67 | 4 | 0 |

The difference packages are MM Weaving Waters and PU Narrow Passage. The next
stratum selects CCP Maps 2, 3, 4, and 5. The coverage cases are AP Noyou Port,
CCMP2 Boreal Maps 1 and 2, and CCMP2 Desert Map 1. No failed case is replaced.

**Both rules predict the same answers to all 48 selected requests.** This
selection has no power to prefer one rule by request labels. The native paths
can still falsify the rules or expose rejected transitions inside successful
paths. These packages do not estimate geographic prevalence.

## Frozen artifacts

`freeze.json` binds the inventory, exclusions, disjoint selections, literal
requests, unqueried candidates, predictions, protocol, and exact source maps.
`features.json` records all consumed Train fields. `catalogs.json` binds only
the old eleven-package catalog union. Unknown prefabs force abstention.
Conflicting full flag names contribute a model fact only when every old
observation agrees on `Invert` or `Outside`. Other flag names are not inputs.

The final pre-query freeze is `20dfb33d863deb4fd13abcbeb952a59e139f93910216771c74fd21c069935a18`,
dated 2026-11-21 21:51:01 UTC. `pre-native-correction.zip` preserves the first
freeze and its sources byte-for-byte. Its replay compared integer-keyed
catalogs with their JSON string-keyed form incorrectly. The correction changes
only that comparison. The inventory, selections, features, requests, and all
predictions are identical. Neither freeze saw a new native outcome.

`metadata-build.json` binds the new DLL to its staged sources. The build adds
one registration call in a staged copy of `Harness.cs`. It does not edit the
accepted harness. `RailMetadata.cs` reads public runtime fields, including
tangents, flags, lane directions, eligibility, and available prefab turn limits.
Unavailable public fields remain null.

Every opening uses the fair queue and fresh offline-account guards. Each query
records pre/post graph digests. Opening and post-batch inventories expose graph
changes. The evaluator reports both all-complete intent-to-test and the exact
snapshot-matched subset. Capture failures, unsupported packages, and unqueried
rows remain in the evidence. Complete failure labels only that literal request.

The unchanged Asanu and Hanami packages and invalid Train-to-Car diagnostics
are separate controls. No holdout query can run before those controls pass.
Pittsburgh is not replayed or pooled. No map, writer, gate, ledger, certificate,
default, golden, or production behavior changes.

## Commands

Run from the repository root with Python 3.12 or newer and the map-factory
environment. The installed game and the hash-bound old CRPs must be available.

```sh
uv run --project tools/map-factory python -m unittest discover \
  -s tools/map-factory/capability-evidence/rail-stock-holdout-v1 -v
uv run --project tools/map-factory python \
  tools/map-factory/capability-evidence/rail-stock-holdout-v1/study.py check
```

For a new unqueried study, run `build_metadata.py`, then `study.py prepare
--package-store PATH`. These commands use exclusive writes and refuse to
overwrite a freeze. Do not rerun them over this study.

For each opening, run `run_one.py SLUG --raw RAW` in the same environment.
Run stock-1 and stock-2 first. Then run each holdout slug exactly once, releasing
the slot between openings. This foreground driver joins its collector and GPU
sampler. `collect.py` refuses changed sources, packages, builds, and controls.

Run `evaluate.py --raw RAW --output REPORT.json` to bind and score observations.
The raw directory needs uncompressed JSON files. Retained compressed copies
can be expanded into task scratch without changing the originals.

Stock packages have no prepared-input or CPU lineage. Preserved proprietary
CRPs and compiled DLLs stay outside Git. The evidence binds their hashes only.
