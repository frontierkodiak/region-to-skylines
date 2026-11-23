# Frozen outside-query stock and budget study

PL-1294 starts at `030db86ce470b972b6ef3462a2698744dff40ebb`.
It tests the unchanged `lane:any_lane:forbidden` rule and `weak_component`
reference. The model's chord cap remains an unvalidated hypothesis parameter.
There is no identified conversion between chord geometry and native cost.

The stock catalog is the accepted eleven-package union at
`914c153687106197e5f3a745d3ff7e181181ea8a`, not new holdout observations.
`prior-stock-catalogs.json` preserves that union and all its input bindings.
Known non-road/ship/air lanes are omitted before reading their direction.
An unknown prefab, relevant direction, or used flag fact causes abstention.
Conflicting full flag names contribute only an agreed `Outside` or `Invert` bit.

`freeze.json` binds the sorted installed inventory, exclusions, features,
selected and unqueried requests, predictions, controls, intervention rows,
source key sets, build, and protocol. `features.json` retains parsed export
fields. The reader uses `read_any` and the declared NetManager version.
No package is repaired or replaced after an outcome.

The two preparation archives precede all new native queries. The first used
the smaller outside-only catalog. The second added the accepted stock catalog
and corrected irrelevant-lane handling. They are not native results or model
refits. The final freeze is the only collection plan.

The study build changes only a staged copy of `NetworkOps.cs`. It passes the
requested float budget directly to the existing public `CreatePath` overload,
and returns its effective arguments. Accepted files stay unchanged.
Each opening uses the fair queue, offline-account guard, and fresh executable,
assembly, plugin, and file inventories. File hashes do not attest memory or
strict no-mods. Every request records pre/post model-field hashes and context.
The driver joins the collector. Cleanup checks bind PID and process start time.

Stock controls, new stock requests, and retained-road interventions are separate.
A mode needs a successful stock positive and invalid-vehicle rejection.
Incomplete, unreleased, endpoint-mismatched, missing, or errored requests stay
unknown. An observed failure labels only its exact request.
The old road labels remain immutable. The budget repeats are new, correlated
observations and cannot establish a universal failure mechanism.

## Reproduce the checks

Run from the repository root with the map-factory and cs1-harness dependencies.

```sh
uv run --project tools/cs1-harness python -m unittest discover \
  -s tools/map-factory/capability-evidence/outside-stock-budget-v1 -v
uv run --project tools/cs1-harness python \
  tools/map-factory/capability-evidence/outside-stock-budget-v1/study.py check
```

For an unqueried copy, run `build_study.py`, then `study.py prepare` once.
Commit the freeze before running `run_one.py CASE --raw PATH`.
Run the two stock controls first, then each selected case and budget opening
once. The slot is released after every opening. Do not retry a failed case.
Run `evaluate.py --raw PATH --output REPORT.json` after every driver has exited.
Preserved gzip files can be expanded into task scratch for evaluation.

No map writer, app, ledger, gate, default, old study, or certificate changes.
No public merge, deployment, Shelf page, or capability activation.
