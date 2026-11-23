"""Integrate the three accepted rail research publications as separate typed studies.

This reads archived bytes only. It never runs the research models, the collector,
a scorer, the game or the browser. It re-checks each publication's file scope and
hash bindings, derives the studies from the frozen outputs, and writes one
projection the ledger page renders under Rail.

The three studies stay distinct: a query-scoped reachability fit, a tangent
junction fit, and a frozen stock holdout. Nothing is pooled with the directed-rail
native study, no confusion table is averaged across studies, and no row becomes a
promise, a certificate or a live rule.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tools/map-factory/capability-evidence"
MANIFEST_FILE = "tools/map-factory/capability-evidence/rail-research-sources.json"
PROJECTION_FILE = "tools/map-factory/capability-evidence/rail-research-studies.json"

STUDY_IDS = ("rail-query-model-v1", "rail-junction-fit-v1", "rail-stock-holdout-v1")

SOURCE = {
    "rail-query-model-v1": {
        "kind": "query_scoped_rail_reachability_study",
        "title": "Query-scoped rail reachability fit",
        "publication_commit": "364628b81701c134e3f469f9e175c4fe40f7a311",
        "publication_base": "1a0e45c65745ba5f05cf22f947da2e88fed25277",
        "internal_merge": "d008778fd44cf448b2078738468267e8a7863af0",
        "source_issue": "01a1ff50-0902-76c7-98ca-3818031097b6",
        "pull_request": 81,
        "branch": "PL-1142-native-v2",
        "accepted_head": "364628b81701c134e3f469f9e175c4fe40f7a311",
        "earlier_head": "97e00389f4ad0eb30aa1ff1d775876c87f4ab27c",
    },
    "rail-junction-fit-v1": {
        "kind": "export_tangent_junction_study",
        "title": "Export-tangent junction fit",
        "publication_commit": "49cf49516f4aa8b24a154d9923c1a6fd149bf1a3",
        "publication_base": "364628b81701c134e3f469f9e175c4fe40f7a311",
        "internal_merge": "fef279efb339d26d3cc86eddcf588f3f7611e290",
        "source_issue": "01a1ffa9-451f-7c0d-ac3c-aa4b85954785",
        "pull_request": 82,
        "branch": "PL-1142-native-v2",
        "accepted_head": "49cf49516f4aa8b24a154d9923c1a6fd149bf1a3",
    },
    "rail-stock-holdout-v1": {
        "kind": "frozen_stock_rule_holdout_study",
        "title": "Frozen stock rail holdout",
        "publication_commit": "914c153687106197e5f3a745d3ff7e181181ea8a",
        "publication_base": "49cf49516f4aa8b24a154d9923c1a6fd149bf1a3",
        "internal_merge": None,
        "source_issue": "01a20005-783b-7b01-b1c8-d4bbda7929cb",
        "pull_request": 84,
        "branch": "PL-1142-native-v2",
        "accepted_head": "914c153687106197e5f3a745d3ff7e181181ea8a",
    },
}

REVIEW = {
    "rail-query-model-v1": {
        "review_comment": "01a1ff7f-3427-7405-b046-2c1fafab5afd",
        "acceptance_comment": "01a1ffaa-7b97-7857-93f0-8fb025ecb019",
        "note": "Correction review requested; the corrected head was accepted after independent reproduction of all 43 tests and the three read-only checks.",
    },
    "rail-junction-fit-v1": {
        "review_comment": "01a20004-6429-7690-be64-20a0fe3ba017",
        "acceptance_comment": "01a20004-6429-7690-be64-20a0fe3ba017",
        "note": "Independent PASS reproduced all 58 rules and 174 grouped rate tables and traced the retained successful Pittsburgh path.",
    },
    "rail-stock-holdout-v1": {
        "review_comment": "01a20066-faae-71b4-9f76-1bf04cd6e579",
        "acceptance_comment": "01a2006a-fec6-7a1b-85dc-79fca6cc411c",
        "parent_acceptance_comment": "01a2006e-7a1d-717a-8be5-291f3b6fdc7d",
        "note": "Neon peer review passed; the owner's return audit replayed the raw/context/freeze/count chain, and the parent replayed it again with identical results.",
    },
}

# The exact files carried in this repository, byte for byte. Everything else in a
# publication is linked as an immutable Git blob through the strict source manifest.
COPIES = {
    "rail-query-model-v1": [
        ("README.md", "document"),
        ("RESULTS.md", "document"),
        ("REPRODUCE.md", "document"),
        ("protocol.json", "protocol"),
        ("integrity.json", "provenance"),
        ("openings.json", "provenance"),
        ("packages.json", "provenance"),
        ("corrected/CORRECTION.md", "document"),
        ("corrected/protocol.json", "protocol"),
        ("corrected/predictions.json", "frozen_predictions"),
        ("corrected/evaluation.json", "metrics"),
        ("corrected/bridge.json", "audit"),
        ("corrected/catalogs.json", "audit"),
        ("corrected/integrity.json", "provenance"),
        ("corrected/evidence/domain-contract-at-97e.log", "evidence"),
        ("corrected/evidence/domain-and-binding-contract-at-corrected.log", "evidence"),
        ("corrected/evidence/binding-probe-at-97e.log", "evidence"),
        ("corrected/evidence/binding-probe-at-corrected.log", "evidence"),
        ("corrected/evidence/binding-probe.py", "evidence"),
    ],
    "rail-junction-fit-v1": [
        ("README.md", "document"),
        ("RESULTS.md", "document"),
        ("REPRODUCE.md", "document"),
        ("manifest.json", "protocol"),
        ("protocol.json", "protocol"),
        ("features.json", "frozen_inputs"),
        ("predictions.json", "frozen_predictions"),
        ("evaluation.json", "metrics"),
        ("diagnostics.json", "audit"),
        ("bridge-audit.json", "audit"),
    ],
    "rail-stock-holdout-v1": [
        ("README.md", "document"),
        ("RESULTS.md", "document"),
        ("RailMetadata.cs", "provenance"),
        ("catalogs.json", "provenance"),
        ("collection-deferred.json", "provenance"),
        ("evaluation.json", "metrics"),
        ("freeze.json", "frozen_predictions"),
        ("history/pre-native-RESULTS.md.gz", "history"),
        ("history/pre-native-evaluation.json.gz", "history"),
        ("metadata-build.json", "provenance"),
        ("native-verification.json", "audit"),
        ("pre-native-correction.zip", "history"),
        ("public-prefab-facts.json", "provenance"),
        ("raw-integrity.json", "provenance"),
        ("resource-journal.json", "provenance"),
        ("selection-power.json", "provenance"),
    ],
}

EXPECTED_PUBLICATION_FILES = {
    "rail-query-model-v1": (29, 19, 10),
    "rail-junction-fit-v1": (18, 10, 8),
    "rail-stock-holdout-v1": (159, 16, 143),
}

# Rows keep only the rules a reader needs to follow the study; every rule's full
# numerator/denominator/null table lives in `tables`.
ROW_RULES = {
    "rail-query-model-v1": [
        "always_fail",
        "always_candidate",
        "weak_component",
        "lane:any_lane:forbidden",
        "lane:orientation_index:forbidden",
        "junction:continuation:any_lane",
    ],
    "rail-junction-fit-v1": [
        "frozen:always_fail",
        "frozen:always_candidate",
        "frozen:weak_component",
        "frozen:junction:continuation:any_lane",
        "chord:continuation:any_lane",
        "tangent:continuation:any_lane",
        "tangent:continuation:orientation_index",
    ],
    "rail-stock-holdout-v1": [
        "tangent:continuation:any_lane",
        "chord:continuation:any_lane",
    ],
}

LIMITS = {
    "rail-query-model-v1": (
        "Already-observed retrospective fit on the 276 selected literal requests of the accepted native "
        "cohort, not a blind or prospective holdout. The junction family was chosen after the first family "
        "was scored, so the fitted rule is a hypothesis and not an accepted native rule. Every observed "
        "success sits inside one weak Train component and all 51 cross-component requests fail; that is a "
        "statement about this selected set, not a proof that a connection can never be joined. Native lane "
        "connectivity, junction behaviour, path cost and rejected pairs are inferred from outcomes. The "
        "100000 length bound, the 128-request cap, Pittsburgh's 112 unqueried candidates, dynamic-assembly "
        "exclusion, plugins, three DLC-panel errors and Pittsburgh's separately audited degraded strict "
        "teardown bound the claim. FILE identity is not memory attestation or strict no-mods. Rail service, "
        "train spawning, editor/gameplay parity, sustained gameplay and human play are not verified. No "
        "geographic accuracy, prevalence, no-rail certificate, service or live yes is claimed."
    ),
    "rail-junction-fit-v1": (
        "Retrospective on an already-observed cohort, not a blind holdout. Tangent fields are not "
        "native-attested: the accepted native snapshots do not emit them, so every tangent value is read "
        "from the export and is an export-derived hypothesis. Strict leave-one-package-out selection picks "
        "the tangent rule in five of six cohort folds, but Pittsburgh, the only package that discriminates "
        "the rules, is the held-out fold where every remaining-perfect rule ties; the pooled selected "
        "out-of-fold result is therefore 10/4/229/1, identical to the reference, and neither number is a "
        "blind estimate. The false negative's native path is not reproduced by either rule (it crosses a "
        "pair both pairings reject), so the tangent rule matches the outcome through a different route: a "
        "better fit, not an identified junction law. The 100000 bound, the 128-request cap, Pittsburgh's "
        "112 unqueried candidates, dynamic-assembly/plugin/DLC limits and Pittsburgh's degraded strict "
        "teardown bound the claim. No game, browser, server or rebuild; no old scorer rerun."
    ),
    "rail-stock-holdout-v1": (
        "A deterministic stock selection inside the old catalog's supported domain, not blind global "
        "accuracy or geographic prevalence. Both rules predicted the same answer for all 48 selected "
        "requests before any native query, so this selection has no power to prefer tangent over chord. "
        "The eight failures belong to one package and are not independent package-level votes; each "
        "failure labels only its exact request and protocol, never geographic absence, service, spawning, "
        "a product promise or a junction law. Four unsupported packages stay metadata-only with no "
        "requests; supported package coverage is 6/10 of the selected packages. The optional Pittsburgh "
        "replay was not run and the retained successful-path counterexample is unresolved. The three "
        "post-load errors and the dynamic-assembly exclusion stay recorded. FILE identity is not memory "
        "attestation or strict no-mods, and stock packages have no prepared-input or CPU receipt lineage."
    ),
}

METHOD = {
    "rail-query-model-v1": (
        "The accepted study froze its protocol and predictions before opening any observation, then scored "
        "the fitted straightest-continuation junction rule on the 276 selected literal-boundary native "
        "requests (32 stock control + 244 cohort). A read-only export bridge re-derives every model-used "
        "field from the saved CRP bytes and compares it with the native network snapshot. This ledger "
        "re-checks the archived bytes and recomputes every rate from the preserved counts."
    ),
    "rail-junction-fit-v1": (
        "The accepted study predeclared a closed set of junction pairings and a 0-180 degree grid, wrote "
        "features and predictions before opening any observation, and scored 58 rules on the same 276 "
        "requests. Its chord family is an independent reimplementation that reproduces the accepted "
        "predictions exactly. Grouped leave-one-package-out selection is applied to the nine cohort "
        "packages. This ledger re-checks the archived bytes, the accepted prefix hashes and the derived "
        "tables."
    ),
    "rail-stock-holdout-v1": (
        "The pre-query freeze selected two pairing-difference, four same-pairing and four unsupported "
        "packages from the 102 non-control stock maps, fixed eight requests per supported package, and "
        "recorded both rules' predictions before any new native query. Twelve openings then ran the "
        "unchanged controls and the ten holdouts; the evaluator binds each request to its frozen "
        "prediction, the native result, the package bytes and the pre/post graph digests, reports the "
        "all-complete intent-to-test and the predeclared snapshot-matched tables, and keeps every "
        "unsupported or unqueried row explicit. This ledger re-checks every archived hash and recomputes "
        "both tables from the preserved rows."
    ),
}


def fail(message: str) -> None:
    raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canon(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def load_json(path: Path):
    return json.loads(path.read_text())


def gz_json(path: Path):
    return json.loads(gzip.decompress(path.read_bytes()))


def expect(condition, message: str) -> None:
    if not condition:
        fail(message)


def rounded(value):
    if isinstance(value, float):
        return round(value, 12)
    return value


def rate_block(table: dict, keys) -> dict:
    return {key: rounded(table.get(key)) for key in keys}


COUNT_KEYS = ("tp", "fp", "tn", "fn", "abstain", "unknown", "scored", "requests")
RATE_KEYS = (
    "coverage",
    "precision",
    "recall",
    "f1",
    "negative_precision",
    "specificity",
    "balanced_accuracy",
    "abstention",
)


def compact_confusion(table: dict) -> dict:
    """Every numerator, denominator and null, without inventing a zero."""
    return {
        "counts": {key: table[key] for key in COUNT_KEYS if key in table},
        "rates": {key: rounded(table[key]) for key in RATE_KEYS if key in table},
    }


def evidence_files(study: str) -> list[dict]:
    rows = []
    for relative, role in COPIES[study]:
        path = EVIDENCE / study / relative
        expect(path.is_file(), f"{study}: missing carried evidence {relative}")
        raw = path.read_bytes()
        rows.append(
            {
                "path": f"tools/map-factory/capability-evidence/{study}/{relative}",
                "sha256": sha(raw),
                "bytes": len(raw),
                "role": role,
            }
        )
    return rows


def source_manifest() -> dict:
    path = ROOT / MANIFEST_FILE
    manifest = load_json(path)
    expect(manifest.get("schema") == 1, "rail research source manifest schema changed")
    expect(
        list(manifest.get("publications", {})) == list(STUDY_IDS),
        "rail research source manifest lost a publication",
    )
    out = {}
    for study in STUDY_IDS:
        publication = manifest["publications"][study]
        expect(
            publication["commit"] == SOURCE[study]["publication_commit"],
            f"{study}: source manifest names another publication",
        )
        total, copied, linked = EXPECTED_PUBLICATION_FILES[study]
        files = publication["files"]
        expect(len(files) == total, f"{study}: publication file scope changed")
        expect(
            sorted(publication["copied"])
            == sorted(relative for relative, _ in COPIES[study]),
            f"{study}: carried-file list changed",
        )
        expect(
            len(publication["copied"]) == copied
            and len(publication["linked"]) == linked,
            f"{study}: carried/linked split changed",
        )
        expect(
            sorted(publication["copied"] + publication["linked"]) == sorted(files),
            f"{study}: carried and linked files do not partition the publication",
        )
        for relative, record in files.items():
            expect(
                isinstance(record.get("sha256"), str) and len(record["sha256"]) == 64,
                f"{study}: bad hash for {relative}",
            )
            expect(
                isinstance(record.get("git_blob"), str)
                and len(record["git_blob"]) == 40,
                f"{study}: bad blob id for {relative}",
            )
            expect(record.get("bytes", 0) > 0, f"{study}: bad size for {relative}")
            if relative in publication["copied"]:
                carried = EVIDENCE / study / relative
                expect(
                    carried.is_file(),
                    f"{study}: copied file missing from the repository: {relative}",
                )
                expect(
                    sha(carried.read_bytes()) == record["sha256"],
                    f"{study}: carried file differs from its publication: {relative}",
                )
            else:
                expect(
                    not (EVIDENCE / study / relative).exists(),
                    f"{study}: linked file must not be duplicated in the repository: {relative}",
                )
        # No stray files under the carried prefix.
        carried_root = EVIDENCE / study
        present = sorted(
            p.relative_to(carried_root).as_posix()
            for p in carried_root.rglob("*")
            if p.is_file()
        )
        expect(
            present == sorted(publication["copied"]),
            f"{study}: carried prefix has files outside the publication scope",
        )
        out[study] = {
            "file": MANIFEST_FILE,
            "sha256": sha(path.read_bytes()),
            "commit": publication["commit"],
            "prefix": publication["prefix"],
            "publication_files": total,
            "copied_files": copied,
            "linked_files": linked,
            "files_sha256": sha(canon(files).encode()),
        }
    return out, manifest["publications"]


def opening_native() -> dict:
    """The accepted query study's openings, with each raw receipt re-hashed."""
    openings = load_json(EVIDENCE / "rail-query-model-v1/openings.json")
    expect(len(openings["openings"]) == 11, "query study opening list changed")
    expect(
        len(openings["excluded"]) == 1
        and openings["excluded"][0]["opening"] == "rio-queue-denial",
        "the retained Rio queue denial changed",
    )
    native = {}
    for entry in openings["openings"]:
        base = EVIDENCE / entry["raw"]
        observation = base / "observation.json.gz"
        freeze = base / "query-freeze.json.gz"
        networks = base / "networks.json.gz"
        for path in (observation, freeze, networks):
            expect(path.is_file(), f"missing native receipt {path.relative_to(ROOT)}")
        obs_stored, plan_stored, net_stored = (
            path.read_bytes() for path in (observation, freeze, networks)
        )
        obs_bytes, plan_bytes, net_bytes = (
            gzip.decompress(raw) for raw in (obs_stored, plan_stored, net_stored)
        )
        native[entry["opening"]] = {
            "entry": entry,
            "stored": {
                "observation_sha256": sha(obs_stored),
                "query_freeze_sha256": sha(plan_stored),
                "networks_sha256": sha(net_stored),
            },
            "decompressed": {
                "observation_sha256": sha(obs_bytes),
                "query_freeze_sha256": sha(plan_bytes),
                "networks_sha256": sha(net_bytes),
            },
            "artifact_sha256": json.loads(obs_bytes)["artifact_sha256"],
            "plan": json.loads(plan_bytes)["plan"]["requests"],
            "paths": json.loads(obs_bytes)["paths"],
        }
    return native


