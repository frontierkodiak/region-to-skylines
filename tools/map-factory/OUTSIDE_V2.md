## Targeted follow-up integration (PL-1181)

The single `capabilities.json` ledger retains `outside-v1` unchanged on native
`4cef6fb620f403c603e597a46f3bb7d7e5feadb7`. `outside-targeted-v2` projects
`29b095475ba2f93c7e918fefc08c736493670304` separately. Repeats are not independent
votes, and neither study measures geographic-negative accuracy.

The adapter reads retained gzip observations, networks, CPU provenance and
collector/helper sources. It verifies all 143 referenced raw files, original
98 compressed files, and the original 619 request/result/observation/time/raw
reference fields. It does **not** claim every derived annotation is identical:
12 upstream rail-panel `counts_match` annotations changed true to null.

There are five runtime-bound observations, four ship control sets (16 complete
controls), and two road witnesses. Distinct-edge road requests give 51 Pittsburgh
and seven Hong Kong successes; same-edge successes are not witnesses. Rail
failures remain Unknown. The page separates the old nine-square projection
(11 witnesses / 25 unknown) from the targeted five-square follow-up.

### Runtime identity and limits

Each retained ship candidate binds an exact CRP, three physical inputs, the frozen
prediction, raw observation hash/timestamps, collector/helper and mod source,
build receipt, executable, launch/opening host and namespace PID/start, all
resolved loaded assembly files, plugin states, actual NewGameFromMap traffic
and launch flags, and cleanup. The collector selects the listed map using
`Path.samefile(installed)` before opening its exact native path; host and
Flatpak path strings differ and both are retained.

The inventory includes 23 resolved files, not just eight compile references.
`CoreOps.RuntimeIdentity` excludes dynamic `AssemblyBuilder` assemblies. File
identity is not in-memory code attestation. An enabled-mod count of zero is not
no-mods: CitiesBridge, the harness and built-ins are loaded. Three missing
DLC-panel assembly errors are preserved at each opening, not whole-game
acceptance. No service, strict no-mods, depth/width fit, geographic negatives,
sustained water, air-v2 controls or blind holdout is established. All nine
water screens warn. No game or writer is run by this integration.

### Review and reproduction

The four active `native_path_certificates` are the exact PR71 proposed objects
with only their review block removed. The original staged objects remain in
the source study, unchanged, so its deterministic projection can be reproduced.
The page excludes an exactly matching active object from the pending-review
count. No production approval switch was added. Qualification is restricted to
the same CRP, three physical inputs and full native observation context; no
pan-time or general ship-clearance promise follows.

Activation is a separately reviewable draft delta on PR71's exact head
`2f7892a1f0acd07347870793f0ca201b1b9ca74d`. Its acceptance and independent
review are recorded on PL-1119; preparing this branch is not public deployment.

From the repository root, using the exact source checkout as `NATIVE`:

```sh
## Rebuild the staged projection in a clean worktree at PR71; the importer
## deliberately refuses to overwrite a ledger with active certificates.
uv run --no-project python tools/map-factory/integrate_outside_v2.py "$NATIVE"
uv run --no-project python tools/map-factory/refresh_capability_ui.py
OUTSIDE_V2_NATIVE_ROOT="$NATIVE" uv run --no-project python -m unittest discover -s tools/map-factory -p test_outside_v2.py -v
node --test --test-concurrency=1 test/capabilities.test.mjs test/outside-v2.test.mjs
```

On blade, the actual retained export files are tested with the map-factory
environment and `OUTSIDE_V2_SELECTION` set to the exact selection file:

```sh
OUTSIDE_V2_SELECTION="$NATIVE/selection.json" OUTSIDE_V2_EXPORT_RESULTS=export-verification.json OUTSIDE_V2_BROWSER_INPUTS=actual-inputs.json uv run --project tools/map-factory python -m unittest discover -s tools/map-factory -p test_outside_v2_exports.py -v
```

The export test expects four exact ship promotions under replayed same-observation
contexts and zero pan/unbound/mutated-context promotions, with Python/JS parity.
Its output is verification evidence, not another ledger or fresh game run. Run
`test/outside-v2-browser.mjs PLAYWRIGHT_CORE DIST actual-inputs.json OUTPUT` in
blade's official matching Playwright image for Chromium/WebKit, receipt HTTP
hashes, separated studies and mobile layout. The usual capability browser test
retains its separately labelled constructed/live checks. Protected Vercel
contents remain unverified; no public merge, Shelf refresh or deploy is made.
