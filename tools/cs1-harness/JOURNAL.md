# cs1-harness journal

How agents built and improved this harness: raw material for a write-up. One
entry per change that mattered: the date, the agent and issue, what got in the
way, what changed, and before/after (boot time, failure rate, what's newly
possible). Keep entries short and honest; failures count.

## 2026-11-09 · Opus 5.5 (blade) · PL-856 · first build

**In the way.** Cities: Skylines tests ran on worm's desktop, and worm
overheats. Moving them to blade meant running a Unity game with no screen,
without disturbing Caleb's streamed desktop (`:0`) or his Steam account.

**Tried and dropped.**
- *gamescope headless*, the brief's first suggestion: "physical device has no
  primary node". The `caleb` user can't open `/dev/dri/card*`, and changing that
  is an access change.
- *Steam on the agents' existing display, with the desktop's D-Bus*: Steam's
  Flatpak exits with "requires a correctly-configured desktop session".
  Blade's user manager has no `DISPLAY`.

**What worked.**
- VirtualGL's EGL back end inside the Steam sandbox. It needs only
  `/dev/nvidia*` and renders GLX on the RTX 3090 (`egl1`) onto a private
  `Xvfb :57`.
- A private session bus with `DISPLAY=:57`. Steam starts and signs in with the
  saved account, and nothing on the desktop changes.
- A zenity stub, so the Flatpak wrapper's udev warning can't hang a headless
  start.
- Control through a mod constructed at startup (the game builds every local
  mod, even a disabled one), so nobody has to tick it in Content Manager.
  `--disableMods` turns off mod loading altogether, so runs use
  `--noWorkshop` instead.

**Got in the way and wasn't solved.** The game's first launch on a new machine
stops at Steam's EULA prompt. The harness doesn't answer it: accepting the EULA
is Caleb's call, and it's waiting on him.

**Before → after.** Before: game tests needed worm's desktop and an agent
clicking through menus. After: `cs1-harness doctor` shows GPU rendering on the
harness display in 1.5 s, with no Steam and nothing left running. The full
game path hasn't run yet.

## 2026-11-09 · Opus 5.5 (blade) · PL-856 · from tool to platform

**Why.** Caleb wants the harness to be a shared tool that agents improve, and
the next users need more than map checks. Example: a prompt-to-asset pipeline
that drives the Asset Editor.

**Changed.**
- The mod's single `switch` became an op registry. `CoreOps` (status, speed,
  camera, UI, screenshot, quit) is split from `CityOps` (New Game, stats,
  water, grids). `call ops` lists what a build can do.
- `up` / `call` / `down` hold a session across CLI calls, which is the layer
  an MCP server or an editor driver would sit on. The map check (`run`) is now
  one tool on top of it.
- GPU sampling moved from a Python thread to a transient `nvidia-smi -l 5`
  unit, so detached sessions get it too.

**Before → after.** Before: one command, `run`, which held everything in one
process. After: any agent can start the game, send ops and stop it from a
shell. Second `up` while one is running exits 75 with a clear message; `call`
with no game says how to start one. In-game ops are still unverified.

## 2026-11-09 · Sol 6.1 (worm) · PL-857 · display fallback

Source: PL-857, before the 20:15–22:30 ET Steam blackout. CS1 1.21.1-f9 on
worm aborted in `SDL_GL_GetAttribute_REAL` before managed startup, both at
1920×1080 windowed and 3840×2160 fullscreen with `-force-glcore`. The existing
GNOME Xorg `:0` had a 3840×2160 screen, but every connector was disconnected
and NVIDIA's `CurrentMetaMode` was `NULL`. The 2080 Ti PRIME-offload route and
a clean transient user-unit launch had the same failure. These observations
do not establish the crash's cause.

`-batchmode -nographics` reached managed startup, then exited on **Steam
Initialization failed** with the Steam client signed out. This is not proof
of usable headless gameplay. No login, EULA acceptance, display reconfiguration
or GPU power change was attempted. The original bridge DLL and game settings
were restored. No game or test-owned Steam process was left running.

Worm's monitor must remain off because it faces Caleb's bed. Do not ask for it
to be turned on or change the live X session to make tests work. Use blade's
private GPU display once its first-launch gate is resolved. PL-857 still needs
ordinary New Game with `--disableMods --noWorkshop`, water stability and native
car-path checks for five generated maps; programmatic map loading alone is
not that acceptance evidence.

## 2026-11-09 · Opus 5.5 (blade) · PL-856 · onto the 2080 Tis

**Why.** Caleb: the 2080 Tis are barely used and "more than suffice for 1080p
Cities: Skylines". Using them keeps blade's 3090 free for experiments and
keeps worm's 3090, whose fan can wake him, out of it.

