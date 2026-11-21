"""Freeze the study design, the input-only features and the input-only predictions.

This script is the only writer of `protocol.json`, `features.json` and
`predictions.json`. It reads, and only reads:

* `manifest.json` (the predeclared design: measures, thresholds, pairings,
  rules, splits, selection protocol, label definitions);
* the accepted `rail-query-model-v1` prefix, hash-pinned in the manifest:
  `openings.json`, `packages.json`, `corrected/protocol.json`,
  `corrected/integrity.json`, `model.py`, `topology.py`, `bridge.py`;
* each opening's frozen `networks.json.gz` (pre-query topology) and
  `query-freeze.json.gz` (the request plan);
* each opening's frozen `.crp` export, at the SHA-256 recorded in the accepted
  `packages.json`.

It never opens `observation.json.gz`. The `input_only` guard below refuses that
file by name, and the test suite scans the predict path for it. The evaluator is
a separate script that binds the predictions to the frozen observation bytes
after this freeze exists.

Order, enforced by `main`: protocol (the design) -> features (the inputs) ->
predictions (the model outputs). Every artifact records the SHA-256 of the one
before it.

Run:  .venv/bin/python capability-evidence/rail-junction-fit-v1/freeze.py
Check:  ... --check  (recompute and compare, ignoring `frozen_at`)
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPABILITY = HERE.parent
sys.path[:0] = [str(HERE.parents[1]), str(HERE)]

import binding  # noqa: E402
import export_topology as exports  # noqa: E402
import junction_model as jm  # noqa: E402
import topology  # noqa: E402

FREEZE = "rail-junction-fit-v1"
PROTOCOL = HERE / "protocol.json"
FEATURES = HERE / "features.json"
PREDICTIONS = HERE / "predictions.json"
OBSERVATION = "observation.json.gz"

FEATURE_SOURCES = (
    "manifest.json",
    "binding.py",
    "export_topology.py",
    "junction_model.py",
    "freeze.py",
)
# The accepted modules the predictions actually execute.
ACCEPTED_SOURCES = ("model.py", "topology.py", "bridge.py")


def input_only(path):
    """Refuse to open an observation: the freeze may not see a label."""
    if Path(path).name == OBSERVATION:
        raise RuntimeError(f"the freeze must not read a label file: {path}")
    return path


def load_input_json(path):
    return binding.load_json(input_only(path))


def sources(manifest):
    own = {name: binding.file_digest(HERE / name) for name in FEATURE_SOURCES}
    accepted = {
        name: binding.file_digest(binding.accepted_paths(manifest)[name])
        for name in ACCEPTED_SOURCES
    }
    return {
        "own": own,
        "accepted": accepted,
        "accepted_artifacts": manifest["source"]["accepted_files"],
    }


def freeze_protocol(manifest, accepted, per_opening, folds):
    return {
        "schema": 1,
        "study": FREEZE,
        "freeze": FREEZE,
        "frozen_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "source": manifest["source"],
        "scope": (
            "retrospective, already-observed fitting of junction-connection rules "
            "over the frozen PL-1215 native rail study; not a blind or prospective "
            "holdout, a geographic impossibility, rail service or a product promise"
        ),
        "hypotheses": {
            "measures": {
                "chord": "turn angle from the chord between node positions (the accepted v2 geometry)",
                "tangent": "turn angle from the export's authored endpoint directions",
            },
            "junction_kinds": {
                "continuation": (
                    "greedy disjoint straightest-first pairing of incident Train "
                    "segments; equal-turn candidates are alternatives"
                ),
                "turn": "every incident Train segment pair whose turn angle is at most the threshold",
            },
            "pairings": {
                "any_lane": "every Train lane continues onto every Train lane of the connected segment",
                "orientation_index": (
                    "Train lane ordinal i continues onto ordinal i at a mixed node and "
                    "n-i-1 at a same-sided node (the accepted v2 lateral-side rule)"
                ),
            },
            "uturn": jm.UTURN,
            "thresholds_degrees": manifest["thresholds_degrees"],
            "tie_tolerance_degrees": jm.TIE_TOLERANCE_DEGREES,
            "threshold_tolerance_degrees": jm.THRESHOLD_TOLERANCE_DEGREES,
            "max_alternatives": jm.MAX_ALTERNATIVES,
            "max_length": jm.MAX_LENGTH,
            "length": "sum of segment chords, a lower bound on the native curve length, never called native cost",
            "tangent_convention": (
                "the stored vector points from the named end into the segment, so "
                "start_direction is the outgoing heading at the start node and "
                "end_direction at the end node; proved against the export's own node positions"
            ),
            "tangent_provenance": (
                "export-derived and not native-attested: the accepted networks.json "
                "snapshot emits no endpoint tangents"
            ),
            "override_direction_limit": (
                "read and recorded for every segment; never used by a rule, because "
                "its game semantics are unproven and every observed value is 0"
            ),
        },
        "rules": jm.rule_names(),
        "baselines": list(jm.BASELINES),
        "frozen_rules": list(jm.FROZEN_RULES),
        "primary": manifest["primary"],
        "selection": manifest["selection"],
        "labels": manifest["labels"],
        "query_selection": {
            "source": "each opening's frozen query-freeze plan",
            "filter": "not diagnostic and position_kind == boundary",
            "request": "literal [segment, lane, offset] endpoints, plan order preserved",
        },
        "packages": {
            key: {
                "locator": entry["locator"],
                "sha256": entry["sha256"],
                "bytes": entry["bytes"],
            }
            for key, entry in sorted(accepted["packages"].items())
        },
        "openings": {
            name: {
                "package": row["package"],
                "split": row["split"],
                "group": row["group"],
                "raw": row["raw"],
                "selected_requests": row["selected"],
                "candidate_boundary_requests": row["candidates"],
                "boundary_limit": row["limit"],
                "networks_sha256": row["networks_sha256"],
                "plan_sha256": row["plan_sha256"],
                "observation_sha256": row["observation_sha256"],
            }
            for name, row in sorted(per_opening.items())
        },
        "splits": {
            "stock_controls": {
                "packages": manifest["expected"]["openings_by_split"]["stock_controls"],
                "role": "separate control group; never a selection training row",
            },
            "cohort": {
                "packages": manifest["expected"]["openings_by_split"]["cohort"],
                "role": "evaluation group; a package never appears in two folds",
            },
        },
        "folds": folds,
        "excluded": accepted["openings"]["excluded"],
        "bridge_scope": (
            "the package container is read for every format the game writes; the "
            "two stock controls are format 8 and are decoded with their declared "
            "data version"
        ),
    }


def opening_features(manifest, accepted, entry, catalogs_all):
    package_path = accepted["packages"][entry["package"]]["locator"]
    container = exports.cached_net(input_only(package_path))
    net = container["net"]
    native_networks = load_input_json(binding.raw_dir(entry) / "networks.json.gz")
    native = topology.from_native(native_networks, entry["opening"])
    built = exports.exported_package(net, catalogs_all)
    counts, failures = exports.accepted_bridge.compare(built, native, train_only=True)
    train_segments = [
        segment_id
        for segment_id, segment in native["segments"].items()
        if topology.train_lanes(segment)
    ]
    table = exports.tangents(net)
    missing = [segment_id for segment_id in train_segments if segment_id not in table]
    tangent_digest = exports.tangent_table_digest(table, train_segments)
    native_digest = exports.accepted_bridge.model_input_digest(native)
    export_digest = exports.accepted_bridge.model_input_digest(built)
    return {
        "package": entry["package"],
        "raw": entry["raw"],
        "crp": container["lineage"],
        "native": {
            "networks_sha256": binding.file_digest(
                input_only(binding.raw_dir(entry) / "networks.json.gz")
            ),
            "plan_sha256": binding.file_digest(
                input_only(binding.raw_dir(entry) / "query-freeze.json.gz")
            ),
            "train_segments": len(train_segments),
        },
        "tangents": {
            "source": "export-derived hypothesis; absent from the native snapshot",
            "train_segments_covered": len(train_segments) - len(missing),
            "missing_train_segments": sorted(missing),
            "table_digest": tangent_digest,
            "report": exports.tangent_report(table),
            "versus_chord": exports.tangent_chord_angles(exports.attach(native, table)),
        },
        "bridge": {
            "train_only_fields": {
                field: {
                    "checked": counts[field + ":checked"],
                    "agree": counts[field + ":agree"],
                    "rate": (counts[field + ":agree"] / counts[field + ":checked"])
                    if counts[field + ":checked"]
                    else None,
                }
                for field in exports.accepted_bridge.MODEL_FIELDS
            },
            "failures": failures,
            "model_input_digest": {
                "native_sha256": native_digest["sha256"],
                "export_sha256": export_digest["sha256"],
                "identical": native_digest == export_digest,
                "segments": native_digest["segments"],
                "nodes": native_digest["nodes"],
            },
            "export_only_needs_catalog": sorted(
                {value.split(":", 1)[0] for value in built["missing"]}
            ),
        },
    }


def freeze_features(manifest, accepted, protocol):
    entries = accepted["openings"]["openings"]
    catalogs_all = exports.catalogs_for(entries, {"packages": accepted["packages"]})
    rows = {}
    for entry in entries:
        rows[entry["opening"]] = opening_features(
            manifest, accepted, entry, catalogs_all
        )
    totals = {}
    for row in rows.values():
        for field, value in row["bridge"]["train_only_fields"].items():
            bucket = totals.setdefault(field, {"checked": 0, "agree": 0})
            bucket["checked"] += value["checked"]
            bucket["agree"] += value["agree"]
    tangent_totals = {
        "train_segments": sum(
            row["tangents"]["train_segments_covered"]
            + len(row["tangents"]["missing_train_segments"])
            for row in rows.values()
        ),
        "covered": sum(
            row["tangents"]["train_segments_covered"] for row in rows.values()
        ),
        "missing": sum(
            len(row["tangents"]["missing_train_segments"]) for row in rows.values()
        ),
        "formats": {},
    }
    for row in rows.values():
        key = str(row["crp"]["crp_format"])
        tangent_totals["formats"][key] = tangent_totals["formats"].get(key, 0) + 1
    return {
        "schema": 1,
        "study": FREEZE,
        "freeze": FREEZE,
        "frozen_at": protocol["frozen_at"],
        "protocol_sha256": binding.digest(binding.encoded(protocol)),
        "sources": sources(manifest),
        "definition": (
            "per opening: the frozen export container and section lineage; the "
            "pre-query native topology hash; the export-derived tangents for every "
            "Train segment and their float precision; and the field-by-field "
            "agreement between export-derived and native model inputs"
        ),
        "openings": rows,
        "totals": {
            field: {
                "checked": value["checked"],
                "agree": value["agree"],
                "rate": (value["agree"] / value["checked"])
                if value["checked"]
                else None,
            }
            for field, value in sorted(totals.items())
        },
        "tangents": tangent_totals,
    }


def build(manifest, write):
    accepted = binding.accepted_openings(manifest, verify_observations=False)
    expected_queries, per_opening = binding.expected_query_set(
        accepted["openings"], accepted["integrity"]
    )
    folds = binding.fold_plan(manifest, per_opening)
    protocol = freeze_protocol(manifest, accepted, per_opening, folds)
    if write:
        PROTOCOL.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    features = freeze_features(manifest, accepted, protocol)
    if write:
        FEATURES.write_text(json.dumps(features, indent=2, sort_keys=True) + "\n")

    rules = jm.rule_names()
    entries = {entry["opening"]: entry for entry in accepted["openings"]["openings"]}
    packages = {}
    engines = {}
    for name, entry in entries.items():
        container = exports.cached_net(
            input_only(accepted["packages"][entry["package"]]["locator"])
        )
        native = topology.from_native(
            load_input_json(binding.raw_dir(entry) / "networks.json.gz"), name
        )
        packages[name] = exports.attach(native, exports.tangents(container["net"]))
        engines[name] = jm.Engine(packages[name])
    queries = []
    for query_id in sorted(
        expected_queries,
        key=lambda key: (
            expected_queries[key]["opening"],
            expected_queries[key]["plan_index"],
        ),
    ):
        query = expected_queries[query_id]
        engine = engines[query["opening"]]
        predictions = {rule: engine.predict(query["request"], rule) for rule in rules}
        queries.append({**query, "predictions": predictions})
    document = {
        "schema": 1,
        "study": FREEZE,
        "freeze": FREEZE,
        "frozen_at": protocol["frozen_at"],
        "protocol_sha256": binding.digest(binding.encoded(protocol)),
        "features_sha256": binding.digest(
            json.dumps(features, indent=2, sort_keys=True).encode() + b"\n"
        ),
        "queries_sha256": binding.digest(json.dumps(queries, sort_keys=True).encode()),
        "sources": sources(manifest),
        "rules": rules,
        "primary": manifest["primary"],
        "openings": {
            name: {
                "train_segments": sum(
                    1
                    for segment in package["segments"].values()
                    if topology.train_lanes(segment)
                ),
                "tangent_missing": package["tangent_missing"],
            }
            for name, package in packages.items()
        },
        "queries": queries,
    }
    if write:
        PREDICTIONS.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return protocol, features, document


def _stable(value):
    """Drop the volatile freeze timestamp before comparing two runs."""
    if isinstance(value, dict):
        return {
            key: _stable(item)
            for key, item in value.items()
            if key
            not in (
                "frozen_at",
                "features_sha256",
                "queries_sha256",
                "protocol_sha256",
                "sources",
            )
        }
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="recompute and compare")
    args = parser.parse_args()
    manifest = binding.load_manifest()
    protocol, features, document = build(manifest, not args.check)
    if args.check:
        frozen_protocol = json.loads(PROTOCOL.read_text())
        frozen_features = json.loads(FEATURES.read_text())
        frozen = json.loads(PREDICTIONS.read_text())
        for name, a, b in (
            ("protocol", protocol, frozen_protocol),
            ("features", features, frozen_features),
            ("predictions", document, frozen),
        ):
            if _stable(a) != _stable(b):
                raise SystemExit(f"{name} is not reproducible from the current sources")
        print(
            json.dumps(
                {
                    "checked": True,
                    "queries": len(document["queries"]),
                    "rules": len(document["rules"]),
                    "predictions_sha256": binding.file_digest(PREDICTIONS),
                }
            )
        )
        return
    print(
        json.dumps(
            {
                "queries": len(document["queries"]),
                "rules": len(document["rules"]),
                "protocol_sha256": binding.file_digest(PROTOCOL),
                "features_sha256": binding.file_digest(FEATURES),
                "predictions_sha256": binding.file_digest(PREDICTIONS),
            }
        )
    )


if __name__ == "__main__":
    main()
