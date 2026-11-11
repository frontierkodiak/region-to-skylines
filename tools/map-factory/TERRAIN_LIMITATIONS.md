# Terrain limitations: Rio and Charleston reference maps

These are measured limitations of the inspected Python reference/test maps, not a universal real-terrain fidelity qualification. Native hydraulic acceptance is a separate judgment. No thresholds, evidence masks, website defaults or installer behavior were changed by these diagnoses.

## Rio: lake beds dominate; shoreline exceptions remain

Exact CRP SHA256: `997d4d07925e26ee07f20e8f82120e2e5785cdf99017d502066e20a3329aefd1`.

Comparing final serialized terrain with the **same-frame, smoothed uncarved banks**, the maximum lowering is **115.471m**, central at `(−48,−2592)` inside the exact Lagoa Rodrigo de Freitas source polygon—not ocean. The held WorldCover sample and all25 neighboring pixels classify this maximum as permanent water. The source DEM assigns93.983mASL there; the browser's connected-component lake-minimum carve produces57.782m game height, versus final57.781m. Natural lake bathymetry was not established.

The effect is broad lake modeling, not a few outer vertices: **8,887 vertices exceed20m lowering and4,799 exceed40m**, all central25. Nominal vertex support is2.275km² and1.229km² respectively; these are not surveyed areas. All1,365 vertices exceeding80m are classified as water. Additional Python lowering from browser PNG is at most **3.008m**, including quantization; the dominant deep cuts already exist in the browser input.

Nonwater exceptions must remain visible:

- Above20m bank lowering: **75 built-up vertices** (~0.0192km² nominal support), including57 outside exact water polygons; **17 forest vertices** (~0.00435km²), including11 outside. All lie within32m of rasterized source water. Fifteen built-up vertices exceed40m. These shoreline labels are held ESA2021 samples, not official buildability or a new independently reframed COG read.
- Three vertices outside source water polygons have entirely built-up5×5 neighborhoods: `(−496,4656)`, `(−128,−2528)`, `(−112,−2528)`, with bank lowering37.715m,26.066m,31.328m.
- Bank lowering is **not identical to displacement from direct raw DEM**: smoothing across high lake-DEM values inflates the latter two bank baselines. Their final-minus-direct-raw-land-fit differences are−1.743m and−6.419m. The northern point remains−46.120m against that raw-fit counterfactual; its raw neighborhood contains−1660.487mASL. This is an unresolved source/carving anomaly, not defensible natural bathymetry. Raw-fit comparisons are diagnostics, not an independent elevation survey.

## Charleston: global failure retained after completed-run binding

Exact CRP SHA256: `fcea76d840f6733b498fae79b82bb3a91324b600c6d1d906587de28dc247b667`.

The completed60.0078-minute report/session and collected immutable startup points/terrain/water are bound to this package. **The original global native ground-truth failure remains unchanged:** 1,600 actual world samples, native zoom13 identity correlation0.7100 against the existing0.9 minimum; the separate saved-grid comparison is0.6892. No point or wetland exclusion turns either into a pass. All eight orientation alternatives were retained; identity is strongest, supporting a non-orientation explanation without proving overall fidelity.

The explicit zoom14 diagnostic gives global correlation0.779343; central25 correlation0.702240. Central built-up73points have MAE0.125m/p950.720m/max1.702m; forest123points have MAE0.258m/p951.406m/max3.083m. These subsets do not replace the global result.

The central wetland maximum **16.675m discrepancy** lies in an exact source tidal-water polygon: pinned vector feature31235433 / OSM relation3123543, independently tagged `tidal=yes`. Component-minimum lake carving creates synthetic beds; surface DEM cannot establish natural underwater depth. Other wetland differences remain, including central outside-water errors−5.799m and+4.365m.

Outside-water forest retains **five global errors above3m**:−6.210m,−3.083m,−3.250m,+4.809m,−3.381m; the final two points were initially dry. Outside-water built-up maximum is2.949m. Thus neither “all land is correct” nor “all error is underwater” is supported.

## Shipping recommendation, not an automatic gate

**Do not block publication of the inspectable Python reference/test pack solely on these residuals**, provided this note and the original failures/subsets accompany it, the pack is not presented as universally terrain-faithful, and its native water/playability status is reported separately. It is useful reproducible evidence, including known failing terrain cases—not a blanket ready-to-play certificate.

**Do not promote these results into a universal website/installer default or a claim that arbitrary regions preserve terrestrial terrain.** The unresolved Rio urban/shoreline cuts, synthetic lake/tidal beds and unchanged Charleston global failure need an explicit product acceptance decision and any further source validation. Keep the website and installer unchanged until accepted. Do not resolve the issue by widening water masks, lowering thresholds or hiding the failing subset.

## Evidence identities

- Rio earthwork audit manifest SHA256: `01b1e9220b9c3e8a5aa9269337fdeefd77d4ba422820c0b40f254634f553004f`.
- Charleston completed-report diagnostic final manifest SHA256: `972128ae8d6fff4c3b00092607c73ffb8492041db4c1499a80fb306670ac943d`.

Those manifests bind the source grids, geometry, classifications, scripts and receipts underlying this note. They predate this supplemental document; its own SHA256 must be included when copying it into the final evidence bundle. No private raw logs are reproduced here.
