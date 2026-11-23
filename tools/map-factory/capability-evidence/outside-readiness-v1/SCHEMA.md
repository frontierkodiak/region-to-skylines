# Readiness bundle schema v2

Version 1 at `d39a31ea8636967e4c398d09ed5c7994d399260e` is rejected.
Its equality comparisons admitted shared missing facts. Its earlier peer PASS
does not apply to this correction. The original acceptance script, five-failure
log, malformed CONSTRUCTED bundle and local reproduction are preserved under
`rejected-d39/`. The module manifest binds those files without rewriting them.

## Evidence boundary

Run `check.py bundle --input BUNDLE.json --evidence-root DIRECTORY`.
The directory contains retained files named by lowercase SHA-256. The checker
reads and rehashes each referenced file. It does not read installed game files,
launch a process, collect new data or write into the evidence directory.
Missing files, empty files and wrong bytes fail closed. A SHA-256 declaration
alone is not evidence. The CLI rejects version 1 and unknown bundle keys.

`test_support.constructed(store)` creates the executable v2 example. Its source
files are retained repository bytes. Its runtime file contents, graph and fresh
context are CONSTRUCTED. They do not claim a real executable, DLL or CRP, and
cannot qualify native observations. Its readiness result remains distinct from
pre-export qualification, which is always Unknown.

The outer object has exactly `version` (integer 2), `controls` (nonempty list),
`observations` (map keyed by control case IDs), `policy` and `prior_sessions`
(a list of unique nonempty session IDs). Duplicate control case IDs fail.
The direct Python boundary requires an `ArtifactStore` and a set of prior IDs.
Malformed arguments produce reasons rather than a ready result.

## Required frozen and observed facts

`schema.FROZEN` and `schema.OBSERVED` define exact field sets. Extra fields are
errors, not ignored facts. Observations require explicit `error: null` when no
error occurred. Every artifact, source, request, prediction, protocol, graph and
consumed-field hash must be a nonempty lowercase 64-digit SHA-256 with matching
retained bytes. Null expected values cannot match absent or null observations.

Source, request and prediction manifests must match their canonical retained
JSON bytes. `schema.canonical` defines the encoding. The source manifest has the
independently named 20-file helper and public-producer set in `schema.SOURCE_KEYS`.
It cannot omit a helper from both the manifest and the observation.
The declared source bytes must match the accepted pins or this versioned module. Adding a
future collector requires a reviewed schema version and source freeze that
includes that collector. The checker does not infer an unimplemented collector.

The control plan contains exactly one positive and one invalid-vehicle request
for each mode, six unique request IDs. Predictions have exactly those IDs and
supported values. Literal request fields, protocol constants and constructor
arguments remain explicit. A missing control or replaced request fails.

Graph artifacts have all three mode keys and complete segment and lane records.
Every consumed-field record has exactly `field`, `graph_sha256`, `source_sha256`
and nonempty `values`. The checker derives the expected values from the retained
graph, source manifest, protocol and requests. It rejects a valid hash pointing
to unrelated or inconsistent evidence. This validates input coverage, not the
native truth of a model prediction or an independent prefab asset interpretation.

## Runtime inventory and cleanup

Policy and phase inventories have exact field sets in `schema.POLICY` and
`schema.PHASE`. File maps contain normalized absolute runtime path names and
byte-backed hashes. Executable and DLL paths must be entries in those maps.
The DLL hash must match its actual retained file. Every assembly has a path,
byte-backed hash and UUID MVID, and must match its inventoried file. The harness
assembly, plugin and DLL paths must form one chain.

Root roles are independently required, even when omitted from every supplied
map: `managed`, `mono`, `builtin_mods`, `user_mods`, plus `plugin:NAME` for every
plugin. The first three paths derive from the executable's game directory:
`Cities_Data/Managed`, `Cities_Data/Mono` and `Files/Mods`. The user root ends in
`Addons/Mods` and is separate from the built-in root. Unknown root roles fail.
Each root lists its nonempty file set. Membership is recomputed from the complete
file map. All files must belong to a declared root or be the executable itself.

Plugins require explicit path, enabled and builtin facts with JSON booleans.
Assemblies require explicit file and MVID facts. The only supported dynamic
exclusion is the retained anonymous dynamic-method assembly. Unresolved entries
fail. Launch, pre and post inventories must match the frozen policy and retain
the same game PID/start identity.

Owned-process and cleanup maps require all five roles: game, driver, collector,
auditor and monitor. Identities cannot be reused across roles. Each record has
exactly PID, start ticks and literal `gone: true`. The game identity must agree
with the runtime inventory. These are retained identity receipts, not a live
process check or permission to terminate a process.

## Limits

Byte verification proves that the declared evidence exists and agrees. It does
not authenticate the collector, prove that a compiler used the declared sources,
attest a loaded MVID from DLL bytes, inspect game memory or establish strict
no-mods operation. Those observation and build provenance responsibilities remain
with the separately authorized collector. No synthetic or caller-supplied bundle
can turn this module's Unknown pre-export qualification into a certificate.
