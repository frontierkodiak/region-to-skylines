"""Score the frozen predictions against the frozen native observations.

This is a new, read-only retrospective evaluator. It does not import or re-run
any earlier scorer, predictor, judge or refit, and it changes no old file. It
reads `predictions.json` (written without outcomes) and, for the first time,
each opening's `observation.json.gz` bytes.

Labels follow the accepted protocol's definition, re-implemented here so this
study is independent of `cs1_harness.rail_study`:

* exact success  - result complete and released, success true, and the returned
                   first and last positions equal the requested literal offsets.
* observed failure - result complete and released, success false. That is a
                   failure of this exact request/mode/flags/protocol, never a
                   statement that the place has no railway.
* unknown        - anything else (incomplete, unreleased, endpoint mismatch,
                   missing row). Never scored.

Run:  .venv/bin/python capability-evidence/rail-query-model-v1/evaluate.py
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CAPABILITY = HERE.parent

EXACT = "exact_path_success"
FAILURE = "selected_query_failure"
UNKNOWN = "unknown"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_json(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf8") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def classify(row):
    """Label one observation row, or None when the row is absent."""
    if row is None:
        return UNKNOWN, {"reason": "row_absent"}
    result = row.get("result") or {}
    if not result.get("complete") or not result.get("released"):
        return UNKNOWN, {"reason": "incomplete_or_unreleased"}
    if not result.get("success"):
        return FAILURE, {
            "flags": result.get("flags"),
            "length": result.get("length"),
            "reason": "native_no_path",
        }
    positions = result.get("positions") or []
    request = row.get("request") or {}
    if not positions or positions[0] != request.get("from") or positions[-1] != request.get("to"):
        return UNKNOWN, {"reason": "returned_endpoint_mismatch"}
    return EXACT, {"flags": result.get("flags"), "length": result.get("length")}


def empty_confusion():
    return {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "abstain": 0}


def add(confusion, predicted, observed):
    if observed not in (EXACT, FAILURE):
        return
    if predicted == "abstain":
        confusion["abstain"] += 1
    elif predicted == "success":
        confusion["tp" if observed == EXACT else "fp"] += 1
    else:
        confusion["tn" if observed == FAILURE else "fn"] += 1


def scored(confusion):
    return confusion["tp"] + confusion["fp"] + confusion["tn"] + confusion["fn"]


def ratios(confusion):
    tp, fp, tn, fn = (confusion[key] for key in ("tp", "fp", "tn", "fn"))
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    negative_precision = tn / (tn + fn) if tn + fn else None
    return {
        "scored": scored(confusion),
        "precision": precision,
        "recall": recall,
        "negative_precision": negative_precision,
        "f1": (None if precision is None or recall in (None, 0) else 2 * precision * recall / (precision + recall)),
    }


def collect(predictions, openings):
    observations = {}
    for entry in openings["openings"]:
        raw = CAPABILITY / entry["raw"]
        observation = load_json(raw / "observation.json.gz")
        rows = observation.get("paths") or []
        if observation.get("completed") is not True:
            rows = []
        observations[entry["opening"]] = {
            "rows": rows,
            "observation_sha256": digest((raw / "observation.json.gz").read_bytes()),
            "query_freeze_sha256": digest((raw / "query-freeze.json.gz").read_bytes()),
            "networks_sha256": digest((raw / "networks.json.gz").read_bytes()),
            "artifact_sha256": observation.get("artifact_sha256"),
            "completed": observation.get("completed"),
            "context": {
                key: observation.get("native_context", {}).get(key)
                for key in ("update_mode", "invert_traffic", "no_workshop", "mods_enabled")
            },
        }
    return observations


def evaluate(predictions, observations, openings):
    by_rule = {rule: empty_confusion() for rule in predictions["rules"]}
    by_group = {}
    per_package = {}
    labels = Counter()
    counterexamples = []
    exact_same_edge = 0
    exact_distinct_edge = 0
    for query in predictions["queries"]:
        opening = query["opening"]
        observation = observations[opening]
        row = observation["rows"][query["plan_index"]] if query["plan_index"] < len(observation["rows"]) else None
        observed, detail = classify(row)
        labels[observed] += 1
        if observed == EXACT:
            edges = query["request"]["endpoint_edges"]
            if edges[0] == edges[1]:
                exact_same_edge += 1
            else:
                exact_distinct_edge += 1
        group = query["group"]
        per_package.setdefault(
            opening,
            {
                "split": query["split"],
                "group": group,
                "labels": Counter(),
                "by_rule": {rule: empty_confusion() for rule in predictions["rules"]},
            },
        )
        per_package[opening]["labels"][observed] += 1
        for rule in predictions["rules"]:
            predicted = query["predictions"][rule]["prediction"]
            add(by_rule[rule], predicted, observed)
            add(per_package[opening]["by_rule"][rule], predicted, observed)
            by_group.setdefault(
                (query["split"], group), {r: empty_confusion() for r in predictions["rules"]}
            )
            add(by_group[(query["split"], group)][rule], predicted, observed)
            if rule == predictions["primary_rule"] and observed in (EXACT, FAILURE):
                if (predicted == "success") != (observed == EXACT) and len(counterexamples) < 400:
                    counterexamples.append(
                        {
                            "kind": "false_positive" if predicted == "success" else "false_negative",
                            "query_id": query["query_id"],
                            "opening": opening,
                            "group": group,
                            "request": query["request"],
                            "observed": observed,
                            "observed_detail": detail,
                            "predicted_detail": query["predictions"][rule]["detail"],
                            "observation_sha256": observation["observation_sha256"],
                            "query_freeze_sha256": observation["query_freeze_sha256"],
                            "networks_sha256": observation["networks_sha256"],
                            "artifact_sha256": observation["artifact_sha256"],
                        }
                    )

    def summarise(confusion):
        result = dict(confusion)
        result.update(ratios(confusion))
        result["coverage"] = (
            scored(confusion) / (scored(confusion) + confusion["abstain"])
            if scored(confusion) + confusion["abstain"]
            else None
        )
        return result

    return {
        "labels": dict(labels),
        "exact_same_edge": exact_same_edge,
        "exact_distinct_edge": exact_distinct_edge,
        "rules": {rule: summarise(confusion) for rule, confusion in by_rule.items()},
        "packages": {
            opening: {
                "split": entry["split"],
                "group": entry["group"],
                "labels": dict(entry["labels"]),
                "rules": {rule: summarise(c) for rule, c in entry["by_rule"].items()},
            }
            for opening, entry in per_package.items()
        },
        "groups": {
            f"{split}:{group}": {
                "split": split,
                "group": group,
                "rules": {rule: summarise(c) for rule, c in confusion.items()},
            }
            for (split, group), confusion in by_group.items()
        },
        "counterexamples": counterexamples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    openings = json.loads((HERE / "openings.json").read_text())
    predictions = load_json(HERE / "predictions.json")
    observations = collect(predictions, openings)
    report = evaluate(predictions, observations, openings)
    document = {
        "schema": 1,
        "predictions_sha256": digest((HERE / "predictions.json").read_bytes()),
        "protocol_sha256": predictions["protocol_sha256"],
        "primary_rule": predictions["primary_rule"],
        "openings": {
            opening: {key: value for key, value in observation.items() if key != "rows"}
            for opening, observation in observations.items()
        },
        "result": report,
    }
    if args.check:
        frozen = json.loads((HERE / "evaluation.json").read_text())
        if frozen["result"] != report:
            raise SystemExit("evaluation is not reproducible")
        print(json.dumps({"checked": True, "evaluation_sha256": digest((HERE / "evaluation.json").read_bytes())}))
        return
    (HERE / "evaluation.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    primary = report["rules"][predictions["primary_rule"]]
    print(
        json.dumps(
            {
                "labels": report["labels"],
                "primary": primary,
                "evaluation_sha256": digest((HERE / "evaluation.json").read_bytes()),
            },
            default=str,
        )
    )


if __name__ == "__main__":
    main()
