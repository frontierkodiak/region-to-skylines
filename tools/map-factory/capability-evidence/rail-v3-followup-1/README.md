# Rail cohort continuation

This directory adds new attempts to the immutable first batch in
[`rail-v3`](../rail-v3/README.md). It references the original stock-control
receipts by hash. Those references are not new openings or independent votes.
No native protocol, mod, package, original case or first-batch raw file changes.

The continuation driver freezes its source, sampler, original selection,
stock-control references and output attempt names before new queries. It skips
completed, bound cases even when their selected queries failed. Rio receives
a new output name because its original directory contains a queue denial.
Every opening still calls the unchanged native collector, which records a
fresh executable, full resolved assembly-file inventory, plugin flags and
process identity. Actual lane enumeration is frozen before that opening's
queries. Midpoint and invalid-vehicle diagnostics remain separate.

The foreground driver joins both collector and telemetry monitor before it
returns. A busy queue stops the batch without displacing another owner.
`integrity.json` names only the additional raw files. The verifier checks the
initial batch first, then combines attempts by original package hash. It
reports each attempt rather than replacing a failed history with a success.
A finite miss stays Unknown, including a completed opening with no candidate.

## Verify

Run from the repository root:

```sh
uv run --directory tools/cs1-harness python \
  ../map-factory/capability-evidence/rail-v3-followup-1/review.py
uv run --directory tools/cs1-harness python -m unittest discover \
  -s ../map-factory/capability-evidence/rail-v3 -p 'test_followup.py'
uv run --directory tools/cs1-harness python -m unittest discover \
  -s ../map-factory/capability-evidence/rail-v3-followup-1 -p 'test_review.py'
```

These commands check retained evidence and continuation behavior. They do not
rerun the game. The initial stock checks and all prior selector revisions stay
separate. Service, sustained gameplay, human play and geographic impossibility
are not established by this study. File identity is not memory attestation or
strict no-mods; dynamic exclusions and reported errors remain in the receipts.

## Cleanup finding

The frozen `followup.py verify` command rejects Pittsburgh's non-empty Steam
teardown list. That original failure is retained in
`strict-verifier-failure.txt`. The receipt is not edited or reclassified as an
empty teardown. The later read-only `cleanup-audit.json` proves the listed
instance absent and all recorded owned game, collector and monitor processes
gone. Other owners' current Steam instances were not stopped.

`review.py` independently rechecks both raw manifests, unchanged native
sources, stock references, frozen requests, exact endpoints, context and
cleanup. It keeps Pittsburgh's teardown finding in its output and requires the
later audit. A missing audit, a live reported Steam remainder, missing cleanup
facts, or a game/unit remainder does not pass. See [Results](RESULTS.md).
