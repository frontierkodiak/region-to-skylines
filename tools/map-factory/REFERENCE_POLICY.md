# Reference-defect protocol v1 (PL-1244)

This protocol and its JSON thresholds are committed before evaluating the new
detector. The seven existing squares are development evidence, not an unseen
validation set. Wilmington NC, Providence RI and Baltimore MD are registered
before acquiring their new source checks; all results, failures and missing
coverage remain. No retuning under version 1 after observing its results.

Run the same detector on every square, independently of exported-map scores.
An alarm requires either:

- A z13/z14 full-grid correlation below 0.9 **and** centered difference RMS
  at least 1 source metre; or
- A z13 tile-boundary median absolute jump at least 1 m and at least five times
  both the z14 and canonical jumps (0.1 m comparison floor), over at least
  32 adjacent sample pairs of the same tile boundary.

A reference alarm is not permission to pass an export. It permits using the
hash-bound higher-fidelity USGS 3DEP bare-earth reference **only after** an
independent OpenStreetMap/OpenFreeMap water-shore registration passes. Neither
Terrarium zoom is assumed to be true merely because it is finer. Missing
3DEP, missing coastline/water geometry, ambiguous registration or insufficient
coverage means **unresolved**, not an inferred pass. No forced z14 fallback.

Registration uses an independently projected vector-water footprint, not the
exporter's fitted ocean mask. The canonical raster's dominant 0.1 m elevation
bin defines a possible hydro-flattened water level; points within 0.25 m form
the DEM's candidate water footprint. This is a geometric feature, not a sea
level or water-safety claim. Require both classes to cover at least 5%, at least
64 interior shoreline cells, balanced land/water agreement at least 0.8 and an
identity advantage of 0.05 over every other rotation/reflection. Symmetric
interior-shore distances must have median <=30 source m and p90 <=90 source m.
Artificial map edges are not shorelines. No water/land filtering of DEM scores.

Every result reports the frozen z13 score, canonical-source score, z14 contrast,
defect evidence, registration result and selected reference. Evaluate complete
grids, eight orientations and any retained native world-sampler points; the
correlation >=0.9, orientation margin >=0.15 and terracing <=0.08 limits do not
change. Native receipts and original frozen verdicts remain immutable. A new
reference-assessment receipt cannot be relabelled as the original frozen pass.

If Norfolk does not meet the reference-defect rule, it remains a frozen-gate
exporter failure requiring diagnosis; low agreement alone is not an exception.
The protocol is deliberately conservative and may leave real defects unresolved.

Boston initial inundation belongs to PL-1191. No detector result clears water
safety, first-hour services, product warnings or default activation.

## Version 1 observations and preregistered version 2

Version 1 was executed on all ten registered squares without changing its
thresholds. It detects Charleston's seam but refuses replacement: small OSM
pools/ponds far from the coast dominate perimeter-weighted shore distances.
Its Charleston area agreement is 0.9596, but shoreline p90 is 568 m. Norfolk
has no v1 alarm (z13/z14 r=0.9150, centered RMS=0.854 m). Both failures remain
in the retained version-1 receipts; none is relabelled as a pass.

The version-2 method is registered before its evaluation, in a separate JSON
file. **All numerical thresholds stay identical.** Two structural corrections:

- Register **coasts**, using only edge-connected water components in both
  independently acquired vector and canonical hydro-flat footprints. Interior
  pools/ponds are not coastal registration features. This does not remove any
  point from any DEM correlation, orientation or terracing calculation.
- Test the third reference relationship explicitly: z13/canonical correlation
  below 0.9 plus centered RMS >=1 m is also an alarm. Two zooms of the same
  product may share a content defect. This arm still requires the higher-fidelity
  canonical acquisition's provenance and independent coastal registration;
  poor exporter agreement cannot itself trigger replacement. Constant vertical
  offsets do not trigger it. The physical cause of a content disagreement need
  not be falsely labelled a tile seam or DSM.

The three v1 prospective squares remain recorded; Portsmouth NH, New Haven CT
and Pensacola FL are newly registered before acquisition for v2. All results
remain, including inconclusive coasts. This is a purposive protocol check, not
a measured global sensitivity/specificity claim. No further v2 tuning after
observing results, and no change to the exporter, game or frozen judge.

## Reproduce the fixed checks

```sh
uv run --project tools/map-factory \
  python -m unittest discover -s tools/map-factory -p test_reference_quality.py -v
uv run --project tools/map-factory python tools/map-factory/reference_quality.py \
  qualified-bundle.npz NEW-RECEIPT.json --policy-version 2
```

Bundles contain full north-up `canonical`, `z13`, `z14`, z13 `tile_x`/`tile_y`,
independently rasterized `vector_water`, source `spacing_m`, JSON `metadata`,
and optional exported `game`/`terracing`. CLI receipts bind bundle, policy and
assessor hashes. Canonical eligibility requires an acquisition SHA-256 plus
the declared `canonical_reference_kind` (`usgs-3dep-bare-earth` or
`county-lidar-terrain`). This checks the receipt boundary, not authenticity of
arbitrary user-supplied claims; acquisition/manifests remain reviewable evidence.
Missing eligibility cannot authorize replacement. The canonical acquisition
is the source-fidelity target; independent geography comes from OpenFreeMap,
not a claim of a second independent elevation survey.

`capture_reference_shores.mjs PLAN.json NEW-SHORE.geojson` acquires water vectors
without fetching elevation or invoking the writer. `PLAN.json` supplies the
z14 `tile_box` (`x0`, `x1`, `y0`, `y1`) obtained from independently projected
sample coordinates. The retained driver projects GeoJSON with pyproj and
rasterio, records source hashes and preserves unavailable coverage as unknown.
Neither command overwrites an existing output receipt.
