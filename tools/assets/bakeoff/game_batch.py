"""Run the nine fixed native build/check pairs serially through the shared harness.

Use the PL-881 harness extension atop PL-880 (scoped auto templates and gameplay
view). A Steam/slot block ends the batch; it never answers a Steam prompt.
Completed pairs resume only against their exact plan and unchanged CRP/receipts.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("harness", type=Path)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("map", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--wait-minutes", type=float, default=120)
    args = parser.parse_args()
    harness, inputs, out = (
        p.resolve() for p in (args.harness, args.inputs, args.output)
    )
    out.mkdir(parents=True, exist_ok=True)
    plan = {
        "input_manifest_sha256": digest(inputs / "manifest.json"),
        "map_sha256": digest(args.map),
        "harness_source": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=harness, text=True
        ).strip(),
        "driver_sha256": digest(harness / "cs1_harness/assets.py"),
        "screen": "1280x720",
        "camera": "close 45m/25deg; gameplay 120m/40deg; LOD 1.05*max switch/40deg",
        "position": [0, 300],
    }
    plan_path = out / "batch-plan.json"
    if plan_path.exists():
        assert json.loads(plan_path.read_text()) == plan, (
            "changed plan: use a new output root"
        )
    plan_path.write_text(json.dumps(plan, indent=2))
    env = {**os.environ, "CS1_HARNESS_SCREEN": plan["screen"], "PYTHONUNBUFFERED": "1"}
    for target, template in (
        ("bungalow", "auto"),
        ("storefront", "auto:Commercial:CommercialLow"),
        ("apartment", "auto:Residential:ResidentialHigh"),
    ):
        for arm in ("A", "B", "C"):
            name = arm + "-" + target
            marker = out / (name + ".complete.json")
            if marker.exists():
                prior = json.loads(marker.read_text())
                assert all(digest(out / p) == h for p, h in prior["files"].items()), (
                    name
                )
                print("RESUME", name, flush=True)
                continue
            elapsed = {}
            for phase in ("build", "check"):
                dest = out / phase / name
                cmd = ["uv", "run", "--frozen", "cs1-harness", "asset", phase]
                if phase == "build":
                    cmd += [
                        "--src",
                        str(inputs / name),
                        "--name",
                        name,
                        "--template",
                        template,
                    ]
                else:
                    cmd += [
                        "--crp",
                        str(out / "build" / name / (name + ".crp")),
                        "--map",
                        str(args.map.resolve()),
                        "--at",
                        "0,300",
                    ]
                cmd += [
                    "--out",
                    str(dest),
                    "--wait-minutes",
                    str(args.wait_minutes),
                    "--max-attempts",
                    "1",
                ]
                print("START", name, phase, flush=True)
                before = time.monotonic()
                rc = subprocess.run(cmd, cwd=harness, env=env, check=False).returncode
                elapsed[phase] = time.monotonic() - before
                if rc:
                    (out / "stopped.json").write_text(
                        json.dumps(
                            {
                                "name": name,
                                "phase": phase,
                                "exit": rc,
                                "seconds": elapsed,
                            },
                            indent=2,
                        )
                    )
                    raise SystemExit(rc)
            files = [out / "build" / name / (name + ".crp")]
            files += [out / p / name / f"asset-{p}.json" for p in ("build", "check")]
            marker.write_text(
                json.dumps(
                    {
                        "seconds_including_queue": elapsed,
                        "files": {str(p.relative_to(out)): digest(p) for p in files},
                    },
                    indent=2,
                )
            )
            print("COMPLETE", name, elapsed, flush=True)


if __name__ == "__main__":
    main()
