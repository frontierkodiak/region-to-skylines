# cs1save: read Cities: Skylines 1 saves offline

Reads a CS1 `.crp` save or map without the game and returns the city: the road,
rail and path network (nodes and segments with prefab names and positions),
buildings (prefab, position, angle, level, footprint), zone blocks and cells,
trees, districts and their policies, parks, transit lines, the economy, and the
headline numbers the game keeps for the whole city. It also turns a run of saves
into a timeline page.

```sh
uv sync --extra plots
uv run cs1save info SAVE.crp                         # counts and the manager layout
uv run cs1save export SAVE.crp city.json             # the city model as JSON
uv run cs1save site SAVES*.crp --out DIR             # timeline page for every city with 2+ saves
```

```python
from cs1save.save import read_save
s = read_save("city.crp")
s.data["NetManager"]["segment_prefab"], s.data["BuildingManager"]["position"]
s.data["DistrictManager"]["city"]["population"]
```

## How it reads a save

The formats are transcribed from the game's own serializers
(`Assembly-CSharp.dll` and `ColossalManaged.dll` of CS1 **1.21.1-f9**, save format
**121034**), not inferred from bytes:

- `package.py`: the CRP container (format 12, little-endian) and its
  reflection-serialized metadata asset.
- `stream.py`: `DataSerializer` (big-endian numbers; shared string, type and object
  tables) and the `EncodedArray` run-length codecs, vectorized with numpy.
- `save.py`: the two streams in the Data asset (SimulationMetaData, then
  SimulationManager.Data). The second lists every manager's data type up front;
  each manager's block opens with its name as a new shared string and closes with
  a reference to it.
- `managers.py`, `districts.py`: one decoder per manager, each a transcription of
  that manager's `Data.Serialize`. A decoder must end exactly on its block's
  closing tag or the read fails. NetManager and BuildingManager are decoded by
  the codec the map writer encodes with, `tools/map-factory/netcodec.py`
  (`codec.py` loads exactly that file); there is no second decoder for them, and
  a game save re-encodes through it to the game's own bytes
  (`tests/test_shared_codec.py`). Managers without a decoder (citizens, vehicles,
  paths and the like) are passed over by finding the next manager's opening tag,
  which has one exact byte form.

Mod data (`m_serializableDataStorage`) is returned as raw bytes per key. Mods
that change the vanilla buffers, such as 81 Tiles, keep their extra state there,
so the vanilla 25-tile area grid is what `GameAreaManager` returns.

`city.py` turns the decoded managers into a plain model: segments as the game's
own Bézier curves (`NetSegment.CalculateMiddlePoints`), building lots, zone cell
centres. `classify.py` names a prefab's kind (local road, highway, rail; school,
park, growable). A save stores prefab names, not classes, so classes come from
`cs1save/data/prefabs-1.21.1-f9.json`, the catalog the running game reported
through cs1-harness `dump_prefabs` (base game and the DLC blade's copy loads).
Prefabs it doesn't know, such as mod networks and Workshop assets, fall back to
name rules and say so (`"source": "name"`).

## Tests

```sh
uv run --group dev pytest tests
CS1SAVE_PRIVATE_SAVES=/path/a.crp:/path/b.crp uv run --group dev pytest tests
```

`test_game_check.py` compares the reader with the running game on one save:
`tests/fixtures/game-check` holds a city cs1-harness built and grew on the stock
Green Plains map, and what the game held when it saved it (`dump_city`). Every
node, segment, building, zone block and tree matches by id, prefab, flags and
position. `test_stream.py` checks every codec against a literal transcription of
the game's element-by-element `Read()` on random streams. `test_template.py`
reads the public map-factory template. `test_private_saves.py` reads real player
saves, which stay out of this repository.

Only format 121034 is implemented; older saves are refused rather than guessed.
