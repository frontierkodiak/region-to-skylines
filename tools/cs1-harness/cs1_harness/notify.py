"""Post a finished run's verdict on the issue that asked for it.

The comment carries the verdict table, the water-change map, the last
screenshots and the timelapse, so the agent that queued the run can resume on
the result instead of polling. `wake` also @mentions the issue's assignee when
it's an agent, which starts that agent's next run.

Credentials: inside a Multica task the CLI's task token posts as that agent.
Anywhere else (a detached `submit` job) the harness uses the host's `driver`
profile, Driver sessions, the identity Polli's outside sessions act as.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess

from . import registry

MAX_ATTACH_BYTES = 25 * 1024 * 1024


def multica(args: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess:
    if os.environ.get("MULTICA_TOKEN"):
        cmd = ["multica", *args]
    else:
        cmd = ["multica", "--profile", os.environ.get("CS1_HARNESS_MULTICA_PROFILE", "driver"), *args]
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)


def short(check: dict) -> str:
    v = check.get("value")
    name = check["name"]
    if name == "probes_wet_end" and isinstance(v, dict):
        dry = v.get("dry") or []
        return f"{v['wet']}/{v['required']} wet" + (
            f"; dry: {', '.join(dry[:6])}{' …' if len(dry) > 6 else ''}" if dry else ""
        )
    if name == "no_flooding" and isinstance(v, dict):
        return f"{v['worst_km2']} km² beyond expected water"
    if name == "paths" and isinstance(v, dict):
        b = v.get("broken") or []
        return f"{v['checked'] - len(b)}/{v['checked']} found" + (
            "; broken: " + ", ".join(f"{x['name']} ({x['when']})" for x in b[:4]) if b else ""
        )
    if name == "screenshots" and isinstance(v, dict):
        return f"{v['shots']} shots, {len(v['blank_or_missing'])} blank"
    if name == "frame_kinds" and isinstance(v, dict):
        return f"{len(v['flagged'])}/{v['shots']} flagged"
    if name == "game_errors" and isinstance(v, dict):
        return f"{v['errors']} errors, {len(v['unexplained'])} unexplained"
    if name == "cleanup":
        return "nothing left running" if not v else json.dumps(v)
    if v is None:
        return check.get("detail") or ""
    return json.dumps(v)[:80]


def body(out: pathlib.Path, v: dict, entry: dict) -> str:
    m = entry.get("metrics") or {}
    head = f"**cs1-harness: {v['verdict'].upper()}** · {v['check_type']}"
    if entry.get("map"):
        head += f" · {entry['map']}"
    lines = [head, ""]
    if v["verdict"] == "error":
        lines += [f"The run stopped before it could be judged: {v.get('reason')}", ""]
        triage = v.get("triage") or {}
        if triage:
            lines += [f"Triage: **{triage.get('class')}**. {triage.get('why', '')}", ""]
    else:
        if m.get("game_minutes"):
            lines += [f"{m['game_minutes']} game-minutes in {m.get('wall_minutes')} wall minutes.", ""]
        triage = v.get("triage") or {}
        if triage:
            lines += [f"Triage: **{triage.get('class')}**. {triage.get('why', '')}", ""]
        lines += ["| Check | Status | Value |", "|:--|:--|:--|"]
        lines += [
            f"| {c['name']} | {'**fail**' if c['status'] == 'fail' else c['status']} | {short(c).replace('|', '/')} |"
            for c in v["checks"]
        ]
        lines.append("")
    lines += [
        f"Run `{entry['id']}` on blade: `{out}`. Map sha256 `{(entry.get('map_sha256') or '?')[:12]}`, "
        f"harness `{(entry.get('harness_commit') or '?')[:7]}`.",
        "Compare with another run: `cs1-harness compare " + entry["id"] + " <other>`.",
    ]
    return "\n".join(lines) + "\n"


def attachments(out: pathlib.Path, v: dict) -> list[pathlib.Path]:
    files = []
    # What a player sees first, and the check against the real world.
    for name in ("shots/player-opening.png", "shots/player-area-zoom.png", "new-game-panel.png", "ground-truth.png"):
        if (out / name).exists():
            files.append(out / name)
    if (out / "water-change.png").exists():
        files.append(out / "water-change.png")
    shots = sorted((out / "shots").glob("*.png")) if (out / "shots").exists() else []
    if shots:
        last_label = shots[-1].name.split("-")[0]
        files += [p for p in shots if p.name.startswith(last_label + "-") and not p.name.startswith("player-")][:1]
    for extra in ("last-frame.jpg", "timelapse.mp4"):
        p = out / extra
        if p.exists() and p.stat().st_size <= MAX_ATTACH_BYTES:
            files.append(p)
    return files


def mention(issue: str, cwd: pathlib.Path) -> str | None:
    """A mention link for the issue's assignee, when that's an agent."""
    r = multica(["issue", "get", issue, "--output", "json"], cwd)
    if r.returncode != 0:
        return None
    data = json.loads(r.stdout)
    if data.get("assignee_type") != "agent" or not data.get("assignee_id"):
        return None
    agents = multica(["agent", "list", "--output", "json"], cwd)
    name = "agent"
    if agents.returncode == 0:
        rows = json.loads(agents.stdout)
        rows = rows if isinstance(rows, list) else rows.get("agents", [])
        name = next((a.get("name") for a in rows if a.get("id") == data["assignee_id"]), name)
    return f"[@{name}](mention://agent/{data['assignee_id']})"


def post(out: pathlib.Path, issue: str, wake: bool = False, dry_run: bool = False) -> dict:
    out = pathlib.Path(out).resolve()
    v = json.loads((out / "verdict.json").read_text())
    entry = registry.entry(out)
    text = body(out, v, entry)
    if wake:
        who = mention(issue, out)
        if who:
            text = f"{who} your harness run finished.\n\n" + text
    files = attachments(out, v)
    note = out / "notify.md"
    note.write_text(text)
    args = ["issue", "comment", "add", issue, "--content-file", note.name, "--output", "json"]
    for f in files:
        args += ["--attachment", str(f.relative_to(out))]
    if dry_run:
        return {"posted": False, "issue": issue, "body": text, "attachments": [str(f) for f in files]}
    r = multica(args, out)
    result = {"posted": r.returncode == 0, "issue": issue, "attachments": [str(f) for f in files]}
    if r.returncode == 0:
        with_id = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
        result["comment_id"] = with_id.get("id")
    else:
        result["error"] = (r.stderr or r.stdout).strip()[-500:]
    (out / "notify.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
