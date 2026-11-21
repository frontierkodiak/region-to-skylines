# Directed rail oracle · PL-1215

This study is separate from `outside-v1` and the parent's capability ledger.
Its base is accepted native source `29b095475ba2f93c7e918fefc08c736493670304`.
The original nine packages, geographic settings, three physical input groups,
historical failures, water warnings and certificates are not changed. Stock
controls are separate from, not replacements for, that geographic cohort.

## Native meaning and calibration

The query is `NetworkOps.path_start`, `mode=train`: two literal native
`[segment, lane index, offset]` positions, Train vehicle type, All categories,
Vehicle/TransportVehicle/CargoVehicle lanes, maximum length 100000 and seed
857. `path_result` retains native flags and all returned positions and releases
completed path units. This tests a sampled native lane path at opening, not a
spawned train, station/port service, sustained gameplay or geographic absence.

The accepted old rail sweep enumerated lane combinations on undirected
candidate components. It did not first calibrate lane direction and literal
endpoint semantics against a stock positive. Rio's 48 and Hong Kong's 16
selected failures therefore stayed Unknown, not native negatives. Those raw
bytes remain unchanged.

The first new selector compared direction *names* and selected no queries on
either stock control. The native names were `AvoidForward` and
`AvoidBackward`, not `Forward` and `Backward`. That failed selector is retained
as `rail-v1`, pinned source/evidence `9c96bf213fa6e84242d3a32e2cd76cad2ee7ef49`.
It is an inventory/selector failure, not two failed rail paths.

The next calibration recorded actual enum values: Forward=1, Backward=2,
AvoidForward=11, AvoidBackward=7. Both avoidance values contain **both** travel
bits. Reversing a stock lane is therefore not necessarily wrong-direction.
Its source/evidence is retained as `rail-v2`, pinned
`aac994054f6024043225297eb0af41bec6b0287b`. Its composite normalization masks
were too broad for plain one-way flags; they are not the final protocol.
Repeated stock openings are diagnostic revisions, never independent votes.

The final `rail-v3` protocol tests Forward and Backward bits directly and
cross-checks the normalized native booleans against the numeric values. It
selects a source travelling away from its Outside node and a destination
travelling towards its Outside node, swapping the desired direction for
segment Invert. It sorts distinct-edge requests first, then exact native
from/to positions, with a fixed 128-boundary-request cap. No undirected
component filter, place name, old access leg or selected player witness enters
this rule. All same-edge results remain distinguishable.

Every boundary request has a midpoint diagnostic. A reversed-position
diagnostic is not presumed invalid. A separate explicit invalid-vehicle query
uses the first selected boundary source and the lexicographically smallest
Car-but-not-Train segment/lane at offset 128. Its rejection is a protocol
diagnostic, never a geographic impossibility observation. Both stock controls
must complete in bound contexts and reject that invalid pair; at least one
must produce an exact literal-boundary path before any cohort query.

## Freeze and identity

`selection.json` is exclusively written and fsynced before launch. It fixes
the protocol, runtime source hashes, build receipt, all 104 stock-package
hashes and the unchanged original nine-case selection. The fixed stock rule
is the first two builtin corpus filenames with positive incoming/outgoing
train metadata: Asanu Beach and Hanami Bay. CO.crp is the system editor package
and is excluded. Actual native boundary segments/lanes, not metadata, establish
what can be queried. Failed controls are not replaced.

Each opening writes an exclusive `query-freeze.json` before any query. It binds
the full native network snapshot, endpoint/lane inventory, ordered requests,
candidate-model statement, protocol, package and runtime identity. Submitted
queries are dated; a verifier rejects a changed/reordered query prefix or
missing completed requests. Cohort freezes must follow the stock-control
receipts. A bounded candidate is not predicted path success; any finite miss
remains Unknown.

Launch and opening hash the actual executable and every resolved loaded
assembly file through the rendering process's namespace PID/start identity.
The same observations retain plugin flags (builtins, bridge and harness),
reported errors, launch arguments and explicit dynamic-assembly exclusions.
Compile references and the mod DLL must match the independently hashed files.
Unresolved assembly files, missing identity or changed PID/start fail closed.
Native NewGameFromMap and non-inverted traffic are read back. This is **FILE
identity**, not in-memory attestation or strict no-mods. New harness bytes get
new stock controls and opening contexts; no old certificate is inherited.

## Reproduction

See [Reproduce the rail study](REPRODUCE.md) for verification and new native runs.
