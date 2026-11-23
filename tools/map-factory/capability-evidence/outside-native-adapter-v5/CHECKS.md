# Reproduce the offline adapter proof

From an exact checkout of this PR, without `.build`. All outputs stay in a
private experiment holding. Never copy compiler/reference/DLL/package bytes into
Git or attachments. A missing or corrupt private artifact is a failure, not a
skip or a passing fresh build.

## Replay the delivered engineering freeze

Blade holding: `~/experiments/PL-1318-native-adapter/evidence`.
It is a task-owned copy of the accepted PL-1315 holding plus retained compiler
runtime, fresh DLL, staged sources, receipt and actual driver handoffs.
`proof/` contains only our metadata, hashes and test receipts.

```bash
module=tools/map-factory/capability-evidence/outside-native-adapter-v5
run=~/experiments/PL-1318-independent-review
mkdir -p "$run"
cp -a --reflink=auto ~/experiments/PL-1318-native-adapter/evidence "$run/evidence"
cp "$module/adapter-freeze.json" "$run/adapter-freeze.json"
cp "$module/fresh-build.json" "$run/fresh-build.json"
uv run --project tools/cs1-harness python "$module/verify_adapter.py" exercise \
  --store "$run/evidence" --freeze "$run/adapter-freeze.json" \
  --run "$run/exercise-final"
mkdir -p "$run/fresh-build" # Replay-only overwrite-refusal target; no compiler runs here.
PL1318_RUN="$run" uv run --project tools/cs1-harness \
  python -m unittest discover -s "$module" -p 'test_*.py' -v
uv run --project tools/cs1-harness python "$module/verify_adapter.py" preserve \
  --store "$run/evidence" --run "$run/preservation"
uvx ruff check "$module"
uvx ruff format --check "$module"
git diff --check
```

The overwrite-refusal test requires an existing directory at
`$run/fresh-build`: create that empty directory when only replaying receipts.
The test does not invoke a fresh compiler into it.

Expected: structural pass, actual five-role birth/exit/absence receipts, driver
observation handoff, constructed runtime facts, zero native requests/openings,
admission/export qualification Unknown. `refusal-effects.json` records every
preflight refusal and its empty transport-call list. `effect-log.json` records
the finite stub operations: pre-query graph/context, independent BuildIndex,
constructor, completion/release, post-query graph/context and inventories.

The tests mutate executable bytes in an isolated source copy, not the accepted
worktree. Retained-byte tests temporarily corrupt/delete their **own private
copy** and restore it. Never run them against another task's holding.

## Make a genuinely fresh local build

Use a new run directory and a task-owned evidence copy as above. Supply the
existing licensed compiler holding explicitly; the builder does not install or
download a compiler, query Steam, read the game directory, or deploy a DLL.

```bash
uv run --project tools/cs1-harness python "$module/verify_adapter.py" build \
  --store "$run/evidence" --run "$run" \
  --dotnet-root ~/.cache/cs1-harness/dotnet
```

This creates a never-before-existing `$run/fresh-build` stage, copies references
from content-addressed licensed evidence, replays our pinned source transform,
executes csc, retains output and constructs a new engineering freeze. It refuses
an existing stage or output freeze. Do this **instead of** copying the delivered
freeze/receipt or creating the empty replay-only directory. Then run exercise
and tests using that new receipt/freeze. Compiler invocation timestamps/paths
and therefore receipt/spec hashes will differ. DLL bytes may reproduce exactly;
that does not make an actual compiler invocation a retained-build rehearsal.

The original v4 spec remains an embedded retained-build rehearsal. Its exact
87/35 role checks are reused, not relabeled. The outer source/build descriptor
and consumer bind the fresh output independently. The producer compiled twice:
initial integration, then once at final executable source. No physical package
rebuild, old evaluator, native study or browser ran.
