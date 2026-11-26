# Vegetation

## Vegetation demand

PL-1327 adds a demand layer, not a new tree-placement policy or a native-game
certificate. It is based on the PL-1119 live-capabilities preview branch.

### One square in, cell expectations out

```js
import { fromUrl } from "geotiff";
import { vegetationExpectation } from "../../vegetation-inputs.js";

const report = await vegetationExpectation(
  { lon: -71.057, lat: 42.36, rotation: 0, scale: 1 },
  { fromUrl },
);
```

In a browser, `vegetation-worker.js` performs acquisition and calculation off
the main thread, using the same-origin `/canopy/` and `/worldcover/` byte-range
rewrites. `app.js` updates and cancels it as the square moves. The readout is
next to the existing capability row. The full report can be downloaded.

`vegetation-model.js:expectation(square, evidence, {cellSize})` is the pure,
deterministic calculation. Both entry points return `polli.vegetation/1`:

- Physical side: `17280 * scale` metres, with clockwise rotation; north-first
  rows in the square's frame. Default cells are 160 m, independent of game scale.
- Canopy occupancy: valid sampled height area at least 2 m high. Missing imagery
  remains missing; valid zero is open ground. Quantiles and height histograms
  describe **canopy area**, not individual trees. Raster samples contribute exact
  overlap area to cells, including non-divisible grids.
- Tree-genus shares and six growth-form fields plus `unknown`, with the selected
  source, method, radius and record count. Mixed genera are not assigned a leaf
  habit. WorldCover grass/shrub shares have a separate area denominator.
- Stem density is available only with explicitly complete inventory survey
  footprints. Neither civic source establishes full private-tree coverage, so
  density is unknown for these examples. Canopy occupancy remains available.

### Inputs and method choice

**Structure:** Meta/WRI CHMv2 `dinov3_global_chm_v2_ml3` COGs, CC BY 4.0.
Source imagery is mostly from 2017–2020, not a 2026 vegetation census. The reader
honors the internal cloud mask: actual invalid pixels can contain zero, so a
255-sentinel check alone is wrong. It reads the finest overview window under
1,048,576 pixels per intersecting tile and records the actual pixel size. The
overview aggregation is not established here; sampled occupancy is not exact
native-resolution crown cover. `tools/map-factory/canopy.py:sample` is the Python
reader for offline analyses, with explicit NaNs and optional atomic caches.

