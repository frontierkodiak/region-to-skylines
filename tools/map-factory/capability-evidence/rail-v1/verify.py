"""Retain or verify PL-1215 raw bytes without modifying the original study."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tempfile

from cs1_harness import rail_study

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def retain(native):
    selection = (native / "selection.json").read_bytes()
    with (HERE / "selection.json").open("xb") as stream:
        stream.write(selection)
    records = []
    for path in sorted((native / "raw").rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(native)
        data = path.read_bytes()
        target = HERE / (str(relative) + ".gz")
        target.parent.mkdir(parents=True, exist_ok=True)
        compressed = gzip.compress(data, mtime=0)
        with target.open("xb") as stream:
            stream.write(compressed)
        records.append(
            {
                "path": str(relative),
                "sha256": sha(data),
                "bytes": len(data),
                "gzip_sha256": sha(compressed),
            }
        )
    rail_study.freeze(
        HERE / "integrity.json",
        {
            "retained_at": rail_study.now(),
            "selection_sha256": sha(selection),
            "verifier_sha256": rail_study.digest(Path(__file__)),
            "files": records,
        },
    )


def verify():
    integrity = json.loads((HERE / "integrity.json").read_text())
    selection = json.loads((HERE / "selection.json").read_text())
    if (
        rail_study.digest(HERE / "selection.json") != integrity["selection_sha256"]
        or rail_study.digest(Path(__file__)) != integrity["verifier_sha256"]
        or selection["sources"] != rail_study.sources()
    ):
        raise ValueError("selection, verifier or native source changed")
    original = (
        rail_study.ROOT
        / "tools/map-factory/capability-evidence/outside-v1/selection.json"
    )
    if (
        rail_study.digest(original) != selection["original_selection_sha256"]
        or json.loads(original.read_text())["cases"] != selection["cohort"]
    ):
        raise ValueError("original nine-package cohort changed")
    with tempfile.TemporaryDirectory(prefix="rail-verify-") as directory:
        unpacked = Path(directory)
        (unpacked / "selection.json").write_bytes(
            (HERE / "selection.json").read_bytes()
        )
        for record in integrity["files"]:
            relative = Path(record["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("invalid raw path")
            compressed = (HERE / (str(relative) + ".gz")).read_bytes()
            data = gzip.decompress(compressed)
            if (
                sha(compressed) != record["gzip_sha256"]
                or sha(data) != record["sha256"]
                or len(data) != record["bytes"]
            ):
                raise ValueError(f"raw bytes changed: {relative}")
            target = unpacked / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        results = {}
        for driver_path in unpacked.glob("raw/telemetry/*/driver.json"):
            driver = json.loads(driver_path.read_text())
            if (
                driver["selection_sha256"] != integrity["selection_sha256"]
                or driver["driver_sha256"]
                != rail_study.digest(Path(__file__).with_name("run_foreground.py"))
                or driver["sampler_sha256"]
                != rail_study.digest(
                    Path(__file__).parent.parent / "outside-v1/sample_gpu.py"
                )
            ):
                raise ValueError(
                    "foreground driver or telemetry source differs from its pre-query receipt"
                )
        stock_gate = rail_study.controls_valid(unpacked)
        control_end = max(
            (
                json.loads(
                    (unpacked / "raw" / case["slug"] / "observation.json").read_text()
                ).get("finished_at", "")
                for case in selection["controls"]
                if (unpacked / "raw" / case["slug"] / "observation.json").exists()
            ),
            default="",
        )
        for group in ("controls", "cohort"):
            results[group] = {}
            for case in selection[group]:
                case_dir = unpacked / "raw" / case["slug"]
                if not (case_dir / "observation.json").exists():
                    results[group][case["slug"]] = {"status": "Unknown/not_run"}
                    continue
                result = rail_study.summarize(case_dir, unpacked / "selection.json")
                if case["artifact_sha256"] != result["artifact_sha256"]:
                    raise ValueError("observation package differs from selection")
                observation = json.loads((case_dir / "observation.json").read_text())
                if group == "cohort" and (case_dir / "query-freeze.json").exists():
                    frozen = json.loads((case_dir / "query-freeze.json").read_text())
                    if not stock_gate or frozen["frozen_at"] < control_end:
                        raise ValueError(
                            "cohort query freeze predates stock-positive validation"
                        )
                elif group == "cohort" and (
                    observation.get("completed") or observation.get("paths")
                ):
                    raise ValueError(
                        "cohort paths lack a frozen stock-validated protocol"
                    )
                if observation["observed_at"] < selection["frozen_at"]:
                    raise ValueError("opening predates prelaunch freeze")
                session = observation.get("session", {})
                if any(session.get("cleanup", {}).values()):
                    raise ValueError("owned session cleanup failed")
                if (
                    observation.get("completed")
                    and not {"game", "steam_instances", "units_active"}
                    <= session.get("cleanup", {}).keys()
                ):
                    raise ValueError("completed observation lacks session teardown")
                results[group][case["slug"]] = result
        return {
            "stock_gate": stock_gate,
            "raw_files": len(integrity["files"]),
            **results,
        }


def main():
    global HERE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retain", type=Path)
    parser.add_argument("--evidence", type=Path, default=rail_study.STUDY)
    args = parser.parse_args()
    HERE = args.evidence.resolve()
    if args.retain:
        retain(args.retain)
    print(json.dumps(verify(), indent=2))


if __name__ == "__main__":
    main()
