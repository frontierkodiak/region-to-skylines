"""Append-only rail continuation. Native protocol and initial evidence stay fixed."""

import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from cs1_harness import rail_study as rail

BASE = Path(__file__).resolve().parent
SAMPLER = BASE.parent / "outside-v1/sample_gpu.py"
VERIFIER = BASE.parent / "rail-v1/verify.py"


def initial_verify():
    spec = importlib.util.spec_from_file_location("initial_rail_verifier", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HERE = BASE
    return module.verify()


def attempts(study, case):
    result = []
    for path in sorted((study / "raw").glob("*/observation.json")):
        observation = json.loads(path.read_text())
        if observation["artifact_sha256"] == case["artifact_sha256"]:
            summary = rail.summarize(path.parent, study / "selection.json")
            result.append((path.parent.name, summary))
    return result


def choose_attempt(study, case):
    previous = attempts(study, case)
    if any(row["completed"] and row["context_bound"] for _, row in previous):
        return None
    number = len(previous) + 1
    while (study / "raw" / f"{case['slug']}-attempt-{number}").exists():
        number += 1
    return {
        **case,
        "original_case": case["slug"],
        "slug": f"{case['slug']}-attempt-{number}",
    }


def prepare(study, batch):
    if not initial_verify()["stock_gate"] or not rail.controls_valid(study):
        raise ValueError("initial stock-positive/invalid-pair gate is not valid")
    selection = json.loads((study / "selection.json").read_text())
    if rail.digest(study / "selection.json") != rail.digest(BASE / "selection.json"):
        raise ValueError("runtime selection differs from immutable initial selection")
    initial = json.loads((BASE / "integrity.json").read_text())
    for record in initial["files"]:
        if rail.digest(study / record["path"]) != record["sha256"]:
            raise ValueError("initial runtime receipt changed")
    cases = [
        planned
        for case in selection["cohort"]
        if (planned := choose_attempt(study, case))
    ]
    return rail.freeze(
        study / "batches" / f"{batch}.json",
        {
            "frozen_at": rail.now(),
            "batch": batch,
            "cases": cases,
            "selection_sha256": rail.digest(study / "selection.json"),
            "initial_integrity_sha256": rail.digest(BASE / "integrity.json"),
            "driver_sha256": rail.digest(Path(__file__)),
            "sampler_sha256": rail.digest(SAMPLER),
            "native_sources": selection["sources"],
            "protocol": selection["protocol"],
            "stock_observation_sha256": {
                case["slug"]: rail.digest(
                    study / "raw" / case["slug"] / "observation.json"
                )
                for case in selection["controls"]
            },
            "prediction": "same bounded candidate rule; misses remain Unknown; calibration references are not new votes",
        },
    )


def load_batch(study, batch):
    frozen = json.loads((study / "batches" / f"{batch}.json").read_text())
    if (
        frozen["driver_sha256"] != rail.digest(Path(__file__))
        or frozen["sampler_sha256"] != rail.digest(SAMPLER)
        or frozen["native_sources"] != rail.sources()
        or frozen["selection_sha256"] != rail.digest(study / "selection.json")
        or frozen["initial_integrity_sha256"] != rail.digest(BASE / "integrity.json")
        or frozen["protocol"] != rail.PROTOCOL
    ):
        raise ValueError("continuation source, protocol or selection changed")
    if not rail.controls_valid(study):
        raise ValueError("stock gate lost before continuation")
    for slug, expected in frozen["stock_observation_sha256"].items():
        if rail.digest(study / "raw" / slug / "observation.json") != expected:
            raise ValueError("calibration receipt changed")
    return frozen


def collect(study, batch):
    frozen = load_batch(study, batch)
    selection = json.loads((study / "selection.json").read_text())
    original = {case["slug"]: case for case in selection["cohort"]}
    for case in frozen["cases"]:
        if {k: v for k, v in case.items() if k not in {"slug", "original_case"}} != {
            k: v for k, v in original[case["original_case"]].items() if k != "slug"
        }:
            raise ValueError("continuation changes an original package or setting")
        result = rail.collect_case(study, case)
        print(
            json.dumps(
                {
                    "case": case["original_case"],
                    "attempt": case["slug"],
                    "completed": result.get("completed"),
                    "error": result.get("error"),
                }
            ),
            flush=True,
        )
        if not result.get("completed"):
            break


def run(study, batch):
    load_batch(study, batch)
    telemetry = study / "raw/telemetry" / batch
    rail.freeze(
        telemetry / "driver.json",
        {
            "observed_at": rail.now(),
            "batch_sha256": rail.digest(study / "batches" / f"{batch}.json"),
            "driver_sha256": rail.digest(Path(__file__)),
            "sampler_sha256": rail.digest(SAMPLER),
        },
    )
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "collect",
        "--study",
        str(study),
        "--batch",
        batch,
    ]
    with (telemetry / "collector.log").open("x") as log:
        with subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT
        ) as collector:
            with subprocess.Popen(
                [
                    sys.executable,
                    str(SAMPLER),
                    str(collector.pid),
                    str(telemetry / "process-gpu.jsonl"),
                ]
            ) as monitor:
                status = collector.wait()
                monitor_status = monitor.wait(timeout=30)
    if status or monitor_status:
        raise SystemExit(status or monitor_status)


