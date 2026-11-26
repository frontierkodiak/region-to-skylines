"""Authorized Workshop acquisition through an explicitly owned Steam-only session.

The SDK log stays private: initialization may print the logged-in account ID.
Only public item IDs, callback codes and container validation enter the receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import time

from installed import crp

CACHE = Path("/peach/Games/SteamLibrary/steamapps/workshop/content/255710")


def local_containers(cache, iid):
    files = list((cache / iid).rglob("*.crp"))
    if not files:
        return None
    return [
        {
            "file": str(path.relative_to(cache)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            **crp(path, strict_checksums=False, measure=False),
        }
        for path in files
    ]


def valid_local(cache, iid):
    try:
        return bool(local_containers(cache, iid))
    except (OSError, ValueError, EOFError):
        return False


def acquire(ids, owner_pid, out, instance, helper, client, api):
    owner = Path(f"/proc/{owner_pid}/cmdline").read_bytes()
    if b"steam_console.py" not in owner or str(out).encode() not in owner:
        raise ValueError("Not the named owned Steam-only session")
    if not ids or not all(re.fullmatch(r"[0-9]+", iid) for iid in ids):
        raise ValueError("Expected public Workshop ID strings")
    ids = list(dict.fromkeys(ids))
    missing = [iid for iid in ids if not valid_local(CACHE, iid)]
    log = out / f"sdk-download-{time.time_ns()}.log"
    result = None
    if missing:
        command = [
            "flatpak",
            "enter",
            instance,
            "env",
            f"HOME={Path.home()}",
            f"USER={pwd.getpwuid(os.getuid()).pw_name}",
            "SteamAppId=255710",
            "SteamGameId=255710",
            str(helper),
            str(client),
            str(api),
            *missing,
        ]
        with log.open("w") as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
    callbacks = []
    if log.exists():
        for line in log.read_text(errors="replace").splitlines():
            if line.startswith('{"id":'):
                callbacks.append(json.loads(line))
    complete, failed = {}, {}
    for iid in ids:
        try:
            complete[iid] = local_containers(CACHE, iid)
            if not complete[iid]:
                failed[iid] = "No CRP files"
        except (OSError, ValueError, EOFError) as error:
            failed[iid] = str(error)
    receipt = {
        "method": "Steamworks DownloadItem(highPriority=false), bounded batches and callbacks",
        "permission": "Caleb's standing Steam-download permission, PL-1326, 2026-11-25",
        "requested": ids,
        "not_already_cached": missing,
        "callbacks": callbacks,
        "flatpak_returncode": result.returncode if result else None,
        "containers": complete,
        "failures": failed,
        "helper_sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
        "private_log_sha256": hashlib.sha256(log.read_bytes()).hexdigest() if log.exists() else None,
        "validation_scope": "CRP directory/ranges and file hashes; stale internal checksum warnings are retained; not a quality pass",
    }
    (out / "acquisition-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if failed:
        raise RuntimeError(f"{len(failed)} items still lack complete local CRPs; see receipt")
    print(f"{len(ids)} items have complete local containers")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", type=Path, required=True)
    parser.add_argument("--owner-pid", type=int, required=True)
    parser.add_argument("--session-out", type=Path, required=True)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--api", type=Path, required=True)
    args = parser.parse_args()
    acquire(
        json.loads(args.ids.read_text()),
        args.owner_pid,
        args.session_out,
        args.instance,
        args.helper,
        args.client,
        args.api,
    )
