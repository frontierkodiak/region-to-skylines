# cs1-harness

Runs Cities: Skylines 1 on blade's GPU with no screen, so agents can drive it.
It has two layers. A **session** (`up` / `call` / `down`) holds the game
running headless and takes ops over a loopback socket from any tool. The **map
check** (`run`) is one tool on that session: it starts a New Game on a `.crp`
map, lets the simulation run, and reports water, population, log errors and
GPU load, with screenshots.

This is a shared tool: agents who use it improve it. See [AGENTS.md](AGENTS.md)
for the limits and the layer layout, and [JOURNAL.md](JOURNAL.md) for what
changed and why.

```sh
cd tools/cs1-harness
uv run cs1-harness build                 # compile the mod against the installed game
uv run cs1-harness setup                 # once per host: VirtualGL, Steam launch wrapper
uv run cs1-harness doctor                # GPU check on the harness display; no Steam

uv run cs1-harness up --map Asheville.crp   # game at the main menu, left running
uv run cs1-harness call ops                 # what this mod build can do
uv run cs1-harness call new_game '{"path": "/…/Maps/Asheville.crp"}'
uv run cs1-harness call screenshot '{"path": "/…/shot.png"}'
uv run cs1-harness down --out DIR           # quit, stop everything, keep the log

uv run cs1-harness run --map Asheville.crp --game-minutes 60 \
    --probes examples/pl848-asheville-probes.json --out ~/experiments/PL-856-cs1-harness/asheville-60
```

The game writes files (screenshots, grids, log) only inside the Steam sandbox,
so paths given to ops must be under
`~/.var/app/com.valvesoftware.Steam/` or `/peach/Games/SteamLibrary`. `run`
stages there and moves results to `--out`.

## How it runs

- **Display and GPU.** A private `Xvfb :57`. The game renders through
  VirtualGL's EGL back end on the GPU at the profile's PCI bus ID: the RTX 2080
  Ti at `05:00.0` on both blade and worm. `CS1_HARNESS_GPU_BUS` overrides it.
  The harness maps the bus to an EGL device by probing renderers, and it fails
  the launch if the game lands on another GPU. EGL needs only `/dev/nvidia*`. gamescope's headless
  backend was tried first and fails here: it needs the DRM nodes `/dev/dri/card*`,
  and the `caleb` user has no access to them.
- **Steam.** The harness starts its own Flatpak Steam on that display, on a
  private D-Bus session bus that carries `DISPLAY=:57`. Steam's Flatpak refuses to
  start when the desktop bus's activation environment lacks `DISPLAY`, and the
  desktop bus must not be pointed at the harness display. It launches the game
  with `-applaunch`, so Steam's own prompts guard the account. If the account is
  playing on another computer, Steam asks first, and the harness never answers:
  it stops with exit code 75 (`--retry-minutes 30` waits and tries again). Other
  prompts, such as the EULA, stop the run with exit code 77. The run refuses to
  start if any Steam is already running for the user.
- **One slot per host.** One run or `up` session at a time. A second one
  exits 75 while another holds the slot (its lock, an `up` session, a running
  game or Steam, the display). `run` and `up` take `--wait-minutes N` to wait
  instead: they poll every 2 s and start in the gap after the other user's
  command, so a long job can queue behind another agent's short ones. They
  never end or take over the other session.
- **Control.** `mod/` is a small mod with a loopback JSON socket
  (`127.0.0.1:8779`). The game constructs every local mod at startup, enabled or
  not, so the socket opens without ticking the mod in Content Manager. The mod
  stays disabled, so the game counts zero enabled mods. The game's
  `--disableMods` skips mod loading entirely, which would remove control too. So
  harness runs use `--noWorkshop`, with only the local mods present. The mod is
  installed for the run and removed after it.
