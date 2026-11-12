# Region to Cities: Skylines

Pick a square of real terrain anywhere and download it as a ready-to-play Cities: Skylines
(CS1) map: rivers already flowing, a highway and a railway to the outside, real forests
and farmland, plus ore and oil, listed under New Game with no Map Editor step. The game's
heightmap is there too, under "Advanced", for anyone who wants to build their own map in
the Map Editor. It runs in your browser from open data, with no account or key, or from the command
line, where it can put the map straight into the game's folder.

Live at <https://region-to-skylines.vercel.app>.

## Have your AI agent do it

Press **Copy instructions for your AI agent** on the page and paste the text to Claude
Code, Codex or any agent with a terminal. It carries the square's link and points the
agent at [agents.md](https://region-to-skylines.vercel.app/agents.md) (also listed in
[llms.txt](https://region-to-skylines.vercel.app/llms.txt)). The agent runs:

```sh
npx -y https://region-to-skylines.vercel.app/cli.tgz "<link | preset | lat,lon | place>" --install
```

That builds the same file as the page and puts the ready-to-play `<name>.crp` into the
game's `Maps` folder, without replacing an existing file unless you pass `--force`. A JSON
of details goes to a cache folder, and it prints what to do in the game. `--heightmap`
makes the heightmap PNG for the Map Editor instead (into its heightmap folder, below, with a
water map of numbered water-source pins); `--help` lists the other options (rotation,
scale, height, name, in-game title, output folder, game folder, JSON output). It needs
Node.js 20.3 or newer, not git or Python; the first run downloads about 30 MB of Pyodide. The copied prompt and agents.md pin the command to the page's commit
(GitHub's tarball of it, via `build.mjs`); `/cli.tgz` is the latest.

## What it does

Pan the map and the square stays in the middle. Rotate it, choose how much real
ground it covers, and watch a 3D preview. The download is the ready-to-play map file;
under "Advanced" are the 1081 x 1081 px, 16-bit
greyscale PNG the CS1 map editor imports, a JSON with the square's centre, rotation,
scale, height mapping and suggested water sources, and a water map. The URL keeps the
square, so a link reproduces it.

How it is built:

- **Heights** come from AWS Terrain Tiles (Terrarium), at the smallest zoom no
  coarser than the map's 16 m pixels. The lowest ground sits at 50 m so water has
  room below the land, and 1 game metre is 1 real metre. When the relief would
  not fit under the game's 1,024 m, heights are squeezed to fit ("Auto"), or you
  pick a height factor.
- **Coasts** keep the sea: ground at or below 3 m that connects to the map edge
  becomes sea 10-40 m deep, and the panel says where to set the editor's sea
  level.
- **Rivers and lakes** come from OpenStreetMap, read from the basemap's vector
  tiles (OpenFreeMap, OpenMapTiles schema) at the most detailed zoom available
  for the square (zoom 14 at true size); for Asheville they match a live Overpass
  query on 99.7% of wet pixels. River lines are cut 10 m deep with a
  smooth profile; wide rivers mapped as areas are cut across their full width;
  lakes are sunk flat 4 m below their shore so a water source can fill them.
  Depths, widths and terrain smoothing are adjustable under "Make it buildable".
- **Which way rivers flow** is read from the ground: from each place a river
  crosses the edge, or ends inside the map, the app walks the carved line 0.6 to
  2.4 km and checks whether it runs downhill (an entry or a start) or uphill (an
  exit or a mouth). That places the suggested water sources.

## The ready-to-play map file

The map file is written by the map writer in [`tools/map-factory`](tools/map-factory)
(Python: NumPy, SciPy, Pillow), the same code whose maps are tested in the game with the
`cs1-harness`. The page doesn't port it: it runs it, under [Pyodide](https://pyodide.org)
(Python compiled to WebAssembly) in a Web Worker, and the CLI runs it under Pyodide in
Node. So the page, the CLI and the reference give the same bytes for the same inputs;
`npm run test:fixtures` checks the five reference maps (`tools/map-factory/fixtures`) byte
for byte. The first map downloads about 30 MB (cached afterwards); a map takes about a
minute and half a gigabyte of memory, so a phone may run out, in which case the page offers
the heightmap instead.

- `inputs.js` captures what the writer reads, for any square: the heightmap (the page's
  defaults, with sea from OpenStreetMap's mapped ocean), the uncarved ground, and the
  rivers, streams, lakes, coast and motorway, trunk and rail lines from the basemap's
  vector tiles, with their tunnel tags. It follows `tools/map-factory/capture.js`, reading
  tiles in a fixed order and filling ocean polygons by pixel centre, so every browser and
  Node agree.
- `mapgen.js` starts Pyodide with the writer, reads [ESA WorldCover](https://esa-worldcover.org)
  land cover (GeoTIFF byte ranges) and USGS MRDS mineral deposits, and runs `generate.py`.
  Python does no network reads (Pyodide has no sockets); `tools/map-factory/web.py` does the
  arithmetic `landcover.py` and `evidence.py` do around theirs, and gives the same land cover
  grid for the reference squares.
- `mapgen-worker.js` is the page's worker; `cli.mjs` calls the same functions.

Maps are not yet tested in the game for every square: the reference's hour-long game tests
cover the Asheville, Innsbruck, Rio de Janeiro, Pittsburgh and Charleston presets, and the
page shows one quiet line for the two whose checks failed (Rio, Charleston). Put the `.crp`
in the game's Maps folder (`%LOCALAPPDATA%\Colossal Order\Cities_Skylines\Maps`,
`~/Library/Application Support/Colossal Order/Cities_Skylines/Maps` or
`~/.local/share/Colossal Order/Cities_Skylines/Maps`) and choose it under New Game.

## Advanced: the heightmap in the Map Editor

1. Save the PNG into the game's heightmap folder:
   - Windows: `%LOCALAPPDATA%\Colossal Order\Cities_Skylines\Addons\MapEditor\Heightmaps`
   - macOS: `~/Library/Application Support/Colossal Order/Cities_Skylines/Addons/MapEditor/Heightmaps`
   - Linux: `~/.local/share/Colossal Order/Cities_Skylines/Addons/MapEditor/Heightmaps`
2. In the game, open **Tools → Map Editor**, make a new map and pick the file
   under **Import heightmap**.
3. **Sea level.** Coastal maps: set it to the "Sea level in game" value the app
   shows. Inland maps: drag it below the lowest riverbed so the valleys stay dry.
4. **Water sources.** The heightmap carves the beds; the Map Editor adds the water.
   Place a source on each dark blue pin, where a river enters the map or starts,
   and raise it until the bed fills to its banks. Grey pins mark where a river
   leaves; put nothing there. Put one in the middle of each lake (light blue
   pins) at the height the app lists. Positions are listed in the panel and the
   JSON in the editor's coordinates (metres from the centre, x east, z north).
5. **Starting tile.** It needs water and a highway in and out (Map Settings →
   Start Area moves it).

**25 vs 81 tiles.** The map is 9 x 9 tiles of 1.92 km, 17.28 km across. The base
game lets you build on the middle 25 tiles (9.6 km square), unlocked one at a
time as the city grows. The [81 Tiles 2](https://steamcommunity.com/sharedfiles/filedetails/?id=2862121823)
mod opens all 81. The heightmap always covers all 81; the app draws the grid,
the middle 25 and the starting tile on the map and the preview. Disable 81
Tiles 2 before opening the Map Editor: it turns the editor off.

**Scale.** At 1x (true size) a real block is a game block. Larger settings
squeeze more region into the 17.28 km map, so everything is smaller than real and
slopes get steeper unless you lower the height factor ("Real slopes" does it for
you); smaller settings stretch a town over the map. The panel spells out the
real distances and how steep slopes come out for the settings you chose.

## Run it locally

It is a static page with no build step. `dev.mjs` serves the checkout like the deployed
site, including the `/worldcover/` rewrite below, which the map file needs and a plain
static server lacks:

```sh
node dev.mjs 8000   # then open http://localhost:8000
```

`terrain.js` holds the data fetching, carving and PNG encoding, `inputs.js` the map
writer's inputs and `mapgen.js` running the writer, all with no DOM or canvas, so the page
and the CLI share them; `app.js` is the map, controls and 3D preview (MapLibre GL JS and
three.js from CDNs); `cli.mjs` is the command line. `npm test` runs the quick checks;
`npm run test:fixtures` builds the five reference maps under Pyodide and compares bytes
(about a minute each). The page's import map loads
`@mapbox/vector-tile` and `pbf` from jsDelivr; Node takes the same versions from
`package.json`. To run the CLI from a checkout: `npm install`, then
`node cli.mjs "35.58,-82.555" --name asheville`.

## Deploying

The site is a static Vercel project (no framework; `node build.mjs` copies the page, the
map writer's files and a packed CLI into `dist/`), connected to this repository: every push
to `main` deploys to production, and other branches get preview deployments. To deploy by
hand from a checkout with the Vercel CLI and a token that can reach the project:

```sh
vercel deploy --prod --yes --token "$VERCEL_TOKEN" --scope <team>
```

**The WorldCover rewrite.** ESA's WorldCover bucket serves byte ranges but no CORS headers,
so the page reads it through its own origin: `vercel.json` rewrites
`/worldcover/ESA_WorldCover_10m_2021_v200_<tile>_Map.tif` (that file pattern only, nothing
else in the bucket) to
`https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/<tile file>`, with an
immutable cache header. The page asks only for the tiles its square covers, and within them
for the byte ranges it needs: about 0.7 MB for Asheville. It runs on the project's existing
plan. **To remove it,** delete the `rewrites` and `headers` entries for `/worldcover/` from
`vercel.json` and push; maps built in the browser then fail at the land-cover step and the
page offers the heightmap (the CLI reads ESA's bucket directly and is unaffected).

## Data sources and licences

| Data | Source | Licence and credit |
|---|---|---|
| Rivers, lakes, basemap | [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, served as vector tiles by [OpenFreeMap](https://openfreemap.org) in the [OpenMapTiles](https://openmaptiles.org) schema | OSM data © OpenStreetMap contributors, [ODbL](https://opendatacommons.org/licenses/odbl/). Tiles © OpenMapTiles. A heightmap made with the water cut is a produced work from OSM data; credit "© OpenStreetMap contributors" if you share it. |
| Elevation | [Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) on AWS Open Data (Mapzen/Tilezen) | Credits below, as the [attribution page](https://github.com/tilezen/joerd/blob/master/docs/attribution.md) requires. |
| Place search | [Nominatim](https://nominatim.org) at nominatim.openstreetmap.org | OSM data, ODbL. Used within the [usage policy](https://operations.osmfoundation.org/policies/nominatim/): only when you press Enter, at most one request a second, answers cached, attribution shown. The CLI sends one request per run, only for a place name, with its own User-Agent. |
| Map hillshade | Terrain Tiles, as above | As above. |
| Land cover (map file) | [ESA WorldCover](https://esa-worldcover.org) 2021 v200, 10 m | ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). |
| Ore and oil (map file) | [USGS MRDS](https://mrdata.usgs.gov/mrds/) | Public domain. |
| Map file template | Saved by Cities: Skylines itself in the map factory (`tools/map-factory/templates`) | Holds the game's own data layout and references to its built-in roads and buildings; no game code or assets. |

Terrain Tiles source credits:

- Mapzen
- ArcticDEM terrain data DEM(s) were created from DigitalGlobe, Inc., imagery and
  funded under National Science Foundation awards 1043681, 1559691, and 1542736;
- Australia terrain data © Commonwealth of Australia (Geoscience Australia) 2017;
- Austria terrain data © offene Daten Österreichs – Digitales Geländemodell (DGM)
  Österreich;
- Canada terrain data contains information licensed under the Open Government
  Licence – Canada;
- Europe terrain data produced using Copernicus data and information funded by the
  European Union - EU-DEM layers;
- Global ETOPO1 terrain data U.S. National Oceanic and Atmospheric Administration
- Mexico terrain data source: INEGI, Continental relief, 2016;
- New Zealand terrain data Copyright 2011 Crown copyright (c) Land Information New
  Zealand and the New Zealand Government (All rights reserved);
- Norway terrain data © Kartverket;
- United Kingdom terrain data © Environment Agency copyright and/or database right
  2015. All rights reserved;
- United States 3DEP (formerly NED) and global GMTED2010 and SRTM terrain data
  courtesy of the U.S. Geological Survey.

Libraries: [MapLibre GL JS](https://maplibre.org) (BSD-3-Clause),
[three.js](https://threejs.org) (MIT), [@mapbox/vector-tile](https://github.com/mapbox/vector-tile-js)
and [pbf](https://github.com/mapbox/pbf) (BSD-3-Clause), loaded from unpkg and jsDelivr.

Cities: Skylines is a trademark of Paradox Interactive; this project is not
affiliated with Paradox Interactive or Colossal Order.

## Experimental building assets

The [Asheville building bake-off](tools/assets/bakeoff/README.md) compares
procedural, image-to-3D and hybrid authoring inputs. It is a separate pre-bridge
experiment: Blender previews and FBX checks are not a game-tested asset pack.

## Licence

The code is MIT licensed; see [LICENSE](LICENSE). The data it fetches keeps its
own licences, above.
