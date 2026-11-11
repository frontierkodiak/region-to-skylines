# cs1-harness journal

## 2026-11-11 · PL-857 native resource-bar settlement (OFFLINE)

Instrumented resource-panel PNGs showed an empty ore bar despite correct
metadata, while the strict native panel showed nonzero ore. Replaced blind
three-second capture delay with actual UIProgressBar/value/exponent/target,
zero-icon and animator readback. Three increasing native render frames must
reach all targets and stabilize before screenshot; capture/post-PNG readbacks
must agree. Read-only bars_only polls avoid preview texture instantiation and
never reselect. Explicit same-index select refreshes through native clear/
reselect only (UIListBox otherwise emits no selection event), never fake values.

Optional frozen require_resource_bars=true adds fail-closed numeric settlement
to the existing hash-bound visual review. Old requests stay legacy and report
resource_bars_verified=false; metadata alone cannot satisfy the new contract.
Timeout records last readings/errors and closes the live modal. Writer probes
were not edited. Native rendering still requires a short same-package proof.

64 offline tests pass (13 new, including metadata-correct/ore-zero failure,
native targets/icons/provenance, animation timeout/cleanup and stable capture);
full Ruff checks pass. Installed-assembly compile writes only own
panel-bars-build scratch output, SHA bf5cb2b7a41b167d0901dbf659acd76db30deba4141ce33d6db6e79db27e342b.
Active private DLL58ae33b2… stayed unchanged; no normal build/install, game,
Steam, doctor, service, GPU/inference/session or platform write occurred.
No native acceptance claimed; parent retains PR/build/short native verification.

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

## 2026-11-10 · Opus 5.5 (blade) · PL-891 · the recorder had stopped after its first run

