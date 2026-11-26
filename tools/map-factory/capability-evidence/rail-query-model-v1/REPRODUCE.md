# Reproducing the rail query-scoped reachability study

Everything here is a pure Python model, evaluator and bridge over files that
already exist in this repository, plus the nine frozen `.crp` packages for the
bridge. No game, browser, server or rebuild is needed.

The corrected v2 freeze is under `corrected/`. The reviewed v1 artifacts at the
prefix root are preserved byte-for-byte and are only read for comparison.

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
`observation.json.gz`. Their SHA-256 values are pinned in
`corrected/integrity.json`.

The bridge additionally needs the nine cohort packages at the frozen locators in
`packages.json` (the `mango`/`peach` mounts on blade). `predict.py` and
`evaluate.py` do not need them. `predict.py` and `bridge.py` verify every
locator's SHA-256 before reading and exit non-zero if a byte differs.

## Order

```sh
# 1. Predictions. Reads topology and plans only; never observes an outcome.
.venv/bin/python capability-evidence/rail-query-model-v1/predict.py

# 2. Evaluation. Binds every prediction to its plan request, observed row,
#    package/snapshot/protocol/source hash, then scores.
.venv/bin/python capability-evidence/rail-query-model-v1/evaluate.py

# 3. Offline bridge over the nine unchanged cohort packages.
.venv/bin/python capability-evidence/rail-query-model-v1/bridge.py
```

`predict.py --check`, `evaluate.py --check` and `bridge.py --check` recompute
from the current sources and compare with the frozen corrected files; the
evaluator's check also revalidates every binding.

## Tests

```sh
cd tools/map-factory
.venv/bin/python -m unittest discover \
  -s capability-evidence/rail-query-model-v1 -p 'test_*.py'
```

43 tests: determinism; id renaming and segment-order invariance; orientation
reversal invariance on a fixture and on a real frozen package; Train-only
domain; Car-only segment exclusion; `Invert` direction; equal-angle junction
ties; dead-end reversal for all three hypotheses; the length bound and its
relaxation to a shorter alternative; endpoint direction; abstention on missing
inputs; junction continuation; baselines; label and confusion arithmetic,
including null denominators; freeze integrity of the preserved v1 artifacts;
the corrected freeze's protocol and sources; the control and cohort groups;
zero-query packages; the bridge status and model-input digest; evaluation
request/row/source binding mutations; a real package deriving every model field
from export bytes; package bytes untouched.

## Contract evidence

The six constructed cases that fail on the reviewed head are the
`DomainContractTest` class. Run only those against a checkout of `97e0038`:

```sh
git worktree add --detach /tmp/r2s-97e 97e00389f4ad0eb30aa1ff1d775876c87f4ab27c
cp tools/map-factory/capability-evidence/rail-query-model-v1/test_rail_query_model.py \
   /tmp/r2s-97e/tools/map-factory/capability-evidence/rail-query-model-v1/
cd /tmp/r2s-97e/tools/map-factory/capability-evidence/rail-query-model-v1
<blade>/region-to-skylines/tools/map-factory/.venv/bin/python \
  -m unittest test_rail_query_model.DomainContractTest -v
```

`97e0038` reports 5 failures and 1 error of 6; the corrected tree passes all
six. The logs are in `corrected/evidence/`. The binding probe under the same
directory shows the mutated-request behaviour on each tree.

## Expected output hashes (corrected v2)

The frozen files are reproducible from the recorded inputs; a run that changes
any number below changed the study.

| File | SHA-256 |
| --- | --- |
| `corrected/protocol.json` | `89665a2b7e067412f58ff851b8ccbc7ec61bbb569be37e2185f9108da1235c2a` |
| `corrected/predictions.json` | `e8268d16fd5b69da88e6a6a2052a55b2282a7366d4c893c781080b3077286a74` |
| `corrected/evaluation.json` | `252e4d6cbf8276c061b9edd5d9cc1171d0f05dbddbbad2836bcfe64b374b52f8` |
| `corrected/bridge.json` | `94398542221512b71dca71021a5c3609d56b72e9383badc3425d07fe1b1ff6c9` |
| `corrected/catalogs.json` | `f4c13451b806dcb280d23765d509f1ad7591b7cf33623131688b7a2c2d3920b0` |
| `corrected/integrity.json` | `f6cfe4be004da17a66fe4bfd650de0fa585bb5f033f6cede860a15a3c249b2f7` |

The reviewed v1 artifacts at the prefix root keep their own hashes and must not
change:

| File | SHA-256 |
| --- | --- |
| `protocol.json` | `1c736e72800d7d469d337be94f2588a366f9772a067e8a0b366cc7e57399699b` |
| `predictions.json` | `2b7a0b0b6304a6bbf7010141cdb553a79909e2e83505a7c54442dc68155ea74d` |
| `evaluation.json` | `1e345edcd5c2759b107847f5433308bd50de675e26cfb39921ffcad1ad455533` |
| `bridge.json` | `cc1794b78600ca482528627d41a883a364e3ff93eef7f0251895116cc8fd711d` |
| `catalogs.json` | `f4c13451b806dcb280d23765d509f1ad7591b7cf33623131688b7a2c2d3920b0` |
| `integrity.json` | `8ce8c9bef003b998d6948d6afb9b5af84e9f81d3882c0c24fe2b3f0fe9228253` |

`predict.py` writes `frozen_at`, so re-freezing a changed model or protocol
changes `corrected/protocol.json` and `corrected/predictions.json`;
`evaluate.py` and `bridge.py` carry the hashes of the files they read, so a
mismatch is visible rather than silent.

## Reading the result

`RESULTS.md` is the report, and `corrected/CORRECTION.md` the correction record.
`corrected/evaluation.json` holds every rule's confusion matrix, every group's,
and each counterexample with the raw-file hashes it was scored against.
`corrected/bridge.json` holds the field-by-field export comparison, the
canonical model-input digests, and the leave-one-package-out catalog checks.