- **Strict vanilla checks.** `up --game-arg=--disableMods` skips control-mod
  installation and returns when the game renders on the pinned GPU. It does
  **not** claim that the main menu is ready. `cs1_harness.x11.GameWindow`
  captures and drives only the exact game window in a caller-named private
  session; it never targets Steam prompts. Use ordinary New Game, record the
  listing and loaded city, and `down` promptly. Autosave suppression requires
  the control mod and therefore does not apply to this mode.
- **Never saves.** The mod stops the autosave timer once a city loads. Nothing
  writes a save or a map.

## Watching a run

Every session records and publishes what the game shows, unless you pass
`--no-record` / `--no-live`. Watching costs the game nothing measurable; the
numbers are in `JOURNAL.md`.

- **Timelapse.** `timelapse.mp4` lands in the run's output: one frame a second,
  played back at 30 fps (a 27-minute run is about 54 s), H.264 at 1280 px.
- **Live page.** <https://blade.tailc29f0.ts.net/research/cs1-live/> (tailnet
  only): the latest frame every 5 s and a status line with the run's label
  (`--label`), map, game-minute, water probes and population. The shelf links
  to it. When the run ends it says so and keeps the last frame.
- **Live view.** `cs1-harness watch` starts a view-only VNC server on the
  harness display, bound to localhost. From carbon, one line:

  ```sh
  ssh -f -L 5957:localhost:5957 blade '.local/bin/cs1-harness watch --hold 60' && sleep 3 && open vnc://localhost:5957
  ```

  Screen Sharing asks for the password `watch` prints; it is per host, in
  `~/.config/cs1-harness/vnc.pass.txt` on blade. `--hold 60` stops the server
  after an hour; `watch --stop` or `down` stops it sooner. Nothing listens on the
  LAN or the internet.

## Output

`--out DIR` gets `report.md`, `report.json`, `timeline.jsonl` (stats and probe
samples every `--sample-every` game-minutes), `game.log`, `gpu.csv`
(temperature and power every 5 s), `shots/` (one image per view every
`--screenshot-every` game-minutes, UI hidden), `grids/` (raw water depth and
terrain), and `water-start.png`, `water-end.png` and `water-change.png` (red
newly wet, yellow dried).

A game-minute is a minute of play at 1x speed: `60 / Time.fixedDeltaTime`
simulation frames. Speed 3 runs at 4x when the CPU keeps up. The in-game clock
moves much faster, about 2.5 game-clock minutes per frame.

Grids are little-endian `uint16`, 1081 × 1081, in the game's order: index
`iz * 1081 + ix`, world `x = ix * 16 - 8640`, `z = iz * 16 - 8640`, units of
1/64 m. Images put north (+z) at the top.

A probes file is JSON with `points` (`{"name", "x", "z"}` in world metres) and
optional `views` (`{"name", "x", "z", "size", "yaw", "pitch"}`). Without one the
run takes a single overview screenshot set and no point samples. A point may
set `"required": true|false` for the verdict, and the file may name a
`reference_water` grid (relative to the file) that flooding is judged against.

## Verdict

Every `run` ends with `verdict.json`: `pass`, `fail` or `error`, one row per
check with its value and threshold, the map's sha256 and the harness commit.
Gate on it rather than on the prose report. The thresholds live in code, in
`cs1_harness/verdict.py`, with the runs they were calibrated on.

| Check type | Checks that can fail it |
|:--|:--|
| `map-soak` (`run`) | `completed`, `probes_wet_end` (≥ 95 % of required probes wet, exactly or within 64 m), `no_flooding` (≤ 0.05 km² deeper than 0.5 m beyond 128 m of expected water), `paths`, `no_terracing`, `screenshots` (none blank), `frame_kinds` (only when Clef flags half the shots), `cleanup` |
| `asset-check` (`asset check`) | `loaded`, `triangles`, `has_lod`, `placed`, `survives_reload`, `screenshots`, `cleanup` |

`warn` rows (unexplained log errors, a few Clef flags) don't fail a run; `skip`
rows say what data was missing. A probe is required unless the probe file says
otherwise: inside the central 25 tiles, not on the map edge, and not tagged
`[stream]`. `cs1-harness verdict DIR…` re-judges finished runs (exit 1 if any
fails), for example after a threshold changes.

