# Rejected bank-restoration experiment

**Do not promote this arm.** It did not earn Rio's visible fix and lost native
wet-bed support between unchanged wet grid vertices. Default generation and
`fixtures/minor-stream-candidate/` have been restored byte-for-byte to `690d2b1`.
The rejected function is isolated in `bank_restoration_experiment.py`; it is
not imported by the shipping writer. Its fixtures remain available at tested
commit `debf9abe9874764183d54abd37fbc0806cfe9671`, and their hashes and audits
are retained under `fixtures/bank-restoration-rejected/`.

## What was tested

The hypothesis restored dry excavated margins to the actual uncarved DEM after
feasible hydraulic fitting, without a width parameter. It retained modeled wet
vertices, mapped surface lines/polygons, source centres and below-target source
footprints, including the native height-quantization boundary. Underground
pieces were not surface support. No native observation or named pixel was an
input to the rule. With no actual uncarved DEM it made no restoration.

All five candidate maps were regenerated and matched the shipping JS/Pyodide
path byte-for-byte, including complete CRPs. Compared with the previous
candidate, initial water and the native WaterSimulation component were exact:
source Y, target, input/output rate and startup water did not change. There was
no terrain lowering, no changed initially wet terrain vertex, no changed probe
or mask, and no horizontal network movement. Network heights and resource plans
refit to the terrain and therefore required fresh qualification.

| Region | Changed terrain bytes | Changed cells | Maximum raise, m |
| --- | ---: | ---: | ---: |
| Asheville | 49,590 | 36,149 | 9.328125 |
| Innsbruck | 22,108 | 17,221 | 5.765625 |
| Rio | 30,347 | 23,211 | 58.234375 |
| Pittsburgh | 45,307 | 33,832 | 9.6875 |
| Charleston | 58,460 | 52,857 | 12.109375 |

Those checks were necessary but insufficient. The raw historical
`vertex-only-audit.json` calls unchanged wet vertices “wet floor”; that wording
must not be read as a continuous native-bed guarantee.

## Native rejection

Full zero/five-minute opening and actual Areas captures used the normal Blade
2080 Ti / private `:57` slot, accepted silence controls and no camera overrides.
The before/after camera poses and projection match exactly for both modes and
phases. Ordinary tutorial guides were closed through their native close-button
handlers, never by hiding UI or answering an account/cloud prompt.

Both five-minute cases tested `debf9abe9874764183d54abd37fbc0806cfe9671`:

| Case | Game minutes | CRP SHA-256 |
| --- | ---: | --- |
| Asheville | 5.090556 | `3d82ece0d6db0b4fe77de719b1bbb5ba8ef6dfb7eee63620ac7509f76b2861a1` |
| Rio | 5.093611 | `31c5013d10e5a5ffecf3997ade34b1c4c0b22e3c20d6fb4671ec049bda3a7478` |

Rio's final zero-minute opening and Areas review images were recaptured paused
under driver head `109dee334660299e2bba417b7d45e97ef26baf39`, with the same full
CRP and exact baseline camera. The guide appeared during the earlier opening
capture; post-capture tutorial checks now prevent that race. This replacement
advanced no simulation and is not an additional five-minute receipt. The native
DLL in the final review cases is SHA-256
`d1451d5ece70343d34ef9481d2125419b4d96bce0f136b0fa6a07a67dc36bc2d`.

Asheville's former western opening cut remains grassy. The French Broad centre
is 2.484375 m deep initially and 2.890625 m at the endpoint. Other minor scars
remain visible in Areas; this is not whole-map acceptance.

Rio still reads as a sandy cut. Restoration steepens its exposed bank instead
of delivering the required visibly wet opening. More importantly, same-world
native samples falsify the supported-floor assumption:

| Observation | Old ground, m | New ground, m | Old startup depth, m | New startup depth, m |
| --- | ---: | ---: | ---: | ---: |
| Elbow north bank | 86.937500 | 87.890625 | 0.750000 | 0 |
| Apparent round gap | 88.671875 | 89.937500 | 2.062500 | 0.796875 |
| Elbow centre | 88.390625 | 88.437500 | 0.921875 | 0.875000 |

