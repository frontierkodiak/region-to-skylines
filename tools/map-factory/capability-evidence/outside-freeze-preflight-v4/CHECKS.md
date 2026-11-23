# Run the offline checks

Run from the repository root. Use a fresh checkout without a local `.build`.
Keep the private store outside the repository. These commands open no game or
queue. A missing or corrupt private artifact fails the check; tests do not skip.

## Replay the delivered freeze

On blade, the task-owned private store is
`~/experiments/PL-1315-freeze-preflight-v4/evidence`.
You can relocate that directory byte-for-byte. None of the producer's absolute
build or game locators is required for replay.

```bash
module=tools/map-factory/capability-evidence/outside-freeze-preflight-v4
run_root=~/experiments/PL-1315-review
private_store=~/experiments/PL-1315-freeze-preflight-v4/evidence
mkdir -p "$run_root"
uv run --project tools/cs1-harness python "$module/verify.py" preflight \
  --store "$private_store" --freeze "$module/future-freeze.json" \
  --output "$run_root/preflight.json"
uv run --project tools/cs1-harness python "$module/verify.py" exercise \
  --store "$private_store" --freeze "$module/future-freeze.json" \
  --output "$run_root/exercise.json"
PL1315_EVIDENCE="$private_store" uv run --project tools/cs1-harness \
  python -m unittest discover -s "$module" -p 'test_*.py' -v
uv run --project tools/cs1-harness python "$module/verify.py" immutability \
  --store "$private_store" --output "$run_root/immutability.json"
uvx ruff check "$module"
uvx ruff format --check "$module"
git diff --check
```

`preflight` must report offline compatibility, launch unauthorized, local fresh
build unverified, and admission/export qualification Unknown. `exercise` must
report a constructed consumer pass, zero native observations, no certificate,
and every owned child collected. Its PIDs will differ on each run.

## Reproduce the first old-freeze failure

```bash
uv run --project tools/cs1-harness python "$module/verify.py" legacy \
  --store "$run_root/deliberately-absent" --output "$run_root/legacy.json"
```

Expected exit code is **2**, with `legacy freeze consumer closure (before build
lookup)`. This reads the actual immutable PL-1313 freeze, not a synthetic copy.
The deliberately absent artifact store cannot hide the earlier contract error.

## Build another offline rehearsal spec

The delivered store already contains the required bytes. The real builder
refuses to overwrite an existing output freeze.

```bash
uv run --project tools/cs1-harness python "$module/verify.py" build \
  --store "$private_store" --output "$run_root/new-future-freeze.json"
```

To seed an independent private holding, use `verify.py seed --store NEW_DIR
--retained OLD_PRIVATE_STORE --compiler COMPILER_FILE --package SELECTED_CRP
--output RECEIPT`. The old compiler hash and package hash are checked against the
declared receipt/input roles. The old holding is copied, never modified.
No licensed binary belongs in Git or an issue attachment.

## Coverage

The tests mutate every source hash and actual source file, every declared
input/build artifact's hash and retained bytes, exact role keysets, role digests,
collector and bundle bindings, each runtime phase binding, actual assembly MVIDs,
control/observation fields, and process coverage/start identities. Corrupt and
missing artifacts both fail. The old consumer rejects the new exact closure;
the versioned consumer accepts the real builder output with constructed facts.

`proof/` contains the final test log, old rejection, structural preflight,
constructed lifecycle receipt and historical-byte receipt. These receipts contain
no licensed bytes. The 142 old publication files, 24 readiness files and 26
stopped-study files are compared byte-for-byte to the exact pin. The old audit
containing 84 facts is hashed as bytes, not rescored. All six old holdout cells
remain unobserved Unknown.
