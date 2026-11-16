# Intake-observer feasibility probe

This is a CPU-only negative observability test, **not a game observer**. It
loads the installed Linux Mono runtime into a disposable child process and
executes an arithmetic fixture using the actual `FastList<WaterSource>` from
the installed game. It never calls `SimulateWater`, launches Steam/a game,
replaces a method, writes an installed file, or changes a map/control.

```bash
uv run --project tools/cs1-harness python tools/cs1-harness/examples/intake-profiler-probe/run.py \
  /home/caleb/experiments/PL-912-intake-observer/replay-unique
```

Use a new output directory. Required local tools are GCC and the harness's
cached .NET SDK; the script installs nothing. It fails closed on a different
engine/runtime hash, compiler/runtime failure, changed fixture computation,
dropped events or different observed accessor counts. Child calls have a
thirty-second timeout and finish before the script returns.

## Exact result on the hash-bound runtime

| Disposable process mode | Getter events | Setter events | Arithmetic checksum |
| --- | ---: | ---: | ---: |
| no profiler | 0 | 0 | 84100 |
| profiler installed before JIT | 0 | 0 | 84100 |
| profiler installed after first access | 0 | 0 | 84100 |
| profiler before JIT, inlining disabled | 580 | 580 | 84100 |

There are two passes over290 real `WaterSource` records. Entry and exit counts
must agree. In default-JIT mode, outer fixture calls are visible but inlined
accessors are not. Late registration also does not retroactively instrument
already compiled calls. `early-noinline` changes JIT optimization defaults in
that **CPU child only**, through the old runtime API; it is not installed in
the harness or authorized as an equivalent native game configuration.

The metadata-only mode hashes the installed solver's original IL without
executing or distributing it. `result.json` binds source, runtime, assemblies,
fixture and executable hashes and always reports
`atomic_intake_observer_ready: false`. A successful process is evidence that
the probe completed, not that the missing native observation was collected.

## Consequence for PL-912

The proposed default-JIT accessor observer is rejected before a game: it would
miss the required atomic source phases. Globally disabling inlining exposes
accessors in the fixture, but does not validate game initialization, state
copies, transport/source phase alignment or noninterference. Do not launch
Rio with it or infer exact native history from this fixture.

Harmony can insert callbacks while retaining calculations, but generates a
replacement method; that is outside PL-912's present instruction, “Do not
replace or reimplement SimulateWater.” No Harmony dependency, solver patch,
game observer or changed shipping default is included here.

A concrete alternative is an engine/IL-hash-pinned, observer-only insertion:
retain every original instruction/branch/store and add bounded copy callbacks
at the five required phases; mechanically strip those additions and require
the original IL/control-flow graph exactly. This needs an explicit narrow
exception to the no-replacement condition before implementation/use. It still
needs noninterference checks, native binding and ordinary tool review; this
probe does not claim those checks or authorize a game.

Primary API references:

- [Mono2.6 profiler header](https://github.com/mono/mono/blob/mono-2-6/mono/metadata/profiler.h)
- [Mono2.6 optimizer API](https://github.com/mono/mono/blob/mono-2-6/mono/mini/driver.c)
- [Harmony replacement execution model](https://github.com/pardeike/Harmony/blob/master/Documentation/articles/execution.md)

Do not redistribute the game runtime, assemblies or decompiled solver code.
