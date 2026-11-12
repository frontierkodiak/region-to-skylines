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

import hashlib
import json
import math
import pathlib
import re
import subprocess

import numpy as np
from PIL import Image

from . import landmarks, mapped_water, new_game_panel, startup_views

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


def flooding(out: pathlib.Path, report: dict, meta: dict, t: dict, *, mapped_path: pathlib.Path | None = None) -> dict:
    corridor = None
    if "mapped_water" in meta:
        try:
            corridor, _ = mapped_water.read_mask(
                mapped_path if mapped_path is not None else out / mapped_water.FROZEN_FILE, meta["mapped_water"]
            )
        except (OSError, ValueError) as exc:
            return row("no_flooding", "fail", detail=f"requested mapped-water evidence invalid: {exc}")
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
        return row("no_flooding", "fail" if corridor is not None else "skip", detail="no saved water grids")
    initial = grid(ref_path) > WET_M
    expected = initial if corridor is None else initial | corridor
    if int(expected.sum()) < t["reference_min_wet_cells"]:
        return row(
            "no_flooding",
            "fail" if corridor is not None else "skip",
            int(expected.sum()),
            detail=f"{ref_from} is nearly dry; give the probe file a reference_water grid to judge flooding",
        )
    near = dilate(expected, int(t["flood_distance_m"] // CELL_M))
    per_grid = []
    initial_grids = []
    initial_near = dilate(initial, int(t["flood_distance_m"] // CELL_M)) if corridor is not None else None
    for path in sorted(grids.glob("t*-water.u16")):
        deep = grid(path) > t["flood_depth_m"]
        far = (~near) & deep
        per_grid.append({"grid": path.name, "km2": round(float(far.sum()) * CELL_M * CELL_M / 1e6, 4)})
        if initial_near is not None:
            initial_grids.append(
                {"grid": path.name, "km2": round(float(((~initial_near) & deep).sum()) * CELL_M * CELL_M / 1e6, 4)}
            )
    worst = max((g["km2"] for g in per_grid), default=0.0)
    value = {"worst_km2": worst, "grids": per_grid, "reference": ref_from}
    if corridor is not None:
        if not per_grid:
            return row("no_flooding", "fail", detail="requested mapped-water check has no saved water grids")
        initial_worst = max(g["km2"] for g in initial_grids)
        value.update(
            reference=ref_from + " union hash-bound mapped_water",
            reference_sha256=hashlib.sha256(ref_path.read_bytes()).hexdigest(),
            mapped_water={
                "file": str(mapped_path) if mapped_path is not None else mapped_water.FROZEN_FILE,
                "sha256": meta["mapped_water"]["sha256"],
                "format": mapped_water.FORMAT,
                "cells": int(corridor.sum()),
            },
            failing_grids=[g for g in per_grid if g["km2"] > t["flood_max_km2"]],
            initial_only_diagnostic={
                "worst_km2": initial_worst,
                "grids": initial_grids,
                "would_fail": int(initial.sum()) >= t["reference_min_wet_cells"] and initial_worst > t["flood_max_km2"],
                "status": "skip"
                if int(initial.sum()) < t["reference_min_wet_cells"]
                else ("fail" if initial_worst > t["flood_max_km2"] else "pass"),
                "reference_cells": int(initial.sum()),
                "gating": False,
            },
        )
    return row(
        "no_flooding",
        "fail" if worst > t["flood_max_km2"] else "pass",
        value,
        f"<= {t['flood_max_km2']} km² deeper than {t['flood_depth_m']} m beyond {t['flood_distance_m']:.0f} m",
    )


def adjudicate_flooding(out: pathlib.Path, mask_path: pathlib.Path, spec: dict) -> dict:
    """Read-only supplemental assessment; never rewrite a historical frozen request/verdict.

    The caller records this separately. It is not a re-run or native acceptance.
    """
    out, mask_path = pathlib.Path(out), pathlib.Path(mask_path)
    report_path = out / "report.json"
    report = json.loads(report_path.read_text())
    meta = probe_meta(out, report)
    source_probes = pathlib.Path(meta["_path"]) if "_path" in meta else None
    return {
        "schema": 1,
        "kind": "supplemental-mapped-water-flooding",
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "probes_sha256": hashlib.sha256(source_probes.read_bytes()).hexdigest() if source_probes else None,
        "mapped_water": spec,
        "mask_path": str(mask_path.resolve()),
        "saved_grid_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((out / "grids").glob("t*-water.u16"))
        },
        "thresholds": {k: v for k, v in MAP_SOAK.items() if k.startswith(("flood_", "reference_"))},
        "assessment": flooding(out, report, {**meta, "mapped_water": spec}, MAP_SOAK, mapped_path=mask_path),
        "native_acceptance": False,
    }


def probes_wet_throughout(out: pathlib.Path, report: dict, meta: dict, t: dict) -> dict:
    """Required probes wet at every observed native sample, not every simulation frame."""
    name = "probes_wet_throughout"
    limit = 40
    coord_tolerance = 0.001  # native float32 coordinate echo roundoff, not spatial water tolerance

    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    def identity(point):
        if not isinstance(point, dict) or not isinstance(point.get("name"), str) or not point["name"]:
            raise ValueError("missing/malformed probe identity")
        if not all(number(point.get(k)) for k in ("x", "z")):
            raise ValueError("missing/nonfinite probe coordinates")
        return point["name"]

    def same_position(a, b):
        return all(abs(a[k] - b[k]) <= coord_tolerance for k in ("x", "z"))

    def table(points):
        if not isinstance(points, list):
            raise ValueError("missing/malformed point table")
        result = {}
        for point in points:
            key = identity(point)
            if key in result:
                raise ValueError(f"duplicate probe identity: {key}")
            result[key] = point
        return result

    try:
        frozen = "points" in meta
        requested = meta["points"] if frozen else report.get("points")
        if frozen:
            if not isinstance(requested, list):
                raise ValueError("malformed frozen probe table")
            normalized = []
            for i, p in enumerate(requested):
                if isinstance(p, dict):
                    p = {**p, "name": p.get("name", f"p{i}")}
                    if "required" in p and type(p["required"]) is not bool:
                        raise ValueError("required override must be boolean")
                elif isinstance(p, list) and len(p) >= 2:
                    p = {"name": f"p{i}", "x": p[0], "z": p[-1]}
                normalized.append(p)
            requested = normalized
        expected = table(requested)
        cohort = {key: p for key, p in expected.items() if required(p, p if frozen else None, t)}
        if not cohort:
            return row(name, "skip", detail="no required probes in the declared cohort")
        reported = table(report.get("points"))
        for key, p in cohort.items():
            if key not in reported or not same_position(p, reported[key]):
                raise ValueError(f"required report identity missing/changed: {key}")
        rows = []
        for line in (out / "timeline.jsonl").read_text().splitlines():
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("malformed timeline row")
            if record.get("kind") == "sample":
                rows.append(record)
        curve = report.get("curve")
        if len(rows) < 2 or not isinstance(curve, list) or len(curve) != len(rows):
            raise ValueError("need at least two real samples and complete report-curve coverage")
        start, end, fpm = (report.get(k) for k in ("start_frame", "end_frame", "frames_per_game_minute"))
        if not all(number(v) for v in (start, end, fpm)) or end <= start or fpm <= 0:
            raise ValueError("missing/malformed run frame interval")
        exact_dry = {key: 0 for key in cohort}
        no_nearby = {key: 0 for key in cohort}
        bad = set()
        nearby_measured = nearby_wet = 0
        frames = []
        per_sample = []
        for sample, summary in zip(rows, curve):
            frame = sample["stats"]["frame"]
            if not number(frame) or (frames and frame <= frames[-1]):
                raise ValueError("sample frames missing, duplicated or unordered")
            frames.append(frame)
            minute = (frame - start) / fpm
            if (
                not isinstance(summary, dict)
                or not number(summary.get("minute"))
                or abs(summary["minute"] - minute) > 0.011
            ):
                raise ValueError("timeline frame differs from report curve (allowing 0.01-minute rounding)")
            observed = table(sample["water"]["samples"])
            dry_here = []
            for key, point in cohort.items():
                if key not in observed or not same_position(point, observed[key]):
                    raise ValueError(f"required native sample identity missing/changed: {key}")
                actual = observed[key]
                if type(actual.get("wet")) is not bool:
                    raise ValueError(f"missing/malformed native wet flag: {key}")
                nearby = actual.get("wet_within_64m")
                if "wet_within_64m" in actual and type(nearby) is not bool:
                    raise ValueError(f"malformed native nearby flag: {key}")
                if nearby is not None:
                    nearby_measured += 1
                    nearby_wet += int(nearby)
                if not actual["wet"]:
                    exact_dry[key] += 1
                    if nearby is None:
                        raise ValueError(f"exact-dry probe has no native nearby evidence: {key}")
                if nearby is False:
                    no_nearby[key] += 1
                if not (actual["wet"] or nearby is True):
                    bad.add(key)
                    dry_here.append(key)
            per_sample.append(
                {
                    "frame": frame,
                    "minute": round(minute, 3),
                    "label": sample.get("label"),
                    "without_water": len(dry_here),
                    "names": dry_here[:limit],
                }
            )
        # Reuse existing 1% completion tolerance for uncovered start margin.
        # End-frame identity is derived by MapCheck from the final sample itself.
        if (
            frames[0] < start
            or frames[0] - start > (end - start) * (1 - t["min_minutes_fraction"])
            or frames[-1] != end
        ):
            raise ValueError("sample evidence does not cover the declared run interval")
        for key in cohort:
            if reported[key].get("samples") != len(rows):
                raise ValueError(f"native sample count differs from report: {key}")
        fraction = 1 - len(bad) / len(cohort)

        def subset(counts):
            names = sorted(key for key, count in counts.items() if count)
            return {
                "probes": len(names),
                "observations": sum(counts.values()),
                "names": names[:limit],
                "names_truncated": max(0, len(names) - limit),
            }

        return row(
            name,
            "pass" if fraction >= t["wet_end_min_fraction"] else "fail",
            {
                "required": len(cohort),
                "samples": len(rows),
                "observations": len(cohort) * len(rows),
                "wet_throughout": len(cohort) - len(bad),
                "fraction": round(fraction, 4),
                "without_water_probes": len(bad),
                "without_water_names": sorted(bad)[:limit],
                "without_water_names_truncated": max(0, len(bad) - limit),
                "exact_dry": subset(exact_dry),
                "native_no_nearby": subset(no_nearby),
                "native_nearby_observations": nearby_measured,
                "native_nearby_wet_observations": nearby_wet,
                "sampled_minutes": [(frames[0] - start) / fpm, (frames[-1] - start) / fpm],
                "largest_sample_gap_minutes": max(b - a for a, b in zip(frames, frames[1:])) / fpm,
                "coordinate_identity_tolerance_m": coord_tolerance,
                "per_sample": per_sample,
            },
            f">= {t['wet_end_min_fraction']:.0%} of required probes wet exactly OR natively within64m at every observed sample",
            "Sampled evidence only, not continuous/every-frame wetness; no inferred legacy nearby values.",
        )
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        return row(name, "fail", detail=f"missing/malformed throughout evidence: {exc}")


def map_soak(out: pathlib.Path, report: dict) -> list[dict]:
    t = MAP_SOAK
    meta = probe_meta(out, report)
    by_name = {p.get("name"): p for p in meta.get("points", []) if isinstance(p, dict)}
    checks = [new_game_panel.assess(out), landmarks.assess(out), startup_views.assess(out)]

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

    checks.append(probes_wet_throughout(out, report, meta, t))
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

    checks.append(ground_truth(out, report, meta))
    checks.append(opening_camera(report))
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


# Checks against the world, independent of the map writer's coordinate code. A map
# soak can't PASS without at least one of these passing (see judge()).
GROUND_TRUTH_CHECKS = ("ground_truth",)
OPENING_HEADING_MAX_DEG = 45  # the opening camera must face within this of north


def ground_truth(out: pathlib.Path, report: dict, meta: dict) -> dict:
    region = meta.get("ground_truth")
    terrain = out / "grids" / f"{report.get('first_dump', 't000')}-terrain.u16"
    if not region:
        return row(
            "ground_truth",
            "skip",
            detail="the probe file has no ground_truth region, so nothing checks the map against the world",
        )
    if not terrain.exists():
        return row("ground_truth", "skip", detail="no terrain dump from the game")
    cached = out / "ground-truth.json"
    if cached.exists():
        r = json.loads(cached.read_text())
    else:
        from . import groundtruth

        try:
            r = groundtruth.check(terrain, region, out)
        except OSError as e:  # the DEM fetch failed; say so rather than guess
            return row("ground_truth", "skip", detail=f"DEM unavailable: {e}")
        cached.write_text(json.dumps(r, indent=2) + "\n")
    return row(
        "ground_truth",
        "pass" if r["passed"] else "fail",
        {
            "orientation": r["orientation"],
            "correlation_as_is": r["correlation"]["as is"],
            "best_other": max(v for k, v in r["correlation"].items() if k != "as is"),
            "landmarks": r["landmarks"],
        },
        f"terrain correlates with the real DEM >= {r['thresholds']['min_correlation']} as is, "
        f"and beats every rotation or mirror by >= {r['thresholds']['min_margin']}",
        "" if r["passed"] else f"the game shows the world {r['orientation']}",
    )


def opening_camera(report: dict) -> dict:
    cam = report.get("opening_camera")
    if (report.get("map") or {}).get("from_save"):
        return row("opening_camera", "skip", detail="started from a save, whose camera is wherever the save left it")
    if not cam:
        return row("opening_camera", "skip", detail="this run didn't read the opening camera")
    heading = float(cam.get("heading_deg", 0.0))
    off = abs((heading + 180) % 360 - 180)
    return row(
        "opening_camera",
        "pass" if off <= OPENING_HEADING_MAX_DEG else "fail",
        {"heading_deg": round(heading, 1), "facing": cam.get("facing")},
        f"faces within {OPENING_HEADING_MAX_DEG}° of north, so the first view matches a north-up map",
        "" if off <= OPENING_HEADING_MAX_DEG else f"a player's first view faces {cam.get('facing')}",
    )


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
    grounded = any(c["name"] in GROUND_TRUTH_CHECKS and c["status"] == "pass" for c in checks)
    outcome = "fail" if failed else ("pass" if grounded or check_type != "map-soak" else "unverified")
    verdict = {
        "schema": SCHEMA,
        "check_type": check_type,
        "verdict": outcome,
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
