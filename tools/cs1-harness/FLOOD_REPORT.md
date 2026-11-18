# Bounded native flood-region reports

This is a read-only report layer over the existing disposable native recorder.
It does not launch Steam, modify settings, generate maps, tune sources or change
acceptance. A diagnostic region does not exempt the rest of the original mask.

```sh
uv run --project tools/cs1-harness python -m cs1_harness.flood_region \
  --run RUN --reference RUN/reference-water.u16 --mapped RUN/mapped-water.u8 \
  --plan region-plan.json --hydrology INPUT/hydrology.json --out report.json
```

The plan contains the original component's native `component_xz` coordinates,
unchanged `package_sha256` and prepared `request_sha256`. The trace binding must
pin the original reference/mapped-mask digests. The tool replays the native
trace with its actual disposable cleanup receipt, verifies those bindings and
the complete selected region, and rejects a different collected endpoint.

`close_region` includes every touching source's complete input/output footprint
and halo to a fixed point, failing above512nodes/32sources. A region without
touching sources is valid; its direct source terms are zero, not proof of remote
source inactivity. Connected components are diagnostic eight-connected groups;
the original depth/distance acceptance predicate is unchanged.

The output separates whole-map flooding, traced cells, original seed cells and
current components intersecting the seed. It reports area/depth, starting-tile
overlap, native transport-bounds overlap and native flooded flags. The supplied
hydrology file pins the starting-tile metadata by hash; the5x5 bounds are the
native ±4800m square, not nine unlocked tiles or independent geographic truth.
Segment bounds are conservative overlap, not a vehicle-path blockage verdict.

Local storage telescopes over sealed published updates only. Values are native
depth-sum units (1/64m per node), not m³/s. Working-minus-published is local net
transport, not individual face flux or remote-source provenance. Unpublished
working passes require a separate carry model and are rejected by this report.

Arming in a paused city does not make an earlier dump co-timed with the first
atomic snapshot. The report exposes that initial gap without assigning its
unrecorded history to transport/sources. The sealed endpoint must match actual
collected depth and hydraulic floor. One unfinished unpublished tail may remain
explicitly excluded; no live unpatch of an executing solver is claimed.

## Actual Rio diagnostic, November18

Unchanged package4858f3eb… at native sourcea8ffc38 ran to20.112779game minutes,
armed at15.028334.285sealed updates/114nodes;32490publication comparisons match.
Region budget4059−5=4054; original54-cell seed3204−25=3179; direct source terms0.
The endpoint is exact. The pre-arm dump differs at74depth nodes (max8units;
region gap+24), so the budget is not extended backward over that gap.

Original-mask whole flooding is.058112km²at15 and.060672at20, both failed vs.05.
Neither snapshot overlaps the starting tile or native road/rail bounds;5cells
are inside the5x5 bounds. The selected pool is already established beforefive
and its terrain is within one native unit of held DEM. This does not establish
its supplying source or justify a coupled repair. All4256observations/1556flags
remain; required1556/1545/1532/1532at0/5/15/20, with the same11five-minute misses.
All40existing Rio pool calibrations pass at5/15/20. No candidate/full sweep ran.

**Separate setup failure:** the attempted blade-only localconfig Cloud edit was
ineffective. Steam logged two automatic save downloads during launch, contrary
to the no-transfer requirement; no upload-OK records. The helper is quarantined,
no further Steam launch is justified by its file readback, and downloaded saves
were not opened/deleted/distributed. No proprietary DLL/decompile or raw Steam
log is delivered. Original engine unchanged; ordinary build restored; cleanup
empty. This trace is an observation, not issue acceptance or shipping approval.

Raw receipts, audits, rejection evidence and reproducible run scripts:
`/home/caleb/experiments/PL-912-flood-cloud`. Copy into your own scratch and
redirect outputs for replay; do not overwrite producer receipts.
