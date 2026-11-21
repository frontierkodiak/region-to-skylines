"""Closed binding: the frozen manifest, the query set, the folds and the labels.

The accepted study's review recorded one nonblocking limit for a future
reuse: *the evaluator assumes the producer's manifest key sets and query-set
uniqueness/completeness; do not repurpose the helper as a generic acceptance
gate without closed-manifest validation.* This module is that closed
validation, and the new study's evaluator calls it before it scores anything.

`BindingError` is raised, never caught into a score.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPABILITY = HERE.parent
ACCEPTED = CAPABILITY / "rail-query-model-v1"
MANIFEST = HERE / "manifest.json"
PROTOCOL = HERE / "protocol.json"
FEATURES = HERE / "features.json"
PREDICTIONS = HERE / "predictions.json"
OBSERVATION = "observation.json.gz"

SUCCESS = "success"
NO_PATH = "no_path"
ABSTAIN = "abstain"
UNKNOWN = "unknown"


class BindingError(Exception):
    """A frozen input, query, fold or label does not match what was declared."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    return digest(Path(path).read_bytes())


def load_json(path):
    import gzip

    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf8") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def closed(record, expected, subject):
    """Reject any key set other than `expected`."""
    if not isinstance(record, dict):
        raise BindingError(f"{subject}: expected an object")
    keys = set(record)
    if keys != set(expected):
        raise BindingError(
            f"{subject}: keys differ; missing {sorted(set(expected) - keys)}, "
            f"unknown {sorted(keys - set(expected))}"
        )


# ------------------------------------------------------------------- manifest

MANIFEST_KEYS = (
    "schema",
    "study",
    "source",
    "expected",
    "measures",
    "pairings",
    "thresholds_degrees",
    "junction_kinds",
    "baselines",
    "frozen_rules",
    "primary",
    "selection",
    "labels",
)
SOURCE_KEYS = (
    "repo",
    "accepted_pr",
    "accepted_head",
    "accepted_merge",
    "internal_branch",
    "native_study",
    "accepted_prefix",
    "accepted_files",
)
EXPECTED_KEYS = ("openings_by_split", "packages", "excluded", "zero_query_packages")
SELECTION_KEYS = (
    "criterion",
    "eligible",
    "ties",
    "not_estimable",
    "control_protocol",
)
LABEL_KEYS = ("positive", "negative", "unknown")


def load_manifest(path=MANIFEST):
    """Read and closed-validate the study design. Raises `BindingError`."""
    manifest = json.loads(Path(path).read_text())
    closed(manifest, MANIFEST_KEYS, "manifest")
    if manifest["schema"] != 1:
        raise BindingError("manifest: unsupported schema")
    if manifest["study"] != "rail-junction-fit-v1":
        raise BindingError("manifest: unexpected study name")
    closed(manifest["source"], SOURCE_KEYS, "manifest.source")
    closed(manifest["expected"], EXPECTED_KEYS, "manifest.expected")
    closed(manifest["selection"], SELECTION_KEYS, "manifest.selection")
    closed(manifest["labels"], LABEL_KEYS, "manifest.labels")
    accepted = accepted_paths(manifest)
    for key, expected in manifest["source"]["accepted_files"].items():
        actual = file_digest(accepted[key])
        if actual != expected:
            raise BindingError(
                f"accepted source {key}: hash differs from the frozen pin"
            )
    if set(manifest["junction_kinds"]) != {"continuation", "turn"}:
        raise BindingError("manifest: junction kinds must be continuation and turn")
    if tuple(manifest["thresholds_degrees"]) != tuple(
        sorted(set(manifest["thresholds_degrees"]))
    ):
        raise BindingError("manifest: thresholds must be a sorted unique grid")
    import junction_model

    expected_rules = expected_rule_names(manifest)
    if tuple(junction_model.BASELINES) != tuple(manifest["baselines"]):
        raise BindingError("manifest: baselines differ from the model's")
    if tuple(junction_model.FROZEN_RULES) != tuple(manifest["frozen_rules"]):
        raise BindingError("manifest: frozen rules differ from the model's")
    if junction_model.rule_names() != expected_rules:
        raise BindingError("model rules differ from the frozen design")
    if manifest["primary"].get("correspondence") != junction_model.PRIMARY_EQUIVALENT:
        raise BindingError("manifest: unexpected primary correspondence rule")
    if manifest["primary"].get("reference") != junction_model.PRIMARY_REFERENCE:
        raise BindingError("manifest: unexpected primary reference rule")
    return manifest


