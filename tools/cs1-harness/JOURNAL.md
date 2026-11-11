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

## 2026-11-10 · Opus 5.5 (blade) · PL-891 · fixes from the first independent review

Before merging the harness to `main`, GPT-6.1 Sol (xhigh, `codex exec`) read
the whole diff for anything that would break a real run. It found three, and
all three were real:

- **Teardown could kill a game that isn't ours.** `stop()` quit and then
  killed every `Cities.x64` on the host. A game someone started on blade's
  desktop during a `--display-only` session would have died at `down`.
  Teardown now acts only on games whose environment has the harness `DISPLAY`
  (the running harness game shows `DISPLAY=:57`). Preflight still refuses to
  start while any game runs.
- **A blocked run could take an active run's files.** Staging was named after
  `--out`'s last component, and PL-857 writes many runs to `…/asheville`. A
  second run waiting for the slot with the same name would, on giving up,
  move the first run's logs, grids and screenshots into its own output.
  Staging is now per process (`<name>-<pid>`).
- **`timeout` left the game running.** SIGTERM ended Python without running
  the session's cleanup, so the game, Steam and units stayed up with no state
  file for `down`. SIGTERM and SIGHUP now raise `SystemExit`, and the session
  stops as on any other exit. `uv run` forwards SIGTERM, checked under
  `timeout`.

**Before → after.** Before: three ways a run could damage something outside
itself. After: none of these three; checked offline (display filter against
the live harness game, SIGTERM under `timeout uv run`), not yet in a full run.
## 2026-11-10 · Opus 5.5 (blade) · PL-891 · verdicts

**What got in the way.** A run ended in a prose report. To decide whether a
map passed, an agent read `report.md`, picked its own notion of "wet enough"
and "flooded", and wrote it into a comment. Two agents could read the same run
differently, and nothing could gate on it.

**What changed.** `cs1_harness/verdict.py` declares the pass/fail thresholds
per check type, and every `run` writes `verdict.json`: pass, fail or error,
with each check's value and threshold, the map hash and the harness commit. A
run that stops early writes an `error` verdict with its reason.
`cs1-harness verdict DIR…` re-judges old runs. The map soak judges required
probes wet at the end, flooding beyond the expected water, native paths,
terracing, blank screenshots, Clef frame kinds and cleanup. The asset check
judges load, triangle count, LOD, placement, reload and screenshots.

**Calibration.** I judged copies of every finished run on blade and compared
with what the agents who ran them concluded by hand:

| Run | By hand | Verdict | Failing checks (value) |
|:--|:--|:--|:--|
| PL-856 PL-848 Asheville, 60 min | rivers drain | fail | probes 0/28 required wet |
| PL-857 original fixture, 10 min | flooding | fail | flooding 0.566 km² |
| PL-857 conservative, 10 min | less flooding, rail failed | fail | paths (rail, road_out); flooding 0.040 km² passes |
| PL-857 gap-joining, 60 min | rail failed, abandoned | fail | paths (rail); flooding 0.095 km² |
| PL-857 selected Asheville, 60 min | pass | pass | (flooding 0.0018 km²) |
| PL-857 R0 Innsbruck, 60 min | pass, 0.023 km² stream pooling | pass | (flooding 0.030 km²) |
| PL-857 no-prefill Asheville, 60 min | pass | pass | flooding skipped: no reference water |
| PL-880 asset checks 3 and 4 | pass | pass | |

All nine agree. The flooding number differs a little from PL-857's
`audit_soak.py`, because the harness has only the run's first water dump as
expected water, not the mapped river lines. A probe file can name a
`reference_water` grid to judge no-prefill runs.

An independent review (GPT-6.1 Sol, high) caught two ways to a wrong pass, both
fixed: a probe file that names native paths now fails `paths` when the run
didn't check them (until PR #8 lands, `run` doesn't), instead of skipping; and
the verdict reads the run's frozen copy of the probe file and reference grid,
so editing the source later can't flip an archived verdict.

**Before → after.** Before: reading prose, no gate. After: one file with a
verdict per run, judged the same way every time, and 9/9 agreement with the
hand calls on existing runs.

