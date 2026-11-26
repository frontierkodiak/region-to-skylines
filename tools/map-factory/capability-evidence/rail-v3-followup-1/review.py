"""Verify native receipts and separately audit a reported teardown remainder.

The frozen collector/verifier remains unchanged. Its strict cleanup failure is
retained; a later audit can establish exit without rewriting that snapshot.
"""

import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

from cs1_harness import rail_study as rail

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "frozen_followup", HERE.parent / "rail-v3/followup.py"
)
frozen_driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen_driver)


def manifests():
    initial = json.loads((frozen_driver.BASE / "integrity.json").read_text())
    extra = json.loads((HERE / "integrity.json").read_text())
    if extra["driver_sha256"] != rail.digest(Path(frozen_driver.__file__)) or extra[
        "initial_integrity_sha256"
    ] != rail.digest(frozen_driver.BASE / "integrity.json"):
        raise ValueError("frozen continuation source or initial manifest changed")
    return initial, extra


def make_audit():
    initial, extra = manifests()
    games, collectors, remainders, observations = [], set(), set(), {}
    for root, manifest in [(frozen_driver.BASE, initial), (HERE, extra)]:
        for record in manifest["files"]:
            path = Path(record["path"])
            if path.name == "observation.json":
                observation = json.loads(
                    gzip.decompress((root / (str(path) + ".gz")).read_bytes())
                )
                observations[str(path)] = record["sha256"]
                identity = observation.get("runtime_identity", {})
                if identity:
                    pid = identity["host_pid"]
                    proc = Path("/proc") / str(pid)
                    current = (
                        (proc / "stat").read_text().rsplit(")", 1)[1].split()[19]
                        if proc.exists()
                        else None
                    )
                    games.append(
                        {
                            "pid": pid,
                            "observed_start_ticks": identity["process_start_ticks"],
                            "current_start_ticks": current,
                            "owned_alive": current == identity["process_start_ticks"],
                        }
                    )
                remainders.update(
                    observation.get("session", {})
                    .get("cleanup", {})
                    .get("steam_instances", [])
                )
            elif path.name == "process-gpu.jsonl":
                for line in gzip.decompress(
                    (root / (str(path) + ".gz")).read_bytes()
                ).splitlines():
                    collectors.add(json.loads(line)["owner_pid"])
    active = subprocess.run(
        ["flatpak", "ps", "--columns=instance,application"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    steam = [
        row[0]
        for line in active.splitlines()
        if len(row := line.split()) >= 2 and row[1] == "com.valvesoftware.Steam"
    ]
    monitors = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            args = (proc / "cmdline").read_bytes().decode().split("\0")
        except (OSError, UnicodeError):
            continue
        if str(frozen_driver.SAMPLER) in args and any(
            str(pid) in args for pid in collectors
        ):
            monitors.append(int(proc.name))
    return rail.freeze(
        HERE / "cleanup-audit.json",
        {
            "observed_at": rail.now(),
            "audit_source_sha256": rail.digest(Path(__file__)),
            "initial_integrity_sha256": rail.digest(
                frozen_driver.BASE / "integrity.json"
            ),
            "followup_integrity_sha256": rail.digest(HERE / "integrity.json"),
            "observation_sha256": observations,
            "games": games,
            "collector_pids": sorted(collectors),
            "collector_pids_still_present": [
                pid for pid in collectors if Path("/proc", str(pid)).exists()
            ],
            "owned_monitor_pids_still_present": monitors,
            "reported_steam_remainders": sorted(remainders),
            "current_steam_instances": steam,
            "reported_steam_remainders_still_present": sorted(remainders & set(steam)),
            "scope": "read-only later exit audit; no process stopped; foreign Steam instances remain untouched",
        },
    )


def cleanup_state(cleanup, audit):
    if not {"game", "steam_instances", "units_active"} <= cleanup.keys():
        raise ValueError("missing cleanup facts")
    if cleanup["game"] or cleanup["units_active"]:
        raise ValueError("game or unit remained at teardown")
    if cleanup["steam_instances"]:
        if (
            set(cleanup["steam_instances"]) - set(audit["reported_steam_remainders"])
            or audit["reported_steam_remainders_still_present"]
        ):
            raise ValueError("Steam remainder is not proven absent")
        return "Steam listed at teardown; later audit proves listed instance absent"
    return "empty teardown snapshot"


def verify():
    frozen_driver.initial_verify()
    initial, extra = manifests()
    audit = json.loads((HERE / "cleanup-audit.json").read_text())
    if (
        audit["audit_source_sha256"] != rail.digest(Path(__file__))
        or audit["initial_integrity_sha256"]
        != rail.digest(frozen_driver.BASE / "integrity.json")
        or audit["followup_integrity_sha256"] != rail.digest(HERE / "integrity.json")
        or any(row["owned_alive"] for row in audit["games"])
        or audit["collector_pids_still_present"]
        or audit["owned_monitor_pids_still_present"]
        or audit["reported_steam_remainders_still_present"]
    ):
        raise ValueError(
            "later cleanup audit is unbound or reports owned work still alive"
        )
    with tempfile.TemporaryDirectory(prefix="rail-reviewed-") as directory:
        study = Path(directory)
        (study / "selection.json").write_bytes(
            (frozen_driver.BASE / "selection.json").read_bytes()
        )
        frozen_driver.unpack(frozen_driver.BASE, initial, study)
        frozen_driver.unpack(HERE, extra, study)
        batch = frozen_driver.load_batch(study, extra["batch"])
        driver = json.loads(
            (study / "raw/telemetry" / extra["batch"] / "driver.json").read_text()
        )
        if (
            driver["batch_sha256"]
            != rail.digest(study / "batches" / f"{extra['batch']}.json")
            or driver["driver_sha256"] != batch["driver_sha256"]
            or driver["sampler_sha256"] != batch["sampler_sha256"]
        ):
            raise ValueError("driver differs from continuation freeze")
        selection = json.loads((study / "selection.json").read_text())
        originals = {case["slug"]: case for case in selection["cohort"]}
        for case in batch["cases"]:
            if {
                k: v for k, v in case.items() if k not in {"slug", "original_case"}
            } != {
                k: v for k, v in originals[case["original_case"]].items() if k != "slug"
            }:
                raise ValueError("continuation changes original package/settings")
        control_end = max(
            json.loads((study / "raw" / c["slug"] / "observation.json").read_text())[
                "finished_at"
            ]
            for c in selection["controls"]
        )
        results, findings = {}, []
        known = {
            case["artifact_sha256"]
            for case in selection["cohort"] + selection["controls"]
        }
        for path in (study / "raw").glob("*/observation.json"):
            if json.loads(path.read_text())["artifact_sha256"] not in known:
                raise ValueError("unselected package")
            relative = str(path.relative_to(study))
            if rail.digest(path) != audit["observation_sha256"].get(relative):
                raise ValueError("later audit refers to different observation bytes")
        for case in selection["cohort"]:
            rows = []
            for slug, summary in frozen_driver.attempts(study, case):
                path = study / "raw" / slug
                observation = json.loads((path / "observation.json").read_text())
                if observation["finished_at"] > audit["observed_at"]:
                    raise ValueError("audit predates observation exit")
                query = path / "query-freeze.json"
                if query.exists():
                    when = json.loads(query.read_text())["frozen_at"]
                    if when < control_end or (
                        slug in {c["slug"] for c in batch["cases"]}
                        and when < batch["frozen_at"]
                    ):
                        raise ValueError("query predates protocol validation/freeze")
                if summary["completed"]:
                    if not query.exists() or not summary["context_bound"]:
                        raise ValueError(
                            "completed opening lacks query freeze/runtime context"
                        )
                    state = cleanup_state(
                        observation.get("session", {}).get("cleanup", {}), audit
                    )
                    summary["cleanup_state"] = state
                    if state != "empty teardown snapshot":
                        findings.append(
                            {
                                "attempt": slug,
                                "raw_cleanup": observation["session"]["cleanup"],
                                "later_state": state,
                            }
                        )
                rows.append({"attempt": slug, **summary})
            results[case["slug"]] = {
                "attempts": rows,
                "status": "sampled_positive"
                if any(r["distinct_edge_boundary_successes"] for r in rows)
                else "Unknown",
            }
        return {
            "stock_gate": rail.controls_valid(study),
            "initial_raw_files": len(initial["files"]),
            "followup_raw_files": len(extra["files"]),
            "cleanup_findings": findings,
            "cleanup_audit_sha256": rail.digest(HERE / "cleanup-audit.json"),
            "cohort": results,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    if args.audit:
        print(make_audit())
    print(json.dumps(verify(), indent=2))
