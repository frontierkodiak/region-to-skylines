# Shipped-map survey

How CS1's 104 shipped maps (base game, DLC and content-creator packs, as
installed on blade at `/peach/Games/SteamLibrary/steamapps/common/Cities_Skylines/Files/Maps/`)
distribute natural resources and trees. The resource stage (`../resources.py`)
is calibrated against these numbers.

```sh
uv run python survey/measure_maps.py MAPS_DIR survey/basemaps.json   # decode every map
uv run python survey/measure_blobs.py MAPS_DIR/*.crp                  # blob shapes -> extra.json
(cd survey && uv run python analyze_maps.py)                          # -> basemaps-tables.md
```

`measure_maps.py` reads any CRP package format (4-12) and decodes MapMetaData,
NaturalResourceManager, TreeManager, TerrainManager, WaterSimulation and
GameAreaManager with CS1 1.21.1-f9's version gates. It is also an independent
decoder for this writer's output. `basemaps.md` is the written summary,
`basemaps-tables.md` the generated tables. Measured 2026-11-10 (PL-902).

## Terrain-shape interest (PL-1228)

The two terrain-shape interest measures are re-measured into a separate
artifact, never into `basemaps.json` or the historical tables:

```sh
cd tools/map-factory
uv run python survey/measure_terrain_interest.py \
  /peach/Games/SteamLibrary/steamapps/common/Cities_Skylines/Files/Maps/ \
  survey/terrain-interest.json
node capability-ledger.mjs --refresh-stock
```

`measure_terrain_interest.py` imports `terrain_interest.terrain_interest_metrics`,
the same function the prepared report uses, so a stock observation and a square's
report share one predicate: the 1081-square, 16 m, south-first game grid at the
1/64 m terrain unit, with the central 25 tiles' node set.

| Measure | Definition |
|---|---|
| Terrain roughness | mean terrain gradient magnitude at 16 m spacing over all 1081 x 1081 nodes, in percent |
| Central height range | 90th minus 10th percentile of terrain height over the central 25 tiles' nodes, in metres |

Both are terrain shape over all terrain, waterbeds included; neither is
buildability, dry room-to-grow or a water mask. The artifact records the sorted
file names and SHA-256, package/data versions, the reader and measure-source
hashes, the one exclusion (`CO.crp`, a blank editor terrain system package),
failures and all 104 measured rows, with linearly interpolated (n-1)*p
quartiles. `capability-ledger.mjs` re-derives those quartiles and re-hashes the
bound tools, so a stale artifact fails validation.
