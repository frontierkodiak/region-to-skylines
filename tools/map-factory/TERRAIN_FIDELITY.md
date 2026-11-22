# Terrain fidelity: attribution and experimental correction (PL-1244)

**Shipping defaults and acceptance thresholds are unchanged. The opt-in terrain
candidate passes the approved dual-reference protocol's checks; the new
protocol still needs independent review. Water safety is not qualified.**

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
untrusted contrasts, not a proposed remedy.

Independent review identified a sharper reference defect, then the producer
recomputed it. The zoom-13 tile boundary between `13/2276/3305` and
`13/2277/3305` lies between sampled columns 52 and 53, at longitude
−79.9365234375. The reference's mean absolute jump there is **2.828 m**, versus
**0.058 m** in canonical 3DEP and **0.021 m** at zoom 14. On the western 19.56%
strip, source/reference correlation is 0.3831 at zoom 13 but 0.9285 at zoom 14;
the two reference zooms correlate only 0.5415 globally. This demonstrates a
reference discontinuity aligned with the tile boundary, not a rotation error.
Fresh downloads of both zoom-13 tiles match the frozen cache byte-for-byte;
their server Last-Modified dates are 2017-11-12. This is not a stale local cache.
It does not establish physical truth at every remaining disagreement, and
zoom 14 still does not make the full square pass. No reference is substituted.

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

## Opt-in correction: source-faithful-v2

