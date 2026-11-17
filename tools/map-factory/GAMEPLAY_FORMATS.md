# Gameplay layers: map versus save

Source-checked for CS1 **1.21.1-f9**, simulation format **121034**, on
2026-11-17 (PL-1019). Repository baseline:
`5a1e045d82eb5d3c54252c7a3c15246bf3acac50`, including PR #45's shared network
codec. This is a format reference, not a newly qualified gameplay exporter.
No game was launched for this investigation.

## A map is not a terrain-only container

A map and a city save both use a format-12 CRP package and a Data asset with
two successive `DataSerializer` roots: `SimulationMetaData`, then
`SimulationManager.Data`. The latter collects every registered manager's data
containers; it does not select a terrain-only subset for maps. Ordinary map
metadata is `MapMetaData` (asset type 100); city metadata is
`SaveGameMetaData` (101). The metadata selects a different entry path, not a
different network/building binary format.[^serialization]

The repository's `native-corridors.crp` map actually contains ZoneManager,
DistrictManager, TransportManager, WaterManager, ElectricityManager and
CitizenManager blocks, as well as terrain, water, networks and buildings.
Its zone blocks and transport lines are empty, and its only district is
district 0. Their emptiness is not a format prohibition.[^reader]

**Encoding state, retaining it through New Game, and having a working service
are three separate claims.** A shared codec proves the first for its supported
records; it does not prove the other two for a new gameplay layer.

## What New Game changes

The following are observations of the installed game's load methods, not an
in-game experiment with newly authored records:[^load]

| State | `NewGameFromMap` behavior |
| --- | --- |
| Network nodes and segments | Valid prefab records remain and acquire `Original`; missing-prefab records are released. |
| Buildings | Valid prefab records remain and acquire `Original`; missing-prefab records are released. `BuildingLoaded` runs during deserialization. |
| Zone blocks | The inspected `ZoneManager.UpdateData` recalculates demand and resets guides; it does not clear the zone-block buffer. |
| Districts and custom names | District data is deserialized; its update method resets guides, not the district grid. InstanceManager retains its name dictionary and clears selection. |
| Transit lines | Lines with missing prefabs, `Invalid`, or invalid owner buildings are released. There is no unconditional map-to-city line wipe. |
| Water/electricity grids | Their managers refresh grids when requested; the inspected update methods do not clear them simply because the load mode is New Game. |
| Purchased areas | Reset to the map's one starting tile. A map is not a way to preserve an existing city's purchased tiles. |
| Finances and progression | Cash returns to start money; taxes, budgets, expenses, income and loans are reset. Milestones are reset rather than continued as a loaded city. |

`SimulationManager.LateUpdateData` also performs **16,384 initialization
iterations**, calling every manager's `SimulationStep(1000)`, for a map-to-city
start. These are special initialization calls, not 16,384 ordinary gameplay
frames. Serialized initial water must survive the game's initialization and
subsequent simulation; a prefilled reservoir is not proof of equilibrium.
`LoadGame` is a distinct mode.[^load]

Consequently, zoning, districts, lines and service buildings are **not
intrinsically save-only**. An editor UI's inability to place them does not
establish a disk-format restriction. A save is the appropriate carrier when
the deliverable needs established city finances, purchased areas and a
continuing population rather than a new-city reset. Renaming a map, changing
its metadata type, or populating BuildingManager alone is not a save writer.

## Carriers and the current implementation boundary

“Map” below means the native representation exists and the inspected load path
does not universally discard it. Except for the existing PR #45 networks, this
is **not** a claim that a newly written layer has passed native load/reload.

