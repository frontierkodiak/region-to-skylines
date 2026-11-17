# Native water tracing

Use this to answer what the installed solver did at selected native grid nodes
and natural sources. It records observations, not a second water simulation.
It is separate from map admission and never selects qualification probes or
changes a gate.

## Scope and installation

Only Blade's disposable harness install on silent private display `:57` is
supported. Honor the current slot queue, holder, Steam account and reservations.
Never install it on carbon, in a shipping map/package, or during Caleb's play.
Keep the owning script in the foreground and collect its cleanup receipt.

The observer is opt-in at build time:

```sh
uv run cs1-harness build --trace-harmony /path/to/net35/0Harmony.dll
```

The accepted dependency is **Lib.Harmony 1.2.0.1, lib/net35/0Harmony.dll**,
SHA256 `e271d22a7c32bfca105d0e471c04eee14eec6142d37a30cd73cb7d32c7d1dd0f`.
The NuGet archive SHA256 is
`078425e55e36bc1d068c3df94b31446aae4c3ef772fe546d10dcb2713514ec75`.
It is not vendored or downloaded automatically. Later library versions tested
on this Unity Mono runtime failed their CPU patching fixtures; do not substitute
one or change global JIT flags.

The installed engine is pinned to
`c7f0e723dfe867d10aef73f14268bcf9f5ea4bab1c5ce4987897ed27f46511a1`,
the Linux Mono runtime to
`4cfea7a0d01dcaec3ca23380106a109f6a97659302675388fc06aa42ec7252b2`.
The original solver IL hash is
`eef2d18b29f0ff396b792dd45ec06c26c5181652985975a7cd93b9e46bb432bc`.
Unexpected hashes, pre-existing solver patches or changed physical controls
fail closed. Unity may load mod assemblies from bytes, leaving `Assembly.Location`
empty: runtime checks use the pinned disposable file plus loaded module identity,
not a fictitious assembly path.

The recording region and touching-source set are planned before arming, outside
the solver. Water-thread callbacks only validate the expected catalog and copy
bounded primitive snapshots into preallocated private storage.

## Choose the observation

Prepare the complete control table from the unchanged CRP **before** acquiring
the slot. From the repository root:

```sh
uv run --project tools/map-factory --locked python tools/map-factory/prepare_water_trace.py \
  /path/to/map.crp --sources 92 163 164 --out /path/to/trace-request.json
```

Source IDs are native, one-based IDs, not browser geometry IDs. This example is
Rio's first investigation, not a built-in selector. `--cells cells.json` accepts
an array of `[x,z]` world coordinates on the exact 16m native grid. Choose sources,
cells, or both. Source selection records each complete input/output footprint
and its one-node halo; explicitly supplied cells record those nodes. Do not round
off-grid coordinates silently. Trace regions are limited to512 nodes and32
intersecting sources; the first version supports only natural type1 sources.
Larger/unsupported regions fail rather than producing a partial success.

In an **already queue-owned disposable Session**, before loading that exact map:

```python
request = json.loads(request_path.read_text())
request["dependency_path"] = str(cfg.mod_dir / "0Harmony.dll")
# Add observer source/package/input/probe/request hashes to request["binding"].
armed = session.client.call("trace_arm", **request)
# Use the ordinary map load and run/capture operations, retaining the full cohort.
```

`trace_arm_loaded` arms the same observer in a paused disposable city. Arming is
once per process. The full control catalog must match the loaded state, and it
is rechecked on every recorded update. The package hash in the request must
also be checked by the owning driver against its installed map.

For a flood window, select an existing failing component under the original
reference-water/mapped-water mask before acquiring the slot. The reusable
`cs1_harness.flood_region` functions retain that predicate and close the region
over every touching source's complete input/output footprint plus halo. A
cells-only region with no touching sources is valid: its direct source terms
are zero, not evidence that remote supplies are inactive. Oversized regions
fail; the whole-map acceptance mask does not change to make a region fit.

