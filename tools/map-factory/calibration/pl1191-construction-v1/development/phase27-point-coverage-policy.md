# Queensland continuous point membership v2

The v1 raster results and ring counts are already known. Retain those artifacts.
Twelve of219 returned polygons have multiple rings; their captured signed areas
are first-clockwise/subsequent-counterclockwise. The inherited source rasterizer
assumes first-outer/later-holes; Esri documents general even-odd fill for polygons,
including disconnected outer rings. This warrants an independent packing/point
check before using raster counts as literal geometric support, not a new query,
OSM precision-repair hypothesis, pass threshold, bank relaxation or game rerun.

Commit method/tests/policy BEFORE a fresh freeze/output. Classify the complete
UNION of every original439clipped-part walk node and all19full in-square bank
unions against ALL219polygons with continuous even-odd membership in the existing
local projection. No ring-order/orientation assumption. Invalid/unclosed/nonfinite
rings remain explicit unresolved. Preserve exact source rows/branches and every
polygon/raw class; no name/nearest/wet selection or geometry replacement.

Predeclare a1mm local-distance boundary-ambiguity band: such nodes remain UNKNOWN,
not admitted inside or inferred dry. This is computational boundary handling,
NOT provider positional accuracy, datum-transformation accuracy or a new water
acceptance threshold. Retain all per-body memberships, boundary unknowns, complete
node ordering, raw classifications and comparison lineage. New node-domain hashes
are not full-map mask hashes. No external polygon becomes an expected-water,
protection or earthwork mask; original v1raster outcomes/refusals remain unchanged.
No physical/native/default/ledger/holdout change or hydraulic/source identity claim.
