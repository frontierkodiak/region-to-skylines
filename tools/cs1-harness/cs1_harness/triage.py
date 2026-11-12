"""Classify every run that didn't pass, and keep the evidence beside it.

Classes, and who usually fixes them:
- map: only map checks failed (water, flooding, paths, terracing); the map's writer.
- harness: our code failed or left something behind; whoever improves the harness.
- steam: Steam refused or is waiting on a person (account in use, EULA, sign-in).
- game-crash: the game died or hung while the harness drove it.
- unknown-dialog: a dialog nobody answered kept the game from getting where it should.
- gpu-vram: wrong GPU, software rendering, blank frames, or the card's memory ran out.
- slot: another run held the slot longer than this one would wait; not a fault.
- unknown: none of the rules matched; read the evidence.

The rules are ordered, first match wins, and each says why it matched.
"""

from __future__ import annotations

import csv
import json
import pathlib
import re
import shutil
import time

MAP_CHECKS = {"probes_wet_end", "no_flooding", "paths", "no_terracing"}
VRAM_HEADROOM_MIB = 256

RULES = [
    # (class, regex on the error reason, why)
    (
        "slot",
        r"holds the lock|a harness session is up|already running on this host|display \S+ is already in use",
        "another run or session held the slot past this run's wait",
    ),
    ("steam", r"Steam is already running", "a Steam this harness didn't start was running (maybe on :0)"),
    (
        "steam",
        r"account is in use|playing-session conflict|playing elsewhere",
        "Steam says the account is playing elsewhere; never answered",
    ),
    (
        "steam",
        r"waiting on a prompt|ShowEula|Steam exited before|cloud sync failed",
        "Steam stopped at a prompt or exited before the game",
    ),
    (
        "gpu-vram",
        r"using GPU\(s\)|not on any NVIDIA GPU|no EGL device|no NVIDIA GPU",
        "the game rendered on the wrong device",
    ),
    (
        "harness",
        r"mod not built|Xvfb .* did not start|private D-Bus did not start|exists with different contents|"
        r"refusing display :0|screenshot .* was not written|does not list .* as a map|Traceback|Error\(",
        "the harness itself failed",
    ),
    ("game-crash", r"no progress for 5 minutes", "the simulation hung"),
]


def gpu_peak(out: pathlib.Path) -> tuple[float | None, float | None]:
    """Peak memory.used on the pinned GPU, and its total from the session receipt."""
    total = None
    receipt = out / "session-receipt.json"
    if receipt.exists():
        total = (json.loads(receipt.read_text()).get("gpu") or {}).get("mem_total_mib")
    path = out / "gpu.csv"
    if not path.exists():
        return None, total
    peak = None
    with open(path) as f:
        reader = csv.reader(f, skipinitialspace=True)
        header = [h.split(" [")[0].strip() for h in next(reader, [])]
        for row in reader:
            try:
                used = float(dict(zip(header, row))["memory.used"])
            except (KeyError, ValueError):
                continue
            peak = used if peak is None else max(peak, used)
    return peak, total


def vram_exhausted(out: pathlib.Path) -> str | None:
    peak, total = gpu_peak(out)
    if peak is not None and total and peak >= float(total) - VRAM_HEADROOM_MIB:
        return f"GPU memory peaked at {peak:.0f} of {total} MiB"
    for name in ("game.log", "game-stdout.log"):
        p = out / name
        if p.exists() and re.search(
            r"out of memory|GL_OUT_OF_MEMORY|Could not allocate memory", p.read_text(errors="replace")
        ):
            return f"{name} reports running out of memory"
    return None


def unknown_dialogs(out: pathlib.Path) -> list[str]:
    """Dialogs the guard saw but didn't recognise (PL-856's dialog guard writes dialogs.jsonl)."""
    p = out / "dialogs.jsonl"
    if not p.exists():
        return []
    seen = []
    for line in p.read_text().splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("known") is False or d.get("kind") == "unknown" or d.get("action") == "reported":
            seen.append(d.get("title") or d.get("text") or json.dumps(d)[:120])
    return seen


def tail(path: pathlib.Path, n: int) -> str:
    return "\n".join(path.read_text(errors="replace").splitlines()[-n:]) if path.exists() else ""