## 2026-11-10 · Opus 5.5 (blade) · PL-891 · a run registry, and compare

**What got in the way.** PL-857 ran a dozen Asheville and Innsbruck variants
today. Finding which run used which map, and lining their water curves up,
meant reading directory names and journal rows, then writing a one-off script.

**What changed.** Every `run` now adds a line to a host-wide registry
(`~/.local/share/cs1-harness/runs.jsonl`): the run's directory, check type,
verdict, map sha256, harness commit, issue and headline metrics.
`cs1-harness runs` filters it by issue, map, map hash, commit, check type or
verdict, and `runs --index DIR` registers older runs without writing into
them. `cs1-harness compare A B …` overlays water volume, wet required probes
and population over game-minutes in `compare.png`, and `compare.json` lists the
verdict checks that differ.

**Before → after.** Before: no index; a comparison was a custom script per
question. After: `runs --index` on copies of blade's nine finished runs
registered all nine in about a second. One `compare` call put PL-857's
prefilled and no-prefill Asheville beside PL-856's draining PL-848 map: both
PL-857 runs settle near 19 M m³ by minute 20, and the PL-848 map loses every
required probe by minute 25. Runs from before this change have no recorded
harness commit; the registry says so (null) rather than guessing.

## 2026-11-10 · Opus 5.5 (blade) · PL-891 · results wake the owner

**What got in the way.** A 60-minute soak takes half an hour of slot time,
plus however long it waits for the slot. The agent that wanted it had to hold
its turn open the whole time, or end it and schedule rechecks. Today PL-857's
waits stacked behind PL-880's builds, and its scheduled recheck fired into a
slot that was still busy.

**What changed.** `run --notify` comments the verdict table, the water-change
map, the last two screenshots and the timelapse on the run's issue, and
`--wake` @mentions the issue's agent assignee so its next run starts on the
result. `cs1-harness submit --issue PL-NNN -- run …` starts the run as a
detached `systemd --user` job with `--notify --wake`, a 4-hour slot wait and
30-minute Steam retries, so the agent can end its turn right after
submitting. Detached jobs post as Driver sessions.

**Before → after.** Before: hold the turn open or poll. After: submit, end the
turn, and resume on the comment. Checked: the comment body and attachments on
copies of real runs (`notify --dry-run`), and that the `driver` profile reads
issues from blade outside a task. Not yet checked: a live post from a finished
`submit` job; the first submitted run is that test.

## 2026-11-10 · Opus 5.5 (blade) · PL-891 · who has the slot

**What got in the way.** When a run had to wait, the only message was
"another cs1-harness run holds the lock". Agents couldn't see whose run it
was, which issue it served, or how long it would take, so they guessed at
retry times. Nobody counted how often the slot was contended, which is what
Caleb needs to decide on a second Steam account.

**What changed.** `cs1-harness queue` names the holder (from `/proc/locks`
and a `holder.json` the new code writes), its issue, label, minutes held and
an ETA for `run` (3 min of boot and teardown plus game-minutes × the median
wall-per-game-minute in the run registry, 0.3 until the registry has runs).
It lists the waiters, including ones started from older checkouts, found from
their command lines. The slot now logs every wait, acquisition, give-up and
release to `slot.jsonl`, and `queue --stats` sums the window.

**Before → after.** Before: "the lock is held". After, the first live
reading at 15:49 ET: PL-857's Innsbruck soak holds the slot, 11.7 min in with
about 9 min left; PL-857's strict Asheville `up` and PL-856's dialog retest
have each been waiting about 11 min. The contention log starts empty and
counts only runs from this checkout on.

## 2026-11-10 · Opus 5.5 (blade) · PL-891 · triage

**What got in the way.** A run that stopped said only "failed: …" or
"blocked: …". Before anyone could fix it, someone had to work out whose
problem it was: the map's writer, the harness, Steam, the game, a dialog or
the GPU. That meant digging through the game log, Steam's logs and
`nvidia-smi` by hand, often after the evidence had rotated away.

