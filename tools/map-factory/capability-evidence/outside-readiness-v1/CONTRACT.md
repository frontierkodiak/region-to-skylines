# Consumed-field bridge contract v1

Scope: unchanged `lane:any_lane:forbidden`, exact source
`d745b14e3e207ee67f91033811958a2934fb38a4`. `bindings.json` binds the actual
model, topology, bridge, reader, catalog, public RPC producers, staged source
recipe, freeze, audit and retained bytes. It includes the entire old study,
not just eight guessed references. `check.py verify` additionally rejects any
tracked change outside this new prefix. This is source/file identity, not
attestation of the code executing in game memory.

## Actual reads and provenance

Names below are relative to `tools/map-factory/capability-evidence/` unless noted.
The projection in `bridge_contract.py` is deliberately conservative (all segments,
all lane entries and all xyz values), rather than conditional on a favorable
request or observed label. It requires normalized forward/backward bits. The
accepted `Prepared` also supports a raw `direction` fallback; callers must
resolve that explicitly using the pinned `topology.direction_bits` first.

| Layer / reader | Actual fields / constants | Source |
| --- | --- | --- |
| `model.Prepared` | package segment keys; segment `start,end,lanes`; lane `index,forward,backward` or `direction` fallback | native networks, or CRP NetManager plus fixed prefab lane template |
| `topology.mode_lanes` | lane `vehicle`, `lane_type` (fallback `type`), `category`; per-mode `VEHICLE`, `CATEGORY_BY_MODE`, `LANE_TYPES_BY_MODE` | same templates; public query masks |
| `model._lookup`, `Prepared.lane_at` | request `from,to` segment and lane; segment inventory and lane index | frozen literal request, no geographic query |
| `topology.endpoint_node`, `other_node` | request endpoint offset (only 0/255 for predictor), segment `start,end` | literal request, NetManager connectivity |
| `model._search` | segment `id,start,end`; incident segments; lane `index`; source/target state; fixed pairing and U-turn policy | normalization plus graph construction |
| `model.can_travel`, `effective_forward` | lane forward/backward, segment start/end and `Invert` membership | explicit lane direction; agreed segment flag bit |
| `model.continues(any_lane)` | source lane ordinal lookup; target mode lane indices (not ordinal equality) | normalized ordered templates |
| `model.chord` | **all three coordinates** of segment `a,b` via `math.dist` | CRP node positions versus native segment endpoints |
| search cap | constant `model.MAX_LENGTH=100000`; nonnegative summed chords | a model parameter, not established native cost units |
| `study.candidates` | above plus node `Outside`; x/z and dominant-axis side; distinct node/segment; sorted IDs and offsets | agreed node flag bit, export positions; determines eligibility/order |
| `study.build_package`, `bridge.bridge_package` | CRP format/version; node/segment record sets, node positions, node/segment integer flags, prefab indices and prefab names; catalog variants/direction/missing flags | `crp.read_any`, `netcodec`, `network_writer`, `survey.measure_maps`, `template` closure in bindings |
| `study.fixed_catalog`, `relevant_lane` | exact eleven-package catalog, ordered lane index/type/vehicle/category/direction, conflict sets | fixed accepted catalog; unresolved relevant facts abstain |
| `study.model_fields`, collector graph hash | IDs, start/end, xyz, Invert, **prefab**, Outside, normalized lanes across all modes | accepted exact bridge/stability identity, retained unchanged |

Prefab name is not read by the normalized predicate. It **is** read to derive
its lanes from export bytes and remains in the accepted exact identity.
Changing a name while holding normalized lanes fixed can preserve this pure
function; changing a prefab upstream need not preserve its lane template.
Outside roles affect request selection, not `_search` once a literal request is
fixed. Request capability/name metadata does not replace its actual endpoint
triples and protocol masks.

Height is read even though eligibility's side calculation uses x/z only.
A constructed two-segment test changes only height and crosses the chord cap,
changing `success` to `no_path`. Thus there is no general height invariance.
The model's old docstring calls its cap a necessary native condition; that is an
unvalidated hypothesis, **not** native cost/metres or a mathematical
impossibility guarantee. No proof here identifies internal search cost or limits.

## Separate oracles

1. **Accepted exact bridge identity**: original `study.model_fields` equality,
   with prefab/Outside/xyz intact. Strict subset stays **16/48**, road only.
   `bridge_contract.exact_raw_identity` compares supplied bytes without
   normalization. `compare.normalized_object_identity` compares supplied objects.
   Neither replaces the accepted subset scorer or its original identity fields.
2. **Model consumed-field equality**: equal conservative projections imply equal
   arguments to the same pinned deterministic predicate, *for the same literal
   request, mode, and constants*. This makes no claim about a different request,
   request selection, upstream catalog lookup, or native behavior. Missing fields
   return Unknown. No post-label invariance fitting is performed.
3. **Native qualification**: always Unknown here. Current bytes lack both fresh
   complete controls and an independently established native decision law. No
   oracle is an admission bypass for the 32 exact mismatches.

Roslyn's **17/18** opening mismatches and **3** query drifts remain in the old
audit; Pittsburgh budget-093's million-budget air drift remains separate. The
old 48-label agreement and native-field diagnostic do not establish prospective
invariance. The four road errors remain unexplained; HK's new budget response
never overwrites its old success label. No old scorer/outcome function is run.

## Public wire semantics

`tools/cs1-harness/mod/CityOps.cs:Stats` calls
`m_metaData.m_invertTraffic.ToString()`; retained bytes are `"False"`.
`protocol.meta_bool` accepts only exact `True`/`False` strings and JSON booleans
as an explicit alternate representation. It rejects numbers, null, case changes,
whitespace and other enum strings. RPC flags accept **only JSON booleans**.

The owned `Harness.cs` appends `ok=true` to successful operation dictionaries;
its exception envelope is exactly `ok=false,error,exception`. The retained
post-control schema correction admits exactly that success key plus the frozen
body. This new module uses that contract without altering the frozen scorer.
The original failure log and correction timing remain hash-bound fixtures.

`NetworkOps.cs:Start` passes literal positions, Randomizer 857, current build
index, per-mode lane/vehicle/category masks to public `PathManager.CreatePath`.
`build.json.staged_NetworkOps` is the actual public-call source for the retained
maxLength argument and effective-argument response. No decompiled code is used.
`Result` derives complete from flags 4/8, success from 4, releases complete
handles and returns positions only for success. This parser conservatively
supports flags 0/1/2/3/4/8, rejecting mixed/unknown bits rather than claiming
undocumented meanings. A complete failure labels only its exact request;
transport success, native completion/success/release, returned literal endpoints
and qualification are distinct outputs.