After collecting an unchanged-package loaded-city window and empty cleanup:

```sh
uv run python -m cs1_harness.flood_region \
  --run /own/run --reference /original/reference-water.u16 \
  --mapped /original/mapped-water.u8 --plan /own/region-plan.json \
  --hydrology /unchanged/hydrology.json --out /own/flood-region-report.json
```

The report replays the actual trace, closes local published storage against
source input/output and net transport, and reports whole-map and selected
flood area/depth, starting-tile overlap and conservative native transport
segment-bounds overlap. It rejects unexplained publication carry or budget
residuals. Bounds overlap is not a path-blockage verdict; keep actual native
path results separate. Net transport is not a reconstruction of face flux
or the provenance of water from distant sources.

After pausing, call `trace_finish` with an absolute staging directory. A paused
water thread can remain inside an update waiting for render progress, so waiting
for the entire solver to become idle is not a valid export contract. The recorder
publishes an immutable completed-update prefix with a memory barrier, and checks
that its last published cells and buffer cycle match a fresh native `BeginRead`
checkpoint. Any unfinished, unpublished tail is counted explicitly and never
read while mutable. A mismatched endpoint is an incomplete diagnostic.

The hook remains loaded until the owning disposable Session ends; it is not
repatched while a water thread may be executing its copy. Normal process teardown
and ephemeral mod removal provide the removal receipt. No file I/O occurs in the
solver or its source lock, and no engine timing/status fields are changed to make
the water thread finish.

```python
finished = session.client.call("trace_finish", dir=str(stage / "atomic-trace"))
assert finished["complete"]  # Completed-prefix coverage, not map acceptance.
# End the disposable Session and verify its empty cleanup receipt before delivery.
```

There are at most512 recorded updates (`max_steps` can lower this limit).
Hitting a bound, missing a completed-update phase, changing controls or failing
disposable cleanup is an incomplete diagnostic. Retain and diagnose the failure; do
not relabel it a map-gate failure or discard it from the history.

## Read and audit

`trace.jsonl` contains a header and one transaction per water update. The header
binds engine, inverse-IL proof, selected world nodes, controls and caller-supplied
provenance. Primitive depth/floor values are unsigned native units (1/64m);
velocities are signed16-bit values packed as unsigned16-bit bit patterns.

Each transaction records:

- Published input to transport, working state after transport, and source-end
  working state.
- Pre-input, post-input and post-output cells for every intersecting source,
  in original source order, plus local and committed source counters.
- Native availability/nominal locals for positive-rate inputs, frame/step/buffer
  indices and the actual published-end cells. Locals for a zero-rate input are
  not meaningful intake calculations.

Run the reusable offline audit from the harness project:

```sh
uv run python -m cs1_harness.watertrace /path/to/trace.jsonl \
  --receipt /path/to/session-receipt.json --out /path/to/audit.json
```

It recomputes natural-input signed arithmetic and cellwise integer removals,
checks source deltas and publication closure, and reports any mismatches.
This does **not** derive the transport flux equations, prove a changed terrain
safe, or qualify a map. Keep fixed-state counterfactuals distinct from forward
predictions. Do not offset losses with gains or infer inactivity from zero output.

## Preservation and cleanup

`TraceIL` adds calls but preserves every original instruction, branch, store,
label and exception boundary. Stripping those exact added instructions must
reconstruct the original canonical instruction/control-flow digest. CPU examples
under `examples/intake-profiler-probe` test this on the exact runtime without
executing the copied solver. `TraceFixture` is explicitly synthetic: it checks
configuration, callback completeness and that its supplied buffers stay unchanged.
It is never native hydraulic evidence.

After the trace, restore the ordinary build:

```sh
uv run cs1-harness build
```

That removes the build dependency and compiles the observer types/ops out. Verify
the ephemeral installed mod is gone and the cleanup receipt is empty. No original
installed DLL or global JIT setting is edited. Do not redistribute game assemblies
or proprietary decompiled code in the repository, reports or attachments.