def observed_label(result: dict) -> tuple[str, str]:
    if result.get("complete") is not True:
        return "unknown", "incomplete or unreleased"
    if result.get("success") is True:
        return "success", "literal endpoints returned"
    return "no_path", "complete and released, success=false"


def study_rows(
    study: str,
    predictions: dict,
    native: dict,
    labels_by_opening: dict,
    observed_counts: dict,
) -> list[dict]:
    expect(
        len(predictions["queries"]) == 276, f"{study}: frozen prediction rows changed"
    )
    rules = ROW_RULES[study]
    rows = []
    totals = {"success": 0, "no_path": 0, "unknown": 0}
    per_opening: dict[str, dict] = {}
    for query in predictions["queries"]:
        opening = query["opening"]
        index = query["plan_index"]
        record = native.get(opening)
        expect(
            record is not None,
            f"{study}: prediction names an unknown opening {opening}",
        )
        expect(index < len(record["plan"]), f"{study}: plan index outside {opening}")
        request = record["plan"][index]
        expect(
            request.get("diagnostic") is False
            and request.get("position_kind") == "boundary",
            f"{study}: predicted row {opening}:{index} is not a selected boundary request",
        )
        path = record["paths"][index]
        expect(
            path["request"] == request,
            f"{study}: native row {opening}:{index} does not match the frozen plan request",
        )
        label, reason = observed_label(path["result"])
        totals[label] += 1
        slot = per_opening.setdefault(
            opening, {"success": 0, "no_path": 0, "unknown": 0}
        )
        slot[label] += 1
        rows.append(
            {
                "id": f"{opening}:{index}",
                "opening": opening,
                "package": query["package"],
                "group": query["group"],
                "plan_index": index,
                "request": request,
                "observed": label,
                "observed_reason": reason,
                "observed_flags": path["result"].get("flags"),
                "observed_length": path["result"].get("length"),
                "predicted": {
                    rule: query["predictions"][rule]["prediction"] for rule in rules
                },
            }
        )
    for opening, counts in labels_by_opening.items():
        expect(
            per_opening.get(opening, {"success": 0, "no_path": 0, "unknown": 0})
            == counts,
            f"{study}: derived labels for {opening} do not match the archived evaluation",
        )
    expect(
        totals == observed_counts,
        f"{study}: derived label totals do not match the archived evaluation",
    )
    return rows


