"""Join an exact collector and verify every observed collector/game identity."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

import study
import collect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id")
    parser.add_argument("--raw", type=Path, required=True)
    args = parser.parse_args()
    out = args.raw / "drivers" / args.case_id
    out.mkdir(parents=True, exist_ok=False)
    command = [
        sys.executable,
        str(study.HERE / "collect.py"),
        args.case_id,
        "--raw",
        str(args.raw),
    ]
    env = dict(os.environ, PYTHONPATH=str(study.HARNESS))
    with (out / "collector.log").open("x") as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
        identity = collect.process_identity(child.pid)
        if identity is None:
            child.wait()
            raise RuntimeError("collector exited before process identity captured")
        study.freeze(
            out / "launch.json",
            {
                "started_at": study.now(),
                "command": command,
                "collector": identity,
                "driver": collect.process_identity(os.getpid()),
                "freeze_sha256": study.sha(study.HERE / "freeze.json"),
                "monitor": "no monitor process; session-owned GPU telemetry only",
            },
        )
        code = child.wait()
    receipt = {
        "finished_at": study.now(),
        "returncode": code,
        "collector": identity,
        "collector_still_running": collect.still_running(identity),
    }
    study.freeze(out / "completion.json", receipt)
    print((out / "collector.log").read_text())
    if receipt["collector_still_running"]:
        raise RuntimeError("collector cleanup failed")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