**Changed.**
- The GPU is chosen by PCI bus ID (`05:00.0` on both hosts), not by an EGL
  index someone looked up once. The harness probes each VirtualGL EGL device's
  renderer and picks the one that matches. After launch it fails the run if
  `Cities.x64` shows up on any other GPU in `nvidia-smi -q -x`, graphics
  processes included.
- `--host` picks a profile: blade (Flatpak Steam) or worm (native Steam). The
  default is the machine's hostname; worm's is `r5-worm`. Running another
  host's profile locally fails with the ssh command to use instead.
- Reports now give VRAM on the pinned GPU: what other work held before launch,
  the peak, and the game's share.
- The mod is installed at launch, not at session start, so `doctor` and
  `up --display-only` never touch game data.

**Before → after.** `doctor` picks the 2080 Ti on both hosts: `egl0`, about
1.5 s. Blade's card has 3,291 MiB free beside the `decisions` Ray replica
(7,973 MiB), which is unmeasured headroom for CS1 until the first game run.
Worm's card has 11,254 MiB free. Worm still can't launch the game through the
harness, because its Steam client is signed out (PL-857 entry above).

## 2026-11-09 · Opus 5.5 (blade) · PL-856 · eyes: Clef-Flash, and the grid where it can't see

**Why.** The lead suggested blade's resident Clef-Flash (`127.0.0.1:9120/v1/systemone`,
the `decisions` replica on the same 2080 Ti) for things the game's state
doesn't report: stair-stepped terrain, water that looks wrong, black or garbled
frames, whether the start looks buildable. The rule stays: where the mod reads
the truth, trust that over Clef.

**Tried.** I labelled 20 screenshots myself, without looking at Clef's answers:
17 real frames from PL-828/PL-848 on worm (menus, a loading screen, a GNOME
crash dialog, editor and city views, Innsbruck before and after smoothing, and
Rio with the transient water sheet over land) plus 3 synthetic bad frames
(black, shifted blocks with a noise band, a magenta hole). One request per
image, about 1 s each after a 3 s first call. The server caps images at 384².

| Question | Caught | Missed / false |
|:--|:--|:--|
| Frame kind (world / menu / desktop / blank) | 18 of 19 labelled, including the crash desktop (0.97) and the black frame | the loading screen, whose backdrop is a 3D scene, scored "world" (0.94) |
| Garbled frame, threshold 0.5 | 3 of 3 synthetic (0.71, 0.79, 0.95) | no false positives on 17 real frames (max 0.12; the crash desktop 0.42) |
| Stair-stepped terrain | none | raw Innsbruck import 0.085 vs smoothed 0.03-0.05; 384 px native crops about 0.02 everywhere |
| Water looks wrong | none | Rio's water sheet over land 0.27, within the 0.06-0.30 of normal frames; a dry Rio crop scored 0.41 |
| Buildable land | not checked | no labels |

**Changed.**
- `run --clef` scores every screenshot after the run and flags frames that
  aren't the game world or score above 0.5 for garbling. It's advisory, and
  `cs1-harness see IMAGE…` does the same by hand.
- Terraces come from the grid instead. Every report checks the game's own raw
  heights. On ground with more than 4 m of relief in a 5 × 5 window, it counts
  how often east-west neighbours have exactly equal height. Measured on
  PL-828's smoothed heightmaps: Asheville 0.002, Innsbruck 0.003, Rio 0.022.
  Quantized copies of the same maps: 1 m steps 0.14-0.17, 4 m steps 0.44-0.51,
  8-bit source 0.54-0.56. Threshold 0.08. PL-848's Asheville terrain grid
  scores 0.003.
- Water stays with the mod's numbers: probe depths, wet area gained or lost,
  and volume.

**Limits.** I chose the labels and judged the screenshots myself, the set is
small, the garbled frames are synthetic, and the terracing positives are
quantized copies, not a real stair-stepped game import.

## 2026-11-10 · Opus 5.5 (blade) · PL-856 · first game runs, and the rivers drain

**Unblocked.** Caleb authorized accepting the Cities: Skylines EULA in blade's
Steam, and nothing else. It was clicked on the harness display through XTEST,
and Steam logged "accepted eula 255710_eula_0".

**Got in the way, in order.**
1. *Steam doesn't resume the launch after the EULA.* The second try said
   "Update required" while a CS1 shader-cache update was finishing; the third
   went through.
2. *Steam's target is Paradox's launcher (`dowser`).* It showed its own
   Paradox User Agreement. Accepting that is outside the authorization, so it
   was closed unanswered. In a harness session the launch wrapper now swaps
   `dowser` for `Cities.x64` and keeps Steam's reaper and Steam Linux Runtime
   container, the same binary worm's runs always used.
3. *Software rendering.* VirtualGL's preload outside pressure-vessel doesn't
   reach the game, which reported `llvmpipe`. The wrapper now preloads it on
   the game itself, inside the container, with absolute paths. The placement
   check now fails a run that isn't on any NVIDIA GPU; before, it passed
   because no wrong GPU showed up.
