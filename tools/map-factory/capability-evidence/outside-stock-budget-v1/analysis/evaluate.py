"""Strict request-fidelity scoring; controls, holdout, intervention stay separate."""

from __future__ import annotations

import argparse
import collections
import subprocess
from pathlib import Path

import study
import collect


def wire_schema_matches(record, body_keys):
    return (
        isinstance(record, dict)
        and set(record) == set(body_keys) | {"ok"}
        and record.get("ok") is True
    )


def label(row):
    result = row.get("result", {})
    if (
        row.get("error")
        or result.get("complete") is not True
        or result.get("released") is not True
    ):
        return "unknown"
    if result.get("success") is False:
        return "no_path"
    positions = result.get("positions")
    request = row["plan"]["request"]
    if (
        result.get("success") is True
        and isinstance(positions, list)
        and positions
        and positions[0] == request["from"]
        and positions[-1] == request["to"]
    ):
        return "success"
    return "unknown"


def controls_from_observations(frozen, observations):
    result = {}
    all_controls_complete = bool(frozen["controls"]) and all(
        observations.get(c["case_id"], {}).get("completed") for c in frozen["controls"]
    )
    for mode in study.MODES:
        rows = [
            r
            for case in frozen["controls"]
            for r in observations.get(case["case_id"], {}).get("paths", [])
            if r["plan"]["mode"] == mode
        ]
        positives = [label(r) for r in rows if r["plan"]["kind"] == "positive"]
        invalid = [label(r) for r in rows if r["plan"]["kind"] == "invalid-vehicle"]
        result[mode] = {
            "qualified": bool(
                all_controls_complete
                and positives
                and invalid
                and all(v == "success" for v in positives)
                and all(v == "no_path" for v in invalid)
            ),
            "positive_labels": positives,
            "invalid_vehicle_labels": invalid,
            "unavailable": {
                c["case_id"]: c["unavailable"][mode]
                for c in frozen["controls"]
                if mode in c["unavailable"]
            },
        }
        if result[mode]["unavailable"]:
            result[mode]["qualified"] = False
    return result


def metrics(rows):
    counts = dict.fromkeys(
        ["TP", "FP", "TN", "FN", "null_prediction", "unknown_label"], 0
    )
    for prediction, actual in rows:
        if prediction not in ("success", "no_path"):
            counts["null_prediction"] += 1
        elif actual == "unknown":
            counts["unknown_label"] += 1
        else:
            key = {
                ("success", "success"): "TP",
                ("success", "no_path"): "FP",
                ("no_path", "no_path"): "TN",
                ("no_path", "success"): "FN",
            }[(prediction, actual)]
            counts[key] += 1
    counts["n"] = len(rows)
    counts["precision"] = (
        counts["TP"] / (counts["TP"] + counts["FP"])
        if counts["TP"] + counts["FP"]
        else None
    )
    counts["recall"] = (
        counts["TP"] / (counts["TP"] + counts["FN"])
        if counts["TP"] + counts["FN"]
        else None
    )
    counts["prediction_coverage"] = (
        (len(rows) - counts["null_prediction"]) / len(rows) if rows else None
    )
    counts["absent_class_power"] = not (
        counts["TP"] + counts["FN"] and counts["TN"] + counts["FP"]
    )
    return counts


