# Native air-template authoring · offline-first

**Native authoring pilot completed; no new writer template adopted or committed.** Based on
harness `8ccb2f47207f2074836f6c655c2801fcc66e9af5`, without concurrent queue
changes. This authors an abstract map-edge flight path, not an airport or an
asserted AVL approach. A real airport outside the footprint need not be placed
inside it to add a native map air connection.

## Exact installed-source evidence

Installed CS1 1.21.1-f9 source: `acs.cs` beside `cm.cs` under
`/home/caleb/scratch/2026-11-09-pl856-cs1-harness/decomp/`.
Assembly-CSharp SHA-256:
`c7f0e723dfe867d10aef73f14268bcf9f5ea4bab1c5ce4987897ed27f46511a1`.

| Source | Contract |
| --- | --- |
| `LoadMapPanel.LoadRoutine`, `acs.cs:235225–235259` | `LoadLevel(asset,"MapEditor","InMapEditor",meta)` with `m_updateMode=LoadMap`. |
| `SimulationManager.UpdateMode`, `acs.cs:388488` | NewMap=0, LoadMap=1, NewGameFromMap=2. |
| `ItemClass.Availability`, `acs.cs:261414` | Game=1, MapEditor=2. Ops require exactly MapEditor and this helper's source-bound LoadMap session. |
| `FlightPathAI.GetInfo`, `acs.cs:325096–325110` | Native outside-count limit and selection of `m_connectedInfo`. |
| `FlightPathAI.GetNodeBuilding`, `acs.cs:325137` | Outside nodes request actual `m_outsideConnection`. |
| `FlightPathAI.UpdateNode`, `acs.cs:325183–325215` | Native lane counts set real building Incoming/Outgoing flags. |
| `NetTool.MakeControlPoint`, `acs.cs:366419`, snapping `366542–366573` | Native raycast, edge snap using prefab half-width, terrain height and `m_outside`. |
| `NetTool.CreateNode`, `acs.cs:365030` | Native allocation/connection-prefab/lane/building creation. |
| `SaveMapPanel.OnSave`, `acs.cs:237271`, coroutine `237317` | Normal UI-driven native serialization to a new local map. |
| Save packaging `acs.cs:237483–237485` | Plane metadata comes from `CalculateOutsideConnectionCount(PublicTransport,PublicTransportPlane,...)`, never a fake air flag. |

Exact full constructor overload:

```csharp
ToolBase.ToolErrors NetTool.CreateNode(
    NetInfo info, NetTool.ControlPoint startPoint,
    NetTool.ControlPoint middlePoint, NetTool.ControlPoint endPoint,
    FastList<NetTool.NodePosition> nodeBuffer, int maxSegments,
    bool test, bool testEnds, bool visualize, bool autoFix,
    bool needMoney, bool invert, bool switchDir, ushort relocateBuildingID,
    out ushort firstNode, out ushort lastNode, out ushort segment,
    out int cost, out int productionRate);
```

Calls use maxSegments=1000, testEnds=true, visualize=false, autoFix=true,
needMoney=false (editor), invert=false, switchDir=false, relocateBuildingID=0.
Only test changes from true to false on identical explicit apply. autoFix lets
native GetInfo select connected variants even with fixed-height prefabs. No
node/segment/lane/outside-building IDs or building flags are assigned by hand.

## Explicit disposable-session flow

The caller owns a dedicated idle harness session, installation of the source
map before launch, and teardown. The helper never starts a session, installs
a DLL, changes GPU placement or touches another session.

1. `template_open {path}` resolves the exact installed MapMetaData asset,
   records its file hash and loads its existing topology into MapEditor.
2. `template_status` returns actual Plane FlightPathAI candidates, original
   fingerprints and graph inventory. Existing air paths/counts are rejected.
   No prefab name is guessed or automatically selected.
3. Pause using existing `run`. `template_air {prefab,endpoints,apply:false}`
   calls native MakeControlPoint and tests native CreateNode on the simulation
   thread. Endpoints must snap to new outside control points, never existing
   graph nodes/segments. Apply requires the identical checked plan.
4. Any construction error gives `failed_discard_editor`: close without saving
   and reload. No binary rollback or retry over a partial construction.
5. Wait for real native outside buildings/counts. Export verifies unchanged
   original topology/counts, a connected plane-only chain and exactly two new
   outside endpoints with building IDs.
6. `template_export {name,map_name}` accepts a fresh `air-template-...` basename,
   refuses overwrite/concurrent save, opens the native SaveMapPanel, leaves
   Publish unchecked and invokes public OnSave. Poll until saving is finished;
   hash the exact file and recheck native inventory after saving.

Later authorized usage, not commands executed for this offline task:

```sh
uv run python -m cs1_harness.template_author INSTALLED_SOURCE.crp RECEIPTS --port 8779
```

Inspect `before.json`, choose an actual native prefab, and create a plan:

```json
{"prefab":"EXACT_NAME_FROM_INSPECTION","endpoints":[[-8639,-2000],[8639,-2000]]}
```

These are generic explicit edge coordinates, not region/airport/probe hacks.
Continue the same exact source-bound editor:

