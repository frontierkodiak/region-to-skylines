"""Bind new observations to the pre-query freeze; no old outcome reruns."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import study
from collect import controls_valid
from cs1_harness import rail_study


def projection(package):
    return study.input_fields(package)


def audit(package, networks, metadata):
    native = study.topology.from_native(networks)
    tangents = {s["id"]: s for s in metadata["segments"]}
    for sid, s in native["segments"].items():
        for key in ["start_direction", "end_direction"]:
            s[key] = tangents.get(sid, {}).get(key)
    expected = {s["id"]: s for s in projection(package)}
    actual = {s["id"]: s for s in projection(native)}
    counts = collections.Counter()
    mismatches = []
    for sid in sorted(set(expected) | set(actual)):
        a, b = expected.get(sid), actual.get(sid)
        if a is None or b is None:
            mismatches.append(
                {
                    "segment": sid,
                    "field": "segment_presence",
                    "export": a is not None,
                    "native": b is not None,
                }
            )
            continue
        for key in a:
            counts[key + ":checked"] += 1
            if a[key] == b[key]:
                counts[key + ":agree"] += 1
            else:
                mismatches.append(
                    {"segment": sid, "field": key, "export": a[key], "native": b[key]}
                )
    return {
        "matched": not mismatches and not package["missing"],
        "fields": dict(counts),
        "mismatches": mismatches,
        "export_sha256": study.digest(projection(package)),
        "native_sha256": study.digest(projection(native)),
        "unsupported": package["missing"],
    }


def bind(case, requests, raw, frozen):
    out = raw / case["slug"]
    path = out / "observation.json"
    if not path.exists():
        return {"state": "not_attempted", "paths": [], "context_bound": False}
    obs = study.read(path)
    if (
        obs["artifact_sha256"] != case["sha256"]
        or obs["freeze_sha256"] != study.sha(study.HERE / "freeze.json")
        or obs["protocol"] != study.PROTOCOL
    ):
        raise ValueError("observation package/freeze/protocol mismatch")
    rows = obs.get("paths", [])
    if [r["request"] for r in rows] != requests[: len(rows)]:
        raise ValueError("observation is not the unique frozen request prefix")
    if obs.get("completed") and len(rows) != len(requests):
        raise ValueError("completed opening omitted requests")
    query_path = out / "query-freeze.json"
    if query_path.exists():
        q = study.read(query_path)
        if (
            q["requests"] != requests
            or obs["query_freeze_sha256"] != study.sha(query_path)
            or q["freeze_sha256"] != obs["freeze_sha256"]
            or q["runtime_identity"] != obs["runtime_identity"]
            or q["build_sha256"] != study.sha(study.HERE / "metadata-build.json")
        ):
            raise ValueError("opening request/runtime/build freeze mismatch")
        if q["networks_sha256"] != study.sha(out / "networks.json") or q[
            "metadata_sha256"
        ] != study.sha(out / "metadata.json"):
            raise ValueError("opening inventory changed")
        for row in rows:
            if (
                not row.get("submitted_at")
                or row["submitted_at"] < q["frozen_at"]
                or row["submitted_at"] < frozen["frozen_at"]
            ):
                raise ValueError("undated or pre-freeze request")
    elif rows:
        raise ValueError("queries without opening freeze")
    bound = rail_study.context_valid(obs)
    return {
        "state": "completed" if obs["completed"] else "capture_failure",
        "error": obs.get("error"),
        "paths": rows,
        "context_bound": bound,
        "cleanup": obs.get("session", {}).get("cleanup"),
        "raw_sha256": study.sha(path),
    }


def score(rows, rule):
    counts = {k: 0 for k in ["tp", "fp", "tn", "fn", "abstain", "unknown"]}
    for row in rows:
        pred = row["predictions"][rule]["prediction"]
        label = row["label"]
        if label == "unknown":
            counts["unknown"] += 1
        elif pred == study.jm.ABSTAIN:
            counts["abstain"] += 1
        elif pred == study.jm.SUCCESS:
            counts["tp" if label == "success" else "fp"] += 1
        elif pred == study.jm.NO_PATH:
            counts["fn" if label == "success" else "tn"] += 1
        else:
            raise ValueError("unknown prediction label")
    tp, fp, tn, fn = (counts[k] for k in ["tp", "fp", "tn", "fn"])
    return {
        **counts,
        "requests": len(rows),
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "coverage": (tp + fp + tn + fn) / len(rows) if rows else None,
    }


def path_audit(package, row):
    if row is None or study.label(row) != "success":
        return None
    positions = row["result"]["positions"]
    engine = study.jm.Engine(package)
    failures = []
    for a, b in zip(positions, positions[1:]):
        if a[0] == b[0]:
            continue
        sa, sb = package["segments"].get(a[0]), package["segments"].get(b[0])
        if sa is None or sb is None:
            failures.append(
                {
                    "from": a,
                    "to": b,
                    "unknown": "segment absent from frozen Train domain",
                }
            )
            continue
        common = {sa["start"], sa["end"]} & {sb["start"], sb["end"]}
        for measure in ["tangent", "chord"]:
            resolutions = engine.resolutions("continuation", measure)
            if not isinstance(resolutions, list):
                failures.append(
                    {
                        "from": a,
                        "to": b,
                        "rule": measure,
                        "unknown": "unresolved junction alternatives",
                    }
                )
            elif not any(
                (a[0], b[0]) in partners.get(node, set())
                for partners in resolutions
                for node in common
            ):
                failures.append(
                    {
                        "from": a,
                        "to": b,
                        "shared_nodes": sorted(common),
                        "rule": measure,
                        "rejected_transition": True,
                    }
                )
    return {"transitions": len(positions) - 1, "findings": failures}


def evaluate(raw):
    frozen = study.read(study.HERE / "freeze.json")
    study.validate_artifacts(frozen)
    catalogs, _, _ = study.old_catalogs()
    gate = controls_valid(frozen, raw)
    controls = {
        c["slug"]: bind(c, c["requests"], raw, frozen) for c in frozen["controls"]
    }
    results, scored = {}, []
    for case in frozen["selected"]:
        bound = bind(case, case["selected_requests"], raw, frozen)
        out = raw / case["slug"]
        audits = {}
        package = None
        if (out / "metadata.json").exists() and "lineage" in case:
            _, package = study.build_package(case["locator"], catalogs)
            for suffix in ["", "-post"]:
                if (out / f"metadata{suffix}.json").exists():
                    audits["opening" if not suffix else "post"] = audit(
                        package,
                        study.read(out / f"networks{suffix}.json"),
                        study.read(out / f"metadata{suffix}.json"),
                    )
        matches = bool(len(audits) == 2 and all(a["matched"] for a in audits.values()))
        opening_digest = (
            study.read(out / "metadata.json")["sha256"]
            if (out / "metadata.json").exists()
            else None
        )
        for prediction, row in zip(
            [p for p in frozen["predictions"] if p["slug"] == case["slug"]],
            itertools_rows(bound["paths"], len(case["selected_requests"])),
        ):
            label = study.label(row) if gate and bound["context_bound"] else "unknown"
            scored.append(
                {
                    **prediction,
                    "label": label,
                    "snapshot_matched": matches
                    and row is not None
                    and row.get("pre_graph", {}).get("sha256") == opening_digest
                    and row.get("post_graph", {}).get("sha256") == opening_digest,
                    "observation": row,
                    "path_audit": path_audit(package, row)
                    if package is not None
                    else None,
                }
            )
        results[case["slug"]] = {k: v for k, v in bound.items() if k != "paths"}
        results[case["slug"]].update(
            file=case["file"],
            stratum=case["stratum"],
            supported=case["supported"],
            selected_requests=len(case["selected_requests"]),
            audit=audits,
        )
    tables = {}
    for name, rows in [
        ("all-complete intent-to-test", scored),
        ("snapshot-matched", [r for r in scored if r["snapshot_matched"]]),
    ]:
        groups = {"all": rows}
        groups.update(
            {
                "stratum:" + s: [r for r in rows if r["stratum"] == s]
                for s in study.STRATA
            }
        )
        groups.update(
            {
                "package:" + c["slug"]: [r for r in rows if r["slug"] == c["slug"]]
                for c in frozen["selected"]
            }
        )
        tables[name] = {
            g: {rule: score(rs, rule) for rule in study.RULES}
            for g, rs in groups.items()
        }
    return {
        "freeze_sha256": study.sha(study.HERE / "freeze.json"),
        "controls_valid": gate,
        "controls": controls,
        "packages": results,
        "tables": tables,
        "rows": scored,
        "counterexamples": [
            r
            for r in scored
            if r["label"] != "unknown"
            and any(
                p["prediction"] in {study.jm.SUCCESS, study.jm.NO_PATH}
                and p["prediction"] != r["label"]
                for p in r["predictions"].values()
            )
        ],
    }


def itertools_rows(rows, count):
    return rows + [None] * (count - len(rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=study.HERE / "evaluation.json")
    args = parser.parse_args()
    result = evaluate(args.raw)
    args.output.write_bytes(study.encoded(result))
    print(
        json.dumps(
            {
                "controls_valid": result["controls_valid"],
                "packages": {s: r["state"] for s, r in result["packages"].items()},
                "scores": result["tables"]["all-complete intent-to-test"]["all"],
            }
        )
    )


if __name__ == "__main__":
    main()
