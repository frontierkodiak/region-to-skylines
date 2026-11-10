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
