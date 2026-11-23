"""Post-capture audit. Does not change frozen predictions or raw observations."""

from __future__ import annotations

import argparse
import collections
import csv
import importlib.util
from pathlib import Path

import study
import collect

SPEC = importlib.util.spec_from_file_location(
    "scoring_repair", Path(__file__).with_name("evaluate.py")
)
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)


def identity_key(row):
    return row["pid"], str(row["start_ticks"])


def cleanup_audit(raw):
    cases = []
    observed_all = {}
    for folder in sorted((raw / "drivers").iterdir()):
        launch = study.read(folder / "launch.json")
        completion = study.read(folder / "completion.json")
        audit = study.read(folder / "audit-completion.json")
        identities = [
            dict(launch["collector"], kind="collector"),
            dict(launch["driver"], kind="driver"),
            dict(audit["source_freeze"]["auditor"], kind="auditor"),
        ]
        identities.extend(audit["coverage"])
        if identity_key(audit["source_freeze"]["collector"]) != identity_key(
            launch["collector"]
        ):
            raise ValueError("auditor watched another collector")
        if (folder / "auditor-launch.json").exists():
            a = study.read(folder / "auditor-launch.json")
            if identity_key(a["auditor"]) != identity_key(
                audit["source_freeze"]["auditor"]
            ):
                raise ValueError("auditor identity mismatch")
            if a["source_sha256"] != study.sha(study.HERE / "audit_processes.py"):
                raise ValueError("auditor source differs")
            if (
                identity_key(completion["auditor"]) != identity_key(a["auditor"])
                or completion["auditor_still_running"]
                or completion["auditor_returncode"]
            ):
                raise ValueError("auditor completion mismatch")
        else:
            source = raw / "process-audit/audit.py.txt"
            if study.sha(source) != audit["source_freeze"]["source_sha256"]:
                raise ValueError("supplemental first-opening auditor source differs")
        if (
            identity_key(completion["collector"]) != identity_key(launch["collector"])
            or completion["collector_still_running"]
        ):
            raise ValueError("collector completion mismatch")
        observation = study.read(raw / folder.name / "observation.json")
        expected_games = {
            (r["host_pid"], str(r["process_start_ticks"]))
            for k, r in observation.items()
            if k.endswith("runtime_identity")
        }
        expected_games.update(
            identity_key(r) for r in observation["observed_game_processes"]
        )
        observed_games = {
            identity_key(r) for r in audit["coverage"] if r["kind"] == "game"
        }
        if not expected_games <= observed_games:
            raise ValueError("game cleanup audit omitted an observed identity")
        if observation.get("session", {}).get("control") and not any(
            r["kind"] == "session_gpu_monitor" for r in audit["coverage"]
        ):
            raise ValueError("session GPU monitor coverage missing")
        rows = []
        for row in identities:
            row = {**row, "verified_still_running": collect.still_running(row)}
            if row["verified_still_running"] or row.get("still_running") is True:
                raise ValueError("observed process remains alive")
            observed_all[identity_key(row)] = row
            rows.append(row)
        cleanup = observation.get("session", {}).get("cleanup", {})
        if cleanup and any(cleanup.values()):
            raise ValueError("session reports leftover owned resources")
        cases.append(
            {"case_id": folder.name, "identities": rows, "session_cleanup": cleanup}
        )
    return {
        "cases": cases,
        "unique_process_identities": len(observed_all),
        "all_observed_processes_gone": True,
        "scope": "every observed Cities.x64, collector, driver, auditor and session GPU monitor PID/start identity; session receipts separately cover owned Steam/display/bus cleanup; no claim of all short-lived helper process birth coverage",
    }


def all_rows(frozen, raw):
    rows = []
    for case, kind in collect.cases(frozen):
        path = raw / case["case_id"] / "observation.json"
        obs = (
            study.read(path)
            if path.exists()
            else {"paths": [], "error": "opening not collected"}
        )
        actual = {r["plan"]["query_id"]: r for r in obs["paths"]}
        plans = collect.requests_for(case, kind)
        if len(actual) != len(obs["paths"]) or set(actual) - {
            r["query_id"] for r in plans
        }:
            raise ValueError("duplicate or unplanned raw request")
        for plan in plans:
            row = actual.get(plan["query_id"])
            rows.append(
                {
                    "case_id": case["case_id"],
                    "kind": kind,
                    "plan": plan,
                    "label": scorer.label(row) if row else "unknown",
                    "observed": row,
                    "missing_reason": None
                    if row
                    else obs.get("error", "request absent"),
                }
            )
    if sorted(r["plan"]["query_id"] for r in rows) != frozen["query_ids"]:
        raise ValueError("complete logical query ID set differs")
    return rows


