"""Turn a run directory into report.json, report.md and water-change images."""

from __future__ import annotations

import csv
import json
import pathlib
import re
import statistics

import numpy as np
from PIL import Image

N = 1081
CELL = 16.0
WET = 0.1  # metres; shallower cells count as dry when comparing extents


def grid(path: pathlib.Path) -> np.ndarray:
    return np.fromfile(path, dtype="<u2").reshape(N, N)


def cell_of(x: float, z: float) -> tuple[int, int]:
    return int(round((z + 8640) / CELL)), int(round((x + 8640) / CELL))


def hillshade(terrain_m: np.ndarray) -> np.ndarray:
    gz, gx = np.gradient(terrain_m, CELL)
    shade = (-gx + gz) / np.sqrt(1 + gx * gx + gz * gz)
    shade = (shade - shade.min()) / max(1e-6, np.ptp(shade))
    return 0.35 + 0.5 * shade


def north_up(a: np.ndarray) -> np.ndarray:
    # The game's arrays start at z = -8640; images put +z (north) at the top.
    return np.flipud(a)


def water_image(terrain_m: np.ndarray, depth_m: np.ndarray, path: pathlib.Path):
    base = hillshade(terrain_m)
    rgb = np.stack([base, base, base], axis=-1)
    wet = depth_m > WET
    t = np.clip(depth_m / 10.0, 0, 1)
    blue = np.stack([0.1 * (1 - t), 0.35 + 0.25 * (1 - t), 0.55 + 0.45 * (1 - t)], axis=-1)
    rgb[wet] = blue[wet]
    Image.fromarray((north_up(rgb) * 255).astype(np.uint8)).save(path)


def change_image(terrain_m: np.ndarray, before: np.ndarray, after: np.ndarray, path: pathlib.Path):
    base = hillshade(terrain_m) * 0.8
    rgb = np.stack([base, base, base], axis=-1)
    b, a = before > WET, after > WET
    rgb[b & a] = (0.2, 0.45, 0.85)  # wet throughout
    rgb[~b & a] = (0.9, 0.15, 0.1)  # newly wet: flooding
    rgb[b & ~a] = (1.0, 0.8, 0.0)  # dried out: draining
    Image.fromarray((north_up(rgb) * 255).astype(np.uint8)).save(path)


def log_errors(log: pathlib.Path, limit: int = 25) -> dict:
    if not log.exists():
        return {"log": None}
    lines = log.read_text(errors="replace").splitlines()
    hits: dict[str, int] = {}
    for line in lines:
        if re.search(r"Exception|(^|\W)Error\b|ERROR|Crash", line) and "Filename:" not in line:
            key = line.strip()[:240]
            hits[key] = hits.get(key, 0) + 1
    version = next((m.group(1) for line in lines for m in [re.search(r"Game Version: *(\S+)", line)] if m), None)
    top = sorted(hits.items(), key=lambda kv: -kv[1])[:limit]
    return {
        "log": log.name,
        "lines": len(lines),
        "error_lines": sum(hits.values()),
        "distinct": len(hits),
        "game_version": version,
        "top": [{"count": n, "line": k} for k, n in top],
    }


def gpu_summary(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}
    # nvidia-smi headers look like "power.draw [W]"; keep the field name only.
    with open(path) as f:
        reader = csv.reader(f, skipinitialspace=True)
        header = [h.split(" [")[0].strip() for h in next(reader, [])]
        rows = [dict(zip(header, row)) for row in reader if len(row) == len(header)]
    out = {"samples": len(rows)}
    for field, name in (
        ("temperature.gpu", "temp_c"),
        ("power.draw", "power_w"),
        ("utilization.gpu", "util_pct"),
        ("memory.used", "mem_mib"),
    ):
        vals = []
        for r in rows:
            try:
                vals.append(float(r[field]))
            except (KeyError, ValueError, TypeError):
                pass
        if vals:
            out[name] = {"min": min(vals), "mean": round(statistics.fmean(vals), 1), "max": max(vals)}
    if rows:
        out["power_limit_w"] = rows[0].get("power.limit")
        out["index"] = rows[0].get("index")
    return out


