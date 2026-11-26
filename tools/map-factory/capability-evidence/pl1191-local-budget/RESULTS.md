# Localized water failures and source-budget experiment

The source-budget change did **not** produce playable stable water. Keep this
constructor experimental and unmerged. PR99 and PR107 remain unchanged drafts.
No public deployment or terrain-drama transform was made.

## Where PR107 fails

The similar 1.01 km² peaks are not one common flood patch. Asheville has 122
flood-union components; Pittsburgh has 41. Only 16 Asheville flood-union cells
are within 128 m of the map edge; Pittsburgh has none. The largest patches are:

- Asheville: Gashes Creek/tunnel vicinity, French Broad low bank, Swannanoa low bank.
- Pittsburgh: two Allegheny north-bank patches, then Monongahela/road-grade vicinity.

Most flood cells are on unraised ground. Road grading overlaps 118/5,722
Asheville and 166/4,653 Pittsburgh flood-union cells. Tunnel proximity overlaps
458 and 739 cells respectively, not an exclusive or dominant explanation.
Sources cannot be assigned as the cause merely from distance: the flood check
already excludes the initial wet/mapped-water margin around many sources.

Of the authored bodies losing retention, 44/49 Asheville and 55/60 Pittsburgh
contain no source. These are mostly disconnected stream reaches in the initial
raster, not proof of disconnected engine flow. Complete component contexts and
all 13 capture curves are retained in the localization JSON; nothing was
selected by a favorable outcome.

## Tested change

The old inlet calculation took a square root after dividing catchment by inlet
count, then applied a per-inlet minimum. Its summed setting grew with inlet
count. The new calculation divides one integer network budget across all
retained inlets, retaining minor-inlet caps. This caps the network budget; it
does not establish physical discharge, mass conservation or outlet capacity.
Both input and output settings change symmetrically. Unused capped budget is
not redistributed.

All eight fixed inputs were prepared before observation. Full package comparison
shows only the source input/output-rate fields and required metadata checksum
changed. Terrain, initial water, controls' identities/positions/targets/order,
sea, other assets and original probes are unchanged. Native source-rate tables
were checked against the intended packages at every capture.

## First-hour results

| Map | Peak flood km² | Minimum mapped-point retention | Losing authored bodies | Maximum wet-surface p95 movement | Verdict |
|---|---:|---:|---:|---:|---|
| Asheville | 0.9357 | 82.64% | 48 | 17.598 m | fail |
| Pittsburgh | 1.0342 | 84.96% | 60 | 20.987 m | fail |

Checks are unchanged from the accepted three-stock calibration: flood ≤0.05 km²
beyond the 128 m margin; every original natural point cohort and authored body
of at least 54 cells retains ≥95%; wet-surface p95 movement ≤3 m. Raw panel and
startup-view failures remain recorded but are not water failures. No original
historical score or sector threshold was changed.

The game assemblies changed since PR107's observation, while harness C# sources
are unchanged. A fresh build and doctor were used. These are current-install
validation results, **not an engine-identical causal A/B**. Exact runtime/build
hashes and teardown are in the raw packet. Human visual quality is not certified.

Both maps failed, so the remaining six fixed maps were not run. Their new CPU
packages are prepared but their water verdicts stay unknown. The original eight
observations and exact-package verdicts remain separately preserved. Holdout12
is unopened; this is not a geographic safe class.

## Decision

Do not promote this rate patch as a water repair. A shared setting budget is a
bounded arithmetic correction, but it has not fixed inland overflow or drying
unfed reaches. The next construction change should address the localized
channel/lake/junction and receiving-water geometry and initialization together;
these results do not justify blindly extending every tributary to the edge,
raising banks, or asserting an exclusive flood cause.

## Verification

- Focused Python behavior checks: 19 passed; scoped Ruff/format passed.
- All eight CPython/Pyodide packages match exactly.
- Full JavaScript suite and static build: see PR test plan. The known historical
  fixture-generation golden failures also reproduce on the consolidated base;
  no fixture score was regenerated for this increment.
- Two complete first hours, 13 depth captures each; exact source-rate table
  matches; both game/Steam/transient-unit teardowns empty.
- No intermediate review child. Finished increment goes through project review.