def read_observation(case, kind, raw, frozen):
    out = raw / case["case_id"]
    path = out / "observation.json"
    if not path.exists():
        return {"case_id": case["case_id"], "missing": True, "paths": []}
    obs = study.read(path)
    if obs["freeze_sha256"] != study.sha(study.HERE / "freeze.json"):
        allowed = frozen.get("retained_prequery_failures", {}).get(case["case_id"])
        if (
            not allowed
            or study.sha(path) != allowed["observation_sha256"]
            or obs["freeze_sha256"] != allowed["freeze_sha256"]
            or obs["paths"]
            or obs["completed"]
        ):
            raise ValueError("unbound historical observation")
    if obs["artifact_sha256"] != case["sha256"] or obs["protocol"] != study.PROTOCOL:
        raise ValueError("raw package/freeze/protocol differs")
    expected = collect.requests_for(case, kind)
    recorded = [r["plan"] for r in obs["paths"]]
    if recorded != expected[: len(recorded)] or len(recorded) > len(expected):
        raise ValueError("raw requests differ from exact ordered plan")
    if obs["completed"] and recorded != expected:
        raise ValueError("completed opening omitted a query")
    if (out / "query-freeze.json").exists():
        q = study.read(out / "query-freeze.json")
        if set(q) != set(study.PROTOCOL["query_freeze_schema"]):
            raise ValueError("query-freeze schema differs")
        committed = subprocess.check_output(
            [
                "git",
                "show",
                f"{q['pre_query_commit']}:{(study.HERE / 'freeze.json').relative_to(study.ROOT)}",
            ],
            cwd=study.ROOT,
        )
        if committed != (study.HERE / "freeze.json").read_bytes():
            raise ValueError("pre-query commit does not bind this freeze")
        if (
            obs["query_freeze_sha256"] != study.sha(out / "query-freeze.json")
            or q["requests"] != expected
            or q["freeze_sha256"] != obs["freeze_sha256"]
            or q["build_sha256"] != frozen["build_sha256"]
        ):
            raise ValueError("query freeze binding differs")
        if (
            study.sha(out / "networks.json") != q["networks_sha256"]
            or collect.graph(study.read(out / "networks.json")) != q["opening_graph"]
        ):
            raise ValueError("opening snapshot binding differs")
        if q["frozen_at"] < frozen["frozen_at"]:
            raise ValueError("query freeze predates study freeze")
        for row in obs["paths"]:
            if row["submitted_at"] < q["frozen_at"]:
                raise ValueError("query predates freeze")
            result = row.get("result")
            if result and not wire_schema_matches(
                result, study.PROTOCOL["result_schema"]
            ):
                raise ValueError("native result schema differs")
            effective = row.get("effective")
            if effective:
                if not wire_schema_matches(
                    effective, study.PROTOCOL["effective_schema"]
                ):
                    raise ValueError("effective API schema differs")
                mode = row["plan"]["mode"]
                if (
                    effective["max_length"] != row["plan"]["max_length"]
                    or effective["seed"] != 857
                    or effective["mode"] != study.MODES[mode]
                    or effective["vehicle"] != study.topology.VEHICLE[mode]
                    or effective["category"] != study.topology.CATEGORY_BY_MODE[mode]
                    or set(effective["lane_types"].split(", "))
                    != set(study.PROTOCOL["lane_types"][mode])
                ):
                    raise ValueError("effective API arguments differ")
                if (
                    effective["from"] != row["plan"]["request"]["from"]
                    or effective["to"] != row["plan"]["request"]["to"]
                ):
                    raise ValueError("effective request endpoints differ")
            row["snapshot_matched"] = (
                row.get("pre_graph") == row.get("post_graph") == q["opening_graph"]
            )
        obs["opening_post_graph_equal"] = (
            out / "networks-post.json"
        ).exists() and collect.graph(study.read(out / "networks-post.json")) == q[
            "opening_graph"
        ]
    # Coverage must include every runtime/GPU observed identity, not just no leftovers.
    observed = {(r["pid"], r["start_ticks"]) for r in obs["observed_game_processes"]}
    covered = {(r["pid"], r["start_ticks"]) for r in obs["game_cleanup_coverage"]}
    runtime = {
        (r["host_pid"], r["process_start_ticks"])
        for k, r in obs.items()
        if k.endswith("runtime_identity")
    }
    gpu_pids = {r["pid"] for r in obs.get("session", {}).get("game_gpu", [])}
    obs["cleanup_coverage_valid"] = (
        observed == covered
        and runtime <= covered
        and gpu_pids <= {p for p, _ in covered}
        and not any(r["still_running"] for r in obs["game_cleanup_coverage"])
    )
    if obs["completed"] and (not runtime or not obs["cleanup_coverage_valid"]):
        raise ValueError("completed observation lacks process cleanup coverage")
    for k in ["launch_runtime_identity", "runtime_identity", "post_runtime_identity"]:
        if k in obs:
            from cs1_harness.runtime_identity import validate_identity

            validate_identity(
                obs[k], study.read(study.HERE / "build.json")["build_receipt"]
            )
    return obs


