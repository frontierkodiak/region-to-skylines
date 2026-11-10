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

### Run log

Per run: host, GPU, peak VRAM (total and game share), peak power and
temperature, wall time, result. Copy the VRAM and GPU lines from `report.md`.

| Date | Agent · issue | Host · GPU | Peak VRAM (game) | Peak W / °C | Wall | Result |
|:--|:--|:--|:--|:--|:--|:--|
