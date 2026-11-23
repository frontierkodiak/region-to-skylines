"""Assemble the byte-backed readiness bundle from the two control openings.

The bundle contains hashes and measured facts only.  Required licensed game
bytes for replay are retained in the same-owner private experiment holding
named by `--evidence`; they are never copied into the repository or posted to
the issue.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import stock_v2 as study
from evidence import ArtifactStore
from readiness import Readiness
from schema import POLICY, consumed_values
import readiness_v3


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


def control_plans(frozen_case):
    return [
        {k: row[k] for k in ("query_id", "mode", "kind", "max_length", "request")}
        for row in frozen_case["requests"]
    ]


def build(raw: Path, evidence: Path):
    freeze = study.read(study.HERE / "freeze.json")
    root = study.ROOT
    evidence.mkdir(parents=True, exist_ok=True)
    sources = freeze["source_files"]
    for name in sources:
        put_file(evidence, root / name)
    source_hash = put(evidence, study.canonical(sources))
    if source_hash != freeze["source_sha256"]:
        raise ValueError("source manifest bytes differ from frozen digest")
    protocol = freeze["protocol"]
    protocol_hash = put(evidence, study.canonical(protocol))
    policies = []
    controls = []
    observations = {}
    for case in freeze["controls"]:
        opening = study.read(raw / case["case_id"] / "opening.json")
        if not opening.get("completed") or opening.get("error"):
            raise ValueError(f"{case['case_id']}: control opening incomplete")
        policies.append(opening["policy"])
        plans = control_plans(case)
        request_hash = put(evidence, study.canonical(plans))
        predictions = {row["query_id"]: case["predictions"][row["query_id"]] for row in case["requests"]}
        prediction_hash = put(evidence, study.canonical(predictions))
        graph_path = raw / case["case_id"] / "graph-opening.json"
        graph_hash = put_file(evidence, graph_path)
        graph = study.read(graph_path)
        coverage = {}
        for field, values in consumed_values(graph, sources, plans, protocol).items():
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
            "source_files": sources,
            "predictions": predictions,
            "artifact_sha256": artifact_hash,
            "source_sha256": source_hash,
            "request_sha256": request_hash,
            "prediction_sha256": prediction_hash,
            "protocol_sha256": protocol_hash,
        }
        observed = {key: frozen[key] for key in (
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
            entry = {
                "plan": row["plan"],
                "pre_build_index": row["pre_build_index"],
                "pre_graph": put_file(evidence, raw / case["case_id"] / _graph_name("pre", row["plan"]["query_id"])),
                "post_graph": put_file(evidence, raw / case["case_id"] / _graph_name("post", row["plan"]["query_id"])),
                "pre_context": row["pre_context"],
                "post_context": row["post_context"],
                "effective": row["effective"],
                "result": row["result"],
                "error": None,
            }
            paths.append(entry)
        observed.update(
            completed=opening["completed"],
            error=opening.get("error"),
            session_id=opening["session_id"],
            native_context=opening["native_context"],
            opening_graph=graph_hash,
            post_graph=post_hash,
            runtime=opening["runtime"],
            owned_processes=opening["owned_processes"],
            cleanup=opening["cleanup"],
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
    bundle = {
        "version": 2,
        "controls": controls,
        "observations": observations,
        "policy": policy,
        "prior_sessions": freeze["prior_sessions"],
    }
    _check_expected_policy(policy, freeze["expected_policy"])
    path = study.HERE / "bundle.json"
    study.write(path, bundle)
    result = readiness_v3.check(
        bundle["controls"],
        bundle["observations"],
        bundle["policy"],
        set(bundle["prior_sessions"]),
        ArtifactStore(evidence),
    )
    study.write(
        raw / "readiness-result.json",
        {
            "ready_for_measurement": result.ready_for_measurement,
            "reasons": list(result.reasons),
            "pre_export_qualification": result.pre_export_qualification,
            "missing_native_fact": result.missing_native_fact,
            "bundle_sha256": study.sha(path),
            "evidence_root": str(evidence),
        },
    )
    return bundle, result


def _check_expected_policy(policy, expected):
    exe = Path(policy["executable_path"])
    if exe.name != expected["executable_name"]:
        raise ValueError("unexpected executable name")
    game = exe.parent
    for role, suffix in expected["root_suffixes"].items():
        if Path(policy["roots"][role]["path"]) != game / suffix:
            raise ValueError(f"unexpected {role} root")
    if not str(policy["roots"]["user_mods"]["path"]).endswith(expected["user_mods_suffix"]):
        raise ValueError("unexpected user Mods root")
    if expected["harness_plugin"] not in policy["plugins"]:
        raise ValueError("harness plugin missing from policy")
    if expected["harness_assembly"] not in policy["assemblies"]:
        raise ValueError("harness assembly missing from policy")
    if set(policy["process_roles"]) != set(expected["process_roles"]):
        raise ValueError("unexpected process role set")
    if policy["protocol_sha256"] != study.digest(expected["protocol"]):
        raise ValueError("frozen protocol digest differs")
    if sorted(policy["excluded_dynamic"]) != sorted(expected["excluded_dynamic"]):
        raise ValueError("unexpected dynamic exclusion set")


def _graph_name(phase, query_id):
    return f"graph-{phase}-{query_id.replace('/', '_')}.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    bundle, result = build(args.raw, args.evidence)
    print(
        study.encoded(
            {
                "ready_for_measurement": result.ready_for_measurement,
                "pre_export_qualification": result.pre_export_qualification,
                "reasons": list(result.reasons),
                "controls": [c["case_id"] for c in bundle["controls"]],
            }
        ).decode()
    )
    raise SystemExit(0 if result.ready_for_measurement else 2)


if __name__ == "__main__":
    raise SystemExit(main())
