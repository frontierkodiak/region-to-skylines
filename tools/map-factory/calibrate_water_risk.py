"""Retrospectively score the general input-only screen against native receipts.

Null labels remain censored. Group identities only organize this report; the
production screen never receives a place, package fingerprint or native result.
The rule family was developed on this corpus: these are calibration figures,
not an untouched geographic holdout or calibrated probabilities of safety.
"""

import argparse
from collections import Counter
import json
from pathlib import Path

from water_risk import DEFAULT_RULES, classify


def metrics(rows):
    counts = {
        key: sum(r["outcome"] == key for r in rows) for key in ["tp", "fp", "tn", "fn"]
    }
    tp, fp, tn, fn = (counts[k] for k in ["tp", "fp", "tn", "fn"])
    return {
        **counts,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "specificity": tn / (tn + fp) if tn + fp else None,
        "positive_runs": tp + fn,
        "negative_runs": tn + fp,
    }


def evaluate(rows):
    results = {}
    for target in ["flood", "drying"]:
        predictions = []
        for row in rows:
            label = row["labels"][target]
            if label is None:
                continue
            positive = bool(classify(row["features"])[target])
            outcome = (
                ("tp" if label else "fp") if positive else ("fn" if label else "tn")
            )
            predictions.append(
                {
                    "run": row["run"],
                    "package_sha256": row["package_sha256"],
                    "square": row["group"],
                    "label": label,
                    "outcome": outcome,
                    "complete_60": row["complete_60"],
                    "reference_stratum": "mapped_or_frozen"
                    if "reference_water" in (row.get("flood_reference") or "")
                    or "mapped_water" in (row.get("flood_reference") or "")
                    else "legacy_initial_water",
                }
            )
        results[target] = {
            **metrics(predictions),
            "runs": len(predictions),
            "squares": len({r["square"] for r in predictions}),
            "full_60_only": metrics([r for r in predictions if r["complete_60"]]),
            "full_60_per_square": {
                g: metrics(
                    [r for r in predictions if r["complete_60"] and r["square"] == g]
                )
                for g in sorted({r["square"] for r in predictions})
            },
            "per_square": {
                g: metrics([r for r in predictions if r["square"] == g])
                for g in sorted({r["square"] for r in predictions})
            },
            "per_reference_stratum": {
                group: metrics(
                    [r for r in predictions if r["reference_stratum"] == group]
                )
                for group in sorted({r["reference_stratum"] for r in predictions})
            },
            "misses": [r for r in predictions if r["outcome"] == "fn"],
            "false_alarms": [r for r in predictions if r["outcome"] == "fp"],
            "predictions": predictions,
        }
    return results


def calibrate(rows, coverage=None):
    known = [r for r in rows if any(v is not None for v in r["labels"].values())]
    results = evaluate(known)
    features = sorted(known[0]["features"])
    model = {
        "schema": 1,
        "version": "water-risk-v1",
        "rules": DEFAULT_RULES,
        "features": features,
        "ranges": {
            f: [
                min(r["features"][f] for r in known),
                max(r["features"][f] for r in known),
            ]
            for f in features
        },
        "calibration": {
            "runs": len(known),
            "squares": len({r["group"] for r in known}),
            "complete_60_runs": sum(r["complete_60"] for r in known),
            "method": "Retrospective calibration of one shared conservative rule; no independent geographic holdout.",
            "native_simulation": False,
            "results": {
                k: {
                    f: v
                    for f, v in d["full_60_only"].items()
                    if f
                    in [
                        "tp",
                        "fp",
                        "tn",
                        "fn",
                        "precision",
                        "recall",
                        "specificity",
                        "positive_runs",
                        "negative_runs",
                    ]
                }
                for k, d in results.items()
            },
        },
    }
    report = {
        "retrospective": results,
        "definitions": {
            "flood": "Original no_flooding check exceeds 0.05 km2, retaining each run's original reference/mask.",
            "drying": "At least one initialized monitored point ends dry and not within 64m of water, OR an original required-water observation is missing at endpoint/sampled-throughout. Advisory label, NOT a replacement for the original 95% native gate. Exact-point thinning is reported separately.",
            "censoring": "Observed short-run failures are positive; passing runs shorter than sixty minutes are null, not negatives.",
        },
        "original_dry_gate": dict(
            Counter(str(r["original_dry_gate_failed"]) for r in known)
        ),
        "original_dry_gate_full_60": dict(
            Counter(
                str(r["original_dry_gate_failed"]) for r in known if r["complete_60"]
            )
        ),
        "required_water_loss_full_60": dict(
            Counter(str(r["required_water_loss"]) for r in known if r["complete_60"])
        ),
        "all_warn_baseline_full_60": {
            target: metrics(
                [
                    {"outcome": "tp" if r["labels"][target] else "fp"}
                    for r in known
                    if r["complete_60"] and r["labels"][target] is not None
                ]
            )
            for target in ["flood", "drying"]
        },
        "limits": [
            "Only five distinct fixture squares; repeated runs/versions are not independent geography.",
            "Rules were developed using this corpus; retrospective results are not independent holdout validation.",
            "Older mask/cohort/writer versions differ. Original receipts and references are retained, not rewritten.",
            "Monitored initialized points include optional water but do not exhaustively label carved beds or visible continuity. Exact-point thinning is not cancelled by nearby-water coverage.",
            "No observed drying-negative complete run exists in this corpus. Drying specificity/false-positive rate cannot be measured; an always-warn screen has the same apparent drying performance.",
            "Unbound/unavailable inputs are explicitly excluded from scoring, never silently counted as safe.",
            "Nominal source capacities and static spill potential are not measured discharge or a forward hydraulic model.",
        ],
    }
    if coverage is not None:
        unscored_full = [
            c
            for c in coverage
            if c["minutes"] >= 60
            and c["status"] != "included"
            and c["status"] != "excluded_nonempty_city"
        ]
        missing_positives = {
            target: sum(
                c.get("native_outcome", {}).get("labels", {}).get(target) is True
                for c in unscored_full
            )
            for target in ["flood", "drying"]
        }
        model["calibration"].update(
            registry_entries=len(coverage),
            complete_60_registry_runs=sum(
                c["minutes"] >= 60 and c["status"] != "excluded_nonempty_city"
                for c in coverage
            ),
            unscored_complete_60_runs=len(unscored_full),
            unscored_complete_60_positive_outcomes=missing_positives,
        )
        report["coverage"] = {
            "entries": len(coverage),
            "statuses": dict(Counter(c["status"] for c in coverage)),
            "unscored_complete_soaks": unscored_full,
            "unscored_positive_full_outcomes": missing_positives,
            "recall_lower_bound_if_unscored_positives_are_missed": {
                target: results[target]["full_60_only"]["tp"]
                / (
                    results[target]["full_60_only"]["tp"]
                    + results[target]["full_60_only"]["fn"]
                    + missing_positives[target]
                )
                if results[target]["full_60_only"]["tp"]
                + results[target]["full_60_only"]["fn"]
                + missing_positives[target]
                else None
                for target in ["flood", "drying"]
            },
        }
    return model, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--coverage", type=Path)
    args = parser.parse_args()
    model, report = calibrate(
        json.loads(args.rows.read_text()),
        json.loads(args.coverage.read_text()) if args.coverage else None,
    )
    args.model.write_text(json.dumps(model, indent=2) + "\n")
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(model["calibration"], indent=2))
