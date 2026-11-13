# Feasible-bank restoration candidate

This is the PL-912 hypothesis authorized after the rejected 24 m experiment,
not an accepted default or an observed physical width.

After fitting the existing feasible hydraulic profiles, restore dry excavated
margins to the supplied uncarved DEM. Retain the modeled wet floor, surface
lines and polygons, and every below-target bed cell in each regulator's native
physical footprint. Protect source centres and the height-quantization boundary.
Explicit underground geometry is not surface support; visible crossings retain
precedence. With no actual uncarved DEM, do not infer restoration from the
fallback local-maximum estimate.

No width, stage, incision, source head, acceptance mask, probe or region-specific
branch is added. This does not turn a startup film into evidence of visibly wet
water. The actual zero/five-minute opening and Areas views must decide whether
restoring the modeled dry shoulders earns the user-visible improvement.

`test_bank_restoration.py` checks the failed narrowing mechanism: supported beds
must not rise above unchanged regulator targets, including unseeded beds and
quantization-edge cells. `verify_bank_restoration.py` compares all five full
packages with the preceding candidate: no terrain lowering, identical initial
water and wet floor, identical native WaterSimulation component (including
source Y, heads and rates), unchanged source headroom, geometry, samples and
horizontal network positions. Network heights and terrain-dependent resource
plans may refit and require fresh native verification.

Accepted fixtures and `NATIVE_FINDINGS.md` remain untouched. Candidate fixtures
are not native qualification. Rio's flooding and Charleston's terrain-correlation
failure subsets remain explicit. The 24 m experiment stays diagnostic-only.