**What changed.** Every non-pass now carries a triage class in
`verdict.json` (`map`, `harness`, `steam`, `game-crash`, `unknown-dialog`,
`gpu-vram`, `slot`, `unknown`), with the rule's reason and the evidence copied
beside it: log tails, Steam's launch lines, the last live frame and GPU
samples. An unexpected Python exception no longer escapes `run`. It becomes an
error verdict classed `harness`, with `traceback.txt`, and still posts with
`--notify`. The registry and the `--notify` comment show the class.

**Before → after.** Before: an error string, with the evidence somewhere on
the host. After: a class, a reason and files. On blade's four failing runs,
triage says `map` for each, which is what their agents concluded. Nine
synthetic error reasons, one per harness message family, land in the
expected class. One case needs Steam's own log to decide: the game ending
because the account started playing elsewhere is `steam`, not `game-crash`.
Not covered yet: the dialog guard on PL-856's dialogs branch writes
`dialogs.jsonl`, which triage reads once that lands.

## 2026-11-10 · Opus 5.5 (blade) · PL-891 · the harness over MCP

**What got in the way.** Claude agents drive the harness from a shell. Codex
and DeepSeek agents in other harnesses do best with tools, and each would
otherwise learn the CLI's flags from the README.

**What changed.** `cs1-harness mcp` is a stdio MCP server (Python `mcp` 2.3,
`MCPServer`) with ten tools: `queue`, `contention`, `runs`, `verdict`,
`compare`, `submit`, `notify`, `up`, `call`, `down`. Each one shells out to
the CLI, so there's one contract and one set of slot rules. `verdict --json`
now prints only JSON, which the tool returns.

**Before → after.** Before: shell only. After: an MCP client over stdio
listed all ten tools, and `queue`, `runs` and `verdict` returned live results
(PL-857's Innsbruck soak holding the slot; PL-857's passing runs; PL-856's
PL-848 verdict, a fail with its triage). Not exercised over MCP: `up`, `call`,
`down` and `submit`, which only wrap the CLI commands of the same names.

## 2026-11-10 · Sol xhigh (blade) · PL-893 · standard test city

**Why.** Empty-map soaks stay at population 0 and cannot test whether a
player's road grid reaches the outside world. `run --scenario test-city`
adds a small city after ordinary New Game, before the existing soak.

**Changed.** `ScenarioOps` builds through native road and building placement
checks on the simulation thread. It selects a dry starting-tile site, joins
the highway approaches, builds a grid, zones R/C/I, and adds a coal plant,
water pump, drain, pipes and power lines. Normal construction costs come from
starting money. No growables, population, utility buffers or completion flags
are forced. The run preserves the construction receipt and checks actual
population growth and native passenger-car paths in both directions.
The source-dirty flag now covers the whole harness, including `mod/`, rather
than just the Python package. A temporary untracked file under `mod/` reproduced
the false-clean result before the fix and reported dirty afterward; removing
it restored clean status.

**Native rules that mattered.** Inspected against the installed CS1 1.21.1-f9
assemblies, then exercised in fresh New Games:

- `NetTool.CanAddSegment` rejects direction dot products over 0.75, including
  pipes and wires. The highway merge must be close, and utility branches must
  use legal angles at connected network nodes.
- PL-848's highway ends are physically about 12 m above terrain although their
  stored node elevation and prefab base height are both zero. Connection
  elevation must come from world geometry relative to the native terrain
  sampler, not that stored byte.
- The stock water prefabs are `Water Intake` and `Water Outlet`, both
  `ShorelineOrGround`. Select by AI capabilities and normal unlock/cost checks,
  not translated UI names. Use the shoreline height rules from the building
  tool, not its roadside maximum height difference.
- A legal shoreline site can be across an elevated railway from the power
  network. Test power access before committing the facility. Pipe proximity
  alone also isn't enough: attach to the facility's native `m_netNode`.
  A development city grew to 154 despite disconnected water, so the verdict
  now separately requires active, connected utilities without supply problems.
