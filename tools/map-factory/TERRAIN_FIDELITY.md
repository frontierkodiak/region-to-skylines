# Terrain fidelity: offline attribution (PL-1244)

**Investigation only. No exporter policy or acceptance threshold has changed.
Boston and Charleston are not qualified.**

The frozen four-place native results are recorded in the harness journal. This
audit compares their exact prepared terrain with the exact canonical source
manifests and terrain tables, rather than attributing every reference mismatch
to serialization. Full grids, model manifests and receipts remain private on
PL-1244; Asheville source/derived grids must not be published here.

## Reproduce

With the original place directory, compiled inputs and prepared directory:

```sh
uv run --project tools/map-factory \
  --with ../agentic-research-workbench/place-model --with matplotlib \
  python tools/map-factory/audit_place_terrain.py \
  PLACE INPUTS PREPARED NEW_AUDIT_DIRECTORY
```

The command rejects a manifest different from the one bound to `geometry.json`
and a terrain table different from its manifest hash. It retains full arrays
and hashes its source files, inputs and metric implementations. It may fetch
the reference DEM into the harness cache; it never rewrites a map or judge.
It uses the unchanged harness terracing function and all eight orientation
correlations on the complete 73,441-point grid. It does not simulate the
native 1,600-point world sampler or claim a native pass.

## Observed stages

Each entry is **DEM correlation / terracing fraction**. The limits remain
correlation ≥0.9, identity margin ≥0.15 and terracing ≤0.08.

| Place | Canonical DEM, affine fit only | Fitted banks | Input PNG | Prepared native terrain |
| --- | --- | --- | --- | --- |
| Boston | 0.9366 / 0.0000 | 0.8635 / 0.6303 | 0.8297 / 0.2353 | 0.8294 / 0.2344 |
| Charleston | 0.5253 / 0.0000 | 0.5199 / 0.7311 | 0.5202 / 0.4273 | 0.5202 / 0.4273 |
| Amherst | 0.9965 / 0.0053 | 0.9965 / 0.0037 | 0.9965 / 0.0037 | 0.9965 / 0.0027 |
| Asheville | 0.9793 / 0.0028 | 0.9794 / 0.0023 | 0.9792 / 0.0023 | 0.9792 / 0.0027 |

The affine-only column is a **counterfactual**, not a generated or water-qualified
map. It retains all source elevations, transformed by the recorded scale/offset.
The final column reproduces the frozen native terrain failures offline. No
shipping file changed, so these are controls, not claimed post-fix regressions.

### Mechanism 1: terrain fitting performs synthetic coastal earthworks

`terrain.js:fitHeights` is not just an affine fit. It forces ocean cells to
at most −10 source metres, clamps them below at −40 m, and raises uncarved land
to at least +1 m. These hard plateaus and shoreline steps exist in the
floating-point banks **before** PNG encoding or native serialization.

Charleston's source terrain has no neighbourhood spanning more than 4 game
metres at this horizontal enlargement. Boston has 987 such vertices, but no
equal east-west pairs in the evaluated subset. The coastal rewrite creates
steep neighbourhoods next to equal-height plateaus. The unchanged terracing
metric detects those pairs. Final 1/64 m rounding contributes at most 0.0078125 m
to any unsaturated vertex; it is not an explanation for the metre-scale edits.

A diagnostic replay retaining existing water carving but omitting only the
coastal rewrite gives Boston 0.8374 / 0.0044 and Charleston 0.4207 / 0.0336.
It removes the terracing failure but **does not** solve DEM correlation. It is
not a proposed policy: ocean wetness and shore safety were not verified.

### Mechanism 2: water earthworks change the object being correlated

The input stage also applies fixed-depth river carving and connected-lake
flattening before Python preparation. On Boston this further reduces the
bank-stage correlation. Restoring all canonical elevations recovers 0.9366;
restoring coastal fitting alone does not. A surface DEM is not measured
bathymetry. Deleting necessary water earthworks merely to improve this score
would not establish a correct water-bearing map.

### Mechanism 3: source and reference disagree before export

Charleston's exact canonical 3DEP terrain already correlates only 0.5253 with
the frozen Terrarium zoom-13 reference. Its affine-only identity margin is
0.0964. Offset and positive vertical scaling cannot improve Pearson correlation.
Identity is strongest of all eight orientations. A diagnostic translation
search over ±16 reference samples (±118.5 source m, in 14.8 m increments),
combined with all eight orientations, reaches only 0.5649. This rules out those
tested registration corrections, not every conceivable acquisition fault.

At the reference's maximum point, the canonical source is 3.393 m while zoom 13
is 27.620 m. Diagnostic zoom 14 is 3.601 m there; it is **not substituted** for
the frozen reference. The whole-grid zoom-14 contrast is only 0.8002 anyway.
Zoom-15 diagnostic arrays contain extreme negative values and are retained as
untrusted contrasts, not a proposed remedy. Which source is physically correct
at each disagreement remains unresolved.

## Three new squares: source consistency, not map qualification

The New Orleans, Norfolk and Savannah 2 km anchors were written down before
acquisition and all retained. They use the same 8 m canonical 3DEP acquisition
and nearest-source/bilinear-target sampling as the place importer, compared
against the unchanged independent zoom-13 reference. No water geometry,
exported map or native run is claimed for these source-only checks.

| New square | Source/reference correlation | Identity margin |
| --- | ---: | ---: |
| New Orleans | 0.9968 | 0.2590 |
| Norfolk | **0.3418** | 0.2160 |
| Savannah | 0.9129 | 0.3477 |

Norfolk reproduces the source/reference problem away from Charleston. This
purposive sample is not a global pass-rate estimate and does not satisfy the
issue's post-fix holdout requirement.

## Next decision and remaining work

Resolve the source/reference contract before claiming that faithful canonical
terrain must pass this independent surface-DEM correlation on every square.
Keep the frozen failures and thresholds intact. Independently review the
diagnosis first; then establish which DEM/bathymetry observations a general
coastal rule must preserve, and implement that rule with source-error and
water-footprint accounting together with PL-1191.

No fixed-depth replacement, smoothing radius, vertical exaggeration, source
substitution, mask, warning waiver or per-city repair is promoted here. No
new native run was justified while Charleston fails even before exporter
policy. Boston/Charleston native passing acceptance, post-fix controls and
three-place exported holdout all remain outstanding.
