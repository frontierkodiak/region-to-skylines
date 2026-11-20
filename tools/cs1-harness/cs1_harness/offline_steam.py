"""Read-only offline-mode evidence; failed offline syncs are not transfers."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re


class OfflineError(ValueError):
    """The requested offline launch has insufficient or contradictory evidence."""


def flags(text: str) -> dict:
    pieces = re.findall(r'"(?:\\.|[^"\\])*"|[{}]|//[^\r\n]*|\s+', text)
    if "".join(pieces) != text:
        raise OfflineError("unrecognized cached-account configuration syntax")
    tokens = iter(p for p in pieces if p[:1] in ('"', "{", "}"))

    def block(nested=False):
        result = {}
        for token in tokens:
            if token == "}" and nested:
                return result
            if not token.startswith('"'):
                raise OfflineError("invalid cached-account configuration block")
            key = json.loads(token).casefold()
            value = next(tokens, None)
            if key in result or value is None:
                raise OfflineError("ambiguous cached-account configuration")
            result[key] = block(True) if value == "{" else json.loads(value)
        if nested:
            raise OfflineError("unfinished cached-account configuration")
        return result

    accounts = list(block().get("users", {}).values())
    selected = accounts if len(accounts) == 1 else [a for a in accounts if a.get("mostrecent") == "1"]
    if len(selected) != 1:
        raise OfflineError("expected one unambiguous cached Steam account")
    account = selected[0]
    if account.get("wantsofflinemode") != "1" or account.get("skipofflinemodewarning") != "1":
        raise OfflineError("cached account does not request offline mode with its warning suppressed")
    return {"wants_offline_mode": True, "skip_offline_mode_warning": True}


def states(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        login = re.search(r"\[login=(true|false)\]", line, re.I)
        mode = re.search(r"\[offlineMode=(true|false)\]", line, re.I)
        if ("[login=" in line and not login) or ("[offlineMode=" in line and not mode):
            raise OfflineError("unrecognized Cloud login/offline state")
        if not login and not mode:
            continue
        stamp = re.match(r"\[([\d :\-]+)\]", line)
        rows.append(
            {
                "timestamp": stamp[1] if stamp else None,
                "login": login[1].lower() == "true" if login else None,
                "offline_mode": mode[1].lower() == "true" if mode else None,
                "failed_sync": bool(re.search(r"\bFailed sync\b", line, re.I)),
            }
        )
    return rows


def require_offline(rows: list[dict]) -> None:
    for row in rows:
        if row["login"] is True or row["offline_mode"] is False:
            raise OfflineError("Cloud log reports login=true or offlineMode=false")
        if row["login"] is not False or row["offline_mode"] is not True or not row["failed_sync"]:
            raise OfflineError("Cloud sync state does not establish a failed offline sync")


class Guard:
    """Validate current configuration/latest sync batch, then watch new records."""

    def __init__(self, steam_root: pathlib.Path):
        self.preferences = steam_root / "config/loginusers.vdf"
        self.log = steam_root / "logs/cloud_log.txt"
        self.evidence = {"flags": flags(self.preferences.read_text())}
        with self.log.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            data = stream.read()
        rows = states(data.decode("utf-8", errors="replace"))
        if not rows or rows[-1]["timestamp"] is None:
            raise OfflineError("no timestamped Cloud sync state available")
        latest = [r for r in rows if r["timestamp"] == rows[-1]["timestamp"]]
        require_offline(latest)
        self.evidence.update(
            preflight_sync=latest,
            latest_sync=latest,
            fresh_syncs=0,
            cloud_initial_sha256=hashlib.sha256(data).hexdigest(),
        )
        self.identity = (stat.st_dev, stat.st_ino)
        self.offset = len(data)
        self.pending = b""

    def check(self) -> dict:
        self.evidence["flags"] = flags(self.preferences.read_text())
        with self.log.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            if (stat.st_dev, stat.st_ino) != self.identity or stat.st_size < self.offset:
                raise OfflineError("Cloud log rotated or truncated; offline audit continuity lost")
            stream.seek(self.offset)
            fresh = stream.read()
        self.offset += len(fresh)
        data = self.pending + fresh
        end = data.rfind(b"\n") + 1
        self.pending = data[end:]
        if re.search(rb"\[(?:login=true|offlineMode=false)\]", self.pending, re.I):
            raise OfflineError("Cloud log reports login=true or offlineMode=false")
        rows = states(data[:end].decode("utf-8", errors="replace"))
        require_offline(rows)
        if rows:
            self.evidence["latest_sync"] = rows[-10:]
        self.evidence["fresh_syncs"] += len(rows)
        return self.evidence