- The fixture omits only `UnlockManager`'s modal milestone presentation.
  Unlocks and rewards still run, but the panel cannot pause an unattended soak.
- Green Plains' highway ends are at x=917.28 and 920.18 m: legally inside the
  tile, but outside the planner's original 48 m inset (x<912). The first attempt
  failed. Using the native purchased-area test fixed it without an exception
  for this map. Receipts now include the tile and twelve nearest road-node
  candidates, and inspection remains usable when construction fails.

**CLI proofs.** Native build, Ruff (22 files), eight verdict tests and the GPU
doctor pass. Both final runs use the same mod DLL (SHA-256
`dee3d1f6bb82accb1ba0a764824d79271784b1df8fef91ca68ec9b5f111cc9a9`).
Both proof commands use `run --scenario test-city --game-minutes 10
--sample-every 1 --screenshot-every 5 --dump-every 5 --wait-minutes 240`.
Evidence lives under `~/experiments/PL-893-test-city/`. Green Plains records
harness `3c84b91`; Asheville records `8fa196e` (documentation-only changes).
The later provenance fix changes no construction or verdict decision logic.

| Map / output | Population | First observed +50 | Native edge paths | Utilities | Verdict | Wall |
|:--|:--|:--|:--|:--|:--|:--|
| Exact PL-848 Asheville / `asheville-area-10` | 0 → 380 at 10.01 game-min | 1.935 game-min | 1 inbound + 1 outbound, found and released | all active, no problems | pass | 6.18 min soak; 8.58 min active; 25.98 min queue |
| Vanilla Green Plains / `vanilla-area-10` | 0 → 411 at 10.06 game-min | 1.524 game-min | 4 inbound + 4 outbound, found and released | all active, no problems | pass | 5.69 min soak; 8.15 min active; 21.15 min queue |

Asheville's source SHA-256 is
`b8507bf6e4c00f2336eb2051daed8785a6912a56ad594161e1e09a32ef0c94f4`.
Construction spent $48,680 of $70,000 starting cash. At the end, 63 residential,
10 commercial and 24 industrial buildings had grown without growable warnings.
The native paths include grid segment 35065 and physical edge endpoints
19415/255 outbound and 6014/0 inbound; both path units were released.
Cleanup reports no game, Steam instances or harness units left running.

Green Plains (`NorthEurope1FINAL.crp`) has source SHA-256
`a4afe28315db5fbcb7b5a08548a80a495960a358bafdf39ad47d435f01d9d538`.
It spent $45,520 and grew 60 residential, 6 commercial and 28 industrial
buildings, also without growable warnings. All eight paths include grid
segment 13760 and the physical map-edge endpoint; all were released. Utilities
were active and cleanup was empty. The earlier Asheville proof, before the
hookup-selector correction, grew 0 → 377 in 10.05 game-min (`asheville-10`).

**Calibration.** Require 50 new residents by 5 game-minutes, retained at the
end. Both final runs cross 50 before minute 2, leaving over 3 game-minutes of
margin for slower arrivals; the empty-map baseline stays at zero. The separate
utility check rejects the observed development false-pass (154 residents but
disconnected water). Outside reachability requires native path positions at
the grid and the real edge endpoint in both directions, not summary booleans.

**Not verified.** Every map, long-term city/utility health, required river
probes or Clef. These city proofs do not replace PL-848's known failing
60-minute river soak. The final Asheville startup log also contains
`CitiesBridge.Bridge` / `CitiesBridge.Ownership` type-load exceptions from a
separate assembly; these precede the post-city error list used by the verdict.
The fixture and native checks pass; that bridge was not investigated or changed.

## 2026-11-10 · Opus 5.5 (blade) · PL-891 · taking turns

**What got in the way.** Waiters polled the lock every 2 s, and whoever
polled first in a gap won. This afternoon PL-891's speed bench waited 88
minutes while runs that arrived after it took the slot five times. `queue`
also showed PL-893's `trial.py`, which imports the harness as a library, as an
unknown holder.

