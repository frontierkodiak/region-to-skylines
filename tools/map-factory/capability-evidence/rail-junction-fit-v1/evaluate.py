"""Score the frozen predictions against the frozen native observations.

This is the study's only evaluator. It reads the frozen `protocol.json`,
`features.json` and `predictions.json`, binds them to the accepted study's
frozen plans, package bytes and observation bytes (`binding.bind_observations`,
which raises `BindingError` rather than scoring a mismatch), and only then
labels and scores.

It does not import or re-run any earlier scorer, predictor, judge or refit; it
changes no file outside this prefix. The accepted `rail-query-model-v1`
`evaluate.py` is not run.

Reports:
* every rule's confusion on the whole set, on the stock controls, on the cohort
  and per opening, with precision/recall/specificity/balanced accuracy and
  coverage/abstention (null, never zero, when a denominator is empty);
* strict leave-one-package-out over the cohort, selecting the rule on training
  packages only, plus the two fixed primary rules evaluated out of fold;
* the stock controls as held-out packages trained only on the cohort;
* the paired comparison of the frozen v2 reference rule and its tangent
  counterpart on identical requests;
* every exact counterexample for the frozen reference, its tangent
  counterpart, and the cohort's descriptive selection.

Run:  .venv/bin/python capability-evidence/rail-junction-fit-v1/evaluate.py
Check: ... --check
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[1]), str(HERE)]

import binding  # noqa: E402
import junction_model as jm  # noqa: E402

FREEZE = "rail-junction-fit-v1"
PROTOCOL = HERE / "protocol.json"
FEATURES = HERE / "features.json"
PREDICTIONS = HERE / "predictions.json"
EVALUATION = HERE / "evaluation.json"
REFERENCE = jm.PRIMARY_REFERENCE
CORRESPONDENCE = jm.PRIMARY_EQUIVALENT


def block(rows, rule):
    counts = binding.confusion(
        [(row["predictions"][rule]["prediction"], row["label"]) for row in rows]
    )
    return {"counts": counts, "rates": binding.rates(counts)}


def by_group(rows, rule):
    openings = sorted({row["opening"] for row in rows})
    return {
        "all": block(rows, rule),
        "stock_controls": block(
            [row for row in rows if row["split"] == "stock_controls"], rule
        ),
        "cohort": block([row for row in rows if row["split"] == "cohort"], rule),
        "openings": {
            name: block([row for row in rows if row["opening"] == name], rule)
            for name in openings
        },
    }


def errors(rows, rule):
    found = []
    for row in rows:
        prediction = row["predictions"][rule]
        if prediction["prediction"] == binding.ABSTAIN:
            found.append(
                {
                    "kind": "abstain",
                    "query_id": row["query_id"],
                    "opening": row["opening"],
                    "plan_index": row["plan_index"],
                    "request": row["request"],
                    "label": row["label"],
                    "detail": prediction["detail"],
                }
            )
            continue
        if prediction["prediction"] == row["label"]:
            continue
        if row["label"] not in (binding.SUCCESS, binding.NO_PATH):
            continue
        found.append(
            {
                "kind": "false_positive"
                if prediction["prediction"] == binding.SUCCESS
                else "false_negative",
                "query_id": row["query_id"],
                "opening": row["opening"],
                "plan_index": row["plan_index"],
                "request": row["request"],
                "label": row["label"],
                "detail": prediction["detail"],
                "label_detail": row["label_detail"],
            }
        )
    return found


def paired(rows, left, right):
    """The same requests scored under two rules: a paired confusion of errors."""
    table = {
        "both_correct": 0,
        "left_only_correct": 0,
        "right_only_correct": 0,
        "both_wrong": 0,
        "not_comparable": 0,
    }
    for row in rows:
        if row["label"] not in (binding.SUCCESS, binding.NO_PATH):
            table["not_comparable"] += 1
            continue
        a = row["predictions"][left]["prediction"]
        b = row["predictions"][right]["prediction"]
        if a == b:
            key = "both_correct" if a == row["label"] else "both_wrong"
        elif a == row["label"]:
            key = "left_only_correct"
        elif b == row["label"]:
            key = "right_only_correct"
        else:
            key = "both_wrong"
        table[key] += 1
    table["left"] = left
    table["right"] = right
    table["rows"] = len(rows)
    return table


def selection_rows(rows, names):
    return [row for row in rows if row["opening"] in names]


def fold_results(rows, fold, candidates, criterion):
    training = selection_rows(rows, fold["selection_train"])
    held = selection_rows(rows, fold["held_out"])
    selected, scores, note = binding.select_rule(training, candidates, criterion)
    held_out = {}
    for name, rule in (
        ("selected", selected),
        ("reference", REFERENCE),
        ("correspondence", CORRESPONDENCE),
    ):
        if rule is None:
            held_out[name] = {"rule": None, "counts": None, "rates": None}
            continue
        held_out[name] = {"rule": rule, **block(held, rule)}
    return {
        "fold": fold["fold"],
        "kind": fold["kind"],
        "train_packages": fold["train"],
        "selection_train": fold["selection_train"],
        "held_out": fold["held_out"],
        "training_rows": len(training),
        "held_rows": len(held),
        "selected": selected,
        "selection_note": note,
        "tied_at_best": note.get("tied_at_best", []),
        "training_scores": {
            rule: {
                "counts": scores[rule]["counts"],
                "rates": scores[rule]["rates"],
            }
            for rule in (selected, REFERENCE, CORRESPONDENCE)
            if rule is not None
        },
        "held_out_scores": held_out,
    }


def pooled_for(rows, folds, results, subset, key):
    """Pool the out-of-fold held-out rows of one fold set under one rule choice."""
    pairs = []
    for fold, result in zip(folds, results):
        if fold not in subset:
            continue
        rule = result["held_out_scores"][key]["rule"]
        if rule is None:
            continue
        for row in selection_rows(rows, fold["held_out"]):
            pairs.append((row["predictions"][rule]["prediction"], row["label"]))
    counts = binding.confusion(pairs)
    return {"counts": counts, "rates": binding.rates(counts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    manifest = binding.load_manifest()
    accepted = binding.accepted_openings(manifest, verify_observations=True)
    expected_queries, per_opening = binding.expected_query_set(
        accepted["openings"], accepted["integrity"]
    )
    protocol = json.loads(PROTOCOL.read_text())
    features = json.loads(FEATURES.read_text())
    predictions = json.loads(PREDICTIONS.read_text())
    if protocol["study"] != FREEZE or features["study"] != FREEZE:
        raise SystemExit("protocol or features belong to another study")
    if features["protocol_sha256"] != predictions["protocol_sha256"]:
        raise SystemExit("features were frozen against a different protocol")
    if predictions["rules"] != protocol["rules"]:
        raise SystemExit("predictions and protocol disagree on the rule list")
    binding.verify_query_set(predictions, accepted["openings"], expected_queries)
    bundles = binding.bind_observations(
        predictions, protocol, features, accepted["openings"], accepted["packages"]
    )
    labels = binding.labels(bundles, expected_queries)
    rows = [
        {
            "query_id": query["query_id"],
            "plan_index": query["plan_index"],
            "opening": query["opening"],
            "split": query["split"],
            "group": query["group"],
            "package": query["package"],
            "request": query["request"],
            "label": labels[query["query_id"]]["label"],
            "label_detail": labels[query["query_id"]]["detail"],
            "predictions": predictions["queries"][index]["predictions"],
        }
        for index, query in enumerate(predictions["queries"])
    ]
    rules = protocol["rules"]
    baselines = set(protocol["baselines"])
    candidates = [rule for rule in rules if rule not in baselines]
    criterion = protocol["selection"]["criterion"]

    label_counts = {"success": 0, "no_path": 0, "unknown": 0}
    per_opening_labels = {}
    for row in rows:
        label_counts[row["label"]] = label_counts.get(row["label"], 0) + 1
        bucket = per_opening_labels.setdefault(
            row["opening"], {"success": 0, "no_path": 0, "unknown": 0, "rows": 0}
        )
        bucket[row["label"]] = bucket.get(row["label"], 0) + 1
        bucket["rows"] += 1

    rule_rows = {rule: by_group(rows, rule) for rule in rules}
    cohort_rows = [row for row in rows if row["split"] == "cohort"]
    stock_rows = [row for row in rows if row["split"] == "stock_controls"]

    descriptive_selected, descriptive_scores, descriptive_note = binding.select_rule(
        cohort_rows, candidates, criterion
    )
    folds = protocol["folds"]["folds"]
    results = [fold_results(rows, fold, candidates, criterion) for fold in folds]
    cohort_folds = [fold for fold in folds if fold["kind"].startswith("cohort")]
    control_folds = [fold for fold in folds if not fold["kind"].startswith("cohort")]

    pooled_scores = {
        "cohort": {
            key: pooled_for(rows, folds, results, cohort_folds, key)
            for key in ("selected", "reference", "correspondence")
        },
        "stock_controls": {
            key: pooled_for(rows, folds, results, control_folds, key)
            for key in ("selected", "reference", "correspondence")
        },
    }

    focus = [REFERENCE, CORRESPONDENCE]
    if descriptive_selected and descriptive_selected not in focus:
        focus.append(descriptive_selected)

    bindings = {
        "manifest_sha256": binding.file_digest(binding.MANIFEST),
        "protocol_sha256": binding.file_digest(PROTOCOL),
        "features_sha256": binding.file_digest(FEATURES),
        "predictions_sha256": binding.file_digest(PREDICTIONS),
        "accepted_prefix_files": predictions["sources"]["accepted_artifacts"],
        "study_sources": predictions["sources"]["own"],
        "accepted_sources": predictions["sources"]["accepted"],
        "packages": {
            key: {"locator": value["locator"], "sha256": value["sha256"]}
            for key, value in accepted["packages"].items()
        },
        "openings": {
            name: {
                "selected_requests": per_opening[name]["selected"],
                "networks_sha256": per_opening[name]["networks_sha256"],
                "plan_sha256": per_opening[name]["plan_sha256"],
                "observation_sha256": per_opening[name]["observation_sha256"],
                "completed": bundles[name]["completed"],
                "native_context": bundles[name]["native_context"],
                "build": bundles[name]["build"],
                "observed_rows": len(bundles[name]["rows"]),
            }
            for name in sorted(per_opening)
        },
        "queries": len(rows),
        "labelled": sum(
            1 for row in rows if row["label"] in (binding.SUCCESS, binding.NO_PATH)
        ),
        "unknown": label_counts["unknown"],
    }
    report = {
        "schema": 1,
        "study": FREEZE,
        "freeze": FREEZE,
        "scored_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "bindings": bindings,
        "labels": {
            "counts": label_counts,
            "per_opening": dict(sorted(per_opening_labels.items())),
        },
        "groups": {
            "stock_controls": protocol["splits"]["stock_controls"]["packages"],
            "cohort": protocol["splits"]["cohort"]["packages"],
            "zero_query": protocol["folds"]["zero_query"],
        },
        "rules": rule_rows,
        "selections": {
            "cohort_descriptive": {
                "criterion": criterion,
                "rule": descriptive_selected,
                "note": descriptive_note,
                "scores": {
                    rule: {
                        "counts": descriptive_scores[rule]["counts"],
                        "rates": descriptive_scores[rule]["rates"],
                    }
                    for rule in candidates
                },
            }
        },
        "folds": results,
        "pooled_out_of_fold": pooled_scores,
        "primary_paired": {
            "all": paired(rows, REFERENCE, CORRESPONDENCE),
            "cohort": paired(cohort_rows, REFERENCE, CORRESPONDENCE),
            "stock_controls": paired(stock_rows, REFERENCE, CORRESPONDENCE),
        },
        "counterexamples": {rule: errors(rows, rule) for rule in focus},
        "baselines": sorted(baselines),
        "candidates": candidates,
    }
    if args.check:
        frozen = json.loads(EVALUATION.read_text())
        for key in (
            "labels",
            "rules",
            "folds",
            "pooled_out_of_fold",
            "primary_paired",
            "counterexamples",
            "bindings",
        ):
            if frozen[key] != report[key]:
                raise SystemExit(f"evaluation is not reproducible: {key}")
        print(
            json.dumps(
                {"checked": True, "evaluation_sha256": binding.file_digest(EVALUATION)}
            )
        )
        return
    EVALUATION.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    summary = {
        "queries": len(rows),
        "labels": label_counts,
        "reference": rule_rows[REFERENCE]["all"],
        "correspondence": rule_rows[CORRESPONDENCE]["all"],
        "cohort_descriptive_selected": descriptive_selected,
        "pooled_cohort": pooled_scores["cohort"],
        "evaluation_sha256": binding.file_digest(EVALUATION),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
