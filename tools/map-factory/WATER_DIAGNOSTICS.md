# Matched hydraulic diagnostics

`water_diagnostics.py SOURCE OUTPUT` exports **diagnostic-only** variants
from a fingerprint-bound prepared resource candidate. It changes no default
hydrology policy and performs no native/session/service/network action.

```sh
uv run python water_diagnostics.py EXACT_PREPARED_CANDIDATE FRESH_OUTPUT
```

Use `--mode portal-intake-original` (repeatable) to export only selected modes;
without this flag all modes are exported. Outputs are `OUTPUT/MODE/SLUG/`, each containing the
exact CRP, initial grids, hydrology, frozen resource plan, generation-bound
geometry, full geographic/routed probes and mapped-water reference. Top-level
`diagnostics.json` gives exact hashes; each `diagnostic.json` retains decoded
before/after native controls, changed indices/rates, initial-grid hashes,
source/input/encoder hashes, unchanged simulation prefix/suffix hashes and
per-asset payload hashes.

## Matched factors

1. **short-output-off**: only currently positive output rates on controls
   tagged `short_surface_river` become zero. Initial water is byte-identical.
   Existing zero-output portal drains stay zero; every intake/position/target,
   non-short output and source count is unchanged.
2. **sea-only**: initial depth becomes the quantized
   `max(0, sea_level_m - terrain_m)` grid. Every encoded source/control remains
   byte-for-byte equivalent, including all continuing positive emissions.
3. **portal-intake-original**: restore only short, zero-output tunnel inlet
   intake rates to their frozen `short_source_footprint.intake_rate_before`.
   Missing/invalid frozen rates fail closed. Initial water, bounded output
   rates, source count/positions/targets and all other controls stay unchanged.
   This tests the intake/output interaction; it is not an inlet-field model or
   evidence that original intake is a correct default policy.

The exporter first replays the **original** terrain, initial water, hydrology
and frozen resource plan through the existing writer/resource encoder. It
requires the entire replayed CRP to equal the generation-bound source CRP,
otherwise stops. Then it changes only WaterSimulation and the metadata
simulation assetRef checksum. All bytes outside WaterSimulation, package
identity, natural resources/trees, resource listing values, network, camera
and both preview assets are frozen to that verified original. Initial
velocity values remain zero; their encoded lengths follow the new wet-grid
topology as the native format requires.

For sea-only this intentionally means resource-water amounts, buildable listing
and previews describe the **original** package, not newly qualified sea-only
terrain. This is causal isolation, **not acceptance or a distributable map**.
Do not silently repaint those diagnostic bytes with the changed water grid.

## Native handoff

Use the exact exported CRP and its matching `probes.json` directly with the
harness `run --map ... --probes ...`. The outputs are already offline-staged;
no game is launched by export. Runs must stay separate and retain exact package
hashes. Do **not** pass sea-only through normal `soak.stage_prepared`, which
recomputes resource-water/listing/previews and will correctly reject this
frozen-context diagnostic hash. A failed diagnostic must never weaken normal
staging checks. No native qualification is claimed by successful export/tests.

Behavior tests decode the actual native-format source table and verify counts,
rate direction, selected zeroed outputs, untouched controls/previews/context,
sea-only grid arithmetic, intake-only restoration, and fail-closed source-control
or frozen-intake metadata mismatch.

In `portal-intake-original`, hydrology's `short_source_footprint` remains the
frozen baseline guard record, not a recomputed default-policy assertion.
`diagnostic.json`'s decoded control tables and restored intake indices/rates
are authoritative for the actual diagnostic CRP.
