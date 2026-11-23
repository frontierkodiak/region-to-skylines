# Future freeze preflight v4

PL-1315 fixes the offline contract boundary. It does not reopen PL-1313.
The source is exactly `4eca4d291cc133513e8bac6484185d3a3b6e80ae`.
The internal PR targets `PL-1142-native-v2`, not main or the application.

## Contract

`spec.build()` produces `future-freeze.json` from actual repository and private
retained bytes. `spec.validate()` returns immutable canonical spec bytes.
The collector binding, runtime policy constructor, bundle builder and consumer
use that same value. Bundle assembly cannot select another source subset.
Preflight and the post-collection consumer both call `consumer.validate_frozen()`.
Those shared checks need input bytes but no runtime facts or control labels.

| Role | Exact versioned keyset | Binding |
| --- | --- | --- |
| Measurement/build provenance | All 82 original source files plus the five v4 measurement modules | `measurement_provenance_sha256` |
| Readiness helpers | The schema-v3 30-file closure plus those five modules | `source_sha256` in the versioned consumer |
| Inputs | Fixed catalog, inventory, exclusions, selection, features, literal requests, predictions, protocol, control packages/graphs, selected holdout package | `inputs` with separate named byte hashes |
| Build | Retained DLL, compiler, game executable, all eight references, all staged C# files, receipt | `build_artifacts` and `build_receipt` |

The freeze's `sources` object is the source-role manifest. Both source maps
retain actual source hashes and their canonical manifest hashes. No provenance
file is removed to satisfy the readiness role. The `spec_sha256` binds all roles.
An empty, declared Python initializer is verified as actual zero-byte source;
missing sources still fail. Runtime artifacts retain the accepted nonempty rule.

The original freeze puts the 82-file map in the 30-file role. `legacy.json`
records its rejection before build or private-store lookup. The regression also
shows that the original self-map preflight instead reaches the missing local
`.build` locator. No historical freeze, runtime binding or outcome is repaired.

## Stages and ownership

`ReadyToLaunchControls` means offline byte and contract compatibility. The
reported `launch_authorized` is false. This repository change grants no opening.
`AfterDriverExit` is a separate external-supervisor stage. It requires the
captured PID/start identity and joined exit of every owned role, including driver.
The supervisor cannot attest its own absence. The fixture uses five finite Python
children, with actual `/proc` birth and post-exit reads. It touches no game,
Steam, foreign process or shared service.

The constructed collector uses literal plans to generate synthetic effective
arguments and result envelopes. It reuses retained input graphs and inventory
bytes, not historical path results. The consumer validates those constructed
facts against the real future spec. Both admission and export qualification
remain Unknown. Real records are unsupported by this offline path and fail
closed. There is no certificate or real-collection bypass.

`consumer.py` versions the pinned schema-v3 and readiness-v3 fact checks under
the new exact closure. It does not monkeypatch or modify the accepted modules.
The extra runtime MVID check reads actual retained assembly bytes.

## Verification modes

Retained-byte verification checks hashes, actual DLL/assembly MVIDs, manifests,
and the pure C# copy/transform recipe. It never reads the old absolute build-stage
locator. The retained PL-1313 DLL is a candidate byte artifact, not a fresh build.

Local fresh-build verification is **unverified** without an explicit context.
Even when a DLL exists there, this command reports **unsupported**, not a pass.
No compiler, native build, package build or deployment runs in this task.
No claim covers compiler trust, memory attestation or strict-no-mods.

See [CHECKS.md](CHECKS.md) for commands and receipts, and [PLAN.md](PLAN.md) for
the prospective study that still requires separate authorization.