def expected_rule_names(manifest):
    names = list(manifest["baselines"]) + list(manifest["frozen_rules"])
    for measure in manifest["measures"]:
        for pairing in manifest["pairings"]:
            names.append(f"{measure}:continuation:{pairing}")
    for measure in manifest["measures"]:
        for threshold in manifest["thresholds_degrees"]:
            for pairing in manifest["pairings"]:
                names.append(f"{measure}:turn:{threshold}:{pairing}")
    return names


def accepted_paths(manifest):
    prefix = Path(manifest["source"]["accepted_prefix"])
    root = HERE.parents[3]
    return {key: root / prefix / key for key in manifest["source"]["accepted_files"]}


# --------------------------------------------------------------- frozen inputs


def accepted_openings(manifest, verify_observations=True):
    paths = accepted_paths(manifest)
    openings = load_json(paths["openings.json"])
    packages = load_json(paths["packages.json"])
    protocol = load_json(paths["corrected/protocol.json"])
    integrity = load_json(paths["corrected/integrity.json"])
    closed(
        openings, ("schema", "note", "openings", "excluded", "bridge"), "openings.json"
    )
    closed(packages, ("schema", "note", "packages"), "packages.json")
    for key in ("code", "inputs_native", "freeze"):
        if key not in integrity:
            raise BindingError(f"integrity.json: missing {key}")

    entries = openings["openings"]
    for entry in entries:
        closed(
            entry,
            ("opening", "split", "group", "label", "package", "raw"),
            f"openings.{entry.get('opening', '?')}",
        )
    for key, entry in packages["packages"].items():
        closed(entry, ("bytes", "locator", "sha256"), f"packages.{key}")

    expected = manifest["expected"]
    by_split = {}
    for entry in entries:
        by_split.setdefault(entry["split"], []).append(entry["opening"])
    if {key: sorted(value) for key, value in by_split.items()} != {
        key: sorted(value) for key, value in expected["openings_by_split"].items()
    }:
        raise BindingError("openings.json: split membership differs from the manifest")
    if set(packages["packages"]) != set(expected["packages"]):
        raise BindingError("packages.json: package keys differ from the manifest")
    if sorted(entry["opening"] for entry in entries) != sorted(
        opening for names in expected["openings_by_split"].values() for opening in names
    ):
        raise BindingError("openings.json: opening set differs from the manifest")
    excluded = [entry["opening"] for entry in openings["excluded"]]
    if sorted(excluded) != sorted(expected["excluded"]):
        raise BindingError("openings.json: excluded set differs from the manifest")

    # The frozen package hashes in the accepted protocol are the ones bound here.
    for key, entry in packages["packages"].items():
        if protocol["packages"].get(key) != entry["sha256"]:
            raise BindingError(f"package {key}: accepted protocol hash differs")
        if Path(entry["locator"]).stat().st_size != entry["bytes"]:
            raise BindingError(f"package {key}: size differs from the frozen record")
        if file_digest(entry["locator"]) != entry["sha256"]:
            raise BindingError(f"package {key}: bytes differ from the frozen SHA-256")

    # Per-opening input hashes are the accepted study's own integrity bindings.
    # The freeze path hashes only the input files; an observation's bytes are
    # read by the evaluator, which binds them here before scoring.
    inputs = integrity["inputs_native"]
    for entry in entries:
        names = ["networks.json.gz", "query-freeze.json.gz"]
        if verify_observations:
            names.append(OBSERVATION)
        for name in names:
            relative = f"capability-evidence/{entry['raw']}/{name}"
            path = HERE.parents[1] / relative
            if relative not in inputs:
                raise BindingError(f"{entry['opening']}: {name} is not integrity-bound")
            if file_digest(path) != inputs[relative]:
                raise BindingError(f"{entry['opening']}: {name} changed")
    return {
        "openings": openings,
        "packages": packages["packages"],
        "protocol": protocol,
        "integrity": integrity["inputs_native"],
        "hashes": {
            key: file_digest(path) for key, path in accepted_paths(manifest).items()
        },
    }


def raw_dir(entry):
    return HERE.parents[1] / "capability-evidence" / entry["raw"]


def selected_requests(plan):
    """The primary set: non-diagnostic literal-boundary requests, in plan order."""
    return [
        (index, request)
        for index, request in enumerate(plan["plan"]["requests"])
        if not request["diagnostic"] and request["position_kind"] == "boundary"
    ]


