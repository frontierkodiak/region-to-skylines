## Independent Sol bounded verification — accepted

Exact source: `83fa0ec27324dd4c4db8c6342e9600f76c3ddc41` in `PL-1078-start-geometry`, compared with `56bd3ca582db7de026f9669b5fa42b6640fefef8`. Reviewed all five changed files for API consistency, timing, fairness and binding only.

**No material blocker in this fixture fix. Accepted for new bounded native stock-reference attempts, not for a capacity or hydrology qualification claim.**

- Water fetch and sewage disposal now use the same declared consumer position and public spatial API family. This changes consumer context, not native supply, buffers, pollution, funds or placement guards. Actual adequacy of this context remains a calibration question.
- The same fixed1000-per256-frame demand is explicitly applied during2minutes of settling and the subsequent60-minute scored horizon. Raw settling records are separate from scored totals; their delivery does not earn a pass. The phase uses the nominal scheduled `due` frame, avoiding late execution relabeling a settling request as scored load. Existing lateness, expected scored-count, full horizon, auxiliary and per-cycle quantity gates remain.
- The contract adds `consumer_api` and `settling_has_load` to model parameters and the hashed witness; native validation refuses the old contract. Python requires both labels, complete separately identified settling records, and scored-only load samples. The oracle is distinctly `native_surface_load_v2`; this must not overwrite or reinterpret the old incomplete diagnostic.
- No player, physical export, map verdict, capability promotion or held-out decision is changed. The documented uncalibrated load/auxiliary-power/finite-horizon limits remain necessary, including for a successful reference attempt.

Verification: all **13 capability/binding tests** passed locally (the session/queue mutation test is fully mocked), and `git diff --check` passed. The19 source hashes in `surface-spatial-build-v3.json` match this tree; its DLL SHA256 matches the on-disk DLL: `f916bdebb5bcef51a646b202b8db728d35f4e3fe811dedf530257d3cc79f1c2b`. Did not compile, rerun the full harness/model suites, operate any native/controller, inspect held-out outcomes, or independently audit the parent-reported incomplete reference telemetry/cleanup.

This source review does not establish that the API correction resolves alternating sewage acceptance, that1000units/256frames is supported by either stock reference, or that a product intake has sufficient clean flow/downstream service. Keep those claims unscored until the separately bounded reference calibration supports them.
