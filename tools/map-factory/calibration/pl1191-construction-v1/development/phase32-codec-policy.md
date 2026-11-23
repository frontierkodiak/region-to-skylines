# Experimental initial-water raw-value codec v1

This is nonshipping serialization capability, not edit authority or a candidate.
Read the legal local crp.py delta/RLE writer/reader, water_payload and existing
water_diagnostics decoder. No proprietary code or runtime is used. Earlier
phase31 results are known. Commit this method/schema/fixtures/tests before the
new copied-input freeze and all evaluation outcomes. Preserve all six cases,
source/contract/probe/refusal files; two cases have NULL physical support.

The supported initial WaterSimulation layout is the exact manager tag, full
uint16 depth raster, three compact raw uint16 arrays, big-endian uint16 source
count, ordered opaque 43-byte source records, 12-byte trailer, 2-byte manager
tail. Known source layout requires identical finite input/output xyz and type1;
the five uint24 raw slots are preserved without inferred physical units. Known
trailer requires zero unknown/flags and finite sea; unsupported layouts fail.
Truncation, array overrun, wrong shape/type and unsupported schema fail closed.

Compact domain keys are flattened row-major native indices (south-first on
physical inputs), sorted ascending. Domains: depth>0; wet OR east neighbour wet;
wet OR south neighbour wet. No wrap at edges. These names are packing relations,
not qualified velocity, engine flow direction or integrated discharge.

Canonical re-encoding uses existing encode_u16. Compare full decoded VALUES and
raw control records/header/trailer/tail. Report bytes separately: legal alternate
RLE representation can normalize. Do not require byte identity to claim value
identity, or silently claim bytes when they differ. No stale table-offset claim.

Only synthetic fixtures may change depth topology here. Nondecreasing uint16
depth required; preserve all old domain values. Explicit declarations must cover
exactly every new domain key, with no hidden default or old-value overwrite.
Fixture specification fixes interior, edges, corners, shared adjacency, nonzero
compact sentinels, control sentinels and alternate delta/RLE before outcomes.
Audit four original packages read-only: reconstruct their manager, simulation
and in-memory package; compare all non-water managers/assets/metadata and controls.
Do not write changed geographic CRPs or water maps. Fresh repacked manager chunks
are audit artifacts only. Both NULL cases stay unknown, never fake zero arrays.

Geographic-change entry point always refuses: there is no complete selected joint
initialization/safety/port plan. Low-level codec tests do not clear phase31
obligations or startup failures, Boston/Charleston, stream refusal or qualification.
All fixed masks/banks/controls/cut/fill/retention/gates and holdout remain untouched.
No game/build/collector/provider/native/rate/stage repetition requested. Independent
combined phase31/32 results review is required before any adoption.