4. *Small things.* CS1's main menu is the `IntroScreen` scene. Steam logs
   launch prompts in `webhelper_js.txt`. The game names its data directory
   through Flatpak's `data -> .local/share` link, so maps are matched by file
   identity. `nvidia-smi -f` buffers until exit (the unit now uses systemd's
   stdout).

**The proof: PL-848 Asheville, 60 game-minutes on blade's 2080 Ti.**
- **Timing.** Main menu 49 s after `Steam starting`, city loaded 39 s later.
  `fixedDeltaTime` is 1/60 s, so a game-minute is 3,600 frames. Speed 3 (4×)
  sustained about 161 frames/s, not the nominal 240: 60 game-minutes took
  27 min of wall time.
- **GPU.** `Cities.x64` was on 2080 Ti `05:00.0` only. VRAM 1,574 MiB at the
  menu, peak card total 10,821 of 11,264 MiB beside the `decisions` replica's
  ~8 GB, so the game's peak was about 2.8 GB and headroom was about 440 MiB.
  60 °C max, 119.5 W mean and 148.3 W max against the 150 W cap, 94 % mean
  utilisation.
- **Water.** Both sources stay active (flow 756 and 930 at capacity 0.2), but
  the prefilled channels drain. Volume falls from 9.1 M m³ to about 1.16 M m³
  by minute 25, then holds. Wet area goes from 3.09 to 0.70 km², with 0.01 km²
  newly wet (no flooding). River probes wet: 62/62 at the start, 20/62 at the
  end. All French Broad samples from FB06 downstream dry out, and the lower
  Swannanoa does too. PL-848's short checks couldn't show this.
- **Terrain.** No terracing (0.0034).
- **Log.** 27 error lines: localisation noise, and worm's `CitiesBridge.dll`
  failing to load because Harmony is a Workshop item and the run uses
  `--noWorkshop`. The bridge is disabled, so these are expected.
- **Clef.** 9 of 25 screenshots flagged, all at minutes 30 and 45, and all
  night frames from the game's day/night cycle. Clef called them "world" but
  scored garbling 0.53-0.81. They're false alarms. Fix: screenshots in
  daylight, or day/night off for harness runs.
- **Teardown.** Nothing left running: no game, Steam, display, bus or sampler.

**Not working yet.** Hiding the UI before screenshots leaves the bottom
toolbar visible.

## 2026-11-10 · Opus 5.5 (blade) · PL-857 · waiting for the slot

Two lanes now share blade's harness. PL-880 runs short Asset Editor builds
back to back, and PL-857 needs five 60-minute soaks, about 27 minutes each. A
soak that exits 75 on a held lock and retries every 30 minutes keeps losing to
the short loop. `run` and `up` now take `--wait-minutes N`: they poll the slot
every 2 s and start in the gap between the other agent's commands. Nobody has
to ferry messages between lanes, and nothing ends another session.

Found on the way: a run blocked by an `up` session, a running game or Steam
kept its lock open for the whole `--retry-minutes` sleep. Python keeps the
exception, and with it the session's lock file, alive during the sleep. So a
blocked waiter held everyone else out. `__enter__` now releases the lock when
it raises.

## 2026-11-10 · Opus 5.5 (blade) · PL-856 · watching a run

**Why.** Caleb: "it would be neat to be able to peer in and see what the agent
is seeing as it is doing the playtest." The lead had already grabbed the
display by hand and found PL-857's game behind a Paradox "Account Link Found"
prompt. Being able to look settles questions like that.

**Changed.**
- *Timelapse.* One ffmpeg per session grabs the harness display at 1 fps. It
  writes `timelapse.mp4` (H.264, 1280 px, played back at 30 fps) into the run's
  output, and every 5 s an atomically replaced JPEG for the live page. The
  first try played at 2× the intended rate; `fps=1` plus passthrough timing
  fixed it.
- *Live page.* `https://blade.tailc29f0.ts.net/research/cs1-live/` (tailnet
  only) shows the frame and a status line: label, map, game-minute, water
  probes, population, fps. It uses blade's existing `/research/` Tailscale
  Serve directory, so there's no new route or port. The shelf links to it, and
  it says "No harness run" when a session ends.
- *Live view.* `cs1-harness watch`: x11vnc 0.9.16 unpacked from Ubuntu's
  packages into `~/.local/opt`, view-only, bound to 127.0.0.1 and ::1, with a
  per-host password. Reach it with an SSH tunnel. It works for `run` sessions
  as well as `up` ones.
- `~/.local/bin/cs1-harness` is a stable command (installed by `setup`). The
  mod reports smoothed render frame time.

