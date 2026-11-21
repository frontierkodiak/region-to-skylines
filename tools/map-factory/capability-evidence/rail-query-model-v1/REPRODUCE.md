# Reproducing the rail query-scoped reachability study

Everything here is a pure Python model, evaluator and bridge over files that
already exist in this repository, plus the nine frozen `.crp` packages for the
bridge. No game, browser, server or rebuild is needed.

## Environment

```sh
cd tools/map-factory
uv sync                    # Python 3.13, numpy/pillow/scipy/rasterio from uv.lock
```

The native snapshot inputs are the accepted PL-1215 study's own frozen files:

```
capability-evidence/rail-v3/raw/{asheville,innsbruck,stock-1,stock-2}/
capability-evidence/rail-v3-followup-1/raw/{boston,charleston,grand-canyon,hong-kong,pittsburgh,rio,yosemite}-attempt-*/
```

Each opening needs `networks.json.gz`, `query-freeze.json.gz` and
`observation.json.gz`. Their SHA-256 values are pinned in `integrity.json`.

The bridge additionally needs the nine cohort packages at the frozen locators in
`packages.json` (the `mango`/`peach` mounts on blade). `predict.py` and
`evaluate.py` do not need them. `predict.py` and `bridge.py` verify every
locator's SHA-256 before reading and exit non-zero if a byte differs.

## Order

```sh
# 1. Predictions. Reads topology and plans only; never observes an outcome.
.venv/bin/python capability-evidence/rail-query-model-v1/predict.py

# 2. Evaluation. The first step that opens an observation.
.venv/bin/python capability-evidence/rail-query-model-v1/evaluate.py

# 3. Offline bridge over the nine unchanged cohort packages.
.venv/bin/python capability-evidence/rail-query-model-v1/bridge.py
```

`predict.py --check`, `evaluate.py --check` and `bridge.py --check` recompute
from the current sources and compare with the frozen files.

## Tests

```sh
cd tools/map-factory
.venv/bin/python -m unittest discover \
  -s capability-evidence/rail-query-model-v1 -p 'test_*.py'
```

26 tests: determinism, id renaming and segment-order invariance, orientation
reversal invariance on a fixture and on a real frozen package, endpoint
direction and reversal handling, abstention on missing inputs, junction
continuation, baseline behaviour, label and confusion arithmetic, freeze
integrity, a real package deriving every model field from export bytes, and the
package file being untouched.

## Expected output hashes

The frozen files are reproducible from the recorded inputs; a run that changes
any number below changed the study.

| File | SHA-256 |
| --- | --- |
| `protocol.json` | `1c736e72800d7d469d337be94f2588a366f9772a067e8a0b366cc7e57399699b` |
| `predictions.json` | `2b7a0b0b6304a6bbf7010141cdb553a79909e2e83505a7c54442dc68155ea74d` |
| `evaluation.json` | `1e345edcd5c2759b107847f5433308bd50de675e26cfb39921ffcad1ad455533` |
| `bridge.json` | `cc1794b78600ca482528627d41a883a364e3ff93eef7f0251895116cc8fd711d` |
| `catalogs.json` | `f4c13451b806dcb280d23765d509f1ad7591b7cf33623131688b7a2c2d3920b0` |
| `integrity.json` | `c65edf54b0583649f6f3d169971f002e9ec8a30d5fcca755b0abc5d8fb82c93a` |

`predict.py` writes `frozen_at`, so re-freezing a changed model or protocol
changes `protocol.json` and `predictions.json`; `evaluate.py` and `bridge.py`
carry the hashes of the files they read, so a mismatch is visible rather than
silent.

## Reading the result

`RESULTS.md` is the report. `evaluation.json` holds every rule's confusion
matrix, every group's, and each counterexample with the raw-file hashes it was
scored against. `bridge.json` holds the field-by-field export comparison and the
leave-one-package-out catalog checks.
