"""Answer the game's known first-run dialogs; report anything else.

A fresh install shows dialogs before and during play: the legal disclaimer,
What's New, "Account Link Found", the tutorial advisor. Caleb cleared answering
these on 2026-11-10 (PL-856), so a run never waits on them. Each rule names the
dialog (the game's panel name) and the button to press. Every answer is logged.
A dialog no rule covers is logged as unknown and left alone: nothing guesses.

Steam's own prompts are different. Steam isn't the game; the session's
Steam-log watcher reports those and never answers them (account in use,
EULA).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import time

from .client import Client, HarnessError
from .config import Config

# (dialog name, button: exact name or visible text, why). The first rule whose
# dialog matches and whose button is present wins.
RULES = [
    (
        "LegalDisclaimerPanel",
        r"(?i)^(continue|ok|accept|i agree|agree)$",
        "first-run legal notice; Caleb cleared re-appearing terms on 2026-11-10",
    ),
    ("WhatsNewPanelPanel", r"(?i)^got it!?$", "What's New carousel"),
    (
        "ParadoxSteamLoginWithSteamFirstTimePanel",
        r"(?i)^yes$",
        "'Account Link Found': log in to the linked Paradox account (Caleb, 2026-11-10)",
    ),
    (
        "ParadoxAccountThankYouLoginPanel",
        r"(?i)^ok$",
        "'Thank you for logging in' after the Account Link login; acknowledgement only",
    ),
    ("TutorialPanel", r"(?i)^close$", "tutorial hint panel (e.g. 'Build Roads'); closed with its own close button"),
    ("TutorialAdvisorPanel", r"close", "tutorial advisor ('Hello!'); closed as Escape does"),
]


def matching_rule(dialog: dict):
    for name, button, why in RULES:
        if dialog["name"] != name:
            continue
        if name == "TutorialAdvisorPanel":
            return "close", why
        for b in dialog.get("buttons", []):
            if not b.get("enabled", True):
                continue
            for candidate in (b.get("text") or "", b.get("name") or ""):
                if re.match(button, candidate.strip()):
                    return candidate.strip(), why
    return None, None


def handle(client: Client, log_path: pathlib.Path | None, reported: set[str]) -> list[dict]:
    """One pass: answer known dialogs, log unknown ones once. Returns what it did."""
    try:
        dialogs = client.call("dialogs")["dialogs"]
    except (OSError, ValueError, HarnessError):
        return []
    events = []
    for d in dialogs:
        button, why = matching_rule(d)
        if button:
            try:
                r = client.call("dialog_click", dialog=d["name"], button=button)
                events.append(
                    {
                        "event": "answered",
                        "dialog": d["name"],
                        "button": r.get("text") or r.get("pressed"),
                        "why": why,
                        "texts": d.get("texts", [])[:3],
                    }
                )
            except HarnessError as e:
                events.append({"event": "click_failed", "dialog": d["name"], "button": button, "error": str(e)})
        else:
            key = d["name"] + "|" + "|".join(d.get("texts", [])[:2])
            if key in reported:
                continue
            reported.add(key)
            events.append(
                {
                    "event": "unknown",
                    "dialog": d["name"],
                    "modal": d.get("modal"),
                    "texts": d.get("texts", []),
                    "buttons": d.get("buttons", []),
                }
            )
    if log_path is not None:
        with open(log_path, "a") as f:
            for e in events:
                f.write(json.dumps({"time": time.time(), **e}) + "\n")
    return events


def guard_loop(cfg: Config, log_path: pathlib.Path, every: float = 2.0):
    client = Client(cfg.port, timeout=10)
    reported: set[str] = set()
    while True:
        handle(client, log_path, reported)
        time.sleep(every)


def summarize(log_path: pathlib.Path) -> dict:
    if not log_path.exists():
        return {"answered": [], "unknown": []}
    rows = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    return {
        "answered": [f"{r['dialog']}: {r['button']}" for r in rows if r["event"] == "answered"],
        "unknown": [{"dialog": r["dialog"], "texts": r.get("texts", [])[:3]} for r in rows if r["event"] == "unknown"],
        "failed": [f"{r['dialog']}: {r.get('error')}" for r in rows if r["event"] == "click_failed"],
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m cs1_harness.dialogs")
    p.add_argument("cmd", choices=["guard-loop"])
    p.add_argument("--host")
    p.add_argument("--log", type=pathlib.Path, required=True)
    a = p.parse_args(argv)
    guard_loop(Config.for_host(a.host), a.log)


if __name__ == "__main__":
    main()
