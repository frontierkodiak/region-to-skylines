# Shipping-input qualification

PL-918 replaces the original canvas captures with the shared `inputs.js` path.
The live pin at the start of qualification is
`5f6ef13d82ae5bbe4265ef4c60c508751e3d14f7`. All captures and reference bytes are
built on blade. macOS reproduction remains PL-917.

## Map identity

Each unmodified `cli.mjs` build is followed by a separate `capture-inputs.mjs`
build. The capture refuses to archive a different package. Its receipt binds
the source revision, writer files, heightmap, geographic JSON, uncarved banks,
resource inputs, prepared grids and full map checksum.

| Region | PL-857 reference | Live-pin CLI |
| --- | --- | --- |
| Asheville | `b66c5c6a3e15` | `eb4d2d9d8314` |
| Innsbruck | `3ba5de0a2cd1` | `6a54f3f24246` |
| Rio de Janeiro | `997d4d07925e` | `3bf4326d2ee5` |
| Pittsburgh | `97f727a7c3eb` | `a78a460314da` |
| Charleston | `fcea76d840f6` | `d5fd2d9973c5` |

The maximum prepared-terrain changes are 3.77, 3.14, 40.89, 7.41 and 19.67 m,
respectively. These are maxima over changed cells, not typical errors or a
terrain-fidelity score. The uncarved Asheville fit and square are unchanged,
so its independently measured GNIS/DEM landmarks retain their original meaning.

## Capture and test a preset

Run the commands in the source worktree being qualified. Use a fresh output
directory. The example keeps files outside the checkout.

```sh
qualification_out="$HOME/experiments/PL-918-live-inputs"
node cli.mjs charleston --out "$qualification_out/live-pin/charleston" --json
node tools/map-factory/capture-inputs.mjs "$qualification_out" charleston
```

`captures/charleston` contains the inputs. Its `out` directory is a prepared
candidate for `soak.py --prepared`, including `generation.json` and the resource
plan. Stage each region separately and use the harness queue. Run the two coasts
first, then Asheville, Innsbruck and Pittsburgh.

The native protocol is the accepted PL-857 protocol, without new thresholds:

- A 60-game-minute instrumented soak, samples every five minutes and full water
  grids at 0, 15, 30, 45 and 60 minutes.
- Exact initial terrain, water and source-control checks with `audit_soak.py`.
- Car-in, car-out and train paths at the start and end.
- All retained surface-river cells, independently projected with pyproj, using
  `audit_coverage.py`. Exact wetness and water within 64 m remain separate.
- Independent terrain comparison, native New Game panel, untouched opening and
  actual Areas view. Rendered content needs a hash-bound visual review.
- A separate ordinary New Game with `--disableMods --noWorkshop`, no control
  socket, a loaded-map log check and reviewed selection/city screenshots.
- Empty owned-session cleanup after every game. Steam conflicts wait 30 minutes
  without answering a takeover prompt.

`strict_vanilla.py` repeats the accepted fixed-resolution UI procedure. Its
`--references` directory contains the four PL-857 known-screen PNGs. Unknown
screens fail closed and are retained for inspection.

## Freeze the captured inputs

Finish PL-902's resource-golden update before replacing fixtures. Preserve its
resource changes when rebasing. A resource-only change can carry the water and
terrain findings only if both prepared grids remain byte-identical.

`freeze_fixtures.py --captures CAPTURES` validates each flat PNG, geographic JSON
and bank file against its capture receipt. It also refuses any generated terrain
or water grid that differs from the live-pin build. The resulting manifest names
`inputs.js` and includes each capture's source and grid bindings.

The native record is authored separately from completed runs, never invented by
the fixture writer:

```sh
uv run python freeze_native_qualification.py RUN_ROOT OUTPUT/native-qualification.json
```

This reads the actual source maps and first native grids, repeats the native
source-control audit, checks 60 minutes and empty cleanup, and binds reviewed
strict-vanilla screenshots. Failed checks remain failed. It also records the
native template, connection layout, sea level, water controls and starting tile.

`npm run test:fixtures` requires that capture contract and reproduces all five
regions under Pyodide. Each region has a shipping MRDS-evidence golden and a
richer offline wells/mines reference golden. The latter preserves PL-902's
resource coverage; it is not labelled as the browser's current input data.
`--shipping-captures` adds the current CLI outputs without replacing that evidence.
Both variants must retain the exact native-tested terrain and water grids.
The separate native record guards the water controls and connections too.

Both verifiers reject changed `inputs.js` or `terrain.js` until the capture
contract is updated. This binds the capture modules, not live upstream tile
contents. The shipping variants also bind `mapgen.js` and `web.py`, so a change to
resource acquisition needs a fresh capture. `verify_regions.py` independently re-prepares the inputs
and checks the same grids and packages on blade. Neither verifier writes goldens.

The frozen source contract includes PL-918's copy-only Rio warning update in
`terrain.js`; the native capture receipts retain the original source hash.
No terrain or input function changed between those revisions.

Qualification results and unresolved checks belong in `NATIVE_FINDINGS.md`.
Minor-stream carving remains PL-912. This protocol does not test populated-city
growth, other squares, other operating systems or stability beyond 60 minutes.
