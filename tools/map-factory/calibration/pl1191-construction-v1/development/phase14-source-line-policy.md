# Conditional source-line quantization correspondence v1

Read-only, committed before matching outcomes. Use the complete frozen phase13
public response only; no new geographic query or polygon/terrain/water outcome
selection. ALL six reviewed source rows672/683/712/713/770/809, every source point,
clip/hash and branch are retained. All five cases' original full geometry, scope,
old refusals and full prepared probes are copied and hash-bound. No constructor,
compiler, physical package, grid, mask, control, probe or threshold is changed.

## Packing evidence and limits

Local inputs.js uses pinned @mapbox/vector-tile2.0.3 toGeoJSON then writes stream
name/class/points/scope tags, discarding featureID/tile/extent. The downloaded npm
tarball is verified against package-lock SHA512; its decoder scales integer
coordinates by layer.extent*2^zoom. Extent defaults4096 but can be encoded otherwise.
The MVT specification does not prescribe clipping/simplification. Current
OpenMapTiles schema is supplementary, not proof of the historical deployment.
Original OSM source IDs/versions, tile bytes/layer extent and encoder simplification
policy are absent; even a unique geometric correspondence is NOT exact identity.

Declare one CONDITIONAL nearest-integer/no-simplification model: world grid2^26
(retained z14 times decoder default4096). Test every source vertex for integer
alignment within1e-5grid units (floating roundtrip allowance). Do not fit extent or
increase tolerance from matching outcomes. Historic extent/rounding/generalization
authority remains unknown whether or not this lattice test passes. Euclidean
nearest-integer rounding radius is sqrt(0.5)grid units plus1e-5numeric allowance,
about0.42m here; this is NOT a verified historical error bound or admission gate.

## Complete correspondence test

Evaluate EVERY complete public way tagged waterway (excluding riverbank polygons),
all names/classes included, retaining unsupported/missing geometry. For each full
captured row, enumerate EVERY endpoint-supported raw polyline subchain in either
direction, not a nearest endpoint/name assignment. Endpoint feet may lie inside
segments (tile clipping authority still unknown). More than256 endpoint embedding
pairs is unresolved multiplicity, not silently truncated. No OSM ways are merged.

For each embedding compare BOTH complete curves, sampling every segment at spacing
<=0.125grid units. Point-to-polyline distance is1-Lipschitz, so sampled maximum is
a lower bound and sampled maximum+0.0625grid an upper bound on the true symmetric
distance. Keep sampling-margin unknowns; never refine/retry until green. Require
nondecreasing feasible vertex positions in both directions as a separate ordered-
vertex check, not a continuous Frechet proof. Preserve every candidate/ambiguity
and chronology gap. Geometry consistency does not prove source identity, topology
or hydraulic connectivity. Explicit raw node IDs are retained separately from
coordinate coincidences; no inferred node-ID merging.

For consistent embeddings ONLY, report a read-only native-walk sensitivity using
the existing projection/walk algorithm on the complete raw subchain. Retain old
nodes/branches/probes and list hypothetical added/removed nodes without solving a
new bank profile, changing source geometry or materializing anything. A different
hypothetical walk does not authorize moving the captured waterway. A matching
walk cannot supply missing banks, widths, floor or runtime qualification.

Keep all failed/no-candidate/unknown results. If exact identity/precision authority
cannot be established, close the source-precision-repair hypothesis rather than
iterating masks. No relaxed rims/no fill/cut>3m/foreign buffer shrinkage or dropped
mandatory feature. Missing initialized water is not repaired by observation.
No native run, holdout input access, historical relabel, geographic qualification
or promise/ledger adoption. Fixed primary definition and all old protocols remain.
