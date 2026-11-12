# CS1 map-making tools and mods: what they expose, what to copy

Research for PL-902 (real-world region → ready-to-play CS1 `.crp` map). Read 2026-11-10.
Legend: **[S]** sourced fact (source given), **[I]** inference. Mod sources were read from
their public repositories (cloned locally; not distributed here). Game facts marked "decomp"
come from fresh decompilation of CS1 1.21.1-f9 (no decompiled code is distributed).

---

## 0. Game facts the tools are built on (decomp + locale)

These decide what any tree or resource writer must do, so they come first.

**Tree limits [S, decomp `TreeManager.cs`]**
- `MAX_TREE_COUNT = 262144` (array size; slot 0 is unused).
- `MAX_MAP_TREES = 250000`: `CheckLimits()` refuses new trees in the **Map Editor** at 250,000.
- In-game `CheckLimits()` refuses at `m_treeCount >= 262139`. Asset editor: trees + props < 64.
- The cap is one pool: map trees and player-planted trees share it ([Steam thread](https://steamcommunity.com/app/255710/discussions/0/1696043263500117400/), confirmed by the code above). A map shipped at 250k leaves a player about 12k trees.

**How trees are stored [S, decomp `TreeManager.Data.Serialize`, `TreeInstance.cs`]**
- Fixed 262,144 slots. For every slot: `m_flags` (ushort, EncodedArray). For live slots only: the prefab index (into the `PrefabCollection<TreeInfo>` name table written after it), `m_posX`, `m_posZ` (shorts). Then the burning-tree list.
- `m_posY` is **not** saved: load sets it to 0 and the tree conforms to terrain. Vanilla can't keep a tree at a fixed height.
- Flags: `Created=1, Deleted=2, Hidden=4, Single=0x10, FixedHeight=0x20, FireDamage=0x40, Burning=0x80, GrowState=0xF00` (bits 8–11). `CreateTree` sets `Created`, `Single` (true for click-placed, **false for brush-placed**), `GrowState=15`.
- Position: `x = m_posX * 0.26367188` m (in-game; about 26 cm steps, ±8640 m); setter `RoundToInt(x * 3.7925925)`.
- Per-tree look: scale and brightness come from `new Randomizer(treeID)`: `scale = m_minScale + r.Int32(10000)*(m_maxScale-m_minScale)*0.0001`, brightness likewise. Rendering uses `Quaternion.identity`: **every vanilla tree faces the same way**. So the only levers a map file gives you are prefab choice, position and slot index.
- Missing prefab on load [S, decomp `PrefabCollection1.cs`]: `BindPrefabs` logs `Unknown prefab: <name>` and binds null; the tree slot survives unrendered. Prop & Tree Anarchy's page says vanilla also throws load errors when tree assets are missing ([Workshop 593588108](https://steamcommunity.com/sharedfiles/filedetails/?id=593588108)).

**Forest resource is derived from trees [S, decomp `NaturalResourceManager.TreesModified`]**
- Resource grid 512×512, cell 33.75 m. For each cell: `m_forest = min(60 × n, 255)` where n counts trees with `(flags & 3) == 1` inside the cell; `m_tree = min(4 × ΣGrowState, 255)`.
- So **5 grown trees saturate a cell's forest**, and **any forest > 0 sets that cell's fertility to 0**. A hedgerow through farmland deletes the fertile land under it.

**Vanilla resource brush [S, decomp `ResourceTool.cs`]**
- Defaults `m_brushSize = 200`, `m_strength = 0.5`; each tick adds `255 × strength × brushValue` per cell.
- Ore and oil eat each other; sand and fertility eat each other (`ChangeMaterial`). Fertility can't be painted where `m_forest != 0`.
- Map Editor brush UI: size 50–2000, strength 0.01–1.00; "a size 50 forest brush places single trees"; sea level 0–500 m ([wiki Map Editor](https://skylines.paradoxwikis.com/Map_Editor), copy in `../pages/wiki_Map_Editor.md`).

**Heightmap format [S]**: 1081×1081 16-bit, 0–1024 m, 1/64 m per unit, 16 m per pixel at 17.28 km (terrain.party README quoted in [this Steam thread](https://steamcommunity.com/app/255710/discussions/0/610574394238360613/); skydark `app.js`: "1081px represents 1080 faces … 1px = 16m").

---

## 1. Heightmap generators and real-world importers

### terrain.party (dead for heightmaps)
- Link: terrain.party (archived JS at `web/tp_app.js`, from the Wayback snapshot of 2016-11-19).
- **Knobs [S, JS]**: only the box. `reset(){setWidth(18e3)}`, `expand` +1 km up to `6e4`, `contract` −1 km down to `8e3`. So the default is 18 km and the range 8–60 km, in 1 km steps. No height scale, no water.
- **Output [S, README]**: a zip of PNGs (ASTER 30 m, SRTM3 v4.1, SRTM30+, and a "Merged" ASTER + USGS NED + SRTM30+ that the README says to use) and a README. Elevation is 1:1; the **lowest point maps to 40 m**, because "Cities: Skylines maps default to having sea level at 40m, with typical terrain starting at 60m."
- **Why it died [S, search summaries; the Paradox forum itself refused my fetches]**: intermittent since 2016; a 2019 forum post says its USGS data source was retired in August 2019. The Image Overlay Renewal page (2025) says it "can no longer generate terrain elevation maps", and users get a zip with only a README.
- **User complaints [S/I]**: the 18 km default box isn't 17.28 km, so maps came out about 4% small (lxteo's Mapper README says "18km is 1:1 scale"; their scale field is "Not working correctly!"). "Starting your map at 40 meters is just plain wrong" ([TotalTerrainTool](https://steamcommunity.com/sharedfiles/filedetails/?id=1894371878)). Flat regions look flat at 1:1.

### heightmap.skydark.pl (sysoppl/Cities-Skylines-heightmap-generator) — the main successor
- Source: https://github.com/sysoppl/Cities-Skylines-heightmap-generator (fork of JBerg60/cities-heightmap). Needs the user's own Mapbox token.
- **Knobs, defaults and ranges [S, `src/index.html`, `src/app.js`]**:

| Knob | Default | Range | Notes |
|---|---|---|---|
| Map size | 17.28 km | 17.28–69.12 km | larger areas get resampled into 1081 px; "reference height scale" = 17.28/size |
| Base level | min height (Auto) | −1023.9…1023.9 m | |
| Height scale | Auto: `min(250, floor((1024 − waterDepth)/(maxH − base)·100))` | 0–250 % | 100 % = 1:1 |
| Water depth | `defaultWaterdepth = 40` | 0–60 m | land pixels are raised by this, water (Mapbox vector water) stays at base |
| Center of gravity / tilt | none; tilt = waterDepth/2 | 13 directions, 0–250 m | tilts the map so rivers flow |
| Streams | auto: on | checkbox | draws `waterway` lines 1 px wide |
| Plains smoothing "To (m)" | 140 | 0–250 | 3×3 mean kernel applied only below `plainsHeight + waterDepth` |
| Passes / post passes | 7 / 3 (auto 10 / 2) | 0–25 / 0–10 | |
| Stream depth | auto 7 | 0–10 m | (stored default reads 140, likely a copy-paste bug) |
| Sharpen | fixed 5×5 kernel above plains | — | "dramatize mountains" |
| Level correction | None | None, Coastline & plains, Aggressive coast & plains, Plains & dramatic mountains | piecewise elevation curves in `levelMap()` |

- Exports: 16-bit PNG, RAW, map image, ZIP with lng/lat, OSM (Overpass).
- README examples: Alps (200–2200 m) → auto base 200 m, scale 50 %, below sea level 5 m. San Francisco (0–350 m) → scale 300 %, 20 m below sea level, "only land raised".

### Terraining (nonta1234/terraining-heightmap-generator) — most complete current tool
- Source: https://github.com/nonta1234/terraining-heightmap-generator; site terraining.ateliernonta.com. Based on the skydark code; needs a MapTiler key. Supports CS1 and CS2.
- **Defaults [S, `src/utils/const.ts` `initialValue`, `mapSpec.cs1`]**: size 17.280 km, resolution 1081, elevation scale 1023.984375 m, base level 0, `vertScale 1.00`, type `manual` (Manual / Limit / Maximise), water `depth: 40`, `littoral: 160` with a `sine` profile (linear/sine/cubic/quint tables), `riparian: 10`, `streamDepth: 0`, `streamWidth: 10`, `smoothing: 0` (Gaussian, radius 1), `sharpen: 0` (unsharp, radius 1), noise 0 (applied by Terrain Ruggedness Index), interpolation `bicubic`, grid angle 0.
- CS1 area 8.64–69.12 km; CS2 28.672–229.376 km (default 57.344 km, 4096 px).
- Unique ideas: a **littoral slope** (gradual coast to seafloor), a **riparian zone** for rivers and lakes, a triangulated **water-depth correction editor**, "use actual seafloor" (MapTiler Ocean RGB), rotation of the selection, smoothing below and sharpening above a threshold.

### tangrams heightmapper
- Source: https://github.com/tangrams/heightmapper. Generic, not CS-specific.
- Knobs [S, `main.js`]: `autoexpose = true` (lowest visible point black, highest white), min/max elevation sliders (−10916…8848 m), "include ocean data" (default false), z:x scale factor (read-only), render multiplier 1–8.
- [I] Auto-exposure stretches any view to full range, so a straight import exaggerates relief, and the canvas export is 8-bit (terracing). Users report it as "not designed for CS, more manual work for map size" and later broken.

### pepijndevos/citiesheightmap (SRTM Python script)
- Source: https://github.com/pepijndevos/citiesheightmap. Defaults [S, `heightmap.py` argparse]: `--span 18` km, `--height-scale 64` (16-bit units per metre, i.e. 1:1), `--blur 2`, `--sealevel 40`, `--seabed -10` (relative), `--fix-water` on (burns OSM water to seabed). README pitch: "improved handling of water and negative altitudes … islands and polders work out of the box."

### Other small generators
- **usagi/cities_heightfield_from_gsi** (Japan GSI DEM): `--altitude_bias 40.0` m, no-data altitude 0 [S, README].
- **marchmarch/add-water**: burns OSM water polygons and waterways (stroke 0.9 px) black into terrain.party PNGs with mapnik [S, `add-water.py`]. [I] Crude: zero-height water, no depth profile.
- **maps4cities**: not found by web or GitHub search. Couldn't verify it exists.
- **frontierkodiak/region-to-skylines** turned up in the GitHub search ("Turn any real place into a Cities: Skylines heightmap, in the browser, from open data"). That is ours, so I didn't review it.

### Cities Skylines Mapper (lxteo) and its OSM forks
- Sources: https://github.com/lxteo/Cities-Skylines-Mapper (2016), forks rdiekema/Cities-Skylines-Mapper, adur1990/grilly86 Open-Cities-Map → Workshop "OpenStreetMap Import" ([1957515502](https://steamcommunity.com/sharedfiles/filedetails/?id=1957515502)).
- Roads only (plus a dam mapping). Knobs [S, README]: scale (broken), tolerance (point simplification), curve tolerance, "tiles to boundary" (2.5 = inner 25 tiles, 4.5 = all 81). Notes the 32,767 road-segment limit. No trees, water or resources.

### GeoSkylines (gonzikcz) and the DavixDevelop fork — the only real land-cover importers
- Sources: https://github.com/gonzikcz/GeoSkylines (Workshop [2292938303](https://steamcommunity.com/sharedfiles/filedetails/?id=2292938303)); fork https://github.com/DavixDevelop/GeoSkylines (Jan 2025, with `VectorToTreesXML.py` and `ImageToTreesXML`).
- Imports from CSV/WKT: roads, rails, water bodies, waterways, trees (raster or vector), zones, services. Water is carved, not filled: **"the depths must be exaggerated for the game water dynamics to work properly"**. Example configs use waterway depths 15/10 m, an extra width of 1 cell (16 m) for rivers, standing water 15 m. You add the water sources yourself afterwards.
- **Raster trees [S, `GeoSkylinesImport.ImportTreesRaster`]**: `trees.png` must be 1081×1081 (±tolerance). Each non-white pixel → one tree at the pixel centre plus uniform jitter of ±half a pixel (`(0.5 − rand) × scale`, scale = 17280/1081 = 15 m in integer maths). `ImportTreesRasterMultiply` thins (−N) or doubles (+N). Stops at `treesCreated > 250000`. `density = 1` (pixel stride).
- **Vector trees**: one tree per CSV point (UTM, centred on a configured lat/lon).
- **Species**: `ImportTreesTreeTypes` is a list; each tree picks one **uniformly at random**. The Lisbon and Olomouc examples use `Tree2,Tree2variant,Tree3variant,Bush02,Corsican Pine 01,Green Tree 01` (vanilla internal names, see §4).
- **DavixDevelop fork [S, `VectorToTreesXML.py`]**: forest polygons carry species percentages (`oak1`, `spruce2` …) that map to composition ids, and each id gets its own prefab list (`[1{0}],[2{1|6}]`). Example budget: `total_trees_count = 1800000` (with the Tree Control mod), of which `non_play_area_tree_count = 550000` go outside the play area with weight `1 − normalized distance` from it, so far tiles get sparser. `play_area_offset = 3640` "instead of 3840 … creates a less hard edge". Placement inside a polygon: a **jittered grid** (spacing from area / count, jitter ±2 m) when more than 8 trees, then `randomPointsInPolygon` for the remainder; species labels are shuffled. The raster tool maps pixel colours to ids, one tree per pixel at any resolution.
- Related benchmark [S, search summary of a Paradox forum post]: the 2021 "Global Build-Off: Berlin" map held about 368k real trees using 56 custom assets (modded).

### Cimtographer (PropaneDragon)
- Source: https://github.com/PropaneDragon/Cimtographer (2016). **Export only**: it writes your city to OSM, including water and ground contours (`OSMExportNew.ExportGroundAndWater`). No import; irrelevant to placement.

### Procedural generators that place resources and trees
- **Terrain Generator** (tomarus/cs-terraingen, Workshop [453425585](https://steamcommunity.com/sharedfiles/filedetails/?id=453425585), 2016). Diamond-square fractals for terrain and resources.
  - Terrain defaults [S, `TerrainUIPanels.cs`]: smoothness 8, scale 0.75, offset 0, blur 1. Resource defaults: smoothness 6, scale 0.75, **forest 0.5, ore 0.33**.
  - Resources (`DoResources`): one fractal is thresholded into bands in a fixed order, fertility → forest → ore → forest → oil, and each cell is written **binary 255**. Forest cells also get `m_tree = 120` ("// ??").
  - Trees (`DoTrees`): per forest cell (33.75 m), up to `density` trees (default **16**, slider 1–64, auto-capped to 250k/total). Uniform random position in the cell, prefab uniformly random from the environment's `TreeCollection` (the code's `r.Next() & (n−1)` is biased when n isn't a power of two), optional "inside 25 tiles".
  - Author's own caveats: trees get planted underwater; tidy shorelines by hand; deleting trees deletes forest resource.
- **Random Terrain Generator** (ash, [497439640](https://steamcommunity.com/sharedfiles/filedetails/?id=497439640)): gradient noise, mountain height scale, horizontal scale, sea-level river and lake channels. Terrain only. One user asked for a gentle slope across the map so rivers flow.
- **TotalTerrainTool** ([1894371878](https://steamcommunity.com/sharedfiles/filedetails/?id=1894371878)): whole-map smooth, set, add, subtract, round, max, min, normalize, Perlin, height². Its descriptions double as a list of user pains: "smooth all of it because you accidentally saved your heightmap as 8-bit", "starting your map at 40 meters is just plain wrong".

---

## 2. Map Editor and in-game helper mods

### Extra Landscaping Tools (formerly "Natural Resources Brush"), BloodyPenguin
- Source https://github.com/bloodypenguin/Skylines-ExtraLandscapingTools (the repo description still reads "Natural Resources Brush mod"). Workshop [502750307](https://steamcommunity.com/sharedfiles/filedetails/?id=502750307) (about 2.36M subscribers); bug-fix fork "ELT Revisited" [3733110460](https://steamcommunity.com/sharedfiles/filedetails/?id=3733110460).
- What it does [S]: brings the **vanilla** Map Editor `ResourceTool`, `WaterTool` and terrain tools into the game. It doesn't change how resources are stored. Adds a tree brush and a tree pencil.
- Knobs [S, `UI.cs`, `TreeToolDetour.cs`]: brush size 14–2000, strength 0–1 (step 0.01), water capacity 0.0001–1 (the page: "manual input … smaller than 0.01 (0.0001 minimum)"), level height 0–1024 m. Tree pencil spacing: a new tree only when the mouse has moved `25 − 25 × strength` m.
- Its "possible future features" include "random trees placement". Users praise in-game resource painting, which is used to fix maps with bad resources.

### Surface Painter (BloodyPenguin)
- Source https://github.com/bloodypenguin/Skylines-SurfacePainter, Workshop [689937287](https://steamcommunity.com/sharedfiles/filedetails/?id=689937287). Paints vanilla surface types (pavement, gravel, field, ruined) on a 4320×4320 grid stored in mod data `SurfaceManager`. Not available in the Map Editor; reverts if the mod is removed. [I] Not usable for a vanilla map file.

### Forest Brush (TPB) and Forest Brush Revisited (Sleepy)
- Sources: https://github.com/twilightsaurus/ForestBrush (TPBCS original, 2019), https://github.com/Sleepy334/ForestBrushRevisited (2025). Workshop [1658679290](https://steamcommunity.com/sharedfiles/filedetails/?id=1658679290) (352k) and [2869784351](https://steamcommunity.com/sharedfiles/filedetails/?id=2869784351) (772k). The best model of "hand-made" forest.
- Brush defaults [S, `Brush.cs`]: `Size = 150`, `Strength = 0.2`, `Density = 8`, `AutoDensity = true`. Revisited adds `SlopeLimit = 40` (slider 1–100, in percent).
- Ranges [S, `Tool.cs`]: size 1–`MaxSize` (1000); strength 0.01–1; density clamped 0.5–16 (the UI shows `(16 − density) × 6.45 %`).
- Hidden constants [S, `Tool.cs` `Tweaker`]: `SizeAddend = 10, SizeMultiplier = 7, NoiseScale = 16, NoiseThreshold = 0.5, MaxRandomRange = 4, Clearance = 4.5, SingleTreeClearance = 0.3, SpacingFactor = 0.6, StrengthMultiplier = 10`.
- **Algorithm [S, `AddTreesImpl`]**, per stroke tick:
  1. Try `Size × 7 + 10` random points in the brush circle.
  2. Accept a point with probability `Strength × (brush × 1.2 − 0.2)`, where `brush` is the bilinear sample of a 128×128 brush texture. This gives soft, decaying edges.
  3. Pick the species from the brush's weighted variation list.
  4. Reject if the slope exceeds the limit (Revisited: `max(|slopeX|, |slopeZ|) > SlopeLimit/100`).
  5. Reject if another tree overlaps a square of half-side `spacing`, where `spacing = crown width × 0.6` (auto) or `Density` m.
  6. Reject if a prop, road or building is within the 4.5 m clearance, or if the point is in water (Shift overrides).
  7. Plant only if `PerlinNoise(x·k, y·k) > 0.5` (k random 0–15) **and** `rand(0, 4) < Strength × 10`. Uses `CreateTree(…, single: false)`.
- **Species mix [S, `ProbabilityCalculator.cs`]**: weights → percent, floored, minimum 1, then fixed up so they sum to exactly 100 (game `TreeInfo.Variation.m_probability`). At most 100 species.

### Other tree brushes
- **TreeBrush** (Destroyer, [423964385](https://steamcommunity.com/sharedfiles/filedetails/?id=423964385); ELT also links 406723376): old, mostly broken (comments: "Cannot create any more objects of this type").
- **Random Tree Brush** ([1654658173](https://steamcommunity.com/sharedfiles/filedetails/?id=1654658173)): pick several trees and each click places a random one. Users ask for presets, select-all, "a prop-line-tool like functionality for rows of random trees".
- **No Tree Brush Slope Limit** (BloodyPenguin, [554763781](https://steamcommunity.com/sharedfiles/filedetails/?id=554763781), source https://github.com/bloodypenguin/Skylines-NoTreeBrushSlopeLimit): zeroes `slopeX`/`slopeZ` from `TerrainManager.SampleDetailHeight` while the tree or prop tool is active. This shows vanilla brushes have a slope cutoff; the constant lives in `TreeTool`, which isn't decompiled here. A map maker in the comments asked for the opposite: "I'm much stricter … If the slope is so great that there's just a hint of rock, there should be no tree there. I used to go through the map, manually … to remove all the incredibly crazy placed trees."

### Anarchy, unlimited trees, tree control (all BloodyPenguin, Quistar or algernon lineage)
- **Prop & Tree Anarchy** ([593588108](https://steamcommunity.com/sharedfiles/filedetails/?id=593588108), about 1.1M): place trees under water, on roads, in building footprints. Also "helps to load maps with missing tree or prop assets because it fixes buggy code of Cities: Skylines".
- **Unlimited Trees** (mabako → Knighth/TreeUnlimiter → BloodyPenguin/DRen72; Workshop [455403039](https://steamcommunity.com/sharedfiles/filedetails/?id=455403039), last code 2018; source https://github.com/Knighth/TreeUnlimiter, also cloned bloodypenguin/TreeUnlimiter).
  - Scale factor 4 (default), 5, 6, 7 or 8 × 262,144 [S, `Config.cs`: values outside 4–8 reset to 4].
  - Storage [S, `LimitTreeManager.cs`]: trees are packed so the vanilla section holds the first 262,144; the rest go to `SimulationManager.m_serializableDataStorage["mabako/unlimiter"]` as ushorts per slot (flags, infoIndex, posX, posZ, plus a header with format version and counts).
  - Recent comments: "all trees gone", "save corrupted"; others say "use Tree Control instead".
- **Unlimited Trees: Revisited** ([2378914031](https://steamcommunity.com/sharedfiles/filedetails/?id=2378914031)): deprecated in favour of Tree Anarchy.
- **Tree Anarchy** ("Unlimited Trees: Rebooted", https://github.com/Quistar-LAB/TreeAnarchy; Workshop 2527486462, which I couldn't read directly because Steam rate-limited me).
  - Scale factor slider 1.5–20 in 0.5 steps, default 4 [S, `TAOptionPanel.cs`, `TAMod.cs`]. Per-tree scale 0.2–5.0.
  - Saves extended trees, including `m_posY` and an extra scale, under the data key `TreeAnarchy`.
  - Search summary of its page: about 14 bytes of RAM per tree; never shrink the limit for an existing save.
- **Tree Control** (algernon, https://github.com/algernon-A/TreeControl, Workshop [2960858317](https://steamcommunity.com/sharedfiles/filedetails/?id=2960858317), 315k). The current standard; it bundles tree snapping, per-tree scaling, random rotation, sway control, lock forestry and a LOD fix.
  - Limit 262,144 up to 8× (`MaxCustomTreeLimit = MAX_TREE_COUNT * 8`).
  - Data keys `MoreTrees`, `TreeScaling`, `TreeSnapping`, `TreeControlAnarchyFlags`; it also reads `mabako/unlimiter` and `TreeAnarchy`.
  - Page, verbatim: "Doesn't alter any savefile structure, and saves its data separately to core game data. Can be safely removed at any time (any trees outside of the normal vanilla tree limit will be lost, and any snapped trees will reset to terrain height)."
  - Its collision check uses radius `instance.Single ? 0.3f : 4.5f`, so brush trees count as 4.5 m clusters.
- **Random Tree Rotation** (boformer, [556784825](https://steamcommunity.com/sharedfiles/filedetails/?id=556784825), 252k): "All instances of a tree … are rotated in the same way, which looks very unnatural." Render-time only (detailed models, not LODs); safe to remove.
- **Tree Movement Control** ([1388613752](https://steamcommunity.com/sharedfiles/filedetails/?id=1388613752)): wind sway; now inside Tree Control.
- **Tree Precision**: not found under that name. Tree Control's scaling and elevation plus Move It cover precise tree edits. "Precision Engineering" is a road tool.

### Image Overlay / Image Overlay Renewal
- [2616880500](https://steamcommunity.com/sharedfiles/filedetails/?id=2616880500) (original 814102166). Overlays a PNG (under 15,000×15,000 px recommended, from `Files/`) on the map for tracing real places; Ctrl+I; opacity. Its page recommends Terraining and heightmap.skydark.pl for heightmaps. [I] The real-world-overlay need our tool removes.

### 81 Tiles / 81 Tiles 2 (algernon, [2862121823](https://steamcommunity.com/sharedfiles/filedetails/?id=2862121823), about 1.8M)
- Unlocks all 81 tiles (vanilla: 25). It **disables the editors** ("patch[es] the game code in a way that breaks maps and assets saved in the editors").
- [I] Implication: most of a 17.28 km map is scenery for vanilla players, but 1.8M subscribers build on all 81 tiles, so resources and forests in outer tiles do matter to many players.

### Loading Screen Mod Revisited (algernon, [2858591409](https://steamcommunity.com/sharedfiles/filedetails/?id=2858591409))
- Can skip tree prefabs at load. Its companion list https://lsmr.thebugfix.net/trees.txt (copy at `web/lsmr_trees.txt`) groups vanilla trees by `TreeCollection`. I use it in §4.

### Not found
- "Map It!", "Map Editor Expansion", a dedicated "water source helper", and any "auto resources" mod besides Terrain Generator. Workshop searches for water sources, resources, map editor tools and procedural returned nothing relevant. The closest are ELT's water tool, Map Editor Tunnels Enabler and TerrainRiverTool (1902022083), whose page I couldn't fetch after Steam rate-limited me.

### CS2, for comparison only
- Map editor dev diary ([Paradox](https://www.paradoxinteractive.com/games/cities-skylines-ii/modding/dev-diary-2-map-editor)):
  - Heightmaps 4096² 16-bit, plus an optional world map whose centre 1024² matches the playable map.
  - Water source types: constant rate, constant level, border river, border sea.
  - Resources (fertile, oil, ore, **groundwater**) painted with brushes **or imported as a greyscale 256×256 mask per resource** ("white to add … black where you want none").
  - Overlap rules: forest excludes fertile, ore excludes oil, the same as CS1.
- No auto-generation of resources found. CS2's Tree Controller (yenyang) adds forest-brush **sets** (Deciduous, Evergreen, Wild bushes, custom), age choices and random rotation.

---

## 3. Tree limit: what happens above 262,144

- [S] Vanilla stores exactly 262,144 slots (§0). Every unlimited-trees mod keeps the vanilla section valid and puts extra trees in a named `m_serializableDataStorage` blob: `mabako/unlimiter`, `TreeAnarchy` or `MoreTrees`.
- [S, Tree Control page] Without the mod, "any trees outside of the normal vanilla tree limit will be lost". The save still loads.
- [I] A map with more than 262k trees therefore **doesn't break vanilla players; they silently get the first 262,144** (whatever the mod packed into the vanilla section). Then the vanilla game refuses every new tree (cap 262,139), and the Map Editor refuses new trees above 250k.
- [I] For a vanilla-first tool: write at most about 262k into the vanilla section, and keep a budget below that. A 250k map leaves a player about 12k trees.
- Tree counts seen:
  - 250k: Map Editor cap; GeoSkylines stops there.
  - "Pineridge River" Workshop map: 545k (modded, via search summary).
  - Berlin Build-Off: about 368k (modded).
  - DavixDevelop's plan: 1.8M (Tree Control).
  - **Base-map tree counts: not found**. They could be measured directly by reading a built-in map's TreeManager section with our own `.crp` reader.

---

## 4. Tree prefab names per environment

Environment ids [S, locale `THEME_NAME`]: `Sunny` = Temperate, `North` = Boreal, `Tropical`, `Europe` = European, `Winter` (Snowfall DLC). These are the strings in `MapMetaData.environment`.

Sources:
- **Internal name → display name**: English locale dump `TREE_TITLE` keys, game 1.20.1-f1 (https://github.com/mzch/CSL_LocaleJa, file `1.20.1-f1.tsv`; copy at `web/csl_locale_1.20.1.tsv`).
- **Display name → theme**: [Paradox wiki, Trees](https://skylines.paradoxwikis.com/Trees) ("Availability").
- **Cross-check**: LSMR `trees.txt`, which lists the TreeCollections "Europe Beautification" and "Winter Beautification". The Europe list has the conifers but no `Bush02` and no palms, exactly as the wiki says.

| Internal prefab name | Display name | Temperate (Sunny) | Boreal (North) | Tropical | European (Europe) |
|---|---|---|---|---|---|
| `Beech01low` | Small Beech | ✓ | ✓ | ✓ | ✓ |
| `Alder01` | Alder (wiki: "Alder #2") | ✓ | ✓ | ✓ | ✓ |
| `Bush01` | Small Bush | ✓ | ✓ | ✓ | ✓ |
| `Tree2` | Oak ([I] likely a random container of the two below: NetworkSkins and PropItUp call it "Random Oak") | ✓ | ✓ | ✓ | ✓ |
| `Tree2variant` | Tree with Leaves #1 ("Small Oak") | ✓ | ✓ | ✓ | ✓ |
| `Tree3variant` | Tree with Leaves #2 ("Large Oak") | ✓ | ✓ | ✓ | ✓ |
| `Green Tree 01` | Green Tree (patch 1.9) | ✓ | ✓ | ✓ | ✓ |
| `Giant Redwood 01`, `Giant Redwood 02` | Giant Redwood #1/#2 (1.9) | ✓ | ✓ | ✓ | ✓ |
| `Flower Tree 01`…`04` | Flower Tree #1–#4 (1.9) | ✓ | ✓ | ✓ | ✓ |
| `Chinese Windmill Palm 01` | (1.10) | ✓ | ✓ | ✓ | ✓ |
| `Corsican Pine 01` | (1.10) | ✓ | ✓ | ✓ | ✓ |
| `Sugar Maple 01` | (1.10) | ✓ | ✓ | ✓ | ✓ |
| `Yew 01` | (1.10) | ✓ | ✓ | ✓ | ✓ |
| `Conifer` | Conifer #1 | | ✓ | | ✓ |
| `Conifer2` | Conifer #2 ("Small Conifer") | | ✓ | | ✓ |
| `Pine01low` | Pine | | ✓ | | ✓ |
| `treeForest` | Wild Conifer ("Large Conifer") | | ✓ | | ✓ |
| `Bush02` | Large Bush | ✓ | | ✓ | |
| `palm01` | Palm Tree | | | ✓ | |
| `palmplant01` | Palm Plant | | | ✓ | |

- **Winter** [S, LSMR "Winter Beautification" + locale]:
  - Natural set: `Alder01Winter`, `Beech01Winter`, `Bush01Winter`, `Pine01Winter`, `Coniferwinter`, `Conifer2Winter`, `WintertreeForest`, `Tree2Winter` (= Tree with Leaves #1), `Tree2Wintervariant` (= **Oak**; the suffix swaps compared with summer), `Tree3Wintervariant` (Tree with Leaves #2).
  - Patch trees as "<name> Winter": `Green Tree 01 Winter`, `Giant Redwood 01/02 Winter`, `Flower Tree 01–04 Winter`, `Chinese Windmill Palm 01 Winter`, `Corsican Pine 01 Winter`, `Sugar Maple 01 Winter`, `Yew 01 Winter`.
  - No winter Large Bush or palms.
- **Content-creator trees, patch 1.14, free [S wiki: "Content Creator Trees tab … by MrMaison"]**: `mp9-BloomingJacarandavnl`, `mp9-BorealPine`, `mp9-CaliforniaPalm`, `mp9-CoconutTreevnl`, `mp9-EasternCottonwood`, `mp9-GenericDatePalm`, `mp9-GenericPineTree`, `mp9-HorseChestnutvnl`, `mp9-Lantanavnl`, `mp9-LiveOaknvl`, `mp9-PacificRhododendronvnl`, `mp9-TallGrassClustervnl`, `mp9-WildHedgevnl`, `mp9-YoungLinden`. LSMR lists the same names (unsuffixed) in both the Europe and Winter collections. [I] Probably loaded in every theme; verify before relying on them.
- **Avoid as wild trees**:
  - Industries farm and forestry props: `Apple Tree 01`, `Orange Tree 01`, `Pear Tree 01`, `Tree Sapling 01` (+ Winter).
  - Pack-gated: `CherryTree01` (Paradox signup pack), `Bamboo1`/`Bamboo2` (China pack).
  - Unknown availability: `Beech`, `Test` (Conifer #3), and the 1.16.1/1.17.0 additions `Baobab`, `California Young Palm`, `Flame Tree`, `Lala Palm`, `Umbrella Thorn`, `Large Shrub`, `Norway Spruce`, `Silver Birch` (+ Winter). LSMR says its list excludes the newest DLC and content-creator packs; [I] these look DLC/CCP-gated. A missing prefab logs `Unknown prefab` and the tree doesn't render.
- [S] Original-release split (wiki Map Editor): beech and alder in Sunny, conifer and pine in North, palms in Tropical, bushes everywhere. The newer Trees page says the leafy set is available in all themes. [I] For natural-looking maps use the biome set (Boreal → conifers, Temperate → beech/alder/oak, Tropical → palms + Bush02) and treat the all-theme trees as accents.

---

## 5. Synthesis

### 5.1 Knobs that recur, with their usual defaults

**Terrain** (columns: terrain.party / skydark / Terraining / pepijndevos / GSI / GeoSkylines)
- **Area**: 17.28 km is the standard; terrain.party (18 km) and pepijndevos (`--span 18`) default to 18 km, which is the 4% scale bug. CS1 range offered: 8.64–69.12 km.
- **Vertical scale**: 1:1 by default everywhere. skydark adds "Auto" = `min(250 %, (1024 − waterDepth)/(max − min))`. Terraining offers Manual / Limit / Maximise. Users exaggerate flat sites (README: San Francisco 300 %) and compress mountains (Alps 50 %).
- **Base / sea offset: 40 m is the convention**:
  - terrain.party lowest point → 40 m;
  - skydark water depth 40 (0–60);
  - Terraining depth 40;
  - pepijndevos sealevel 40, seabed −10;
  - GSI bias 40;
  - CS default sea level 40 m.
- **Water carving**: rivers and lakes need exaggerated depth (GeoSkylines 10–15 m; skydark streams 0–10 m, auto 7). Coastal slopes: Terraining littoral 160 with a sine profile, riparian 10.
- **Smoothing**: smooth the plains, keep or sharpen the mountains (skydark: 3×3 mean below 140 m + water depth, 7–10 passes then 2–3 post passes, 5×5 sharpen above; Terraining Gaussian and unsharp around a threshold, off by default; pepijndevos blur 2). Always 16-bit output.
- **Tilt** so rivers flow (skydark "center of gravity", 0–250 m; a user asked Random Terrain Generator for it).

**Trees**
- Brush size: Forest Brush 150 (1–1000); vanilla editor 50–2000 (50 = single trees); ELT 14–2000.
- Strength: Forest Brush 0.2; vanilla resource brush 0.5; range 0.01–1.
- Spacing: Forest Brush auto `0.6 × crown width`, or 8 m manual (0.5–16).
- Slope limit: Forest Brush Revisited 40 % (1–100); vanilla has a hard-coded cutoff.
- Species weights summing to 100 %.
- Density per resource cell (Terrain Generator 16, range 1–64) or per pixel (GeoSkylines one per 16 m pixel, multiply ±N).
- Area restriction (inner 25 tiles, coordinate max).
- Hard cap 250k; with mods, a limit multiplier (Unlimited Trees 4–8 ×, default 4; Tree Anarchy 1.5–20, default 4; Tree Control up to 8 ×).

**Resources**
- Vanilla brush 200 / 0.5. Terrain Generator: forest 0.5, ore 0.33, binary 255 cells.
- CS2's answer is a 256² greyscale mask per resource.

### 5.2 What veteran users ask these tools for
- **Correct scale and true 1:1 by default**, with controls to exaggerate flat sites or squeeze high ones into 1024 m. Complaints: 18 km boxes, broken scale fields, auto-exposure stretching.
- **Sea level and water that work in the simulation**: not "everything starts at 40 m"; rivers deep enough to hold water; lakes, polders and islands that work "out of the box" (pepijndevos's whole pitch); soft coastlines (Terraining's littoral and riparian controls); outside water you only need to switch on.
- **No terracing**: 16-bit output, smoothed plains (TotalTerrainTool's "accidentally saved as 8-bit").
- **Trees that look painted, not stamped**: mixed species (Forest Brush, about 1.1M subscribers across both versions; Random Tree Brush; CS2 forest sets), random rotation (Random Tree Rotation 252k, now in Tree Control), no trees on rock or steep slopes (explicit request; slope limit added in Forest Brush Revisited), none in water (Terrain Generator's own caveat), none on roads or buildings (4.5 m clearance), lines of random trees for hedges and avenues.
- **Room under the tree cap**, or a mod to lift it (Unlimited Trees, Tree Anarchy, Tree Control). Players hit "cannot create any more objects".
- **Resources where reality puts them, and editable later**: ELT's in-game resource painting (2.36M subscribers) exists because maps ship with poor resources. Forest that doesn't wipe fertile land ("Lock Forestry" exists to stop tree edits from changing forest resources).
- **Real land cover**: GeoSkylines and the 2025 DavixDevelop fork (species composition per forest polygon; dense play area, thinned outskirts). OSM roads importers are popular but struggle with node limits and short segments.
- **Use of all 81 tiles** (81 Tiles 2, about 1.8M), so the outer tiles need believable forests and resources too.

### 5.3 Tree-prefab names per environment
See the table in §4. Short version:
- Temperate (`Sunny`): `Beech01low`, `Alder01`, `Tree2variant`, `Tree3variant`, `Bush01`, `Bush02`, plus the all-theme extras.
- Boreal (`North`): `Conifer`, `Conifer2`, `Pine01low`, `treeForest`, plus `Beech01low`, `Alder01`, `Bush01`.
- Tropical: `palm01`, `palmplant01`, `Bush02`, `Bush01` (+ leafy).
- European (`Europe`): Boreal's conifers plus the leafy set, no `Bush02`.
- Winter: the `…Winter` set (`Coniferwinter`, `Conifer2Winter`, `Pine01Winter`, `WintertreeForest`, `Tree2Wintervariant`, `Tree3Wintervariant`, `Tree2Winter`, `Beech01Winter`, `Alder01Winter`, `Bush01Winter`, plus the "<1.9/1.10 name> Winter" trees).

### 5.4 How to place trees and paint resources so it looks hand-made
Mechanics the game imposes [S, §0]:
- Scale and brightness come from the slot index; rotation is fixed; position is quantized to about 26 cm; height conforms to terrain on load.
- So the only visual levers are **species mix, spacing pattern and the slot→position mapping**. [I] Shuffle slot indices instead of filling them in raster order. Then neighbours don't get consecutive `Randomizer` seeds, and scale and brightness stay decorrelated in space (worth checking against the Randomizer).
- Write brush-style trees: `Created`, `GrowState = 15`, not `Single`.
- Keep forest and fertility consistent:
  - every cell with a tree gets `m_forest = min(60n, 255)` and fertility 0;
  - 5 trees per 33.75 m cell saturate forestry;
  - [I] so keep fields free of scattered trees and put hedgerows on cell lines or accept the fertility loss.

Placement recipe distilled from Forest Brush, GeoSkylines and DavixDevelop ([I], with sourced constants):
1. **Mask** where trees are allowed. Land-cover forest or scrub, minus:
   - water (`HasWater`) and a shoreline buffer;
   - slope above 0.40 (Forest Brush Revisited default; slopes are `max(|dh/dx|, |dh/dz|)`);
   - a 4.5 m clearance around roads, rails, buildings and props;
   - [I] fields marked fertile.
2. **Density with soft edges**: probability = strength × falloff, where falloff rises from the polygon edge inward (Forest Brush's `brush × 1.2 − 0.2` profile goes slightly negative at the rim, so edges thin out and fray).
3. **Clumps and glades**: gate by low-frequency noise (Forest Brush: `Perlin > 0.5` at a random scale per tree, plus random acceptance). This makes clusters and clearings instead of an even carpet.
4. **Spacing**: reject a candidate if another tree lies within about `0.6 × crown width` (Forest Brush auto). Practical default 5–8 m centre to centre for broadleaf; Forest Brush's manual default is 8 m. Within a polygon, a jittered grid (DavixDevelop ±2 m) plus a random remainder fills evenly without looking gridded; per-pixel imports should jitter ±half a pixel (GeoSkylines).
5. **Species mix**: weighted variation lists summing to 100 % per land-cover class (Forest Brush), using the biome set from §4. Put small trees and bushes (`Bush01`, `Bush02`, `Beech01low`) at forest edges and along fields and water [I], and conifers higher up and on cooler slopes in Boreal and Europe [I].
6. **Budget**: put trees in the 25-tile play area first and thin the outer ring with distance (DavixDevelop's `1 − normalized distance`, with a soft offset of 3640 m instead of 3840 m). Stay well under 250k for vanilla. [I] 150–200k leaves players 60–110k.
7. **Resources**:
   - Paint ore, oil, fertile land and sand as graded values, not binary blocks. The vanilla brush accumulates `255 × strength × brush` and ore/oil and sand/fertility are mutually exclusive, so the brush itself produces gradients.
   - Derive forest only from the trees.
   - Avoid Terrain Generator's look of binary bands on a fractal.
   - [I] Tie them to real data: ore in rocky uplands, oil in sedimentary basins and offshore, fertile land on flat low-slope soils away from forest and towns.

---

## 6. Not verified or not found
- Couldn't find: maps4cities, "Map It!", "Map Editor Expansion", "Tree Precision", a dedicated water-source helper, an auto-resource mod other than Terrain Generator, and **tree counts for the base maps**. I'd measure the base-map counts with our `.crp` reader.
- Vanilla `TreeTool` brush spacing and slope cutoff: not in `../decomp`. Decompiling `TreeTool` would give the exact numbers.
- Whether `Tree2` (Oak) is a variation container: inferred from two mods' display renames. If it is, write `Tree2variant`/`Tree3variant` directly, or check `m_variations` in-game with ModTools.
- Availability of the `mp9-*` trees in every theme, and the DLC status of the 1.16.1/1.17.0 trees: not verified.
- terrain.party's cause of death comes from search summaries of Paradox forum posts. The forum, Simtropolis, Reddit and Fandom all blocked my fetches, and late in the session Steam rate-limited me, so Tree Anarchy's Workshop page (2527486462) was seen only through search summaries.
- The ELT, Forest Brush and Tree Control knob values come from source, not from running the mods.
