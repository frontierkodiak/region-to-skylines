"""A scripted opening's verdict, separate from empty-map water qualification."""

from __future__ import annotations

import re
import json
import pathlib

MINUTES = 60
WARMUP_MINUTES = 5
MAX_SAMPLE_GAP_MINUTES = 6
GRID_KM2 = 288 * 288 / 1e6
SUPPLY_PROBLEMS = {
    "Electricity",
    "Water",
    "DirtyWater",
    "WaterNotConnected",
    "Sewage",
    "NoResources",
    "NoFuel",
    "Flood",
    "TurnedOff",
}


def failure(out: pathlib.Path, reason: str) -> dict:
    """Keep a first-hour verdict and actual observations when construction/simulation aborts."""
    observations, errors, fixture = [], [], {}
    scenario = out / "scenario.json"
    if scenario.is_file():
        try:
            fixture = json.loads(scenario.read_text())
        except (OSError, ValueError):
            errors.append("unreadable scenario receipt")
    timeline = out / "timeline.jsonl"
    if timeline.is_file():
        for number, line in enumerate(timeline.read_text().splitlines(), 1):
            try:
                row = json.loads(line)
                if row.get("kind") != "sample":
                    continue
                stats, city = row["stats"], row.get("scenario") or {}
                observations.append(
                    {
                        "label": row["label"],
                        "frame": stats["frame"],
                        "population": stats["population"],
                        "money": stats.get("money"),
                        "traffic": city.get("traffic"),
                        "utilities": city.get("utilities"),
                        "growable_problems": city.get("growable_problems"),
                    }
                )
            except (ValueError, KeyError, TypeError):
                errors.append(f"unreadable timeline record {number}")
    return {
        "name": "first_hour",
        "status": "fail",
        "threshold": "completed scripted 60-minute opening",
        "detail": reason,
        "value": {
            "completed": False,
            "phase": "simulation" if observations else "construction" if scenario.is_file() else "preflight_or_load",
            "construction_state": fixture.get("state"),
            "land": (fixture.get("result") or {}).get("land"),
            "observations": observations,
            "evidence_errors": errors,
            "scope": "Partial observations only; no full-hour, end-path or healthy-utility qualification is implied.",
        },
    }


def assess(report: dict, city_checks: list[dict], panel: dict) -> dict:
    """Do not let final recovery, missing observations or a template panel pass."""
    result = {
        "name": "first_hour",
        "status": "skip",
        "value": None,
        "threshold": "60 game-minutes; growth, both car paths, sampled services/movement, land and native panel",
        "detail": "not requested (use --scenario first-hour)",
    }
    if report.get("requested_scenario") != "first-hour":
        return result
    observations = report.get("scenario_observations") or []
    minutes = [o["minute"] for o in observations]
    fixture = report.get("scenario") or {}
    city = {c["name"]: c["status"] for c in city_checks}
    checks = {name: city.get(name) == "pass" for name in ("population_growth", "outside_connection", "utilities")}
    checks["duration"] = report.get("game_minutes", 0) >= MINUTES * 0.99
    checks["sample_coverage"] = bool(
        len(minutes) >= 13
        and 0 <= minutes[0] <= 0.25
        and minutes[-1] >= MINUTES * 0.99
        and all(0 < b - a <= MAX_SAMPLE_GAP_MINUTES for a, b in zip(minutes, minutes[1:]))
    )
    outages = []
    for observation in observations:
        if observation["minute"] < WARMUP_MINUTES:
            continue
        status = observation["status"]
        if status.get("state") != "done":
            outages.append({"minute": observation["minute"], "reason": "city construction not complete"})
        roles = {u["role"] for u in status.get("utilities") or []}
        if roles != {"power", "water", "sewage"}:
            outages.append({"minute": observation["minute"], "reason": "missing utility evidence"})
        for facility in status.get("utilities") or []:
            flags = set(re.split(r"[,\s]+", facility.get("flags", "")))
            problems = set(re.split(r"[,\s]+", facility.get("problems", ""))) & SUPPLY_PROBLEMS
            if (
                "Active" not in flags
                or problems
                or type(facility.get("requires_electricity")) is not bool
                or (facility.get("requires_electricity") and facility.get("electricity_grid_powered") is not True)
                or (facility["role"] != "power" and facility.get("connected_segments", 0) == 0)
            ):
                outages.append(
                    {
                        "minute": observation["minute"],
                        "role": facility["role"],
                        "problems": sorted(problems),
                        "electricity_grid_powered": facility.get("electricity_grid_powered"),
                    }
                )
        for problems, count in (status.get("growable_problems") or {}).items():
            if count and set(re.split(r"[,\s]+", problems)) & SUPPLY_PROBLEMS:
                outages.append({"minute": observation["minute"], "growables": count, "problems": problems})
    checks["sampled_services"] = checks["sample_coverage"] and not outages
    tail = [o for o in observations if o["minute"] >= MINUTES - 15]
    traffic = [o["status"].get("traffic") for o in tail]
    observed = bool(traffic) and all(
        t is not None
        and t.get("scope") == "scenario road segments"
        and 0 <= t.get("moving", -1) <= t.get("vehicles", -1)
        for t in traffic
    )
    checks["sampled_traffic_movement"] = (
        checks["sample_coverage"] and observed and any(t["moving"] > 0 for t in traffic)
    )
    land = (fixture.get("result") or {}).get("land") or {}
    checks["starter_land"] = bool(
        fixture.get("state") == "done" and land.get("samples", 0) > 0 and land.get("dry_flat_km2", 0) >= GRID_KM2
    )
    checks["map_panel"] = panel["status"] == "pass"
    result.update(
        status="pass" if all(checks.values()) else "fail",
        value={
            "checks": checks,
            "outages": outages,
            "land": land,
            "traffic_last_15_minutes": [{"minute": o["minute"], "traffic": o["status"].get("traffic")} for o in tail],
            "map_panel": panel,
        },
        detail="Services and traffic are sampled, not continuous. Traffic uses native current-path segments on "
        "the roads built by this scenario; movement does not rule out individual bottlenecks. "
        "Land is a 32 m start-tile sample at <=15% axis slope plus actual native city construction; "
        "it is not the game's New Game buildable-area score. Water-soak gates remain independent.",
    )
    return result