Every PL-891 run tonight had a 0-byte `timelapse.mp4`, and the live page
showed a stale frame. The grabber's ffmpeg writes the timelapse and the live
page's `frame.jpg` in one process. The live page keeps its last frame when a
run ends, so from the second run on, ffmpeg found `frame.jpg` already there,
refused to overwrite it without `-y`, and exited at once, taking the timelapse
with it. The journal said so every time ("File … frame.jpg already exists.
Exiting"). The observer bench worked because it was the first run.

Fix: `-y`. Reproduced with the same output options on a test source: without
`-y`, a 0-byte MP4; with it, a 8.9 kB MP4 and a fresh frame. The smoke run's
comment on PL-891 claimed a timelapse attachment it didn't have.
## 2026-11-10 · Opus 5.5 (blade) · PL-891 · the comment is the wake

The first `submit` smoke run posted its PASS on PL-891 with `--no-wake`, and
that comment alone started the assignee's next run: a member's comment on an
agent's issue wakes the agent. An @mention on top would be redundant and might
start a second run, so `submit` no longer adds `--wake` by default. It's
opt-in (`submit --wake`), and the MCP `submit` tool now defaults to
`wake=False`.

## 2026-11-10 · Opus 5.5 (blade) · PL-891 · how fast can a soak go

**What got in the way.** One Steam account runs one game at a time, so the
slot's speed sets everyone's throughput. The harness never knew whether
drawing frames was slowing the simulation.

**What changed.** A mod op, `render {fps, camera}`, caps the frame rate (or
stops the main camera), and `cs1-harness bench-speed` measures simulation
frames per second at speed 3 with drawing throttled in steps. `run` now caps
drawing at 10 fps between screenshot sets (`--render-fps`, default 10) and
draws at full rate for the screenshots themselves.

**Measured.** PL-848 Asheville on blade's 2080 Ti at 1280×720, 45–50 s per
window:

| Drawing | Sim frames/s | Game CPU |
|:--|--:|--:|
| unlimited | 241.2 | 225 % |
| 10 fps | 239.9 | 114 % |
| 2 fps | 84.5 | 87 % |
| camera off, 2 fps | 84.9 | 73 % |
| unlimited again | 240.0 | 216 % |

Speed 3 is the game's 4× cap, 240 frames a second, and the game holds it at
720p. A 10 fps cap keeps it and halves the CPU. At 2 fps the simulation drops
to about 42 frames per drawn frame, so the cap can go too low. Turning the
camera off adds nothing once the rate is capped. The 157–166 frames/s of
earlier soaks ran at 1920×1080, where drawing held the simulation back.

**Live check** (10 game-minutes of PL-848 Asheville at 1920×1080 with the
default cap, 23:02 ET): 205 simulation frames a second, against 157–166 in
earlier uncapped 1080p soaks. That's 29 % faster, with the cap active and
screenshots still full 1920×1080. (Those screenshots show the game's toolbar,
as every harness screenshot has since the first run: the `ui` op doesn't hide
it. That's a separate issue.)

**Before → after.** Before: unknown, and 1080p soaks ran at about 160
frames/s. After: the ceiling is the game's own 4× (60 game-minutes ≥ 15 wall
minutes), reached at 720p with half the CPU. Going faster than 4× would mean
changing the game's speed table, which the harness doesn't do.
## 2026-11-10 · Opus 5.5 (blade) · PL-891 · agents check their own frame; the playtest checks the world

**What happened.** Caleb's first playtest of "Asheville - Ready to Play"
(7:40–8:05 PM) found two problems that every agent review had missed. The New
Game panel looked broken: no preview, a stranger's name as author, empty
resources. And the map looked rotated about 90°.

**Why we missed them.** Every check we had compared the game with our own
code's frame. The writer's coordinate code placed the probes and drew the water
readback, the terrace check and `water-start.png`. A rotated, mirrored or
transposed map passes all of them. The lead's first answer to "is it
rotated?" was "no". That answer rested on `water-start.png`, which the harness
draws in the writer's frame. None of these checks saw what a player sees.

**What changed.**
- `ground_truth` checks the map against the world. The harness fetches
  elevation itself and projects it with its own code into the game's frame
  (+x east, +z north). It then correlates it with the terrain the game reports,
  in all eight rotations and mirrors.
- `opening_camera` reads the camera's real heading at load. `run` saves the
  opening view and Area Zoom as a player sees them, and `--notify` posts them
  with the New Game panel (PR #8's capture) and the ground-truth image.
- A map soak can no longer report PASS from self-consistent checks alone. With
  no passing `ground_truth` it reports `unverified`.

**First answer.** On the PL-848 Asheville terrain the game reported in
tonight's smoke run, the heights correlate with the real DEM at r = 0.977 as
is. Every rotation or mirror scores 0.38 or less. So the heights reach the game
north-up, and Caleb's sideways view is most likely the opening camera. The
camera heading needs a live run; it's queued behind the playtest hold. The
region's highest point is 58 m lower in game than the DEM's trend predicts,
which looks like smoothing on the peaks. That goes to the writer.

**Before → after.** Before: nine checks, all in our own frame, and a PASS on a
map a person saw as broken in its first minute. After: a PASS needs the world
to agree. Re-judged under the new rule, PL-857's best Asheville soak reads
`unverified` until its probe file names its region. The lesson: an agent's
check is only as independent as the frame it's drawn in. The playtest checked
the world, so now the harness does too.
## 2026-11-10 · Sol xhigh (blade) · PL-857 · hydraulic and native-path evidence

The first arbitrary-region Asheville fixture was not the older two-source
PL-848 map: its 207 sources flooded 0.522 km² more than 128 m from initial or
mapped water in just ten game-minutes (depth >0.5 m). Stream initialization and
lake outlet targets, not just river capacity, mattered. Conservative stream
rates and lake rim limits reduced that to 0.038 km² in the next diagnostic.
The R0 trial also controls the downstream ends of mapped reaches;
its 60-minute saved grids show no water meeting that distant-flood threshold.
Exact-point dry samples are retained separately from nearby wet-channel
evidence. Minor streams are not all perennial.

Added native network inspection and owned car/train path requests, with full
returned lane/segment positions and release on completion. Positive highway
checks pass all 56 segments per direction; deliberately reversed traffic fails.
Rail chunks passed but a full rail path failed at one 108.22° turn. Smoothing
the writer's rail alignment made the complete 173-segment native path pass at
both ends of the R0 Asheville soak. This was a geometry defect, not a
generic pathfinder-probe problem.

Added 64 m neighbourhood water measurements alongside unchanged exact samples,
and session-only daylight for screenshots. Neither changes the exported map.

## 2026-11-10 · Sol xhigh (blade) · PL-857 · ordinary vanilla New Game

`up --game-arg=--disableMods` now skips the mod/socket entirely and returns at
GPU rendering, explicitly not menu readiness. A named private-window X11 helper
captures and drives the actual game; bounds checks reject off-window clicks.
Unity ignored instantaneous button events, so presses now hold for 120 ms.
No Steam prompt is targeted. The existing account-conflict policy is unchanged.

Verified on the R0 Asheville CRP (SHA-256
`4b3d3cd31b3c934b0b6d4a44e6b98d3f39d97f01f40170722b6292c3ce32a390`):
actual arguments `--disableMods --noWorkshop`, absent control socket, main menu
0/0 mods and Workshop inactive, correct ordinary New Game listing, selection,
and a loaded city with the city UI and starter approaches. Only that exact map
was installed. Screenshots and the native load log were retained. The map
preview is black, a remaining cosmetic template limitation. Optional Paradox
auto-login was declined; no account or terms were accepted. Vanilla teardown
terminates its own uninstrumented game instead of waiting for an absent socket;
the resulting game/Steam/unit cleanup lists are all empty.

The display-only `doctor` check now accepts the same `--wait-minutes` slot
queue as `run` and `up`, so verifying a harness PR does not require racing a
long soak. It still starts neither Steam nor the game.

## Run log

Large map checks produced a single Markdown line containing thousands of dry
probe names. The report now shows the full failing count and the first eight
names, pointing to `report.json` for the unchanged full list. This limits
terminal/context output without dropping measurements or changing verdicts.
Checked by rendering the completed R3 Asheville report and retaining its
original JSON bytes and full dry-point array.

PL-857's PR was replayed onto the merged harness on `main` (`8fadee3`),
preserving the observer, verdict, registry and fair queue layers. The older
two-second polling waiters had repeatedly lost gaps to newer work. Only
PL-857's still-queued processes were interrupted and collected; no game or
other user's session was stopped. Their replacements use the registered
first-come-first-served queue. The same map hashes and water policy are used.

Per run: host, GPU, peak VRAM (total and game share), peak power and
temperature, wall time, result. Copy the VRAM and GPU lines from `report.md`.

| Date | Agent · issue | Host · GPU | Peak VRAM (game) | Peak W / °C | Wall | Result |
|:--|:--|:--|:--|:--|:--|:--|
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB incremental | 165.5 W / 63 °C | 20.3 min sim | R3 Rio60 FAIL: 1.652 km² distant flooding, max13.77m; 323/342 playable river points wet end; inputs/controls/native paths pass, cleanup empty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 9,748 MiB card / 1,748 MiB incremental | 158.7 W / 62 °C | 130 s sampled | Strict R3 Rio attempt: actual 1920×1080, no control socket; task driver rejected ordinary What's New header; safe exit before New Game, cleanup empty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB incremental | 163.1 W / 63 °C | 16.3 min sim | R3 prefilled Asheville60: all28 playable river points wet at every sample; no distant flooding; all native paths/inputs/controls; cleanup empty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB incremental | 160.0 W / 63 °C | 17.6 s sim / 230 s sampled | R3 Innsbruck render diagnostic, 1.12 game-min: all six native paths pass; render metadata exercised; zoom-dependent mesh gap retained; cleanup empty |
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
| 2026-11-10 | Opus 5.5 · PL-856 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB game | 148 W / 60 °C | 27 min sim (31 min total) | 60 game-min Asheville; rivers drain to 20/62 wet probes |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB game | 161.9 W / 63 °C | 3.9 min sim | original arbitrary-region: 10 min; flooding; cleanup empty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB game | 160.3 W / 63 °C | 2.7 min sim | conservative: 10 min; reduced flooding, rail failed; cleanup empty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB game | 159.9 W / 63 °C | 16.2 min sim | gap-joining diagnostic: 60 min; rail failed; abandoned; cleanup empty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB game | 166.4 W / 63 °C | 17.7 min sim | R0 Asheville: 60 min; paths pass; no distant flooding in saved grids; cleanup empty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB game | 163.4 W / 63 °C | 16.6 min sim | R0 no-prefill Asheville A/B: 60 min; all28 playable river probes wet by5min and at end; paths pass; cleanup empty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GiB incremental | 169.7 W / 64 °C | 14.3 min session samples | R0 strict vanilla Asheville: ordinary listing, selection and city; no socket; cleanup empty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 8,259 MiB card / ~0.3 GiB incremental | 145.0 W / 62 °C | 50 s sampled | strict Innsbruck startup attempt: driver grayscale/RGB comparison error; safe exit before menu; cleanup empty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB game | 168.9 W / 63 °C | 16.6 min sim | R0 Innsbruck60: all93 major probes have nearby water throughout; exact92/93end, allpaths pass;0.023km2 shallow stream pooling; cleanup empty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti05:00.0 | 10,821 MiB card / ~2.8GB game | 162.6W / 63°C | 8.6min session sampled | R1 failed drain experiment; stopped aftert020; Sill drawdown, source-radius injection; normalquit, cleanupempty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti05:00.0 | 10,821 MiB card / ~2.8GB game | 168.9W / 63°C | 15.7min sim | R2 Innsbruck60: true creek drains verified; pooling reduced97%; long Inn has intermittent drygaps; nativepathsallpass; cleanupempty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti05:00.0 | 10,821 MiB card / ~2.8GB game | 165.9W / 63°C | 16.1min sim | R3 Innsbruck60: all35playable wetend,all455nearbyreadingswet;allpaths;4cellmaxshallowpooling;cleanupempty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti05:00.0 | 10,821 MiB card / ~2.8GB game | 159.2W / 64°C | 15.7min sim | R3 Ashnofill60: all28playablemajorwetby5minandend;nodistantspreading;allpaths;cleanupempty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB incremental | 163.3 W / 63 °C | 120 s sampled | R3 strict Asheville: ordinary city and complete highway, checksum-bound; cleanup empty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 8,099 MiB card / ~0.1 GB incremental | 145.6 W / 63 °C | 45 s sampled | R3 strict Innsbruck first attempt: double-query GPU race; cleanup empty |
| 2026-11-10 | Sol xhigh · PL-857 | blade · 2080 Ti 05:00.0 | 10,821 MiB card / ~2.8 GB incremental | 159.3 W / 64 °C | 321 s sampled | R3 strict Innsbruck: real city verified; UI driver falsely expected a different internal asset name; cleanup empty |

PL-893 development wall times are the approximate first-to-last GPU sample
span, including boot and teardown. Game VRAM is card peak minus the 8,000 MiB
pre-launch baseline, not a process-isolated peak. The existing 150 W limit was
unchanged; the table reports `nvidia-smi`'s observed transient power peaks.
Active wall time is slot acquisition through completed cleanup, excluding the
queue; soak time is only the simulation loop. Green Plains reported 1280×720
at the menu and the final Asheville run 1920×1080, so these are not controlled
performance comparisons.

All runs retained the existing 150 W power limit. Instantaneous telemetry
occasionally exceeded it; no power setting was changed. About 8,000 MiB on the
card belonged to the resident inference replica, which was left untouched.

The R0 A/B used byte-identical terrain and source controls. Final volume was
18.990 M m³ without prefill versus 18.936 M m³ with it (0.3% apart). Both had
28/28 playable river probes wet at the end; without prefill they start 0/28
and reach 28/28 by minute5. Prefill is retained for immediate startup water,
not credited for equilibrium. Comparing spreading against the SAME prefilled
expected footprint, neither run has distant flooding in its saved grids.
Native 64 m neighbourhood fields were exercised live by the no-prefill run.

`doctor --wait-minutes120` acquired a real gap after this soak and passed on
blade's 2080 Ti05:00.0 / egl0, 8,000 MiB existing use of11,264 MiB. No Steam
or game was launched by doctor; its transient display/bus were removed.

The task-local UI driver initially assumed RGB screenshots. ImageMagick emits
grayscale for a black startup frame; normalizing both comparison crops to RGB
fixed that driver error. The harness capture itself was correct. The obsolete
R0 Rio and vanilla waiters were explicitly canceled before launch after the
Innsbruck pooling finding; no other agent/session was touched.

Native source review explained the failed trial: natural sources emit into ALL
lower cells inside their capacity-dependent radius, not just their center.
A below-center-bed target is NOT drain-only. The R2 writer therefore supports
an explicit zero output capacity, keeps small creek withdrawal at0.01, and
omits creek controls within96m of major mapped rivers. These are writer
changes, not a change to native simulation or harness measurements.

R3 adds writer-level river stage controls at fixed2,048m arc intervals,
independent of verification probes: endpoint-only forcing left intermittent
mid-Inn dry gaps once creek spillover was removed. Initial R3samples retain
all35 playable Inn/Sill/Ruetz points wet exactly, without extra distant
spreading beyond the tiny known creek pool. Full five-region qualification
remains pending. The completed R3 Innsbruck run retained all 35 playable
major-river probes wet at the end, with nearby water throughout; four shallow
creek-pooling cells remain.

A staging-camera error was caught before publishing evidence: shallow creek
initialization changed Asheville's selected tile17to11, but copied camera
coordinates still aimed at the old start. The writer's soak driver now binds
that view to the candidate's actual landing. Only the queued old-view run was
canceled; the replacement uses the SAMECRP bytes and corrected camera.

A live strict Innsbruck startup exposed a placement-check race: launch queried
GPU processes twice, saw a process first, then an empty transient registration
on the second query, and incorrectly failed as software rendering. Reusing
one observed snapshot fixes that inconsistency; wrong-GPU checks remain.
The failed attempt cleaned up fully and was archived separately before retry.
The observed GPU processes are also intersected with live game PIDs so stale
registrations cannot certify a new launch. The retry rendered the complete
Innsbruck starter highway in an ordinary vanilla city. The task-local UI
driver then falsely timed out because it expected a region-labelled internal
asset name. Native names are opaque template identifiers; reading kind 52
from the installed checksum-bound CRP fixed that assumption. Screenshots and
the real native load line independently verify the city. Both attempts
cleaned up. The queued display-only doctor passed on 05:00.0 / egl0.

Added read-only network snapshots at path-check endpoints: native bounds,
segment/node flags and matching render parts/LOD metadata. This investigates
highway meshes absent only in a wide harness camera while native paths and
the normal vanilla view remain intact. It changes no map or simulation state.

## 2026-11-10 — PL-857 opt-in New Game panel check (offline)

Added frozen probe expectations for native NewGamePanel listing, package
author/buildable/resource/connection values and resolvable snapshot + Steam
preview textures. Driver selects the native modal and captures its rendered
selection; verdict requires separate hash-bound visual review and fails while
unreviewed. No synthetic image or package-only success counts as a panel pass.
Strict disableMods verification is unchanged. Offline: built against installed
game assemblies; eleven verdict fixture tests and Ruff lint/format checks passed.
No game, Steam, doctor, display or GPU session started: Caleb's reservation
remained held. Native modal operation/rendered capture still need live checks
after the hold; GPU/VRAM/power/temperature/run-wall metrics are not applicable.

PL-857 offline review follow-up: capture now polls up to30s for a verified,
decodable native PNG, hashes those exact validated bytes, and fails immediately
on explicit false liveness (or Session.alive's normal exception); dead bridges
are not called just to dismiss the modal. Four additional tests cover death,
partial-to-complete writes, timeout and float-only denominator tolerance (15
passing total). Only maxResourceAmount gets rel1e-7/abs1e-6 comparison slack.
Native Package.cs:946-962 deserializes each Instantiate; PackageDeserializer.cs:
243-257 calls Image.CreateTexture, which constructs a fresh Texture2D at
Image.cs:279-284. CacheAsset caches bytes, not texture objects; destroying the
private inspection texture cannot destroy the displayed snapshot. Offline build
and full Ruff checks passed again; no game/session/Steam actions.

## 2026-11-10 — PL-857 native landmark and camera observations (offline)

Added read-only world_observe op: native SampleRawHeightSmooth heights plus
interpolated/current target/render camera vectors and AreasVisible. Map runs
freeze startup-world before any harness camera/run overrides; explicit frozen
landmark expectations give a fail-closed terrain_landmarks verdict. References
must be independent DEM/known landmark coordinates, not prepared-grid roundtrips;
no geography or expected heights were invented and no terrain/camera mutated.
Native source confirms x contiguous/z rows at[z*1081+x], world/16+540, height/64;
Area Zoom snaps current right-vector to a cardinal camera override. SavedCamera
mode2 matches NewGameFromMap; normal mode3 matches LoadGame, not NewGame.
Offline installed-assembly build and full Ruff lint/format passed; nine new
meaningful fixture checks (24total) cover height mismatches, swapped probes,
missing evidence, invalid expectations/camera/phase and read-only capture.
No Steam/game/doctor/session/lock actions. Actual old/new package orientation,
startup/Area Zoom headings and any serialized camera change remain unverified
until live sampling after Caleb's held slot. No GPU/run metrics applicable.

PL-857: the frozen absolute-height request now uses `landmark_expectations`,
leaving PR #22's geographic `ground_truth`/landmark contract unambiguous.
The two checks are complementary: fixed GNIS/DEM absolute samples and
independently fetched whole-map orientation. No map or camera is changed.

## 2026-11-10 22:36 ET — PL-857 post-reservation attempt (Steam blocked)

Blade / RTX 2080 Ti 05:00.0 / egl0: the exact Asheville north-camera
candidate (`3013a635…886b15`) was installed, but Steam reported
`KickingOtherSession` after 35 s. No prompt was answered and no game started.
The session receipt confirms empty game, Steam and unit cleanup. Peak sampled
VRAM was 8,000 MiB total (the pre-existing baseline; no game allocation),
power 63.17 W and temperature 28 C; the 150 W limit was unchanged. Output:
`PL-857-sustained-water/native-north-smoke/asheville`. Only this attempt's
retry-sleep child was terminated after cleanup; its exit 143 was collected by
the foreground soak driver (exit 1). The next attempt will use a persisted Multica wakeup at least 30 minutes
after the account conflict, not an orphaned run-owned sleep. Panel, landmarks,
startup/Area Zoom camera and five-region final-package acceptance remain unrun.

## 2026-11-10 — Sol xhigh · PL-857 actual startup/Areas views (OFFLINE)

Added opt-in frozen `startup_views` expectations for native interpolated yaw
and render heading. Driver records the un-aimed opening and actual Areas-tool
PNG/readbacks after startup-world and before harness camera overrides. Core's
new `area_zoom` op selects GameAreaTool/DefaultTool, matching the normal native
toolbar; it never writes camera fields. Native AreasVisible is required, not
maximum camera zoom. Three stable readings, complete decoded PNGs, capture
identity/frame/dimensions/hashes, initial startup identity and finally-close
evidence gate the verdict; screenshot-content claims require separate hash-bound
visual review. WorldOps and geographic/landmark contracts remain unchanged.

Offline: installed-game assembly build succeeded in a private
`start-view-cache` (no shared active DLL changed); 38 tests passed, including
14 new mocked cases for wrong native/render headings, fake max-zoom mode,
failure cleanup, evidence/PNG identity, missing review and valid observations.
The driver-order test verifies capture follows startup-world before any run or
camera override.
Ruff lint/format checks passed. No Steam/game/doctor/session/display/lock
actions, no GPU use or native captures; VRAM/power/temperature/game-run wall
metrics do not apply. Actual tool transitions, headings, screenshots and native
cleanup are **not verified** and await the integration owner's live run.

## 2026-11-10 23:23 ET — PL-857 first panel trial and native hierarchy fix

Blade / RTX 2080 Ti 05:00.0 / egl0 launched the exact Asheville camera
candidate (`3013a635…886b15`) after a 15.6-minute fair-queue wait. The map was
listed, but the panel op failed before city load: it looked for NewGamePanel
on the library root, which actually has NewGameMainPanel. The map-list
controller is a child of its Maps tab. Resolve that unique child and activate
the native TabChooseMap button rather than treating the modal root as the
listing. Installed-assembly build passes; the corrected native operation still
needs a live retry. Startup and Areas instrumentation is integrated but remains
unverified in game.

GPU samples span 55.1 s: peak 9,584 MiB total (1,584 above the 8,000 MiB
baseline), 83.86 W and 41 C; power limit remained 150 W. Output:
`PL-857-sustained-water/native-north-smoke-retry-2307/asheville`. Game and
units were gone at cleanup, but its receipt still listed one Steam instance;
do not call that an empty cleanup or terminate another queued session to fix
it. The next successful retry must check cleanup again. No city, landmark,
camera, water or screenshot acceptance came from this failed trial.

## 2026-11-10 — Sol xhigh · PL-857 harness rebase (OFFLINE)

Rebased exact `6027240853e0bcf013e50ae6f5ee24ff832e3b74` onto exact main
`e971c27d8b5e3a7650d945c43c7081611ceee124` in an isolated worktree. Ten local
commits were replayed as Polli Agent; no active source/cache, session, Steam,
game, doctor, slot, Multica or remote GitHub state was changed.

Conflict decisions retain both main's test-city scenario hooks and PR8's
paths/network snapshots, main's render cap and native camera-state op alongside
actual Areas controls, and all journal text/rows from both histories. CLI keeps
both path requests and render-fps configuration. Native panel/root-child
selection remains before new_game. Immediately after city load, startup-world
and native landmark sampling run first, actual startup/Areas evidence second,
then run/daylight, scenario, legacy player-path and render/camera overrides.
Main's independent groundtruth implementation and 40x40 native-world sampling
remain intact; frozen landmark_expectations stays separate from geographic
ground_truth/landmarks. No writer or rotation-sign logic was changed.

Legacy player-area-zoom filename/notifications remain compatible, but docs now
identify it as maximum camera size, never actual GameAreaTool evidence. The
actual Areas check still requires native tool/mode receipts and hash-bound
visual review. Added offline integration coverage for panel-before-new_game,
startup-before-scenario ordering and the 1600 native world-sample points.

Offline gates: all 47 unittest fixtures pass; full Ruff check and format check
pass. Installed-game assembly build succeeds in separate `rebase-cache`, DLL
SHA-256 `58ae33b2ba9877ba1d38f385b932de94a07f4d6fbda2ed7f52723d51bb859906`.
This is not native validation. Tool transitions, rendered views, combined
scenario/render behavior and actual geography/heading acceptance still need
live checks. GPU/VRAM/power/temperature/game-run wall metrics do not apply.

## 2026-11-10 23:33 ET — PL-857 native panel, landmarks and actual Areas proof

On blade's RTX 2080 Ti 05:00.0 / egl0, `native-start-ui-trial/asheville`
loaded exact CRP `3013a635…886b15` using pre-rebase harness `6027240` and
DLL `11bc5cd9…`. After genuine hash-bound screenshot review, panel, four
landmarks and startup_views pass. Both native yaw and render heading are0°
in the untouched opening and actual GameAreaTool view; AreasVisible changes
false → true → false. Landmark errors are -1.605, -0.335, -0.925 and -1.629 m
against the independent GNIS/DEM references (12 m tolerance). The native panel
resolves both preview sizes, hides the blank author, and shows70% buildable.
This candidate's resource crosses remain intentional/unpainted, not completion
of PL-902. Source view has a Hello tutorial overlay; it is not a marketing shot.

The short diagnostic reached1.1314 game-minutes in19.78 simulation wall seconds,
not60minutes. All28 playable major-river probes stayed exactly wet, all six
path checks passed, initial terrain/water/source controls matched, distant
spreading was0 and cleanup was empty. Peak VRAM10,821 MiB total /2,821 above
baseline, power123.98 W, temperature57 C;150 W cap unchanged. This proves
the camera correction and panel operation on this exact package, not all five
regions' final water/resource qualification.

## 2026-11-10 23:40 ET — PL-857 R4 Rio60 remains a rejected policy

`r4-north-rio-60/rio`, exact CRP `e1844ef2…e7bd`, same blade GPU/pre-rebase
harness, completed60.0289 game-minutes in932.49 simulation wall seconds.
All initial inputs/controls matched; native full car/train paths passed at
both ends; cleanup was empty. Playable major rivers ended337/342 exactly wet;
five had an exact miss and one had a no-water-within64m sample. Distant
spreading (>0.5m, >128m from initial/mapped water) reached0.377600 km²;
peak distant depth4.453125m at45minutes. That is an improvement over R3's
1.651968 km², but still fails flooding acceptance. Normal exit is not a pass.
Peak VRAM10,821 MiB total /2,821 above baseline, power129.05 W and59 C;
150 W cap unchanged. Numeric audits retain all failures and native views.

Prepared, not yet executed: matched15-minute no-emission and sea-only-initial-
water ablations. They separate spill from initial fill versus continued source
head before another policy change. R4 has175 river regulators (all bank-limited),
up from51 in R3; summed output/intake capacities are31.24/14.99 versus22.2/22.2.
This is a diagnostic, not proof that capacity alone caused the spill.

The legacy PL-848 example now uses Cartesian rotation+0.905, from its original
`water-geometry.json` browser rotation-0.905. The actual native terrain dump
and Caleb-save decoded terrain are byte-identical (`293d639f…ad6b6`); their
independent DEM comparison at the correct frame scoresr=.9999 as-is. The
new PL-857 capture isrotation0 and remains unchanged. This correction is not
a new live sampler/camera operation on the legacy save.

## 2026-11-11 00:29–00:50 ET — resource/coastal qualification queued

Active harness `efd6177` uses the rebased main native sampler and prior real
New Game/startup/Area Tool checks. DLL SHA-256 is
`58ae33b2ba9877ba1d38f385b932de94a07f4d6fbda2ed7f52723d51bb859906`.
Private-cache doctor passed on EGL0 / PCI05:00.0 with baseline8,000 MiB;
the150 W cap, inference placement, shared checkout and shared cache are unchanged.

Foreground jobs (all pending, **not acceptance**): `resources-north-asheville-60`
uses resource-painted CRP `be8b2482…f3cc3`; `resources-three-60` queues Innsbruck
`5859e371…2495b`, Pittsburgh `1acdfbb9…32f8d` and corrected-coast Charleston
`3d6443ff…56fba` individually for60 game-minutes. Compound writer PR27 preserves
PR24 resource algorithms/defaults and the current north-facing camera. Its
capture-only ocean correction is described in `COAST_EVIDENCE.md`; website and
installer stay unchanged. Frozen plans are replayed, never silently replanned
at launch. `strict_resource_batch.py` separately queues ordinary New Game starts
for all five exact packages, with `--disableMods --noWorkshop`, no control
socket, known UI anchors, actual internal asset names and own-session cleanup.
No selected/city screenshot has yet been reviewed for these resource packages.

`rio-coast-noemit-15` queues a labelled15-minute diagnostic at `639d6213…82fe3`,
derived from corrected-coast resource Rio `bc1045d2…bd137`. It changes only
natural-source output to0 and retains intake/targets/terrain/prefill. Matching
sea-only-prefill arm `0258cd92…dd6143` is prepared, not yet queued. These test
initial-fill escape versus continued emission before another capacity/stage
change. They are not release candidates and inherit no R4 acceptance.

Independent **offline** DEM checks on corrected prepared terrain score Rio
r=.9978 and Charleston r=.6893; Charleston remains a failure, not a reason to
lower thresholds. Charleston's captured raw DEM agrees at r=.9988 with the
independent zoom14 fetch but only r=.8256 with the checker's zoom13 fetch;
modified game terrain still scores only r=.7503 at zoom14. Restricting the
check to DEM land also fails. These observations are retained pending native
sampler/height and terrain-modification diagnosis; no exclusion mask or
automatic pass was added. All registered jobs wait fairly and answer no Steam
prompt. Inferred parent-script entries in `queue` are display-only: inspecting
the actual wait tickets ruled out the suspected parent/child FIFO deadlock.

## 2026-11-11 00:57 ET — neutral pointer before native startup observation

Resource Asheville's panel now genuinely shows the two previews, hidden blank
author and nonempty forest/fertile/ore/oil/water bars (buildable73%). Its
opening native/render yaw remains0, but position drifts to the start tile's
north-west corner while paused. Read-only X11 inspection found the pointer at
root(160,90), exactly the upper-left of the1600×900 Cities window positioned
at(160,90) in the1920×1080 private root. This triggers ordinary edge panning;
it is not evidence for a serialized grid/camera rotation.

`Session.launch` now parks the pointer at the private root centre after the
game is observed, before any New Game operation. It requires the owned slot,
refuses display:0, sends no key/click, and records the position in the receipt.
No camera position/heading is forced. Existing queued Python processes retain
their already imported source; the currently running60-minute water check is
not altered. A fresh short startup check must verify centring and stable
position on the same package before that claim is made. All47 unit tests and
whole-harness Ruff pass; this pointer correction is not yet live-verified.

The frozen startup request also supports explicit `opening_center` world x/z
and metre tolerance. It checks both observed current and target pivots after
capture, not just heading. A regression fixture reproduces the actual corner
drift and must fail despite yaw0. All48 tests pass. Writer PR27 now emits the
selected start-tile centre with64m tolerance for newly staged runs. Existing
frozen requests are not edited retroactively and make heading-only claims.

## 2026-11-11 01:11 ET — painted Asheville60 completed

`resources-north-asheville-60/asheville`, exact CRP `be8b2482…f3cc3`, completed
60.0731 game-minutes /932.74 simulation wall seconds. Native initial grids and
all source controls match. All28 playable major rivers and59 nonboundary
rivers are exactly wet in all13 samples. Two physical-edge river misses remain;
streams are not all perennial (837/1527 playable stream probes end exact wet).
All saved0/15/30/45/60 grids show0 distant spread. Six full car/train paths and
empty cleanup pass; its own game ignored graceful quit and was terminated by
normal owned-session teardown, not by touching another session.

Independent grid and native1,600-point terrain checks both passr=.9999;
best wrong native transform.3727. Four GNIS/DEM landmark errors are−.335 to
−1.629m. Actual panel and real Areas/opening images were manually inspected,
hash-bound and reviewed. Panel has preview/blank author/resources/73% buildable;
heading0 in opening and actual Areas; the drifted opening is explicitly **not**
centred-camera acceptance. Native verdict passes its frozen heading-only
request; no extra centring claim is inherited. `resources-neutral-pointer-
asheville-1` queues the same exact CRP with new64m centre expectation. Matching
Rio nofill15 arm `rio-coast-nofill-15` is also now queued; both remain foreground.
Peak memory10,821 MiB /2,821 above8,000 baseline;136.59 W,54°C,150 W unchanged.

## 2026-11-11 01:17 ET — corrected-coast Rio no-output diagnostic

`rio-coast-noemit-15/rio`, CRP `639d6213…82fe3` from `bc1045d2…bd137`, completed
15.0133 game-minutes. All initial grids and controls match; all natural output
rates are0, with intake/positions/targets retained. Both saved grids have0
distant spill, but only94/342 playable river probes end exact wet, with169
having no water within64m in a sample. Removing supply is not a sustainable
default. This does not by itself prove the continuing-source cause on the new
coastal input: matched source-on/no-prefill and full `resources-coast-rio-60`
baseline (same exact `bc1045d2…bd137`) are queued. Both full native path sets
pass and cleanup is empty; peak10,821 MiB total,139.07 W,52°C. Panel/Areas PNGs
are not reviewed for this rejected diagnostic, and its verdict correctly fails.

## 2026-11-11 01:48 ET — first-attempt FIFO bypass reproduced and fixed

The strict five-map batch repeatedly acquired a just-free lock before older
registered waiters reached their next2s poll. This is different from the
inferred-parent display concern ruled out above. `slot()` consulted older
tickets only after its own first busy result, so a fresh process could cut in.
An isolated regression with a free synthetic Session and older live-PID ticket
failed on8ccb2f4 (`Blocked not raised`), without touching host locks/services.
All entrants now register before their first attempt; busy reason updates do
not reset queue age. No-wait entrants cannot jump an older ticket. Three
isolated tests also cover uncontended acquisition and preflight-failure cleanup.
All51 tests and whole-harness Ruff pass. Existing processes retain imported
source; the fix affects fresh invocations, not someone else's current session.

The exact current five-map strict batch finished ordinary New Game/city starts
with `--disableMods --noWorkshop`, absent control socket, checksum-bound sole
custom map and empty named-session cleanup. Actual selected/city PNG visual
reviews remain pending; they are not automatically marked reviewed.

## 2026-11-11 02:16 ET — phase-specific outcomes and panel-review correction

All ten strict selected/city PNGs have now been inspected and hash-bound in
`strict-resources-coast-<slug>-review.json`. All five exact packages show their
own preview, blank author, populated resources and ordinary city HUD with no
Map Editor; actual launch flags/socket absence and empty cleanup are checked.
Buildable scores are73/75/73/79/58 (Asheville/Innsbruck/Rio/Pittsburgh/Charleston).
The test typed `pl857-<slug>` into the editable city field for identification;
that is not evidence for a supported metadata city-name default.

Painted Innsbruck60 completed60.0122 game-minutes:34/35 playable major probes
end exactly wet,35/35 have nearby water in all455 native observations. The
Sill point(192,-2112) has an exact miss with1m water16m away; it is retained,
not relabelled exact wet. Nonboundary rivers end89/90 exact wet; all have nearby
water throughout. Maximum distant extent is0.001024km², maximum depth0.671875m
(a few shallow cells, not zero). Inputs, six paths, cleanup and native1,600-point
DEM comparison pass (r=1.0000, strongest wrong.4728). Actual opening/Areas
images are reviewed; opening pivot(1920,0), headings0.

`resources-neutral-pointer-asheville-1` confirms same-package `be8b2482…f3cc3`
current/target pivot exactly(-1920,0) before/after opening capture, native/render
yaw0, actual Areas yaw0 and empty cleanup. Explicit64m centring check passes.

**Review correction:** comparing strict vanilla versus instrumented Asheville
showed the latter's ore bar captured visually empty despite positive metadata.
Both instrumented Asheville panel reviews now set `resources_match:false`;
rejudged verdicts fail only `new_game_panel`, retaining valid physics/geography/
camera findings. The old3s sleep is not settled-UI proof. A disjoint helper
change will read actual bar values/targets/animation state and wait boundedly;
fresh same-package panel proofs are required. No image was replaced/blessed
and no map bytes changed to conceal this capture problem.

Corrected-coast Rio full baseline `bc1045d2…bd137` still fails:60.1289 minutes,
336/342 playable exact end wet, all4,446 native nearby readings wet, but0.353024
km² distant spread (up to4.328125m). Its matching no-land-prefill15 arm reaches
0.332032km²/4.140625m, identical extent to prefilled baseline at15minutes;
no-output arm remains0. Sustained forcing, not startup fill, drives this spill.
`rio-coast-shallow-head-15` is queued at CRP `31ff92e5…97851`: only173 bank-
limited source targets cap at1m above finished local grid bed; both rates,
positions, terrain, prefill and frozen resource plan remain exact. Diagnostic,
not a release policy. All tests/runs remain foreground and fair queued.

## 2026-11-11 02:40 ET — observable bars build and cold-modal protocol

The resource-bar observer at9618f9c independently passes64 tests, whole Ruff,
format and native compile. Private-cache DLL is
`bf5cb2b7a41b167d0901dbf659acd76db30deba4141ce33d6db6e79db27e342b`;
fresh same-package Asheville1 is fair queued, not yet evidence of rendering.
PL-902 reported its older dfe3e03 probe checking modal visibility on the same
call that opened it. Selection now returns an explicit pending phase while
the native modal or Maps tab is not visible. Python polls only that explicit
state, records every selection reply and times out boundedly; absent maps,
other errors and dead games are not retried as UI readiness. Two synthetic
protocol tests bring the suite to66. This additional cold-modal change has
not yet been compiled into the private cache or exercised live.

Painted Pittsburgh `1acdfbb9…32f8d` completed60.0164 minutes with all79
playable river probes exactly wet throughout, all216 nonboundary rivers
exact wet at end and all native nearby observations wet. Inputs/controls,
six paths, cleanup and independent terrain comparison pass (r=.9992,
strongest wrong.2436). Original first-water-only flood verdict flags2.165km²;
the separately defined audit (initial water union actual mapped waterways)
finds0 deep water beyond128m. These are different references, not equivalent
results. A hash-bound optional corridor-reference verdict is being prepared;
the historical frozen probes/verdict are preserved. Actual panel/opening/
Areas images have been viewed; review receipts are pending transcription.

## 2026-11-11 — explicit mapped-water flood reference (OFFLINE)

`PL-857-water-corridor`, based on `9618f9c`: optional hash-bound binary mapped
water footprint is validated/frozen before session acquisition and unioned with
the legacy initial/reference grid for saved-grid flooding. Existing Euclidean
128m distance, >0.5m depth and 0.05km² allowance unchanged; legacy initial-only
result retained as non-gating diagnostic, no automatic mask creation/widening.
Missing/changed/malformed requested masks fail closed. Read-only supplemental
adjudication binds historical report/probes/reference/grids and external mask
without editing frozen artifacts. Synthetic fixtures cover channel extension
versus distant spill, boundaries, corruption, freeze isolation and legacy mode.
72 offline unittests pass; full harness Ruff check/format and diff check pass.
No native code/cache, game, shared services, writer or website changes. No
Pittsburgh/Rio acceptance claimed. GPU/VRAM/power/temperature/native wall time:
not applicable; native build/doctor/run intentionally not performed.
