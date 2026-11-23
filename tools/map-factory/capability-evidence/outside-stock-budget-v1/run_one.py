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
        auditor_command = [
            sys.executable,
            str(study.HERE / "audit_processes.py"),
            str(out),
            str(child.pid),
        ]
        auditor = subprocess.Popen(
            auditor_command, stdout=log, stderr=subprocess.STDOUT, env=env
        )
        auditor_identity = collect.process_identity(auditor.pid)
        if auditor_identity is None:
            code = child.wait()
            auditor.wait()
            raise RuntimeError("auditor identity missing")
        study.freeze(
            out / "auditor-launch.json",
            {
                "source_sha256": study.sha(study.HERE / "audit_processes.py"),
                "command": auditor_command,
                "auditor": auditor_identity,
            },
        )
        code = child.wait()
        auditor_code = auditor.wait(timeout=30)
    receipt = {
        "finished_at": study.now(),
        "returncode": code,
        "collector": identity,
        "collector_still_running": collect.still_running(identity),
        "auditor": auditor_identity,
        "auditor_still_running": collect.still_running(auditor_identity),
        "auditor_returncode": auditor_code,
    }
    study.freeze(out / "completion.json", receipt)
    print((out / "collector.log").read_text())
    if (
        receipt["collector_still_running"]
        or receipt["auditor_still_running"]
        or auditor_code
    ):
        raise RuntimeError("collector cleanup failed")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
