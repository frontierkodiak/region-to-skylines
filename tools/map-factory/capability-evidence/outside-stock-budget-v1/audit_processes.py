"""Read-only supplemental coverage of each observed game/GPU monitor identity."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def identity(pid):
    try:
        p = Path("/proc") / str(pid)
        v = (p / "stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start_ticks": v[19], "state": v[0]}
    except (FileNotFoundError, ProcessLookupError):
        return None


def alive(row):
    current = identity(row["pid"])
    return bool(
        current
        and current["start_ticks"] == row["start_ticks"]
        and current["state"] != "Z"
    )


out = Path(sys.argv[1])
target = identity(int(sys.argv[2]))
seen = {}
header = {
    "started_at": datetime.datetime.now(datetime.UTC).isoformat(),
    "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "auditor": identity(os.getpid()),
    "collector": target,
    "scope": "supplemental read-only process observation; no game/config/source writes; begins when invoked, not a claim of complete process birth coverage",
}
(out / "audit-source-freeze.json").write_text(json.dumps(header, indent=2) + "\n")


def add(pid, kind):
    row = identity(pid)
    if row:
        seen[(pid, row["start_ticks"])] = {**row, "kind": kind}


add(target["pid"], "collector")
while alive(target):
    reply = subprocess.run(
        ["systemctl", "--user", "show", "cs1-harness-gpu", "-p", "MainPID", "--value"],
        capture_output=True,
        text=True,
        check=False,
    )
    if reply.stdout.strip().isdigit() and int(reply.stdout) > 0:
        add(int(reply.stdout), "session_gpu_monitor")
    for path in Path("/proc").glob("[0-9]*"):
        try:
            if (
                path / "comm"
            ).read_text().strip() == "Cities.x64" and b"DISPLAY=:57" in (
                path / "environ"
            ).read_bytes().split(b"\0"):
                add(int(path.name), "game")
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    time.sleep(0.5)
rows = [{**r, "still_running": alive(r)} for r in seen.values()]
(out / "audit-completion.json").write_text(
    json.dumps(
        {
            "finished_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "source_freeze": header,
            "coverage": rows,
        },
        indent=2,
    )
    + "\n"
)
print(json.dumps({"coverage": rows}))
