"""Who holds this host's harness slot, who is waiting, and how contended it is.

One Steam account runs one game at a time, so the slot is the scarcest thing
the harness has. `cs1-harness queue` shows the holder (its issue, label and
ETA) and every waiter, including runs started by older harness checkouts,
which it finds from their command lines. Every wait, acquisition and release
is appended to `slot.jsonl` beside the run registry; `queue --stats` sums it,
as evidence for or against a second Steam account.
"""

from __future__ import annotations

import json
import os
import pathlib
import statistics
import time

from . import registry

LOG = registry.REGISTRY.parent / "slot.jsonl"
COMMANDS = ("run", "up", "doctor", "bench-observe", "asset")
DEFAULT_WALL_PER_GAME_MINUTE = 0.3  # blade's 2080 Ti at speed 3: 60 game-min in 16-27 wall min
BOOT_MINUTES = 3.0  # Steam, menu, city load and teardown


def log_event(event: str, **data):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps({"t": time.time(), "event": event, "pid": os.getpid(), **data}, default=str) + "\n")


def holder_file(cfg) -> pathlib.Path:
    return cfg.runtime_dir / "holder.json"


def waiter_dir(cfg) -> pathlib.Path:
    return cfg.runtime_dir / "waiting"


def wall_per_game_minute() -> float:
    """Median wall minutes per game-minute over registered map runs."""
    rates = []
    for r in registry.load():
        m = r.get("metrics") or {}
        if m.get("game_minutes") and m.get("wall_minutes") and m["game_minutes"] >= 5:
            rates.append(m["wall_minutes"] / m["game_minutes"])
    return statistics.median(rates) if rates else DEFAULT_WALL_PER_GAME_MINUTE


def eta_minutes(meta: dict) -> float | None:
    if meta.get("command") == "run" and meta.get("game_minutes"):
        return round(BOOT_MINUTES + meta["game_minutes"] * wall_per_game_minute(), 1)
    if meta.get("command") == "doctor":
        return 0.5
    return None


def describe(meta: dict) -> dict:
    return {k: meta.get(k) for k in ("command", "label", "issue", "out", "game_minutes")}


def mark_waiting(cfg, meta: dict, reason: str):
    waiter_dir(cfg).mkdir(parents=True, exist_ok=True)
    (waiter_dir(cfg) / f"{os.getpid()}.json").write_text(
        json.dumps({"pid": os.getpid(), "since": time.time(), "reason": reason, **describe(meta)})
    )
    log_event("wait", reason=reason, holder=holder(cfg), **describe(meta))


def mark_acquired(cfg, meta: dict, waited_s: float):
    (waiter_dir(cfg) / f"{os.getpid()}.json").unlink(missing_ok=True)
    eta = eta_minutes(meta)
    info = {"pid": os.getpid(), "since": time.time(), "eta_minutes": eta, **describe(meta)}
    holder_file(cfg).write_text(json.dumps(info))
    log_event("acquire", waited_s=round(waited_s, 1), eta_minutes=eta, **describe(meta))


def mark_released(cfg, meta: dict, held_s: float, detached: bool = False):
    if not detached:
        holder_file(cfg).unlink(missing_ok=True)
    log_event("detach" if detached else "release", held_s=round(held_s, 1), **describe(meta))


def mark_gave_up(cfg, meta: dict, waited_s: float, reason: str):
    (waiter_dir(cfg) / f"{os.getpid()}.json").unlink(missing_ok=True)
    log_event("give_up", waited_s=round(waited_s, 1), reason=reason, **describe(meta))


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def lock_pid(cfg) -> int | None:
    """The process holding the slot's flock, from /proc/locks."""
    try:
        ino = cfg.lock_file.stat().st_ino
    except OSError:
        return None
    for line in pathlib.Path("/proc/locks").read_text().splitlines():
        parts = line.split()
        if len(parts) > 5 and parts[1] == "FLOCK" and parts[5].endswith(f":{ino}"):
            return int(parts[4])
    return None


