"""Join one collector and its GPU sampler before returning."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

import study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("--raw", type=Path, required=True)
    args = parser.parse_args()
    sampler = study.CAP / "outside-v1/sample_gpu.py"
    telemetry = args.raw / "telemetry" / args.slug
    command = [
        sys.executable,
        str(study.HERE / "collect.py"),
        args.slug,
        "--raw",
        str(args.raw),
    ]
    study.freeze(
        telemetry / "driver.json",
        {
            "frozen_at": study.now(),
            "command": command,
            "sampler_sha256": study.sha(sampler),
            "freeze_sha256": study.sha(study.HERE / "freeze.json"),
        },
    )
    env = dict(os.environ, PYTHONPATH=str(study.HARNESS))
    with (telemetry / "collector.log").open("x") as log:
        with subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT, env=env
        ) as collector:
            with subprocess.Popen(
                [
                    sys.executable,
                    str(sampler),
                    str(collector.pid),
                    str(telemetry / "process-gpu.jsonl"),
                ],
                env=env,
            ) as monitor:
                result = collector.wait()
                monitor_result = monitor.wait(timeout=30)
    print((telemetry / "collector.log").read_text())
    if result or monitor_result:
        raise SystemExit(result or monitor_result)


if __name__ == "__main__":
    main()