## Triage

A run that doesn't pass gets a `triage` block in `verdict.json`: a class, why
the rule matched, and its evidence. The classes are `map` (only map checks
failed), `harness`, `steam`, `game-crash`, `unknown-dialog`, `gpu-vram`,
`slot` (it waited out its `--wait-minutes`) and `unknown`. The evidence sits
beside the verdict: tails of `game.log`, `game-stdout.log` and Steam's
launch log, `last-frame.jpg` (the live page's last frame), `gpu.csv`, and
`traceback.txt` when the harness itself raised. The rules are in
`cs1_harness/triage.py`, ordered, first match wins. A game that ends while
Steam logs a playing-session conflict is `steam`, not a crash.

## Finding and comparing runs

Every `run` adds a line to the host's run registry,
`~/.local/share/cs1-harness/runs.jsonl` (`CS1_HARNESS_REGISTRY` overrides): its
directory, check type, verdict, map name and sha256, harness commit, the issue
it's for (`--issue`, else a `PL-NNN` in `--label` or `--out`) and headline
metrics.

```sh
uv run cs1-harness runs --issue PL-857 --verdict fail      # filters AND together
uv run cs1-harness runs --map-sha 4b3d3cd3 --json
uv run cs1-harness runs --index ~/experiments              # register older runs (judged, not modified)
uv run cs1-harness compare RUN_A RUN_B --out DIR           # compare.png + compare.json
```

`compare` takes run directories or registry ids. It plots water volume, the
share of required probes wet, and population against game-minutes, and lists
which verdict checks differ between the runs.

## The slot

One Steam account runs one game at a time. `cs1-harness queue` shows who
holds the host's slot (command, issue, label, minutes held and an ETA for
`run`) and who is waiting, including runs from older checkouts, found from
their command lines. Every wait, acquisition, give-up and release goes to
`~/.local/share/cs1-harness/slot.jsonl`; `queue --stats [--hours 24]` sums it:
acquisitions that had to wait, total and longest wait, and the share of the
window the slot was held. That's the evidence for or against a second Steam
account.

## Results come to the issue

`run --issue PL-NNN --notify` comments the verdict table, the water-change
map, the last screenshots and the timelapse on that issue when the run ends;
`--wake` also @mentions the issue's assignee if it's an agent, which starts its
next run. A blocked or failed run posts its error verdict the same way.

To queue a check and end your turn, submit it instead of running it:

```sh
uv run cs1-harness submit --issue PL-857 -- run --map X.crp --probes P.json --out ~/experiments/PL-857-…/x
```

`submit` starts the run as a `systemd --user` job that waits for the slot (4 h
by default), retries if Steam says the account is busy, and posts with
`--notify --wake`. It prints the unit, the log (`submit.log` in `--out`) and
how to stop it. Detached jobs post as Driver sessions (the host's `driver`
Multica profile); a run inside a Multica task posts as that task's agent.
`cs1-harness notify DIR --issue PL-NNN --dry-run` shows what would be posted.

## MCP

`cs1-harness mcp` serves the same operations over MCP (stdio): `queue`,
`contention`, `runs`, `verdict`, `compare`, `submit`, `notify`, `up`, `call`
and `down`. Each tool runs the CLI in a subprocess, so the CLI stays the one
contract: same arguments, slot rules and outputs. Register it with, for
example:

```sh
claude mcp add cs1-harness -- uv run --directory ~/dev/frontierkodiak/region-to-skylines/main/tools/cs1-harness cs1-harness mcp
```

Soaks go through `submit`: it returns at once, and the verdict arrives as a
comment on the issue.

Optional `paths` entries contain `name`, `from` and `to` native
`[segment,lane,offset]` positions, `rail` (boolean), and `expected_segments`.
The map check asks the native car/train pathfinder at the start and end,
retaining success flags, all positions, and missing expected segments. A
completed run is not a path-pass verdict. `networks` lists native IDs, lanes,
directions, segment/node flags, bounds and matching render-part/LOD metadata
to calibrate those probes. Runs with paths retain `networks-t000.json` and
the final network snapshot alongside path results; these are read-only
observations, not repairs. `path_start` and `path_result` also work
interactively. Completed harness-owned paths are released.

