"""Post-control assembly correction: the contract-exact readiness bundle.

Why this tool exists, stated plainly:

- The pre-control `freeze.json` binds a *superset* of the versioned source
  closure (82 files: the study tree).  The accepted readiness contract requires
  `frozen.source_files` to be exactly the declared closure (its words: extra
  fields are errors).  Every file of the declared 30-file closure is present in
  the freeze with the same pre-control hash; this tool projects that subset and
  refuses if any current byte differs.
- The frozen `bundle_v2.py` passed the 82-file superset straight through and
  never retained the runtime file bytes the checker rehashes.

Neither is a measurement fact, request, prediction, selection, label, schema or
checker change.  This tool measures nothing, opens no game and edits no frozen
file.  It re-runs the unchanged version-3 checker over retained bytes and
records both source digests so the projection is auditable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import stock_v2 as study

import schema
import schema_v3
from evidence import ArtifactStore
from readiness import Readiness
from schema import POLICY, consumed_values
import readiness_v3

CONTRACT = tuple(sorted(schema_v3.SOURCE_KEYS_V3))


def put(root: Path, data: bytes) -> str:
    key = hashlib.sha256(data).hexdigest()
    path = root / key
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != key:
            raise ValueError(f"corrupt retained artifact {key}")
    else:
        path.write_bytes(data)
    return key


def put_file(root: Path, path: Path) -> str:
    return put(root, Path(path).read_bytes())


def control_plans(case):
    return [
        {k: row[k] for k in ("query_id", "mode", "kind", "max_length", "request")}
        for row in case["requests"]
    ]


def build(raw: Path, evidence: Path):
    freeze = study.read(study.HERE / "freeze.json")
    if not set(CONTRACT) <= set(freeze["source_files"]):
        raise ValueError("frozen source manifest does not contain the contract closure")
    closure = {name: freeze["source_files"][name] for name in CONTRACT}
    for name, hashed in closure.items():
        actual = hashlib.sha256((study.ROOT / name).read_bytes()).hexdigest()
        if actual != hashed:
            raise ValueError(f"contract source changed after the freeze: {name}")
    evidence.mkdir(parents=True, exist_ok=True)
    for name in closure:
        put_file(evidence, study.ROOT / name)
    source_hash = put(evidence, study.canonical(closure))
    protocol = freeze["protocol"]
    protocol_hash = put(evidence, study.canonical(protocol))
    controls = []
    observations = {}
    policies = []
    for case in freeze["controls"]:
        opening = study.read(raw / case["case_id"] / "opening.json")
        if not opening.get("completed") or opening.get("error"):
            raise ValueError(f"{case['case_id']}: control opening incomplete")
        policies.append(opening["policy"])
        plans = control_plans(case)
        request_hash = put(evidence, study.canonical(plans))
        predictions = {
            row["query_id"]: case["predictions"][row["query_id"]]
            for row in case["requests"]
        }
        prediction_hash = put(evidence, study.canonical(predictions))
        graph_path = raw / case["case_id"] / "graph-opening.json"
        graph_hash = put_file(evidence, graph_path)
        graph = study.read(graph_path)
        coverage = {}
        for field, values in consumed_values(graph, closure, plans, protocol).items():
            coverage[field] = put(
                evidence,
                study.canonical(
                    {
                        "field": field,
                        "graph_sha256": graph_hash,
                        "source_sha256": source_hash,
                        "values": values,
                    }
                ),
            )
        artifact_hash = put_file(evidence, Path(case["locator"]))
        if artifact_hash != case["sha256"]:
            raise ValueError("control package hash differs")
        frozen = {
            "case_id": case["case_id"],
            "requests": plans,
            "consumed_fields": coverage,
            "exact_graph_sha256": graph_hash,
            "source_files": closure,
            "predictions": predictions,
            "artifact_sha256": artifact_hash,
            "source_sha256": source_hash,
            "request_sha256": request_hash,
            "prediction_sha256": prediction_hash,
            "protocol_sha256": protocol_hash,
        }
        observed = {k: frozen[k] for k in (
            "artifact_sha256",
            "source_sha256",
            "request_sha256",
            "prediction_sha256",
            "protocol_sha256",
            "consumed_fields",
        )}
        post_hash = put_file(evidence, raw / case["case_id"] / "graph-post.json")
        paths = []
        for row in opening["paths"]:
            if row.get("error"):
                raise ValueError(f"{case['case_id']}: control query errored")
            paths.append(
                {
                    "plan": row["plan"],
                    "pre_build_index": row["pre_build_index"],
                    "pre_graph": put_file(
                        evidence,
                        raw / case["case_id"] / f"graph-pre-{row['plan']['query_id'].replace('/', '_')}.json",
                    ),
                    "post_graph": put_file(
                        evidence,
                        raw / case["case_id"] / f"graph-post-{row['plan']['query_id'].replace('/', '_')}.json",
                    ),
                    "pre_context": row["pre_context"],
                    "post_context": row["post_context"],
                    "effective": row["effective"],
                    "result": row["result"],
                    "error": None,
                }
            )
        observed.update(
            completed=opening["completed"],
            error=None,
            session_id=opening["session_id"],
            native_context=opening["native_context"],
            opening_graph=graph_hash,
            post_graph=post_hash,
            runtime=opening["runtime"],
            owned_processes={
                role: {"pid": record["pid"], "start_ticks": record["start_ticks"], "gone": record["gone"]}
                for role, record in opening["cleanup"].items()
            },
            cleanup={
                role: {"pid": record["pid"], "start_ticks": record["start_ticks"], "gone": record["gone"]}
                for role, record in opening["cleanup"].items()
            },
            paths=paths,
        )
        controls.append(frozen)
        observations[case["case_id"]] = observed
    first = policies[0]
    policy = {key: first[key] for key in POLICY if key in first}
    policy["process_roles"] = ["game", "driver", "collector", "auditor", "monitor"]
    if set(policy) != POLICY:
        raise ValueError(f"policy key set differs: {sorted(set(POLICY) ^ set(policy))}")
    for other in policies[1:]:
        for key in set(POLICY) - {"process_roles"}:
            if other[key] != policy[key]:
                raise ValueError(f"runtime policy differs between controls: {key}")
    # Retain the licensed runtime bytes the checker rehashes.  They stay in the
    # same-owner private holding; only their hashes enter the repository.
    fallback = {}
    built = study.read(study.HERE / "freeze.json")["build"]["dll"]
    fallback[policy["dll_sha256"]] = Path(built["path"])
    for name, hashed in policy["files"].items():
        source = Path(name)
        if not source.exists():
            source = fallback.get(hashed)
            if source is None or not source.exists():
                raise ValueError(f"retained runtime bytes unavailable: {name}")
        actual = put_file(evidence, source)
        if actual != hashed:
            raise ValueError(f"runtime file bytes differ from the measured inventory: {name}")
    for name, assembly in policy["assemblies"].items():
        source = Path(assembly["path"])
        if not source.exists():
            source = fallback.get(assembly["sha256"])
        if source is None or not source.exists():
            raise ValueError(f"retained assembly bytes unavailable: {name}")
        if put_file(evidence, source) != assembly["sha256"]:
            raise ValueError(f"assembly bytes differ: {name}")
    put_file(evidence, Path(policy["executable_path"]))
    bundle = {
        "version": 2,
        "controls": controls,
        "observations": observations,
        "policy": policy,
        "prior_sessions": freeze["prior_sessions"],
    }
    path = study.HERE / "bundle.json"
    study.write(path, bundle)
    result = readiness_v3.check(
        bundle["controls"],
        bundle["observations"],
        bundle["policy"],
        set(bundle["prior_sessions"]),
        ArtifactStore(evidence),
    )
    return bundle, result, source_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    bundle, result, source_hash = build(args.raw, args.evidence)
    record = {
        "ready_for_measurement": result.ready_for_measurement,
        "pre_export_qualification": result.pre_export_qualification,
        "reasons": list(result.reasons),
        "missing_native_fact": result.missing_native_fact,
        "bundle_sha256": study.sha(study.HERE / "bundle.json"),
        "evidence_root": str(args.evidence),
        "contract_source_sha256": source_hash,
        "study_source_sha256": study.read(study.HERE / "freeze.json")["source_sha256"],
        "contract_source_files": len(CONTRACT),
        "study_source_files": len(study.read(study.HERE / "freeze.json")["source_files"]),
        "assembler_sha256": study.sha(Path(__file__).resolve()),
        "scope": "post-control assembly correction only; no measurement or contract change",
    }
    study.write(args.raw / "readiness-result.json", record)
    print(study.canonical(record).decode())
    return 0 if result.ready_for_measurement else 2


if __name__ == "__main__":
    raise SystemExit(main())
