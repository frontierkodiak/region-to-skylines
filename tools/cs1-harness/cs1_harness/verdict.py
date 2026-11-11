"""Pass/fail verdicts for harness runs, with every threshold declared here.

Each check type turns a run directory into `verdict.json`: one row per check
with its status (pass, fail, warn, skip), the measured value and the threshold.
The run fails if any check fails. `warn` marks evidence a person or agent
should look at that isn't calibrated well enough to fail a run; `skip` means
the run has no data for that check, with the reason.

Thresholds were calibrated on blade's 2026-11-10 runs (PL-856, PL-857,
PL-880, PL-893); JOURNAL.md has the numbers. Change one only with evidence, and say
which runs it moves from pass to fail or back.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess

import numpy as np
from PIL import Image

SCHEMA = 1

# Map soak (`cs1-harness run`).
MAP_SOAK = {
    # Required probes wet at the end (depth > 0.1 m at the point, or within 64 m
    # when the mod reports it). PL-857's selected Asheville: 28/28 playable river
    # probes; PL-856's PL-848 Asheville: 20/62, its rivers drained.
    "wet_end_min_fraction": 0.95,
    # Probes are required unless the probe file says otherwise: inside the
    # central 25 tiles (|x|, |z| <= 4800 m), not on the map edge, and not tagged
    # "[stream]" in their name (minor streams aren't perennial).
    "playable_half_m": 4800.0,
    "edge_m": 8640.0 - 16.0,
    # Flooding: water deeper than 0.5 m more than 128 m from the expected water
    # (the probe file's reference grid, else the run's first dump), in any saved
    # grid. PL-857's first Asheville fixture spread over 0.522 km² in 10 minutes;
    # its selected policy, 0; Innsbruck's accepted run, 0.023 km² of stream pooling.
    "flood_depth_m": 0.5,
    "flood_distance_m": 128.0,
    "flood_max_km2": 0.05,
    # A reference footprint needs some water to mean anything.
    "reference_min_wet_cells": 100,
    # The run reached the minutes it asked for.
    "min_minutes_fraction": 0.99,
    # A screenshot whose grey-level standard deviation is below this is blank.
    "blank_shot_std": 3.0,
    # Clef frame-kind flags fail the run only when at least this share of shots
    # is flagged (systematic); fewer is a warning. Clef misread 1 of 19 frames.
    "clef_fail_fraction": 0.5,
    # test-city only; calibration and measured growth times go in JOURNAL.md.
    "population_min_growth": 50,
    "population_growth_by_minute": 5.0,
}

# Asset placement (`cs1-harness asset check`).
ASSET_CHECK = {
    "blank_shot_std": 3.0,
    "max_triangles": 20000,  # far above PL-880's 420-triangle kit house; catches a runaway mesh
}

# Log lines every vanilla 1.21.1-f9 run prints; they don't count as errors.
BENIGN_ERRORS = [
    re.compile(r"Assembly resolution failure\. No assembly named '\w+GroupPanel' was found"),
]

GRID_N = 1081
CELL_M = 16.0
WET_M = 0.1


def row(name: str, status: str, value=None, threshold=None, detail: str = "") -> dict:
    return {"name": name, "status": status, "value": value, "threshold": threshold, "detail": detail}


def harness_commit() -> dict:
    here = pathlib.Path(__file__).resolve().parent
    try:
        sha = subprocess.run(
            ["git", "-C", str(here), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "-C", str(here), "status", "--porcelain", "--", ".."], capture_output=True, text=True
            ).stdout.strip()
        )
        return {"commit": sha, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def unexplained_errors(lines: list[str]) -> list[str]:
    return [line for line in lines if not any(p.search(line) for p in BENIGN_ERRORS)]


def shot_std(path: pathlib.Path) -> float | None:
    try:
        with Image.open(path) as im:
            return float(np.asarray(im.convert("L").resize((320, 180)), dtype=np.float32).std())
    except (OSError, ValueError):
        return None


def shots_check(out: pathlib.Path, shots: list[dict], threshold: float) -> dict:
    if not shots:
        return row("screenshots", "fail", 0, threshold, "the run took no screenshots")
    bad = []
    for s in shots:
        std = shot_std(out / s["file"])
        if std is None or std < threshold:
            bad.append({"file": s["file"], "std": None if std is None else round(std, 2)})
    return row(
        "screenshots",
        "fail" if bad else "pass",
        {"shots": len(shots), "blank_or_missing": bad},
        f"grey std >= {threshold}",
        "" if not bad else f"{len(bad)} blank or unreadable",
    )


def required(point: dict, meta: dict | None, t: dict) -> bool:
    if meta and "required" in meta:
        return bool(meta["required"])
    reach = max(abs(point["x"]), abs(point["z"]))
    return reach <= t["playable_half_m"] and reach < t["edge_m"] and "[stream]" not in point["name"]


def probe_meta(out: pathlib.Path, report: dict) -> dict:
    """The probe file this run used: its frozen copy in the run directory, else (older runs) the
    path it recorded. Editing the source later can't change an archived run's verdict."""
    for p in (out / "probes.json", pathlib.Path(report.get("probes") or "/nonexistent")):
        if p.is_file():
            data = json.loads(p.read_text())
            data = {"points": data} if isinstance(data, list) else data
            data["_path"] = str(p)
            return data
    return {}


def grid(path: pathlib.Path) -> np.ndarray:
    return np.fromfile(path, dtype="<u2").reshape(GRID_N, GRID_N) / 64.0


def dilate(mask: np.ndarray, radius_cells: int) -> np.ndarray:
    """Cells within `radius_cells` (Euclidean) of any True cell."""
    out = mask.copy()
    r = radius_cells
    for dz in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dz * dz > r * r or (dx == 0 and dz == 0):
                continue
            src = mask[max(0, -dz) : GRID_N - max(0, dz), max(0, -dx) : GRID_N - max(0, dx)]
            out[max(0, dz) : GRID_N - max(0, -dz), max(0, dx) : GRID_N - max(0, -dx)] |= src
    return out


def flooding(out: pathlib.Path, report: dict, meta: dict, t: dict) -> dict:
    grids = out / "grids"
    first = grids / f"{report.get('first_dump', 't000')}-water.u16"
    ref_path, ref_from = None, None
    if (out / "reference-water.u16").exists():
        ref_path, ref_from = out / "reference-water.u16", "probe file reference_water (frozen copy)"
    elif meta.get("reference_water"):
        ref_path = pathlib.Path(meta["_path"]).parent / meta["reference_water"]
        ref_from = "probe file reference_water"
    elif first.exists():
        ref_path, ref_from = first, "the run's first water dump"
    if ref_path is None or not ref_path.exists():
        return row("no_flooding", "skip", detail="no saved water grids")
    expected = grid(ref_path) > WET_M
    if int(expected.sum()) < t["reference_min_wet_cells"]:
        return row(
            "no_flooding",
            "skip",
            int(expected.sum()),
            detail=f"{ref_from} is nearly dry; give the probe file a reference_water grid to judge flooding",
        )
    near = dilate(expected, int(t["flood_distance_m"] // CELL_M))
    per_grid = []
    for path in sorted(grids.glob("t*-water.u16")):
        far = (~near) & (grid(path) > t["flood_depth_m"])
        per_grid.append({"grid": path.name, "km2": round(float(far.sum()) * CELL_M * CELL_M / 1e6, 4)})
    worst = max((g["km2"] for g in per_grid), default=0.0)
    return row(
        "no_flooding",
        "fail" if worst > t["flood_max_km2"] else "pass",
        {"worst_km2": worst, "grids": per_grid, "reference": ref_from},
        f"<= {t['flood_max_km2']} km² deeper than {t['flood_depth_m']} m beyond {t['flood_distance_m']:.0f} m",
    )


def map_soak(out: pathlib.Path, report: dict) -> list[dict]:
    t = MAP_SOAK
    meta = probe_meta(out, report)
    by_name = {p.get("name"): p for p in meta.get("points", []) if isinstance(p, dict)}
    checks = []

    asked = report.get("requested_game_minutes")
    got = report.get("game_minutes") or 0
    if asked:
        checks.append(
            row(
                "completed",
                "pass" if got >= asked * t["min_minutes_fraction"] else "fail",
                round(got, 2),
                f">= {t['min_minutes_fraction']:.0%} of {asked}",
            )
        )

    points = report.get("points") or []
    req = [p for p in points if required(p, by_name.get(p["name"]), t)]
    if not req:
        checks.append(row("probes_wet_end", "skip", detail="no required probes"))
    else:

        def wet(p):
            return bool(p.get("wet_end") or p.get("wet_within_64m_end"))

        dry = [p["name"] for p in req if not wet(p)]
        frac = 1 - len(dry) / len(req)
        checks.append(
            row(
                "probes_wet_end",
                "pass" if frac >= t["wet_end_min_fraction"] else "fail",
                {"wet": len(req) - len(dry), "required": len(req), "fraction": round(frac, 3), "dry": dry[:40]},
                f">= {t['wet_end_min_fraction']:.0%} of required probes",
                f"{len(points) - len(req)} probes not required (outside the playable 25 tiles, on the edge, or streams)",
            )
        )

    checks.append(flooding(out, report, meta, t))
    checks.extend(scenario_checks(report))

    paths = [("start", p) for p in report.get("paths_start") or []] + [
        ("end", p) for p in report.get("paths_end") or []
    ]
    asked_paths = [p.get("name") for p in meta.get("paths") or [] if isinstance(p, dict)]
    if not paths and asked_paths:
        checks.append(
            row(
                "paths",
                "fail",
                {"asked": asked_paths, "checked": 0},
                "every native path found, no expected segment missing",
                "the probe file names paths but this harness didn't check them (needs native path probes, PR #8)",
            )
        )
    elif not paths:
        checks.append(row("paths", "skip", detail="the probe file names no paths"))
    else:
        broken = [
            {
                "when": when,
                "name": p.get("name"),
                "success": p.get("success"),
                "missing": len(p.get("missing_segments") or []),
            }
            for when, p in paths
            if not p.get("success") or p.get("missing_segments")
        ]
        checks.append(
            row(
                "paths",
                "fail" if broken else "pass",
                {"checked": len(paths), "broken": broken},
                "every native path found, no expected segment missing",
            )
        )

    terrain = report.get("terrain") or {}
    if "terraced" in terrain:
        checks.append(
            row(
                "no_terracing",
                "fail" if terrain["terraced"] else "pass",
                terrain.get("equal_pair_fraction_on_slopes"),
                f"<= {terrain.get('threshold')}",
            )
        )

    checks.append(shots_check(out, report.get("shots") or [], t["blank_shot_std"]))

    clef = report.get("clef")
    if clef and clef.get("available"):
        n, flagged = len(clef.get("shots") or []), len(clef.get("flagged") or [])
        status = "pass" if not flagged else ("fail" if n and flagged / n >= t["clef_fail_fraction"] else "warn")
        checks.append(
            row(
                "frame_kinds",
                status,
                {"shots": n, "flagged": [f.get("file") for f in clef.get("flagged") or []]},
                f"fail at >= {t['clef_fail_fraction']:.0%} flagged",
            )
        )
    else:
        checks.append(row("frame_kinds", "skip", detail="Clef not run (pass --clef)"))

    checks += common(report.get("session") or {}, (report.get("final_status") or {}).get("errors") or [])
    return checks


def scenario_checks(report: dict) -> list[dict]:
    """An empty map isn't a growth test; a requested fixture must never skip it."""
    if not report.get("requested_scenario"):
        return [
            row("population_growth", "skip", detail="no scenario requested (use --scenario test-city)"),
            row("outside_connection", "skip", detail="no scenario requested"),
            row("utilities", "skip", detail="no scenario requested"),
        ]
    fixture = report.get("scenario") or {}
    curve = report.get("curve") or []
    initial = curve[0]["population"] if curve else 0
    final = curve[-1]["population"] if curve else 0
    minimum = MAP_SOAK["population_min_growth"]
    deadline = MAP_SOAK["population_growth_by_minute"]
    observations = report.get("population_observations") or curve
    hits = [p["minute"] for p in observations if p["population"] - initial >= minimum]
    reached = min(hits) if hits else None
    grew = fixture.get("state") == "done" and reached is not None and reached <= deadline and final - initial >= minimum
    population = row(
        "population_growth",
        "pass" if grew else "fail",
        {"initial": initial, "final": final, "growth": final - initial, "first_observed_minute": reached},
        f">= {minimum} new residents by minute {deadline:g}, retained at the end",
    )
    reach = fixture.get("reachability") or {}
    successful = set()
    for path in reach.get("paths") or []:
        positions = path.get("positions") or []
        grid = path.get("grid_segment")
        edge = path.get("edge_segment")
        offset = path.get("edge_offset")
        if (
            path.get("success")
            and path.get("released")
            and grid
            and edge
            and offset in (0, 255)
            and any(p[0] == grid for p in positions)
            and any(p[0] == edge and abs(p[2] - offset) <= 1 for p in positions)
        ):
            successful.add(path.get("direction"))
    connected = reach.get("complete") and {"inbound", "outbound"}.issubset(successful)
    outside = row(
        "outside_connection",
        "pass" if connected else "fail",
        {
            "complete": bool(reach.get("complete")),
            "directions": sorted(successful),
            "paths_checked": len(reach.get("paths") or []),
        },
        "native passenger-car paths grid -> highway edge and edge -> grid, released",
    )
    facilities = {u.get("role"): u for u in (fixture.get("final") or {}).get("utilities") or []}
    broken = []
    for role in ("power", "water", "sewage"):
        facility = facilities.get(role) or {}
        active = "Active" in (facility.get("flags") or "").split(", ")
        connected = role == "power" or (facility.get("connected_segments") or 0) > 0
        supply_problems = set((facility.get("problems") or "").split(", ")) & {
            "Electricity",
            "Water",
            "WaterNotConnected",
            "Sewage",
            "NoResources",
            "Flood",
            "TurnedOff",
        }
        if not active or not connected or supply_problems:
            broken.append(
                {
                    "role": role,
                    "flags": facility.get("flags"),
                    "problems": facility.get("problems"),
                    "connected": connected,
                }
            )
    utilities = row(
        "utilities",
        "fail" if broken else "pass",
        {"broken": broken},
        "power, water and sewage active, native pipe nodes connected, no connection or supply problems",
    )
    return [population, outside, utilities]


