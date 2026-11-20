"""Verify committed evidence integrity; this does not substitute for native runs."""

import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from water_support import support

HERE = Path(__file__).resolve().parent


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(require_nine_attempts=False):
    evidence_path = HERE / "evidence.json"
    evidence = json.loads(evidence_path.read_text())
    checked = {}

    def raw(ref):
        path = ref["path"]
        if path not in checked:
            value = gzip.decompress((HERE / path).read_bytes())
            if digest(value) != ref["sha256"]:
                raise ValueError(f"raw evidence changed: {path}")
            checked[path] = value
        elif digest(checked[path]) != ref["sha256"]:
            raise ValueError(f"conflicting raw evidence hash: {path}")
        return checked[path]

    def refs(value):
        if isinstance(value, dict):
            if value.get("encoding") == "gzip":
                raw(value)
            for child in value.values():
                refs(child)
        elif isinstance(value, list):
            for child in value:
                refs(child)

    refs(evidence)
    if evidence["agreement"] is not None:
        raise ValueError("this study has no aggregate agreement metric")
    cases = {case["slug"]: case for case in evidence["artifacts"]}
    if len(cases) != 9:
        raise ValueError("fixed nine-square cohort changed")
    for row in evidence["rows"]:
        if row["capability_id"] not in {"road", "rail", "ship", "air"}:
            raise ValueError("unknown capability")
        if row["observed"] is not None and type(row["observed"]) is not bool:
            raise ValueError("observed must be true, false or null")
        if row["artifact_sha256"] != cases[row["slug"]]["artifact_sha256"]:
            raise ValueError("row belongs to another package")
        if (
            row["oracle_type"] in {"actual_service", "geographic_impossibility"}
            and row["observed"] is not None
        ):
            raise ValueError("unmeasured service/geographic claims cannot be promoted")
        if row["oracle_type"] == "native_path" and row["observed"] is not None:
            result = row["path_result"]
            if (
                not result["complete"]
                or not result["released"]
                or result["success"] != row["observed"]
            ):
                raise ValueError("path observation is incomplete or was not released")
            if datetime.datetime.fromisoformat(row["observed_at"]).tzinfo is None:
                raise ValueError("native observation lacks a timezone")
    versions = {
        version["collector_sha256"]: version
        for version in evidence["collector_versions"]
    }
    seen_attempts = set()
    attempts = 0
    covered_cases = 0
    for case in cases.values():
        case_attempts = case.get(
            "attempts", [case] if case["observation_evidence"] else []
        )
        covered_cases += bool(case_attempts)
        for attempt in case_attempts:
            ref = attempt["observation_evidence"]
            attempts += 1
            observation = json.loads(raw(ref))
            if observation["artifact_sha256"] != case["artifact_sha256"]:
                raise ValueError("native collector belongs to another package")
            identity = (
                observation["artifact_sha256"],
                observation["observed_at"],
                observation["finished_at"],
            )
            if identity in seen_attempts:
                raise ValueError("the same native attempt was imported twice")
            seen_attempts.add(identity)
            if observation["collector_sha256"] not in versions:
                raise ValueError(
                    "native collector source has no retained version binding"
                )
            if "session" in observation and any(
                observation["session"].get("cleanup", {}).values()
            ):
                raise ValueError("native session did not clean up")
            if observation.get("completed"):
                session = observation["session"]
                if session["map"]["sha256"] != case["artifact_sha256"]:
                    raise ValueError("installed package differs from observed package")
                if session["mod_sha256"] != observation["build_receipt"]["dll_sha256"]:
                    raise ValueError(
                        "installed native mod differs from the recorded build"
                    )
                if any(session["cleanup"].values()):
                    raise ValueError("native session did not clean up")
        reproduction_ref = case["reproduction_evidence"]
        if reproduction_ref:
            reproduced = json.loads(raw(reproduction_ref))["cases"][case["slug"]]
            if not reproduced["baseline_comparison"]["package_unchanged"]:
                raise ValueError("archived package did not reproduce")
            if reproduced["generation"]["package"]["sha256"] != case["artifact_sha256"]:
                raise ValueError("reproduction package differs")
    if require_nine_attempts and covered_cases != 9:
        raise ValueError(
            f"only {covered_cases}/9 selected squares have a native attempt retained"
        )
    water_path = HERE / "water-support.json"
    water = json.loads(water_path.read_text())
    refs(water)
    for row in water["rows"]:
        if row["artifact_sha256"] != cases[row["slug"]]["artifact_sha256"]:
            raise ValueError("water bound belongs to another package")
        risk = json.loads(raw(cases[row["slug"]]["water_risk_evidence"]))
        if risk["inputs_sha256"]["water.u16"] != row["water_sha256"]:
            raise ValueError("water bound differs from unchanged water-risk input")
        depth = np.frombuffer(raw(row["raw_evidence"]), dtype="<u2").reshape(1081, 1081)
        if [support(depth, stride) for stride in [1, 4]] != row["rasters"]:
            raise ValueError("prepared-water bound does not reproduce")
    return {
        "evidence_sha256": digest(evidence_path.read_bytes()),
        "water_support_sha256": digest(water_path.read_bytes()),
        "rows": len(evidence["rows"]),
        "raw_files_verified": len(checked),
        "native_attempts": attempts,
        "selected_squares_attempted": covered_cases,
        "native_completed": sum(case["completed"] for case in cases.values()),
        "scope": "Data integrity and deterministic raster reproduction, not independent game reruns or geographic/service acceptance.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-nine-attempts", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.require_nine_attempts), indent=2))
