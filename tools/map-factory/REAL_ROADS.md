# Real roads, rail, flight and ship paths (PL-982)

`real_roads.py` replaces the template's corridor highway with the square's
real OpenStreetMap motorways, trunks, ramps and main-line rail, adds a flight
path on the region's runway axis, and a ship lane on coastal squares. It runs
main's own `generate.generate` unchanged (preparation, resources and the native
water admission), then adds the roads to the final terrain, replans resources
around them and rewrites the map. `generate.py`, `paint.py` and
`fixtures/current.json` are untouched, so the shipping maps don't change. The
website and CLI stay opt-in until Rio and Pittsburgh pass the same in-game
checks.

```sh
uv run python real_roads.py PNG GEOMETRY OUTPUT --banks BANKS \
  --landcover landcover.u8.gz --evidence evidence.json
uv run python soak.py STAGE --prepared OUTPUT_PARENT --only REGION   # probes, no game
```

## What a map gets

- **Highways** (`osm_highways.py`): OSM `motorway` and `trunk` ways from the
  same OpenMapTiles z14 tiles the website already reads, joined across tiles,
  split into native one-way carriageways (`Highway`) and ramps (`HighwayRamp`,
  from `ramp=1`), resampled to 60–110 m segments with one shared tangent per
  through node. Profiles follow 150 m-smoothed terrain at no more than 6 %
  (ramps 8 %); planning grades the terrain within 40 m of the road, capped at
  ±15 m and never in mapped water. A segment over water, needing more than 20 m
  of fill, or on an OSM bridge becomes `Highway Bridge` / `HighwayRampElevated`
  with the template's native pillar. An OSM tunnel becomes `Highway Tunnel`
  segments behind a `Highway Slope` portal at each end, as the game builds
  them. Each carriageway that leaves the square ends in an outside connection
  exactly on the edge. Ramps to local roads we don't import stay as
  stubs: they're where the player joins the highway.
- **Rail**: OSM main-line `rail` (no yards, sidings or service spurs), parallel
  tracks within 25 m merged into one double-track `Train Track` centreline, at
  most 3.5 % grade, with `Train Track Elevated` bridges, `Train Track Tunnel`
  behind `Train Track Slope` portals, and a two-way `Train Connection` at each
  edge. It replaces the template's elevated corridor railway.
- **Terrain** is then shaped exactly onto the graded profiles (`seat`): flat
  within 14 m of a road or track, blending back to the land by 40 m, never in
  mapped water or its two-cell margin. This pass has no cap, so it removes the
  gaps the planning cap leaves; the receipt reports its largest cut and fill
  (Asheville 18.6 m and 17.8 m). Tunnel interiors are not seated; their portal
  segments are.
- **Grades in the curve**: each segment's end directions carry the grade at
  that node (the mean of the two segments at a through node), so CS1's curve
  follows the profile instead of easing level at every node.
- **Start tile**: one interchange's exit-ramp stub and on-ramp stub within
  400 m, with no bridge or railway within 250 m of them, and water in the tile.
  The standard tile stays when its interchange qualifies; otherwise the most
  central tile that does. Ramp ends that wait for local roads sit on a 60 m
  level pad at their height.
- **Flight path** (`transport_paths.air_path`): an edge-to-edge two-way
  `Airplane Path` on the extended centreline of the region's main runway (OSM
  `aeroway=runway`), cruising 300 m above the highest ground under it. Planes
  arrive on the real approach track; the player's airport joins it.
- **Ship lane** (`transport_paths.ship_path`): a two-way `Ship Path` through
  edge-connected water at least 6 m deep, from the most open edge, past the
  start tile's shore, to a second edge.
- **New Game panel**: incoming/outgoing road, plane and ship counts match the
  written connections.

## How the map is written

`netcodec.py` decodes and re-encodes `NetManager.Data` and
`BuildingManager.Data` exactly as CS1 1.21.1-f9 serializes them
(`Assembly-CSharp` SHA-256 `c7f0e723…11a1`, decompiled `acs.cs`
`NetManager.Data.Serialize` and `BuildingManager.Data.Serialize`). It is the
one decoder for these sections: the offline save reader (`tools/save-reader`)
reads games through it too, guide and milestone prefabs included. Its array
encoder is ColossalFramework's `EncodedArray` writer transcribed exactly, so an
unchanged section re-encodes to the game's own bytes: the shipping template
and real game saves (a 26,000-node city among them) round-trip byte for byte.

Facts the writer relies on, each checked in the game source:

- **Lanes are optional on disk.** `NetManager.Data.AfterDeserialize` calls
  `NetSegment.UpdateLanes(loading: true)` for every segment, and
  `NetAI.UpdateLanes` allocates a missing lane chain (`CreateLanes`) before
  computing its curves. New segments are written with `m_lanes = 0`.
- **Prefabs bind by name.** Each `PrefabCollection<T>` block is an index array
  followed by the collection's name table; names absent from the template are
  appended. The vanilla names come from a workshop map with pre-built networks
  (7th Island Enhanced): `Highway`, `HighwayRamp`, `Highway Bridge`,
  `HighwayRampElevated`, `Train Track`, `Train Track Elevated`,
  `Airplane Path`, `Ship Path`, and the outside-node prefabs
  `Train Connection Track`, `Airplane Connection Path`, `Ship Connection Path`.
  A ground highway's outside node is a plain `Highway` node.
- **Node flags are not recomputed on load.** They are written as
  `NetNode.CalculateNode` would set them: `End|Moveable` for one segment,
  `Middle|Moveable` for two opposite directions, `Bend` otherwise, `Junction`
  for three or more, `Outside` alone at the edge; `OnGround` for ground
  networks; `OneWayOut` where a one-way segment starts and `OneWayIn` where one
  ends. The results match 7th Island's highways exactly (`0x1404121` through
  node, `0x404401` entry, `0x1004401` exit).
- **Outside connections are buildings.** An outside node's `m_building` is an
  outside-connection building (`Road Connection`, `Train Connection`,
  `Airplane Connection`, `Ship Connection`); the game never creates one on
  load. The writer clones the template's native records, moves them and, for
  two-way paths, sets `Incoming|Outgoing` (`0xC0`).

## Not done or not verified

- PL-1031 adds ramp tunnel/slope encoding after checking the stock prefab
  catalogue. That addition, like its local-street variants, still needs native
  qualification. See [the street pilot](STARTING_CITY.md).
- Rail crosses roads where OSM does; where neither side is a bridge (one in
  Asheville) the two overlap without a level crossing.
- Airports for squares outside the five fixtures must be passed as
  `geometry["airport"]`; the website capture doesn't read runways yet.
- The website and `cli.mjs` don't run this stage; adopting it means requalifying
  the shipping contract.
- In-game results live on PL-982.
