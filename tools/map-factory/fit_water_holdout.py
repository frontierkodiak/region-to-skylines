"""Freeze candidate cutoffs using only the old, geographically repeated corpus."""

import argparse
import hashlib
import itertools
import json
from pathlib import Path

from calibrate_water_risk import calibrate
from water_risk import DEFAULT_RULES, classify


def weighted_rates(rows, rules):
    groups = sorted({r["group"] for r in rows})
    rates = []
    for label in (True, False):
        per_group = []
        for group in groups:
            subset = [
                r for r in rows if r["group"] == group and r["labels"]["flood"] is label
            ]
            if subset:
                per_group.append(
                    sum(
                        bool(classify(r["features"], rules)["flood"]) is label
                        for r in subset
                    )
                    / len(subset)
                )
        rates.append(sum(per_group) / len(per_group) if per_group else None)
    return rates  # macro recall and specificity; versions do not weight a square more


def fit(rows):
    candidates = []
    for coastal, exposure in itertools.product(
        (0.5, 1, 1.5, 2, 3, 4), (0.001, 0.0025, 0.005, 0.01, 0.02, 0.05)
    ):
        rules = {
            **DEFAULT_RULES,
            "low_coastal_freeboard_m": coastal,
            "emitter_exposure_km2": exposure,
        }
        recall, specificity = weighted_rates(rows, rules)
        if recall is not None and recall >= 0.9:
            # Maximise macro specificity at >=90% macro recall. Break ties by
            # recall, then distance from the deployed cutoffs, then lower values.
            distance = abs(coastal - 1.5) / 1.5 + abs(exposure - 0.01) / 0.01
            rank = (specificity or 0, recall, -distance, -coastal, -exposure)
            candidates.append((rank, rules))
    if not candidates:
        return dict(DEFAULT_RULES)
    return max(candidates, key=lambda candidate: candidate[0])[1]


def freeze(rows_path, panel_path, output):
    rows = json.loads(rows_path.read_text())
    rows = [r for r in rows if r["complete_60"]]
    if len({r["group"] for r in rows}) != 5 or len(rows) != 50:
        raise ValueError("Fit must use the original 50 full runs / five landscapes")
    rules = fit(rows)
    model, report = calibrate(rows, rules=rules)
    groups = sorted({r["group"] for r in rows})
    diagnostics = []
    for group in groups:
        train = [r for r in rows if r["group"] != group]
        held = [r for r in rows if r["group"] == group]
        fold_rules = fit(train)
        _, fold = calibrate(held, rules=fold_rules)
        diagnostics.append(
            {
                "held_old_landscape": group,
                "rules": fold_rules,
                "metrics": fold["retrospective"]["flood"]["full_60_only"],
            }
        )
    output.mkdir(parents=True, exist_ok=False)
    (output / "model.json").write_text(json.dumps(model, indent=2) + "\n")
    frozen = {
        "schema": 1,
        "old_corpus_sha256": hashlib.sha256(rows_path.read_bytes()).hexdigest(),
        "panel_sha256": hashlib.sha256(panel_path.read_bytes()).hexdigest(),
        "model_sha256": hashlib.sha256(
            (output / "model.json").read_bytes()
        ).hexdigest(),
        "selection": "36 fixed flood cutoff pairs; highest equal-landscape specificity with macro recall >=90%; ties by recall, distance from deployed values, then smaller cutoffs. Complete old runs only.",
        "drying": "No old negative examples. Retain the corrected drying rule as an unvalidated comparator; no specificity fit is possible. Drop/rework after the one-shot holdout if it cannot beat always-warn.",
        "old_training": {
            k: r["full_60_only"] for k, r in report["retrospective"].items()
        },
        "old_leave_one_landscape_out": diagnostics,
        "limits": "Five old landscapes only. Neither training nor these folds is the new geographic test. No new outcomes may change this model or panel.",
    }
    (output / "freeze.json").write_text(json.dumps(frozen, indent=2) + "\n")
    print(json.dumps(frozen, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    parser.add_argument("panel", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    freeze(args.rows, args.panel, args.output)