**Does watching slow the game?** `bench-observe`, PL-848 Asheville at speed 3
on blade's 2080 Ti, three 60 s windows: off, on, off. "On" means timelapse,
live page, and x11vnc with a viewer pulling raw updates.

| Window | Sim frames/s | Render frame (ms) | Game CPU | Observer CPU |
|:--|--:|--:|--:|--:|
| off | 157.5 | 153.8 | 192 % | 0 |
| on (viewer 13.7 MB/s) | 155.7 | 157.2 | 187 % | 3.7 % |
| off | 155.4 | 157.7 | 186 % | 0 |

"On" is within the drift between the two "off" windows: sim rate 1.1 % below
the first and 0.2 % above the second. On its own, the grabber used 2.6 % of one
core. Render frames are long (about 6 fps) because at speed 3 the simulation,
not drawing, sets the pace. The bench viewer stalled once for 10 s in the "on"
window (a socket timeout), so its 13.7 MB/s average understates a viewer that
never pauses.

**Noticed.** This session came up at 1280×720, where earlier ones were
1920×1080. Something changed the game's resolution setting between runs.

## 2026-11-10 · Opus 5.5 (blade) · PL-880 · Asset Editor mode: a kit house to a placeable .crp

**In the way.** The prompt-to-asset pipeline needs the game's Asset Editor,
which has no API. CSUR RoadImporter drives it for roads from inside the game;
nothing did it for buildings, or headless.

**What changed.**
- `EditorOps.cs` opens the editor on a new asset and runs one job: pick the
  template, select the FBX in the import wizard, wait for the model, set the
  scale, compare the imported size with the bake receipt, continue, wait for
  texture compression, set the lot, and save through the save panel after its
  compulsory snapshots. `CheckOps.cs` loads the `.crp` in a fresh game, places
  it completed, sets the clock, and saves and reloads the city.
  `asset build` / `asset check` drive them; `Jobs.cs` steps multi-frame work
  once a frame so ops stay quick.
- **The native texture read-back kills the game here.** `Image(Texture)` reads
  the GL texture through its native pointer; under VirtualGL's EGL back end the
  process died a few seconds later with no trace, in threaded and direct
  rendering, for RGB24 and RGBA32. The importer's compression and the package
  save both use it. Bisected with `image_check` (no debugger: ptrace scope 1,
  no gdb, no cores). `Readback.cs` redirects that one constructor to a read-back
  through Unity (the texture's CPU copy, else blit and `ReadPixels`, keeping
  sRGB colour maps encoded because the game renders in Linear). It is installed
  for Asset Editor sessions only and lasts for that process.
- The launch wrapper now keeps the game's stdout and stderr in the run
  (`game-stdout.log`), where Mono writes native crash traces.
- `status` reports the modal stack. A Paradox "log in with Steam" panel sits on
  the main menu; New Game and the editor load past it, and nothing answers it.
- The pointer is parked off-centre before screenshots: the game's hover
  highlight tinted the building blue under the centred pointer.
- The mod builds per checkout (`.build/`). The shared `~/.cache` build let one
  agent's `build` change the DLL another agent's next `up` installed.
- `CS1_HARNESS_SCREEN=1280x720` sets the harness screen. It saved little VRAM
  (10.78 GB vs 10.82 GB on the card), so it is a knob, not a fix.

**Learned in game, not from docs.** Blender's "FBX All" export is read at
1/100 scale (the asset guide's "scale 100"). The importer negates X but keeps
winding, so correctly wound meshes render inside out; `cs1-assets` writes
reversed triangles with outward custom normals. Built-in themes load through
their metadata's `assetRef`, not the metadata asset ("File format version not
supported"). Custom buildings become prefabs only when a level loads. Flatpak
shows the data directory through a `data` symlink, so paths compare resolved.

**Before → after.** Before: no way to make a building asset without a person
in the editor. After: `asset build` turns an FBX import set into a `.crp` in
about 2 minutes, game start included (17 s from import to save), and `asset
check` places it in a fresh New Game with day, night, distant and reload views
in about 4 minutes.

## Run log

Per run: host, GPU, peak VRAM (total and game share), peak power and
temperature, wall time, result. Copy the VRAM and GPU lines from `report.md`.

| Date | Agent · issue | Host · GPU | Peak VRAM (game) | Peak W / °C | Wall | Result |
|:--|:--|:--|:--|:--|:--|:--|
| 2026-11-10 | Opus 5.5 · PL-856 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB game | 148 W / 60 °C | 27 min sim (31 min total) | 60 game-min Asheville; rivers drain to 20/62 wet probes |
| 2026-11-10 | Opus 5.5 · PL-856 | blade · 2080 Ti 05:00.0 | 2,414 MiB free before launch | (bench) | 6 min | observer A/B/A: no measurable slowdown; `observe-bench/timelapse.mp4` |
