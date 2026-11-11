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

uv run cs1-harness run --map Asheville.crp --scenario test-city \
    --game-minutes 10 --sample-every 1 --wait-minutes 90 \
    --issue PL-893 --out ~/experiments/PL-893-test-city/asheville
```

The game writes files (screenshots, grids, log) only inside the Steam sandbox,
so paths given to ops must be under
`~/.var/app/com.valvesoftware.Steam/` or `/peach/Games/SteamLibrary`. `run`
stages there and moves results to `--out`.

## Standard test city

`run --scenario test-city` builds a disposable city after ordinary New Game,
then runs the same water/terrain soak. It finds a dry site in the starting
tile, connects the existing highway approaches to a 288 m road grid, zones
residential/commercial/industrial, and places a coal plant, water pump, drain,
pipes and power lines. Construction runs on the simulation thread through
the native tools, with space, slope, purchased-area and money checks. A river
crossing uses the game's bridge/ramp prefabs. It spends starting money; it
doesn't enable unlimited money, place growables, force utility buffers or
set population.
Milestones and their rewards still apply. Their modal notification panel is
disabled for this process so it cannot pause an unattended soak.

The run keeps `scenario.json` (including a partial receipt on a placement
failure), adds a close-up camera view, and observes population between the
normal water samples. A requested scenario adds three verdict checks:

- `population_growth`: at least 50 new residents within 5 game-minutes, with
  that net growth retained at the end.
- `outside_connection`: native passenger-car paths in both directions between
  the grid and the actual map-edge endpoint, with every completed path released.
- `utilities`: power, water and sewage active, both native pipe connection
  nodes attached, and no connection or supply problems.

Without `--scenario`, these checks are skipped; an empty-map soak is not
evidence that a city can grow. Calibration runs are in `JOURNAL.md`.

For another driver, the same ops are `scenario_build` in a paused New Game,
`scenario_status` until `done`/`failed`, and `scenario_paths {"start":true}`
followed by polling `scenario_paths` after the simulation has advanced. A city
can be built only once per New Game. The planner rejects a map without an
accessible starting-tile road hookup, a suitable dry grid site, an affordable
crossing, or usable shoreline; it never bypasses a rejected placement.

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

## Speed

The game's fastest setting, speed 3, is 4× play: 240 simulation frames a
second, so 60 game-minutes take at least 15 wall minutes. On blade's 2080 Ti at
1280×720 the game holds that cap. `run` draws at most 10 frames a second
between screenshot sets (`--render-fps`, 0 for unlimited), which keeps the full
240 at half the game's CPU. It draws at full rate again for each screenshot.
Below about 10 fps the simulation slows, because the game advances at most
about 42 simulation frames per drawn frame. `cs1-harness bench-speed` measures
this on a map, and the mod's `render` op sets the cap (`{fps, camera}`).

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

## Checking against the world

Every other map check is drawn in the map writer's own coordinate frame, so a
rotated or mirrored map would pass all of them. Two checks look from outside
that frame:

- `ground_truth` fetches elevation itself (AWS Terrain Tiles, Terrarium, cached
  in `~/.cache/cs1-harness/terrarium`) and projects it with pyproj into the
  game's frame (+x east, +z north). It then correlates it with the terrain the
  game reports, as is and in the seven other rotations and mirrors. It passes
  when the map as is correlates at r ≥ 0.9 and beats every other orientation by
  0.15. `ground-truth.png` shows north-up hillshades of the real DEM beside the
  game's terrain. Landmark rows give the game's height at the region's highest
  and lowest points, and at any named landmarks. The probe file supplies the
  region: `"ground_truth": {"lat", "lon", "size_m", "rotation", "base"?,
  "landmarks"?: [{"name", "lat", "lon"}]}`.
- `opening_camera` reads the camera the map opens with, before the harness
  moves it, and fails if it faces more than 45° from north. `run` also saves
  what a player sees first: `shots/player-opening.png` (UI showing) and
  `shots/player-area-zoom.png` (fully zoomed out). `--notify` posts both, with
  the New Game panel and `ground-truth.png`.

A map soak with no passing `ground_truth` check reports `unverified`, never
`pass`.

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
map, the last screenshots and the timelapse on that issue when the run ends.
A detached job posts as Driver sessions, and a member's comment on an issue
assigned to an agent starts that agent's next run, so the comment alone wakes
the owner. `--wake` adds an @mention of the assignee; use it only when the
comment wouldn't wake them (for example, when the run posts as that same
agent). A blocked or failed run posts its error verdict the same way.

To queue a check and end your turn, submit it instead of running it:

```sh
uv run cs1-harness submit --issue PL-857 -- run --map X.crp --probes P.json --out ~/experiments/PL-857-…/x
```

`submit` starts the run as a `systemd --user` job that waits for the slot (4 h
by default), retries if Steam says the account is busy, and posts with
`--notify` (`submit --wake` adds the mention). It prints the unit, the log (`submit.log` in `--out`) and
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
