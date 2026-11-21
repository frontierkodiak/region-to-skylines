# Coastal boundary/corridor witness policy v1

This read-only follow-up knows PL-1245's preliminary boundary/drawdown observations.
Commit this exact method before its full replay, not as an outcome-blind study.
Use only the unchanged phase15 physical package, geometry, complete27386probes,
61full current-floor/depth grids and complete API timelines. Keep old artifacts
immutable. No game, forcing, geometry, mask, probe, threshold or holdout change.

Correct attribution from exact source records: rivers:50 is Bulimba Creek, not
Main Drain. Obtain every label/scope/clip/hash from the full source geometry;
retain every Main/Bulimba piece, explicit underground/outside/empty record and
all original probes. Named groups are diagnostic, not natural feature sectors.

Native orientation/units remain row-z-increasing,16m,1/64m. Ocean mask is the
literal captured polygon raster. Boundary is its intersection with square edge;
interior is all other ocean-mask nodes. Report both all-node H=(floor+depth)/64
and wet-only H for depth>0.1m. At a dry node H is a bed-plus-depth proxy, NOT an
observed free surface. Partition storage over the complete ocean/non-ocean masks;
encoded depth sums are net storage, not integrated source flux/discharge units.

Route selection is solely static geometry/floor, never water outcomes. Seeds:
ocean-mask square-edge nodes with actual floor<authored sea90. For every source
node of every target piece (including excluded diagnostic rows separately),
find a deterministic shortest4-adjacent floor<90 path to a seed. Ascending flat
seed order and neighbour order up/left/right/down break ties. Keep all paths;
no name merging, nearest-mouth/end-point guess or branch omission. The geometric
ocean-boundary crossings on these paths are not accepted hydraulic junctions.

An unconnected source node stays unconnected at90. Additionally record a
conditional minimax-floor witness over the full square: minimize maximum floor,
then step count, then flat-node queue order from the same seeds. This quantifies
a raster sill/barrier only, not a hydraulic route, bank/width authority, physical
feasibility or permission to carve. No mask/bank is retired. Keep static and
minimax paths distinctly labeled. Roots have no invented velocity direction.

Save complete paths and shared node profiles for all61times, including floor,
depth and H, wet/dry coverage and every mapped ocean crossing. Localize head
differences and adjacent WET-pair gradients descriptively; do not interpret a
dry-bed difference as a fluid gradient or infer flux/cause from it.

Use the complete velocity timeline, validating all27386names/coordinates at
every snapshot. Signed horizontal velocity is a projection toward the chosen
grid parent/ocean edge, NOT known geographic river direction. Only API queries
within0.001m of a native grid node supply that node's readback; arbitrary nearby
probes are not interpolated into unmeasured fields. Keep exact probe indices,
multiple readings, missing-node coverage and all full-cohort observations.
Velocities at unobserved route nodes remain unknown, not zero. No discharge,
evaporation, physical rate budget or exclusive loss mechanism is established.

PL-1245 supports the limited phase15 measurements, not geographic/runtime/full-
hour acceptance. Fix reporting attribution with an explicit NEW erratum, retain
the original report/archive/receipt. Normalize future archive paths relative
to their repository root, prohibit traversal/absolute/duplicate/non-file members,
and verify normal GNU extraction on the corrected additive packet. No native
repeat is warranted by either review finding. All promises remain unknown;
original full-hour/drying/flood/water gates and immutable PL-1072 study unchanged.
