"""Freeze the study protocol and generate the input-only query predictions.

Reads, and only reads: `openings.json`, `packages.json`, each opening's frozen
`networks.json.gz` and `query-freeze.json.gz`, and the model sources. It never
opens `observation.json.gz`, any verification file or any old score, so the
predictions it writes cannot have seen the outcome they will be scored against.

Run:  .venv/bin/python capability-evidence/rail-query-model-v1/predict.py
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CAPABILITY = HERE.parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    return digest(Path(path).read_bytes())


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load_json(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf8") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def selected_requests(plan):
    """The frozen primary set, with each request's index in the frozen plan."""
    return [
        (index, request)
        for index, request in enumerate(plan["plan"]["requests"])
        if not request["diagnostic"] and request["position_kind"] == "boundary"
    ]


def sources():
    files = [
        HERE / "topology.py",
        HERE / "model.py",
        HERE / "predict.py",
        HERE / "openings.json",
        HERE / "packages.json",
    ]
    return {str(path.relative_to(ROOT)): file_digest(path) for path in files}


def freeze_protocol(openings, packages):
    import model

    return {
        "schema": 1,
        "frozen_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "study": "rail-query-model-v1",
        "scope": "retrospective query-scoped rail reachability over the frozen PL-1215 native study",
        "primary_set": "selected literal-boundary requests: non-diagnostic, position_kind=boundary, from the frozen query-freeze plan of each accepted opening",
        "excluded_from_primary": "midpoint, reversed-position and invalid-vehicle diagnostics; rail-v1 and rail-v2 selector revisions; the rio fair-queue denial; any outcome or path",
        "protocol_copied_from_source": "PathManager.CreatePath, vehicle Train, category All, laneTypes Vehicle|TransportVehicle|CargoVehicle, seed 857, maxLength 100000, literal [segment,lane,offset] endpoints",
        "positive_label": "complete and released native path whose returned first and last positions equal the requested literal offsets",
        "negative_label": "complete and released selected request whose native result reports success=false; this is an observed failure for that exact request, mode, flags and protocol, never a geographic negative",
        "unknown_label": "incomplete, unreleased or endpoint-mismatched result; unscored",
        "features_allowed": "pre-query topology, geometry, lane direction bits, category, flags and request parameters only",
        "features_forbidden": "place names, artifact ids, special segment ids, successful paths, observation bytes, old scores",
        "splits": {
            "stock_controls": {
                "packages": [
                    o["package"]
                    for o in openings["openings"]
                    if o["split"] == "stock_controls"
                ],
                "role": "separate control group; never pooled with the cohort as independent votes",
            },
            "cohort": {
                "packages": [
                    o["package"] for o in openings["openings"] if o["split"] == "cohort"
                ],
                "role": "evaluation group; every selected query of a package stays in that package's group",
            },
        },
        "rules": model.RULES,
        "primary_rule": model.PRIMARY_RULE,
        "fitted_rule": model.FITTED_RULE,
        "pairings": model.PAIRINGS,
        "uturns": model.UTURNS,
        "junctions": model.JUNCTIONS,
        "families": {
            "topology_only": {
                "rules": model.BASELINES + model.LANE_RULES,
                "frozen": "before any prediction was scored",
            },
            "junction": {
                "rules": model.JUNCTION_RULES,
                "frozen": "after the topology-only family failed to separate observed successes from observed failures; every member is reported and none is adopted",
            },
        },
        "max_length": model.MAX_LENGTH,
        "estimable": "precision and recall are null when their denominator is zero; no always-fail accuracy headline",
        "packages": {
            key: value["sha256"] for key, value in packages["packages"].items()
        },
    }


def build(openings, packages, write):
    import model
    import topology

    protocol = freeze_protocol(openings, packages)
    queries = []
    per_opening = {}
    for entry in openings["openings"]:
        raw = CAPABILITY / entry["raw"]
        networks_path = raw / "networks.json.gz"
        plan_path = raw / "query-freeze.json.gz"
        if not networks_path.exists() or not plan_path.exists():
            raise SystemExit(f"{entry['opening']}: missing frozen topology or plan")
        package = topology.load_native(networks_path, entry["opening"])
        plan = load_json(plan_path)
        requests = selected_requests(plan)
        per_opening[entry["opening"]] = {
            "selected_requests": len(requests),
            "candidate_boundary_requests": plan["plan"]["candidate_boundary_count"],
            "unqueried_boundary_candidates": max(
                0,
                plan["plan"]["candidate_boundary_count"]
                - plan["plan"]["boundary_limit"],
            ),
            "train_segments": sum(
                1
                for segment in package["segments"].values()
                if topology.train_lanes(segment)
            ),
            "networks_sha256": file_digest(networks_path),
            "query_freeze_sha256": file_digest(plan_path),
        }
        for rank, (plan_index, request) in enumerate(requests):
            predictions = {
                rule: model.predict(package, request, rule) for rule in model.RULES
            }
            queries.append(
                {
                    "query_id": f"{entry['opening']}:{plan_index}",
                    "plan_index": plan_index,
                    "rank": rank,
                    "opening": entry["opening"],
                    "split": entry["split"],
                    "group": entry["group"],
                    "package": entry["package"],
                    "request": request,
                    "predictions": predictions,
                }
            )
    document = {
        "schema": 1,
        "frozen_at": protocol["frozen_at"],
        "protocol_sha256": digest(encoded(protocol)),
        "sources": sources(),
        "primary_rule": model.PRIMARY_RULE,
        "fitted_rule": model.FITTED_RULE,
        "rules": model.RULES,
        "openings": per_opening,
        "queries": queries,
    }
    if write:
        (HERE / "protocol.json").write_bytes(encoded(protocol))
        (HERE / "predictions.json").write_bytes(encoded(document))
    return protocol, document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the frozen files instead of writing",
    )
    args = parser.parse_args()
    openings = json.loads((HERE / "openings.json").read_text())
    packages = json.loads((HERE / "packages.json").read_text())
    for key, entry in packages["packages"].items():
        path = Path(entry["locator"])
        if not path.exists():
            raise SystemExit(f"package {key}: locator is unreadable: {path}")
        if file_digest(path) != entry["sha256"]:
            raise SystemExit(f"package {key}: bytes differ from the frozen SHA-256")
    protocol, document = build(openings, packages, not args.check)
    if args.check:
        frozen = json.loads((HERE / "predictions.json").read_text())
        if frozen["queries"] != document["queries"]:
            raise SystemExit(
                "predictions are not reproducible from the current sources"
            )
        print(
            json.dumps(
                {
                    "checked": True,
                    "queries": len(document["queries"]),
                    "rules": len(document["rules"]),
                    "predictions_sha256": file_digest(HERE / "predictions.json"),
                }
            )
        )
        return
    print(
        json.dumps(
            {
                "queries": len(document["queries"]),
                "rules": len(document["rules"]),
                "protocol_sha256": document["protocol_sha256"],
                "predictions_sha256": file_digest(HERE / "predictions.json"),
            }
        )
    )


if __name__ == "__main__":
    main()