def retain(study, batch, evidence):
    frozen = load_batch(study, batch)
    paths = [study / "batches" / f"{batch}.json"]
    paths += list((study / "raw/telemetry" / batch).glob("*"))
    for case in frozen["cases"]:
        paths += list((study / "raw" / case["slug"]).glob("*"))
    records = []
    for path in sorted(paths):
        if not path.is_file():
            continue
        relative = path.relative_to(study)
        data = path.read_bytes()
        target = evidence / (str(relative) + ".gz")
        target.parent.mkdir(parents=True, exist_ok=True)
        compressed = gzip.compress(data, mtime=0)
        with target.open("xb") as stream:
            stream.write(compressed)
        import hashlib

        records.append(
            {
                "path": str(relative),
                "sha256": hashlib.sha256(data).hexdigest(),
                "gzip_sha256": hashlib.sha256(compressed).hexdigest(),
                "bytes": len(data),
            }
        )
    rail.freeze(
        evidence / "integrity.json",
        {
            "retained_at": rail.now(),
            "batch": batch,
            "driver_sha256": rail.digest(Path(__file__)),
            "initial_integrity_sha256": rail.digest(BASE / "integrity.json"),
            "files": records,
        },
    )


def unpack(evidence, manifest, target):
    import hashlib

    for record in manifest["files"]:
        relative = Path(record["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe retained path")
        compressed = (evidence / (str(relative) + ".gz")).read_bytes()
        data = gzip.decompress(compressed)
        if (
            hashlib.sha256(compressed).hexdigest() != record["gzip_sha256"]
            or hashlib.sha256(data).hexdigest() != record["sha256"]
            or len(data) != record["bytes"]
        ):
            raise ValueError("retained continuation bytes changed")
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)


def verify(evidence):
    initial_verify()
    manifest = json.loads((evidence / "integrity.json").read_text())
    if manifest["driver_sha256"] != rail.digest(Path(__file__)) or manifest[
        "initial_integrity_sha256"
    ] != rail.digest(BASE / "integrity.json"):
        raise ValueError("continuation source or initial integrity changed")
    with tempfile.TemporaryDirectory(prefix="rail-followup-") as directory:
        study = Path(directory)
        (study / "selection.json").write_bytes((BASE / "selection.json").read_bytes())
        unpack(BASE, json.loads((BASE / "integrity.json").read_text()), study)
        unpack(evidence, manifest, study)
        frozen = load_batch(study, manifest["batch"])
        driver = json.loads(
            (study / "raw/telemetry" / manifest["batch"] / "driver.json").read_text()
        )
        if (
            driver["batch_sha256"]
            != rail.digest(study / "batches" / f"{manifest['batch']}.json")
            or driver["driver_sha256"] != frozen["driver_sha256"]
            or driver["sampler_sha256"] != frozen["sampler_sha256"]
        ):
            raise ValueError("continuation driver is not bound to its pre-query batch")
        selection = json.loads((study / "selection.json").read_text())
        known = {
            case["artifact_sha256"]
            for case in selection["cohort"] + selection["controls"]
        }
        for path in (study / "raw").glob("*/observation.json"):
            if json.loads(path.read_text())["artifact_sha256"] not in known:
                raise ValueError("unselected package observation")
        control_end = max(
            json.loads((study / "raw" / c["slug"] / "observation.json").read_text())[
                "finished_at"
            ]
            for c in selection["controls"]
        )
        results = {}
        for case in selection["cohort"]:
            rows = []
            for slug, summary in attempts(study, case):
                observation = json.loads(
                    (study / "raw" / slug / "observation.json").read_text()
                )
                if any(observation.get("session", {}).get("cleanup", {}).values()):
                    raise ValueError("owned continuation cleanup failed")
                query = study / "raw" / slug / "query-freeze.json"
                if (
                    query.exists()
                    and json.loads(query.read_text())["frozen_at"] < control_end
                ):
                    raise ValueError("query precedes stock validation")
                if slug in {c["slug"] for c in frozen["cases"]} and query.exists():
                    if json.loads(query.read_text())["frozen_at"] < frozen["frozen_at"]:
                        raise ValueError("query precedes continuation freeze")
                if (
                    slug in {c["slug"] for c in frozen["cases"]}
                    and observation["observed_at"] < frozen["frozen_at"]
                ):
                    raise ValueError("continuation opening precedes batch freeze")
                if summary["completed"] and (
                    not query.exists()
                    or not summary["context_bound"]
                    or not {"game", "steam_instances", "units_active"}
                    <= observation.get("session", {}).get("cleanup", {}).keys()
                ):
                    raise ValueError(
                        "completed continuation is not bound and cleaned up"
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
            "initial_raw_files": len(
                json.loads((BASE / "integrity.json").read_text())["files"]
            ),
            "followup_raw_files": len(manifest["files"]),
            "cohort": results,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["prepare", "run", "collect", "retain", "verify"]
    )
    parser.add_argument("--study", type=Path)
    parser.add_argument("--batch", default="followup-1")
    parser.add_argument(
        "--evidence", type=Path, default=BASE.parent / "rail-v3-followup-1"
    )
    args = parser.parse_args()
    if args.action != "verify" and args.study is None:
        parser.error("--study is required")
    if args.action == "prepare":
        print(prepare(args.study, args.batch))
    elif args.action == "run":
        run(args.study, args.batch)
    elif args.action == "collect":
        collect(args.study, args.batch)
    else:
        if args.action == "retain":
            retain(args.study, args.batch, args.evidence)
        print(json.dumps(verify(args.evidence), indent=2))


if __name__ == "__main__":
    main()
