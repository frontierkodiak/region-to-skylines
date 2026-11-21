## Scope and architecture decision

Finish the already-frozen South American regulated observation before editing
any bound dependency or implementing this stream tranche. Current native job:
exec session48657, driver534857, game538186. Runtime sidecar is captured.
No phase-seven final issue comment has been posted. All other jobs collected.

Two shapes considered:

1. Replace name-group routing inside the shipping `region.py` and its compiler.
   This would mix legacy replay, new branch provenance and new hydraulic rules.
2. Add an explicit source-piece catalog and a separate bounded graph-feasibility
   planner, with a version-three inventory adapter. Existing exporters and v1/v2
   validators remain untouched. Chosen: each source row owns its provenance;
   each connected native stream graph owns its proposed node stages/earthworks.

## Concrete modules

`waterway_pieces.py`:

- Catalog every rivers/streams source row, including missing/invalid rows,
  explicit intermittent/tunnel exclusions and finite outside-square geometry.
- Bind original field/index, full canonical source-feature SHA and independently
  clipped polyline-piece IDs. Preserve clipping flags and every clipped part.
- Produce ordered nearest-native16m nodes for every part without name grouping,
  longest-path selection or a45-node cutoff. Consecutive duplicate grid nodes
  may collapse, not branches or source rows. Retain singleton/loop ambiguity.
- Wrap the frozen v2 inventory as v3, retaining all original contracts/points.
  Attach precise piece/clip/plan provenance. A proposal or refusal remains
  unresolved: static feasibility is not materialized authored support, native
  retention, or full source-budget evidence. No old artifact is relabeled.

`stream_construction.py`:

- Target all mandatory surface stream pieces, not only wet or large pieces.
  Shared native vertices join components by geometry, never by name/dilation.
  Retain every part's ownership of nodes and ordered edges, including branches.
  Explicit unknown direction/cycles/ambiguous junctions stay unresolved.
- Infer only a provisional direction from unequal quantized endpoint floors;
  do not present this as known geographic flow direction. Equal endpoints are
  unresolved. No extra input fetched. No outcomes select geometry or probes.
- Build fixed infrastructure/control/landing protection as before; protect all
  other mapped water, including excluded intermittent streams. Only the complete
  current stream graph is a target, not all same-name waterways. Keep source
  masks/protected evidence and refusals; no post-refusal relaxation.
- Native stage bounds at each target node: L=floor-3m+max(1m,old_initial_depth),
  U=min(untouched exterior eight-neighbour bank floor)-0.5m. Quantize inward.
  Boundary/missing bank witnesses stay unresolved. All outside nodes stay fixed.
- On an acyclic directed graph, propagate the greatest nonincreasing stage:
  T(v)=min(U(v),T(predecessors)). If any T<L, no profile satisfying those declared
  inequalities exists; retain a bound witness, not a geographic-impossibility
  assertion. If feasible, proposed bed=min(old_floor,T-max(1m,old_depth)), no fill,
  cut<=3m, source-node depth>=1m, exterior banks untouched/freeboard>=0.5m.
- Do not add source forcing or serialize a physical/native-qualified package
  from this necessary geometry check. Integrated supply, outlet/junction
  treatment, actual flow/footprints, terraces and native retention remain
  unresolved. Do not apply the lake regulator budget to flowing streams.

## Verification before new outcomes or holdout

Meaningful unit cases: same-name disconnected lines remain separate; a short
branch is retained; square clipping preserves multiple parts; excluded/invalid
features remain accounted; branches are not reduced to one route; cycles and
equal-endpoint direction remain unresolved; protected cells cannot become
passes; cut/no-fill/full-bank constraints; brute-force small-DAG equivalence to
the quantized upper/lower solver; no contract/probe omission in v3.

Run the source-only planner on all three predeclared prepared development cases;
retain the two original base refusals. Bind geometry, floor, water, hydrology,
layout, compiler and planner hashes in a fresh freeze before holdout access.
These are diagnostics/proposals, not a predictor prefilter or new native water
observations. The12-square holdout stays unopened; every promise stays unknown.
