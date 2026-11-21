"""Project a frozen witness study into PL-1119-compatible observations.

This produces a static study report, never a live capability inventory or a
promise. Native negatives concern the specified witness, not every possible
plan. Absent attempts stay null; archived/player outcomes are not substituted.
"""

import argparse
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path

EMPTY = {"game": [], "steam_instances": [], "units_active": []}


def read(path):
    if path.exists():
        return json.loads(path.read_bytes())
    return json.loads(
        gzip.decompress(path.with_suffix(path.suffix + ".gz").read_bytes())
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal_paths(raw):
    """Require returned endpoints, not just a pathfinder success flag."""
    found = {"inbound": 0, "outbound": 0}
    for row in raw.get("paths", []):
        direction, positions = row.get("direction"), row.get("positions") or []
        if row.get("success") is not True or direction not in found or not positions:
            continue
        edge, grid = (
            (positions[-1], positions[0])
            if direction == "outbound"
            else (positions[0], positions[-1])
        )
        if (
            edge[0] == row.get("edge_segment")
            and edge[2] == row.get("edge_offset")
            and edge[2] in (0, 255)
            and grid[0] == row.get("grid_segment")
            and grid[2] == 128
        ):
            found[direction] += 1
    return {
        "complete": raw.get("complete") is True,
        **found,
        "both_directions": raw.get("complete") is True and all(found.values()),
    }


def observation(entry, capability, root, model, dll, collector, frozen_at):
    prediction, slug, split = entry["prediction"], entry["slug"], entry["split"]
    expected = prediction["capabilities"][capability]
    mode = "surface" if capability == "water" else "start"
    oracle = (
        "native_surface_load_v2" if capability == "water" else "exact_start_witness_v1"
    )
    folder = (
        root
        / ("native-v2-" + mode + ("-heldout" if split == "held_out" else ""))
        / slug
    )
    row = {
        "capability_id": capability,
        "square": prediction["square"],
        "split": split,
        "observed_at": None,
        "source_sha": prediction["source_sha"],
        "assessment_source_sha": prediction["assessment_source_sha"],
        "artifact_sha256": prediction["artifact_sha256"],
        "model_sha256": model,
        "witness_sha256": expected.get("witness_sha256"),
        "oracle": oracle,
        "predicted": expected["predicted"],
        "observed": None,
        "evidence": [],
        "scope": "Specified witness only; rejection is not geographic incapability",
        "limits": expected.get("limits", []),
    }
    if not (folder / "observation.json").exists():
        row["unscored_reason"] = "no_completed_native_attempt"
        return row
    raw = read(folder / "observation.json")
    source = raw.get("oracle_source") or {}
    if (
        raw.get("model_sha256") != model
        or raw.get("oracle_dll_sha256") != dll
        or raw.get("oracle") != oracle
        or raw.get("artifact_sha256") != row["artifact_sha256"]
        or raw.get("prediction_sha256") != entry["prediction_sha256"]
        or sha(folder / "prediction.json") != entry["prediction_sha256"]
        or source.get("commit") != collector
        or source.get("dirty") is not False
    ):
        raise ValueError("Native identity does not match the frozen study: " + slug)
    if not expected.get("witness"):
        raise ValueError("Native attempt has no frozen witness: " + slug)
    if split == "held_out" and datetime.fromisoformat(
        raw["controller_started_at"]
    ) < datetime.fromisoformat(frozen_at):
        raise ValueError("Held-out collector started before prediction freeze: " + slug)
    row.update(
        observed_at=raw.get("observed_at"),
        oracle_source=raw.get("oracle_source"),
        oracle_dll_sha256=dll,
    )
    for name in (
        "observation.json",
        "prediction.json",
        "witness-job.json",
        "native-paths.json",
    ):
        path = folder / name
        if path.exists():
            row["evidence"].append(
                {"path": str(path.relative_to(root)), "sha256": sha(path)}
            )
        elif path.with_suffix(path.suffix + ".gz").exists():
            compressed = path.with_suffix(path.suffix + ".gz")
            row["evidence"].append(
                {
                    "path": str(compressed.relative_to(root)),
                    "sha256": sha(compressed),
                    "encoding": "gzip",
                    "decompressed_sha256": hashlib.sha256(
                        gzip.decompress(compressed.read_bytes())
                    ).hexdigest(),
                }
            )
    if (
        raw.get("error")
        or raw.get("cleanup_qualified") is not True
        or raw.get("cleanup") != EMPTY
    ):
        row["unscored_reason"] = raw.get("error") or "unqualified_cleanup"
        return row
    job = read(folder / "witness-job.json")
    result = job["result"]
    if (
        job.get("state") != "done"
        or result.get("witness_sha256") != row["witness_sha256"]
    ):
        row["unscored_reason"] = "incomplete_or_unbound_native_job"
        return row
    expected_mode = (
        "fixed_surface_load_no_search"
        if capability == "water"
        else "exact_recorded_plan_no_search"
    )
    if result.get("mode") != expected_mode:
        raise ValueError("Native witness mode changed: " + slug)
    value = raw.get(
        "observed_water_capability" if capability == "water" else "observed_start"
    )
    if value is not None and type(value) is not bool:
        raise ValueError("Native label must be bool or null: " + slug)
    if capability == "water" and value is not result.get("observed_water_capability"):
        raise ValueError("Collector label disagrees with raw water job: " + slug)
    row["facets"] = {
        key: result.get(key)
        for key in (
            "observed_native_placement",
            "observed_shore_snap",
            "observed_footprint_predicates",
            "observed_surface_service",
            "fixture_qualified",
            "observed_horizon_game_minutes",
        )
    }
    if capability == "start" and value is not None:
        placement = result.get("observed_native_placement")
        if placement is True:
            paths = read(folder / "native-paths.json")
            if value is not bool(paths.get("inbound") and paths.get("outbound")):
                raise ValueError(
                    "Collector start label disagrees with native paths: " + slug
                )
            audit = literal_paths(paths)
            row["facets"]["literal_boundary_paths"] = audit
            if value is True and not audit["both_directions"]:
                row["unscored_reason"] = (
                    "success_flags_lack_matched_returned_outside_endpoints"
                )
                return row
        elif not (
            value is False
            and placement is False
            and result.get("failure_kind") == "native_tool_rejection"
        ):
            raise ValueError(
                "Start negative lacks a native necessary-condition rejection: " + slug
            )
    row["observed"] = value
    if value is None:
        row["unscored_reason"] = "native_result_unscored"
    return row


def summarize(rows):
    result = {}
    for split in ("fitting", "held_out"):
        result[split] = {}
        for capability in ("start", "water"):
            selected = [
                r
                for r in rows
                if r["split"] == split and r["capability_id"] == capability
            ]
            positive = [r for r in selected if r["predicted"] is True]
            agreed = sum(r["observed"] is True for r in positive)
            disagreed = sum(r["observed"] is False for r in positive)
            result[split][capability] = {
                "registered_squares": len(selected),
                "positive_predictions": len(positive),
                "agreed": agreed,
                "disagreed": disagreed,
                "unscored_positive": len(positive) - agreed - disagreed,
                "positive_witness_agreement": agreed / (agreed + disagreed)
                if agreed + disagreed
                else None,
            }
    return result


def report(snapshot, native_root, dll, collector, expected_snapshot):
    if sha(snapshot) != expected_snapshot:
        raise ValueError("Prediction snapshot differs from the recorded freeze")
    manifest = read(snapshot)
    export_path = native_root / "exports/cpu-report.json"
    if sha(export_path) != manifest["cpu_export_receipt_sha256"]:
        raise ValueError("Export receipt/warnings differ from the frozen study")
    exports = read(export_path)
    model = manifest["model_sha256"]
    rows = []
    for entry in manifest["rows"]:
        if entry["prediction"]["model"]["sha256"] != model:
            raise ValueError("Mixed frozen models")
        for capability in ("start", "water"):
            row = observation(
                entry,
                capability,
                native_root,
                model,
                dll,
                collector,
                manifest["frozen_at"],
            )
            row["water_risk"] = exports["cases"][entry["slug"]]["water_risk"]
            rows.append(row)
    return {
        "schema": 1,
        "snapshot_sha256": sha(snapshot),
        "export_receipt_sha256": sha(export_path),
        "model_sha256": model,
        "rows": rows,
        "summary": summarize(rows),
        "limits": [
            "Positive-witness agreement, not overall accuracy or sensitivity",
            "Fitting and regional holdouts remain separate; absent attempts are null",
            "Post-construction start paths are not fresh-map outside-road certificates",
            "Native-unit water load has conditional auxiliary power and a finite horizon",
            "No launch-context certificate, promise or physical exporter gain is implied",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "native_root", "out"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--dll-sha256", required=True)
    parser.add_argument("--collector-source-sha", required=True)
    parser.add_argument("--snapshot-sha256", required=True)
    args = parser.parse_args()
    result = report(
        args.snapshot,
        args.native_root,
        args.dll_sha256,
        args.collector_source_sha,
        args.snapshot_sha256,
    )
    with args.out.open("x") as output:
        output.write(json.dumps(result, indent=2) + "\n")
