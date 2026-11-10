# cs1-harness is a shared tool

Any agent that uses this harness owns improving it. If it gets in your way
(slow boot, an unclear failure, a missing check, a command you had to
improvise), fix it in a normal PR on this repo. No one needs to sign off on
that beyond ordinary review. Then add an entry to [JOURNAL.md](JOURNAL.md).

Limits that still hold:

- No security or access changes: groups, ACLs, tokens, sandbox or permission
  settings, `sudo`. The harness exists because it works without them.
- No purchases.
- Shared host services change only through the `configs` repo. The harness's
  own transient `systemd --user` units are not shared services.
- Caleb's Steam account comes first. Launch through Steam (`-applaunch`) and
  never start a game during a window he has reserved. If Steam says the
  account is in use, stop and retry later; never pick "play here". The
  harness itself answers no prompt.
- Terms that reappear only because a host is a fresh install (a game's EULA in
  Steam, the Paradox Launcher's user agreement) may be accepted by an agent.
  Caleb has already accepted them on his account and gave broad clearance on
  2026-11-10 (PL-856). That clearance doesn't cover purchases, Workshop
  publishing or new accounts. Harness runs start `Cities.x64` directly, so the
  Paradox Launcher doesn't appear in them anyway.
- Nothing runs after you finish: `cs1-harness down` leaves no game, Steam,
  display or bus behind, and says so.

## Layers

Keep these separate. Map checks are one tool on top of a general game session.

| Layer | Python | Mod | Use |
|:--|:--|:--|:--|
| Session: display, bus, Steam, launch, teardown | `session.py`, `config.py`, `setup.py` | `Harness.cs` (socket, op registry) | everything |
| General control | `client.py`, `up` / `call` / `down` | `CoreOps.cs` (status, run, camera, ui, screenshot, quit) | everything |
| Map checks | `mapcheck.py`, `report.py`, `run` | `CityOps.cs` (maps, new_game, stats, water, dump) | generated-map QA |

To add a capability, add an ops module to the mod: a static class with
`Register()`, called from `Host.Awake`. Give each op a `Needs` level and one
line of help, so `call ops` describes it. Put its Python driver in its own
module. An Asset Editor mode for prompt-to-asset work (CSUR-RoadImporter
style: load the editor, import, save `.crp`) belongs here as `EditorOps.cs`
plus a driver, not inside the map check. An MCP server should wrap `up`,
`call` and `down`, and nothing else.

## Each run

Add a line to the run log in [JOURNAL.md](JOURNAL.md): host, GPU, peak VRAM
(total and the game's share), peak power and temperature, wall time and
result. The 2080 Tis are capped at 150 W; never change power settings.

## Before a PR

- `uv run cs1-harness build` compiles against the installed game.
- `uvx ruff check . && uvx ruff format --check .`
- `uv run cs1-harness doctor` passes.
- When you touched the session or mod, run something in game (`up`,
  `call status`, `down`) and say in the PR what you ran.
