"""Run one rail batch and collect its owned telemetry before returning."""

import argparse
from pathlib import Path
import subprocess
import sys

from cs1_harness import rail_study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["controls", "cohort"])
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--only")
    args = parser.parse_args()
    sampler = Path(__file__).resolve().parent.parent / "outside-v1/sample_gpu.py"
    command = [
        sys.executable,
        "-m",
        "cs1_harness.rail_study",
        args.action,
        "--study",
        str(args.study),
    ]
    if args.only:
        command += ["--only", args.only]
    telemetry = args.study / "raw/telemetry" / (args.only or args.action)
    rail_study.freeze(
        telemetry / "driver.json",
        {
            "observed_at": rail_study.now(),
            "command": command,
            "driver_sha256": rail_study.digest(Path(__file__)),
            "sampler_sha256": rail_study.digest(sampler),
            "selection_sha256": rail_study.digest(args.study / "selection.json"),
        },
    )
    with (telemetry / "collector.log").open("x") as log:
        with subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT
        ) as collector:
            with subprocess.Popen(
                [
                    sys.executable,
                    str(sampler),
                    str(collector.pid),
                    str(telemetry / "process-gpu.jsonl"),
                ]
            ) as monitor:
                status = collector.wait()
                monitor_status = monitor.wait(timeout=30)
    if status or monitor_status:
        raise SystemExit(status or monitor_status)


if __name__ == "__main__":
    main()
