"""Foreground native cohort; preserve frozen observations and stop on regression."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from audit_soak import audit
from soak import stage_prepared


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(inputs, reference, output, harness, only):
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise ValueError("Commit the reviewed candidate before native evaluation")
    cohort = {
        "status": "running",
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "cases": [],
    }
    for slug, package, probes in stage_prepared(inputs, output, only):
        prior = read(reference / slug / "probes.json")
        data = read(probes)
        for key in ["points", "ground_truth", "landmark_expectations", "startup_views"]:
            assert data.get(key) == prior.get(key), (slug, key, "observation drift")
        assert (probes.parent / "mapped-water.u8").read_bytes() == (
            reference / slug / "mapped-water.u8"
        ).read_bytes(), slug
        for key in [
            "views",
            "retain_opening_until_five",
            "supplementary_world_observations",
        ]:
            if key in prior:
                data[key] = prior[key]
        probes.write_text(json.dumps(data, indent=2) + "\n")
        run = output / slug
        run.mkdir(parents=True, exist_ok=False)
        print(f"{slug}: starting one 60-minute native evaluation", flush=True)
        with (run / "driver.log").open("w") as log:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "--locked",
                    "cs1-harness",
                    "run",
                    "--map",
                    str(package),
                    "--probes",
                    str(probes),
                    "--game-minutes",
                    "60",
                    "--wait-minutes",
                    "0",
                    "--out",
                    str(run),
                    "--issue",
                    "PL-912",
                ],
                cwd=harness,
                stdout=log,
                stderr=log,
                check=False,
            )
        if result.returncode:
            cohort.update(
                status="blocked", blocked_case=slug, process_exit=result.returncode
            )
            (output / "evaluation.json").write_text(json.dumps(cohort, indent=2) + "\n")
            raise SystemExit(f"{slug}: process failed; no subsequent map launched")
        report, verdict = read(run / "report.json"), read(run / "verdict.json")
        checks = audit(run, inputs / slug, inputs / slug / "geometry.json")
        (run / "audit-common.json").write_text(json.dumps(checks, indent=2) + "\n")
        assert report["game_minutes"] >= 60
        assert report["harness"] == {"commit": cohort["source_head"], "dirty": False}
        assert all(
            checks[k]
            for k in ["terrain_exact", "initial_water_exact", "source_controls_match"]
        )
        assert not any(report["session"]["cleanup"].values())
        previous = read(reference / slug / "verdict.json")
        regressions = sorted(set(verdict["failed"]) - set(previous["failed"]))
        cohort["cases"].append(
            {
                "slug": slug,
                "crp_sha256": sha(package),
                "game_minutes": report["game_minutes"],
                "failed": verdict["failed"],
                "previous_failed": previous["failed"],
                "regressions": regressions,
                "initial_audits": {
                    k: checks[k]
                    for k in [
                        "terrain_exact",
                        "initial_water_exact",
                        "source_controls_match",
                    ]
                },
                "receipts_sha256": {
                    name: sha(run / name)
                    for name in [
                        "report.json",
                        "verdict.json",
                        "session-receipt.json",
                        "audit-common.json",
                    ]
                },
            }
        )
        (output / "evaluation.json").write_text(json.dumps(cohort, indent=2) + "\n")
        print(
            f"{slug}: {report['game_minutes']:.3f} minutes; failed={verdict['failed']}; regressions={regressions}",
            flush=True,
        )
        if regressions:
            cohort["status"] = "rejected_regression"
            (output / "evaluation.json").write_text(json.dumps(cohort, indent=2) + "\n")
            raise SystemExit(
                "A previously passing gate failed; remaining maps not launched"
            )
    cohort["status"] = (
        "complete_with_recorded_failures"
        if any(c["failed"] for c in cohort["cases"])
        else "complete"
    )
    (output / "evaluation.json").write_text(json.dumps(cohort, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["inputs", "reference", "output", "harness"]:
        parser.add_argument(name, type=Path)
    parser.add_argument(
        "--only",
        nargs="+",
        default=["rio", "asheville", "innsbruck", "pittsburgh", "charleston"],
    )
    args = parser.parse_args()
    evaluate(
        args.inputs.resolve(),
        args.reference.resolve(),
        args.output.resolve(),
        args.harness.resolve(),
        args.only,
    )
