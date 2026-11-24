# Vegetation supply ledger

PL-1326, the supply side of PL-1325. This tool inventories the installed CS1
content, discovers public Workshop vegetation, and builds an offline-capable
shelf. It does not subscribe, download Workshop packages, log in, publish assets,
or change the map exporter’s plant selection.

## Evidence, not approval by popularity

The index separates:

- serialized built-in `TreeInfo` and name-screened natural `PropInfo` objects;
- Workshop **items**, which may contain several separately measured prefabs;
- author-declared triangle counts from measured mesh counts;
- loaded native metrics from offline serialized metrics;
- unknown review evidence from passes and hard forest-fill target failures.

No asset passes merely because it is popular, old, or described as optimized.
An over-target pack may contain useful individual variants; the item-level
failure means the whole pack has not earned unrestricted forest-fill use.

`data/index.json` is the canonical browse index. `observations/` holds the
normalized input snapshots and provenance needed to regenerate it. The shelf
HTML is generated from `shelf.html`; the tailnet shelf carries the native PNGs.
The committed JSON and shelf metadata regenerate without those ignored PNGs;
copy them from the published shelf into `observations/native/` to reproduce the
image gallery. `observations/manifest.json` distinguishes the accepted timing
run from the later sheet-only framing supplement.
Workshop packages, extracted meshes, texture images, DLLs, saves and account
files are never checked in or placed on the shelf.

## Reproduce

From this directory:

```sh
uv sync --locked
uv run --locked python -m unittest test_vegetation.py
uv run --locked ruff check . ../cs1-harness
uv run --locked ruff format --check . ../cs1-harness

# From the committed observations, without contacting Steam or starting a game.
uv run --locked python assemble.py \
  --installed observations/installed.json \
  --workshop observations/workshop.json \
  --native observations/native \
  --out data
```

To refresh on blade, write outputs under a new issue-owned experiment folder:

```sh
uv run --locked python installed.py \
  --game /peach/Games/SteamLibrary/steamapps/common/Cities_Skylines \
  --workshop /peach/Games/SteamLibrary/steamapps/workshop/content/255710 \
  --out installed.json
uv run --locked python catalog.py --out workshop.json
uv run --locked python catalog.py --out workshop.json --enrich
```

`--installed-ids ids.json` optionally adds cached Workshop item IDs to discovery.
Without it, refreshing the metadata does not enumerate Caleb’s subscriptions.
Collection membership and item facts use Valve’s public Web API. Public browse
state supplements creator names and ratings; public item pages supply declared
dependencies. Unavailable pages remain unknown, not “no dependencies.” Direct
dependencies are not a verified transitive dependency closure.

Dependency enrichment is resumable and bounded to 50 previously unchecked pages
per invocation (`--page-limit`), paced three seconds apart. HTTP 429 stops it
immediately and checkpoints progress; it is never automatically retried or
worked around. The first bulk observation hit this limit: its missing
dependencies remain unknown, and the shelf exposes the actual inspected share.

`installed.py` hashes every inspected root `.assets` and `levelN` file, and checks
every CRP directory range and payload checksum. Mesh bounds are unscaled metre
envelopes, not crown area measured from alpha coverage. Tree LODs are generated
by the game, so offline packages need not contain a separate authored LOD.
Serialized-file discovery does not establish DLC ownership, theme availability,
native loadability or exhaustiveness of name-screened vegetation props.

## Native work

Read `../cs1-harness/AGENTS.md` first. Use an isolated checkout of the harness on
blade, build its mod there, and run the driver from its locked environment:

```sh
cd ../cs1-harness
uv run --locked cs1-harness build
uv run --locked ../vegetation/native.py \
  --installed /path/to/installed.json \
  --out /path/to/new-native-output --wait-minutes 45
# Add --sheet-only to redo framing without repeating the timing experiment.
```

The driver joins the normal foreground FIFO slot. It copies **already-cached**,
checksum-matched tree packages into session-owned local Assets paths, launches
with `--noWorkshop` and the read-only offline/account guards, and makes a new
Grand River city. Nothing is saved. Teardown removes its copies and stops its
game, Steam, display, audio and bus. Do not run this on carbon or reuse a player
city. Empty copy directories can remain; the receipts check files and processes.

New ops: `vegetation_catalog`, `vegetation_retarget`, `vegetation_pair`,
`vegetation_frames`. The latter three mutate only the loaded disposable session.
They are not exporter APIs. The pair op **clears that city’s existing trees**;
never call it on a city you intend to keep.

The benchmark interleaves five A/B/A trials at two fixed zooms, retaining 300
wall-frame samples per arm after 120 warm-up frames. Instance positions, count,
growth flags, camera, stock lighting and paused simulation stay fixed. A/B/A
drift, errors, actual native counts, GPU/CPU host contention and zoom sensitivity
must accompany any interpretation. A frame-time comparison is not isolated GPU
time, an ecological-density validation, or a general performance guarantee.

The sheet takes twenty **installed candidate prefabs**, round-robin across
packs after sorting by triangle count. Their built-in tree neighbours prefer the same name-inferred genus, then
growth form, then nearest generated height; these are not botanical identifications. It is not the requested
globally best twenty: uncached candidates still require package access and QA.

## Browser verification

`check.mjs` drives source, biome and quality filters, empty results, pagination,
HTML-like author text, and a 390 px mobile viewport. Run it in blade’s matching
Playwright container (currently `v1.65.0-noble`) with `playwright-core@1.65.0` in
the container, not a headed browser on carbon. Arguments are the module URL,
generated shelf URL and an output directory. Its JSON receipt and screenshots
belong with the issue evidence.

## Remaining acceptance

See `REPORT.md` for measured coverage and the proposed bar. Runtime theme
coverage, actual wind/snow/season observations, scale and multi-angle billboard
reviews, maintenance checks, and the globally best-twenty selection remain
separate evidence gates. There is no automatic “recommend this” integration.
Any Steam-authenticated package download needs Caleb’s explicit approval on
PL-1326 before proceeding. The proposed download shortlist is data, not approval.
