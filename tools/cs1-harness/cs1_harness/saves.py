"""Save the city at chosen moments (a repro for Caleb, or a checkpoint), and start from a save.

Uses the mod's `save_game` and `load_game` ops (PL-880, PR #10): the game's
own save routine, so a save opens in any copy of Cities: Skylines 1.21. Saves
are copied out of the game's Saves folder into the run's `saves/` and removed
from the game at the end of the session.
"""

from __future__ import annotations

import pathlib
import shutil
import time

from .client import HarnessError

CARBON_SAVES = "~/Library/Application Support/Colossal Order/Cities_Skylines/Saves/"


def has_ops(client, *names: str) -> bool:
    ops = {o["op"] for o in client.call("ops").get("ops", [])}
    return all(n in ops for n in names)


def wait_job(session, reply: dict, timeout: float, what: str) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        session.alive()
        st = session.client.call("job")
        if st.get("job") != reply.get("job"):
            raise HarnessError(f"{what}: expected job {reply.get('job')}, mod reports {st.get('job')}")
        if st["state"] == "done":
            return st.get("result") or {}
        if st["state"] == "failed":
            raise HarnessError(f"{what} failed: {st.get('error')}")
        time.sleep(1)
    raise HarnessError(f"{what}: no result after {timeout:.0f} s")


def save(session, out: pathlib.Path, label: str, why: str) -> dict:
    """Save the running city, copy it to out/saves/<label>.crp, and note how to open it."""
    c = session.client
    if not has_ops(c, "save_game", "job"):
        raise HarnessError("this mod build has no save_game op (it comes with PR #10)")
    paused = c.call("stats")["paused"]
    c.call("run", paused=True)
    try:
        name = f"cs1h-{out.name}-{label}-{time.strftime('%H%M%S')}"
        reply = c.call("save_game", name=name)
        result = wait_job(session, reply, 300, f"save {label}")
        src = pathlib.Path(result.get("path") or reply["path"])
        if hasattr(session, "track"):
            session.track(src)
        elif src not in session.installed:
            session.installed.append(src)
        dest = out / "saves" / f"{label}.crp"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    finally:
        c.call("run", paused=paused)
    frame = c.call("stats")["frame"]
    entry = {"label": label, "why": why, "file": f"saves/{dest.name}", "bytes": dest.stat().st_size, "frame": frame}
    with open(out / "repro.md", "a") as f:
        if f.tell() == 0:
            f.write(
                "# Open this run's saves in your own game\n\n"
                f"Copy a save into `{CARBON_SAVES}` on carbon, then Load Game and pick it. "
                "No mods are needed.\n\n"
            )
        f.write(f"- `{entry['file']}`: {why} (frame {frame}).\n")
    return entry


def load(session, save_file: pathlib.Path, load_timeout: float) -> dict:
    """Start the game from a save instead of a New Game. Returns the status once the city is up."""
    cfg, c = session.cfg, session.client
    if not has_ops(c, "load_game"):
        raise HarnessError("this mod build has no load_game op (it comes with PR #10)")
    saves = cfg.data_dir / "Saves"
    saves.mkdir(parents=True, exist_ok=True)
    name = f"cs1h-from-{save_file.stem}"
    target = saves / f"{name}.crp"
    shutil.copy2(save_file, target)
    session.installed.append(target)
    c.call("load_game", name=name)
    time.sleep(5)
    return c.wait(
        lambda st: st.get("in_game") and not st.get("loading"), load_timeout, "the save to load", alive=session.alive
    )
