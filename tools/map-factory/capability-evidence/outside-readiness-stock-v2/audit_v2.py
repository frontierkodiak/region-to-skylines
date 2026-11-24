"""Auditor and monitor: retained PID/start coverage that the driver joins.

Two roles with distinct process identities:
- auditor: discovers game/collector processes on the harness display, records
  each PID/start and final absence, and never signals a process.
- monitor: samples the pinned GPU and records game presence at the same time.

Neither role answers a Steam prompt, touches a lock or terminates anything.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import time

import stock_v2 as study


def identity(pid):
    path = Path("/proc") / str(pid)
    try:
        fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start_ticks": int(fields[19]), "state": fields[0]}
    except (FileNotFoundError, IndexError, ValueError):
        return None


def gone(record):
    current = identity(record["pid"])
    return not (
        current
        and current["start_ticks"] == record["start_ticks"]
        and current["state"] != "Z"
    )


def on_display(pid, display):
    try:
        env = (Path("/proc") / str(pid) / "environ").read_bytes().split(b"\0")
    except OSError:
        return False
    return f"DISPLAY={display}".encode() in env


def game_pids(display):
    out = subprocess.run(
        ["pgrep", "-x", "Cities.x64"], capture_output=True, text=True, check=False
    ).stdout
    return [int(p) for p in out.split() if on_display(int(p), display)]


def children(pid):
    path = Path("/proc") / str(pid) / "task"
    found = set()
    if not path.is_dir():
        return found
    for task in path.iterdir():
        try:
            data = (task / "children").read_text().split()
        except OSError:
            continue
        found.update(int(p) for p in data)
    return found


def audit(kind, out, collector, display):
    own = identity(os.getpid())
    if own is None:
        raise SystemExit("auditor identity unavailable")
    seen = {}
    samples = []
    start = identity(collector)
    while True:
        current = identity(collector)
        if current is None or start is None or current["start_ticks"] != start["start_ticks"]:
            break
        if kind == "auditor":
            found = {pid: identity(pid) for pid in game_pids(display)}
            found.update(
                {pid: identity(pid) for pid in children(collector) if identity(pid)}
            )
            samples.append({"at": study.now(), "processes": found})
        else:
            record = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,temperature.gpu,power.draw,memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            samples.append(
                {
                    "at": study.now(),
                    "gpu": record,
                    "game_pids": game_pids(display),
                }
            )
        for pid, record in samples[-1].get("processes", {}).items():
            if record:
                seen[(pid, record["start_ticks"])] = record
        time.sleep(2)
    return {
        "role": kind,
        "identity": own,
        "collector": collector,
        "samples": samples,
        "observed": [dict(record, gone=gone(record)) for record in seen.values()],
        "finished_at": study.now(),
        "scope": "PID/start observation only; no signals and no live permission claim",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=["auditor", "monitor"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--collector", type=int, required=True)
    parser.add_argument("--display", default=":57")
    args = parser.parse_args()
    receipt = audit(args.role, args.out, args.collector, args.display)
    study.write(args.out / f"{args.role}-receipt.json", receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