def query_study(native: dict, publication: dict) -> dict:
    base = EVIDENCE / "rail-query-model-v1"
    evaluation = load_json(base / "corrected/evaluation.json")
    predictions = load_json(base / "corrected/predictions.json")
    protocol = load_json(base / "corrected/protocol.json")
    bridge = load_json(base / "corrected/bridge.json")
    integrity = load_json(base / "corrected/integrity.json")
    earlier_integrity = load_json(base / "integrity.json")
    openings = load_json(base / "openings.json")
    packages = load_json(base / "packages.json")["packages"]
    expect(
        evaluation["schema"] == 2
        and evaluation["model_version"] == "rail-query-model-v2-corrected",
        "query study evaluation header changed",
    )
    expect(
        evaluation["freeze"]
        == predictions["freeze"]
        == protocol["freeze"]
        == integrity["freeze"]
        == "rail-query-model-v2-corrected",
        "query study freeze identity changed",
    )
    expect(
        sha((base / "corrected/predictions.json").read_bytes())
        == evaluation["predictions_sha256"],
        "query study evaluation does not bind the carried predictions",
    )
    expect(
        sha((base / "corrected/protocol.json").read_bytes())
        == evaluation["protocol_sha256"],
        "query study evaluation does not bind the carried protocol",
    )
    expect(
        predictions["supersedes"]["head"]
        == SOURCE["rail-query-model-v1"]["earlier_head"],
        "query study superseded head changed",
    )
    expect(
        predictions["supersedes"]["predictions_sha256"]
        == integrity["corrects"]["preserved_v1_artifacts"]["predictions.json"]
        and predictions["supersedes"]["protocol_sha256"]
        == integrity["corrects"]["preserved_v1_artifacts"]["protocol.json"],
        "query study superseded artifacts changed",
    )
    expect(
        integrity["corrects"]["reviewed_head"]
        == SOURCE["rail-query-model-v1"]["earlier_head"],
        "query study correction record names another reviewed head",
    )
    for relative, digest in integrity["corrects"]["preserved_v1_artifacts"].items():
        record = publication["files"].get(relative)
        expect(
            record is not None and record["sha256"] == digest,
            f"query study preserved v1 artifact changed: {relative}",
        )
        carried = base / relative
        if carried.is_file():
            expect(
                sha(carried.read_bytes()) == digest,
                f"carried v1 artifact differs: {relative}",
            )
    expect(
        earlier_integrity["study"] == "rail-query-model-v1",
        "query study earlier integrity names another study",
    )
    expect(
        sorted(integrity["outputs"])
        == [
            "corrected/bridge.json",
            "corrected/catalogs.json",
            "corrected/evaluation.json",
            "corrected/predictions.json",
            "corrected/protocol.json",
        ],
        "query study output scope changed",
    )
    for relative in integrity["evidence"]:
        expect((base / relative).is_file(), f"query study evidence lost {relative}")
    for name, record in native.items():
        package = packages[record["entry"]["package"]]
        expect(
            package["sha256"] == record["artifact_sha256"],
            f"query study package hash differs from the native opening: {name}",
        )
    for name, entry in evaluation["openings"].items():
        expect(
            entry["artifact_sha256"] == native[name]["artifact_sha256"],
            f"query study opening {name} names another package",
        )
        expect(
            entry["observation_sha256"] == native[name]["stored"]["observation_sha256"]
            and entry["query_freeze_sha256"]
            == native[name]["stored"]["query_freeze_sha256"]
            and entry["networks_sha256"] == native[name]["stored"]["networks_sha256"],
            f"query study opening {name} names another raw receipt",
        )

    result = evaluation["result"]
    expect(
        result["labels"] == {"exact_path_success": 27, "selected_query_failure": 249},
        "query study label counts changed",
    )
    expect(
        result["exact_distinct_edge"] == 25 and result["exact_same_edge"] == 2,
        "query study exact-edge split changed",
    )
    expect(len(result["rules"]) == 28, "query study rule count changed")
    fitted, primary = evaluation["fitted_rule"], evaluation["primary_rule"]
    expect(
        fitted == "junction:continuation:any_lane"
        and primary == "lane:orientation_index:forbidden",
        "query study fitted or primary rule changed",
    )
    expect(
        (
            result["rules"][fitted]["tp"],
            result["rules"][fitted]["fp"],
            result["rules"][fitted]["tn"],
            result["rules"][fitted]["fn"],
        )
        == (26, 4, 245, 1),
        "query study fitted confusion changed",
    )
    expect(
        (
            result["rules"][primary]["tp"],
            result["rules"][primary]["fp"],
            result["rules"][primary]["tn"],
            result["rules"][primary]["fn"],
        )
        == (11, 198, 51, 16),
        "query study primary confusion changed",
    )
    for row in result["rules"].values():
        expect(
            row["tp"] + row["fp"] + row["tn"] + row["fn"] + row["abstain"] == 276,
            "query study rule totals do not add up to the selected set",
        )
    expect(
        evaluation["bindings"]["query_bindings"] == 276
        and evaluation["bindings"]["opening_bindings"] == 11,
        "query study binding counts changed",
    )

    labels_by_opening = {
        name: {
            "success": entry["labels"].get("exact_path_success", 0),
            "no_path": entry["labels"].get("selected_query_failure", 0),
            "unknown": 0,
        }
        for name, entry in result["packages"].items()
    }
    expect(labels_by_opening, "query study per-package labels disappeared")
    rows = study_rows(
        "rail-query-model-v1",
        predictions,
        native,
        labels_by_opening,
        {"success": 27, "no_path": 249, "unknown": 0},
    )

    expect(
        bridge["status"] == "bridge_established",
        "query study bridge is not established",
    )
    expect(
        bridge["totals"]["segment_present:checked"] == 6774
        and bridge["totals"]["node_outside:checked"] == 6750,
        "query study bridge segment counts changed",
    )
    expect(
        bridge["prediction_agreement"]["identical"] == 244
        and bridge["prediction_agreement"]["queries"] == 244,
        "query study bridge prediction agreement changed",
    )
    expect(
        bridge["prediction_disagreements"] == {},
        "query study bridge recorded a disagreement",
    )
    for name, count in bridge["prediction_agreement"]["by_package"].items():
        expect(
            count["identical"] == count["queries"],
            f"query study bridge disagreement on {name}",
        )

    counterexamples = [
        row for row in result["counterexamples"] if row["rule"] == fitted
    ]
    expect(
        len(counterexamples) == 5
        and all(row["opening"] == "pittsburgh" for row in counterexamples),
        "query study fitted counterexamples changed",
    )
    for row in counterexamples:
        expect(
            row["query_id"] in {query["id"] for query in rows},
            "query study counterexample lost its row",
        )
        expect(
            row["observation_sha256"]
            in {value["stored"]["observation_sha256"] for value in native.values()},
            "query study counterexample lost its observation binding",
        )
        expect(
            row["networks_sha256"]
            in {value["stored"]["networks_sha256"] for value in native.values()}
            and row["query_freeze_sha256"]
            in {value["stored"]["query_freeze_sha256"] for value in native.values()},
            "query study counterexample lost its network or plan binding",
        )
        expect(
            len(row["query_freeze_sha256"]) == 64 and len(row["networks_sha256"]) == 64,
            "query study counterexample lost its receipt binding",
        )

    tables = {
        rule: compact_confusion(result["rules"][rule])
        for rule in sorted(result["rules"])
    }
    groups = {
        group: {
            rule: compact_confusion(row["rules"][rule])
            for rule in ROW_RULES["rail-query-model-v1"]
            if rule in row["rules"]
        }
        for group, row in sorted(result["groups"].items())
    }
    stock_group = result["groups"]["stock_controls:stock"]["rules"]
    expect(
        stock_group[fitted]["tp"] == 16
        and stock_group[fitted]["fp"] == 0
        and stock_group[fitted]["tn"] == 16
        and stock_group[fitted]["fn"] == 0,
        "query study stock control confusion changed",
    )
    split_totals = {}
    for rule in ROW_RULES["rail-query-model-v1"]:
        stock_counts = {key: stock_group[rule][key] for key in ("tp", "fp", "tn", "fn")}
        all_counts = result["rules"][rule]
        split_totals[rule] = {
            "stock_controls": stock_counts,
            "cohort": {
                key: all_counts[key] - stock_counts[key]
                for key in ("tp", "fp", "tn", "fn")
            },
        }
    expect(
        split_totals[fitted]["cohort"] == {"tp": 10, "fp": 4, "tn": 229, "fn": 1},
        "query study cohort confusion changed",
    )
    return {
        "kind": SOURCE["rail-query-model-v1"]["kind"],
        "study": "rail-query-model-v1",
        "capability": "rail",
        "evidence_only": True,
        "certificates": "none",
        "source": SOURCE["rail-query-model-v1"],
        "review": REVIEW["rail-query-model-v1"],
        "freeze": {
            "name": "rail-query-model-v2-corrected",
            "frozen_before_observations": True,
            "supersedes": SOURCE["rail-query-model-v1"]["earlier_head"],
            "preserved_v1_artifacts": integrity["corrects"]["preserved_v1_artifacts"],
        },
        "scope": (
            "Query-scoped reachability: whether one exact selected literal Train request, between "
            "Outside positions on a saved export, is predicted to return a complete path within the "
            "100000-unit bound. Fitted retrospectively; not a place-level promise, service claim or "
            "native junction law."
        ),
        "method": METHOD["rail-query-model-v1"],
        "limits": LIMITS["rail-query-model-v1"],
        "files": evidence_files("rail-query-model-v1"),
        "closure": {
            "publication_files": len(publication["files"]),
            "copied_files": len(publication["copied"]),
            "linked_files": len(publication["linked"]),
            "commit": publication["commit"],
            "prefix": publication["prefix"],
        },
        "selection": {
            "selected_queries": 276,
            "stock_controls": 32,
            "cohort": 244,
            "exact_distinct_edge": result["exact_distinct_edge"],
            "exact_same_edge": result["exact_same_edge"],
            "labels": result["labels"],
            "openings": [
                {
                    **{
                        key: entry[key]
                        for key in (
                            "opening",
                            "split",
                            "group",
                            "label",
                            "package",
                            "raw",
                        )
                    },
                    "artifact_sha256": packages[entry["package"]]["sha256"],
                    "observation_sha256": native[entry["opening"]]["stored"][
                        "observation_sha256"
                    ],
                    "networks_sha256": native[entry["opening"]]["stored"][
                        "networks_sha256"
                    ],
                    "query_freeze_sha256": native[entry["opening"]]["stored"][
                        "query_freeze_sha256"
                    ],
                }
                for entry in openings["openings"]
            ],
            "excluded": openings["excluded"],
            "zero_query": ["charleston", "grand-canyon", "yosemite"],
            "unqueried": {
                "pittsburgh": 112,
                "note": "Pittsburgh's fixed 128-request cap left 112 candidates unqueried; they are not failures.",
            },
        },
        "rules": {
            "fitted": fitted,
            "primary": primary,
            "all": tables,
            "groups": groups,
            "split_totals": split_totals,
            "bindings": evaluation["bindings"],
        },
        "rows": rows,
        "counterexamples": counterexamples,
        "controls_summary": {"stock_controls": 2, "cohort_openings": 9},
        "runtime": {
            "export_bridge": {
                "status": bridge["status"],
                "totals": bridge["totals"],
                "prediction_agreement": bridge["prediction_agreement"],
                "leave_one_package_out": sorted(bridge["leave_one_package_out"]),
                "scope": bridge["scope"],
                "status_note": bridge["status_note"],
            }
        },
        "documents": [
            row["path"]
            for row in evidence_files("rail-query-model-v1")
            if row["path"].endswith(".md")
        ],
    }