def vram(run: dict) -> dict:
    """VRAM on the pinned GPU: what else held it before launch, the peak, and the game's share."""
    session = run.get("session") or {}
    before = (session.get("gpu") or {}).get("mem_used_before_mib")
    total = (session.get("gpu") or {}).get("mem_total_mib")
    game = [p.get("mib") for p in session.get("game_gpu") or []]
    return {
        "gpu": (session.get("gpu") or {}).get("name"),
        "bus": (session.get("gpu") or {}).get("bus"),
        "before_launch_mib": before,
        "total_mib": total,
        "game_at_menu_mib": max(game) if game else None,
    }


def build(out: pathlib.Path, run: dict) -> dict:
    timeline = [json.loads(line) for line in open(out / "timeline.jsonl")]
    samples = [t for t in timeline if t["kind"] == "sample"]
    grids = out / "grids"
    terrain = grid(grids / f"{run['first_dump']}-terrain.u16") / 64.0
    first = grid(grids / f"{run['first_dump']}-water.u16") / 64.0
    last = grid(grids / f"{run['last_dump']}-water.u16") / 64.0
    water_image(terrain, first, out / "water-start.png")
    water_image(terrain, last, out / "water-end.png")
    change_image(terrain, first, last, out / "water-change.png")
    b, a = first > WET, last > WET
    km2 = CELL * CELL / 1e6
    fpm = run["frames_per_game_minute"]
    start = run["start_frame"]

    curve = [
        {
            "minute": round((s["stats"]["frame"] - start) / fpm, 2),
            "game_time": s["stats"]["game_time"],
            "population": s["stats"]["population"],
            "buildings": s["stats"]["buildings"],
            "wet_cells": s["water"]["wet_cells"],
            "volume_m3": round(s["water"]["volume_m3"]),
            "max_depth_m": s["water"]["max_depth_m"],
        }
        for s in samples
    ]

    points = []
    if samples and samples[0]["water"]["samples"]:
        names = [p["name"] for p in samples[0]["water"]["samples"]]
        for i, name in enumerate(names):
            series = [s["water"]["samples"][i] for s in samples]
            depths = [p["depth"] for p in series]
            iz, ix = cell_of(series[0]["x"], series[0]["z"])
            points.append(
                {
                    "name": name,
                    "x": series[0]["x"],
                    "z": series[0]["z"],
                    "wet_start": series[0]["wet"],
                    "wet_end": series[-1]["wet"],
                    "dry_samples": sum(1 for p in series if not p["wet"]),
                    "samples": len(series),
                    "depth_start": round(depths[0], 2),
                    "depth_end": round(depths[-1], 2),
                    "depth_min": round(min(depths), 2),
                    "depth_max": round(max(depths), 2),
                    "grid_depth_start": round(float(first[iz, ix]), 2) if 0 <= iz < N and 0 <= ix < N else None,
                }
            )

    check = [
        abs(p["grid_depth_start"] - p["depth_start"])
        for p in points
        if p["grid_depth_start"] is not None and p["depth_start"] > 0.5
    ]
    report = {
        **run,
        "water": {
            "wet_km2_start": round(float(b.sum()) * km2, 2),
            "wet_km2_end": round(float(a.sum()) * km2, 2),
            "newly_wet_km2": round(float((~b & a).sum()) * km2, 2),
            "dried_km2": round(float((b & ~a).sum()) * km2, 2),
            "volume_m3_start": curve[0]["volume_m3"] if curve else None,
            "volume_m3_end": curve[-1]["volume_m3"] if curve else None,
            "wet_threshold_m": WET,
            "grid_point_check_median_abs_m": round(statistics.median(check), 3) if check else None,
        },
        "points": points,
        "points_wet_start": sum(p["wet_start"] for p in points),
        "points_wet_end": sum(p["wet_end"] for p in points),
        "points_ever_dry": [p["name"] for p in points if p["dry_samples"]],
        "curve": curve,
        "errors": log_errors(out / "game.log"),
        "gpu": gpu_summary(out / "gpu.csv"),
        "vram": vram(run),
    }
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    (out / "report.md").write_text(markdown(report))
    return report