Exact water samples remain authoritative point measurements. Supplementary
`wet_within_64m`, `max_depth_within_64m` and `nearest_water_m` fields describe
water above 0.1 m in nearby native grid cells; they do not turn an exact dry
sample into a wet one. Map checks disable day/night for that session only,
without changing saved user settings, to keep screenshots interpretable.

## Hosts

`--host blade|worm` picks a profile; the default is this machine's hostname.
The profile runs on its own host: from blade, `ssh worm` and run the harness in
worm's checkout. Blade uses its Flatpak Steam, worm its native Steam. Worm's
Steam must be signed in, and the CS1 EULA accepted there, before it can launch
the game.

## Host layout (blade)

| What | Where |
|:--|:--|
| Game | `/peach/Games/SteamLibrary/steamapps/common/Cities_Skylines` (`CS1_GAME_DIR`) |
| Game data (Flatpak) | `~/.var/app/com.valvesoftware.Steam/.local/share/Colossal Order/Cities_Skylines` |
| VirtualGL 3.1.5 | `~/.var/app/com.valvesoftware.Steam/opt/virtualgl-3.1.5` |
| Launch wrapper, staging | `~/.var/app/com.valvesoftware.Steam/opt/cs1-harness` |
| .NET SDK, built mod | `~/.cache/cs1-harness` |

`setup` sets the game's Steam launch options to `<wrapper> %command%`. Without a
harness session on the current display the wrapper runs the game unchanged, so
playing on `:0` is unaffected. `setup --undo` removes the launch options,
wrapper, VirtualGL and mod. Session pieces (`cs1-harness-xvfb`,
`cs1-harness-dbus`, `cs1-harness-steam`) are transient `systemd --user` units
that exist only while a session is up; `cs1-harness-gpu` samples the GPU every 5 s into the session's `gpu.csv`.

### Opt-in New Game panel verdict (PL-857)

Add `new_game_panel` to the probe JSON to check the real menu before loading
the city. Every expectation is required. Use the intended map's actual values,
**not these illustrative zeros**. Amounts and directional counts are raw
`MapMetaData` fields; `buildableArea` is the integer percentage. `author` is
the package author, not the randomly generated suggested city name. An
intentional empty author hides the label.

```json
{
  "new_game_panel": {
    "map_name": "Asheville", "author": "", "buildableArea": 37,
    "resources": {
      "maxResourceAmount": 1000000.0,
      "oilAmount": 0, "oreAmount": 0, "forestAmount": 0,
      "fertileLandAmount": 0, "waterAmount": 0
    },
    "connections": {
      "incomingRoads": 0, "outgoingRoads": 0,
      "incomingTrainTracks": 0, "outgoingTrainTracks": 0,
      "incomingShipPath": 0, "outgoingShipPath": 0,
      "incomingPlanePath": 0, "outgoingPlanePath": 0
    }
  }
}
```

The mod opens `NewGamePanel`, finds the exact package path in its native
listing, selects it, waits for resource animations, and captures the rendered
modal. `new-game-panel.json` retains native metadata, resolved `imageRef` and
`steamPreviewRef` texture dimensions, actual labels and screenshot SHA-256.
`new-game-panel.png` is game-rendered, never constructed. Package metadata
alone cannot pass this check.

Initially `new_game_panel` **fails as unreviewed**. Inspect that PNG and record
what you actually see in `new-game-panel-review.json` in the run directory:

```json
{
  "sha256": "SHA256_OF_THE_CAPTURE_YOU_REVIEWED",
  "reviewer": "your name or agent/run identifier",
  "notes": "Specific observations of the selected map, preview, bars and icons",
  "observed": {
    "map_name": "Asheville", "author": "", "buildableArea": 37,
    "preview_matches_map": true, "resources_match": true,
    "connections_match": true, "selected_map_visible": true
  }
}
```

