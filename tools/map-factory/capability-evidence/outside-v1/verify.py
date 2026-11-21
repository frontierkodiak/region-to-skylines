"""Verify committed evidence integrity; this does not substitute for native runs."""

import argparse
import datetime
import gzip
import hashlib
import json
import copy

from annotate import annotations, summary
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
            if (
                row.get("request")
                and row["capability_id"] != row["request"]["capability"]
            ):
                raise ValueError("path capability differs from raw request")
            result = row["path_result"]
            if (
                not result["complete"]
                or not result["released"]
                or result["success"] != row["observed"]
            ):
                raise ValueError("path observation is incomplete or was not released")
            if datetime.datetime.fromisoformat(row["observed_at"]).tzinfo is None:
                raise ValueError("native observation lacks a timezone")
    if annotations(copy.deepcopy(evidence)) != evidence:
        raise ValueError("derived annotations differ from raw evidence")
    markdown, cells = summary(evidence)
    if (HERE / "RESULTS.md").read_text() != markdown or json.loads(
        (HERE / "capability-summary.json").read_text()
    ) != cells:
        raise ValueError("summary differs from raw-derived rows")
    fresh_rows = {}
    for row in evidence["rows"]:
        if row["oracle_type"] != "native_path":
            continue
        if "archive_context" in row:
            report = json.loads(raw(row["raw_evidence"]))
            if row["path_result"] not in report[row["archive_context"]["phase"]]:
                raise ValueError("archived path differs from raw report")
            continue
        if row.get("raw_evidence"):
            fresh_rows.setdefault(row["raw_evidence"]["path"], []).append(row)
    for path, rows in fresh_rows.items():
        observation = json.loads(raw(rows[0]["raw_evidence"]))
        expected = observation.get("paths", [])
        actual = [row for row in rows if row["request"] is not None]
        if len(actual) != len(expected):
            raise ValueError("fresh raw requests missing or duplicated")
        for source in expected:
            matching = [row for row in actual if row["request"] == source["request"]]
            if len(matching) != 1:
                raise ValueError("fresh request not uniquely represented")
            row = matching[0]
            result = source.get("result", {})
            observed = result.get("success") if result.get("complete") else None
            if (
                row["request"] != source["request"]
                or row["path_result"] != result
                or row["observed"] != observed
                or row["error"] != source.get("error")
                or row["observed_at"] != observation["finished_at"]
            ):
                raise ValueError("fresh path row differs from raw observation")
    versions = {
        version["collector_sha256"]: version
        for version in evidence["collector_versions"]
    }
    for identity, version in versions.items():
        if digest(raw(version["raw_source"])) != identity:
            raise ValueError("collector source identity differs from retained source")
    runtime_bound_observations = []
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
            if observation.get("schema", 1) >= 2:
                version = versions[observation["collector_sha256"]]
                for name, source in version["dependencies"].items():
                    if digest(raw(source)) != observation["collector_sources"].get(
                        name
                    ):
                        raise ValueError(
                            "collector helper differs from retained source"
                        )
                if observation.get("completed"):
                    for mode, coverage in observation["candidate_coverage"].items():
                        executed = sum(
                            p["request"]["capability"] == mode
                            and p["request"]["name"] == "outside-to-outside"
                            for p in observation["paths"]
                        )
                        if (
                            executed != coverage["planned_requests"]
                            or executed > coverage["candidate_requests"]
                        ):
                            raise ValueError(
                                "native candidate coverage differs from raw requests"
                            )
            if observation.get("schema", 1) >= 2 and observation.get("completed"):
                protocol = observation.get("new_game_protocol", {})
                if (
                    protocol.get("update_mode") != "NewGameFromMap"
                    or protocol.get("invert_traffic") != "False"
                ):
                    raise ValueError("native New Game protocol is not bound")
                context = observation.get("native_context", {})
                if (
                    context.get("update_mode") != "NewGameFromMap"
                    or context.get("invert_traffic") != "False"
                    or context.get("no_workshop") is not True
                    or context.get("mods_enabled") is not True
                ):
                    raise ValueError("actual native simulation context is not bound")
                runtime = observation.get("runtime_identity", {})
                launch = observation.get("launch_runtime_identity", {})
                if not launch.get("build_matches") or (
                    launch.get("host_pid"),
                    launch.get("process_start_ticks"),
                ) != (runtime.get("host_pid"), runtime.get("process_start_ticks")):
                    raise ValueError(
                        "opening observation differs from the launch-bound process"
                    )
                if runtime != observation["session"].get("runtime_identity"):
                    raise ValueError("session and opening runtime identities differ")
                build = observation["build_receipt"]
                if not runtime.get("build_matches") or runtime.get(
                    "executable", {}
                ).get("sha256") != build.get("game_executable_sha256"):
                    raise ValueError("runtime executable is not bound to build")
                loaded = {
                    Path(a["path"]).name: a["sha256"] for a in runtime["assemblies"]
                }
                for name, expected in {
                    **build["game_assemblies"],
                    "Cs1Harness.dll": build["dll_sha256"],
                }.items():
                    if loaded.get(name) != expected:
                        raise ValueError(
                            "runtime assembly is not bound to build: " + name
                        )
                if (
                    "--noWorkshop" not in runtime["launch_args"]
                    or "--disableMods" in runtime["launch_args"]
                    or runtime["launch_args"] != observation["session"]["launch_args"]
                ):
                    raise ValueError("unbound native launch protocol")
                runtime_bound_observations.append(
                    {
                        "slug": case["slug"],
                        "attempt_id": attempt["attempt_id"],
                        "observation_sha256": ref["sha256"],
                        "artifact_sha256": case["artifact_sha256"],
                        "scope": "sampled_native_lane_paths_at_opening",
                    }
                )
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
        "runtime_bound_observations": runtime_bound_observations,
        "scope": "Data integrity and deterministic raster reproduction, not independent game reruns or geographic/service acceptance.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-nine-attempts", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.require_nine_attempts), indent=2))
