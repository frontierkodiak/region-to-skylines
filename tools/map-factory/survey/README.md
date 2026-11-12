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