def bridge_differences(case, obs, raw):
    path = raw / case["case_id"] / "networks.json"
    if not path.exists() or not case.get("supported"):
        return {
            "supported": case.get("supported"),
            "reason": "unsupported or no opening; predictions remain null",
            "by_mode": {},
        }
    package, _ = study.build_package(case["locator"], study.fixed_catalog())
    native = study.native_package(study.read(path))
    result = {}
    for mode in study.MODES:
        expected = study.model_fields(package, mode)
        actual = study.model_fields(native, mode)
        by_expected = {r["id"]: r for r in expected}
        by_actual = {r["id"]: r for r in actual}
        mismatches = []
        for sid in sorted(set(by_expected) | set(by_actual)):
            a, b = by_expected.get(sid), by_actual.get(sid)
            if a != b:
                fields = sorted(
                    k
                    for k in set(a or {}) | set(b or {})
                    if (a or {}).get(k) != (b or {}).get(k)
                )
                mismatches.append(
                    {"segment": sid, "fields": fields, "export": a, "native": b}
                )
        result[mode] = {
            "exact_equal": not mismatches,
            "export_sha256": study.digest(expected),
            "native_sha256": study.digest(actual),
            "mismatches": mismatches,
        }
    return {"supported": True, "by_mode": result}


def evaluate(raw):
    frozen = study.read(study.HERE / "freeze.json")
    study.check()
    observations = {
        c["case_id"]: read_observation(c, k, raw, frozen)
        for c, k in collect.cases(frozen)
    }
    driver_cleanup = []
    for case, _ in collect.cases(frozen):
        folder = raw / "drivers" / case["case_id"]
        if not (folder / "launch.json").exists():
            driver_cleanup.append({"case_id": case["case_id"], "missing": True})
            continue
        launch = study.read(folder / "launch.json")
        completion = (
            study.read(folder / "completion.json")
            if (folder / "completion.json").exists()
            else None
        )
        obs = observations[case["case_id"]]
        if obs.get("collector") and obs["collector"] != launch["collector"]:
            # State can change R/S; PID plus start identity cannot.
            if (obs["collector"]["pid"], obs["collector"]["start_ticks"]) != (
                launch["collector"]["pid"],
                launch["collector"]["start_ticks"],
            ):
                raise ValueError("collector identity differs")
        if completion is None or completion["collector"] != launch["collector"]:
            raise ValueError("collector completion coverage missing")
        alive = any(collect.still_running(launch[k]) for k in ["collector", "driver"])
        driver_cleanup.append(
            {
                "case_id": case["case_id"],
                "collector": launch["collector"],
                "driver": launch["driver"],
                "still_running": alive,
                "returncode": completion["returncode"],
            }
        )
        if alive or completion["collector_still_running"]:
            raise ValueError("observed collector/driver remains alive")
    bridges = {
        c["case_id"]: bridge_differences(c, observations[c["case_id"]], raw)
        for c in frozen["selected"]
    }
    qualification = controls_from_observations(frozen, observations)
    groups = collections.defaultdict(list)
    disagreements, holdout_rows = [], []
    for case in frozen["selected"]:
        obs = observations[case["case_id"]]
        by_id = {r["plan"]["query_id"]: r for r in obs["paths"]}
        for mode, inputs in case["modes"].items():
            if not inputs["selected"]:
                holdout_rows.append(
                    {
                        "case_id": case["case_id"],
                        "mode": mode,
                        "prediction": None,
                        "label": "unknown",
                        "reason": inputs["reason"] or "empty_query_stratum",
                    }
                )
            for query in inputs["selected"]:
                actual_row = by_id.get(query["query_id"])
                actual = label(actual_row) if actual_row else "unknown"
                for rule in study.RULES:
                    prediction = query["rules"][rule]["prediction"]
                    row = {
                        "case_id": case["case_id"],
                        "mode": mode,
                        "query_id": query["query_id"],
                        "rule": rule,
                        "prediction": prediction,
                        "label": actual,
                        "snapshot_matched": actual_row.get("snapshot_matched", False)
                        if actual_row
                        else False,
                        "qualified_mode": qualification[mode]["qualified"],
                        "selection_reasons": case["selection_reasons"],
                    }
                    row["snapshot_matched"] = row["snapshot_matched"] and bridges[
                        case["case_id"]
                    ]["by_mode"].get(mode, {}).get("exact_equal", False)
                    holdout_rows.append(row)
                    for key in [
                        f"mode:{mode}",
                        f"package:{case['case_id']}",
                        *[f"stratum:{s}" for s in case["selection_reasons"]],
                    ]:
                        groups[rule + "/" + key].append((prediction, actual))
                        if row["snapshot_matched"]:
                            groups["snapshot_matched/" + rule + "/" + key].append(
                                (prediction, actual)
                            )
                    if actual != "unknown" and prediction != actual:
                        disagreements.append(
                            {
                                **row,
                                "request": query["request"],
                                "result": actual_row["result"],
                                "effective": actual_row.get("effective"),
                            }
                        )
    interventions = []
    for case, kind in collect.cases(frozen):
        if kind != "intervention":
            continue
        obs = observations[case["case_id"]]
        by_id = {r["plan"]["query_id"]: r for r in obs["paths"]}
        for old in case["rows"]:
            labels = []
            for budget in study.BUDGETS:
                key = f"intervention/{old['canonical_request_sha256']}/{budget}"
                row = by_id.get(key)
                labels.append(
                    {
                        "requested_max_length": budget,
                        "label": label(row) if row else "unknown",
                        "snapshot_matched": row.get("snapshot_matched", False)
                        if row
                        else False,
                        "effective": row.get("effective") if row else None,
                        "result": row.get("result") if row else None,
                    }
                )
            interventions.append(
                {
                    "old_query_id": old["old_query_id"],
                    "immutable_old_label": old["old_label"],
                    "selection": old["selection"],
                    "new_intervention_rows": labels,
                    "sensitive": len({r["label"] for r in labels} - {"unknown"}) > 1,
                    "scope": "new correlated intervention; does not replace old label or identify a universal failure cause",
                }
            )
    integrity = {
        str(p.relative_to(raw)): study.sha(p)
        for p in sorted(raw.rglob("*"))
        if p.is_file()
    }
    result = {
        "schema": 1,
        "freeze_sha256": study.sha(study.HERE / "freeze.json"),
        "controls": qualification,
        "driver_cleanup": driver_cleanup,
        "bridge": bridges,
        "package_mode_coverage": [
            {
                "case_id": c["case_id"],
                "mode": m,
                "supported_package": c["supported"],
                "selected_requests": len(v["selected"]),
                "unqueried_candidates": len(v["unqueried"]),
                "null_prediction": not v["selected"],
                "reason": v["reason"]
                or ("no valid literal requests" if not v["selected"] else None),
            }
            for c in frozen["selected"]
            for m, v in c["modes"].items()
        ],
        "holdout_rows": holdout_rows,
        "metrics": {g: metrics(r) for g, r in sorted(groups.items())},
        "disagreements": disagreements,
        "intervention": interventions,
        "raw_integrity": integrity,
        "openings": [
            {
                k: o.get(k)
                for k in [
                    "case_id",
                    "completed",
                    "missing",
                    "error",
                    "cleanup_coverage_valid",
                    "opening_post_graph_equal",
                ]
            }
            for o in observations.values()
        ],
        "limitations": [
            "request counts are correlated, not independent votes",
            "empty strata and absent native classes are not estimable",
            "file identity is not memory attestation or strict no-mods",
            "dynamic exclusions and serialization errors remain retained",
            "stock packages have no prepared-input/CPU lineage",
            "no geographic negative, model refit, app adoption, certificate, or promise activation",
        ],
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_bytes(study.encoded(evaluate(args.raw)))
