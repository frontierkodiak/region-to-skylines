# Explicit ocean evidence · PL-857

**Experimental, offline only (2026-11-11). Website and installer unchanged.**
Based on exact writer `fb77e74cb3c64801044c8b231d1265205d006cab`.
Controlled captures ran at `3862fd59d3979b4097cf3c84d5ca854a8bdaa4cd`;
subsequent changes add tests, measurement code and documentation, not a different
capture policy or Python terrain/water generator. Resource qualification branch
`2584088` remains separate and untouched.

## Root cause and fix

The old capture helper called `terrain.seaMask(elevation.heights)`. That helper
marks edge-connected heights <=3m as sea (including some small low islands),
and `fitHeights` then forces every marked cell at least 10m below sea level.
This classifies real low coastal land as ocean before Python water preparation.
Reducing water depths cannot restore the corrupted PNG and bank inputs.

The capture helper now reads actual `water/class=ocean` Polygon/MultiPolygon
features in its existing basemap transport/stream jobs. Other observed water
classes are inventoried, not silently reclassified. Ocean geometry, holes,
feature properties/identity, tile URL/status/hash and classification provenance
are included in the captured geometry. Polygon rings use the existing terrain
frame conversion, even-odd holes and binary-mask union. Per-polygon thresholding
prevents repeated tile-edge antialiasing from accumulating into extra sea cells.
No ocean polygon in frame means null sea; missing tiles are not ocean evidence.
The existing smoothing, carving, fitting and source-generation functions are
reused without modifying `terrain.js` or adding a second terrain generator.

Actual observed ocean evidence:

| Case | Ocean features | Polygon pieces | Explicit mask fraction | VT status |
| --- | ---: | ---: | ---: | --- |
| Rio | 43 | 61 | 43.474% | all 200 |
| Charleston | 28 | 31 | 18.040% | all 200 |

Other actual classes included river, lake, pond, dock and swimming_pool. Only
literal ocean features enter the sea mask. Both DEM captures used 81 Terrarium
tiles at zoom 14. Tile evidence and raw sampled Float32 DEM are retained.

## Controlled changes

Original geometry comes from
`/home/caleb/experiments/PL-857-sustained-water/captures-frozen/<slug>-geometry.json`.
The exact square, rivers, lakes, riverAreas, roads and streams compare equal
before/after for both cases. Fit base and vertical scale are also unchanged:
Rio `-40 / 0.9198811898929851`; Charleston `-40 / 1`.

Derived sources are **not** all unchanged. The unchanged browser `waterSources`
function sees corrected fitted heights and can choose different endpoints:
Rio keeps 12 sources with two identities replaced and three common entries
changed; Charleston keeps 18 sources with seven identities replaced and four
common entries changed. Unchanged Python preparation derives 200 native
controls instead of 199 for Rio, and 57 instead of 44 for Charleston. Rio's
start tile remains 22; Charleston changes from 24 to 16 on restored land.
Full before/after arrays and identity differences are recorded in each input
directory's `source-changes.json`. No manual source rates, thresholds or
bank-frame offsets were introduced.

## Initial prepared inundation

Independent WorldCover 2021 data is the existing north-first 1728-square
resource input. Native-format water depth is 1081-square south-first; the
measurement bilinearly samples it at south-first 10m WorldCover cell centres.
Wet means depth >0.1m. **No coastal correlation/exclusion mask or acceptance
threshold change.** Percentages below are fractions of each land-cover class,
not fractions of all map cells. These are initial prepared grids, not native
simulation observations.

| Case/window | Built-up before → after | Forest before → after | Total wet before → after |
| --- | ---: | ---: | ---: |
| Charleston, whole square | 41.16% → 2.91% | 43.14% → 3.67% | 69.48% → 34.81% |
| Charleston, central 25 | 66.61% → 3.83% | 61.36% → 4.11% | 84.07% → 42.60% |
| Rio, whole square | 6.06% → 5.98% | 2.40% → 2.14% | 39.25% → 46.61% |
| Rio, central 25 | 6.70% → 6.57% | 2.79% → 2.60% | 15.36% → 19.91% |

Rio's explicit ocean extent increases initial total water despite a small
reduction in built-up/forest overlap. It is not evidence that Rio's known
60-minute flood failure is fixed. Charleston still has nonzero class overlap;
coastline resolution, old non-sea geometry, WorldCover age/classification and
native behavior require review. Synthetic ocean bathymetry can affect raw-DEM
correlation; this task did not mask that comparison or alter its thresholds.

## Artifacts and hashes

Inputs: `/home/caleb/experiments/PL-857-sustained-water/coast-evidence-inputs/<slug>/`.
Each contains `<slug>.png`, `-banks.f32`, `-geometry.json`, `-provenance.json`,
`-raw.f32`, `-sea.u8`, `capture.json` and `source-changes.json`.
`capture.json` binds all six original download hashes and original geometry.

| Input | SHA-256 |
| --- | --- |
| Rio PNG | `f9ccdd7b677182cefcb10a2e1915516526d07699db4e97de4d51aa1b58acaf32` |
| Rio banks | `0788db8fcb982828c858ee51e9d7c78fe98be0613ad9624140071ffe4db19a83` |
| Rio geometry | `db0162a1b27e894a014ef4340c4d93b87e23aedd8c3d30094948dd4ffcfebcc0` |
| Charleston PNG | `89f2574f4e505fafe62a26cb5ef38aac4784159962da43e30d69893f7e5d8611` |
| Charleston banks | `73fbb8d19703cd2b533971db5945d6c0f6b26cc007aab8a06da66e100e48c93f` |
| Charleston geometry | `cbbfa7e46c03272e8d30d08bc152c13a325acad118dcfcafbb9fd40f3516a263` |

Prepared candidates: `coast-evidence-candidates/<slug>/` under the same experiment
root; each has generation receipt, geometry and `inundation.json`.
Exact replay staging is in `coast-evidence-staging/maps/<slug>/`.

| Candidate | SHA-256 |
| --- | --- |
| Rio | `e2475ee124f034d489116a8c5b6dea25d77b58bbe0e45d5be4ca964d8abec151` |
| Charleston | `f461a871787c3dab3d00ac016340b6456d9dad677d20159ec777ad66aa45e790` |

Both packages stage to exactly the generated hashes. No fixtures or expected
checksums were changed. Packages are unpainted to isolate the coastal input
change; resource integration remains a separate experiment.

## Verification and residuals

Eleven browser assertions pass: low <=3m edge-connected land, true ocean,
island holes, inland null behavior/fit, duplicate-tile union, outside-frame
null, non-ocean class rejection, MultiPolygon/feature identity, clockwise
geographic rotation and unsupported ocean-geometry rejection. The duplicate
test first exposed opacity accumulation and drove the binary-union fix.
Node syntax checks and Ruff lint/format checks for the new Python helpers pass.
An analytic south-first row-gradient test verifies native-node-to-WorldCover
centre resampling at both map edges.

Capture logs and cleanup receipts are under `coast-evidence-inputs/browser-logs`;
the final eleven-test run and cleanup are under
`/home/caleb/scratch/2026-11-10-pl857/coast-browser-tests/browser-logs`.
Both named headless sessions and private HTTP servers were closed in `finally`.
No Steam, game, GPU harness, shared service or remote/platform write occurred.
Live website/installer and original Python terrain/water generation code remain
unchanged. Native coastal hydrology, preview/camera/resource appearance and
ready-to-play acceptance are **not verified**.