def markdown(r: dict) -> str:
    w, g, e = r["water"], r["gpu"], r["errors"]
    lines = [
        f"# CS1 harness run: {r['map'].get('map_name')}",
        "",
        f"- {r['game_minutes']:.1f} game-minutes ({r['end_frame'] - r['start_frame']} frames, "
        f"{r['frames_per_game_minute']:.0f} per minute at 1x) at speed {r['speed']} in {r['wall_seconds'] / 60:.1f} "
        "wall minutes.",
        f"- Map listed in New Game: {r['map'].get('published')}. Game {e.get('game_version')}, "
        f"rendered on {r['menu_status'].get('gpu')} at {r['menu_status'].get('screen')}.",
        f"- Water: {w['wet_km2_start']} km² wet at start, {w['wet_km2_end']} km² at end; "
        f"{w['newly_wet_km2']} km² newly wet, {w['dried_km2']} km² dried (threshold {w['wet_threshold_m']} m). "
        f"Volume {w['volume_m3_start']:,} → {w['volume_m3_end']:,} m³.",
        f"- Probe points wet: {r['points_wet_start']}/{len(r['points'])} at start, "
        f"{r['points_wet_end']}/{len(r['points'])} at end; ever dry: {', '.join(r['points_ever_dry']) or 'none'}.",
        f"- Population {r['curve'][0]['population'] if r['curve'] else '?'} → "
        f"{r['curve'][-1]['population'] if r['curve'] else '?'}.",
        f"- Log: {e.get('error_lines', 0)} error lines ({e.get('distinct', 0)} distinct); "
        f"mod saw {r['final_status'].get('error_count')} Unity errors.",
    ]
    v = r.get("vram") or {}
    if g and v.get("before_launch_mib") is not None:
        peak = (g.get("mem_mib") or {}).get("max")
        v["peak_total_mib"] = peak
        v["peak_game_mib"] = peak - v["before_launch_mib"] if peak is not None else None
        lines.append(
            f"- VRAM on {v.get('gpu')} ({v.get('bus')}): {v['before_launch_mib']} MiB held by other work before launch, "
            f"peak {peak} of {v.get('total_mib')} MiB, so the game's peak was about {v['peak_game_mib']} MiB "
            f"({v.get('game_at_menu_mib')} MiB at the main menu)."
        )
    if g:
        lines.append(
            f"- GPU {g.get('index')}: {g.get('temp_c', {}).get('max')} °C max, power "
            f"{g.get('power_w', {}).get('mean')} W mean / {g.get('power_w', {}).get('max')} W max "
            f"(limit {g.get('power_limit_w')} W), utilisation {g.get('util_pct', {}).get('mean')}% mean."
        )
    lines += ["", "| minute | population | wet cells | volume m³ | max depth m |", "|--:|--:|--:|--:|--:|"]
    lines += [
        f"| {c['minute']} | {c['population']} | {c['wet_cells']} | {c['volume_m3']:,} | {c['max_depth_m']:.2f} |"
        for c in r["curve"]
    ]
    if e.get("top"):
        lines += ["", "Most frequent log errors:", ""]
        lines += [f"- {t['count']}× `{t['line'][:160]}`" for t in e["top"][:10]]
    lines += [
        "",
        "Images: `water-start.png`, `water-end.png`, `water-change.png` (red newly wet, yellow dried), and `shots/`.",
        "",
    ]
    return "\n".join(lines)
