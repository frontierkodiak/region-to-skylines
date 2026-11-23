"""Driver: one foreground opening, joined auditor and monitor, one opening.json.

The driver is the only process that writes `opening.json`, so the five owned
process roles are captured from the processes that actually ran and joined.
The game identity comes from the collector's runtime inventory; the driver,
collector, auditor and monitor identities are this process tree.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

import stock_v2 as study

HERE = Path(__file__).resolve().parent


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id")
    parser.add_argument("--raw", type=Path, required=True)
    args = parser.parse_args()
    freeze = study.read(HERE / "freeze.json")
    kind = (
        "control"
        if any(c["case_id"] == args.case_id for c in freeze["controls"])
        else "holdout"
    )
    out = args.raw / args.case_id
    driver_out = args.raw / "drivers" / args.case_id
    driver_out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONPATH=str(study.HARNESS) + os.pathsep + str(study.OLD))
    command = [
        sys.executable,
        str(HERE / "collect_v2.py"),
        args.case_id,
        "--raw",
        str(args.raw),
    ]
    with (driver_out / "collector.log").open("x") as log:
        collector = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
        collector_identity = identity(collector.pid)
        if collector_identity is None:
            collector.wait()
            raise RuntimeError("collector exited before identity captured")
        auditor = subprocess.Popen(
            [
                sys.executable,
                str(HERE / "audit_v2.py"),
                "--role",
                "auditor",
                "--out",
                str(out),
                "--collector",
                str(collector.pid),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
        )
        monitor = subprocess.Popen(
            [
                sys.executable,
                str(HERE / "audit_v2.py"),
                "--role",
                "monitor",
                "--out",
                str(out),
                "--collector",
                str(collector.pid),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
        )
        roles = {
            "collector": collector_identity,
            "auditor": identity(auditor.pid),
            "monitor": identity(monitor.pid),
            "driver": identity(os.getpid()),
        }
        if any(value is None for value in roles.values()):
            for child in (collector, auditor, monitor):
                child.wait()
            raise RuntimeError("owned process identity missing")
        study.write(
            driver_out / "driver-launch.json",
            {
                "started_at": study.now(),
                "case_id": args.case_id,
                "kind": kind,
                "command": command,
                "roles": roles,
                "freeze_sha256": study.sha(HERE / "freeze.json"),
            },
        )
        code = collector.wait()
        auditor_code = auditor.wait(timeout=120)
        monitor_code = monitor.wait(timeout=120)
    observation = study.read(out / "observation.json")
    game = observation.get("runtime", {}).get("launch")
    if not game:
        raise RuntimeError("no game runtime inventory")
    owned = {
        "game": {"pid": game["pid"], "start_ticks": game["start_ticks"]},
        "driver": {"pid": roles["driver"]["pid"], "start_ticks": roles["driver"]["start_ticks"]},
        "collector": {
            "pid": roles["collector"]["pid"],
            "start_ticks": roles["collector"]["start_ticks"],
        },
        "auditor": {
            "pid": roles["auditor"]["pid"],
            "start_ticks": roles["auditor"]["start_ticks"],
        },
        "monitor": {
            "pid": roles["monitor"]["pid"],
            "start_ticks": roles["monitor"]["start_ticks"],
        },
    }
    identities = {(v["pid"], v["start_ticks"]) for v in owned.values()}
    if len(identities) != len(owned):
        raise RuntimeError("owned process identity reused across roles")
    cleanup = {role: dict(record, gone=gone(record)) for role, record in owned.items()}
    if not all(value["gone"] for value in cleanup.values()):
        raise RuntimeError("owned process still running at return")
    observation["owned_processes"] = owned
    observation["cleanup"] = cleanup
    observation["auditor"] = study.read(out / "auditor-receipt.json")
    observation["monitor"] = study.read(out / "monitor-receipt.json")
    study.write(out / "opening.json", observation)
    study.write(
        driver_out / "driver-completion.json",
        {
            "finished_at": study.now(),
            "case_id": args.case_id,
            "collector_returncode": code,
            "auditor_returncode": auditor_code,
            "monitor_returncode": monitor_code,
            "roles": roles,
            "cleanup": cleanup,
            "observation_sha256": study.sha(out / "opening.json"),
            "completed": observation.get("completed"),
            "error": observation.get("error"),
        },
    )
    print((driver_out / "collector.log").read_text())
    if not observation.get("completed") or code or auditor_code or monitor_code:
        raise SystemExit(code or 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