def junction_study(
    native: dict, publication: dict, accepted: dict, query: dict
) -> dict:
    base = EVIDENCE / "rail-junction-fit-v1"
    evaluation = load_json(base / "evaluation.json")
    predictions = load_json(base / "predictions.json")
    protocol = load_json(base / "protocol.json")
    features = load_json(base / "features.json")
    diagnostics = load_json(base / "diagnostics.json")
    bridge = load_json(base / "bridge-audit.json")
    declaration = load_json(base / "manifest.json")
    expect(
        evaluation["study"] == "rail-junction-fit-v1" and evaluation["schema"] == 1,
        "junction study evaluation header changed",
    )
    expect(len(evaluation["rules"]) == 58, "junction study rule count changed")
    bindings = evaluation["bindings"]
    expect(
        sha((base / "predictions.json").read_bytes()) == bindings["predictions_sha256"],
        "junction study evaluation does not bind the carried predictions",
    )
    expect(
        sha((base / "protocol.json").read_bytes()) == bindings["protocol_sha256"],
        "junction study evaluation does not bind the carried protocol",
    )
    expect(
        sha((base / "features.json").read_bytes()) == bindings["features_sha256"],
        "junction study evaluation does not bind the carried features",
    )
    expect(
        sha((base / "manifest.json").read_bytes()) == bindings["manifest_sha256"],
        "junction study evaluation does not bind the carried declaration",
    )
    expect(
        predictions["features_sha256"] == bindings["features_sha256"]
        and predictions["protocol_sha256"] == bindings["protocol_sha256"],
        "junction study frozen predictions do not bind the same inputs",
    )
    expect(
        diagnostics["evaluation_sha256"] == sha((base / "evaluation.json").read_bytes())
        and diagnostics["predictions_sha256"] == bindings["predictions_sha256"]
        and diagnostics["protocol_sha256"] == bindings["protocol_sha256"]
        and diagnostics["features_sha256"] == bindings["features_sha256"],
        "junction study diagnostics do not bind the carried files",
    )
    for relative, digest in bindings["accepted_prefix_files"].items():
        record = accepted["files"].get(relative)
        expect(
            record is not None,
            f"junction study binds an unknown accepted file {relative}",
        )
        expect(
            record["sha256"] == digest,
            f"junction study accepted prefix hash changed: {relative}",
        )
    expect(
        declaration["source"]["accepted_head"]
        == SOURCE["rail-junction-fit-v1"]["publication_base"],
        "junction study declaration names another accepted head",
    )
    expect(
        declaration["source"]["accepted_pr"] == 81
        and declaration["source"]["native_study"]
        == SOURCE["rail-query-model-v1"]["publication_base"],
        "junction study declaration lost its sources",
    )
    expect(
        declaration["expected"]["zero_query_packages"]
        == ["charleston", "grand-canyon", "yosemite"],
        "junction study zero-query packages changed",
    )
    expect(
        features["freeze"]
        == protocol["freeze"]
        == predictions["freeze"]
        == evaluation["freeze"],
        "junction study freeze identity changed",
    )

    reference, tangent = "chord:continuation:any_lane", "tangent:continuation:any_lane"
    frozen = "frozen:junction:continuation:any_lane"

    def counts(rule):
        return evaluation["rules"][rule]["all"]["counts"]

    expect(
        (
            counts(frozen)["tp"],
            counts(frozen)["fp"],
            counts(frozen)["tn"],
            counts(frozen)["fn"],
        )
        == (26, 4, 245, 1),
        "junction study reference confusion changed",
    )
    expect(
        (
            counts(tangent)["tp"],
            counts(tangent)["fp"],
            counts(tangent)["tn"],
            counts(tangent)["fn"],
        )
        == (27, 0, 249, 0),
        "junction study tangent confusion changed",
    )
    expect(
        (
            counts(reference)["tp"],
            counts(reference)["fp"],
            counts(reference)["tn"],
            counts(reference)["fn"],
        )
        == (26, 4, 245, 1),
        "junction study chord reimplementation diverged from the reference",
    )
    expect(
        evaluation["labels"]["counts"] == {"no_path": 249, "success": 27, "unknown": 0},
        "junction study label counts changed",
    )
    expect(
        bindings["queries"] == 276
        and bindings["labelled"] == 276
        and bindings["unknown"] == 0,
        "junction study binding counts changed",
    )
    selection = evaluation["selections"]["cohort_descriptive"]
    expect(selection["rule"] == tangent, "junction study selected rule changed")
    out_of_fold = evaluation["pooled_out_of_fold"]["cohort"]
    expect(
        (
            out_of_fold["selected"]["counts"]["tp"],
            out_of_fold["selected"]["counts"]["fp"],
            out_of_fold["selected"]["counts"]["tn"],
            out_of_fold["selected"]["counts"]["fn"],
        )
        == (10, 4, 229, 1),
        "junction study selected out-of-fold confusion changed",
    )
    expect(
        (
            out_of_fold["correspondence"]["counts"]["tp"],
            out_of_fold["correspondence"]["counts"]["fp"],
            out_of_fold["correspondence"]["counts"]["tn"],
            out_of_fold["correspondence"]["counts"]["fn"],
        )
        == (11, 0, 233, 0),
        "junction study predeclared counterpart confusion changed",
    )
    expect(
        out_of_fold["selected"]["counts"] == out_of_fold["reference"]["counts"],
        "junction study grouped selection no longer ties the reference",
    )
    paired = evaluation["primary_paired"]["all"]
    expect(
        paired["rows"] == 276
        and paired["both_correct"] == 271
        and paired["right_only_correct"] == 5
        and paired["left_only_correct"] == 0
        and paired["both_wrong"] == 0
        and paired["not_comparable"] == 0,
        "junction study paired comparison changed",
    )
    cohort_folds = [
        fold
        for fold in evaluation["folds"]
        if fold["kind"] == "cohort_leave_one_package_out"
    ]
    expect(
        len(evaluation["folds"]) == 8
        and len(cohort_folds) == 6
        and sum(1 for fold in cohort_folds if fold["selected"] == tangent) == 5
        and any(
            fold["held_out"] == ["pittsburgh"] and fold["selected"] == reference
            for fold in cohort_folds
        ),
        "junction study fold selection changed",
    )
    expect(
        len(evaluation["counterexamples"][frozen]) == 5
        and evaluation["counterexamples"][tangent] == [],
        "junction study retained counterexamples changed",
    )
    expect(
        len(evaluation["candidates"]) == 55 and len(evaluation["baselines"]) == 3,
        "junction study candidate or baseline scope changed",
    )
    for rule, row in evaluation["rules"].items():
        for split in ("all", "cohort", "stock_controls"):
            counts_split = row[split]["counts"]
            expect(
                counts_split["tp"]
                + counts_split["fp"]
                + counts_split["tn"]
                + counts_split["fn"]
                + counts_split["abstain"]
                == (276 if split == "all" else 244 if split == "cohort" else 32),
                f"junction study {rule} {split} totals do not add up",
            )
    expect(
        bridge["status"] == "export_bridge_established"
        and bridge["totals"]["packages"] == 11,
        "junction study export bridge changed",
    )
    expect(
        bridge["totals"]["tangent_missing"] == 0
        and bridge["totals"]["tangent_train_segments"] == 7216,
        "junction study tangent coverage changed",
    )
    expect(
        bridge["totals"]["digests_identical"] == 11,
        "junction study model-input digests changed",
    )
    expect(
        bridge["tangents"]["native_attested"] is False,
        "junction study claims native tangents",
    )
    expect(
        bridge["accepted_prefix_hashes"]["corrected/evaluation.json"]
        == accepted["files"]["corrected/evaluation.json"]["sha256"],
        "junction study bridge names another accepted evaluation",
    )

    labels_by_opening = {
        opening: {
            "success": counts["success"],
            "no_path": counts["no_path"],
            "unknown": counts["unknown"],
        }
        for opening, counts in evaluation["labels"]["per_opening"].items()
    }
    rows = study_rows(
        "rail-junction-fit-v1",
        predictions,
        native,
        labels_by_opening,
        {"success": 27, "no_path": 249, "unknown": 0},
    )
    expect(
        {row["id"] for row in rows} == {row["id"] for row in query["rows"]},
        "junction study and query study select different requests",
    )

    tables = {}
    for rule, row in sorted(evaluation["rules"].items()):
        tables[rule] = {
            split: compact_confusion(row[split]["counts"] | row[split]["rates"])
            for split in ("all", "cohort", "stock_controls")
        }
        tables[rule]["openings"] = {
            opening: compact_confusion(value["counts"] | value["rates"])
            for opening, value in evaluation["rules"][rule]["openings"].items()
        }
    return {
        "kind": SOURCE["rail-junction-fit-v1"]["kind"],
        "study": "rail-junction-fit-v1",
        "capability": "rail",
        "evidence_only": True,
        "certificates": "none",
        "source": SOURCE["rail-junction-fit-v1"],
        "review": REVIEW["rail-junction-fit-v1"],
        "freeze": {
            "name": protocol["freeze"],
            "frozen_before_observations": True,
            "accepted_prefix": accepted["prefix"],
            "frozen_rules": len(protocol["rules"]),
        },
        "scope": (
            "Export-tangent junction pairing: whether the straightest continuation measured from each "
            "segment's authored endpoint tangents pairs the lanes the game used. Export-derived "
            "hypothesis, fitted retrospectively; not native-attested and not a ruleset for product use."
        ),
        "method": METHOD["rail-junction-fit-v1"],
        "limits": LIMITS["rail-junction-fit-v1"],
        "files": evidence_files("rail-junction-fit-v1"),
        "closure": {
            "publication_files": len(publication["files"]),
            "copied_files": len(publication["copied"]),
            "linked_files": len(publication["linked"]),
            "commit": publication["commit"],
            "prefix": publication["prefix"],
        },
        "selection": {
            "selected_queries": 276,
            "stock_controls": 32,
            "cohort": 244,
            "labels": evaluation["labels"]["counts"],
            "zero_query": evaluation["groups"]["zero_query"],
            "excluded": [
                {
                    "opening": "rio-queue-denial",
                    "reason": "fair-queue denial before launch; retained, not predicted",
                }
            ],
            "unqueried": {
                "pittsburgh": 112,
                "note": "Pittsburgh's 112 unqueried candidates stay unqueried and are not failures.",
            },
            "folds": evaluation["folds"],
            "openings": [dict(entry) for entry in query["selection"]["openings"]],
        },
        "rules": {
            "reference": frozen,
            "chord_reimplementation": reference,
            "fitted": tangent,
            "predeclared_counterpart": "tangent:continuation:orientation_index",
            "all": tables,
            "selection": selection,
            "pooled_out_of_fold": evaluation["pooled_out_of_fold"],
            "paired": evaluation["primary_paired"],
            "bindings": {
                key: value for key, value in bindings.items() if key != "openings"
            },
        },
        "rows": rows,
        "counterexamples": {frozen: evaluation["counterexamples"][frozen], tangent: []},
        "runtime": {
            "export_bridge": {
                "status": bridge["status"],
                "totals": bridge["totals"],
                "tangents": bridge["tangents"],
                "precision": bridge["precision"],
                "accepted_head": bridge["accepted_head"],
            }
        },
        "documents": [
            row["path"]
            for row in evidence_files("rail-junction-fit-v1")
            if row["path"].endswith(".md")
        ],
    }