def expected_query_set(openings, integrity):
    """Every selected query of every opening, with its plan request and hashes.

    Only the input files are read. The observation hash is the accepted study's
    own integrity binding, not a hash of bytes this function opens.
    """
    queries = {}
    per_opening = {}
    for entry in openings["openings"]:
        directory = raw_dir(entry)
        plan = load_json(directory / "query-freeze.json.gz")
        if set(plan) != {"schema", "plan", "submitted"} and "plan" not in plan:
            raise BindingError(f"{entry['opening']}: query freeze has no plan")
        selected = selected_requests(plan)
        per_opening[entry["opening"]] = {
            "package": entry["package"],
            "split": entry["split"],
            "group": entry["group"],
            "raw": entry["raw"],
            "selected": len(selected),
            "candidates": plan["plan"].get("candidate_boundary_count"),
            "limit": plan["plan"].get("boundary_limit"),
            "plan_sha256": file_digest(directory / "query-freeze.json.gz"),
            "networks_sha256": file_digest(directory / "networks.json.gz"),
            "observation_sha256": integrity[
                f"capability-evidence/{entry['raw']}/{OBSERVATION}"
            ],
        }
        for rank, (plan_index, request) in enumerate(selected):
            query_id = f"{entry['opening']}:{plan_index}"
            if query_id in queries:
                raise BindingError(f"query {query_id} appears twice")
            queries[query_id] = {
                "query_id": query_id,
                "plan_index": plan_index,
                "rank": rank,
                "opening": entry["opening"],
                "split": entry["split"],
                "group": entry["group"],
                "package": entry["package"],
                "request": request,
            }
    return queries, per_opening


def verify_query_set(predictions, openings, expected):
    """The predictions must be exactly the expected selected set, once each."""
    rows = predictions["queries"]
    seen = set()
    for row in rows:
        query_id = row["query_id"]
        if query_id in seen:
            raise BindingError(f"prediction {query_id} appears twice")
        seen.add(query_id)
        if query_id not in expected:
            raise BindingError(f"prediction {query_id} is not a selected plan request")
        want = expected[query_id]
        for key in (
            "plan_index",
            "rank",
            "opening",
            "split",
            "group",
            "package",
            "request",
        ):
            if row[key] != want[key]:
                raise BindingError(f"{query_id}: {key} differs from the frozen plan")
    missing = sorted(set(expected) - seen)
    if missing:
        raise BindingError(
            f"predictions omit {len(missing)} selected queries: {missing[:3]}"
        )
    if len(rows) != len(expected):
        raise BindingError("predictions do not cover the selected set exactly")
    return rows


# ------------------------------------------------------------------------ folds


def fold_plan(manifest, per_opening):
    """Strict leave-one-package-out over the cohort; controls trained on cohort.

    A package is never on both sides of a fold, and a stock control never enters
    a selection. Zero-query packages contribute no row; folds that would hold
    out one of them are recorded as not estimable instead of scored as absent.
    """
    cohort = manifest["expected"]["openings_by_split"]["cohort"]
    controls = manifest["expected"]["openings_by_split"]["stock_controls"]
    packages = set(manifest["expected"]["packages"])
    if set(cohort) & set(controls):
        raise BindingError(
            f"a package is in both splits: {sorted(set(cohort) & set(controls))}"
        )
    if set(cohort) | set(controls) != packages:
        raise BindingError(
            "the splits do not partition the frozen packages; "
            f"missing {sorted(packages - (set(cohort) | set(controls)))}"
        )
    with_queries = [name for name in cohort if per_opening[name]["selected"] > 0]
    zero_query = [name for name in cohort if per_opening[name]["selected"] == 0]
    folds = []
    for held in with_queries:
        train = [name for name in cohort if name != held]
        folds.append(
            {
                "fold": f"cohort:{held}",
                "kind": "cohort_leave_one_package_out",
                "train": train,
                "held_out": [held],
                "selection_train": [
                    name for name in train if per_opening[name]["selected"] > 0
                ],
            }
        )
    for held in controls:
        folds.append(
            {
                "fold": f"control:{held}",
                "kind": "stock_control_held_out",
                "train": list(cohort),
                "held_out": [held],
                "selection_train": list(with_queries),
            }
        )
    for fold in folds:
        if set(fold["train"]) & set(fold["held_out"]):
            raise BindingError(
                f"fold {fold['fold']} trains on its own held-out package"
            )
        if fold["held_out"][0] in fold["selection_train"]:
            raise BindingError(f"fold {fold['fold']} selects on its held-out package")
        if set(fold["selection_train"]) & set(controls):
            raise BindingError(f"fold {fold['fold']} selects on a stock control")
        if not set(fold["selection_train"]) <= set(cohort):
            raise BindingError(f"fold {fold['fold']} selects outside the cohort")
    covered = [
        fold["held_out"][0] for fold in folds if fold["kind"].startswith("cohort")
    ]
    if sorted(covered) != sorted(with_queries):
        raise BindingError(
            "cohort folds do not cover every package with queries exactly once"
        )
    if sorted(zero_query) != sorted(manifest["expected"]["zero_query_packages"]):
        raise BindingError("zero-query package set differs from the manifest")
    return {"folds": folds, "zero_query": zero_query}


