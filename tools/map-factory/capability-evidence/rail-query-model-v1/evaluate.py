"""Score the frozen predictions against the frozen native observations.

This is a new, read-only retrospective evaluator. It does not import or re-run
any earlier scorer, predictor, judge or refit, and it changes no old file. It
reads the corrected `predictions.json` (written without outcomes) and, for the
first time, each opening's `observation.json.gz` bytes.

Corrected binding (v2). Before scoring, every prediction is bound to its
records: the frozen plan request at `plan_index`, the observed row request at
the same index, the package locator and SHA-256, the network-snapshot and
query-freeze hashes, the protocol hash and the model sources. A mismatch is a
`BindingError`, not a score. A missing row (an incomplete opening) is an
Unknown; a present row with a missing or non-boolean `complete`, `released` or
`success` is a `BindingError`.

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
OUTPUT = HERE / "corrected"

EXACT = "exact_path_success"
FAILURE = "selected_query_failure"
UNKNOWN = "unknown"

# The rules whose individual errors the report shows in full.
FOCUS_RULES = ("lane:orientation_index:forbidden", "junction:continuation:any_lane")
LABEL_FIELDS = ("complete", "released", "success")


class BindingError(ValueError):
    """The predictions and the frozen records do not bind; refuse to score."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    return digest(Path(path).read_bytes())


def load_json(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf8") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def classify(row):
    """Label one observation row; a missing row is Unknown, invalid fields raise."""
    if row is None:
        return UNKNOWN, {"reason": "row_absent"}
    result = row.get("result")
    if not isinstance(result, dict):
        raise BindingError("observation row has no result object")
    for field in LABEL_FIELDS:
        if not isinstance(result.get(field), bool):
            raise BindingError(f"observation result has no boolean {field!r}")
    if not result["complete"] or not result["released"]:
        return UNKNOWN, {"reason": "incomplete_or_unreleased"}
    if not result["success"]:
        return FAILURE, {
            "flags": result.get("flags"),
            "length": result.get("length"),
            "reason": "native_no_path",
        }
    positions = result.get("positions") or []
    request = row.get("request") or {}
    if (
        not positions
        or positions[0] != request.get("from")
        or positions[-1] != request.get("to")
    ):
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
        "f1": (
            None
            if precision is None or recall in (None, 0)
            else 2 * precision * recall / (precision + recall)
        ),
    }


def collect(openings):
    """Read the frozen observation, plan and package bytes for every opening."""
    observations = {}
    for entry in openings["openings"]:
        raw = CAPABILITY / entry["raw"]
        observation = load_json(raw / "observation.json.gz")
        plan = load_json(raw / "query-freeze.json.gz")
        observations[entry["opening"]] = {
            "rows": observation.get("paths") or [],
            "plan_requests": plan["plan"]["requests"],
            "completed": observation.get("completed") is True,
            "observation_sha256": digest((raw / "observation.json.gz").read_bytes()),
            "query_freeze_sha256": digest((raw / "query-freeze.json.gz").read_bytes()),
            "networks_sha256": digest((raw / "networks.json.gz").read_bytes()),
            "artifact_sha256": observation.get("artifact_sha256"),
            "package": observation.get("package"),
            "context": {
                key: observation.get("native_context", {}).get(key)
                for key in (
                    "update_mode",
                    "invert_traffic",
                    "no_workshop",
                    "mods_enabled",
                )
            },
        }
    return observations


def bind(predictions, observations, openings, packages=None):
    """Raise BindingError unless every prediction is bound to its frozen records."""
    import model

    packages = packages or load_json(HERE / "packages.json")["packages"]
    if predictions.get("freeze") != "rail-query-model-v2-corrected":
        raise BindingError("predictions are not the corrected v2 freeze")
    if predictions.get("model_version") != model.MODEL_VERSION:
        raise BindingError("predictions were made by a different model version")
    protocol = OUTPUT / "protocol.json"
    if not protocol.exists():
        raise BindingError("corrected protocol.json is missing")
    if digest(protocol.read_bytes()) != predictions.get("protocol_sha256"):
        raise BindingError("corrected protocol.json does not match the predictions")
    for name, expected in predictions.get("sources", {}).items():
        path = ROOT / name
        if not path.exists() or file_digest(path) != expected:
            raise BindingError(f"model source {name} changed after the freeze")

    entries = {entry["opening"]: entry for entry in openings["openings"]}
    for opening, observation in observations.items():
        entry = entries[opening]
        frozen = predictions["openings"][opening]
        package = packages[entry["package"]]
        if observation["networks_sha256"] != frozen["networks_sha256"]:
            raise BindingError(f"{opening}: network snapshot changed")
        if observation["query_freeze_sha256"] != frozen["query_freeze_sha256"]:
            raise BindingError(f"{opening}: query freeze changed")
        if observation["artifact_sha256"] != package["sha256"]:
            raise BindingError(
                f"{opening}: package hash does not match the frozen artifact"
            )
        if observation["package"] != package["locator"]:
            raise BindingError(
                f"{opening}: package locator differs from the frozen locator"
            )
        requests = observation["plan_requests"]
        rows = observation["rows"]
        if observation["completed"] and len(rows) != len(requests):
            raise BindingError(f"{opening}: completed observation is missing plan rows")
        if len(rows) > len(requests):
            raise BindingError(
                f"{opening}: observation has more rows than the frozen plan"
            )
        if frozen["selected_requests"] != sum(
            1
            for request in requests
            if not request["diagnostic"] and request["position_kind"] == "boundary"
        ):
            raise BindingError(
                f"{opening}: selected-request count disagrees with the plan"
            )
        for index, row in enumerate(rows):
            if row.get("request") != requests[index]:
                raise BindingError(
                    f"{opening}: observation row {index} is not the frozen plan request"
                )

    for query in predictions["queries"]:
        opening = query["opening"]
        entry = entries.get(opening)
        if entry is None:
            raise BindingError(f"{opening}: unknown opening")
        observation = observations[opening]
        if query["package"] != entry["package"]:
            raise BindingError(
                f"{query['query_id']}: package binding differs from the opening"
            )
        if (query["split"], query["group"]) != (entry["split"], entry["group"]):
            raise BindingError(
                f"{query['query_id']}: split/group binding differs from the opening"
            )
        plan_index = query["plan_index"]
        if not 0 <= plan_index < len(observation["plan_requests"]):
            raise BindingError(f"{query['query_id']}: plan index out of range")
        if observation["plan_requests"][plan_index] != query["request"]:
            raise BindingError(
                f"{query['query_id']}: frozen prediction request is not the plan request"
            )
        if plan_index < len(observation["rows"]):
            if observation["rows"][plan_index].get("request") != query["request"]:
                raise BindingError(
                    f"{query['query_id']}: observed row request is not the predicted request"
                )
        elif observation["completed"]:
            raise BindingError(
                f"{query['query_id']}: completed observation lacks this row"
            )
    return {
        "opening_bindings": len(observations),
        "query_bindings": len(predictions["queries"]),
        "rows_checked": sum(
            len(observation["rows"]) for observation in observations.values()
        ),
    }


