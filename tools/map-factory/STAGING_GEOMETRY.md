# Prepared geometry binding before acceptance references

2026-11-11 offline fix, based on `f494ff65b8a08515871dc33fede7544d20851edd`.
No native work or candidate/golden replacement.

`stage_prepared()` previously checked the regenerated CRP/plan, then independently
read mutable `geometry.json` to construct flood references and the geographic
frame. That file does not enter `write_map()` when replaying a frozen plan.
Keeping the exact candidate and changing only geometry to a map-covering lake
could therefore generate an all-one, self-hash-valid expected-water mask.

## Guard and archive

Before creating the staging directory or generating any package/reference:

- Every resource/plan candidate must have a valid saved
  `generation.resources.prepared_geometry_sha256`. Missing/malformed bindings,
  missing geometry, or changed bytes fail closed. Removing the resource metadata
  cannot bypass this while a resource plan remains.
- Existing declared `generation.source.inputs_sha256["geometry.json"]` is also
  enforced, including on unpainted inputs.
- Legacy unpainted inputs without any declared geometry hash retain their prior
  optional-geometry behavior; no resource-candidate opt-out flag is introduced.

The validated bytes are read once, copied **unchanged** into the staging bundle
as `maps/SLUG/geometry.json`, and used in memory for both mapped-water and world
references. `staging.json.geometry` and frozen
`probes.json.mapped_water_provenance.source_geometry` record the raw-byte SHA,
filename, generation field(s), and binding mode. The existing normalized semantic
geometry hash remains unchanged and distinct from this exact-file binding.

The filename in that receipt is relative to the staging bundle containing
`staging.json`. Retain `maps/SLUG/geometry.json` alongside run evidence; this
writer-only fix does **not** add a harness copy into each individual run directory.
No flood tolerance, mask rasterization, probe, portal, source or package policy
changes here. Exact hashes bind provenance; they are not hydraulic exact-digit
thresholds.

## Verification

```sh
MAP_FACTORY_PREPARED_CASE=/path/to/exact/resource/candidate \
  uv run python -m unittest discover -p 'test*.py'
```

Eleven tests pass, including the optional exact-candidate corruption test on the
selected Rio candidate: copy the full candidate, modify **only** geometry by adding
a map-covering lake, and require rejection before package generation, references
or native invocation. Five focused binding tests also cover missing/malformed
bindings, missing geometry, unchanged exact bytes and legacy unpainted behavior.

A full offline staging pass used all five current `surface-final-candidates` and
`surface-final-selection.json`. Each source geometry already matched its saved
resource binding. All regenerated CRPs match the selected hashes, all expected-
water masks are byte-identical to the pre-guard rasterizer output, and every
archived geometry matches the source bytes. Receipts and the executable check:
`/home/caleb/scratch/2026-11-11-pl857/geometry-binding/{verification.json,verify.py}`.

| Region | Unchanged selected CRP SHA-256 |
|---|---|
| Asheville | `4409846c62af4cc336c13261f1590872f0685d0783c48eebae50f93284ed2251` |
| Innsbruck | `97833522e5bf06c5f8f508ce49109db229fc941a029cd46f5a819c9c7ba12b66` |
| Rio | `117b4d16179853c19527891b55e431ec6559aa47c44add346bd2665024777555` |
| Pittsburgh | `0e0673e898c13972b57923cbbb4221dbfc2bd3b745f50911288beb782f5eb8ce` |
| Charleston | `8f5b5268f00aa7eb789727ea0f98753b4c90d62d23ddbdb8a9f6fa8c3dc25c2c` |

Changed Python files pass Ruff check/format; diff check passes. No Steam, browser,
server, native compilation, game-cache writes, active-batch edits or remote writes.
This does not judge the ongoing native runs or establish hydraulic acceptance.
