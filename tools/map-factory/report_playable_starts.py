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
    if status == "pass" and verdict.get("verdict") != "pass":
        status = "fail" if verdict.get("verdict") == "fail" else "unjudged"
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


def export_hashes(root):
    path = root / "cpu-report.json"
    report = json.loads(path.read_text()) if path.is_file() else {}
    return {
        slug: (row.get("stage") or {}).get("crp_sha256")
        for slug, row in report.get("cases", {}).items()
    }


def compare(cohort, controls, baseline, candidate):
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
    expected_before, expected_after = export_hashes(baseline), export_hashes(candidate)
    slugs = [row["slug"] for row in cohort["original"] + cohort["fresh"]]
    cases = {
        slug: {
            "before": opening(baseline / "native" / slug, expected_before.get(slug)),
            "after": opening(candidate / "native" / slug, expected_after.get(slug)),
        }
        for slug in slugs
    }
    before = summarize([row["before"] for row in cases.values()], player)
    after = summarize([row["after"] for row in cases.values()], player)
    comparable = qualified and all(
        row["complete"] and row["same_qualified_player"] for row in (before, after)
    )
    return {
        "schema": 1,
        "issue": cohort["issue"],
        "controls": stock,
        "stock_policy_qualified": qualified,
        "qualified_player_mod_sha256": player,
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
        json.loads(args.cohort.read_text()),
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