Only mark those assertions true after reviewing the panel against expectations:
preview is the intended map (not template), author/buildable percent are correct,
resource bars/no-resource marks match amounts, and directional transport icons
match intended connections. Resource bars use native nonlinear normalization,
not raw counts or percentages. Then rejudge with
`uv run cs1-harness verdict RUN_DIR`.

Missing/invalid expectations or evidence, unresolved refs, changed screenshots,
and absent/stale reviews fail closed. Without a request the row is `skip`.
Rejudging uses only the frozen run's `probes.json`, not mutable source probes.
This is mod-enabled instrumentation only: strict `--disableMods` vanilla checks
are unchanged. Manual vanilla panel captures are a separate workflow and cannot
silently substitute for these native bridge observations.

### Native landmark orientation and read-only camera receipts (PL-857)

Every mod-enabled map run records `startup-world.json` (also report's
`startup_world`) immediately after city load and **before any harness camera
or run overrides**. It contains the native interpolated current camera
position/angle/size/height, requested target fields, actual render transform
(position/forward/up/Euler angles), and `areas_visible`. Heading is yaw in
Unity world axes: `atan2(forward.x, forward.z)` in [0,360), so0faces+Z and90
faces+X; no geographic north assumption is embedded. At a near-vertical view
render heading is null; current native yaw/tilt remains available.

To require geographic orientation checks, add this object to the frozen probe
JSON (numbers shown are **synthetic examples, not Asheville landmarks**):

```json
{
  "landmark_expectations": {
    "reference": "Independent DEM and landmark coordinates, source/hash and vertical-transform provenance",
    "points": [
      {"name": "ridge", "x": 103.125, "z": -500.75, "expected_height_m": 612, "tolerance_m": 12},
      {"name": "river", "x": -1000, "z": 2048, "expected_height_m": 101, "tolerance_m": 12}
    ]
  }
}
```

Use at least two uniquely named known landmarks with separated x **and** z
coordinates and expected heights distinguishable beyond combined tolerances.
Coordinates are native world meters; expected heights are native game-height
meters **after the documented DEM vertical transform**, not unconverted ASL
and not sampled back from the prepared game grid. Extra per-point source
metadata is retained. Choose tolerances for DEM accuracy, quantization and
native cubic smoothing; do not widen them to hide orientation failures.
`TerrainManager.SampleRawHeightSmooth(Vector3(x,0,z))` supplies each native
height. Input coordinates are retained exactly; `sample_position` records the
actual float32 position passed to the native sampler.

The `terrain_landmarks` verdict row fails on any out-of-tolerance height,
missing/malformed evidence, wrong point identities, or startup observations
already in Area Zoom. Without landmark expectations it skips; camera receipts
are observational, not an assertion that any heading is correct. This detects
orientation mismatches but does not automatically rotate terrain or override
the camera. Verify the actual artifact under investigation: a newer package
cannot certify an older screenshot/package.

For Area Zoom inspection, open the actual area UI through ordinary gameplay
and call `world_observe` with optional `points` containing `{name,x,z}` objects:

```sh
uv run cs1-harness call world_observe '{}'
```

This op is entirely read-only, usable in normal/Area Zoom views. It neither
opens the UI nor changes terrain, camera or area state. Strict disableMods
vanilla runs remain a separate workflow; this mod bridge is not available there.

