"""Read full dependency closure through the owned, logged-in Steam client.

Raw descriptions stay in the private experiment, never in the published ledger.
The compiled helper contains only Steamworks read/query/release operations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time


def collect(ids, instance, helper, client, api, out):
    out.mkdir(parents=True, exist_ok=True)
    records = {}
    for path in out.glob("batch-*.jsonl"):
        for line in path.read_text().splitlines():
            if line.startswith("{"):
                record = json.loads(line)
                records[record["id"]] = record
    queue = set(ids)
    for record in records.values():
        if record["result"] == 1:
            queue.update(record["children"])
    while queue - records.keys():
        batch = sorted(queue - records.keys(), key=int)[:100]
        number = len(list(out.glob("batch-*.jsonl")))
        command = ["flatpak", "enter", instance, str(helper), str(client), str(api), *batch]
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (out / f"batch-{number:04d}.log").write_text(result.stderr)
        if result.returncode:
            raise RuntimeError(f"Steamworks batch failed: {result.stderr[-500:]}")
        incoming = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        if [r["id"] for r in incoming] != batch:
            raise ValueError("Metadata result IDs differ from the requested batch")
        for record in incoming:
            records[record["id"]] = record
            if record["result"] == 1:
                queue.update(record["children"])
        body = "\n".join(json.dumps(r) for r in incoming) + "\n"
        (out / f"batch-{number:04d}.jsonl").write_text(body)
        print(f"Steamworks metadata {len(records)}/{len(queue)}", flush=True)
        time.sleep(1)
    (out / "receipt.json").write_text(
        json.dumps(
            {
                "method": "ISteamUGC details + SetReturnChildren + transitive queries",
                "queried": len(records),
                "requested": len(ids),
                "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "batches": [
                    {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                    for path in sorted(out.glob("batch-*.jsonl"))
                ],
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ids", required=True, type=Path)
    p.add_argument("--instance", required=True)
    p.add_argument("--helper", required=True, type=Path)
    p.add_argument("--client", required=True, type=Path)
    p.add_argument("--api", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    ids = json.loads(a.ids.read_text())
    if not all(re.fullmatch(r"[0-9]+", iid) for iid in ids):
        p.error("IDs must be numeric strings")
    collect(ids, a.instance, a.helper, a.client, a.api, a.out)
