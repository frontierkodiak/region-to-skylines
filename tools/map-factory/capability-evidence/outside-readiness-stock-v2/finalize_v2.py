"""Finalize one retained opening after its driver has exited.

This tool measures nothing.  It joins the retained observation, the retained
driver launch/role record and the auditor/monitor receipts, then verifies that
every owned PID/start identity is absent *after* the driver exited, which is the
only point at which the driver's own absence can be attested.  It writes
`opening.json` and `finalize.json`; it never edits the observation.

It is deliberately outside the frozen measurement source closure: the frozen
collector, driver and auditor produced every measurement fact it reads.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import time

import stock_v2 as study

ROLES = ("game", "driver", "collector", "auditor", "monitor")


def identity(pid):
    path = Path("/proc") / str(pid)
    try:
        fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start_ticks": int(fields[19]), "state": fields[0]}
    except (FileNotFoundError, IndexError, ValueError):
        return None


def gone(record):
    current = identity(record["pid"])
    if current is None:
        return True
    if current["start_ticks"] != record["start_ticks"]:
        return True
    return current["state"] == "Z"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id")
    parser.add_argument("--raw", type=Path, required=True)
    args = parser.parse_args()
    out = args.raw / args.case_id
    driver_out = args.raw / "drivers" / args.case_id
    observation = study.read(out / "observation.json")
    launch = study.read(driver_out / "driver-launch.json")
    if not observation.get("completed") or observation.get("error"):
        raise SystemExit(f"opening not complete: {observation.get('error')}")
    if len(observation["paths"]) != len(observation["plans"]):
        raise SystemExit("planned requests are not all observed")
    roles = launch["roles"]
    game = observation["runtime"]["launch"]
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
    if len({(v["pid"], v["start_ticks"]) for v in owned.values()}) != len(roles) + 1:
        raise SystemExit("owned process identity reused across roles")
    deadline = time.monotonic() + 60
    while True:
        cleanup = {role: dict(record, gone=gone(record)) for role, record in owned.items()}
        if all(value["gone"] for value in cleanup.values()):
            break
        if time.monotonic() >= deadline:
            raise SystemExit(f"owned processes still running: {cleanup}")
        time.sleep(0.5)
    finalizer = identity(__import__("os").getpid())
    observation["owned_processes"] = owned
    observation["cleanup"] = cleanup
    observation["auditor"] = study.read(out / "auditor-receipt.json")
    observation["monitor"] = study.read(out / "monitor-receipt.json")
    observation["finalizer"] = {
        "identity": finalizer,
        "finalized_at": study.now(),
        "source_sha256": study.sha(Path(__file__).resolve()),
        "scope": "post-exit absence verification and packaging only; no measurement",
    }
    study.write(out / "opening.json", observation)
    study.write(
        out / "finalize.json",
        {
            "case_id": args.case_id,
            "finalized_at": study.now(),
            "finalizer": finalizer,
            "owned_processes": owned,
            "cleanup": cleanup,
            "observation_sha256": study.sha(out / "observation.json"),
            "opening_sha256": study.sha(out / "opening.json"),
            "driver_completion_present": (driver_out / "driver-completion.json").exists(),
        },
    )
    print(study.canonical({"case_id": args.case_id, "cleanup": cleanup}).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
