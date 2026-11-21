"""Plot every arm/sample of the declared synthetic cohort, without qualifying it."""

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def plot(results, output):
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), constrained_layout=True)
    table = []
    for path, color in zip(results, ("#4b5563", "#b45309", "#0369a1")):
        result = json.loads(path.read_text())
        features = result["features"]["contracts"]
        engineered = [f for f in features if f["kind"] == "engineered"]
        natural = [f for f in features if f["kind"] == "natural"]
        timeline = [
            json.loads(s)
            for s in (path.parent / "timeline.jsonl").read_text().splitlines()
            if '"kind": "water_study_snapshot"' in s
        ]
        times, means, ports, sectors = [], [], [], []
        for row, storage in zip(timeline, result["measured_storage"]):
            label = row["prefix"]
            if storage["prefix"] != label:
                raise ValueError("Plot inputs have different snapshot cohorts")
            times.append(storage["minute_before"])
            means.append(
                storage["declared_channel_depth_sum_q"]
                / (len(storage["declared_channel_depth_q"]) * 64)
            )
            port_depths = [
                p["depth"]
                for p in row["samples"]
                if p["name"].startswith("synthetic-port:")
            ]
            if len(port_depths) != len(engineered) or len(engineered) != 3:
                raise ValueError("Missing exact engineered port in plot cohort")
            ports.append(min(port_depths))
            checks = [
                next(s for s in f["samples"] if s["label"] == label) for f in natural
            ]
            if len(checks) != 3 or any(c["missing"] or not c["total"] for c in checks):
                raise ValueError("Incomplete natural sector observation")
            sectors.append(min(c["wet"] / c["total"] for c in checks))
            table.append(
                {
                    "arm": result["arm"],
                    "prefix": label,
                    "game_minute_before": times[-1],
                    "mean_declared_channel_depth_m": means[-1],
                    "minimum_exact_port_depth_m": ports[-1],
                    "minimum_natural_sector_retention": sectors[-1],
                }
            )
        for row in axes:
            for ax, values in zip(row, (means, ports, sectors)):
                ax.plot(times, values, color=color, linewidth=1.5, label=result["arm"])
    titles = (
        "Mean depth on all 73 declared nodes",
        "Minimum exact depth across all 3 ports",
        "Minimum retention across all 3 sectors",
    )
    for i, row in enumerate(axes):
        for j, ax in enumerate(row):
            ax.set_title(titles[j] if i == 0 else "Full frozen hour")
            ax.set_xlim(0, 10 if i == 0 else 60)
            ax.set_ylim(bottom=-0.03)
            ax.set_xlabel("Game minutes (before-read simulation counter)")
            ax.set_ylabel("Depth (m)" if j < 2 else "Nearby wet fraction")
            ax.grid(alpha=0.2)
            if j == 1:
                ax.axhline(0.5, color="#b91c1c", linestyle=":", linewidth=1)
            elif j == 2:
                ax.axhline(0.95, color="#b91c1c", linestyle=":", linewidth=1)
    axes[0, 0].legend(loc="best", fontsize=8)
    fig.suptitle(
        "Synthetic branched-channel response — intakes fixed; joint upstream outputs 0 / 32 / 128\nSampled development evidence, not geographic qualification or integrated flow",
        fontsize=12,
    )
    fig.savefig(output.with_suffix(".png"), dpi=160)
    plt.close(fig)
    with output.with_suffix(".csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("results", type=Path, nargs=3)
    args = parser.parse_args()
    plot(args.results, args.output)