def asset_check(out: pathlib.Path, doc: dict) -> list[dict]:
    t = ASSET_CHECK
    r = doc.get("result") or {}
    checks = []
    asset = r.get("asset") or {}
    checks.append(row("loaded", "pass" if asset.get("name") else "fail", asset.get("name")))
    tris = (asset.get("mesh") or {}).get("triangles")
    if tris is not None:
        checks.append(
            row("triangles", "pass" if tris <= t["max_triangles"] else "fail", tris, f"<= {t['max_triangles']}")
        )
    checks.append(row("has_lod", "pass" if asset.get("lod") else "fail", bool(asset.get("lod"))))
    placed = r.get("placed") or {}
    checks.append(
        row(
            "placed",
            "pass" if placed.get("exists") and "Completed" in (placed.get("flags") or "") else "fail",
            placed.get("flags"),
            "exists, Completed",
        )
    )
    after = r.get("after_reload") or {}
    checks.append(
        row(
            "survives_reload",
            "pass" if after.get("exists") and after.get("name") == asset.get("name") else "fail",
            after.get("name"),
        )
    )
    checks.append(shots_check(out, r.get("shots") or [], t["blank_shot_std"]))
    checks += common(doc.get("session") or {}, r.get("errors") or [])
    return checks


def common(session: dict, errors: list[str]) -> list[dict]:
    rows = []
    cleanup = session.get("cleanup")
    if cleanup is not None:
        left = {k: v for k, v in cleanup.items() if v}
        rows.append(row("cleanup", "fail" if left else "pass", left or {}, "nothing left running"))
    extra = unexplained_errors(errors)
    rows.append(
        row(
            "game_errors",
            "warn" if extra else "pass",
            {"errors": len(errors), "unexplained": extra[:10]},
            "no errors beyond the known vanilla ones",
            "advisory; not yet calibrated to fail a run",
        )
    )
    return rows


