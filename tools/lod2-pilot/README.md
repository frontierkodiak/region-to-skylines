# lod2-pilot

PL-900: how much of an Asheville building's identity comes from measured geometry?
Fifty buildings (Montford and downtown), three ways of making each, the same plain
materials on all three:

1. **current**: the pixel-asheville generator (kudzu kit and block rules, Microsoft
   height estimates or 6 m placeholders);
2. **height**: the county outline raised to its lidar-measured height;
3. **lod2**: a measured LoD2.2 roof from [Roofer](https://github.com/3DBAG/roofer) 1.0.0.

Ten buildings set the method and the tolerances; forty stayed locked until both were
frozen (`frozen/method.json` in the experiment folder records them with script hashes).
Results, sheets and the report are on the issue and the
[shelf page](https://blade.tailc29f0.ts.net/shelf/asheville-buildings-measured-lod2-vs-height-only-vs-current/).

## Round 2 (PL-909)

PL-900 missed three of four bars with its frozen method. Round 2 changed three things,
tuned them on PL-900's fifty buildings (all development now), froze them
(`frozen-round2/method.json`) and ran once on forty buildings drawn afterwards:

- **Split outlines** (`split_outlines.py`). A county outline that holds two or more
  OpenStreetMap buildings is cut into them before reconstruction, so a downtown block is
  its buildings, not one object. County parcels work as the line source too (`--source
  parcels`); OSM is the default because it is open and exists everywhere.
- **Small-building rule only where needed** (`--classes rescue`, now the default).
  Unclassified roof-like planes become building points only on an outline the lidar left
  with fewer than 50 building points.
- **Roofer keeps the outline** (`--no-clip-terrain`, `--no-clear-insufficient`). Its
  terrain clipping removed roof from 23 of the 50 outlines. An outline or part the lidar
  shows as open ground (building points on under 40% of its 1 m cells; in practice, built
  after the 2017 flight) is left out and counted as not usable.

| Check | Bar | The 50 (tuned on) | Fresh 40 (frozen) |
|:--|:--|:--|:--|
| Usable LoD2, no per-building change | 80% | 45/50 (90%) | 36/40 (90%) |
| Roof form and ridge direction right | 80% | 38/46 judgeable (83%) | 25/33 judgeable (76%); 8 partly, 0 wrong |
| LoD2 over height-only, city view | 70% | first judge 59%, second 80% | first 55%, second 63% |
| LoD2 over height-only, close view | 70% | first judge 65%, second 82% | first 68%, second 74% |

Ties count as non-wins and are a quarter to a third of the city-view answers; height-only
was preferred outright on 3 to 6 of the fresh 38. Numbers per building are in
`results/summary.json` and `results/summary-second.json` in the experiment folder.

`export_cs1.py` now mutes the wall colours for the game's lighting and adds plain window
panes so buildings light at night.

Round 2's output is in `~/experiments/PL-909-lod2-round2` (`LOD2_EXP`), which links
PL-900's lidar, tools and textures.

## Run

Needs `uv`, Node 20+, Docker (PDAL runs as `pdal/pdal`), Chrome, and the Roofer release
binary unpacked at `<experiment>/tools/roofer`. Output goes to
`~/experiments/PL-900-lod2-pilot` (`LOD2_EXP` overrides).

```sh
uv sync && npm install
uv run select_buildings.py --pixel <workbench>/pixel-asheville/public/data   # 50 buildings, before any lidar
uv run split_outlines.py               # round 2: cut block outlines into buildings (selection/parts.json)
# lidar: PDAL pipelines in <experiment>/data (2017 USGS EPT per neighbourhood; the 2025 NC tile converted to metres)
uv run crop_points.py --set all        # per building: fitting set and withheld 2 m patches
uv run reconstruct.py --set all        # Roofer, twice per building: without the withheld patches, and with everything
node current/export_current.mjs <workbench>   # arm 1's triangles out of the real generator
uv run build_scene.py --set all && node render.mjs all && uv run sheets.py --set all
uv run evaluate.py --set locked        # errors against withheld points and against the 2025 flight
uv run judge_sheets.py --set locked    # blind sheets; agents judge them with judge/rubric-*.md
uv run score_judges.py --set locked --judge first && uv run summarize.py && uv run shelf_page.py
```

Delivery checks: `node current/pixel_import.mjs <workbench> <ids>` puts LoD2 buildings
into the real pixel-asheville scene; `uv run export_cs1.py --cs1-assets ../cs1-assets
<ids>` bakes Cities: Skylines import sets through the PL-880 bridge (branch
`PL-880-asset-bridge` until it merges), for `cs1-harness asset build`.
`second_city.py` repeats the frozen method on a Boston sample.

## What the method is

- **Frame.** EPSG:6542 (NC state plane, metres); local x east, z south from the
  pixel-asheville origin; heights NAVD88 metres.
- **Outlines.** City of Asheville's Buncombe County Building Footprints 2024, as published.
  Downtown, one outline is often a whole block.
- **Lidar.** 2017 USGS `NC_Phase5_Buncombe_2017` EPT for every building. Every
  point in it is a single return (what a Geiger-mode sensor delivers), about 20-40
  points/m2, and trees hide roofs. The one 2025 NC QL1 tile held (SDD job 234441,
  39 points/m2, up to 7 returns) covers 13 downtown buildings and is used as an
  independent check, not for fitting.
- **Building points.** Delivered class 6, plus (`--classes promote`) non-ground points
  over the outline, 2 m or more above the ground beside it, that lie on roof-like planes.
  Needed because class 6 skips small buildings: 4 of the 50 outlines had no class-6 point.
  It also added points on 5 other outlines and lifted tree canopy into three roofs as towers; `--classes rescue` (only when an
  outline has almost no class 6) avoids that and was tried after unblinding.
- **Roofer.** Default parameters, one call per building, about 0.1 s for a house and up
  to 9 s for a downtown block. Its terrain clipping removes parts of an outline where it
  sees ground, so a model can cover less than the outline.
- **Checks.** Withheld 2 m patches (one in five) and the 2025 flight give height errors;
  blind agent judges compare arms against the 2025 orthoimage and the lidar surface.

## Files

| File | What |
|:--|:--|
| `select_buildings.py` | the 50 buildings and their hard-case flags; `--fresh` adds a later locked set |
| `split_outlines.py` | block outlines cut into buildings along OSM or parcel lines |
| `crop_points.py` | per-building clouds, fitting and withheld sets |
| `reconstruct.py` | class preparation, Roofer, CityJSON to triangles, the height-only arm |
| `current/export_current.mjs`, `current/export_page.js` | arm 1 from the real generator |
| `build_scene.py`, `render/`, `render.mjs`, `sheets.py` | one renderer for all arms |
| `evaluate.py`, `judge_sheets.py`, `score_judges.py`, `summarize.py` | the checks |
| `current/pixel_import.mjs`, `export_cs1.py` | delivery into pixel-asheville and CS1 |
| `second_city.py` | Boston sample |
| `shelf_page.py` | the comparison page |
