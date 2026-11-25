# Vegetation supply ledger

PL-1326: measured existing supply for PL-1325 and local Workshop bake controls
for PL-1328. Read [the report](REPORT.md) before interpreting a grade as a pass.

The canonical browse index is `data/index.json`. `prefab_reviews` holds bound
per-root metrics and independent review gates. `best_by_biome_form` separates
best observed near art from best within forest geometry/texture targets.
`data/reference-handback.json` names genus-exact local bake references and gaps.
The native census and final twenty-tree sheet are still pending; see
`observations/2026-11-25/pending-census.json` and the report.
Near-art grades never imply a frame-budget, ecological or full-bar pass.

## Rebuild the current snapshot

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
  --out data
```

Native PNGs and contact JPEGs are omitted from Git. The published tailnet shelf
has them under `native/` and `contacts/<run>/`; the JSON records source names
and digests. Rebuilding without images still reproduces the measurements and
quality ledger, while the gallery explicitly says images are unavailable.
November 23 observations and their manifest remain historical, on a different
game assembly. Do not blend those timings with November 25 captures.

## Collect and measure

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

## Native review on blade

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
add `--sheet-only`. A final plan has `ids`, `triangle_target`, twenty explicit
`selected_names`, optional `reference_names`, and optional
`diagnostic_resolution`. No popularity-based selection is substituted for the
reviewed list. A `reference_only: true` plan permits one to twenty explicit
controls with `--sheet-only`, such as the three Tilia/Ulmus anchors. No review
plan waits in-game for human input. `contact_sheet.py --source RUN --out CONTACTS` only resizes and
labels native captures. Grades are deliberately authored in `near-reviews.json`.

The driver copies exact-hash packages to owned local Assets paths, launches
with `--noWorkshop` and offline/account guards, and opens a fresh Grand River
city. It refuses selected duplicate identities and modal-obstructed frames.
Maximum native random scales are included in pair framing. Full review captures
near, gameplay, side/back, LOD-transition and second wind frames; two wind
frames alone are not a validated animation test. A uniquely named QA save holds
exactly one of every selected/reference identity and is reloaded and removed.
Teardown removes installed copies and verifies game, Steam and owned units ended.
Never run this native game on carbon or use it on a player city.

The benchmark uses the same 139,362 stock positions at two zooms, five A/B/A
repeats each, with 120 warm-up and 300 retained wall-frame samples per arm.
Native timing is not GPU time. Baseline drift, render validity, host contention,
resolution sensitivity and limiter attribution constrain any conclusion.

## Verification and delivery

The native mod must compile against the actual game and be exercised in game.
`check.mjs` checks the generated shelf in Playwright, including source/biome and
quality filters, search, pagination, hostile author text, image loading and mobile
overflow. Keep exact browser and native receipts with the snapshot.

Publish only normalized facts, reports, screenshots/contact pages and receipts.
Never publish CRPs, extracted meshes/texture pixels, DLLs, saves, credentials,
raw SDK logs, Steam UI/account screenshots or personal subscription lists.
