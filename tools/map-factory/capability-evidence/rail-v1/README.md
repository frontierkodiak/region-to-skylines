# Directed rail calibration · PL-1215

This is a separate harness study on accepted native source
`29b095475ba2f93c7e918fefc08c736493670304`. It does not change the parent's
capability ledger, packages, exporter, certificates or UI. Stock controls are
not members or replacements of the original nine-square geographic cohort.

## What the native query tests

`NetworkOps.path_start` passes two exact `[segment, lane index, offset]`
positions to the game's `PathManager.CreatePath`. For `mode=train`, it requests
Train vehicle type, all vehicle categories and Vehicle/TransportVehicle/
CargoVehicle lane types, with a 100,000-unit maximum length and seed 857.
The harness polls the returned unit, retains its flags and positions, and
releases every completed path. It does not create a train, a station, an
outside service or a sustained gameplay session.

The old sweep sampled every Train-typed lane combination on selected outside
segments, with boundary/midpoint offsets and both directions. Its component
filter was undirected. Retaining lane directions was not the same as selecting
direction-compatible lanes. Consequently, native failure of those requests
cannot distinguish a disconnected railway from an inappropriate lane/endpoint
or path protocol. Rio's 48 and Hong Kong's 16 historical failures stay intact
and Unknown.

The new planner enumerates source lanes travelling away from their outside
node and destination lanes travelling towards theirs. Forward/Backward is
swapped for a segment's Invert flag. It requires a compatible native lane type
and Train vehicle type; missing inventory fails closed. It prefers different
map edges, sorts by native segment/node/lane identifiers, and takes at most 128
directed boundary requests. Each has a matching midpoint diagnostic. It also
reverses the first boundary request **without changing its lanes**, a
wrong-direction diagnostic on one-way lanes (not assumed invalid on a
bidirectional lane). Reciprocal valid requests use the reciprocal lanes, not
just swapped endpoints. No undirected-component test filters this study.

The direction rule is a candidate model, not asserted game semantics: stock
native paths calibrate it. Success requires completed/released native success
and exact first/last segment, lane and offset. A midpoint or returned endpoint
mismatch never becomes a literal-boundary witness. An exhausted finite set of
failed queries still does not establish geographic impossibility.

## Frozen selection and runtime binding

`selection.json` freezes protocol, all runtime tool sources, build receipt,
104 stock-package hashes and the unchanged nine-case selection before launch.
The stock rule chooses the first two builtin filenames with positive incoming
and outgoing train metadata: Asanu Beach and Hanami Bay. CO.crp, the system
editor package, is excluded exactly as in the original 104-map survey. Native
lane inventories, not that metadata, determine whether there are real probes.
Neither failed stock control is replaced.

Each opening writes an exclusive, fsynced `query-freeze.json` before any query.
It binds the complete network snapshot, endpoint/lane inventory, predictions,
ordered requests, package, protocol and running file identity. Every submitted
request is dated. The cohort action refuses to run until both stock controls
have completed and at least one has an exact directed literal-boundary path in
a bound context. Cohort lane enumeration is frozen at each opening only after
that stock gate. Source or build changes require a separate new freeze/study.

Launch and opening bind the actual executable and full resolved loaded-assembly
file inventory through the rendering process's namespace PID/start identity.
Both snapshots retain builtin/bridge/harness plugin flags, errors, launch
arguments and dynamic-assembly exclusions. Unresolved file assemblies fail
closed. Dynamic assemblies remain excluded: this is FILE identity, not memory
attestation or strict no-mods. Native NewGameFromMap and non-inverted traffic
are read back, not inferred from the wire-protocol number. New bytes do not
inherit old certificates.

## Reproduce

From the repository root, verify compressed and uncompressed raw hashes,
source identity, package bindings, frozen enumeration, dated query prefix,
runtime context, endpoint outcomes and cleanup:

```sh
uv run --directory tools/cs1-harness python \
  ../map-factory/capability-evidence/rail-v1/verify.py
uv run --project tools/map-factory python \
  tools/map-factory/capability-evidence/outside-v1/verify.py --require-nine-attempts
```

This replays evidence interpretation, not the game. No proprietary assemblies,
decompiled code or stock package binaries are included.

A new live study on blade uses the same deterministic rule and original
packages, not rebuilt or recaptured inputs:

```sh
uv run --directory tools/cs1-harness cs1-harness build
uv run --directory tools/cs1-harness python -m cs1_harness.rail_study prepare --study RUN
uv run --directory tools/cs1-harness python -m cs1_harness.rail_study controls --study RUN
# Only after the stock-positive gate; --only SLUG permits one foreground opening.
uv run --directory tools/cs1-harness python -m cs1_harness.rail_study cohort --study RUN
```

All game steps use the existing fair queue with zero wait, fresh offline/idle
guards and session cleanup. Busy or failed openings are retained, never erased
to retry. No detached collector, account/install/security change, map repair,
legacy access-path rescue or physical package rebuild is part of this study.