def stock_study(native: dict, publication: dict) -> dict:
    base = EVIDENCE / "rail-stock-holdout-v1"
    freeze = load_json(base / "freeze.json")
    evaluation = load_json(base / "evaluation.json")
    verification = load_json(base / "native-verification.json")
    raw_integrity = load_json(base / "raw-integrity.json")
    selection_power = load_json(base / "selection-power.json")
    build = load_json(base / "metadata-build.json")
    facts = load_json(base / "public-prefab-facts.json")
    journal = load_json(base / "resource-journal.json")
    deferred = load_json(base / "collection-deferred.json")
    metadata = (base / "RailMetadata.cs").read_text()
    expect(
        freeze["schema"] == 1
        and freeze["protocol"]["id"] == "PL-1239-stock-holdout-v1",
        "stock study freeze header changed",
    )
    expect(
        sha((base / "freeze.json").read_bytes())
        == "20dfb33d863deb4fd13abcbeb952a59e139f93910216771c74fd21c069935a18",
        "stock study freeze bytes changed",
    )
    expect(
        evaluation["freeze_sha256"] == sha((base / "freeze.json").read_bytes()),
        "stock study evaluation does not bind the carried freeze",
    )
    expect(
        raw_integrity["freeze_sha256"] == evaluation["freeze_sha256"],
        "stock study raw integrity names another freeze",
    )
    expect(
        selection_power["freeze_sha256"] == evaluation["freeze_sha256"],
        "stock study selection power names another freeze",
    )
    expect(
        freeze["frozen_at"] == "2026-11-21T21:51:01.430026+00:00",
        "stock study freeze timestamp changed",
    )
    expect(
        freeze["discordant_predictions"] == 0,
        "stock study freeze recorded a discordant prediction",
    )
    expect(
        len(freeze["query_ids"]) == 48 and len(freeze["predictions"]) == 48,
        "stock study freeze query set changed",
    )
    expect(
        len(freeze["selected"]) == 10
        and len(freeze["inventory"]) == 105
        and len(freeze["excluded_hashes"]) == 11,
        "stock study selection scope changed",
    )
    expect(
        freeze["protocol"]["rules"]
        == ["tangent:continuation:any_lane", "chord:continuation:any_lane"],
        "stock study rule pair changed",
    )
    expect(
        freeze["strata"]["pair_difference"]["selected"] == 2
        and freeze["strata"]["no_pair_difference"]["selected"] == 4
        and freeze["strata"]["unsupported_or_no_pair"]["selected"] == 4,
        "stock study strata changed",
    )
    expect(
        freeze["source"] == SOURCE["rail-stock-holdout-v1"]["publication_base"],
        "stock study freeze names another source pin",
    )

    expect(
        evaluation["controls_valid"] is True and evaluation["counterexamples"] == [],
        "stock study control gate or counterexample list changed",
    )
    expect(
        len(evaluation["rows"]) == 48 and len(evaluation["packages"]) == 10,
        "stock study scored rows changed",
    )
    tables = evaluation["tables"]
    expect(
        list(tables) == ["all-complete intent-to-test", "snapshot-matched"],
        "stock study tables changed",
    )
    for name, table in tables.items():
        for rule in ("tangent:continuation:any_lane", "chord:continuation:any_lane"):
            all_counts = table["all"][rule]
            expect(
                (all_counts["tp"], all_counts["fp"], all_counts["tn"], all_counts["fn"])
                == (40, 0, 8, 0),
                f"stock study {name} {rule} confusion changed",
            )
            expect(
                all_counts["requests"] == 48
                and all_counts["unknown"] == 0
                and all_counts["abstain"] == 0,
                f"stock study {name} {rule} coverage changed",
            )
    labels = {"success": 0, "no_path": 0, "unknown": 0}
    for row in evaluation["rows"]:
        expect(
            row["snapshot_matched"] is True, "stock study lost a snapshot-matched row"
        )
        labels[row["label"]] = labels.get(row["label"], 0) + 1
        expect(
            row["predictions"]["tangent:continuation:any_lane"]["prediction"]
            == row["predictions"]["chord:continuation:any_lane"]["prediction"],
            "stock study rules disagree on a request",
        )
    expect(
        labels == {"success": 40, "no_path": 8, "unknown": 0},
        "stock study row labels changed",
    )
    frozen_by_id = {row["id"]: row for row in freeze["predictions"]}
    expect(
        set(frozen_by_id) == {row["id"] for row in evaluation["rows"]},
        "stock study frozen queries do not match the scored rows",
    )
    for row in evaluation["rows"]:
        expect(
            row["predictions"] == frozen_by_id[row["id"]]["predictions"],
            "stock study scored a prediction other than the frozen one",
        )
    failures = [row for row in evaluation["rows"] if row["label"] == "no_path"]
    expect(
        len(failures) == 8 and {row["slug"] for row in failures} == {"holdout-02"},
        "stock study failures are no longer one package",
    )
    supported = [
        package
        for package, record in evaluation["packages"].items()
        if record["supported"]
    ]
    expect(len(supported) == 6, "stock study supported-package count changed")
    supported_train_segments = 0
    for package in supported:
        opening_audit = evaluation["packages"][package]["audit"]["opening"]
        post_audit = evaluation["packages"][package]["audit"]["post"]
        expect(
            opening_audit["mismatches"] == [] and post_audit["mismatches"] == [],
            f"stock study supported package lost its clean field audit: {package}",
        )
        checked = opening_audit["fields"]["id:checked"]
        expect(
            post_audit["fields"]["id:checked"] == checked,
            f"stock study supported package changed its checked segment count: {package}",
        )
        supported_train_segments += checked
    expect(
        supported_train_segments == 1277,
        "stock study supported Train segment count changed",
    )
    unsupported = [
        package
        for package, record in evaluation["packages"].items()
        if not record["supported"]
    ]
    expect(
        len(unsupported) == 4
        and all(
            evaluation["packages"][package]["selected_requests"] == 0
            for package in unsupported
        ),
        "stock study unsupported packages gained requests",
    )
    expect(
        sorted(
            len(evaluation["packages"][package]["audit"]["opening"]["mismatches"])
            for package in unsupported
        )
        == [6, 8, 14, 44],
        "stock study unsupported mismatch counts changed",
    )
    for package, record in evaluation["packages"].items():
        expect(
            record["cleanup"]
            == {"game": [], "steam_instances": [], "units_active": []},
            f"stock study {package} cleanup is not empty",
        )
        expect(
            record["context_bound"] is True and record["error"] is None,
            f"stock study {package} lost context",
        )
    expect(
        len(verification["openings"]) == 12 and verification["verified_requests"] == 48,
        "stock study native verification counts changed",
    )
    expect(
        {entry["slug"] for entry in verification["openings"]}
        == {"stock-1", "stock-2"} | {f"holdout-{index:02d}" for index in range(1, 11)},
        "stock study native verification openings changed",
    )
    for entry in verification["openings"]:
        expect(
            entry["graph_opening_post_equal"] is True
            and entry["cleanup"]
            == {"game": [], "steam_instances": [], "units_active": []},
            f"stock study native verification lost {entry['slug']}",
        )
        expect(
            isinstance(entry["host_pid"], int) and entry["process_start_ticks"],
            f"stock study native verification lost the process identity for {entry['slug']}",
        )
    for rule, counts in verification["independent_counts"].items():
        expect(
            counts == {"tp": 40, "tn": 8},
            f"stock study independent counts changed for {rule}",
        )
    for slug, control in evaluation["controls"].items():
        expect(
            control["cleanup"]
            == {"game": [], "steam_instances": [], "units_active": []},
            f"stock study control {slug} cleanup is not empty",
        )
        expect(
            control["context_bound"] is True, f"stock study control {slug} lost context"
        )
        boundary = [
            path
            for path in control["paths"]
            if path["request"]["position_kind"] == "boundary"
            and path["request"]["diagnostic"] is False
        ]
        invalid = [
            path
            for path in control["paths"]
            if path["request"]["name"] == "invalid-train-to-car-lane"
        ]
        expect(
            invalid and invalid[-1]["result"]["success"] is False,
            f"stock study control {slug} lost its invalid-pair diagnostic",
        )
        successes = sum(1 for path in boundary if path["result"]["success"] is True)
        expect(
            (slug, successes, len(boundary)) in (("stock-1", 8, 8), ("stock-2", 8, 24)),
            f"stock study control {slug} counts changed",
        )

    raw_files = raw_integrity["files"]
    expect(len(raw_files) == 136, "stock study retained raw file count changed")
    expect(
        raw_integrity["primary_raw"] == "raw/attempt-2",
        "stock study primary raw batch changed",
    )
    for relative, record in raw_files.items():
        published = publication["files"].get(relative)
        expect(
            published is not None,
            f"stock study raw file outside the publication: {relative}",
        )
        expect(
            published["sha256"] == record["stored_sha256"]
            and published["bytes"] == record["stored_bytes"],
            f"stock study raw integrity differs from the publication: {relative}",
        )
        expect(
            record["original_bytes"] >= 0 and len(record["original_sha256"]) == 64,
            f"stock study raw integrity lost the original digest: {relative}",
        )
        if relative.startswith("raw/attempt-2/"):
            expect(
                record["original_bytes"] > 0,
                f"stock study primary raw file is empty: {relative}",
            )
        expect(
            not (base / relative).exists(),
            f"stock study raw file must be linked, not carried: {relative}",
        )
    expect(
        raw_integrity["earlier_denial"] in raw_files
        or raw_integrity["earlier_denial"] == "raw/stock-1/observation.json.gz",
        "stock study earlier denial lost",
    )
    expect(
        deferred["freeze_sha256"] == evaluation["freeze_sha256"]
        and deferred["owned_native_launches"] == 0
        and deferred["cleanup_identity"] is None,
        "stock study earlier slot denial changed",
    )

    expect(
        build["build_receipt"]["dll_sha256"]
        == "7185c630657cdf480c2ed62be3830bb545a8b45e34cedb455375fa8fffe46357",
        "stock study build receipt changed",
    )
    expect(len(facts["prefabs"]) == 7, "stock study public prefab facts changed")
    for name, entries in facts["prefabs"].items():
        expect(
            len(entries) == 1
            and entries[0]["prefab_max_turn_angle"] == 45
            and entries[0]["override_direction_limit"] is None,
            f"stock study turn-angle fact changed: {name}",
        )
    expect(
        "BindingFlags.Instance | BindingFlags.Public" in metadata
        and "NonPublic" not in metadata,
        "stock study metadata reader no longer reads public fields only",
    )
    expect(
        len(journal["openings"]) == 12 and journal["host"] == "blade",
        "stock study resource journal changed",
    )

    rows = [
        {
            "id": row["id"],
            "opening": row["slug"],
            "package": row["slug"],
            "group": row["stratum"],
            "plan_index": int(row["id"].rsplit(":", 1)[1]),
            "request": row["request"],
            "observed": row["label"],
            "observed_reason": row["observation"]["result"].get("reason")
            if isinstance(row["observation"].get("result"), dict)
            else None,
            "observed_flags": row["observation"]["result"].get("flags"),
            "observed_length": row["observation"]["result"].get("length"),
            "predicted": {
                rule: row["predictions"][rule]["prediction"]
                for rule in ROW_RULES["rail-stock-holdout-v1"]
            },
            "snapshot_matched": row["snapshot_matched"],
            "stratum": row["stratum"],
            "path_audit": row["path_audit"],
        }
        for row in evaluation["rows"]
    ]

    per_package = {}
    for package, record in sorted(evaluation["packages"].items()):
        package_rows = [row for row in rows if row["package"] == package]
        per_package[package] = {
            "file": record["file"],
            "stratum": record["stratum"],
            "supported": record["supported"],
            "state": record["state"],
            "selected_requests": record["selected_requests"],
            "raw_sha256": record["raw_sha256"],
            "context_bound": record["context_bound"],
            "success": sum(1 for row in package_rows if row["observed"] == "success"),
            "no_path": sum(1 for row in package_rows if row["observed"] == "no_path"),
            "unknown": sum(1 for row in package_rows if row["observed"] == "unknown"),
            "audit": record["audit"],
        }
    strata = {}
    for name in freeze["strata"]:
        selected = [
            package
            for package, record in per_package.items()
            if record["stratum"] == name
        ]
        strata[name] = {
            **freeze["strata"][name],
            "packages": selected,
            "requests": sum(
                per_package[package]["selected_requests"] for package in selected
            ),
            "success": sum(per_package[package]["success"] for package in selected),
            "no_path": sum(per_package[package]["no_path"] for package in selected),
        }
    return {
        "kind": SOURCE["rail-stock-holdout-v1"]["kind"],
        "study": "rail-stock-holdout-v1",
        "capability": "rail",
        "evidence_only": True,
        "certificates": "none",
        "source": SOURCE["rail-stock-holdout-v1"],
        "review": REVIEW["rail-stock-holdout-v1"],
        "freeze": {
            "name": "PL-1239-stock-holdout-v1",
            "sha256": sha((base / "freeze.json").read_bytes()),
            "frozen_at": freeze["frozen_at"],
            "frozen_before_observations": True,
            "source_pin": freeze["source"],
            "query_source": freeze["query_source"],
            "native_source": freeze["native_source"],
            "discordant_predictions": freeze["discordant_predictions"],
        },
        "scope": (
            "Frozen stock-package holdout: whether each frozen rule predicts the exact selected literal "
            "Train request result on packages selected before any new query. Request-scoped, not "
            "geographic prevalence, service, a junction law or a product promise."
        ),
        "method": METHOD["rail-stock-holdout-v1"],
        "limits": LIMITS["rail-stock-holdout-v1"],
        "files": evidence_files("rail-stock-holdout-v1"),
        "closure": {
            "publication_files": len(publication["files"]),
            "copied_files": len(publication["copied"]),
            "linked_files": len(publication["linked"]),
            "commit": publication["commit"],
            "prefix": publication["prefix"],
        },
        "selection": {
            "selected_queries": 48,
            "package_count": 10,
            "supported_packages": len(supported),
            "unsupported_packages": len(unsupported),
            "inventory": len(freeze["inventory"]),
            "selected_packages": [
                {
                    "file": entry["file"],
                    "stratum": entry["stratum"],
                    "crp_sha256": entry["lineage"]["crp_sha256"],
                    "bytes": entry["bytes"],
                    "locator": entry["locator"],
                }
                for entry in freeze["selected"]
            ],
            "excluded_hashes": freeze["excluded_hashes"],
            "strata": strata,
            "freeze_schema": freeze["protocol"],
            "unqueried": {"note": freeze["protocol"]["selection"]},
            "zero_query": [
                package
                for package, record in per_package.items()
                if record["selected_requests"] == 0
            ],
        },
        "rules": {
            "rules": freeze["protocol"]["rules"],
            "identical_predictions": 48,
            "discordant_predictions": freeze["discordant_predictions"],
            "tables": {
                name: {
                    "all": {
                        rule: compact_confusion(table["all"][rule])
                        for rule in table["all"]
                        if rule in freeze["protocol"]["rules"]
                    },
                    "packages": {
                        package.split(":", 1)[1]: {
                            rule: compact_confusion(package_table[rule])
                            for rule in package_table
                            if rule in freeze["protocol"]["rules"]
                        }
                        for package, package_table in table.items()
                        if package.startswith("package:")
                    },
                    "strata": {
                        stratum.split(":", 1)[1]: {
                            rule: compact_confusion(stratum_table[rule])
                            for rule in stratum_table
                            if rule in freeze["protocol"]["rules"]
                        }
                        for stratum, stratum_table in table.items()
                        if stratum.startswith("stratum:")
                    },
                }
                for name, table in tables.items()
            },
            "labels": labels,
        },
        "rows": rows,
        "controls": [
            {
                "slug": slug,
                "state": control["state"],
                "context_bound": control["context_bound"],
                "cleanup": control["cleanup"],
                "boundary_successes": sum(
                    1
                    for path in control["paths"]
                    if path["request"]["diagnostic"] is False
                    and path["request"]["position_kind"] == "boundary"
                    and path["result"]["success"] is True
                ),
                "boundary_requests": sum(
                    1
                    for path in control["paths"]
                    if path["request"]["diagnostic"] is False
                    and path["request"]["position_kind"] == "boundary"
                ),
                "invalid_pair_rejected": any(
                    path["request"]["name"] == "invalid-train-to-car-lane"
                    and path["result"]["success"] is False
                    for path in control["paths"]
                ),
            }
            for slug, control in evaluation["controls"].items()
        ],
        "runtime": {
            "native_verification": verification,
            "build": {
                "dll_sha256": build["build_receipt"]["dll_sha256"],
                "game_executable_sha256": build["build_receipt"][
                    "game_executable_sha256"
                ],
                "sources": len(build["build_receipt"]["sources"]),
                "game_assemblies": len(build["build_receipt"]["game_assemblies"]),
            },
            "public_prefab_facts": facts,
            "field_audit": {
                "supported_packages": supported,
                "supported_train_segments": supported_train_segments,
                "supported_mismatches": {
                    package: {
                        "opening": len(
                            evaluation["packages"][package]["audit"]["opening"][
                                "mismatches"
                            ]
                        ),
                        "post": len(
                            evaluation["packages"][package]["audit"]["post"][
                                "mismatches"
                            ]
                        ),
                    }
                    for package in supported
                },
                "unsupported": [
                    {
                        "package": package,
                        "opening_mismatches": len(
                            evaluation["packages"][package]["audit"]["opening"][
                                "mismatches"
                            ]
                        ),
                        "post_mismatches": len(
                            evaluation["packages"][package]["audit"]["post"][
                                "mismatches"
                            ]
                        ),
                        "supported": evaluation["packages"][package]["supported"],
                    }
                    for package in unsupported
                ],
                "transition_audit": {
                    "successful_paths": 40,
                    "distinct_segment_transitions": 8336,
                    "rejected_pairs": 0,
                },
            },
            "raw_retention": {
                "files": len(raw_files),
                "primary_raw": raw_integrity["primary_raw"],
                "earlier_denial": raw_integrity["earlier_denial"],
                "positions": "raw file bytes are served as immutable Git blobs and cross-checked against raw-integrity.json",
            },
            "resource_journal": journal,
            "collection_deferred": deferred,
            "metadata_reader": {
                "file": "tools/map-factory/capability-evidence/rail-stock-holdout-v1/RailMetadata.cs",
                "public_fields_only": True,
                "proprietary_source": False,
            },
        },
        "documents": [
            row["path"]
            for row in evidence_files("rail-stock-holdout-v1")
            if row["path"].endswith(".md")
        ],
    }


