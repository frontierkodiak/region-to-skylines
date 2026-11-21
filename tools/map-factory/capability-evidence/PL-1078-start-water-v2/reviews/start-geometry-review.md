## Independent Sol review — accepted

Exact source: `56bd3ca582db7de026f9669b5fa42b6640fefef8` in `PL-1078-start-geometry`, compared with `1f2d4f4d7bbff5daf16e9bd8a645ec4ed3864589`. Reviewed all three changed files and the relevant unchanged graph writer, witness execution and identity-binding paths.

**No material logic, fairness or binding finding in this bounded delta. Accepted as a provisional v2 model for frozen native evaluation, not as demonstrated native improvement.**

- Endpoint direction signs match the exported `start_dir`/`end_dir` convention and the native player's outward-heading convention. The cubic uses the endpoint directions toward each segment's interior; the new tests exercise tangent-sensitive heading and a bowed corridor missed by the chord.
- Corridor clearance screens and order ranking are deterministic CPU decisions. The declared step order, bound hook positions and ordering metadata enter the witness digest; changed source and the v2 model ID enter the model digest. The native operation still executes that exact order, with guarded placement and no adaptive retry or construction waiver.
- Intended paired stubs are excluded only from the unrelated-corridor screen. Their mutual collision/junction acceptance remains native work. Rejection by finite search remains unknown; the change does not broaden the existing scoped missing-outside-anchor negative into geographic impossibility.
- There is no physical exporter, player, judge, ledger-promotion or oracle-DLL change. Water service remains independently unknown/unqualified by these start geometry changes.

The one-third-chord curve, two-dimensional clearance, nominal chord-based 4m sampling and ignored native widths/pillars remain approximations. They can abstain conservatively or produce a false positive; the documentation makes native falsification explicit. This does not block a fitted hypothesis from evaluation. Preserve v1 false positives and freeze v2 code, parameters and prediction/witness hashes before any held-out native outcome; keep fitting and held-out accuracy separate.

Verification: independently ran all **11 `test_start_capabilities.py` tests**, which passed, and `git diff --check`. Did not rerun the other focused/full-map tests, regenerate maps, inspect held-out results or operate any native game/controller. The parent-supplied v1 fitting outcomes and v2 fitting selections were context, not independently re-audited native evidence.
