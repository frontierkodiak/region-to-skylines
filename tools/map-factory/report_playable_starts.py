"""Compare a frozen cohort only under a stock-qualified, byte-identical player.

Native folders are ROOT/native/SLUG. ROOT/cpu-report.json supplies each exact
export's package hash. Control folders are CONTROLS/SLUG. Missing attempts are
not failures or passes, and historical results under another mod cannot become
a qualified before/after comparison.
"""

import argparse
import hashlib
import json
from pathlib import Path


def opening(folder, expected_package):
    verdict_path = folder / "verdict.json"
    if not verdict_path.is_file():
        return {"status": "not_run"}
    raw = verdict_path.read_bytes()
    verdict = json.loads(raw)
    row = next((c for c in verdict.get("checks", []) if c["name"] == "first_hour"), {})
    value = row.get("value") or {}
    receipt_path = folder / "session-receipt.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
    actual_package = (receipt.get("map") or {}).get("sha256")
    status = row.get("status", "unjudged")
    explicit_failure = any(
        check.get("status") == "fail" for check in verdict.get("checks", [])
    )
    if status == "pass" and (verdict.get("verdict") != "pass" or explicit_failure):
        status = (
            "fail"
            if verdict.get("verdict") == "fail" or explicit_failure
            else "unjudged"
        )
    if verdict.get("verdict") == "error" and value.get("phase") == "preflight_or_load":
        status = "blocked"
    if status != "blocked":
        if not expected_package or not actual_package:
            status = "missing_map_identity"
        elif actual_package != expected_package:
            status = "source_mismatch"
        if not receipt.get("mod_sha256"):
            status = "missing_player_identity"
    report_path = folder / "report.json"
    report = json.loads(report_path.read_text()) if report_path.is_file() else {}
    populations = report.get("population_observations") or []
    return {
        "status": status,
        "first_hour": row.get("status"),
        "overall": verdict.get("verdict"),
        "additional_failed_checks": [
            check["name"]
            for check in verdict.get("checks", [])
            if check["status"] == "fail" and check["name"] != "first_hour"
        ],
        "game_minutes": report.get("game_minutes"),
        "population_last": populations[-1]["population"] if populations else None,
        "population_peak": max(row["population"] for row in populations)
        if populations
        else None,
        "checks": value.get("checks"),
        "outages": value.get("outages", []),
        "reason": verdict.get("reason"),
        "phase": value.get("phase"),
        "package_sha256": actual_package,
        "expected_package_sha256": expected_package,
        "player_mod_sha256": receipt.get("mod_sha256"),
        "verdict_sha256": hashlib.sha256(raw).hexdigest(),
        "harness": verdict.get("harness"),
    }


def summarize(rows, player):
    same_player = bool(player) and all(
        row.get("player_mod_sha256") == player
        for row in rows
        if row["status"] in ("pass", "fail")
    )
    passed = sum(row["status"] == "pass" for row in rows)
    failed = sum(row["status"] == "fail" for row in rows)
    complete = passed + failed == len(rows)
    return {
        "planned": len(rows),
        "passed": passed,
        "failed": failed,
        "unresolved": len(rows) - passed - failed,
        "complete": complete,
        "same_qualified_player": same_player,
        "qualified_pass_rate": passed / len(rows) if complete and same_player else None,
    }


def export_report(root):
    path = root / "cpu-report.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def compare(cohort_path, controls, baseline, candidate):
    raw = cohort_path.read_bytes()
    cohort = json.loads(raw)
    preregistration = hashlib.sha256(raw).hexdigest()
    stock = {
        row["name"].lower().replace(" ", "-"): opening(
            controls / row["name"].lower().replace(" ", "-"), row["sha256"]
        )
        for row in cohort["controls"]
    }
    stock_players = {row.get("player_mod_sha256") for row in stock.values()}
    qualified = 2 <= len(stock) <= 3 and all(
        row["status"] == "pass" for row in stock.values()
    )
    qualified = qualified and len(stock_players) == 1 and None not in stock_players
    player = next(iter(stock_players)) if qualified else None
    report_before, report_after = export_report(baseline), export_report(candidate)
    selection = report_before.get("selection") or {}
    original_inputs = {
        row["slug"]: row["input_files_sha256"] for row in cohort["original"]
    }
    selection_bound = bool(
        selection == report_after.get("selection")
        and selection.get("preregistration_sha256") == preregistration
        and selection.get("fixtures") == list(original_inputs)
        and selection.get("frozen_input_files") == original_inputs
        and selection.get("fresh") == cohort["fresh"]
    )
    slugs = [row["slug"] for row in cohort["original"] + cohort["fresh"]]
    cases = {}
    for slug in slugs:
        before_case = report_before.get("cases", {}).get(slug, {})
        after_case = report_after.get("cases", {}).get(slug, {})
        inputs = before_case.get("inputs_sha256")
        inputs_bound = bool(inputs and inputs == after_case.get("inputs_sha256"))
        if slug in original_inputs:
            inputs_bound = inputs_bound and inputs == original_inputs[slug]
        cases[slug] = {
            "before": opening(
                baseline / "native" / slug,
                before_case.get("stage", {}).get("crp_sha256"),
            ),
            "after": opening(
                candidate / "native" / slug,
                after_case.get("stage", {}).get("crp_sha256"),
            ),
            "frozen_inputs_match": inputs_bound,
        }
    all_inputs_bound = all(row["frozen_inputs_match"] for row in cases.values())
    before = summarize([row["before"] for row in cases.values()], player)
    after = summarize([row["after"] for row in cases.values()], player)
    if not selection_bound or not all_inputs_bound:
        before["qualified_pass_rate"] = after["qualified_pass_rate"] = None
    comparable = (
        qualified
        and selection_bound
        and all_inputs_bound
        and all(
            row["complete"] and row["same_qualified_player"] for row in (before, after)
        )
    )
    return {
        "schema": 1,
        "issue": cohort["issue"],
        "controls": stock,
        "stock_policy_qualified": qualified,
        "qualified_player_mod_sha256": player,
        "preregistration_sha256": preregistration,
        "frozen_selection_matches": selection_bound,
        "all_frozen_inputs_match": all_inputs_bound,
        "paired_comparison_qualified": comparable,
        "map_fault_attribution": "qualified" if comparable else "withheld",
        "before": before,
        "after": after,
        "cases": cases,
        "note": "All selected squares remain. Missing/blocked/source-mismatched attempts are unresolved, "
        "not failures. No qualified rate is emitted for incomplete cohorts or another player. "
        "Historical 1/8 under the original policy remains a separate observation.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cohort", "controls", "baseline", "candidate", "out"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = compare(
        args.cohort,
        args.controls,
        args.baseline,
        args.candidate,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "stock_policy_qualified",
                    "paired_comparison_qualified",
                    "before",
                    "after",
                )
            },
            indent=2,
        )
    )