def judge(out: pathlib.Path, write: bool = True) -> dict:
    """Judge a finished run directory; write `verdict.json` unless `write` is False."""
    out = pathlib.Path(out)
    if (out / "report.json").exists():
        doc = json.loads((out / "report.json").read_text())
        check_type, checks = "map-soak", map_soak(out, doc)
        thresholds = MAP_SOAK
        session = doc.get("session") or {}
    elif (out / "asset-check.json").exists():
        doc = json.loads((out / "asset-check.json").read_text())
        check_type, checks = "asset-check", asset_check(out, doc)
        thresholds = ASSET_CHECK
        session = doc.get("session") or {}
    else:
        raise FileNotFoundError(f"{out} has no report.json or asset-check.json")
    failed = [c["name"] for c in checks if c["status"] == "fail"]
    verdict = {
        "schema": SCHEMA,
        "check_type": check_type,
        "verdict": "fail" if failed else "pass",
        "failed": failed,
        "warnings": [c["name"] for c in checks if c["status"] == "warn"],
        "checks": checks,
        "thresholds": thresholds,
        "map_sha256": (session.get("map") or {}).get("sha256"),
        "harness": doc.get("harness") or (doc.get("result") or {}).get("harness"),  # None: run predates recording
        "judged_by": harness_commit(),
    }
    if write:
        (out / "verdict.json").write_text(json.dumps(verdict, indent=2, default=str) + "\n")
    return verdict


def error_verdict(
    out: pathlib.Path, check_type: str, reason: str, exit_code: int, issue: str | None = None, label: str | None = None
) -> dict:
    """A run that ended before it could be judged."""
    verdict = {
        "schema": SCHEMA,
        "check_type": check_type,
        "verdict": "error",
        "failed": [],
        "reason": reason,
        "exit_code": exit_code,
        "issue": issue,
        "label": label,
        "checks": [],
        "harness": harness_commit(),
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "verdict.json").write_text(json.dumps(verdict, indent=2) + "\n")
    return verdict


def summary(v: dict) -> str:
    if v["verdict"] == "error":
        return f"{v['check_type']}: ERROR ({v.get('reason')})"
    marks = {"pass": "ok", "fail": "FAIL", "warn": "warn", "skip": "skip"}
    parts = [f"{c['name']} {marks[c['status']]}" for c in v["checks"]]
    return f"{v['check_type']}: {v['verdict'].upper()} · " + ", ".join(parts)
