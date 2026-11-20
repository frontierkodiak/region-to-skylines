"""Collect a frozen empty-map cohort serially, in foreground harness sessions."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from refresh_water_risk import sha, write


class IncompleteNativeRun(ValueError):
    """A cleanly closed attempt lacks a complete judged observation."""


def validate_inputs(item, staged):
    for name, expected in item["files_sha256"].items():
        if sha(staged / name) != expected:
            raise ValueError(f"Frozen input changed: {item['slug']}/{name}")


def validate(item, staged, run, expected_harness=None):
    """Accept complete judged observations, including failing water verdicts."""
    validate_inputs(item, staged)
    report = json.loads((run / "report.json").read_text())
    if report["game_minutes"] < 60:
        raise IncompleteNativeRun("Native report is shorter than sixty game minutes")
    if report["session"]["map"]["sha256"] != item["files_sha256"][item["package"]]:
        raise ValueError("Native package does not match the frozen capture")
    if report["session"]["cleanup"] != {
        "game": [],
        "steam_instances": [],
        "units_active": [],
    }:
        raise ValueError("Native lifecycle is not clean")
    if not report["session"].get("carbon_preflight", {}).get("idle"):
        raise ValueError("Native launch lacks carbon-idle evidence")
    if report["session"].get("offline_steam_error") or not report["session"].get(
        "offline_steam"
    ):
        raise ValueError("Native launch lacks continuous offline evidence")
    if any(p.get("population", 0) for p in report.get("curve", [])):
        raise ValueError("Populated city cannot supply empty-map labels")
    if not (run / "verdict.json").is_file():
        raise IncompleteNativeRun("Native observation has no verdict")
    verdict = json.loads((run / "verdict.json").read_text())
    if verdict.get("verdict") not in {"pass", "fail", "unverified"}:
        raise IncompleteNativeRun(
            "Native verdict is an infrastructure error or invalid"
        )
    source = json.loads((run / "harness-source.json").read_text())
    if (
        source.get("dirty") is not False
        or not source.get("commit")
        or (expected_harness and source["commit"] != expected_harness)
    ):
        raise ValueError(
            "Per-run harness provenance does not match the pinned clean source"
        )
    for name in ("terrain.u16", "water.u16"):
        if sha(run / "grids" / ("t000-" + name)) != item["files_sha256"][name]:
            raise ValueError(f"Initial native grid mismatch: {name}")
    for name, expected in (
        ("probes.json", item["files_sha256"]["probes.json"]),
        ("mapped-water.u8", item["files_sha256"]["mapped-water.u8"]),
        ("reference-water.u16", item["files_sha256"]["water.u16"]),
    ):
        if sha(run / name) != expected:
            raise ValueError(f"Native observation/reference mismatch: {name}")
    return report


def run_panel(staging, native, harness, plan, only=None, max_new=None):
    if max_new is not None and max_new < 1:
        raise ValueError("--max-new must be positive")
    manifest = json.loads((staging / "staging.json").read_text())
    if only and not any(
        r["slug"] == only and r["status"] == "prepared" for r in manifest["squares"]
    ):
        raise ValueError(f"--only must name a prepared panel square: {only}")
    provenance = json.loads(plan.read_text())
    if sha(staging / "staging.json") != provenance["staging_sha256"]:
        raise ValueError("Staging changed after native-plan freeze")
    if (harness / "tools/cs1-harness/pyproject.toml").is_file():
        harness = harness / "tools/cs1-harness"
    if (
        not (harness / "pyproject.toml").is_file()
        or not (harness / "cs1_harness/cli.py").is_file()
    ):
        raise ValueError(
            "Harness must identify the checkout or its tools/cs1-harness project"
        )
    repo = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=harness, text=True
        ).strip()
    )
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=harness, text=True
    ).strip()
    if actual != provenance["harness_source"]:
        raise ValueError("Wrong harness revision")
    subprocess.run(
        ["git", "diff", "--exit-code", "HEAD", "--", str(harness.relative_to(repo))],
        cwd=repo,
        check=True,
    )
    native.mkdir(parents=True, exist_ok=True)
    journal = native.parent / "native-driver.jsonl"
    new_cases = 0
    for item in manifest["squares"]:
        slug = item["slug"]
        if item["status"] != "prepared" or (only and slug != only):
            continue
        canonical = native / slug
        if canonical.exists():
            if (canonical / "failure.json").exists():
                print(f"{slug}: preserved quarantined failure", flush=True)
            else:
                validate(item, staging / slug, canonical, actual)
                records = (
                    [json.loads(line) for line in journal.read_text().splitlines()]
                    if journal.exists()
                    else []
                )
                if not any(
                    r["slug"] == slug
                    and r["report_sha256"] == sha(canonical / "report.json")
                    and r["verdict_sha256"] == sha(canonical / "verdict.json")
                    for r in records
                ):
                    raise ValueError(
                        f"Completed alias lacks a matching collection receipt: {slug}"
                    )
                print(f"{slug}: preserved complete native run", flush=True)
            continue
        attempts = []
        validate_inputs(item, staging / slug)
        for attempt in range(1, 4):
            output = native / f"{slug}-attempt-{attempt}"
            if output.exists():
                raise ValueError(f"Prior unclassified attempt exists: {output}")
            output.mkdir()
            command = [
                "uv",
                "run",
                "--locked",
                "--project",
                str(harness),
                "cs1-harness",
                "run",
                "--map",
                str(staging / slug / item["package"]),
                "--probes",
                str(staging / slug / "probes.json"),
                "--game-minutes",
                "60",
                "--issue",
                "PL-1072",
                "--label",
                f"PL-1072 {slug}",
                "--require-offline",
                "--no-live",
                "--no-record",
                "--wait-minutes",
                "120",
                "--retry-minutes",
                "0",
                "--out",
                str(output),
            ]
            write(
                output / "invocation.json",
                {
                    "argv": command,
                    "harness_source": actual,
                    "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            )
            print(
                f"{slug}: attempt {attempt} starts; offline/carbon/FIFO guards enabled",
                flush=True,
            )
            with (output / "driver.log").open("w") as log:
                process = subprocess.run(
                    command, cwd=harness, stdout=log, stderr=log, check=False
                )
            attempts.append({"path": str(output), "exit_code": process.returncode})
            receipt_path = output / "session-receipt.json"
            receipt = (
                json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
            )
            if process.returncode in (75, 77) or receipt.get("offline_steam_error"):
                raise RuntimeError(
                    f"Shared slot/account guard stopped {slug}; no automatic retry: {process.returncode}"
                )
            if (output / "report.json").exists():
                # A binding/lifecycle error stops the experiment. It cannot be
                # repaired by retrying or silently dropping the square.
                try:
                    report = validate(item, staging / slug, output, actual)
                except IncompleteNativeRun as error:
                    write(output / "collection-error.json", {"reason": str(error)})
                else:
                    collected = {
                        "slug": slug,
                        "path": str(output),
                        "exit_code": process.returncode,
                        "game_minutes": report["game_minutes"],
                        "report_sha256": sha(output / "report.json"),
                        "verdict_sha256": sha(output / "verdict.json"),
                    }
                    with journal.open("a") as stream:
                        stream.write(json.dumps(collected) + "\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                    canonical.symlink_to(output.name, target_is_directory=True)
                    print(
                        f"{slug}: complete {report['game_minutes']:.3f} game minutes; cleanup empty",
                        flush=True,
                    )
                    break
            if receipt.get("cleanup") != {
                "game": [],
                "steam_instances": [],
                "units_active": [],
            }:
                raise RuntimeError(f"Cannot establish clean teardown after {slug}")
            print(f"{slug}: failed attempt retained; retrying fresh", flush=True)
        else:
            canonical.mkdir()
            write(
                canonical / "failure.json",
                {"reason": "three failed full-run attempts", "attempts": attempts},
            )
            print(f"{slug}: quarantined, not a safe negative", flush=True)
        new_cases += 1
        if max_new is not None and new_cases >= max_new:
            print(
                f"Collected tranche of {new_cases} new squares; no child remains active",
                flush=True,
            )
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("staging", "native", "harness", "plan"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--only")
    parser.add_argument(
        "--max-new",
        type=int,
        help="collect this many new squares, then return after teardown",
    )
    args = parser.parse_args()
    run_panel(
        args.staging.resolve(),
        args.native.resolve(),
        args.harness.resolve(),
        args.plan.resolve(),
        args.only,
        args.max_new,
    )
