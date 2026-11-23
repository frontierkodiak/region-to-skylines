## Narrow Geofabric source capture on existing coastal input — v1

Official BOM metadata request returned403, retained without retry. A separately
published Geofabric Network service returned root and stream/waterbody metadata;
its later connectivity-table request failed network access. Preserve that partial
capture, including unrequested/failed tables; do not claim all metadata captured.
Discovery/schema outcomes known before this NEW feature-data protocol.

Freeze method, query and complete retained metadata BEFORE feature queries. Use
only Network Stream All7 and Waterbody All10 at the published service, on the
bounding rectangle of the EXISTING low-coast-oceania rotated/scaled source square.
Use the exact inverse of prepare.pixel for all four corners; no expanded search
neighbourhood, new geography/holdout square or wet-selected region. This Australian
source does not supply data for the other five cases; their registry/refusals stay.

Query all intersecting OBJECTIDs first, bound10000/layer; sorted batches of200
with all attributes/full geometry at requested EPSG4326. Every ID must return
exactly once; returned geometry CRS must explicitly confirm EPSG4326. Missing/
duplicate/extra IDs, truncation, malformed/error or failed
responses are failed/partial capture, not repaired or zero/absent water. One
request per URL, no retries. Retain full bodies/headers/URLs/errors/timestamps/
hashes. ID-query plus batches are NOT an atomic database snapshot. Complete full
geometries may extend outside the query rectangle; no other square is selected.

Preserve HydroID/From_Node/To_Node/NextDownID/FlowDir/source/accuracy fields, nulls
and all polygon rings. FlowDir codes are documented in metadata; absence/0/3 is
unknown, not inferred from endpoint terrain. Network geometry describes potential
terrain-derived flow if water is present, not measured discharge/replenishment.
Neither field existence nor polygons identify old captured OSM pieces or establish
surveyed bank width, actual hydraulic floor, sea-stage coupling or outlet capacity.
No nearest-name/endpoint correspondence and no replacing original geometry/masks.
Future geometric association must be separately predeclared and retain ambiguity.

Source-only supplementary evidence, not native observation, qualification or a
holdout prefilter. No physical package/control/carve/fill/bank/probe/default/ledger
change. No retiring full8rims or relaxing fixed protections. Metadata/publisher
credit: Commonwealth of Australia (Bureau of Meteorology)2022, published online
service with Geoscience Australia changes; CC BY4.0. Keep dataset version/lineage
distinct from the historical OpenFreeMap/OSM capture and original immutable study.