| Layer | Native carrier in a map or save | What this repository can already do; what is missing |
| --- | --- | --- |
| Dam/hydropower | NetManager dam wall plus BuildingManager powerhouse/node buildings and WaterSimulation sources/state | Network/building encode/decode exists. Correct dam ownership, geometry, source lifecycle and hydraulic qualification do not. |
| Water/sewage sites | BuildingManager facilities, pipe networks in NetManager, WaterManager and WaterSimulation | Facilities' raw columns are understood by the building codec. WaterManager is only tag-bounded by the save reader; no general utility-network/grid writer exists. |
| Real zoning | ZoneManager road-relative blocks and segment zone-block references in NetManager | Zone blocks/cells decode. There is no ZoneManager encoder or local-road/zoning importer. Polygons cannot simply be appended as zones. |
| Named neighborhoods | DistrictManager district records/policy masks/grid plus InstanceManager custom names | Both managers decode. Their encoders and rasterization are missing. A district's random seed is not its custom display name. |
| Full rail | NetManager tracks/junctions and BuildingManager supports/outside connections; terminals add service-building state | PR #45 already writes real **main-line** rail, not just one arbitrary outside link. Yards, sidings, spurs, crossings and terminal hookups remain an extension. |
| ART transit | TransportManager line records, NetManager stop/line links and usable roads; depot/vehicles for operation | Lines and stop chains decode. No line encoder, GTFS-to-road matching, depot setup or local-street importer. A GTFS shape is not a usable bus path. |
| Power | Generation buildings, NetManager power lines and ElectricityManager distribution state | Shared net/building codec is reusable. ElectricityManager is tag-bounded, not semantically decoded/encoded. Real voltage classes have no direct vanilla equivalent. |
| Floodplains | No NFHL polygon meaning in these vanilla managers | Keep reference polygons in an external overlay/sidecar. Water grids can encode a flood state, not its FEMA probability. A timed flood scenario needs separate scenario/disaster authoring and any required DLC, not merely polygons or a save extension. |
| Real starting city | Interdependent networks, zones, buildings, residents/households, services, economy, unlocks and areas | Selected managers decode; only the net/building sections have the shared general codec. No complete offline save authoring path exists. Prefer save semantics for continuity; physical seeding into a map is structurally possible but receives the resets above. |

The standard district grid is **512 × 512 at 19.2 m**, with four district IDs
and alpha weights per cell. It covers about 9.83 km across, not the full
17.28 km terrain. There are 128 district slots including district 0. Do not
claim full-81-tile neighborhood coverage from the vanilla buffer. Zoning uses
8 m cells in road-oriented blocks, with valid/shared/occupied masks; use only
valid, non-shared cells. Legal mixed-use zoning requires an explicit
approximation into vanilla zone types.[^reader][^load]

## A dam is not just a building

The loaded prefab catalogue names the network `Dam` (`DamAI`) and buildings
`Dam Power House` (`DamPowerHouseAI`) and `Dam Node Building`. `DamAI` chooses
an owner powerhouse while placing the curved network. Building/net ownership
and node chains must agree; adding a named building at an NID point does not
create the wall.[^services]

The powerhouse samples tailwater, derives a target from its position and
connected segment heights with an **8 m offset**, and bases production on
transferred water and the remaining head. It creates/updates a **type-2**
buffered water source with separate upstream/downstream positions. Its stock
input/output rate values are 10,000,000; those are game parameters, not real
river discharge. Source creation searches for nearby water at both ends.
Source ownership, direction, tailwater and initial wetness matter even when
the record is structurally valid.[^services]

