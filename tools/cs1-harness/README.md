# cs1-harness

Runs Cities: Skylines 1 on blade's GPU with no screen, so agents can drive it.
It has two layers. A **session** (`up` / `call` / `down`) holds the game
running headless and takes ops over a loopback socket from any tool. Tools sit
on that session:

- the **map check** (`run`) starts a New Game on a `.crp` map, lets the
  simulation run, and reports water, population, log errors and GPU load, with
  screenshots;
- the **Asset Editor mode** (`asset build`, `asset check`) turns an FBX import
  set into a building `.crp` through the game's own editor, then loads that
  `.crp` in a separate game process, places it and checks it.

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

## Asset Editor mode

```sh
# An import set: <name>.fbx, <name>_lod.fbx and the _d/_s/_i/_c (and _n/_a) maps,
# e.g. from ../cs1-assets (`cs1-assets kit-house`), with its <name>.bake.json.
uv run cs1-harness asset build --src ~/experiments/PL-880-asset-bridge/kit-house \
    --name KudzuCraftsman --out ~/experiments/PL-880-asset-bridge/build
uv run cs1-harness asset check --crp ~/experiments/PL-880-asset-bridge/build/KudzuCraftsman.crp \
    --map Asheville.crp --out ~/experiments/PL-880-asset-bridge/check
```

`build` copies the set into `Addons/Import`, opens the Asset Editor on a new
asset (`asset_editor`), and runs the `asset_build` job in the mod. The job
drives the game's import wizard the way a player does, through its own panels
and handlers: it picks the template (`--template auto` takes a low-density
residential level-1 template on the lot), selects the FBX, waits for the model
and textures, sets the scale, compares the imported size with the bake receipt
(a unit or axis slip fails here), continues, waits for texture compression,
sets the lot in 8 m cells, and saves through the save panel after its
compulsory snapshots. The `.crp` lands in `--out`; the import set and the
`.crp` leave the game's data at `down`.

`check` starts a fresh game with only that `.crp` added (the harness mod
present and disabled, as always), starts a New Game on the map, places the
building completed at a dry, flat spot near the centre (`--at x,z` to choose),
and takes close, distant (past its LOD distance) and high views at noon and at
22:00. Then it saves the city, reloads the save and checks the building is
still there by id and prefab name. The save is deleted at `down`.

Two things the editor needs on blade that a desktop doesn't:

- **Texture read-back.** The game's native `Image(Texture)` read-back kills the
  process under VirtualGL. `asset_editor` installs `Readback.cs`, which reads
  textures back through Unity instead, for that game process only
  (`safe_readback: false` turns it off; `call image_check` reproduces the crash).
- **Colours.** By default the job turns the template's colour variations off and
  sets the materials' colours to white, so the model keeps its own colours
  (`color_variations: true` keeps the template's).

The import set's scale comes from its bake receipt (`import_scale`, 100 for
`cs1-assets` FBX files), and a size mismatch fails the job before anything is
saved.

Placing a growable by hand would leave a construction site that the
simulation abandons without zoning or a road, so `place_building` marks it
completed and the check keeps the simulation paused.

The ops are usable one by one: `asset_editor`, `templates`, `asset_build`,
`job`, `custom_assets`, `place_building`, `building`, `time_of_day`,
`save_game`, `load_game` (`call ops` has a line on each). Long ones run as a
job in the mod; poll `call job`.

## Files

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
- **Saves only on request.** The mod stops the autosave timer once a city or
  the Asset Editor loads. Only `asset_build` and `save_game` write, and the
  driver removes what they wrote at `down`.

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
run takes a single overview screenshot set and no point samples.

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
| .NET SDK | `~/.cache/cs1-harness` |
| Built mod | `tools/cs1-harness/.build` in each checkout |

`setup` sets the game's Steam launch options to `<wrapper> %command%`. Without a
harness session on the current display the wrapper runs the game unchanged, so
playing on `:0` is unaffected. `setup --undo` removes the launch options,
wrapper, VirtualGL and mod. Session pieces (`cs1-harness-xvfb`,
`cs1-harness-dbus`, `cs1-harness-steam`) are transient `systemd --user` units
that exist only while a session is up; `cs1-harness-gpu` samples the GPU every 5 s into the session's `gpu.csv`.