def fidelity_audit(rows, frozen, raw):
    result = []
    for row in rows:
        actual = row["observed"]
        if actual is None:
            result.append(
                {
                    "query_id": row["plan"]["query_id"],
                    "status": "not_observed",
                    "reason": row["missing_reason"],
                }
            )
            continue
        errors = []
        effective = actual.get("effective")
        native = actual.get("result")
        if effective and native:
            if native["id"] != effective["id"]:
                errors.append("native request/result handle differs")
            flags = native["flags"]
            if (
                native["complete"] != bool(flags & 12)
                or native["success"] != bool(flags & 4)
                or native["released"] != native["complete"]
            ):
                errors.append("native flags/completion/success/release inconsistent")
            if actual["completed_at"] < actual["submitted_at"]:
                errors.append("completion precedes submission")
        else:
            errors.append("effective argument or result absent")
        result.append(
            {
                "query_id": row["plan"]["query_id"],
                "status": "valid" if not errors else "invalid",
                "errors": errors,
            }
        )
    inventories = []
    for path in sorted(raw.glob("*/observation.json")):
        obs = study.read(path)
        for key, identity in obs.items():
            if not key.endswith("runtime_identity"):
                continue
            inventory = identity["file_inventory"]
            hashes = {r["sha256"] for r in inventory.values()}
            build = study.read(study.HERE / "build.json")["build_receipt"]
            required = {
                build["game_executable_sha256"],
                build["dll_sha256"],
                *build["game_assemblies"].values(),
            }
            if not required <= hashes:
                raise ValueError(
                    "required launch/build file inventory coverage missing"
                )
            inventories.append(
                {
                    "case_id": path.parent.name,
                    "phase": key,
                    "files": len(inventory),
                    "roots": identity["inventory_roots"],
                    "unresolved_loaded_assemblies": identity[
                        "unresolved_loaded_assemblies"
                    ],
                    "excluded_dynamic_assemblies": identity[
                        "excluded_dynamic_assemblies"
                    ],
                }
            )
    return {
        "requests": result,
        "invalid_requests": [r for r in result if r["status"] == "invalid"],
        "file_inventories": inventories,
    }


def budget_audit(frozen, rows):
    by_id = {r["plan"]["query_id"]: r for r in rows}
    cases = []
    for old in frozen["intervention"]:
        selected = [
            by_id[f"intervention/{old['canonical_request_sha256']}/{budget}"]
            for budget in study.BUDGETS
        ]
        effective = [
            r["observed"].get("effective") if r["observed"] else None for r in selected
        ]
        nonbudget = [
            {k: v for k, v in e.items() if k not in ["id", "max_length"]} if e else None
            for e in effective
        ]
        graphs = [
            (r["observed"].get("pre_graph"), r["observed"].get("post_graph"))
            if r["observed"]
            else (None, None)
            for r in selected
        ]
        contexts = [
            (r["observed"].get("pre_context"), r["observed"].get("post_context"))
            if r["observed"]
            else (None, None)
            for r in selected
        ]
        states = [
            {k: v for k, v in c.items() if k in ["update_mode", "invert_traffic"]}
            if c
            else None
            for pair in contexts
            for c in pair
        ]
        cases.append(
            {
                "old_query_id": old["old_query_id"],
                "immutable_old_label": old["old_label"],
                "selection": old["selection"],
                "new_labels": [r["label"] for r in selected],
                "requested_max_length": study.BUDGETS,
                "non_budget_effective_arguments_equal": all(
                    e is not None for e in nonbudget
                )
                and nonbudget[1:] == nonbudget[:-1],
                "graph_unchanged_across_all_budgets": all(
                    a is not None and a == b for a, b in graphs
                )
                and len({a for a, b in graphs}) == 1,
                "entry_context_unchanged": all(c is not None for c in states)
                and states[1:] == states[:-1],
                "source_length": old["geometric_length"],
                "source_request_sha256": old["canonical_request_sha256"],
                "scope": "maxLength float passed to public API; internal native clamping or cost units not attested",
            }
        )
    return cases


