# Proposed independent study v1

**Proposed, not authorized or executed.** Parent inspection of this source-only
artifact precedes a new result-bearing tranche. This is not a retroactive gate
on earlier authorized diagnostics or a request to retry PL-1294.

## What can change next

| Gap | Off-game action in this PR | New observation needed |
| --- | --- | --- |
| MetaBool truthiness | Explicit typed parser, original guard and Asanu regression | None to demonstrate parsing fix |
| RPC envelope omission | Parse exact body plus `ok`; preserve failure and post-control correction history | None to demonstrate schema fix |
| Missing or failed controls | Require every frozen control, no substitutions | Two independently opened controls with all 12 requests complete |
| Fresh context and constructor identity | Require PID/start, fresh frames, independent pre-call build index, exact masks/endpoints/seed/budget | New per-query build-index readback; not inferred from its response |
| Exact bridge and graph drift | Keep all xyz, prefab and Outside facts; reject drift | Fresh export/opening/pre/post all-mode snapshots with literal field equality |
| Native decision law and cost | Return Unknown with the missing fact | Independently measured predictions can falsify the hypothesis; agreement alone cannot prove a universal law |

The minimum experiment that changes the **control-readiness** result is two fresh
control openings with six queries each. It cannot qualify pre-export predictions.
The minimum next test of the unchanged predictor adds one fresh, previously
unqueried stock package with both predicted classes in every mode, six requests.
If no such package exists, use the bounded coverage selection below. This tests
18 to 30 literal requests total. Report the six package-mode/class cells, not a
single accuracy number. Any disagreement, Unknown, or exact-identity mismatch
prevents a new qualified claim for that cell. Even full agreement supports only
this finite, frozen request population. A universal place-model-to-game function
remains Unknown until its semantics are established independently.

## Freeze before collection

1. Capture the installed stock inventory once. Store sorted `(CRP SHA256, path)`
   records and the inventory SHA256. Keep paths only as locators.
2. Exclude duplicate package hashes, Blank CO, all prior nine geographic cases,
   both controls, all ten PL-1239 packages, and every PL-1294 selected package,
   including unsupported selections. Hash the explicit exclusion table and its
   source inventories. Exclude a hash even if its filename changes.
3. Use the unchanged pinned CRP reader and fixed eleven-package lane catalog.
   Decode once. Record unsupported inputs and all missing used facts. No decoder
   repair, catalog extension, threshold fitting, or stock physical-input/CPU
   lineage invention. Stock packages have CRP lineage only.
4. Enumerate literal boundary pairs with the pinned `study.candidates` semantics.
   IDs only locate fields and sort candidates. Order supported packages by
   `(CRP SHA256, path)`. First choose a package that covers all six mode/class
   strata. Otherwise greedily select the first package that adds an uncovered
   stratum, up to three packages. If six strata are not covered, stop Unknown.
5. In each selected package, order requests by distinct edge first, then `from`
   and `to` triples lexically. Choose the first request in each available
   `(mode, predicted success/no_path)` cell. Cap at six per package, 18 total.
   Freeze excluded, selected, unqueried and unsupported rows. No native label
   participates in selection. Do not reserve outcomes for later case swaps.
6. Freeze separate Asanu and Hanami control requests from their accepted stock
   inventories: one literal positive and one existing-lane invalid-vehicle
   rejection per mode, six per opening. These are new observations with new
   opening identities, not replacements for the failed historical Asanu opening.
   Keep the old six Unknown controls and all old labels unchanged.
7. Freeze source file hashes, reader/catalog/helper closure, exact protocol,
   constructor constants, request JSON, prediction JSON, CRP hashes, consumed-field
   coverage, exclusions, selection and stop policy. Use canonical JSON SHA256.
   `readiness.digest` defines compact sorted JSON for new bundles; do not confuse
   its encoding with the old study's indented JSON digests.
8. Freeze the parser and result schema **before controls**. Bind its tests and
   this PR head. The retained scorer correction occurred **after stock-2
   control outcomes**, as recorded in `analysis/source-fix.json`. Preserve that
   historical timing; it is not prospective validation of this new schema.

## Per-opening protocol for a separately authorized collector

This PR contains no collector, mod build, live deployment, queue acquisition,
Steam access or browser action. The following changes belong to the future
collector's own review, worktree and authorization.