```sh
uv run python -m cs1_harness.template_author INSTALLED_SOURCE.crp RECEIPTS \
  --port 8779 --continue-editor --plan plan.json
# Only after review, same dedicated session and checked plan:
uv run python -m cs1_harness.template_author INSTALLED_SOURCE.crp RECEIPTS \
  --port 8779 --continue-editor --plan plan.json --apply \
  --export-name air-template-UNIQUE_TOKEN --map-name "Experimental air template"
```

## Receipt and adoption boundary

`air-template.json` binds source/export SHA-256, plan, native before/after
inventories and new IDs. Nodes contain prefab/AI/service/subservice, positions,
links, outside status and real building IDs/prefabs/flags. Segments contain
native node IDs, prefab/AI, lane vehicle kinds/directions, real lane IDs and
directions. Fingerprints cover exact floats, flags, topology, prefab names,
attached building IDs and lane-head IDs; road/rail/ship counts must not change.

The receipt says writer_adopted=false and native_new_game_verified=false. No
account identity field is emitted and no raw template/live receipt is committed.
A later native map file may contain ordinary native author/mod metadata: keep
it private until existing writer cleanup and explicit acceptance are reviewed.

**Do not feed the export into today's writer descriptor builder.** Examined
writer `eaabf27`, not modified here:

- `template.py:200–236`: both-ends-outside currently means rail. Decode prefab
  references or join this hash-bound native segment/prefab/AI/lane inventory,
  validating complete ID sets and rejecting mixed/unsupported kinds. Never
  infer air from endpoints or allocate IDs blindly.
- `region.py:533–605`: rail-versus-road alignment feeds ground grading and
  earthworks. Add a separate preserved air network using native prefab height
  semantics; no road/rail bridge clearance or terrain corridor cuts for air.
- `resources.py:175`: ground network masks currently consume every segment;
  exclude air so flight paths do not erase underlying trees/resources.
- `soak.py:88–94`: non-rail routes become car tests. Exclude air from highway
  probes; require separate plane verification if flight pathfinding is claimed.

Use a new versioned, fingerprint-bound descriptor. Leave the existing three-
route template, fixtures and expected checksums intact; adoption is separate.

## Offline implementation checkpoint (before native pilot)

59 tests (11 new authoring fixtures), full Ruff lint/format checks and installed-
assembly compile pass. Direct Roslyn output only:
`/home/caleb/scratch/2026-11-10-pl857/air-template-build/Cs1Harness.dll`, SHA-256
`7a595de0a9ec026e6a0218a9c4701f81640458df7f026a64c23ed303550981aa`.
CS1_HARNESS_CACHE was set as required for SDK lookup; normal build()/install
was never called. Active cached DLL stayed exactly
`58ae33b2ba9877ba1d38f385b932de94a07f4d6fbda2ed7f52723d51bb859906`.

The smallest native pilot is actual prefab/connected-variant inspection, one
explicit dry run/apply, confirmation of deferred outside-building updates while
paused, and native SaveMapPanel/file/count validation. Raycast/placement,
paused updates and save controls remain unverified. If they differ, discard
the editor instead of bypassing checks. A later disposable New Game must prove
the real icon/connection before adoption. No Steam, game, native authoring,
template save, service change or platform write ran for this implementation.

## Native authoring pilot · 2026-11-11

PR8's combined implementation (including later alias preflight) compiled and
completed `air-template-pilot-0310` in an owned foreground blade session.
The actual prefab relationship selected `Airplane Path`; explicit dry run then
apply created175 plane-only nodes,174 segments and two real outside buildings.
Native counts are2incoming/2outgoing; original road/rail/ship inventories and
fingerprints remain unchanged. Native SaveMapPanel exported a new unpublished
package with SHA `33871c8a168f0dc8e6db3de6bb19bcfa10e487b4def6495461155ad9943d7938`.
The original template is unchanged, cleanup is empty and the game-directory
export was removed after a private exact copy. The export is not committed:
native author metadata can identify the account.

This proves native template authoring is available. It does not adopt a new
descriptor, retrofit air into current five-region packages, prove New Game's
air icon or claim plane pathfinding/airport service. The adoption blockers
above still apply. A map-edge path is not an asserted AVL airport approach.

## Offline alias preflight (2026-11-11)

`template_open` requires `{path, source_sha256}`. Before loading, it checks the
requested file bytes, then selects exactly one installed MapMetaData asset:
exact full path first; only when absent, same basename AND exact SHA-256 bytes.
Zero or ambiguous matching assets fail. Different basenames never qualify.
Native open/status receipts contain actual installed `source_path`,
`requested_source_path`, `source_binding` (`exact_path` / `basename_sha256`),
`source_matches: 1`, and `source_sha256`. Python checks binding at open, initial
inventory, and export; its final receipt retains the installed path. No similar
terrain/content fallback exists. Source files must remain immutable during
loading; no atomic filesystem lease or native alias behavior is demonstrated.

Exporter names are confirmed in installed `acs.cs:236939`–`236941`:
`MapName`, `SaveName`, `Publish`; public `OnSave()` at `237271` reads those fields
and calls the native save routine. This does not prove live panel hierarchy or
export. Offline protocol fixtures cover alias receipt acceptance, wrong hash
and basename, ambiguous/malformed selection rejection. No native run or compile
for this follow-up. Original topology fingerprints and deferred native outside
updates while paused remain strict pilot uncertainties; no guards relaxed.
