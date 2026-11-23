"""Freeze the input-only predictions for the outside-query model.

Reads only `requests.json` (label-free) and the retained pre-query network
snapshots it names. It never opens `inventory.json`, `outside-v1/evidence.json`
or any observation, so a prediction written here cannot have seen the label it
is later scored against.

Writes `protocol.json` and `predictions.json`; the protocol records the SHA-256
of the predictions, which `evaluate.py` requires before it will read a label.

Run:  python3 predict.py
"""

from __future__ import annotations

import datetime
import gzip
import hashlib
import json
from pathlib import Path

import model
import topology

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "outside-v1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_snapshot(entry):
    path = SOURCE / entry["networks"]["path"]
    raw = gzip.decompress(path.read_bytes())
    actual = sha(raw)
    if actual != entry["networks"]["sha256"]:
        raise ValueError(f"network snapshot changed: {entry['networks']['path']}")
    return json.loads(raw), actual


def main():
    requests_doc = json.loads((HERE / "requests.json").read_text())
    requests_sha = sha((HERE / "requests.json").read_bytes())

    openings = {entry["key"]: entry for entry in requests_doc["openings"]}
    prepared = {}
    snapshot_provenance = []
    for key in sorted(openings):
        entry = openings[key]
        if not entry["networks"]["path"]:
            continue
        networks, digest = load_snapshot(entry)
        package = topology.from_native(networks, key)
        snapshot_provenance.append(
            {
                "opening": key,
                "slug": entry["slug"],
                "attempt_id": entry["attempt_id"],
                "package_sha256": entry["artifact_sha256"],
                "networks": entry["networks"],
                "verified_sha256": digest,
                "segments": len(package["segments"]),
                "node_flag_conflicts": len(package["node_flag_conflicts"]),
            }
        )
        for mode in topology.VEHICLE:
            if topology.mode_index(package, mode)[0]:
                prepared[(key, mode)] = model.Prepared(package, mode)

    prediction_records = []
    absent = []
    for entry in requests_doc["requests"]:
        key = f"{entry['slug']}/{entry['attempt_id']}"
        prepared_package = prepared.get((key, entry["mode"]))
        if prepared_package is None:
            absent.append(
                {
                    "query_id": entry["query_id"],
                    "reason": "no_mode_lane_in_opening",
                }
            )
            continue
        rules = {
            rule: model.predict(prepared_package, entry["request"], rule)
            for rule in model.RULES
        }
        prediction_records.append(
            {
                "query_id": entry["query_id"],
                "slug": entry["slug"],
                "attempt_id": entry["attempt_id"],
                "mode": entry["mode"],
                "stratum": entry["stratum"],
                "request": entry["request"],
                "rules": rules,
            }
        )

    predictions = {
        "schema": 1,
        "study": "outside-query-model-v1",
        "model_version": model.MODEL_VERSION,
        "requests_sha256": requests_sha,
        "rules": model.RULES,
        "primary_rule": model.PRIMARY_RULE,
        "absent": absent,
        "predictions": prediction_records,
    }
    (HERE / "predictions.json").write_text(
        json.dumps(predictions, indent=1, sort_keys=True) + "\n"
    )
    predictions_sha = sha((HERE / "predictions.json").read_bytes())

    protocol = {
        "schema": 1,
        "study": "outside-query-model-v1",
        "model_version": model.MODEL_VERSION,
        "scope": (
            "retrospective, query-scoped reachability over the retained road, ship "
            "and air native path requests of the accepted outside-v1 study. Not "
            "prospective and not blind: these observations already existed."
        ),
        "protocol_copied_from_source": (
            "PathManager.CreatePath; vehicle per mode (Car/Ship/Plane), category "
            "All, laneTypes Vehicle|TransportVehicle|CargoVehicle, seed 857, "
            "maxLength 100000, literal [segment,lane,offset] endpoints."
        ),
        "features_allowed": (
            "pre-query network topology: segment id, start/end node ids, prefab, "
            "endpoint positions, and per-lane index, lane type, vehicle, category "
            "and recorded direction."
        ),
        "features_forbidden": (
            "place names, artifact ids, special segment ids, query outcomes, "
            "returned paths, panel counts, observation bytes, old scores, the "
            "request's own endpoint_roles/endpoint_edges/lane_directions metadata."
        ),
        "domain": {
            "mode_vehicle": topology.VEHICLE,
            "accepted_lane_types": sorted(topology.ACCEPTED_LANE_TYPES),
            "direction_bits": {
                name: {"forward": bits[0], "backward": bits[1]}
                for name, bits in topology.DIRECTION_BITS.items()
            },
            "junction": (
                "all: every incident mode segment pair connects at a node. The "
                "retained queries are two-endpoint reachability questions and do "
                "not separate junction-pairing hypotheses, so those are not "
                "searched."
            ),
            "segment_flags": (
                "`Invert` is applied: travel away from a node counts as forward "
                "only when (node == segment start) XOR Invert."
            ),
            "max_length": model.MAX_LENGTH,
            "length_measure": (
                "sum of segment chord lengths, a lower bound on the native curve "
                "length; a path whose lower bound exceeds maxLength is not a success."
            ),
        },
        "pairings": model.PAIRINGS,
        "uturns": model.UTURNS,
        "baselines": model.BASELINES,
        "lane_rules": model.LANE_RULES,
        "rules": model.RULES,
        "rules_per_mode": len(model.RULES),
        "primary_rule": model.PRIMARY_RULE,
        "primary_rule_basis": (
            "registered before scoring: the weakest lane-continuation hypothesis "
            "(any lane continues onto any lane) with no reversal, matching the "
            "protocol's acceptance of every lane type and category All."
        ),
        "positive_label": (
            "complete and released native path whose returned first and last "
            "positions equal the requested literal offsets"
        ),
        "negative_label": (
            "complete and released selected request whose native result reports "
            "success=false; an observed failure for that exact request, mode, "
            "flags and protocol, never a geographic negative"
        ),
        "unknown_label": "incomplete, unreleased or endpoint-mismatched result; unscored",
        "strata": {
            "primary_distinct_edge": "scored primary stratum, distinct map edges",
            "same_edge": "scored separately, both endpoints on one map edge",
            "midpoint_diagnostic": "not scored; correlated repeat of a boundary request",
            "unclassified_protocol": "earliest collector version, unknown",
            "unrequested": "no request recorded, unknown",
        },
        "selection_criterion": (
            "leave-one-package-out: on the remaining packages maximise F1, break "
            "ties by higher recall, then by the frozen rule order. Reported as "
            "retrospective selection, not as a fitted law."
        ),
        "sources": {
            "evidence": requests_doc["source_evidence_sha256"],
            "inventory": requests_doc["inventory_sha256"],
            "requests": requests_sha,
            "catalogs": sha((HERE / "catalogs.json").read_bytes())
            if (HERE / "catalogs.json").exists()
            else None,
            "packages": sha((HERE / "packages.json").read_bytes())
            if (HERE / "packages.json").exists()
            else None,
        },
        "snapshots": snapshot_provenance,
        "frozen_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "prediction_count": len(prediction_records),
        "predictions_sha256": predictions_sha,
        "predictions_bytes": (HERE / "predictions.json").stat().st_size,
        "absent": absent,
    }
    (HERE / "protocol.json").write_text(
        json.dumps(protocol, indent=1, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {
                "predictions": len(prediction_records),
                "absent": len(absent),
                "rules": len(model.RULES),
                "predictions_sha256": predictions_sha,
                "snapshots": len(snapshot_provenance),
            },
            indent=1,
        )
    )
    return protocol


if __name__ == "__main__":
    main()