Native source notes (installed game's decompilation):

- `TerrainManager.SampleRawHeightSmooth` maps worldx/16+540 to the contiguous
  x index and worldz/16+540 to rowz; smoothing indexes `rawHeights2[z*1081+x]`
  and converts height units by/64. This establishes native axes, not the actual
  geographic correctness of an untested package.
- `CameraController.SavedCameraView` serializes mode,position,size,angle,height;
  `GameAreaManager.Data.Serialize` stores it after the four buildable-area
  floats. `Reset` restores it only when saved mode matches load UpdateMode.
  Native enum values are NewGameFromMap=2 and LoadGame=3; ordinary in-game saves
  use3, map-editor saves use1. Otherwise Reset uses original camera settings
  plus start-tile offset. Binary patch safety still requires exact version and
  offset verification; this harness does not patch serialized camera data.
- `GameAreaManager.UpdateAreaMapping` chooses Area Zoom yaw0/180 or±90 from
  the current camera right-vector and uses SetOverrideModeOn. An Area Zoom
  heading alone therefore does not establish that terrain was transposed.

### Opt-in opening and actual Areas-tool views (PL-857; offline verified)

Add `startup_views` to the frozen probe JSON to require native camera headings
and rendered evidence in the untouched opening view and actual Area Zoom.
These are **explicit example expectations**, not verified headings for a map:

```json
{
  "startup_views": {
    "opening": {"native_yaw_degrees": 0, "render_heading_degrees": 0},
    "area_zoom": {"native_yaw_degrees": 0, "render_heading_degrees": 0},
    "tolerance_degrees": 1
  }
}
```

Both headings are required for each view; comparison is circular in degrees.
Tolerance must be explicitly chosen in `(0,5]`. Native yaw is the interpolated
`SavedCameraView.m_angle.x`, not the target angle. Render heading is the world
forward-vector heading described above; a null/vertical heading cannot pass.
No geographic orientation or pivot expectation is inferred from these fields.

After the existing `startup-world.json` observation and **before the first
harness camera override**, the driver pauses simulation, captures the opening
view without aiming it, and calls `area_zoom {"enabled":true}`. That op uses
`ToolsModifierControl.SetTool<GameAreaTool>()`, just like the normal toolbar.
Native `GameAreaTool.OnEnable` sets `AreasVisible`; the game itself performs
Area Zoom camera mapping. This is not a maximum-zoom camera preset. The helper
waits up to 15 seconds per mode for three native/render heading samples,
0.25 seconds apart, stable within 0.1 degrees, and checks again after each
native PNG capture. PNG completion/decode uses the same bounded reader as the
New Game panel check. Bridge calls retain the client's socket timeout.

In `finally`, it selects `DefaultTool`, waits for `AreasVisible=false`, and
restores the previous pause state. It never calls `camera`, purchases a tile,
changes terrain/package data, or edits any camera field. `world_observe`
remains unchanged and read-only. Runs without this request do not open Areas
or capture these additional images; the new verdict row skips.

Evidence files are `startup-views.json`, `startup-opening.png` and
`startup-area_zoom.png`. The JSON binds the initial startup-world hash, mode
transitions, stable samples, post-capture observations, native screenshot
path/frame receipts, image dimensions/hashes and tool cleanup. The
`startup_views` verdict fails on missing/changed evidence, incorrect phase,
wrong tool/mode, unstable or out-of-tolerance headings, invalid/blank PNGs,
or missing visual review. Initial startup headings must also match the opening
expectations, so a later settled view cannot hide a wrong opening heading.

Inspect both actual game PNGs, then add `startup-views-review.json` to the run:

```json
{
  "reviewer": "Who inspected these two exact PNGs",
  "notes": "What was visibly checked; identify the intended opening and Areas view",
  "opening": {
    "sha256": "SHA-256 from the opening capture",
    "view_matches": true,
    "areas_ui_visible": false
  },
  "area_zoom": {
    "sha256": "SHA-256 from the actual Areas capture",
    "view_matches": true,
    "areas_ui_visible": true
  }
}
```

Do not generate those assertions from native camera values. They assert actual
screenshot content; numeric heading comes separately from native readbacks.
Re-run `cs1-harness judge RUN_DIR` after review. No geographic `ground_truth`
or landmark contract is added or changed by this check.

Implementation has an installed-assembly build and mocked fixture coverage,
**not native execution**. The tool transitions, opening/Areas PNGs, headings,
and cleanup still require a live run; no actual map passes based on these tests.