# ----------------------------------------------------------------------- labels


def label(row):
    """One observed row's label: `success`, `no_path` or `unknown`.

    A success must be complete, released, report success and return the literal
    request endpoints as its first and last positions. A failure must be
    complete, released and report success=false. Anything else is Unknown and
    is never scored.
    """
    if "result" not in row:
        return UNKNOWN, {"reason": "row_has_no_result"}
    result = row["result"]
    for key in ("complete", "released", "success"):
        if not isinstance(result.get(key), bool):
            raise BindingError(f"row result {key} is missing or not boolean")
    if not result["complete"]:
        return UNKNOWN, {"reason": "incomplete"}
    if not result["released"]:
        return UNKNOWN, {"reason": "unreleased"}
    request = row.get("request")
    if request is None:
        raise BindingError("observed row has no request")
    if result["success"]:
        positions = result.get("positions") or []
        if len(positions) < 2:
            return UNKNOWN, {"reason": "success_without_positions"}
        if positions[0] != request["from"] or positions[-1] != request["to"]:
            return UNKNOWN, {"reason": "returned_endpoints_differ"}
        return SUCCESS, {
            "reason": "literal_endpoints_returned",
            "length": result.get("length"),
            "flags": result.get("flags"),
        }
    return NO_PATH, {
        "reason": "observed_failure",
        "length": result.get("length"),
        "flags": result.get("flags"),
    }


def observation_bundle(entry):
    """One opening's observed rows, its frozen plan and its provenance.

    Reading this function's return is the first time the study sees a label.
    """
    directory = raw_dir(entry)
    document = load_json(directory / OBSERVATION)
    plan = load_json(directory / "query-freeze.json.gz")
    if "paths" not in document:
        raise BindingError(f"{entry['opening']}: observation has no paths")
    return {
        "rows": document["paths"],
        "plan_requests": plan["plan"]["requests"],
        "completed": document.get("completed") is True,
        "observation_sha256": file_digest(directory / OBSERVATION),
        "artifact_sha256": document.get("artifact_sha256"),
        "package": document.get("package"),
        "native_context": {
            key: document.get("native_context", {}).get(key)
            for key in ("update_mode", "invert_traffic", "no_workshop", "mods_enabled")
        },
        "build": {
            key: document.get("build_receipt", {}).get(key)
            for key in ("dll_sha256", "game_executable_sha256")
        },
        "limits": document.get("limits"),
        "collector_sha256": document.get("collector_sha256"),
    }


OBSERVATION_KEYS = ("update_mode", "invert_traffic", "no_workshop", "mods_enabled")


def bind_observations(predictions, protocol, features, openings, packages):
    """Bind the predictions to the frozen plans, packages and observation bytes.

    Mirrors the accepted v2 evaluator's binding and adds the closed validation
    the accepted review asked for: the observation's selected-row set must be
    exactly the predicted query set, once each, at its plan index.
    """
    if predictions.get("freeze") != "rail-junction-fit-v1":
        raise BindingError("predictions are not the rail-junction-fit-v1 freeze")
    if predictions.get("study") != "rail-junction-fit-v1":
        raise BindingError("predictions belong to another study")
    if file_digest(PROTOCOL) != predictions.get("protocol_sha256"):
        raise BindingError("protocol.json does not match the predictions")
    if file_digest(FEATURES) != predictions.get("features_sha256"):
        raise BindingError("features.json does not match the predictions")
    if digest(encoded(protocol)) != file_digest(PROTOCOL):
        raise BindingError("protocol.json on disk differs from its canonical encoding")
    for name, expected in predictions.get("sources", {}).get("own", {}).items():
        if file_digest(HERE / name) != expected:
            raise BindingError(f"study source {name} changed after the freeze")
    for name, expected in predictions.get("sources", {}).get("accepted", {}).items():
        if file_digest(ACCEPTED / name) != expected:
            raise BindingError(f"accepted source {name} changed after the freeze")

    entries = {entry["opening"]: entry for entry in openings["openings"]}
    bundles = {}
    for opening, entry in entries.items():
        bundle = observation_bundle(entry)
        frozen = protocol["openings"][opening]
        package = packages[entry["package"]]
        if bundle["observation_sha256"] != frozen["observation_sha256"]:
            raise BindingError(f"{opening}: observation bytes changed")
        if (
            bundle["plan_requests"]
            != load_json(raw_dir(entry) / "query-freeze.json.gz")["plan"]["requests"]
        ):
            raise BindingError(f"{opening}: plan rows are inconsistent")
        if bundle["artifact_sha256"] != package["sha256"]:
            raise BindingError(f"{opening}: observed artifact hash is not the package")
        if bundle["package"] != package["locator"]:
            raise BindingError(f"{opening}: observed package locator differs")
        rows = bundle["rows"]
        requests = bundle["plan_requests"]
        if bundle["completed"] and len(rows) != len(requests):
            raise BindingError(f"{opening}: completed observation is missing plan rows")
        if len(rows) > len(requests):
            raise BindingError(f"{opening}: more observation rows than plan requests")
        for index, row in enumerate(rows):
            if row.get("request") != requests[index]:
                raise BindingError(
                    f"{opening}: observation row {index} is not the frozen plan request"
                )
        bundles[opening] = bundle
    return bundles


