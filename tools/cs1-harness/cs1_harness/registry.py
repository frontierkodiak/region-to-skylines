"""A host-wide index of finished runs, and side-by-side comparison of runs.

Every judged run appends one line to `runs.jsonl` (default
`~/.local/share/cs1-harness/runs.jsonl`, or `CS1_HARNESS_REGISTRY`): where it
is, what it checked, its verdict, the map hash, the harness commit, the issue
that asked for it, and headline metrics. `runs` filters it; `compare` overlays
water volume, wet required probes and population over game-minutes for two or
more runs.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import re

from . import verdict as verdict_mod

REGISTRY = pathlib.Path(
    os.environ.get("CS1_HARNESS_REGISTRY", str(pathlib.Path.home() / ".local/share/cs1-harness/runs.jsonl"))
).expanduser()

ISSUE = re.compile(r"\b((?:PL|POL)-\d+)\b", re.IGNORECASE)


def issue_of(out: pathlib.Path, doc: dict) -> str | None:
    for text in (doc.get("issue"), doc.get("label"), str(out)):
        m = ISSUE.search(text or "")
        if m:
            return m.group(1).upper()
    return None


def check_value(v: dict, name: str):
    return next((c.get("value") for c in v.get("checks") or [] if c["name"] == name), None)


def entry(out: pathlib.Path) -> dict:
    """The registry line for a run directory. Uses its verdict.json, or judges it without writing one."""
    out = pathlib.Path(out).resolve()
    vfile = out / "verdict.json"
    v = json.loads(vfile.read_text()) if vfile.exists() else verdict_mod.judge(out, write=False)
    doc = {}
    for name in ("report.json", "asset-check.json"):
        if (out / name).exists():
            doc = json.loads((out / name).read_text())
    run = doc.get("result", doc)
    session = doc.get("session") or {}
    wet = check_value(v, "probes_wet_end") or {}
    flood = check_value(v, "no_flooding") or {}
    curve = run.get("curve") or []
    gpu = run.get("gpu") or {}
    finished = None
    if (out / "timeline.jsonl").exists():
        lines = (out / "timeline.jsonl").read_text().splitlines()
        finished = json.loads(lines[-1]).get("wall") if lines else None
    finished = finished or (vfile if vfile.exists() else out).stat().st_mtime
    return {
        "id": out.name if out.parent.name in ("experiments", "") else f"{out.parent.name}/{out.name}",
        "path": str(out),
        "finished": datetime.datetime.fromtimestamp(finished).isoformat(timespec="seconds"),
        "check_type": v.get("check_type"),
        "verdict": v.get("verdict"),
        "failed": v.get("failed"),
        "reason": v.get("reason"),
        "triage": (v.get("triage") or {}).get("class"),
        "issue": v.get("issue") or issue_of(out, run),
        "label": run.get("label") or v.get("label"),
        "map": (run.get("map") or {}).get("map_name") if isinstance(run.get("map"), dict) else run.get("map"),
        "map_sha256": v.get("map_sha256") or (session.get("map") or {}).get("sha256"),
        "harness_commit": (v.get("harness") or {}).get("commit"),
        "metrics": {
            "game_minutes": round(run["game_minutes"], 2) if run.get("game_minutes") else None,
            "wall_minutes": round(run["wall_seconds"] / 60, 1) if run.get("wall_seconds") else None,
            "probes_wet_end": wet.get("wet"),
            "probes_required": wet.get("required"),
            "flood_km2": flood.get("worst_km2"),
            "volume_m3_end": curve[-1]["volume_m3"] if curve else None,
            "population_end": curve[-1]["population"] if curve else None,
            "gpu_w_max": (gpu.get("power_w") or {}).get("max"),
            "gpu_c_max": (gpu.get("temp_c") or {}).get("max"),
        },
    }


def load() -> list[dict]:
    if not REGISTRY.exists():
        return []
    rows = {}
    for line in REGISTRY.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            rows[r["path"]] = r  # the latest line for a path wins (re-judged runs)
    return list(rows.values())


def add(out: pathlib.Path) -> dict:
    e = entry(out)
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY, "a") as f:
        f.write(json.dumps(e, default=str) + "\n")
    return e


def find(rows: list[dict], **filters) -> list[dict]:
    out = []
    for r in rows:
        ok = True
        for k, want in filters.items():
            if want is None:
                continue
            have = r.get(k) or ""
            ok &= have.startswith(want) if k in ("map_sha256", "harness_commit") else have.lower() == want.lower()
        if ok:
            out.append(r)
    return sorted(out, key=lambda r: r.get("finished") or "")


def resolve(ref: str) -> pathlib.Path:
    """A run directory from a path, or a registry id or path suffix."""
    p = pathlib.Path(ref).expanduser()
    if p.is_dir():
        return p.resolve()
    hits = [r for r in load() if r["id"] == ref or r["path"].endswith("/" + ref)]
    if len(hits) == 1:
        return pathlib.Path(hits[0]["path"])
    raise SystemExit(f"{ref}: {'ambiguous' if hits else 'not a run directory or registry id'}")


def series(out: pathlib.Path) -> dict:
    """Per-sample curves from a map run: minute, volume, wet required probes, population."""
    report = json.loads((out / "report.json").read_text())
    meta = verdict_mod.probe_meta(out, report)
    by_name = {p.get("name"): p for p in meta.get("points", []) if isinstance(p, dict)}
    fpm, start = report["frames_per_game_minute"], report["start_frame"]
    rows = []
    for line in (out / "timeline.jsonl").read_text().splitlines():
        t = json.loads(line)
        if t["kind"] != "sample":
            continue
        samples = t["water"].get("samples") or []
        req = [s for s in samples if verdict_mod.required(s, by_name.get(s.get("name")), verdict_mod.MAP_SOAK)]
        rows.append(
            {
                "minute": round((t["stats"]["frame"] - start) / fpm, 2),
                "volume_m3": t["water"].get("volume_m3"),
                "wet_required": sum(bool(s.get("wet") or s.get("wet_within_64m")) for s in req),
                "required": len(req),
                "population": t["stats"].get("population"),
            }
        )
    return {"run": str(out), "map": report["map"].get("map_name"), "samples": rows}


def compare(refs: list[str], out_dir: pathlib.Path) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    runs = [resolve(r) for r in refs]
    data = []
    for run in runs:
        s = series(run)
        vfile = run / "verdict.json"
        v = json.loads(vfile.read_text()) if vfile.exists() else verdict_mod.judge(run, write=False)
        s["verdict"] = v["verdict"]
        s["checks"] = {c["name"]: c["status"] for c in v.get("checks") or []}
        s["label"] = run.name if len({r.name for r in runs}) == len(runs) else f"{run.parent.name}/{run.name}"
        data.append(s)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    for s in data:
        m = [r["minute"] for r in s["samples"]]
        name = f"{s['label']} ({s['verdict']})"
        axes[0].plot(m, [r["volume_m3"] / 1e6 for r in s["samples"]], marker=".", label=name)
        axes[1].plot(
            m, [r["wet_required"] / r["required"] if r["required"] else None for r in s["samples"]], marker="."
        )
        axes[2].plot(m, [r["population"] for r in s["samples"]], marker=".")
    axes[0].set_ylabel("water volume (M m³)")
    axes[1].set_ylabel("required probes wet")
    axes[1].set_ylim(-0.05, 1.05)
    axes[1].axhline(verdict_mod.MAP_SOAK["wet_end_min_fraction"], color="grey", lw=0.8, ls="--")
    axes[2].set_ylabel("population")
    axes[2].set_xlabel("game-minutes")
    axes[0].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "compare.png", dpi=110)
    plt.close(fig)
    names = sorted({k for s in data for k in s["checks"]})
    result = {
        "runs": data,
        "checks": {n: {s["label"]: s["checks"].get(n) for s in data} for n in names},
        "differs": [n for n in names if len({s["checks"].get(n) for s in data}) > 1],
        "png": str(out_dir / "compare.png"),
    }
    (out_dir / "compare.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def scan(roots: list[pathlib.Path]) -> list[pathlib.Path]:
    """Run directories under these roots (a report.json or asset-check.json beside a session receipt)."""
    found = set()
    for root in roots:
        for name in ("report.json", "asset-check.json"):
            for p in root.expanduser().rglob(name):
                if (p.parent / "session-receipt.json").exists() or name == "asset-check.json":
                    found.add(p.parent.resolve())
    return sorted(found)
