"""Reproduce sampled telemetry; peaks are sampled, not continuous maxima."""

import csv
import datetime
import gzip
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def unpack(path):
    return gzip.decompress(path.read_bytes()).decode()


def report(root):
    samples = []
    for path in root.glob("raw/telemetry/*/process-gpu.jsonl.gz"):
        samples.extend(json.loads(line) for line in unpack(path).splitlines())
    output = {}
    for path in sorted(root.glob("raw/*/observation.json.gz")):
        observation = json.loads(unpack(path))
        label = Path(observation["package"]).name
        owned = [r for r in samples if r["holder"]["label"] == label]
        gpu_path = path.parent / "gpu.csv.gz"
        board = (
            list(csv.DictReader(io.StringIO(unpack(gpu_path)), skipinitialspace=True))
            if gpu_path.exists()
            else []
        )
        wall = (
            datetime.datetime.fromisoformat(observation["finished_at"])
            - datetime.datetime.fromisoformat(observation["observed_at"])
        ).total_seconds()
        output[path.parent.name] = {
            "wall_seconds_including_cleanup": round(wall, 1),
            "board_sample_peak_mib": max(
                (int(r["memory.used [MiB]"]) for r in board), default=None
            ),
            "game_sample_peak_mib": max(
                (sum(p["mib"] for p in r["game_processes"]) for r in owned),
                default=None,
            ),
            "launch_game_mib_not_peak": sum(
                p["mib"] for p in observation.get("session", {}).get("game_gpu", [])
            ),
            "board_sample_peak_w": max(
                (float(r["power.draw [W]"]) for r in board), default=None
            ),
            "board_sample_peak_c": max(
                (float(r["temperature.gpu"]) for r in board), default=None
            ),
            "observed_power_limits_w": sorted(
                {float(r["power.limit [W]"]) for r in board}
            ),
            "cleanup": observation.get("session", {}).get("cleanup"),
        }
    return output


if __name__ == "__main__":
    print(
        json.dumps(
            {
                name: report(HERE.parent / name)
                for name in ["rail-v1", "rail-v2", "rail-v3"]
            },
            indent=2,
        )
    )