The elbow north-bank world position is `(-1299.890380859375, 3617.747802734375)`
(see raw receipt for the authoritative binding). A positive depth elsewhere or
within 64 m does not repair this loss. At five minutes the fixed-world depths
are 1.484375 m at the horizontal centre, 2.375 m at the elbow, 0.8125 m at the
diagonal and 0.265625 m at that north bank. These samples are regression
observations, not a production mask or visual acceptance.

## Mechanism and smallest next correction

Offline inspection of the installed `TerrainManager.SampleWaterData` method
confirms that it reads four `m_blockHeights` vertices and performs fixed-point
bilinear interpolation. The assembly SHA-256 is
`c7f0e723dfe867d10aef73f14268bcf9f5ea4bab1c5ce4987897ed27f46511a1`.
IL `0000–00A2` selects the vertices; `02B1–033A` computes ground. The standalone
inspection source and raw IL are in the readback archive.

`native_water_ground` replays that arithmetic and matches **all 44 native ground
values in 22 old/new pairs exactly**. Raising a nominally dry neighbour raises
the continuous bed, even while the wet vertex, source centre and water bytes
stay unchanged. This is not a source-target or sample-binding discrepancy.

The smallest next correction is to preserve every terrain vertex contributing
to a modeled wet interpolation patch, and the complete continuous source
headroom footprint, before restoring a dry shoulder. Derive this from modeled
feasible stage and the native sampling stencil, not native observed water or a
universal physical width. `require_continuous_floor` is a conservative CPU
fail-fast guard for the incident bilinear patches; it now rejects this arm in
all five maps. It is not an acceptance/carve mask, and does not model the
renderer's separate smooth-height or shoreline shader.

That correction is proposed, not implemented as a new default or claimed to
fix the visible scar. It would need a new matched short native comparison;
if only steep sandy banks remain, a bank-only approach has not earned further
qualification. Do not raise heads, deepen the floor or relax probes to force a
pass.

## Verification and limits

- 43 Python tests pass (2 skips), including new continuous-bed counterexamples;
  112 harness tests, scoped lint/format, installed-game build and doctor pass.
- The earlier rejected 24 m arm is rejected by the CPU wet-floor check: 9,346
  initially wet vertices changed. The present arm passes that old vertex-only
  check but fails the new continuous-support guard, as intended.
- Full five-map Python/shipping-JS agreement passes for the rejected arm and,
  after quarantine, for the restored default candidate. Accepted-golden fixtures
  and their qualification history were not promoted or relabelled.
- **No 60-minute soaks or new highway/rail path qualification were started.** The
  conditional visible/support gate failed. All five changed default candidates
  still need fresh 60-minute, path and visual qualification before acceptance.
- Accepted `NATIVE_FINDINGS.md`, hashes, masks and thresholds are unchanged.
  Rio's flooding and Charleston's terrain-correlation failure subsets remain.
- PR #41 stays draft. The bounded failed-arm result returns for PM judgment;
  the overall user-visible water task is incomplete.


## Recorded commands

To reproduce the rejected generator, use its immutable tested head in an
isolated worktree, not the current quarantined default:

```sh
uv run --project tools/map-factory python tools/map-factory/minor_stream_candidate.py "$OUT/candidate"
node tools/map-factory/verify-candidate.mjs "$OUT/candidate"
uv run --project tools/cs1-harness python tools/map-factory/native_opening_diagnostic.py "$OUT/candidate/inputs/rio" "$OUT/rio" --interactive --requests "$RIO_REQUESTS"
uv run --project tools/cs1-harness python tools/map-factory/native_opening_diagnostic.py "$OUT/candidate/inputs/asheville" "$OUT/asheville" --interactive --requests "$ASHEVILLE_REQUESTS"
```

The paused replacement used the later driver and the same Rio package with
`--minutes 0`. The capture-only branch never unpauses. These commands record the
completed foreground unit; a new native unit needs its applicable PM release.