def bridge_audit(report, frozen, raw):
    result = []
    for case in frozen["selected"]:
        details = report["bridge"][case["case_id"]]
        if not details.get("supported"):
            result.append(
                {
                    "case_id": case["case_id"],
                    "unsupported": True,
                    "missing": case["missing"],
                }
            )
            continue
        native = study.native_package(
            study.read(raw / case["case_id"] / "networks.json")
        )
        fields = collections.Counter()
        delta = [0.0, 0.0, 0.0]
        for mode, entry in details["by_mode"].items():
            for row in entry["mismatches"]:
                fields.update(row["fields"])
                if row["export"] and row["native"]:
                    for key in ["a", "b"]:
                        for i, (a, b) in enumerate(
                            zip(row["export"][key], row["native"][key])
                        ):
                            delta[i] = max(delta[i], abs(a - b))
        diagnostic = []
        for mode, entry in case["modes"].items():
            prepared = study.model.Prepared(native, mode)
            for row in entry["selected"]:
                diagnostic.append(
                    {
                        "query_id": row["query_id"],
                        "frozen": row["rules"][study.RULES[0]],
                        "native_snapshot_diagnostic": study.model.predict(
                            prepared, row["request"], study.RULES[0]
                        ),
                    }
                )
        result.append(
            {
                "case_id": case["case_id"],
                "mismatched_fields_counted_for_every_mode_segment": dict(fields),
                "max_coordinate_difference_xyz": delta,
                "fixed_rule_native_snapshot_diagnostics": diagnostic,
                "scope": "post-outcome bridge diagnostic only; never a replacement pre-export prediction or a refit",
            }
        )
    return result


def opening_changes(raw):
    result = []
    for path in sorted(raw.glob("*/networks-post.json")):
        before = study.native_package(study.read(path.with_name("networks.json")))
        after = study.native_package(study.read(path))
        modes = {}
        for mode in study.MODES:
            a = {r["id"]: r for r in study.model_fields(before, mode)}
            b = {r["id"]: r for r in study.model_fields(after, mode)}
            changes = []
            for sid in sorted(set(a) | set(b)):
                if a.get(sid) != b.get(sid):
                    changes.append(
                        {"segment": sid, "before": a.get(sid), "after": b.get(sid)}
                    )
            modes[mode] = {
                "before_sha256": study.digest(list(a.values())),
                "after_sha256": study.digest(list(b.values())),
                "changes": changes,
            }
        result.append({"case_id": path.parent.name, "by_mode": modes})
    return result


def package_metrics(frozen, rows, report):
    actual = {r["plan"]["query_id"]: r["label"] for r in rows}
    result = []
    for case in frozen["selected"]:
        for mode, entry in case["modes"].items():
            for rule in study.RULES:
                pairs = [
                    (q["rules"][rule]["prediction"], actual[q["query_id"]])
                    for q in entry["selected"]
                ]
                result.append(
                    {
                        "case_id": case["case_id"],
                        "mode": mode,
                        "rule": rule,
                        "metrics": scorer.metrics(pairs),
                        "null_package_mode": not bool(entry["selected"]),
                        "selection_reasons": case["selection_reasons"],
                        "qualified_mode": report["controls"][mode]["qualified"],
                    }
                )
    return result


def gpu_log(raw):
    result = []
    for path in sorted(raw.glob("*/gpu.csv")):
        with path.open() as stream:
            rows = list(csv.DictReader(stream, skipinitialspace=True))

        def peak(prefix):
            values = []
            for row in rows:
                for key, value in row.items():
                    if key and key.startswith(prefix):
                        try:
                            values.append(float(value))
                        except (ValueError, TypeError):
                            pass
            return max(values) if values else None

        obs = study.read(path.with_name("observation.json"))
        result.append(
            {
                "case_id": path.parent.name,
                "host": "blade",
                "gpu": "RTX 2080 Ti / 05:00.0",
                "started_at": obs["started_at"],
                "finished_at": obs["finished_at"],
                "total_gpu_memory_peak_mib": peak("memory.used"),
                "power_peak_watts": peak("power.draw"),
                "power_limit_reported_watts": peak("power.limit"),
                "temperature_peak_c": peak("temperature.gpu"),
                "game_memory_menu_samples_mib": [
                    r["mib"] for r in obs.get("session", {}).get("game_gpu", [])
                ],
                "game_memory_peak": "not measured separately; total GPU memory includes other workloads",
            }
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frozen = study.read(study.HERE / "freeze.json")
    report = study.read(args.report)
    rows = all_rows(frozen, args.raw)
    counts = collections.Counter((r["kind"], r["label"]) for r in rows)
    value = {
        "created_at": study.now(),
        "source_sha256": study.sha(Path(__file__)),
        "rows": rows,
        "counts": {f"{k[0]}/{k[1]}": v for k, v in sorted(counts.items())},
        "cleanup": cleanup_audit(args.raw),
        "fidelity": fidelity_audit(rows, frozen, args.raw),
        "budget": budget_audit(frozen, rows),
        "bridge": bridge_audit(report, frozen, args.raw),
        "opening_changes": opening_changes(args.raw),
        "package_metrics": package_metrics(frozen, rows, report),
        "run_log": gpu_log(args.raw),
    }
    args.output.write_bytes(study.encoded(value))


if __name__ == "__main__":
    main()