- Open controls separately, then selected packages, one fresh process per package.
  Allow at most **5 openings, 30 path requests, 30 seconds per query, 10 minutes
  load time and 15 minutes total per opening, 75 minutes total**. Use a monotonic
  global deadline as well as the per-query deadline. Stop at the first failed
  control. No retries, budget sweeps, threshold sweeps, or case replacement.
- Use `NewGameFromMap`, `--noWorkshop`, declared mods-enabled launch behavior,
  traffic inversion false, fixed protocol version and Randomizer seed 857.
  The query budget is **100000**, not metres. Road uses car/Car/PassengerCar and
  Vehicle. Ship and air use Ship or Plane, category All, and the exact three lane
  types. Record the actual public overload, all defaults and literal positions.
- Before starting, bind build source closure to compiler/version, referenced
  assembly hashes, staged source hashes, DLL hash and MVID. Bind launch receipts
  to executable hash, command line, namespace and host PID/start, DLL loaded
  module MVID, required assemblies and exact protocol. No proprietary decompiled
  implementation may enter the repository.
- Capture full file inventories at launch, pre-query batch and post-query batch.
  Include executable, Managed, Mono, built-in and user Mods roots, every plugin
  root, loaded assembly files, plugin names/paths/enabled/builtin state, dynamic
  exclusions and unresolved assemblies. Require exact frozen key sets and file
  hashes. Zero enabled plugins is not proof of no loaded code. File identity is
  not memory attestation and is not strict-no-mods evidence.
- Capture the exact export and opening graph, all modes and full key sets. Require
  equality before querying. At every request, capture pre/post all-mode snapshots,
  hashes, native context, frame and independently read current build index.
  Reject graph changes, stale/reversed frames or context changes. Do not excuse
  air drift on a road request by dropping air from the identity.
- Keep transport replies and native result bodies intact. Record start/result
  handle, effective constructor arguments, flags, completion, success, release,
  full returned positions and exact first/last triples. A missing body, unsupported
  representation, timeout, error or unreleased handle stays Unknown.
- Join every owned collector/driver/auditor/monitor. Record each PID/start identity,
  child discovery and final absence, including the game and namespace/host mapping.
  Record queue release and cleanup receipts. Compare the process-role set, not
  just a cleanup-success boolean. A reused PID without its start identity is not
  proof. Leave no run-owned work after completion.

## Readiness bundle and stop rules

`check.py bundle --input BUNDLE.json --evidence-root DIRECTORY` consumes version 2,
controls, observations, frozen runtime policy and prior session IDs.
[SCHEMA.md](SCHEMA.md) defines the exact schema and required retained artifacts.
Version 1 from rejected head `d39a31e` is not a collection prerequisite. It has no holdout-label input.
`test_support.constructed(store)` is the executable schema example, clearly marked
CONSTRUCTED. Its readiness result never activates a real certificate.

Each frozen control supplies requests, exact graph hash, source-file map and hash,
prediction map and hash, protocol hash, CRP hash and every key in
`readiness.CONSUMED_COVERAGE`. The frozen policy supplies complete file/root/plugin/
assembly maps, dynamic exclusions, source/DLL/protocol hashes and all five process
roles. Each observation supplies fresh session ID, exact bindings, entry context,
three runtime inventories, opening/post graph hashes, full control paths with
pre/post context and graph hashes, independent pre-build index, and PID/start
cleanup maps. The future collector adapter must retain the referenced byte artifacts. The
checker rehashes those bytes, validates required facts before equality, and
derives consumed-field values from the retained inputs. It cannot authenticate
a caller's measurements or attest executing code. Extending the collector/source
closure requires a reviewed schema version and a new pre-control freeze.

Stop Unknown on a missing field, missing source, decode/catalog ambiguity,
changed context, changed graph, failed control, mismatched request, incomplete
inventory, unresolved assembly, changed plugin state, missing PID/start cleanup,
source/request/prediction hash change, unsupported envelope, deadline or count
limit. Preserve the failed opening and all planned-but-unobserved requests. A
post-control schema change requires an explicit new study version and freeze,
not edited old outcomes. No named-case exception is permitted.

No result here asserts geography, service, spawning, continuous clearance,
sustained navigation or stable water. Water-writer work and native evidence-page
integration remain with their existing owners.
