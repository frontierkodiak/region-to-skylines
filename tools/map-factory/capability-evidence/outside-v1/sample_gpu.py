"""Read-only telemetry, restricted to one collector's actual slot ownership."""

import argparse
import datetime
import json
from pathlib import Path
import time

from cs1_harness import gpu, slots
from cs1_harness.config import Config

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("owner_pid", type=int)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    cfg = Config.for_host()
    process = Path(f"/proc/{args.owner_pid}/stat")
    identity = process.read_text().split()[21]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        while process.exists() and process.read_text().split()[21] == identity:
            if slots.lock_pid(cfg) == args.owner_pid:
                holder = slots.holder(cfg)
                row = {
                    "observed_at": datetime.datetime.now(datetime.UTC).isoformat(),
                    "owner_pid": args.owner_pid,
                    "holder": holder,
                    "gpu": gpu.gpu_at(cfg.gpu_bus),
                    "game_processes": [
                        p
                        for p in gpu.game_placement()
                        if p["bus"] == gpu.norm_bus(cfg.gpu_bus)
                    ],
                }
                stream.write(json.dumps(row) + "\n")
                stream.flush()
            time.sleep(2)
