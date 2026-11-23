"""Bind frozen predictions to retained labels and score them.

Run only after `predict.py`: this is the first program in the study that reads a
label. It refuses to run unless `protocol.json` records the SHA-256 of the
`predictions.json` on disk, and it re-checks every binding before scoring:

* every prediction's query id and request must equal one eligible inventory
  query, one-to-one and in the same count;
* every eligible inventory query must have a prediction;
* the frozen rule list and primary rule must match `model.py`.

Writes `evaluation.json` and `integrity.json`.

Run:  python3 evaluate.py
"""

from __future__ import annotations

import collections
import gzip
import hashlib
import heapq
import json
import math
from pathlib import Path

import model
import topology

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "outside-v1"
MODES = ("road", "ship", "air")
STRATA = ("primary_distinct_edge", "same_edge")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_json(name):
    return json.loads((HERE / name).read_text())


def confusion(pairs):
    """pairs: iterable of (prediction, label). Returns counts and metrics."""
    counts = {"TP": 0, "FP": 0, "TN": 0, "FN": 0, "abstain": 0}
    for prediction, label in pairs:
        if prediction == model.ABSTAIN:
            counts["abstain"] += 1
        elif prediction == model.SUCCESS and label is True:
            counts["TP"] += 1
        elif prediction == model.SUCCESS and label is False:
            counts["FP"] += 1
        elif prediction == model.NO_PATH and label is False:
            counts["TN"] += 1
        elif prediction == model.NO_PATH and label is True:
            counts["FN"] += 1
        else:  # pragma: no cover - guarded by the caller
            raise ValueError(f"unlabelable pair {prediction!r} {label!r}")
    tp, fp, tn, fn = counts["TP"], counts["FP"], counts["TN"], counts["FN"]
    positives = tp + fp
    actual_positive = tp + fn
    precision = tp / positives if positives else None
    recall = tp / actual_positive if actual_positive else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall)
        else None
    )
    return {
        **counts,
        "n": tp + fp + tn + fn + counts["abstain"],
        "scored": tp + fp + tn + fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "coverage": positives / (tp + fp + tn + fn) if (tp + fp + tn + fn) else None,
        "actual_negatives": tn + fp,
        "predicted_positives": positives,
        "classes": {
            "positives": actual_positive,
            "negatives": tn + fp,
            "estimable": bool(actual_positive and (tn + fp)),
        },
    }


def shortest_undirected(prepared, request):
    """Shortest chord distance over the mode graph ignoring direction."""
    source = prepared.segments.get(int(request["from"][0]))
    target = prepared.segments.get(int(request["to"][0]))
    if source is None or target is None:
        return None
    start = topology.endpoint_node(source, request["from"][2])
    finish = topology.endpoint_node(target, request["to"][2])
    if start not in prepared.incident:
        return None
    distances = {start: 0.0}
    queue = [(0.0, start)]
    adjacency = collections.defaultdict(list)
    for segment_id, segment in prepared.segments.items():
        weight = model.chord(segment)
        adjacency[segment["start"]].append((segment["end"], weight))
        adjacency[segment["end"]].append((segment["start"], weight))
    while queue:
        distance, node = heapq.heappop(queue)
        if node == finish:
            return distance
        if distance > distances.get(node, math.inf):
            continue
        for neighbour, weight in adjacency[node]:
            candidate = distance + weight
            if candidate < distances.get(neighbour, math.inf):
                distances[neighbour] = candidate
                heapq.heappush(queue, (candidate, neighbour))
    return None


