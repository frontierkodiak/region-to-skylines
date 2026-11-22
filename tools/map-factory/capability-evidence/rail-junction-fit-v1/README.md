# Rail junction-fit v1: chord or authored tangent?

A bounded, off-game research study of one modelling choice in the accepted
[`rail-query-model-v1`](../rail-query-model-v1/README.md) junction rule. That
rule connects, at each node, the disjoint straightest continuation of the
incident Train segments, measuring "straightest" from the chord between node
positions. This study asks whether the authored endpoint tangents the game
stores on each segment describe those junctions better.

The measurements are the point. The report is [`RESULTS.md`](RESULTS.md); the
reproduction is [`REPRODUCE.md`](REPRODUCE.md).

## Ten-second summary

* The accepted rule's five errors are **all inside Pittsburgh, and all trace to
  two junctions** - the only two junctions in that package where the chord and
  tangent continuation pairings differ.
* The same continuation rule with tangent angles separates **all 276** selected
  outcomes; the accepted chord rule scores 271 of 276. Nothing that was right
  becomes wrong (5 corrected, 0 broken).
* The strict leave-one-package-out **selection cannot prefer** the tangent rule,
  because the one package with errors to discriminate them is held out exactly
  then: its pooled selected score equals the accepted rule's. The fixed,
  pre-registered tangent counterpart scores perfectly out of fold. Neither is a
  blind estimate.
* The accepted rule's false negative is matched by a **different path** than the
  native one, so this is a better fit, not an identified native junction law.

## Layout

| Path | Purpose |
| --- | --- |
| `manifest.json` | the predeclared design: measures, junction kinds, pairings, the 12-value threshold grid, the 58 rules, splits, selection protocol, label definitions; pins the accepted prefix and source revision |
| `export_topology.py` | the only module that opens package bytes: container (formats 4-12), declared data version, NetManager section, tangents; reuses the accepted bridge's catalogs, comparator and digest |
| `junction_model.py` | the junction hypotheses: chord vs authored tangent, greedy continuation vs turn threshold; calls the accepted corrected `model._reach` unchanged |
| `binding.py` | closed manifest validation, query-set completeness and uniqueness, fold construction and leakage checks, observation binding, labels, scoring helpers |
| `freeze.py` | writes `protocol.json`, `features.json`, `predictions.json`; never opens an observation |
| `evaluate.py` | binds and scores; writes `evaluation.json` |
| `diagnose.py` | after the freeze, explains the reference rule's errors; writes `diagnostics.json` |
| `export_bridge.py` | audits every consumed field from `.crp` bytes, including the two stock controls in the older package container; writes `bridge-audit.json` |
| `test_rail_junction_fit.py` | 35 tests: geometry and convention, domain invariants, ID/order/orientation invariance on a real package, binding and fold mutations, freeze purity, accepted-prediction equivalence, reported outputs |
| `protocol.json`, `features.json`, `predictions.json`, `evaluation.json`, `diagnostics.json`, `bridge-audit.json` | the frozen artifacts, in freeze order |

`predictions.json` records a `queries_sha256` over its predictions alone, so a
later documentation or diagnostics change can be shown not to have moved a
prediction.

## Run it

```sh
cd tools/map-factory
uv sync
.venv/bin/python capability-evidence/rail-junction-fit-v1/freeze.py
.venv/bin/python capability-evidence/rail-junction-fit-v1/evaluate.py
.venv/bin/python capability-evidence/rail-junction-fit-v1/diagnose.py
.venv/bin/python capability-evidence/rail-junction-fit-v1/export_bridge.py
```

Each stage has `--check` to recompute and compare. No game, browser, server or
physical rebuild is needed; the only inputs are the accepted study's frozen
native snapshots, plans and observation files, and the frozen `.crp` exports at
their recorded SHA-256.
