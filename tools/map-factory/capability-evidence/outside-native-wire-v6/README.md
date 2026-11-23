# Native wire integration — parked WIP

PL-1321 was parked by the parent owner in comment
`01a20a49-06d4-7dd1-be9d-6767a43056b0`: PL1119 now pursues visible
open-data connection rules. Do not use this draft for a native opening or
continue it without renewed scope. PR97 remains draft against `PL-1142-native-v2`.
The accepted v5 adapter and its non-recording refusal are unchanged.

## Current implementation

The new entry validates source/build/input/request/budget integrity before its
factory effect boundary. Constructed authority is separate from a native
provider that reads two exact authenticated parent records using the existing
Multica CLI. No native acceptance or opening authorization exists.

`wire.py` implements the actual one-connection newline-JSON protocol with
absolute connect/send/read/poll deadlines. `runtime.py` maps actual operations,
checks independent BuildIndex immediately before path_start, retains raw bytes,
partial observations and unresolved handles, and uses unchanged v5 policy and
consumer logic. Completed path_result acknowledges release; no release RPC is
invented. Strict JSON/type checks precede legacy graph normalization.

The constructed path runs a finite loopback server plus separate collector,
driver, auditor and monitor processes. The external owner joins them and reads
actual PID/start/exit/absence. An owned pidfd lock-lease probe preserves an
already-held original guard through cancellation; it never acquires the lock
for a worker. This is constructed OS evidence, not native lifecycle evidence.
The study simulator runs two fresh controls and frozen input-only holdout cases;
all results remain Constructed, admission/export qualification Unknown.

The future native orchestration, slot/staging/Session adapter and Flatpak
ownership shim are implemented but UNINVOKED. They are not a verified launch
path. In particular, cli.slot enters the original Session before yielding it;
Session.__enter__ can call its original stop on startup failure before our
instance delegates are installed. That original stop uses display-wide PID
termination. Startup supervision/cleanup fidelity therefore remains unresolved.
No old module/global patch was made to conceal this gap.

## Verification snapshots

At executable revision `988ddcaeb73bb76ba3184dcebc60be6f8cca6b75`, private
`candidate-13.json` passed 22 tests, including a full constructed study. The
private holding is `~/experiments/PL-1321-native-wire`; candidates are immutable,
source-specific WIP snapshots, not authority. Build evidence reuses the accepted
v5 compile after exact byte validation; no new compile occurred.

The later parked source passed 15 public tests and Ruff/format checks. Its new
opening/whole-study integration test and latest protocol changes have NOT had a
fresh private-suite run. Candidate13 does not bind this later executable source.
A resumed task needs a new candidate and fresh private verification before any
review or future use. Do not overwrite an older candidate.

## Portable tests

```bash
module=tools/map-factory/capability-evidence/outside-native-wire-v6
uv run --no-project python -m unittest discover -s "$module" -p test_wire.py -v
```

These use only finite task-owned Python processes and ephemeral loopback
sockets, no game, licensed inputs or compiler. Private byte checks require the
separately held evidence store and an exactly matching immutable candidate:

```bash
PL1321_RUN=~/experiments/PL-1321-native-wire PL1321_FREEZE=candidate-13.json \
  uv run --offline --project tools/cs1-harness python -m unittest discover \
  -s "$module" -p 'test_*.py' -v
```

That example applies ONLY to revision988, not the parked head. Never copy
licensed package/DLL/compiler/reference payloads into Git or attachments.
No game/Steam/queue/native opening, browser, physical build, manual deployment
or Shelf action was performed. All six old holdout cells remain Unknown;
old observations are unchanged. File identity is not memory/compiler
authentication or strict-no-mods. Dynamic assembly exclusions and the three
historical DLC errors remain limitations.
