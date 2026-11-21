# Verify or repeat the outside-connection study

## Verify the committed evidence

Run these commands from the repository root:

```sh
study=tools/map-factory/capability-evidence/outside-v1
uv run --project tools/map-factory python "$study/verify.py"
uv run --project tools/map-factory python -m unittest discover -s "$study" -p 'test_*.py'
```

Add `--require-nine-attempts` to reject a dataset that lacks a native attempt
for any selected square. That flag requires coverage, not successful paths.
The verifier checks hashes, package bindings, completed path release, session
cleanup, and raster-bound reproduction. It does not rerun the game.

## Repeat native observations on blade

Use the existing frozen package holding. Do not recapture inputs, move a square,
or change a water warning to improve a result. Choose a new native output root.
The collector refuses existing case directories.

1. Build and check the collector:

   ```sh
   uv run --directory tools/cs1-harness cs1-harness build
   uv run --directory tools/cs1-harness cs1-harness doctor --wait-minutes 180
   ```

2. Collect the fixed squares in the foreground:

   ```sh
   uv run --directory tools/cs1-harness python -m cs1_harness.connections \
     ../map-factory/capability-evidence/outside-v1/selection.json \
     --out ~/experiments/PL-1121-outside-oracle/native-recheck-01 --wait-minutes 180
   ```

   The collector uses the fair queue and fresh offline-Steam and carbon-idle
   guards. It releases the slot after each map. It does not repair packages,
   invoke a browser, or leave a preview. Completed paths are released. A pending
   path timeout ends that session. A startup failure remains unknown.

3. Retain the original attempts when you assemble a repeat:

   ```sh
   uv run --project tools/map-factory python "$study/assemble.py" \
     --native ~/experiments/PL-1121-outside-oracle/native \
     --retry-native ~/experiments/PL-1121-outside-oracle/native-recheck-01 \
     --reproduction ~/experiments/PL-1121-outside-oracle/reproduction
   uv run --project tools/map-factory python "$study/verify.py" --require-nine-attempts
   ```

Use `--only SLUG` on the collector to retry an environment startup failure on
the same immutable package. Keep every attempt. Do not retry completed negative
path results to select a better outcome. Distinct retry roots receive distinct
attempt IDs in the evidence.

## Reproduce the CPU package comparison

On blade, the frozen inputs and packages are under the experiment roots named
in `selection.json`. These commands reuse those bytes:

```sh
uv run --project tools/map-factory python tools/map-factory/qualify_connections.py \
  ~/experiments/PL-1121-outside-oracle/reproduction \
  --baseline ~/experiments/PL-1066-eligibility
uv run --project tools/map-factory python "$study/water_support.py"
```

The Boston capture program is `capture-boston.mjs`. It fixes the square and
uses `includeRunways=true`. The original capture receipt and input hashes are
retained. A new live capture is not a reproduction of that capture's bytes.

## PL-1142 correction and focused v2 diagnostic

`annotate.py` derives endpoint roles, collector/protocol labels and missing-request
reasons from retained raw observations and networks. `assemble.py` calls it
automatically. `verify.py` rejects fresh rows that differ from raw requests/results
and checks derived annotations and summary. Historical gzip files, failures and
timestamps are unchanged. Historical v1 attempts lack runtime executable binding
and cannot qualify as exact-runtime certificates. All nine water-risk screens
remain warnings.

After building, run the focused collector in the foreground on blade:

```sh
uv run --directory tools/cs1-harness python -m cs1_harness.connections \
  ../map-factory/capability-evidence/outside-v1/selection.json \
  --focused-v2 --out ~/experiments/PL-1142-native-v2/native --wait-minutes 0
```

The fixed selection is ship in Rio, Charleston, Hong Kong and Boston; additionally
Rio rail, Pittsburgh road, and Hong Kong road/rail. The diagnostic subset had no
successful fresh two-edge witness in the reviewed evidence. This is a diagnostic
re-probe, not a new holdout, threshold fit or map repair. Candidates are restricted to an undirected vehicle component for probe selection,
not a native connectivity claim. A fixed 256-request/mode budget rotates across
endpoint pairs before trying their other lane combinations. Each submitted lane
pair keeps boundary/midpoint controls in both directions; omitted pairs remain
unknown. All ship candidates fit within this budget. Road pairs
require opposite OneWay roles. Native requests determine rail reachability.
No failed request is a global capability negative.

The collector binds the rendering PID through its namespace PID and hashes
`/proc/PID/exe`. It asks that process for loaded assembly paths and hashes,
independently hashes those files through `/proc/PID/root`, then compares all build
references and the mod DLL. Missing or mismatched identity aborts before map
observations. This binds loaded assembly files at menu readiness, not in-memory
code pages.

Each batch releases the fair queue slot. If occupied, retain that attempt and
arrange a persisted continuation. Never leave a waiter or game behind. Preserve
all old attempts when importing new receipts with another `--retry-native`.
Retain the new collector and runtime helper source hashes/version before import.

Append each v2 batch without replacing historical attempts:

```sh
study=tools/map-factory/capability-evidence/outside-v1
uv run --project tools/map-factory python "$study/import_v2.py" \
  --native ~/experiments/PL-1142-native-v2/native \
  --reproduction ~/experiments/PL-1121-outside-oracle/reproduction \
  --attempt-id native-v2-1
```

Register the collector source version first in `collector-versions.json`. Keep
every partial or failed batch with a distinct attempt ID. Runtime-bound fresh
two-edge witnesses are separate from historical fresh witnesses in the summary.
