"""Evaluate engineered storage separately from pooled historical drying gates.

Natural-feature inventory and retention are not implemented here. A storage
check cannot issue an overall maintained-water promise.
"""

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "calibration/pl1191-construction-v1"


def storage_outcome(hydro, report, samples):
    """Use authored reservoir positions, never a point selected from wet results."""
    raw = (ROOT / "maintained-water-definition.json").read_bytes()
    definition = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    if (
        digest
        != json.loads((ROOT / "outcome-freeze.json").read_text())["definition_sha256"]
    ):
        raise ValueError("Maintained-water definition differs from outcome freeze")
    policy = definition["native_observation"]
    minimum_depth = definition["thresholds"]["storage_exact_depth_m_min"]
    minutes = [
        (row["stats"]["frame"] - report["start_frame"])
        / report["frames_per_game_minute"]
        for row in samples
    ]
    gaps = [b - a for a, b in zip(minutes, minutes[1:])]
    complete = (
        len(samples) >= policy["samples_min"]
        and report["game_minutes"] >= policy["game_minutes_min"]
        and bool(minutes)
        and abs(minutes[0]) <= 0.001
        and minutes[-1] >= policy["game_minutes_min"]
        and all(0 < gap <= policy["largest_gap_game_minutes_max"] for gap in gaps)
    )
    anchors = []
    for index, source in enumerate(hydro["sources"]):
        if source.get("class") != "reservoir":
            continue
        x, _, z = source["position"]
        depths, missing, failed = [], [], []
        for row in samples:
            matches = [
                p.get("depth")
                for p in row["water"]["samples"]
                if math.hypot(p["x"] - x, p["z"] - z) <= 0.001
            ]
            if not matches or any(
                not isinstance(v, (int, float)) or not math.isfinite(v) for v in matches
            ):
                missing.append(row["label"])
                continue
            depth = min(matches)
            depths.append(depth)
            if depth < minimum_depth:
                failed.append(row["label"])
        anchors.append(
            {
                "source_index": index,
                "position_xz": [x, z],
                "status": "fail"
                if failed
                else "pass"
                if complete and not missing
                else "unknown",
                "minimum_exact_depth_m": min(depths) if depths else None,
                "failed_samples": failed,
                "missing_samples": missing,
            }
        )
    statuses = {a["status"] for a in anchors}
    status = (
        "not_applicable"
        if not anchors
        else "fail"
        if "fail" in statuses
        else "unknown"
        if "unknown" in statuses
        else "pass"
    )
    return {
        "schema": "polli.engineered-storage-outcome/1",
        "definition_sha256": digest,
        "status": status,
        "anchors": anchors,
        "observation_complete": complete,
        "largest_sample_gap_game_minutes": max(gaps) if gaps else None,
        "scope": "Authored reservoir anchors only; natural-feature coverage and overall maintained-water qualification are not assessed.",
    }