def collect_evidence(out: pathlib.Path, cfg=None) -> list[str]:
    files = []
    for name, n in (("game.log", 80), ("game-stdout.log", 80)):
        t = tail(out / name, n)
        if t:
            (out / f"triage-{name}.tail.txt").write_text(t + "\n")
            files.append(f"triage-{name}.tail.txt")
    if cfg is not None:
        # Launch steps are in webhelper_js.txt on current clients, console-linux.txt on older ones.
        lines = []
        for name in ("console-linux.txt", "webhelper_js.txt"):
            log = cfg.steam_root / "logs" / name
            lines += [
                line
                for line in tail(log, 400).splitlines()
                if re.search(r"255710|GameAction|LaunchApp|prompt|sync failed", line)
            ]
        if lines:
            (out / "triage-steam.tail.txt").write_text("\n".join(lines[-60:]) + "\n")
            files.append("triage-steam.tail.txt")
        # The live frame is host-wide: it's this run's only if this run held the slot (it then has a receipt).
        frame = cfg.live_dir / "frame.jpg"
        ours = (out / "session-receipt.json").exists()
        if (
            ours
            and frame.exists()
            and frame.stat().st_mtime > time.time() - 1800
            and not (out / "last-frame.jpg").exists()
        ):
            shutil.copyfile(frame, out / "last-frame.jpg")
    for name in ("last-frame.jpg", "dialogs.jsonl", "session-receipt.json", "gpu.csv"):
        if (out / name).exists():
            files.append(name)
    return files


def classify(out: pathlib.Path, v: dict) -> dict | None:
    if v.get("verdict") == "pass":
        return None
    failed = set(v.get("failed") or [])
    reason = v.get("reason") or ""
    vram = vram_exhausted(out)
    dialogs = unknown_dialogs(out)

    if v.get("verdict") == "fail":
        if "cleanup" in failed:
            return {"class": "harness", "why": "the run left the game, Steam or a unit running"}
        if "screenshots" in failed:
            if vram:
                return {"class": "gpu-vram", "why": f"blank screenshots; {vram}"}
            return {"class": "gpu-vram", "why": "blank or unreadable screenshots (rendering, not the map)"}
        if "completed" in failed:
            return {"class": "harness", "why": "the run stopped short of its game-minutes"}
        if failed and failed <= MAP_CHECKS:
            return {"class": "map", "why": "only map checks failed: " + ", ".join(sorted(failed))}
        if "frame_kinds" in failed:
            if dialogs:
                return {"class": "unknown-dialog", "why": f"frames weren't the city; unknown dialogs: {dialogs[:3]}"}
            return {"class": "unknown", "why": "Clef flagged most frames as not the city"}
        return {"class": "unknown", "why": "failed checks: " + ", ".join(sorted(failed))}

    if "ended unexpectedly" in reason or "connection closed" in reason or "connection refused" in reason.lower():
        # The harness can't tell a crash from Caleb starting to play; Steam's log can.
        steam = out / "triage-steam.tail.txt"
        if steam.exists() and re.search(r"[Cc]onflict|in use|PlayingElsewhere", steam.read_text()):
            return {"class": "steam", "why": "the game ended and Steam logged a playing-session conflict"}
        if vram:
            return {"class": "gpu-vram", "why": f"the game died; {vram}"}
        return {"class": "game-crash", "why": "the game process ended while the harness drove it"}
    for cls, pattern, why in RULES:
        if re.search(pattern, reason):
            return {"class": cls, "why": why}
    if "did not reach the main menu" in reason or "timed out" in reason:
        if dialogs:
            return {"class": "unknown-dialog", "why": f"stuck behind dialogs the guard didn't know: {dialogs[:3]}"}
        if vram:
            return {"class": "gpu-vram", "why": vram}
        steam = out / "triage-steam.tail.txt"
        if steam.exists() and re.search(r"waiting for user response|syncfailed", steam.read_text()):
            return {"class": "steam", "why": "Steam is waiting on a prompt"}
        return {"class": "unknown-dialog", "why": "the game never got where it should; look at last-frame.jpg"}
    return {"class": "unknown", "why": "no rule matched the reason"}


def attach(out: pathlib.Path, cfg=None) -> dict | None:
    """Add a triage block to a non-passing run's verdict.json, with its evidence files."""
    vfile = pathlib.Path(out) / "verdict.json"
    if not vfile.exists():
        return None
    v = json.loads(vfile.read_text())
    if v.get("verdict") == "pass":
        return None
    evidence = collect_evidence(out, cfg)
    t = classify(out, v) or {}
    t["evidence"] = evidence
    v["triage"] = t
    vfile.write_text(json.dumps(v, indent=2, default=str) + "\n")
    return t