The [place reader](PLACE_INPUT.md#opt-in-source-faithful-terrain-experiment-pl-1244)
now exposes one fixed experimental policy. Shipping remains `legacy`.

An initial prototype retained a blanket 3 m ocean-depth target and a dry-land
floor. Its ramp still produced equal-height contour bands: Boston terracing
0.1959, Charleston 0.5843. That rejected prototype and all its outputs are
retained; it was not retried under the same identity.

Version 2 preserves existing below-sea terrain and source depressions, removes
the dry-land shelf, and applies only a shallow engineered minimum where an
explicit ocean polygon needs it. It bounds carving by robust relief and the
existing depth ceiling. There is no added noise, orientation correction,
per-city setting or changed acceptance mask.

| Place | Legacy correlation / terracing | Candidate correlation / terracing | Mean absolute source error: legacy → candidate |
| --- | --- | --- | --- |
| Boston | 0.8294 / 0.2344 | **0.9143 / 0.0029** | 0.791 → 0.221 m |
| Charleston | 0.5202 / 0.4273 | **0.5042 / 0.0000** | 2.269 → 0.097 m |
| Amherst | 0.9965 / 0.0027 | 0.9965 / 0.0027 | Terrain bytes unchanged |
| Asheville | 0.9792 / 0.0027 | 0.9792 / 0.0027 | Terrain bytes unchanged |

Charleston remains a frozen DEM/orientation failure despite being much closer
to the canonical source. The candidate's water-risk screen still warns in both
coastal development cases. No product export approval or water-safety promise
is inherited from these terrain improvements.

Initial inundation is also reported separately from subsequent flood growth.
At depth >0.5 game m, Boston has approximately 1.4915 game km² newly wet and
1.0276 game km² no longer wet relative to legacy initialization; all newly wet
vertices sample WorldCover's built-up class. Charleston has 0.0476 game km²
newly wet (0.0192 built-up) and 1.5252 game km² no longer wet. These are
vertex-area/dated-landcover diagnostics, not proof of real-world flooding.
They must not be hidden by a growth-only flood check's use of the new initial
water as its reference. No water-safety clearance or default activation is
justified by terrain scores alone.

### Three new exported squares

The policy was fixed before their feature capture/export, with no subsequent
tuning. The original source-only anchors were all retained. Each now has
paired legacy/candidate CRPs, using its previously acquired 3DEP terrain and
the common OpenFreeMap feature capture. They are **not** newly acquired full
canonical place models; optional resource painting was not used for this
terrain-only comparison. Source and feature provenance remain separate.

| New square | Legacy correlation / terracing | Candidate correlation / terracing |
| --- | --- | --- |
| New Orleans | 0.4022 / 0.0000 | **0.9056 / 0.0000** |
| Norfolk | 0.2075 / 0.0119 | **0.2761 / 0.0174** |
| Savannah | 0.8519 / 0.0039 | **0.9026 / 0.0000** |

Norfolk remains a failure, not an excluded or replaced holdout. These exported
checks are offline evidence, not three new native qualifications.

### Native observation

Two immutable candidate packages completed through the shared FIFO slot,
one at a time. Physical writer head is `874bf0298cafef9cb36c9f948e09f84a72942858`;
the frozen controller is `dc8b6f2d675765d252e4c043f47821be79b58651`.
All water/world sample points, route observations, mapped-water mask bytes and
DEM thresholds are retained. Only package-derived panel/camera expectations
are updated to match the new export. Both initial native terrain grids match
their prepared inputs byte-for-byte.

| Case | Game minutes | Native grid correlation / terracing | Native 1,600-point correlation | Frozen verdict |
| --- | ---: | --- | ---: | --- |
| Boston | 60.0883 | **0.9143 / 0.0029** | 0.9147 | Pass: 11 pass, 7 skip |
| Charleston | 60.1067 | **0.5042 / 0.0000** | 0.5072 | Fail: ground truth; 10 pass, 1 fail, 7 skip |

Identity margins are 0.2155 and 0.0750 respectively. Both have zero qualifying
subsequent flood growth under the unchanged check; this does **not** clear the
initial-inundation differences above. Required-wetness checks are skipped:
there is no declared wet cohort. No first-hour scenario, utility/supply,
population or Clef qualification is claimed.

A separate diagnostic samples the original georeferenced 3DEP raster at all
1,600 native world points: Boston correlation 0.9921, margin 0.3029, mean
absolute source error 0.2915 m; Charleston 0.9745, margin 0.2677, error 0.1156 m.
This uses the same primary acquisition, not an independent physical survey or
an approved replacement gate. The frozen failures remain unchanged.

Actual panel/opening/Areas/final PNGs were viewed and hash-reviewed. Both
cleanup receipts are empty, with no offline or telemetry errors. No game,
Steam instance or transient unit remains from either run. The shared slot was
released between runs and PL-1191 subsequently took it. Resource measurements
and the build/controller separation are recorded in the harness journal.

## Approved reference assessment (2026-11-22)

The lead approved a general defect detector, both scores on every square,
unchanged limits and independent geographic registration before reference
replacement. [Protocol and preregistration](REFERENCE_POLICY.md) preserve the
initial v1 refusal and the structural v2 correction; the numerical limits did
not change. Commits `d58eb93` and `edfd900` register each method before its
evaluation and each new source cohort before acquisition. These are purposive
checks, not a global detector-accuracy estimate.

V2 compares z13/z14, tile-boundary jumps and z13/canonical source disagreement.
Selection never reads generated terrain. It additionally requires hash-bound
eligible bare-earth source provenance and independent OSM/OpenFreeMap coastal
registration through pyproj/rasterio, not the writer's water mask. Registration
uses edge-connected coastal components; interior pools are not coastline.
Every DEM score still uses all 73,441 points and all eight orientations, without
land/water exclusion. The canonical source is the exporter's fidelity target,
not an independent physical survey; geographic registration is separate.

| Exported square | Frozen z13 r | Canonical-source r | z14 contrast r | Terracing | Selected reference / margin |
| --- | ---: | ---: | ---: | ---: | --- |
| Amherst | 0.9965 | 1.0000 | 0.9964 | 0.0027 | Frozen / 0.4648 |
| Asheville | 0.9792 | 0.9999 | 0.9791 | 0.0027 | Frozen / 0.3933 |
| Boston | 0.9143 | 0.9925 | 0.9118 | 0.0029 | Frozen / 0.2155 |
| Charleston | **0.5042** | **0.9745** | 0.7547 | 0.0000 | Canonical / 0.2670 |
| New Orleans | 0.9056 | 0.9095 | 0.9084 | 0.0000 | Frozen / 0.2735 |
| Norfolk | **0.2761** | **0.9510** | 0.2916 | 0.0174 | Canonical / 0.3814 |
| Savannah | 0.9026 | 0.9897 | 0.9038 | 0.0000 | Frozen / 0.3749 |

All seven selected terrain assessments meet r>=0.9, margin>=0.15 and
terracing<=0.08. The canonical source is original USGS 3DEP except Asheville's
original county-derived terrain, whose bytes remain private and unchanged.
Both the failing frozen scores and the unselected canonical scores are kept.
Zoom 14 is a contrast, not an automatic replacement.

Charleston fires the seam, cross-zoom and canonical-disagreement arms. Norfolk
does **not** fire the seam/cross-zoom arms: z13/z14 r=0.9150 and centered RMS
0.854 m. It fires the same canonical-disagreement arm applied to every square:
source/z13 r=0.3418, centered RMS=2.075 m. Its two zooms share disagreement with
registered bare-earth terrain; no unsupported DSM-cause label is required.
The candidate's source score 0.9510 still has to clear the unchanged 0.9 gate.

| Defective-reference square | Independent coast median / p90 distance | Balanced accuracy / orientation advantage |
| --- | --- | --- |
| Charleston | 10.48 / 74.11 source m | 0.9661 / 0.0817 |
| Norfolk | 7.41 / 16.56 source m | 0.9511 / 0.1076 |

The fixed registration limits are median<=30 m, p90<=90 m, accuracy>=0.8 and
advantage>=0.05, with minimum support checks. These geometric limits are not
substituted for the unchanged DEM orientation margin of 0.15.

### Prospective source checks, all retained

These six locations have no newly exported maps or native runs. Correlations
below compare the newly acquired canonical source with each reference, not an
export with itself. The first three were registered for v1; the last three
were registered before v2 acquisition. All appear in the receipts.

| Source-only square | Canonical vs z13 / z14 | V2 registration | V2 reference assessment |
| --- | --- | --- | --- |
| Wilmington NC | 0.9998 / 0.9999 | Unresolved | No alarm |
| Providence RI | 0.9994 / 0.9994 | Unresolved | No alarm |
| Baltimore MD | 0.9979 / 0.9978 | Pass | No alarm |
| Portsmouth NH | 0.9859 / 0.9855 | Unresolved | No alarm |
| New Haven CT | 0.9545 / 0.9534 | Unresolved | No alarm |
| Pensacola FL | 0.7938 / 0.7037 | **Unresolved** | **Alarm, no replacement allowed** |

Pensacola's shoreline distances miss the fixed limits. It stays unresolved;
no source exclusion, threshold adjustment or positive map qualification is
made. Inconclusive registration on a no-alarm square never authorizes fallback.

### Retained native observations under the approved contract

No game was rerun and no original frozen verdict was edited. A separate receipt
binds the reference assessment to all 1,600 original native world-sampler points.
Boston retains its frozen native r=0.9147; Charleston retains frozen r=0.5072
and additionally passes against original georeferenced 3DEP at r=0.9745,
margin=0.2677. Both native terracing checks pass. Original Charleston's frozen
verdict remains a failure, not a rewritten historical pass.

## Review and remaining limits

Neon independently passed the diagnostic head `721a14e` and the opt-in exporter
implementation at `dc0a646`. The reference-assessment implementation and v2
method need a fresh independent review. Ten new behavioral checks cover
reference selection, shared-product defects, missing provenance, real cliffs,
constant datum shifts, rotated/shifted shores and nonfinite coverage. The
current-head harness doctor subsequently passed after the shared slot cleared;
the earlier blocked attempt remains recorded.

The lead routed Boston's initial-inundation counterexample to PL-1191, with
exact inputs and measurements. Do not repair it by changing terrain here.

No shipping/default promotion, source substitution, mask, warning waiver or
per-city repair is made here. Water safety remains separate from terrain
fidelity and must continue to respect PL-1191's native evidence and constraints.