def evaluate(predictions, observations, openings, packages=None):
    binding = bind(predictions, observations, openings, packages)
    by_rule = {rule: empty_confusion() for rule in predictions["rules"]}
    by_group = {}
    # Every opening is listed, including the zero-query packages, so an
    # unscored package reads as "not estimable" and never as an exact cell.
    per_package = {
        entry["opening"]: {
            "split": entry["split"],
            "group": entry["group"],
            "labels": Counter(),
            "by_rule": {rule: empty_confusion() for rule in predictions["rules"]},
        }
        for entry in openings["openings"]
    }
    labels = Counter()
    counterexamples = []
    exact_same_edge = 0
    exact_distinct_edge = 0
    for query in predictions["queries"]:
        opening = query["opening"]
        observation = observations[opening]
        row = (
            observation["rows"][query["plan_index"]]
            if query["plan_index"] < len(observation["rows"])
            else None
        )
        observed, detail = classify(row)
        labels[observed] += 1
        if observed == EXACT:
            edges = query["request"]["endpoint_edges"]
            if edges[0] == edges[1]:
                exact_same_edge += 1
            else:
                exact_distinct_edge += 1
        group = query["group"]
        per_package[opening]["labels"][observed] += 1
        for rule in predictions["rules"]:
            predicted = query["predictions"][rule]["prediction"]
            add(by_rule[rule], predicted, observed)
            add(per_package[opening]["by_rule"][rule], predicted, observed)
            by_group.setdefault(
                (query["split"], group),
                {r: empty_confusion() for r in predictions["rules"]},
            )
            add(by_group[(query["split"], group)][rule], predicted, observed)
            if (
                rule in FOCUS_RULES
                and observed in (EXACT, FAILURE)
                and predicted != "abstain"
            ):
                if (predicted == "success") != (observed == EXACT):
                    counterexamples.append(
                        {
                            "rule": rule,
                            "kind": "false_positive"
                            if predicted == "success"
                            else "false_negative",
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
        "binding": binding,
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
    predictions = load_json(OUTPUT / "predictions.json")
    observations = collect(openings)
    report = evaluate(predictions, observations, openings)
    document = {
        "schema": 2,
        "freeze": predictions["freeze"],
        "model_version": predictions["model_version"],
        "predictions_sha256": digest((OUTPUT / "predictions.json").read_bytes()),
        "protocol_sha256": predictions["protocol_sha256"],
        "primary_rule": predictions["primary_rule"],
        "fitted_rule": predictions["fitted_rule"],
        "bindings": report["binding"],
        "openings": {
            opening: {
                key: value
                for key, value in observation.items()
                if key not in ("rows", "plan_requests")
            }
            for opening, observation in observations.items()
        },
        "result": report,
    }
    if args.check:
        frozen = json.loads((OUTPUT / "evaluation.json").read_text())
        if frozen["result"] != report or frozen["bindings"] != report["binding"]:
            raise SystemExit("evaluation is not reproducible")
        print(
            json.dumps(
                {
                    "checked": True,
                    "bindings": report["binding"],
                    "evaluation_sha256": file_digest(OUTPUT / "evaluation.json"),
                }
            )
        )
        return
    (OUTPUT / "evaluation.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n"
    )
    primary = report["rules"][predictions["primary_rule"]]
    fitted = report["rules"][predictions["fitted_rule"]]
    print(
        json.dumps(
            {
                "labels": report["labels"],
                "primary": primary,
                "fitted": fitted,
                "bindings": report["binding"],
                "evaluation_sha256": file_digest(OUTPUT / "evaluation.json"),
            },
            default=str,
        )
    )


if __name__ == "__main__":
    main()