**Growth forms:** the separate [Copernicus LC100 forest-type layer](https://doi.org/10.5281/zenodo.3939050), 2019 v3.0.1, CC BY 4.0, provides ~100 m pixel priors wherever its tree-cover fraction exceeds 1%. Codes 1, 2 and 4 identify evergreen needleleaf, evergreen broadleaf and deciduous broadleaf. Mixed pixels, deciduous needleleaf (outside the six requested forms), missing and untyped pixels remain unknown. Known record traits take precedence; the prior fills only unknown record mass. It does not assign a trait to a species or create a genus observation. `tree_forms` and `canopy.form_prior` keep these bases separate. Coverage is 60°S–80°N, and the layer is historical, not current planting truth. A small species-level leaf-habit table in `vegetation-traits.js` links every entry to its NC State Extension source. Mixed genera such as Acer and Magnolia are not classified as a whole.

The archived global tiled TIFF is range-readable, without overviews. Its historical VITO S3 bucket is gone. Node requires a descriptive project User-Agent for anonymous Zenodo range reads; the local fixed-source proxy supplies it. The Vercel rewrite uses the caller’s browser User-Agent and is not deployed by this change. Unavailable priors leave forms unknown.

**Composition:** public Boston street/park inventory (52,028 named records,
2026-11-23, PDDL); live active Asheville public-tree inventory (6,237 normalized
records at acquisition); OSM tagged trees; and GBIF occurrences matched to the
48,518-name TreeGOER 2024.07 list (CC BY 4.0). Boston's dated compact snapshot is
bundled. Asheville is fetched live because explicit reuse terms were not found.
GBIF reads are capped at 1,200 eligible plant records per query window, filtered
to known tree-species names, 200 m stated coordinate uncertainty, years 2000–2026
and CC0/CC BY licenses. The cap and source failures are reported, not hidden.
OSM incompleteness is not absence. Synonym misses remain unknown coverage.

For the six-square sheet, the named Cabinet iNaturalist metadata snapshot
`20261027` supplies 15,577 research-grade occurrences, with stated positional
accuracy at most 100 m, queried against **all** TreeGOER names. It has no
cultivated/captive flag. Occurrence records are evidence proxies, not abundance
or a natural-only sample. No photos were downloaded or used for training.

The first 24-neighbour inventory interpolator failed spatial validation.
The selected urban method therefore uses observed local inventory counts
(at least three records within 100 m), otherwise the same inventory's source-wide
mix within 25 km. Urban and non-urban selection stays explicit. No city-name
or latitude-based vegetation palette is used. Outside inventory coverage,
bounded OSM/occurrence composition is labelled a proxy.

[The literature review](METHODS.md) covers NicheFlow, SINR, Sat-SINR, SAGE,
MIAM, BioAnalyst and GeoTreeCLIP. NicheFlow's demonstrated target is reptile
niches; native-range SDMs and forest-filtered tree classifiers do not establish
planted urban abundance. No foundation-model inference or model-training
comparison was run. The sourced reference is
[in knowledge](https://github.com/polli-labs/knowledge/blob/main/data/vegetation-demand.md).

### Measured accuracy

Whole 1 km blocks inside each preset are withheld, with a **250 m exclusion
buffer**. The source-wide prior also excludes that block and buffer. Metrics
are equal-weight block means of genus-share total variation distance (0 exact,
1 disjoint). The committed model SHA256 is
`7593fef8bfadc4535d4e0dd8983b23fefaac713e779d2e4f09ca4319acf64ae4`.

| City | Blocks / withheld records | Rejected local k24 | Selected source prior |
|---|---:|---:|---:|
| Boston | 87 / 40,466 | 0.511 | 0.306 |
| Asheville | 32 / 3,973 | 0.561 | 0.470 |

The final fallback equals the unsmoothed training-only regional baseline;
it does **not** demonstrate improved spatial prediction. It was selected after
the first model failed, so these are not untouched model-selection holdouts.
The observed local-count branch is a reconstruction of supplied inventory,
not independently validated inference. Source-specific genus attributes are
trusted, not independently resurveyed. Height accuracy, individual-tree height
distributions, natural-forest abundance and unseen-city transfer are unverified.
Detailed receipts are in [evidence](evidence/final_source_pool_benchmark.json).

### Reproduce

Use a task-owned scratch directory, not the source tree. Paths below are from
the repository root; `VEGETATION_DATA_DIR` is required by acquisition scripts.

```bash
export VEGETATION_DATA_DIR=/your/task/scratch/vegetation
mkdir -p "$VEGETATION_DATA_DIR"
cp tools/vegetation/squares.json "$VEGETATION_DATA_DIR/"
gzip -dc tools/vegetation/evidence/cabinet_snapshot_manifest.json.gz > "$VEGETATION_DATA_DIR/cabinet_snapshot_manifest.json"
uv run --project tools/map-factory python tools/vegetation/reproduce/acquire_inventory.py
uv run --project tools/map-factory python tools/vegetation/reproduce/validate_inventory.py
uv run --project tools/map-factory python tools/vegetation/reproduce/acquire_treegoer.py
node tools/vegetation/reproduce/validate-production.mjs vegetation-model.js final_source_pool
node tools/vegetation-sheet.mjs "$VEGETATION_DATA_DIR" "$VEGETATION_DATA_DIR/sheet"
```

The sheet generator also expects the rejected-model receipt as
`production_benchmark.json`; copy `evidence/rejected-k24-benchmark.json` there
when regenerating only the selected model. Source services can change: use the
receipts' hashes to distinguish a fresh acquisition from the measured snapshot.
Cabinet must have the named snapshot and its normal route available.

```bash
npm test
uv run --project tools/map-factory python -m unittest discover \
  -s tools/map-factory -p test_canopy.py -v
node build.mjs
```

The UI adoption manifest adds hashes for this sidecar and refreshes current UI
hashes only. Archived gates, native packages, hydraulic writers and historical
game observations are unchanged. Nothing here promotes a public deployment or
changes an existing game capability promise.

## Vegetation supply ledger

PL-1326: measured existing supply for PL-1325 and local Workshop bake controls
for PL-1328. Read [the report](REPORT.md) before interpreting a grade as a pass.

The canonical browse index is `data/index.json`. `prefab_reviews` holds bound
per-root metrics and independent review gates. `best_by_biome_form` separates
best observed near art from best within forest geometry/texture targets.
`data/reference-handback.json` names genus-exact local bake references and gaps.
The bounded native census and twenty-tree sheet are retained with explicit
unresolved cases in `observations/2026-11-25/pending-census.json` and the report.
Near-art grades never imply a frame-budget, ecological or full-bar pass.

### Rebuild the current snapshot

From this directory, without Steam or a running game:

```sh
uv sync --locked
uv run --locked python -m unittest test_vegetation.py
uv run --locked ruff check . ../cs1-harness
uv run --locked ruff format --check . ../cs1-harness
uv run --locked python assemble.py \
  --installed observations/2026-11-25/installed.json \
  --workshop observations/2026-11-25/workshop.json \
  --reviews observations/2026-11-25 \
  --native observations/2026-11-25/palette-delivery \
  --benchmark observations/2026-11-25/runs/native-benchmark-clean \
  --out data
```

The delivered gallery is explicitly composed from short native source sessions;
`data/index.json` records each tree’s `source_run`, original frame names and
`sheet_sources` receipts. A separate `save_only: true` twenty-name plan verifies
co-load/save/reload without another long screenshot loop.

Native PNGs and contact JPEGs are omitted from Git. The published tailnet shelf
has them under `native/` and `contacts/<run>/`; the JSON records source names
and digests. Rebuilding without images still reproduces the measurements and
quality ledger, while the gallery explicitly says images are unavailable.
November 23 observations and their manifest remain historical, on a different
game assembly. Do not blend those timings with November 25 captures.

### Collect and measure

`catalog.py` performs bounded public discovery; HTTP 429 stops page enrichment.
It never treats collection membership as a hard dependency. `ugc_details.cpp`
and `ugc_catalog.py` use the existing authenticated Steam client for read-only
details, children and transitive dependency queries. `normalize_ugc.py` joins
them to public discovery. Raw descriptions and SDK logs stay private; only
normalized public facts, description digests and query receipts are published.
Denied or unresolved dependencies stay unknown.

`installed.py` scans installed serialized files and local CRPs. Root-prefab
bindings follow package checksum references through materials; a pack-wide
largest mesh is not assigned to every variant. Every file has a SHA-256.
Non-strict scanning retains stale internal checksum warnings, never calls them
a quality pass. Structural-only validation is available for acquisition checks.
`prefab_name_collisions` reports identities duplicated across supplied CRPs.

```sh
uv run --locked python installed.py \
  --game /peach/Games/SteamLibrary/steamapps/common/Cities_Skylines \
  --workshop /peach/Games/SteamLibrary/steamapps/workshop/content/255710 \
  --candidate-ids candidate-ids.json --out new-installed.json
```

`steam_console.py` owns a Steam-only private-display/FIFO session. It supports
explicit operator actions, never player-display automation or automatic prompt
acceptance. `acquire.py` validates that exact owner before using
`steam_download.cpp`'s non-priority, bounded SDK downloads. Download callbacks
and local-byte validation are separate evidence: a NoConnection callback can
coexist with a complete committed cache file. No subscriptions, publishing or
purchases are performed. Caleb's standing 2026-11-25 permission covers use of
the existing Steam login for arbitrary Workshop downloads, with no purchases,
publishing or redistribution. Restore offline mode before native harness work.

### Native review on blade

Read `../cs1-harness/AGENTS.md`. Build in an isolated blade checkout, then use
the normal foreground FIFO:

```sh
cd ../cs1-harness
uv run --locked cs1-harness build
CS1_HARNESS_GPU_BUS=00000000:0B:00.0 uv run --locked ../vegetation/native.py \
  --installed /path/to/assembly-matched-installed.json \
  --out /path/to/new-run --review-plan /path/to/plan.json --wait-minutes 60
```

An overview plan has `ids`, `overview_only: true`, and optional `skip_names`;
add `--sheet-only`. A twenty-identity save plan has `ids`, `triangle_target`, twenty explicit
`selected_names`, and `save_only: true`. No popularity-based selection is substituted for the
reviewed list. A `reference_only: true` capture plan permits one to five explicit
controls with `--sheet-only`, such as the three Tilia/Ulmus anchors. No review
plan waits in-game for human input. A `benchmark_only: true` plan needs `ids`,
`triangle_target`, and optional `diagnostic_resolution`; it runs without
`--sheet-only`, in a separate short slot. Pass its output with `assemble.py
--benchmark RUN`. Run the twenty-identity save-only plan with `--sheet-only`; capture the
references in short batches and retain every tree’s source session when composing
the gallery. Monolithic 140-frame sessions proved unreliable in this experiment. `contact_sheet.py --source RUN --out CONTACTS` only resizes
and labels native captures. Grades are deliberately authored in `near-reviews.json`.

The driver copies exact-hash packages to owned local Assets paths, launches
with `--noWorkshop` and offline/account guards, and opens a fresh Grand River
city. It refuses selected duplicate identities and modal-obstructed frames.
Maximum native random scales are included in pair framing. Full review captures
near, 200 m gameplay, side/back, LOD-transition and second wind frames; two wind
frames alone are not a validated animation test. A uniquely named QA save holds
exactly one of every selected/reference identity and is reloaded and removed.
Teardown removes installed copies and verifies game, Steam and owned units ended.
Never run this native game on carbon or use it on a player city.

The benchmark uses the same 139,362 stock positions at two zooms, five A/B/A
repeats each, with 120 warm-up and 300 retained wall-frame samples per arm.
Native timing is not GPU time. Baseline drift, render validity, host contention,
resolution sensitivity and limiter attribution constrain any conclusion.

### Verification and delivery

The native mod must compile against the actual game and be exercised in game.
`check.mjs` checks the generated shelf in Playwright, including source/biome and
quality filters, search, pagination, hostile author text, image loading and mobile
overflow. Keep exact browser and native receipts with the snapshot.

Publish only normalized facts, reports, screenshots/contact pages and receipts.
Never publish CRPs, extracted meshes/texture pixels, DLLs, saves, credentials,
raw SDK logs, Steam UI/account screenshots or personal subscription lists.
