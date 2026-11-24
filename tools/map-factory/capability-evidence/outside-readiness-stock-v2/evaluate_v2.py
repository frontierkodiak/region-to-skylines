"""Descriptive evaluation of this study's new observations only.

No old scorer, outcome, predictor or judge function is imported or replayed.
Labels come from the accepted typed parser applied to the new raw replies, and
the frozen predictions are consumed exactly as frozen.  There is no global
accuracy, no pooled old vote and no geographic or service claim.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import stock_v2 as study
from protocol import Label, Request, decide, position


def request_of(plan):
    return Request(
        plan["mode"],
        position(plan["request"]["from"]),
        position(plan["request"]["to"]),
        plan["max_length"],
        0,
    )


def bridge_exact(graph, plan):
    mode = plan["mode"]
    rows = {row["id"]: row for row in graph[mode]}
    start = rows.get(plan["request"]["from"][0])
    end = rows.get(plan["request"]["to"][0])
    if start is None or end is None:
        return False
    lanes = {lane["index"] for lane in start["lanes"]}
    lanes &= {lane["index"] for lane in end["lanes"]}
    if plan["request"]["from"][1] not in lanes or plan["request"]["to"][1] not in lanes:
        return False
    if plan["request"]["from"][2] not in (0, 255) or plan["request"]["to"][2] not in (0, 255):
        return False
    return any(start["outside"]) and any(end["outside"])


def counts(rows):
    table = Counter(row["label"] for row in rows)
    predicted = Counter(row["prediction"] for row in rows if row["prediction"])
    tp = sum(1 for row in rows if row["prediction"] == "success" and row["label"] == "success")
    fp = sum(1 for row in rows if row["prediction"] == "success" and row["label"] == "no_path")
    tn = sum(1 for row in rows if row["prediction"] == "no_path" and row["label"] == "no_path")
    fn = sum(1 for row in rows if row["prediction"] == "no_path" and row["label"] == "success")
    estimable = bool(predicted.get("success") and predicted.get("no_path"))
    return {
        "n": len(rows),
        "predicted": dict(predicted),
        "observed": dict(table),
        "TP": tp,
        "FP": fp,
        "TN": tn,
        "FN": fn,
        "precision": (tp / (tp + fp)) if tp + fp else None,
        "recall": (tp / (tp + fn)) if tp + fn else None,
        "both_classes_predicted": estimable,
        "null_prediction": sum(1 for row in rows if not row["prediction"]),
        "unknown_label": table.get("unknown", 0),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    args = parser.parse_args()
    freeze = study.read(study.HERE / "freeze.json")
    selection = study.read(study.HERE / "selection.json")
    predictions = study.read(study.HERE / "predictions.json")
    cases = [(c["case_id"], "control") for c in freeze["controls"]] + [
        (row["case_id"], "holdout")
        for row in sorted({r["case_id"]: r for r in freeze["holdout"]}.values(), key=lambda r: r["case_id"])
    ]
    rows = []
    openings = []
    drift = []
    for case_id, kind in cases:
        opening = study.read(args.raw / case_id / "opening.json")
        graph = study.read(args.raw / case_id / "graph-opening.json")
        openings.append(
            {
                "case_id": case_id,
                "kind": kind,
                "completed": opening.get("completed"),
                "error": opening.get("error"),
                "session_id": opening["session_id"],
                "opening_graph_sha256": opening["opening_graph_sha256"],
                "post_graph_sha256": opening.get("post_graph_sha256"),
                "requests": len(opening["paths"]),
                "cleanup": opening["cleanup"],
                "auditor": opening["auditor"]["identity"],
                "monitor": opening["monitor"]["identity"],
            }
        )
        if opening["opening_graph_sha256"] != opening.get("post_graph_sha256"):
            drift.append({"case_id": case_id, "kind": "opening/post"})
        for row in opening["paths"]:
            plan = row["plan"]
            decision = decide(row.get("effective"), row.get("result"), Request(
                plan["mode"],
                position(plan["request"]["from"]),
                position(plan["request"]["to"]),
                plan["max_length"],
                row["pre_build_index"],
            ))
            prediction = predictions[plan["query_id"]]
            rows.append(
                {
                    "case_id": case_id,
                    "kind": kind,
                    "query_id": plan["query_id"],
                    "mode": plan["mode"],
                    "class": plan["kind"],
                    "prediction": prediction,
                    "label": decision.literal_label.value,
                    "reason": decision.reason,
                    "bridge_exact": bridge_exact(graph, plan),
                    "pre_build_index": row["pre_build_index"],
                    "effective_build_index": row["effective"].get("build_index"),
                    "contract": decision.transport_success is True,
                }
            )
            if row.get("pre_context", {}).get("frame", 0) > row.get("post_context", {}).get("frame", 0):
                drift.append({"case_id": case_id, "kind": "frame", "query_id": plan["query_id"]})
    groups = defaultdict(list)
    for row in rows:
        groups[f"{row['kind']}:{row['case_id']}"].append(row)
        groups[f"{row['kind']}:{row['case_id']}:{row['mode']}"].append(row)
        groups[f"{row['kind']}:{row['case_id']}:{row['mode']}:{row['class']}"].append(row)
    metrics = {name: counts(group) for name, group in sorted(groups.items())}
    evaluation = {
        "schema": 2,
        "issue": "PL-1313",
        "created_at": study.now(),
        "freeze_sha256": study.sha(study.HERE / "freeze.json"),
        "openings": openings,
        "rows": rows,
        "metrics": metrics,
        "bridge": {
            "exact": sum(1 for row in rows if row["bridge_exact"]),
            "observed": len(rows),
            "rule": "both endpoint segments present with the literal lane index, offsets 0/255, and both endpoints flagged Outside",
        },
        "drift": drift,
        "limitations": [
            "Prospective only relative to these frozen requests and this finite population.",
            "Old 030 fit remains retrospective; no pooled old votes and no global accuracy.",
            "One lane/category and one literal request per available cell; packages, lanes and openings are correlated.",
            "File identity is not memory attestation and not strict-no-mods; the displayed harness mod is enabled from user Mods.",
            "No geographic, service, spawning, sustained-navigation or stable-water claim.",
            "No certificate, app adoption, model refit or public deployment.",
        ],
    }
    study.write(study.HERE / "evaluation.json", evaluation)
    unsupported = [
        row for row in study.read(study.HERE / "inventory.json") if row["exclusion"] is None and not row["supported"]
    ]
    (study.HERE / "RESULTS.md").write_text(
        _results_markdown(freeze, selection, evaluation, unsupported)
    )
    print(study.encoded({"rows": len(rows), "openings": len(openings), "drift": drift}).decode())
    return 0


def _results_markdown(freeze, selection, evaluation, unsupported):
    lines = [
        "# Results: corrected outside-query controls on a frozen unseen stock cohort",
        "",
        "Prospective relative to the frozen requests below. One request per available",
        "package-mode/class cell, separate controls, and no global accuracy.",
        "",
        "## Selection",
        "",
        f"- rule: `{selection['rule']}`",
        f"- selected: {', '.join(row['file'] for row in selection['selected'])}",
        f"- covered cells: {', '.join(selection['covered_cells'])}",
        f"- missing cells: {', '.join(selection['missing_cells']) or 'none'}",
        f"- holdout requests frozen: {len(freeze['holdout'])}",
        f"- eligible unsupported packages retained: {len(unsupported)}",
        "",
        "## Openings",
        "",
        "| case | kind | completed | requests | error |",
        "| --- | --- | --- | --- | --- |",
    ]
    for opening in evaluation["openings"]:
        lines.append(
            f"| {opening['case_id']} | {opening['kind']} | {opening['completed']} | "
            f"{opening['requests']} | {opening['error'] or ''} |"
        )
    lines += [
        "",
        "## Per cell",
        "",
        "| group | n | observed | TP | FP | TN | FN | precision | recall |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, metric in evaluation["metrics"].items():
        if name.count(":") < 3:
            continue
        lines.append(
            f"| {name} | {metric['n']} | {metric['observed']} | {metric['TP']} | "
            f"{metric['FP']} | {metric['TN']} | {metric['FN']} | "
            f"{metric['precision']} | {metric['recall']} |"
        )
    lines += [
        "",
        "## Bridge and drift",
        "",
        f"- exact bridge subset: {evaluation['bridge']['exact']}/{evaluation['bridge']['observed']}",
        f"- drift rows: {len(evaluation['drift'])}",
        "",
        "## Limits",
        "",
        *[f"- {item}" for item in evaluation["limitations"]],
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