Craggy's NID hydraulic height is only 13 ft (about 4 m; see
[Asheville sources](ASHEVILLE_GAMEPLAY_DATA.md#dam-candidates-in-the-default-square)).
**Inference:** the stock tall-dam geometry and target offset cannot be assumed
to reproduce this low-head structure or generate useful electricity at true
scale. NID height is not measured operating head or an absolute pool elevation.
A taller fictional wall would be a gameplay approximation, not a faithful
import. Zero/nonzero production and upstream/downstream stability remain native
questions, not conclusions of this source inspection.

`WaterFacilityAI` likewise creates type-2 sources and moves water/pollution
through buffers; a source pin alone is not a powered, piped utility. Available
stock names include `Water Intake`, `Water Outlet`, `Water Treatment Plant`
and `Water Tower`. MSD treats effluent: a raw `Water Outlet` at its site is not
an accurate representation of its treatment process.[^services]

PL-912 owns water qualification. Reuse its source footprints, stage/storage
and transient-withdrawal findings rather than selecting rates or adding
reservoir regulators here. In particular, a natural target source inside an
impoundment can replenish/drain it independently of the dam; an apparently
stable lake then does not demonstrate dam-controlled water. No existing map's
qualification transfers to changed dams, utility withdrawals or discharges.
The current baseline remains partial, as documented in
[NATIVE_FINDINGS.md](NATIVE_FINDINGS.md) and
[CURRENT_FIXTURE_CONTRACT.md](CURRENT_FIXTURE_CONTRACT.md).

## Extending the codec safely

`netcodec.py` is shared by the map writer and save reader. It can append network
nodes/segments and clone an existing building record. `BuildingSection.clone`
is not a general service-building factory: outside-connection records do not
become valid pumps or powerhouses just by changing a prefab name. Preserve the
AI-specific references, flags, buffers and ownership links.[^codec]

Missing lanes may be allocated by `AfterDeserialize` through `UpdateLanes`;
outside-connection buildings must still exist. See
[REAL_ROADS.md](REAL_ROADS.md). Managers are not isolated length-prefixed blobs:
serializer string/type/object tables and queued objects cross their boundaries.
An encoder extension must preserve those relationships and package checksums;
successfully decoding one block is not enough.[^serialization][^codec]

For each new layer, distinguish an offline structural round trip from a native
New Game/load-save-reload result and from operating gameplay. Dam/utility work
also needs settled levels, wet downstream reaches, flood and pollution checks,
and observed service production. These checks have **not** been run by PL-1019.

## Source audit and reproduction

No game DLLs or decompiled code are distributed with this document. The native
observations above used ILSpy **9.1.0.7988** against the installed Linux
`Assembly-CSharp.dll`, SHA-256:
`c7f0e723dfe867d10aef73f14268bcf9f5ea4bab1c5ce4987897ed27f46511a1`.
Inspect the named types with `ilspycmd -t TYPE "$CS1_MANAGED/Assembly-CSharp.dll"`;
this does not launch the game. Claims apply to this build, not every CS1 version.

The existing reader checks can be run without the game or private city saves:

```sh
cd tools/save-reader
uv run --group dev pytest tests
```

The PL-1019 run passed **22 tests**; the **3 private-save tests were skipped**.
The committed game-check fixture is existing evidence, not a new game session.

[^serialization]: Fresh native inspection: `SaveMapPanel.SaveMap`, `LoadingManager.SaveSimulationData`, `SimulationManager.Data.Serialize`. Repository transcription: [save.py](../save-reader/cs1save/save.py), [package.py](../save-reader/cs1save/package.py), and [map_metadata.py](map_metadata.py).
[^load]: Fresh native inspection: `SimulationManager.LateUpdateData`; `NetManager`, `BuildingManager`, `ZoneManager`, `DistrictManager`, `TransportManager`, `InstanceManager`, `WaterManager`, `ElectricityManager`, `GameAreaManager`, `EconomyManager` and `UnlockManager` load/update methods; `DistrictManager.GetDistrictName`.
[^reader]: [Save-reader format and limits](../save-reader/README.md); [manager decoders](../save-reader/cs1save/managers.py), [district/transit decoders](../save-reader/cs1save/districts.py), [template tests](../save-reader/tests/test_template.py). The native template was also read directly with `cs1save.save.read_save` on 2026-11-17.
[^services]: Fresh native inspection: `DamAI.CheckBuildPosition`, `DamPowerHouseAI.SimulationStep`, `HandleWaterSource`, `GetElectricityRate`, `GetRefundAmount`; `WaterFacilityAI.HandleWaterSource`. Names/AI bindings: [existing loaded-prefab catalogue](../save-reader/cs1save/data/prefabs-1.21.1-f9.json).
[^codec]: [Shared codec](netcodec.py), [network writer](network_writer.py), [save-reader adapter](../save-reader/cs1save/codec.py), [shared-codec tests](../save-reader/tests/test_shared_codec.py), [rail filtering and pruning](osm_highways.py).