def harness_processes() -> list[dict]:
    """Every cs1-harness command running on this host, from /proc."""
    found = []
    for d in pathlib.Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            argv = (d / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        argv = [a.decode(errors="replace") for a in argv if a]
        if len(argv) < 2 or "python" not in pathlib.Path(argv[0]).name:
            continue
        joined = " ".join(argv)
        if "cs1-harness" not in joined and "cs1_harness" not in joined:
            continue
        cmd = next((a for a in argv[1:] if a in COMMANDS), None)
        if cmd is None:
            continue
        opts = argv[argv.index(cmd) + 1 :]

        def opt(name):
            return opts[opts.index(name) + 1] if name in opts and opts.index(name) + 1 < len(opts) else None

        found.append(
            {
                "pid": int(d.name),
                "command": cmd,
                "label": opt("--label") or opt("--name"),
                "issue": opt("--issue"),
                "out": opt("--out"),
                "game_minutes": float(opt("--game-minutes")) if opt("--game-minutes") else None,
                "checkout": str(pathlib.Path(argv[0]).parents[2]) if len(pathlib.Path(argv[0]).parents) > 2 else None,
                "started": d.stat().st_mtime,
            }
        )
    return found


def holder(cfg) -> dict | None:
    pid = lock_pid(cfg)
    info = None
    if holder_file(cfg).exists():
        with_file = json.loads(holder_file(cfg).read_text())
        if alive(with_file.get("pid", -1)) and (pid is None or pid == with_file["pid"]):
            info = with_file
    if info is None and pid is not None:
        proc = next((p for p in harness_processes() if p["pid"] == pid), {"pid": pid})
        info = {**proc, "since": proc.get("started"), "eta_minutes": eta_minutes(proc)}
    if info is None and cfg.state_file.exists():
        state = json.loads(cfg.state_file.read_text())
        info = {"command": "up (detached)", "label": state.get("label"), "since": state.get("started"), "pid": None}
    if info and info.get("issue") is None:
        info["issue"] = registry.issue_of(
            pathlib.Path(info.get("out") or info.get("checkout") or ""), {"label": info.get("label")}
        )
    return info


def status(cfg) -> dict:
    h = holder(cfg)
    waiting = []
    files = {}
    if waiter_dir(cfg).exists():
        for f in waiter_dir(cfg).glob("*.json"):
            w = json.loads(f.read_text())
            if alive(w["pid"]):
                files[w["pid"]] = w
            else:
                f.unlink(missing_ok=True)
    for p in harness_processes():
        if h and p["pid"] == h.get("pid"):
            continue
        w = files.pop(p["pid"], None) or {**p, "since": p["started"], "reason": "(older harness; inferred)"}
        if w.get("issue") is None:
            w["issue"] = registry.issue_of(
                pathlib.Path(w.get("out") or w.get("checkout") or ""), {"label": w.get("label")}
            )
        waiting.append(w)
    waiting += list(files.values())
    now = time.time()
    if h:
        h["held_minutes"] = round((now - h["since"]) / 60, 1) if h.get("since") else None
        if h.get("eta_minutes") is not None and h["held_minutes"] is not None:
            h["remaining_minutes"] = round(max(0.0, h["eta_minutes"] - h["held_minutes"]), 1)
    for w in waiting:
        w["waiting_minutes"] = round((now - w["since"]) / 60, 1) if w.get("since") else None
    return {"holder": h, "waiting": sorted(waiting, key=lambda w: w.get("since") or 0)}


def stats(since_hours: float = 24.0) -> dict:
    """Contention over the window, from slot.jsonl."""
    if not LOG.exists():
        return {"events": 0}
    cut = time.time() - since_hours * 3600
    ev = [json.loads(line) for line in LOG.read_text().splitlines() if line.strip()]
    ev = [e for e in ev if e["t"] >= cut]
    acq = [e for e in ev if e["event"] == "acquire"]
    waited = [e["waited_s"] for e in acq if e.get("waited_s", 0) > 5]
    gave_up = [e for e in ev if e["event"] == "give_up"]
    held = [e["held_s"] for e in ev if e["event"] in ("release", "detach")]
    return {
        "window_hours": since_hours,
        "events": len(ev),
        "acquisitions": len(acq),
        "acquisitions_after_waiting": len(waited),
        "share_waited": round(len(waited) / len(acq), 2) if acq else None,
        "wait_minutes_total": round(sum(waited) / 60, 1),
        "wait_minutes_max": round(max(waited) / 60, 1) if waited else 0,
        "gave_up": len(gave_up),
        "held_hours_total": round(sum(held) / 3600, 2),
        "slot_busy_share": round(sum(held) / (since_hours * 3600), 2),
    }