def labels(bundles, expected_queries):
    """Attach each selected query's label from the row at its plan index."""
    out = {}
    for query_id, query in expected_queries.items():
        bundle = bundles[query["opening"]]
        index = query["plan_index"]
        if index >= len(bundle["rows"]):
            out[query_id] = {"label": UNKNOWN, "detail": {"reason": "row_absent"}}
            continue
        row = bundle["rows"][index]
        if row["request"] != query["request"]:
            raise BindingError(f"{query_id}: observed row is not the plan request")
        value, detail = label(row)
        out[query_id] = {"label": value, "detail": detail}
    return out


# --------------------------------------------------------------------- scoring


def confusion(pairs):
    """Counts for (prediction, label) pairs, abstentions kept separate."""
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "abstain": 0, "unknown": 0}
    for prediction, value in pairs:
        if value == UNKNOWN:
            counts["unknown"] += 1
        elif prediction == ABSTAIN:
            counts["abstain"] += 1
        elif prediction == SUCCESS and value == SUCCESS:
            counts["tp"] += 1
        elif prediction == SUCCESS and value == NO_PATH:
            counts["fp"] += 1
        elif prediction == NO_PATH and value == NO_PATH:
            counts["tn"] += 1
        elif prediction == NO_PATH and value == SUCCESS:
            counts["fn"] += 1
    return counts


def rates(counts):
    tp, fp, tn, fn = counts["tp"], counts["fp"], counts["tn"], counts["fn"]
    positives = tp + fn
    negatives = tn + fp
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / positives if positives else None
    specificity = tn / negatives if negatives else None
    if recall is None or specificity is None:
        balanced = None
    else:
        balanced = (recall + specificity) / 2.0
    scored = tp + fp + tn + fn
    coverage = (
        scored / (scored + counts["abstain"]) if (scored + counts["abstain"]) else None
    )
    return {
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "balanced_accuracy": balanced,
        "coverage": coverage,
        "abstention": (counts["abstain"] / (scored + counts["abstain"]))
        if (scored + counts["abstain"])
        else None,
    }


def select_rule(rows, rules, criterion="balanced_accuracy"):
    """Pick one rule using training rows only, with a predeclared tie order.

    A rule is eligible only when it abstains on nothing in training and both
    classes are present. Ties are broken by precision, then recall, then the
    rule name; the full tied set is returned so the reader sees the tie.
    """
    scores = {}
    for rule in rules:
        pairs = [(row["predictions"][rule]["prediction"], row["label"]) for row in rows]
        counts = confusion(pairs)
        metrics = rates(counts)
        scores[rule] = {"counts": counts, "rates": metrics}
    if not rows:
        return None, scores, {"reason": "no training rows"}
    values = {row["label"] for row in rows}
    if values != {SUCCESS, NO_PATH}:
        return (
            None,
            scores,
            {"reason": "training set lacks a class", "classes": sorted(values)},
        )
    eligible = [
        rule
        for rule in rules
        if scores[rule]["counts"]["abstain"] == 0
        and scores[rule]["rates"][criterion] is not None
    ]
    if not eligible:
        return None, scores, {"reason": "no eligible rule"}

    def key(rule):
        metrics = scores[rule]["rates"]
        return (
            -metrics[criterion],
            -(metrics["precision"] if metrics["precision"] is not None else -math.inf),
            -(metrics["recall"] if metrics["recall"] is not None else -math.inf),
            rule,
        )

    ranked = sorted(eligible, key=key)
    best = scores[ranked[0]]["rates"][criterion]
    tied = [rule for rule in ranked if scores[rule]["rates"][criterion] == best]
    return ranked[0], scores, {"tied_at_best": tied, "criterion": criterion}
