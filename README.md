# Region to Cities: Skylines

Pick any square of real terrain and download it as a Cities: Skylines (CS1)
heightmap. It runs in your browser from open data, with no account or key.

Live at <https://region-to-skylines.vercel.app>.

## What it does

Pan the map and the square stays in the middle. Rotate it, choose how much real
ground it covers, and watch a 3D preview. The download is the 1081 x 1081 px,
16-bit greyscale PNG the CS1 map editor imports, plus an optional JSON with the
square's centre, rotation, scale, height mapping and suggested water sources.
The URL keeps the square, so a link reproduces it.

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
  for the square (zoom 14 at true size). River lines are cut 10 m deep with a
  smooth profile; wide rivers mapped as areas are cut across their full width;
  lakes are sunk flat 4 m below their shore so a water source can fill them.
  Depths, widths and terrain smoothing are adjustable under "Make it buildable".
- **Refine water with live OSM data** is optional. It sends one query for the
  square to a public Overpass API server and caches the answer in your browser.
  Live data gives exact river directions and starts; the tiles already match it
  closely. Public Overpass servers are run by volunteers for OSM mappers and are
  often busy, so the app never asks them on its own.

## Using the heightmap in Cities: Skylines

1. Save the PNG into the game's heightmap folder:
   - Windows: `%LOCALAPPDATA%\Colossal Order\Cities_Skylines\Addons\MapEditor\Heightmaps`
   - macOS: `~/Library/Application Support/Colossal Order/Cities_Skylines/Addons/MapEditor/Heightmaps`
   - Linux: `~/.local/share/Colossal Order/Cities_Skylines/Addons/MapEditor/Heightmaps`
2. In the game, open **Tools → Map Editor**, make a new map and pick the file
   under **Import heightmap**.
3. **Sea level.** Coastal maps: set it to the "Sea level in game" value the app
   shows. Inland maps: drag it below the lowest riverbed so the valleys stay dry.
4. **Water sources.** The heightmap carves the beds; the game adds the water.
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

It is a static page with no build step:

```sh
python3 -m http.server -d . 8000   # then open http://localhost:8000
```

`terrain.js` holds the data fetching, carving and PNG encoding; `app.js` the map,
controls and 3D preview (MapLibre GL JS and three.js from CDNs).

## Deploying

The site is a static Vercel project (no framework, no build command, served
from the repository root), connected to this repository: every push to `main`
deploys to production, and other branches get preview deployments. To deploy by
hand from a checkout with the Vercel CLI and a token that can reach the project:

```sh
vercel deploy --prod --yes --token "$VERCEL_TOKEN" --scope <team>
```

## Data sources and licences

| Data | Source | Licence and credit |
|---|---|---|
| Rivers, lakes, basemap | [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, served as vector tiles by [OpenFreeMap](https://openfreemap.org) in the [OpenMapTiles](https://openmaptiles.org) schema | OSM data © OpenStreetMap contributors, [ODbL](https://opendatacommons.org/licenses/odbl/). Tiles © OpenMapTiles. A heightmap made with the water cut is a produced work from OSM data; credit "© OpenStreetMap contributors" if you share it. |
| Live water (optional) | Public [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) instances: private.coffee, then VK Maps | OSM data, ODbL, as above. One query per square, only when asked, cached in the browser. |
| Elevation | [Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) on AWS Open Data (Mapzen/Tilezen) | Credits below, as the [attribution page](https://github.com/tilezen/joerd/blob/master/docs/attribution.md) requires. |
| Place search | [Nominatim](https://nominatim.org) at nominatim.openstreetmap.org | OSM data, ODbL. Used within the [usage policy](https://operations.osmfoundation.org/policies/nominatim/): only when you press Enter, at most one request a second, answers cached, attribution shown. |
| Map hillshade | Terrain Tiles, as above | As above. |

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

## Licence

The code is MIT licensed; see [LICENSE](LICENSE). The data it fetches keeps its
own licences, above.