**What changed.** A waiter now registers in the slot's `waiting/` directory
and tries the lock only when no older registered waiter is still alive. That
makes it first come, first served among runs from this checkout on. Older
checkouts don't register, so they can still take a gap until they update.
Files left by dead waiters are removed. `queue` names Python scripts run from a
harness checkout (`script trial.py`), and takes the issue from the most
specific `PL-NNN` in a path (`PL-891-PL-893-test-city` is PL-893).

**Before → after.** Before: the order was a polling race, and one wait ran
88 min. After: oldest first among registered waiters, checked offline with a
live older waiter (deferred), a dead one (cleaned up) and the older one
exiting (proceeds). `queue` now reads "held by script trial.py · PL-893".

## Run log

Per run: host, GPU, peak VRAM (total and game share), peak power and
temperature, wall time, result. Copy the VRAM and GPU lines from `report.md`.

| Date | Agent · issue | Host · GPU | Peak VRAM (game) | Peak W / °C | Wall | Result |
|:--|:--|:--|:--|:--|:--|:--|
| 2026-11-10 | Opus 5.5 · PL-856 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB game | 148 W / 60 °C | 27 min sim (31 min total) | 60 game-min Asheville; rivers drain to 20/62 wet probes |
| 2026-11-10 | Opus 5.5 · PL-856 | blade · 2080 Ti 05:00.0 | 2,414 MiB free before launch | (bench) | 6 min | observer A/B/A: no measurable slowdown; `observe-bench/timelapse.mp4` |
| 2026-11-10 | Sol xhigh · PL-893 trial 1 | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 160.42 W / 63 °C | ~3.0 min | highway elevation rejected; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 trial 2 | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 162.57 W / 63 °C | ~3.9 min | highway elevation rejected; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 trial 3 | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 162.66 W / 63 °C | ~4.3 min | water prefab name rejected; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 trial 4 | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 157.89 W / 63 °C | ~5.0 min | water placement mode rejected; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 trial 5 | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 160.44 W / 63 °C | ~5.0 min | native prefab inspection; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 trial 6 | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 162.10 W / 63 °C | ~7.5 min | power routing rejected; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 trial 7 | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 163.22 W / 63 °C | ~7.3 min | power routing rejected; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 trial 8 | blade · 2080 Ti 05:00.0 | 9,553 MiB (~1,553 MiB game) | 163.25 W / 63 °C | ~3.8 min | menu only after failed rebuild; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 trial 9 | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 157.40 W / 64 °C | ~13.7 min | rail collision diagnosed; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 trial 10 | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 165.44 W / 64 °C | ~6.9 min | rail collision rejected; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 trial 11 | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 157.08 W / 63 °C | ~6.7 min | grew 154, both car paths found, native water node disconnected; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 trial 12 | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 161.86 W / 63 °C | ~5.4 min | grew 153 by 2.05 game-min, utilities working; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 Asheville first proof | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 157.82 W / 63 °C | 4.59 min soak / 6.92 min active | 10 game-min; population 0 → 377; verdict pass; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 Green Plains first attempt | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 155.29 W / 63 °C | ~1.75 min monitored | no hookup found under planner inset; error verdict; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 Green Plains final proof | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 158.62 W / 63 °C | 5.69 min soak / 8.15 min active | 10 game-min; population 0 → 411; verdict pass; clean teardown |
| 2026-11-10 | Sol xhigh · PL-893 Asheville final proof | blade · 2080 Ti 05:00.0 | 10,821 MiB (~2,821 MiB game) | 160.80 W / 63 °C | 6.18 min soak / 8.58 min active | 10 game-min; population 0 → 380; verdict pass; clean teardown |

PL-893 development wall times are the approximate first-to-last GPU sample
span, including boot and teardown. Game VRAM is card peak minus the 8,000 MiB
pre-launch baseline, not a process-isolated peak. The existing 150 W limit was
unchanged; the table reports `nvidia-smi`'s observed transient power peaks.
Active wall time is slot acquisition through completed cleanup, excluding the
queue; soak time is only the simulation loop. Green Plains reported 1280×720
at the menu and the final Asheville run 1920×1080, so these are not controlled
performance comparisons.
