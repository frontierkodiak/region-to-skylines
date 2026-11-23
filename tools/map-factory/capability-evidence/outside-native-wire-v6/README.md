# Native wire integration, work in progress

PL-1321 is incomplete. Do not use this draft for a native opening.
The accepted v5 adapter and its refusal are unchanged.

`wire.py` implements the harness's one-connection, newline-JSON protocol.
It applies an absolute monotonic deadline to connect, send, receive and polling.
`runtime.py` collects literal controls over that client, retains partial failures
and unresolved handles, and uses the accepted consumer and inventory retention.
`entry.py` separates integrity checks from an injected external authorizer.
The supplied authorizer and session factory are explicitly constructed fixtures.
They grant no native authority.

`candidate.py` creates a new input-only inventory and cohort with the unchanged
old decoder, model, constants and eleven-package catalog. It does not execute
an old scorer or read holdout outcomes. It retains selected package bytes only
in the private evidence store. The candidate selects Cavern Coast for six-cell
coverage. That package remains unobserved.

## Run the public socket tests

```bash
module=tools/map-factory/capability-evidence/outside-native-wire-v6
uv run --no-project python -m unittest discover -s "$module" -p test_wire.py -v
```

These tests need no game, compiler, references or private evidence. They bind
only their own ephemeral loopback sockets and reap their fixture processes.

## Run the private integration checks

Use a task-owned copy of the accepted v5 evidence holding. Never mutate someone
else's store or put its package, DLL, compiler or reference bytes in Git.

```bash
module=tools/map-factory/capability-evidence/outside-native-wire-v6
run=~/experiments/PL-1321-native-wire
PL1321_RUN="$run" PL1321_FREEZE=candidate-11.json \
  uv run --offline --project tools/cs1-harness python -m unittest discover \
  -s "$module" -p 'test_*.py' -v
```

The private holding has immutable intermediate candidates. Each binds its own
source revision. A source change requires a new candidate, never an overwrite.
Build evidence is reused from accepted v5 after byte validation. No new compile
or game opening is claimed.

## Remaining work before peer review

- Enforce and prove session entry, launch, shutdown and whole-study cancellation
  with an external worker supervisor and exact PID/start joins.
- Complete the native study orchestration after fresh admitted controls,
  including the frozen holdout. The current collector exercises controls only.
- Audit the external authority contract and executable dependency retention.
- Complete the requested inventory, graph, context, argument, interrupted-send,
  pending-handle and release negative cases through the real entry.
- Produce the final reviewed invocation, immutable study freeze, complete
  metadata proof and historical-byte assertions. Refresh the candidate after
  executable changes.

The native session factory is uninvoked and is not a verified launch path.
Native admission, export qualification and all six old holdout cells are Unknown.
