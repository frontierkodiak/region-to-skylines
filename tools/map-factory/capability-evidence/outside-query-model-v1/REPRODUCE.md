# Reproducing the outside-query model

Nothing is captured, rebuilt or repaired. Every input is read from the accepted
outside-v1 evidence bundle in this repository plus the nine unchanged `.crp`
packages, each bound by SHA-256.

## Environment

- Python 3.12.
- `topology.py`, `model.py`, `inventory.py`, `predict.py`, `evaluate.py` and the
  tests use the standard library only.
- `bridge.py` needs the map-factory's dependencies (`numpy`, `Pillow`) because it
  imports the repository's `.crp` reader. With `uv`:

  ```sh
  uv venv .venv --python 3.12
  uv pip install --python .venv/bin/python numpy pillow
  ```

## Inputs

| Input | Where | Binding |
| --- | --- | --- |
| Accepted evidence | `../outside-v1/evidence.json` | its SHA-256 is recorded in `inventory.json`, `requests.json` and `protocol.json` |
| Raw observations and network snapshots | `../outside-v1/raw/...` | each gzip member's SHA-256 is checked against the recorded one |
| The nine `.crp` packages | locators in `packages.json` | each package's SHA-256 is checked before it is read |

The `.crp` files are the accepted generation's own exports and are not
redistributed here. If a locator is unavailable the bridge cannot run and
`bridge.py` fails closed; `inventory.py`, `predict.py` and `evaluate.py` do not
need it.

## Order

Run from this directory:

```sh
python3 inventory.py             # inventory.json, requests.json, manifest.json
.venv/bin/python bridge.py       # catalogs.json, bridge.json   (needs the .crp files)
python3 predict.py               # protocol.json, predictions.json (label-free)
python3 evaluate.py              # evaluation.json, integrity.json (first label read)
python3 -m unittest -v test_outside_query_model
```

`bridge.py` must run before `predict.py` because the protocol records the
catalog's SHA-256. `predict.py` reads only `requests.json` and the retained
pre-query snapshots. `evaluate.py` refuses to run unless `protocol.json` already
records the SHA-256 of the `predictions.json` on disk.

Each freeze commit carries the predictions and their protocol before the
evaluation code that scores them, so the order in git shows the freeze rather
than asserting it.

## What to check

- `integrity.json` lists every binding assertion and its result; `all_ok` must
  be `true`.
- `predictions.json` is deterministic: re-running `predict.py` reproduces the
  same bytes, and the protocol's `predictions_sha256` matches the file.
- `evaluation.json` binds `predictions_sha256`, so a changed prediction cannot
  be scored against the old report.
- `bridge.json` answers whether the model's inputs are recoverable from the
  export bytes, per package and per mode, and lists the leave-one-package-out
  cross-validation.
- `manifest.json` lists every excluded request with its reason. Excluded rows
  never become a failure label.

## Bounds on re-running

Re-running in this checkout reproduces the same numbers. On another host the
bridge needs the nine packages at the locators in `packages.json`; a package
whose SHA-256 differs is refused rather than silently substituted. Nothing in
this study writes outside
`tools/map-factory/capability-evidence/outside-query-model-v1/`.