def validate(protocol, predictions_doc, inventory, requests_doc, predictions_sha):
    """Every binding that must hold before a label may be read.

    Returns a list of named assertions. `main` refuses to score when any of them
    fails, so a changed prediction, request map or inventory cannot be scored
    against a stale protocol.
    """
    assertions = []

    def check(name, ok, detail=None):
        assertions.append({"name": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    check(
        "protocol_binds_this_predictions_file",
        protocol.get("predictions_sha256") == predictions_sha,
        {"protocol": protocol.get("predictions_sha256"), "file": predictions_sha},
    )
    check(
        "protocol_binds_this_requests_file",
        protocol.get("sources", {}).get("requests")
        == sha((HERE / "requests.json").read_bytes())
        if (HERE / "requests.json").exists()
        else False,
    )
    check("frozen_rules_match_model", protocol.get("rules") == model.RULES)
    check("frozen_primary_rule", protocol.get("primary_rule") == model.PRIMARY_RULE)
    check(
        "inventory_source_evidence_unchanged",
        requests_doc.get("source_evidence_sha256")
        == inventory.get("source", {}).get("evidence_sha256"),
    )
    prediction_rows = predictions_doc.get("predictions") or []
    request_rows = requests_doc.get("requests") or []
    query_rows = inventory.get("queries") or []
    check(
        "prediction_count_matches_requests",
        len(prediction_rows) == len(request_rows),
        {"predictions": len(prediction_rows), "requests": len(request_rows)},
    )

    by_query = {query["query_id"]: query for query in query_rows}
    eligible = {
        query["query_id"]: query for query in query_rows if query["eligible"]
    }
    predicted = {}
    duplicates = []
    for record in prediction_rows:
        if record["query_id"] in predicted:
            duplicates.append(record["query_id"])
        predicted[record["query_id"]] = record
    check("no_duplicate_predictions", not duplicates, duplicates[:10])
    check(
        "every_prediction_has_an_inventory_query",
        all(query_id in by_query for query_id in predicted),
        sorted(set(predicted) - set(by_query))[:10],
    )
    check(
        "every_eligible_query_has_a_prediction",
        set(eligible) <= set(predicted),
        sorted(set(eligible) - set(predicted))[:10],
    )
    check(
        "prediction_query_ids_are_unique_against_inventory",
        len(by_query) == len(query_rows),
        len(query_rows) - len(by_query),
    )
    request_mismatches = [
        query_id
        for query_id, record in predicted.items()
        if query_id in by_query and record["request"] != by_query[query_id]["request"]
    ]
    check(
        "predictions_repeat_the_exact_request",
        not request_mismatches,
        request_mismatches[:10],
    )
    check(
        "every_eligible_query_has_a_strict_boolean_label",
        all(
            type(eligible[query_id]["observed"]) is bool
            for query_id in eligible
        ),
    )
    check(
        "eligible_queries_are_all_frozen_strata",
        all(query["stratum"] in STRATA for query in eligible.values()),
    )
    return assertions


def refuse_if_failed(assertions, stage):
    """Fail closed: a failed binding or check stops the run before it writes."""
    failed = [item for item in assertions if not item["ok"]]
    if failed:
        print(json.dumps({"refused": True, "stage": stage, "failed": failed}, indent=1))
        raise SystemExit(2)
    return assertions


def main():
    protocol = load_json("protocol.json")
    predictions_doc = load_json("predictions.json")
    inventory = load_json("inventory.json")
    requests_doc = load_json("requests.json")

    predictions_sha = sha((HERE / "predictions.json").read_bytes())
    assertions = validate(
        protocol, predictions_doc, inventory, requests_doc, predictions_sha
    )
    refuse_if_failed(assertions, "binding")

    by_query = {query["query_id"]: query for query in inventory["queries"]}
    eligible = {
        query["query_id"]: query
        for query in inventory["queries"]
        if query["eligible"]
    }
    predicted = {record["query_id"]: record for record in predictions_doc["predictions"]}

    def check(name, ok, detail=None):
        assertions.append({"name": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    # Per-mode prepared topology, only for the independent length check.
    prepared = {}
    for entry in requests_doc["openings"]:
        if not entry["networks"]["path"]:
            continue
        raw = gzip.decompress((SOURCE / entry["networks"]["path"]).read_bytes())
        package = topology.from_native(json.loads(raw), entry["key"])
        for mode in MODES:
            if topology.mode_index(package, mode)[0]:
                prepared[(entry["slug"], entry["attempt_id"], mode)] = model.Prepared(package, mode)

    scored = [
        {
            "query_id": query_id,
            "query": eligible[query_id],
            "prediction": predicted[query_id],
        }
        for query_id in eligible
    ]

    def pairs(records, rule):
        return [
            (record["prediction"]["rules"][rule]["prediction"], record["query"]["observed"])
            for record in records
        ]

    def subset(records, **filters):
        result = []
        for record in records:
            query = record["query"]
            if any(query[field] != value for field, value in filters.items()):
                continue
            result.append(record)
        return result

    by_rule = {}
    for rule in model.RULES:
        by_rule[rule] = {"all_strata": confusion(pairs(scored, rule))}
        for stratum in STRATA:
            by_rule[rule][stratum] = confusion(
                pairs(subset(scored, stratum=stratum), rule)
            )
        by_rule[rule]["by_mode"] = {
            mode: confusion(pairs(subset(scored, mode=mode), rule)) for mode in MODES
        }
        by_rule[rule]["by_mode_primary"] = {
            mode: confusion(
                pairs(subset(scored, mode=mode, stratum="primary_distinct_edge"), rule)
            )
            for mode in MODES
        }

    def rank(rule, records, stratum="primary_distinct_edge"):
        metrics = confusion(pairs(subset(records, stratum=stratum), rule))
        return (
            metrics["f1"] if metrics["f1"] is not None else float("-inf"),
            metrics["recall"] if metrics["recall"] is not None else float("-inf"),
            -model.RULES.index(rule),
        )

    primary_records = subset(scored, stratum="primary_distinct_edge")
    global_best = max(model.RULES, key=lambda rule: rank(rule, primary_records))
    check(
        "global_best_is_in_frozen_family",
        global_best in model.RULES,
        global_best,
    )

    packages = sorted({record["query"]["slug"] for record in primary_records})
    folds = []
    for held_out in packages:
        training = [record for record in primary_records if record["query"]["slug"] != held_out]
        held = [record for record in primary_records if record["query"]["slug"] == held_out]
        training_classes = confusion(pairs(training, model.RULES[0]))
        estimable = training_classes["classes"]["estimable"] and bool(held)
        fold = {
            "held_out": held_out,
            "held_out_n": len(held),
            "held_out_labels": dict(
                collections.Counter(str(record["query"]["observed"]) for record in held)
            ),
            "training_n": len(training),
            "training_classes": training_classes["classes"],
            "estimable": estimable,
        }
        if estimable:
            selected = max(model.RULES, key=lambda rule: rank(rule, training))
            metrics = confusion(pairs(held, selected))
            fold.update(
                {
                    "selected_rule": selected,
                    "held_out_metrics": metrics,
                    "identical_to_global_best": selected == global_best,
                }
            )
        else:
            fold.update({"selected_rule": None, "reason": "not estimable: one class in training"})
        folds.append(fold)

    # Disagreements for the two rules that matter: the registered primary rule
    # and the family's best member on this data.
    def disagreements(rule):
        output = []
        for record in scored:
            query = record["query"]
            detail = record["prediction"]["rules"][rule]
            if detail["prediction"] == model.ABSTAIN:
                output.append(
                    {
                        "query_id": record["query_id"],
                        "relation": "abstained",
                        "reason": detail["detail"],
                    }
                )
            elif detail["prediction"] == model.SUCCESS and query["observed"] is False:
                output.append(
                    {
                        "query_id": record["query_id"],
                        "relation": "false_positive",
                        "package": query["slug"],
                        "mode": query["mode"],
                        "stratum": query["stratum"],
                        "request": query["request"],
                        "endpoint_roles": query["endpoint_roles"],
                        "endpoint_edges": query["endpoint_edges"],
                        "returned_endpoints_match": query["returned_endpoints_match"],
                        "native": query["result"],
                        "model": detail["detail"],
                    }
                )
            elif detail["prediction"] == model.NO_PATH and query["observed"] is True:
                output.append(
                    {
                        "query_id": record["query_id"],
                        "relation": "false_negative",
                        "package": query["slug"],
                        "mode": query["mode"],
                        "stratum": query["stratum"],
                        "request": query["request"],
                        "endpoint_roles": query["endpoint_roles"],
                        "native": query["result"],
                        "model": detail["detail"],
                    }
                )
        return output

    disagreement_report = {
        rule: disagreements(rule) for rule in dict.fromkeys([model.PRIMARY_RULE, global_best])
    }

    # Every disagreement of the best rule must be either a native maxLength
    # denial or an endpoint mismatch; anything else is an unexplained error.
    unexplained = []
    for rule, items in disagreement_report.items():
        for item in items:
            if item["relation"] == "abstained":
                unexplained.append(item)
                continue
            native = item["native"]
            length_denial = native["flags"] == 8 and native["length"] == model.MAX_LENGTH
            endpoint_mismatch = item["returned_endpoints_match"] is False
            if item["relation"] == "false_positive" and not (
                length_denial or endpoint_mismatch
            ):
                unexplained.append(item)
            elif item["relation"] == "false_negative":
                unexplained.append(item)
    check("no_unexplained_disagreement", not unexplained, unexplained[:10])

    # Correlated repeats asked in two openings of the same unchanged package.
    repeat_pairs = []
    for query in inventory["queries"]:
        repeat_of = query.get("repeat_of")
        if not repeat_of or not query["eligible"]:
            continue
        other = by_query.get(repeat_of)
        if other is None or not other["eligible"]:
            continue
        repeat_pairs.append(
            {
                "query_id": query["query_id"],
                "repeat_of": repeat_of,
                "agree": query["observed"] == other["observed"],
            }
        )
    check(
        "rewritten_packages_repeat_consistently",
        all(pair["agree"] for pair in repeat_pairs),
        {"pairs": len(repeat_pairs), "agree": sum(1 for p in repeat_pairs if p["agree"])},
    )

    midpoint = inventory["counts"]["midpoint_pairs"]
    check(
        "midpoint_repeats_agree",
        inventory["counts"]["midpoint_agree"] == midpoint,
        {"pairs": midpoint, "agree": inventory["counts"]["midpoint_agree"]},
    )

    # Length check: an undirected chord lower bound is at most any directed
    # chord path, so if even it stays far below the cap the maxLength test
    # cannot bind for an eligible query.
    chord_ratios = []
    for record in scored:
        query = record["query"]
        prepared_package = prepared.get((query["slug"], query["attempt_id"], query["mode"]))
        if prepared_package is None:
            continue
        distance = shortest_undirected(prepared_package, query["request"])
        if distance is not None:
            chord_ratios.append(distance / model.MAX_LENGTH)
    length_report = {
        "max_length": model.MAX_LENGTH,
        "eligible_queries_with_chord_path": len(chord_ratios),
        "max_undirected_chord_over_cap": max(chord_ratios) if chord_ratios else None,
        "binds": bool(chord_ratios and max(chord_ratios) >= 1.0),
        "note": (
            "The chord test cannot change any prediction: the largest eligible "
            "undirected chord lower bound is well under the protocol maximum, so "
            "even a 20% chord error cannot reach it."
        ),
    }
    check(
        "max_length_lower_bound_never_binds",
        not length_report["binds"],
        length_report["max_undirected_chord_over_cap"],
    )
    if length_report["max_undirected_chord_over_cap"] is not None:
        check(
            "chord_bridge_error_cannot_flip_the_length_test",
            length_report["max_undirected_chord_over_cap"] * 1.2 < 1.0,
        )

    one_class = {}
    for mode in MODES:
        metrics = by_rule[model.PRIMARY_RULE]["by_mode_primary"][mode]
        one_class[mode] = {
            "positives": metrics["classes"]["positives"],
            "negatives": metrics["classes"]["negatives"],
            "discrimination_estimable": metrics["classes"]["negatives"] > 0,
            "recall": metrics["recall"],
            "precision": metrics["precision"],
            "note": (
                "one class only: the retained evidence for this mode contains "
                "successful requests and no observed failures. The arithmetic "
                "precision is therefore trivially 1 and no discrimination among "
                "the frozen rules is estimable."
                if metrics["classes"]["negatives"] == 0
                else "both classes present"
            ),
        }
    identical_rules = {}
    for mode in MODES:
        signatures = {
            rule: json.dumps(
                [
                    record["prediction"]["rules"][rule]["prediction"]
                    for record in subset(scored, mode=mode)
                ],
                sort_keys=True,
            )
            for rule in model.RULES
        }
        groups = collections.defaultdict(list)
        for rule, signature in signatures.items():
            groups[signature].append(rule)
        identical_rules[mode] = [rules for rules in groups.values() if len(rules) > 1]

    evaluation = {
        "schema": 1,
        "study": "outside-query-model-v1",
        "protocol_sha256": sha((HERE / "protocol.json").read_bytes()),
        "predictions_sha256": predictions_sha,
        "inventory_sha256": sha((HERE / "inventory.json").read_bytes()),
        "counts": {
            "eligible": len(eligible),
            "primary": len(primary_records),
            "same_edge": len(subset(scored, stratum="same_edge")),
            "by_mode": dict(collections.Counter(record["query"]["mode"] for record in scored)),
            "by_package": dict(
                collections.Counter(record["query"]["slug"] for record in scored)
            ),
        },
        "by_rule": by_rule,
        "primary_rule": model.PRIMARY_RULE,
        "best_rule_on_primary": global_best,
        "best_rule_metrics": by_rule[global_best]["primary_distinct_edge"],
        "primary_rule_metrics": by_rule[model.PRIMARY_RULE]["primary_distinct_edge"],
        "groups": {
            "by_package": {
                slug: {
                    rule: confusion(
                        pairs(
                            subset(
                                primary_records,
                                slug=slug,
                            ),
                            rule,
                        )
                    )
                    for rule in (model.PRIMARY_RULE, global_best)
                }
                for slug in packages
            },
            "by_study": {
                study: {
                    rule: confusion(
                        pairs(subset(scored, study=study), rule)
                    )
                    for rule in (model.PRIMARY_RULE, global_best)
                }
                for study in sorted({record["query"]["study"] for record in scored})
            },
            "by_fidelity": {
                str(bound): {
                    rule: confusion(
                        pairs(subset(scored, runtime_bound=bound), rule)
                    )
                    for rule in (model.PRIMARY_RULE, global_best)
                }
                for bound in sorted(
                    {record["query"]["runtime_bound"] for record in scored},
                    key=str,
                )
            },
        },
        "leave_one_package_out": folds,
        "disagreements": disagreement_report,
        "unexplained_disagreements": unexplained,
        "one_class": one_class,
        "identical_rules": identical_rules,
        "repeats": {
            "cross_opening": repeat_pairs,
            "cross_opening_pairs": len(repeat_pairs),
            "cross_opening_agree": sum(1 for pair in repeat_pairs if pair["agree"]),
            "midpoint": {
                "pairs": midpoint,
                "agree": inventory["counts"]["midpoint_agree"],
            },
        },
        "length_check": length_report,
        "limitations": [
            "The study is retrospective: the observations existed before the model.",
            "Road, ship and air observations are not independent votes across "
            "direction pairs, midpoint repeats or repeated openings of the same package.",
            "Ship and air can only be checked for positive consistency; their "
            "evidence contains no observed failures.",
            "A failure is an observed failure of that exact request under that "
            "exact protocol, never evidence that a place cannot support the mode.",
        ],
    }
    refuse_if_failed(assertions, "checks")

    (HERE / "evaluation.json").write_text(
        json.dumps(evaluation, indent=1, sort_keys=True) + "\n"
    )

    integrity = {
        "schema": 1,
        "study": "outside-query-model-v1",
        "assertions": assertions,
        "all_ok": all(item["ok"] for item in assertions),
        "hashes": {
            "evidence.json": inventory["source"]["evidence_sha256"],
            "inventory.json": sha((HERE / "inventory.json").read_bytes()),
            "requests.json": sha((HERE / "requests.json").read_bytes()),
            "manifest.json": sha((HERE / "manifest.json").read_bytes()),
            "protocol.json": sha((HERE / "protocol.json").read_bytes()),
            "predictions.json": predictions_sha,
            "evaluation.json": sha((HERE / "evaluation.json").read_bytes()),
            "catalogs.json": sha((HERE / "catalogs.json").read_bytes())
            if (HERE / "catalogs.json").exists()
            else None,
            "bridge.json": sha((HERE / "bridge.json").read_bytes())
            if (HERE / "bridge.json").exists()
            else None,
            "packages.json": sha((HERE / "packages.json").read_bytes())
            if (HERE / "packages.json").exists()
            else None,
        },
        "counts": inventory["counts"],
        "anomalies": inventory["anomalies"],
    }
    (HERE / "integrity.json").write_text(
        json.dumps(integrity, indent=1, sort_keys=True) + "\n"
    )

    summary = {
        "all_ok": integrity["all_ok"],
        "primary_rule": model.PRIMARY_RULE,
        "primary": {
            key: by_rule[model.PRIMARY_RULE]["primary_distinct_edge"][key]
            for key in ("TP", "FP", "TN", "FN", "abstain", "precision", "recall", "f1")
        },
        "best_rule": global_best,
        "best": {
            key: by_rule[global_best]["primary_distinct_edge"][key]
            for key in ("TP", "FP", "TN", "FN", "precision", "recall", "f1")
        },
        "same_edge": {
            key: by_rule[global_best]["same_edge"][key]
            for key in ("TP", "FP", "TN", "FN", "precision", "recall")
        },
        "one_class": {mode: one_class[mode]["note"] for mode in MODES},
        "folds_estimable": sum(1 for fold in folds if fold["estimable"]),
        "unexplained": len(unexplained),
        "assertions_failed": [item["name"] for item in assertions if not item["ok"]],
    }
    print(json.dumps(summary, indent=1))
    return evaluation


if __name__ == "__main__":
    main()
