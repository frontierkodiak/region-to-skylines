"""Render cohort results and CPU-only outer-ring coverage from bound exports."""

import argparse
import json
from pathlib import Path

import numpy as np

from qualify_connections import dump, sha
from resources import TREE_UNIT


def outer_ring(folder):
    """Map data outside central five tiles, not evidence of native 81-tile play."""
    with np.load(folder / "plan.npz") as plan:
        axis = (np.arange(512) + 0.5) * 33.75 - 8640
        outer = (np.abs(axis[:, None]) > 4800) | (np.abs(axis[None, :]) > 4800)
        resources = {
            name: {
                "outer_nonzero_cells": int(np.count_nonzero(plan[name][outer])),
                "all_nonzero_cells": int(np.count_nonzero(plan[name])),
                "outer_encoded_sum": int(plan[name][outer].astype(np.uint64).sum()),
                "all_encoded_sum": int(plan[name].astype(np.uint64).sum()),
            }
            for name in ["ore", "oil", "fertility", "forest"]
        }
        trees = (np.abs(plan["px"].astype(float) * TREE_UNIT) > 4800) | (
            np.abs(plan["pz"].astype(float) * TREE_UNIT) > 4800
        )
        tree_counts = {"outer": int(trees.sum()), "all": int(trees.size)}
    water = np.fromfile(folder / "water.u16", dtype="<u2").reshape(1081, 1081)
    axis = np.arange(1081) * 16 - 8640
    outer = (np.abs(axis[:, None]) > 4800) | (np.abs(axis[None, :]) > 4800)
    return {
        "scope": "CPU map content only; central 5x5 half-extent 4800 m; no native 81-tile proof",
        "resources": resources,
        "trees": tree_counts,
        "water": {
            "outer_wet_nodes": int(np.count_nonzero(water[outer])),
            "all_wet_nodes": int(np.count_nonzero(water)),
        },
        "source_sha256": {
            name: sha(folder / name) for name in ["plan.npz", "water.u16"]
        },
    }


def render(output, harness_root=None):
    report = json.loads((output / "cpu-report.json").read_text())
    plan = report["selection"]
    slugs = plan["fixtures"] + [sq["slug"] for sq in plan["fresh"]]
    lines = [
        "# PL-1066 CPU real-connections qualification",
        "",
        "Disposable test exports; no native qualification, native 81-tile proof, public shipping approval or default change.",
        "",
        "Selection: " + plan["selection_rule"],
        "",
        "| Square | CPU export | Road eligibility | Water screen | Road in/out | Rail in/out | Plane in/out | Ship in/out | Theme |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    coverage, commands = {}, []
    for slug in slugs:
        row = report["cases"].get(slug)
        if not row:
            lines.append(
                f"| {slug} | pending | not assessed | not assessed | — | — | — | — | — |"
            )
            continue
        c = row.get("stage", {}).get("new_game_panel", {}).get("connections", {})
        counts = [
            f"{c.get('incoming' + kind, '—')}/{c.get('outgoing' + kind, '—')}"
            for kind in ["Roads", "TrainTracks", "PlanePath", "ShipPath"]
        ]
        theme = (
            row.get("generation", {}).get("resources", {}).get("environment", "unknown")
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    slug,
                    row["status"],
                    row.get("road_eligibility", {}).get("status", "not recorded"),
                    row["water_risk"]["status"],
                    *counts,
                    theme,
                ]
            )
            + " |"
        )
        if row["status"] == "exported":
            coverage[slug] = outer_ring(output / "maps" / slug)
        if harness_root is not None and "stage" in row:
            staged = output / "stage" / "maps" / slug
            crp = next(staged.glob("*.crp"))
            base = [
                "uv",
                "run",
                "--locked",
                "cs1-harness",
                "run",
                "--map",
                str(crp),
                "--probes",
                str(staged / "probes.json"),
                "--game-minutes",
                "60",
                "--sample-every",
                "5",
                "--wait-minutes",
                "120",
                "--retry-minutes",
                "30",
            ]
            for mode in ["first-hour", "empty-water"]:
                argv = base + (
                    ["--scenario", "first-hour"] if mode == "first-hour" else []
                )
                commands.append(
                    {
                        "slug": slug,
                        "mode": mode,
                        "executed": False,
                        "cwd": str(harness_root),
                        "argv": argv + ["--out", str(output / "native" / mode / slug)],
                        "crp_sha256": sha(crp),
                        "probes_sha256": sha(staged / "probes.json"),
                        "requires_owner_resolved_steam_readiness": True,
                        "requires_parent_first_hour_harness": mode == "first-hour",
                    }
                )
    lines.extend(["", "## Retained flags and limitations", ""])
    for slug in slugs:
        row = report["cases"].get(slug)
        if not row:
            continue
        lines.extend([f"### {slug}", ""])
        if eligibility := row.get("road_eligibility"):
            lines.append(
                f"- Road eligibility: **{eligibility['status']}**; fallback: {eligibility['fallback']}."
            )
            lines.extend("- " + reason for reason in eligibility["reason_codes"])
        if comparison := row.get("baseline_comparison"):
            lines.append(
                "- Original CRP: **"
                + (
                    "byte-identical"
                    if comparison["package_unchanged"]
                    else "changed; requires new package-bound native evidence"
                )
                + "**."
            )
        lines.extend("- " + reason for reason in row["water_risk"]["reasons"])
        if row.get("error"):
            lines.append("- Export error: " + row["error"])
        if row.get("stage_error"):
            lines.append("- Staging error: " + row["stage_error"])
        roads = row.get("generation", {}).get("real_roads", {})
        for field in ["air", "ship", "start_tile_reason"]:
            if field in roads:
                lines.append(
                    f"- {field}: " + json.dumps(roads[field], ensure_ascii=False)
                )
        if stage := row.get("stage"):
            lines.append(
                "- CRP SHA-256: `"
                + stage["crp_sha256"]
                + "`; staged byte-identically, panel expectations read from CRP."
            )
        lines.append("")
    lines.extend(
        [
            "## Evidence scope",
            "",
            "Each warning binds the final real-roads-seated grids and controls plus the landed risk tool/model. Full features, reasons and hashes are retained in cpu-report.json and each map's water-risk.json. No threshold or per-square waiver changed.",
            "",
            "outer-ring.json records resource cells, tree counts and wet nodes outside the central 5x5. These are CPU content counts, not native unlock/playability evidence. Native selection UI, car/train/plane/ship behavior, hydraulic soaks, growth and strict vanilla opening remain unverified.",
            "",
        ]
    )
    dump(output / "outer-ring.json", coverage)
    if harness_root is not None:
        dump(output / "native-commands.json", commands)
    (output / "CPU_RESULTS.md").write_text("\n".join(lines))
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--harness-root",
        type=Path,
        help="Record unexecuted native commands for the parent's qualified harness",
    )
    args = parser.parse_args()
    print(
        render(
            args.output.resolve(),
            args.harness_root.resolve() if args.harness_root else None,
        )
    )