def build_projection() -> dict:
    closure, publications = source_manifest()
    native = opening_native()
    query = query_study(native, publications["rail-query-model-v1"])
    junction = junction_study(
        native,
        publications["rail-junction-fit-v1"],
        publications["rail-query-model-v1"],
        query,
    )
    stock = stock_study(native, publications["rail-stock-holdout-v1"])
    for study in (query, junction, stock):
        expect(
            study["closure"]["publication_files"]
            == EXPECTED_PUBLICATION_FILES[study["study"]][0]
            and study["closure"]["copied_files"]
            == EXPECTED_PUBLICATION_FILES[study["study"]][1]
            and study["closure"]["linked_files"]
            == EXPECTED_PUBLICATION_FILES[study["study"]][2],
            f"{study['study']}: closure counts changed",
        )
    for study in (query, junction, stock):
        study["checks"] = [
            f"{study['closure']['publication_files']} publication files: "
            f"{study['closure']['copied_files']} carried byte for byte here, {study['closure']['linked_files']} served as immutable Git blobs.",
            "Every carried file's SHA-256 matches its publication record; linked files are absent here and pinned by SHA-256 and Git blob id.",
            "Rows below are joined from the frozen predictions and the retained native observation at the same plan index; the joined label totals equal the archived evaluation.",
        ]
    return {
        "schema": 1,
        "note": (
            "Three accepted rail research publications as distinct typed evidence studies. They are not "
            "pooled with directed-rail-v3, they are not promises or certificates, and no research code "
            "runs as a product check."
        ),
        "source_manifest": closure,
        "studies": {
            "rail-query-model-v1": query,
            "rail-junction-fit-v1": junction,
            "rail-stock-holdout-v1": stock,
        },
    }


def main() -> int:
    projection = build_projection()
    raw = (json.dumps(projection, indent=1, sort_keys=False) + "\n").encode()
    target = ROOT / PROJECTION_FILE
    if "--check" in sys.argv:
        if not target.is_file() or target.read_bytes() != raw:
            print(
                "rail research projection is stale; rerun integrate_rail_research.py",
                file=sys.stderr,
            )
            return 1
        print(f"rail research projection is current: {sha(raw)}")
        return 0
    target.write_bytes(raw)
    print(f"wrote {PROJECTION_FILE} ({len(raw)} bytes, {sha(raw)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
