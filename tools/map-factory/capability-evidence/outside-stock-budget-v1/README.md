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
source key sets, build, and protocol. `features.json.gz` retains parsed export
fields. The reader uses `read_any` and the declared NetManager version.
No package is repaired or replaced after an outcome.

The three preparation archives precede all new native queries. The first used
the smaller outside-only catalog. The second added the accepted stock catalog
and corrected irrelevant-lane handling. The checksum correction fixes JSON mode
ordering and compresses the feature evidence. None contains native outcomes.
The final request and prediction hashes remain fixed through collection.

Asanu's first opening fails before any path request because the original guard
reads the native MetaBool string `"False"` as a Python boolean. That opening is
retained and is not retried. A source-only guard correction precedes every new
path request. `history/pre-query-freeze.json.gz` preserves the earlier freeze.
The stricter frozen control-completion rule therefore leaves all modes unqualified.

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
The original frozen `evaluate.py` omits the transport's `ok=true` field in its
body-schema check. Its failure is retained in `analysis/frozen-scorer-failure.log`.
The post-control scorer in `analysis/evaluate.py` requires exactly the frozen
body keys plus `ok=true`. `analysis/source-fix.json` binds the actual scoring
sources. This is a schema correction, not a rule, label, or threshold change.

After every driver exits, run the repaired scorer with the study directory on
`PYTHONPATH`. Then run `analysis/audit.py --raw PATH --report REPORT.json
--output AUDIT.json`. It checks every observed process identity, request handle,
result flags, bridge mismatch, and budget argument group.
Preserved gzip files can be expanded into task scratch for evaluation.

No map writer, app, ledger, gate, default, old study, or certificate changes.
No public merge, deployment, Shelf page, or capability activation.

## Replay the retained bytes

The scorer needs the exact installed packages and old CRPs at their frozen
locators. The reconstruction check itself does not launch the game.
Use a new task-scratch directory for `TASK_REPLAY_DIR`.

```sh
study_dir=tools/map-factory/capability-evidence/outside-stock-budget-v1
PYTHONPATH="$PWD/$study_dir" uv run --project tools/cs1-harness python \
  "$study_dir/analysis/retain.py" verify --unpack "$TASK_REPLAY_DIR"
PYTHONPATH="$PWD/$study_dir" uv run --project tools/cs1-harness python \
  "$study_dir/analysis/evaluate.py" --raw "$TASK_REPLAY_DIR" \
  --output "$TASK_REPLAY_DIR/../evaluation-replay.json"
PYTHONPATH="$PWD/$study_dir" uv run --project tools/cs1-harness python \
  "$study_dir/analysis/verify.py"
```

`integrity.json` binds the complete retained artifact file set. The verifier
also checks unchanged predictions, source-map key sets, installed CRP receipts,
entry protocol, request fidelity, and observed process identities.
