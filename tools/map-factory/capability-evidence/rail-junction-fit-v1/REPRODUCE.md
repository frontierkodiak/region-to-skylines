# Reproducing the rail junction-fit study

Everything is pure Python over files that already exist in this repository plus
the nine cohort and two stock-control `.crp` exports at their frozen locators.
No game, browser, server or rebuild is involved.

## Environment

```sh
cd tools/map-factory
uv sync            # Python 3.13, numpy/pillow/scipy/rasterio from uv.lock
```

Verified with Python 3.13.13, uv 0.11.11, Ruff 0.11.6.

The inputs are the accepted PL-1215 native study's own frozen files:

```
capability-evidence/rail-v3/raw/{stock-1,stock-2,asheville,innsbruck}/
capability-evidence/rail-v3-followup-1/raw/{boston,charleston,grand-canyon,hong-kong,pittsburgh,rio,yosemite}-attempt-*/
```

Each needs `networks.json.gz`, `query-freeze.json.gz` and `observation.json.gz`;
their SHA-256 values are the accepted study's `corrected/integrity.json`
bindings, read through the hash-pinned accepted prefix. The export bridge and
the freeze additionally need the `.crp` exports at the locators in the accepted
`packages.json`; every one is checked against its recorded SHA-256 before it is
read. The two stock controls are the Steam-install copies
`/peach/Games/SteamLibrary/.../AP Asanu Beach.crp` and
`.../AP Hanami Bay.crp`.

## Order, and why the order matters

```sh
# 1. Design and input-only predictions. Refuses to open any observation.
.venv/bin/python capability-evidence/rail-junction-fit-v1/freeze.py

# 2. Bind and score. The first stage that reads a label.
.venv/bin/python capability-evidence/rail-junction-fit-v1/evaluate.py

# 3. Explain the reference rule's remaining errors, after the scores exist.
.venv/bin/python capability-evidence/rail-junction-fit-v1/diagnose.py

# 4. Audit the export bridge, including the two format-8 stock controls.
.venv/bin/python capability-evidence/rail-junction-fit-v1/export_bridge.py
```

`freeze.py` writes `protocol.json`, then `features.json`, then
`predictions.json`, each recording the SHA-256 of the artifact before it.
`evaluate.py` raises `BindingError` rather than scoring if the protocol,
features, predictions, package bytes, plan, observation bytes, query set or
source hashes disagree. `diagnose.py` and `export_bridge.py` bind their reports
to the hashes they read.

Every stage has `--check`, which recomputes from the current sources and compares
with the frozen file (ignoring only the volatile `frozen_at`/`computed_at`
stamps and the source map):

```sh
.venv/bin/python capability-evidence/rail-junction-fit-v1/freeze.py --check
.venv/bin/python capability-evidence/rail-junction-fit-v1/evaluate.py --check
.venv/bin/python capability-evidence/rail-junction-fit-v1/diagnose.py --check
.venv/bin/python capability-evidence/rail-junction-fit-v1/export_bridge.py --check
```

## Tests

```sh
cd tools/map-factory
.venv/bin/python -m unittest discover \
  -s capability-evidence/rail-junction-fit-v1 -p 'test_*.py'
```

35 tests. They cover: the tangent convention and its proof against node
positions; a shared-node fixture where chord and tangent derive different
pairings and different reachability; turn thresholds; symmetric ties; missing
tangents; non-contiguous Train lane indexes; `Invert`; the length lower bound and
a shorter alternative; **full ID, record-order and orientation reversal on a
real frozen package** (the orientation test is also the empirical check of the
tangent convention: reading the wrong end's direction would change predictions);
closed-manifest and fold-partition mutations; source, protocol and observed-row
binding mutations; duplicate, missing and extra queries; label mutations; freeze
purity; exact equivalence with the accepted frozen predictions for both chord
continuation rules; witness/prediction agreement; and every reported number in
`RESULTS.md` that the artifacts carry.

Lint:

```sh
ruff check capability-evidence/rail-junction-fit-v1
ruff format --check capability-evidence/rail-junction-fit-v1
```

## Frozen hashes

| File | SHA-256 |
| --- | --- |
| `manifest.json` | `3ec070f05c74c14bc0d4613dc0ea6a8cba4a1ce1281b11dbe5fd6867a25b5aa7` |
| `protocol.json` | `f7607cff8807170da70f0152d1752617e0930561cf1fe648537b8b1610ffccce` |
| `features.json` | `d38cf3e634d75d0ed69d08f35444f6548e621bf2fdd9b85f43a9b2d8f0d07551` |
| `predictions.json` | `ce0830d379f344697f958bca12161bd3a2e53f5aef87678b2a78d144ccfbcbd4` |
| `predictions.json` `queries_sha256` | `d0c7fd0fa0bb110dfa3a951bf4f74945541603f10a6c2a7408d131d252978988` |
| `evaluation.json` | `64cfbe21495771acc9362ab8c9a8daa6ab286aded34d450c402e5535876d9dcc` |
| `diagnostics.json` | `d35953f1f5d3899cd481df020e672da4da753c74c7abb61bb5883c477bc58b8e` |
| `bridge-audit.json` | `cb49abcac5ad8a305e62a4a07ea71550613b566e19ccbfda226b7a5ffbbc4d78` |

`freeze.py` stamps `frozen_at`, so re-freezing an unchanged model still changes
`protocol.json` and `predictions.json`. The `queries_sha256` above is the stable
identity of the predictions themselves: re-running the freeze with unchanged
predict-path sources must reproduce it, and a documentation or diagnostics change
cannot move it.

The accepted prefix is pinned, not modified:
`openings.json`, `packages.json`, `corrected/protocol.json`,
`corrected/predictions.json`, `corrected/evaluation.json`,
`corrected/integrity.json`, `model.py`, `topology.py` and `bridge.py` at the
exact SHA-256 values in `manifest.json` and in `predictions.json.sources`.

## Reading the result

[`RESULTS.md`](RESULTS.md) is the report. `evaluation.json` holds every rule's
confusion on the full set, the stock controls, the cohort and each opening, the
per-fold selections with their tie sets, the pooled out-of-fold scores, the
paired comparison and every counterexample. `diagnostics.json` holds the error
mechanics and the input-only count of junctions where the two measures differ.
`bridge-audit.json` holds the per-package container lineage, field agreement,
digests and tangent precision.
