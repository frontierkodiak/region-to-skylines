# Offline native adapter v5

Source pin: `3afadcceb5d3378e96aa3cb3cb844d4de281a5f6`.
Only this new prefix changes. No live transport is supplied or enabled.

| Role | Implementation / immutable binding |
|---|---|
| Accepted measurement/build provenance | v4 `spec.py`: all 87 source facts retained unchanged |
| Accepted helper/consumer role | v4 `spec.py`: distinct exact 35-file closure; no projection of the 87 into 35 |
| New executable closure | `adapter_spec.py`: seven exact Python files, each retained by hash |
| Fresh staged C# | `fresh_build.py` replays `spec.staged_sources()` / immutable `build_v2` transform; all 17 originals and 17 full staged files |
| Compiler/runtime | Existing dotnet/csc; complete declared dotnet executable, host, shared runtime and Roslyn/bincore files retained privately |
| Fresh DLL | Actual isolated compilation, full args/tool versions/reference hashes/log, SHA and parsed MVID |
| Collector entry | `adapter.preflight()` validates before stub queue/launcher seam; captures `pipeline.collector_binding()` before facts |
| Runtime policy | `pipeline.runtime_policy()` and `pipeline.validate_policy()` on the composed validated spec |
| Byte capture | `adapter.retain_inventory()` retains every file and assembly on each launch/pre/post capture |
| Bundle | Actual `pipeline.bundle()` over the same composed spec; outer gate validates exact spec bytes and all binding fields, then calls unchanged `consumer.opening()` |
| Lifecycle | External `adapter.supervise()` owns five harmless Python processes; driver writes observations, exits; unchanged `lifecycle.finalize()` joins/reads absence; only owner adds cleanup |

The composed API exposes v4's validated input/helper view to its fact consumer;
its bindings additionally include the outer canonical spec, adapter closure,
fresh DLL/build, API, inputs and requests. `pipeline.bundle()` revalidates the
embedded v4 baseline; the outer gate also validates the full new descriptor.
Neither schema nor module globals are patched. Old retained build facts are
still separate from the actual fresh build. The fresh DLL replaces the harness
file/assembly in a complete **constructed** inventory, never an installed file.
Every required inventory map is compared against the independent frozen full set,
so matching omissions in policy and observations cannot pass.

`RecordingTransport` supplies finite generated facts through independent
BuildIndex/create/result-release/inventory seams. No old measured controls or
labels are scored. A harmless driver writes these observations; the external
finalizer's actual process evidence is attached later. Native protocol fidelity,
real control admission and export qualification remain Unknown. See `PLAN.md`.
