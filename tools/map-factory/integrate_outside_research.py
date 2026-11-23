"""Integrate the accepted outside-connection query-model publication as one typed study.

This reads archived bytes only. It never runs the study's model, predictor,
collector, scorer, a native game or a browser. It re-checks the publication's
file scope, hash bindings, semantic protocol, source keys, collector identity,
package lineage, raw-record counts and derived tables, then writes one projection
the ledger page renders under Road, Ship and Air.

The study is evidence only: not pooled with the native outside-v1/v2 studies,
not a promise, not a certificate, not a live rule and not a native observation.

Two modes:

    python3 tools/map-factory/integrate_outside_research.py --source <dir>
        Derive the manifest and projection from an exact checkout of the
        publication's 21 files, e.g.
        `git archive <commit> -- <prefix> | tar -x -C <dir>`.

    python3 tools/map-factory/integrate_outside_research.py --check
        Re-check the committed manifest, projection and every carried byte
        against every declaration the publication itself carries.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tools/map-factory/capability-evidence"
STUDY = "outside-query-model-v1"
PREFIX = f"tools/map-factory/capability-evidence/{STUDY}"
MANIFEST_FILE = "tools/map-factory/capability-evidence/outside-research-sources.json"
PROJECTION_FILE = "tools/map-factory/capability-evidence/outside-research-studies.json"

MODES = ("road", "ship", "air")
STRATA = (
    "primary_distinct_edge",
    "same_edge",
    "midpoint_diagnostic",
    "unclassified_protocol",
    "archived_player_run",
    "unrequested",
)

PUBLICATION = {
    "study": STUDY,
    "kind": "outside_connection_query_model_study",
    "title": "Query-scoped outside-connection reachability model",
    "publication_commit": "030db86ce470b972b6ef3462a2698744dff40ebb",
    "publication_base": "49cf49516f4aa8b24a154d9923c1a6fd149bf1a3",
    "accepted_base": "49cf49516f4aa8b24a154d9923c1a6fd149bf1a3",
    "internal_merge": "f6c73b17a9b211c6887ede23d313545caac3735b",
    "pull_request": 87,
    "branch": "PL-1249-outside-models",
    "source_issue": "01a2006b-105d-7bc7-af9e-c3e42ea9c944",
    "review_pass": "01a207a7-3557-7ba2-b3ef-aa8dd579bfdf",
    "engineering_note": "01a207a8-9578-7079-8bc1-f7e262d798ef",
    "parent_acceptance": "01a20819-0135-77a7-ba31-17c1b2808581",
    "native_sources": {
        "outside_v1": "4cef6fb620f403c603e597a46f3bb7d7e5feadb7",
        "targeted_v2": "29b095475ba2f93c7e918fefc08c736493670304",
    },
}

# The exact files carried in this repository, byte for byte. The three bulk
# source documents stay at their publication commit: the frozen requests, the
# frozen predictions and the retained inventory.
COPIES = {
    "README.md": "document",
    "REPRODUCE.md": "document",
    "RESULTS.md": "document",
    "bindings.json": "provenance",
    "bridge.json": "audit",
    "bridge.py": "tool",
    "catalogs.json": "audit",
    "evaluate.py": "tool",
    "evaluation.json": "metrics",
    "integrity.json": "provenance",
    "inventory.py": "tool",
    "manifest.json": "provenance",
    "model.py": "tool",
    "packages.json": "provenance",
    "predict.py": "tool",
    "protocol.json": "protocol",
    "test_outside_query_model.py": "tool",
    "topology.py": "tool",
}

LINKED = {
    "inventory.json": "retained_inventory",
    "predictions.json": "frozen_predictions",
    "requests.json": "frozen_requests",
}

DOCUMENTS = ("README.md", "REPRODUCE.md", "RESULTS.md")

EXPECTED_PUBLICATION_FILES = 21

# The exact frozen key sets the publication itself declares in bindings.json and
# integrity.json. A new or missing entry there is a changed publication.
FROZEN_SOURCE_FILES = {
    "bridge.json",
    "bridge.py",
    "catalogs.json",
    "inventory.json",
    "inventory.py",
    "manifest.json",
    "model.py",
    "packages.json",
    "predict.py",
    "predictions.json",
    "requests.json",
    "topology.py",
}
FROZEN_DIGEST_FILES = {
    "bindings.json",
    "bridge.json",
    "catalogs.json",
    "evaluate.py",
    "evaluation.json",
    "inventory.json",
    "manifest.json",
    "packages.json",
    "predictions.json",
    "protocol.json",
    "requests.json",
}
PROTOCOL_SOURCES = {"catalogs", "evidence", "inventory", "packages", "requests"}

COLLECTOR = {
    "path": "tools/cs1-harness/mod/NetworkOps.cs",
    "revision": "29b095475ba2f93c7e918fefc08c736493670304",
    "sha256": "d644218e8969f40737ce08367a3a3e4c9adb6a550ba145fb3bf220ffa5f23813",
}
# Every opening's actual collector build and the DLL that build produced. The
# source of that collector is pinned above and asserted per opening by the
# publication itself (`opening_protocol_source_<slug>_<attempt>`).
EXPECTED_BUILDS = {
    (
        "e3488f300e8797fd2e92dfb182e7c55988a1831d57d8a97908f74d3a7952a6f6",
        "f760887856abe15232f221a8419f9e0b84c19fb2a9a3adb937844f7945b301f1",
    ): 2,
    (
        "d5a40930097dd7482fc71e9124a632c42a4c82a67a682c981cb05aafcac3d358",
        "f760887856abe15232f221a8419f9e0b84c19fb2a9a3adb937844f7945b301f1",
    ): 8,
    (
        "a1c774edbe768a9d4168aa1df429f0996538c18d9808daecc837c5755c0e1def",
        "861811c03026cdd86e559a94bba91aeedea4882963a79605734338e4881e38a7",
    ): 5,
    ("a1c774edbe768a9d4168aa1df429f0996538c18d9808daecc837c5755c0e1def", None): 1,
    (
        "818e6a12d15fb0a90bd7c3155a2199d942c01ebb744888a03ebfb5f9d5797df1",
        "083c91197fb0f20d5ef69eb230b26547cd50d15b6e1846153c9f2293d0f73fa5",
    ): 1,
}

# The corrected actual protocol this evidence was collected under. The older
# `All`-for-road statement is not used anywhere below.
EXPECTED_DOMAIN = {
    "mode_vehicle": {"road": "Car", "ship": "Ship", "air": "Plane"},
    "category_by_mode": {"road": "PassengerCar", "ship": "All", "air": "All"},
    "accepted_lane_types": {
        "road": ["Vehicle"],
        "ship": ["CargoVehicle", "TransportVehicle", "Vehicle"],
        "air": ["CargoVehicle", "TransportVehicle", "Vehicle"],
    },
    "max_length": 100000.0,
}
PROTOCOL_TEXT = (
    "seed 857",
    "maxLength 100000",
    "PassengerCar",
    "Vehicle|TransportVehicle|CargoVehicle",
    "Car/Ship/Plane",
)

RULES = [
    "always_fail",
    "always_candidate",
    "weak_component",
    "directed_segment",
    "lane:any_lane:forbidden",
    "lane:any_lane:allowed",
    "lane:index_same:forbidden",
    "lane:index_same:allowed",
    "lane:index_mirror:forbidden",
    "lane:orientation_index:forbidden",
    "lane:orientation_index:allowed",
    "lane:orientation_mirror:forbidden",
]
BASELINES = ["always_fail", "always_candidate", "weak_component", "directed_segment"]
PRIMARY_RULE = "lane:any_lane:forbidden"
FITTED_RULE = "directed_segment"

PACKAGE_NAMES = (
    "asheville",
    "boston",
    "charleston",
    "grand-canyon",
    "hong-kong",
    "innsbruck",
    "pittsburgh",
    "rio",
    "yosemite",
)

PRIMARY_ROWS = 342
SAME_EDGE_ROWS = 36

# The exact counts the retained inventory, its manifest and its integrity record
# all carry. They are three copies of one classification.
EXPECTED_COUNTS = {
    "queries": 876,
    "eligible": 378,
    "openings": 17,
    "anomalies": 3,
    "midpoint_agree": 378,
    "midpoint_pairs": 378,
    "by_stratum": {
        "archived_player_run": 28,
        "midpoint_diagnostic": 378,
        "primary_distinct_edge": 342,
        "same_edge": 36,
        "unclassified_protocol": 64,
        "unrequested": 28,
    },
    "by_exclusion": {
        "midpoint_diagnostic_unscored": 378,
        "no_request_recorded": 28,
        "player_construction_not_unchanged_map": 28,
        "protocol_fields_absent": 64,
    },
    "by_mode": {"air": 33, "road": 802, "ship": 41},
    "eligible_by_mode": {"air": 10, "road": 352, "ship": 16},
    "eligible_by_stratum": {"primary_distinct_edge": 342, "same_edge": 36},
    "labels": {"False": 276, "True": 102},
    "labels_by_mode": {
        "air": {"True": 10},
        "road": {"False": 276, "True": 76},
        "ship": {"True": 16},
    },
}

EXPECTED_MODES = {
    "road": {"primary": 316, "fitted": (67, 19, 230, 0), "estimable": True},
    "ship": {"primary": 16, "fitted": (16, 0, 0, 0), "estimable": False},
    "air": {"primary": 10, "fitted": (10, 0, 0, 0), "estimable": False},
}

EXPECTED_GROUPS = {
    "PL-1121 first openings": {
        "n": 114,
        "tp": 27,
        "fp": 0,
        "tn": 87,
        "fn": 0,
        "fidelity": "collector-recipe-only",
    },
    "PL-1142 targeted openings": {
        "n": 264,
        "tp": 75,
        "fp": 19,
        "tn": 170,
        "fn": 0,
        "fidelity": "runtime-bound",
    },
}
EXPECTED_PACKAGES = {
    "asheville": {"n": 20, "tp": 2, "fp": 0, "tn": 18, "fn": 0},
    "boston": {"n": 24, "tp": 6, "fp": 0, "tn": 18, "fn": 0},
    "charleston": {"n": 24, "tp": 6, "fp": 0, "tn": 18, "fn": 0},
    "hong-kong": {"n": 102, "tp": 11, "fp": 6, "tn": 85, "fn": 0},
    "pittsburgh": {"n": 148, "tp": 53, "fp": 13, "tn": 82, "fn": 0},
    "rio": {"n": 24, "tp": 15, "fp": 0, "tn": 9, "fn": 0},
}

BRIDGE_TOTALS = {
    "segments_native": 27191,
    "nodes_native": 26633,
    "segments_built": 27191,
    "nodes_built": 26633,
    "start_end_equal": 27191,
    "prefab_equal": 27191,
    "lanes_equal": 27191,
    "invert_equal": 27191,
    "chords_equal_within_2pct": 27136,
    "chords_equal_within_20pct": 27191,
    "positions_within_tolerance": 25993,
    "outside_nodes_equal": 26633,
    "node_flags_differ_count": 1213,
    "node_flags_differ_outside_disagreements": 0,
}

DISAGREEMENT_IDS = [
    "hong-kong/native-v2-5/road/013",
    "hong-kong/native-v2-5/road/021",
    "hong-kong/native-v2-5/road/061",
    "hong-kong/native-v2-5/road/069",
    "hong-kong/native-v2-5/road/085",
    "hong-kong/native-v2-5/road/093",
    "pittsburgh/native-v2-6/road/015",
    "pittsburgh/native-v2-6/road/037",
    "pittsburgh/native-v2-6/road/071",
    "pittsburgh/native-v2-6/road/093",
    "pittsburgh/native-v2-6/road/127",
    "pittsburgh/native-v2-6/road/151",
    "pittsburgh/native-v2-6/road/161",
    "pittsburgh/native-v2-6/road/179",
    "pittsburgh/native-v2-6/road/183",
    "pittsburgh/native-v2-6/road/187",
    "pittsburgh/native-v2-6/road/201",
    "pittsburgh/native-v2-6/road/205",
    "pittsburgh/native-v2-6/road/209",
]

SCOPE = (
    "One retrospective, query-scoped question on the accepted outside-v1 native study and its targeted "
    "repeat: given one literal-boundary outside-connection request, does the native pathfinder return a "
    "complete path whose first and last positions equal the requested offsets? The model reads only the "
    "saved pre-query network. The observations already existed before this model; nothing here is "
    "prospective, blind or a new capture."
)

METHOD = (
    "The accepted study classified 876 retained road, ship and air native path rows and scored the 378 "
    "literal boundary requests among them against a frozen family of 12 reachability rules per mode, with "
    "lane:any_lane:forbidden registered as primary and a leave-one-package-out selection over the six "
    "packages that carry a primary request. A read-only bridge re-derived every field the model reads from "
    "the nine unchanged .crp packages. This ledger re-checks the archived bytes, re-derives every table "
    "from the preserved request rows and refuses a changed binding. No scorer, predictor or native run is "
    "repeated."
)

LIMITS = (
    "Retrospective and query-scoped on one observed cohort: not blind or global accuracy, not a random "
    "sample of geography, and not geographic impossibility of any mode. A selected request failure labels "
    "only that exact query under that exact protocol; it never establishes that a place cannot support a "
    "road, harbour or airport, that a service exists, or that a player will see one. The 19 road false "
    "positives all sit in two targeted second openings, all return flags=8 and length=100000, and all "
    "remain unexplained: a retained sentinel is not proof that a search budget was exhausted. Chord length "
    "is not a native cost, grade, width, water depth or SI conversion, and no native threshold was fitted. "
    "Ship and air retain one class only, so their arithmetic precision of 1 carries no information and no "
    "rule can be distinguished on them. Midpoint repeats, direction pairs and repeated openings of one "
    "package are correlated, not independent votes, so no confidence interval treats requests as "
    "independent packages. The nine packages are curated squares read-only by SHA-256; 114 "
    "collector-recipe-only observations and 264 runtime-bound observations stay separate and are not a "
    "strict no-mods or memory attestation. Three openings failed before a network snapshot existed and "
    "stay recorded as anomalies. No observation date is recorded anywhere in the publication, so every "
    "observation date stays Unknown rather than being replaced by a publication or freeze time. The study "
    "does not transfer this evidence's agreement to the current runtime checker, the live estimate, a "
    "certificate, a promise or rail."
)


def fail(message: str) -> None:
    raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def canon(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return sha(canon(value).encode())


def expect(condition, message: str) -> None:
    if not condition:
        fail(message)


def read_carried() -> dict[str, bytes]:
    carried = {}
    for relative in COPIES:
        path = EVIDENCE / STUDY / relative
        expect(path.is_file(), f"missing carried evidence {relative}")
        carried[relative] = path.read_bytes()
    return carried


def publication_documents(source: Path) -> dict[str, bytes]:
    docs = {}
    for relative in list(COPIES) + list(LINKED):
        path = source / relative
        expect(path.is_file(), f"publication is missing {relative}")
        docs[relative] = path.read_bytes()
    present = sorted(
        p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()
    )
    expect(present == sorted(docs), "publication directory is not exactly its 21 files")
    return docs


def build_manifest(docs: dict[str, bytes]) -> dict:
    files = {
        relative: {"bytes": len(raw), "sha256": sha(raw), "git_blob": git_blob(raw)}
        for relative, raw in docs.items()
    }
    return {
        "schema": 1,
        "note": (
            "Strict file scope for the accepted outside-query-model-v1 publication. Every listed file is "
            "pinned by its SHA-256, byte length and Git blob id at the publication commit. `copied` names "
            "evidence carried byte for byte in this repository; `linked` names the bulk frozen requests, "
            "frozen predictions and retained inventory served as immutable blobs at that commit."
        ),
        "publications": {
            STUDY: {
                "commit": PUBLICATION["publication_commit"],
                "prefix": PREFIX,
                "files": files,
                "copied": sorted(COPIES),
                "linked": sorted(LINKED),
            }
        },
    }


def check_manifest(manifest: dict, carried: dict[str, bytes]) -> dict:
    expect(
        manifest.get("schema") == 1, "outside research source manifest schema changed"
    )
    expect(
        list(manifest.get("publications", {})) == [STUDY],
        "outside research source manifest lost its publication",
    )
    publication = manifest["publications"][STUDY]
    expect(
        publication["commit"] == PUBLICATION["publication_commit"],
        "source manifest names another publication",
    )
    expect(publication["prefix"] == PREFIX, "source manifest prefix changed")
    files = publication["files"]
    expect(len(files) == EXPECTED_PUBLICATION_FILES, "publication file scope changed")
    expect(sorted(publication["copied"]) == sorted(COPIES), "carried-file list changed")
    expect(sorted(publication["linked"]) == sorted(LINKED), "linked-file list changed")
    expect(
        sorted(publication["copied"] + publication["linked"]) == sorted(files),
        "carried and linked files do not partition the publication",
    )
    for relative, record in files.items():
        expect(
            isinstance(record.get("sha256"), str) and len(record["sha256"]) == 64,
            f"bad hash for {relative}",
        )
        expect(
            isinstance(record.get("git_blob"), str) and len(record["git_blob"]) == 40,
            f"bad blob id for {relative}",
        )
        expect(record.get("bytes", 0) > 0, f"bad size for {relative}")
        if relative in COPIES:
            raw = carried[relative]
            expect(
                sha(raw) == record["sha256"] and len(raw) == record["bytes"],
                f"carried file differs from its publication: {relative}",
            )
            expect(
                git_blob(raw) == record["git_blob"],
                f"carried file has another Git blob id: {relative}",
            )
        else:
            expect(
                not (EVIDENCE / STUDY / relative).exists(),
                f"linked file must not be duplicated in the repository: {relative}",
            )
    carried_root = EVIDENCE / STUDY
    present = sorted(
        p.relative_to(carried_root).as_posix()
        for p in carried_root.rglob("*")
        if p.is_file()
    )
    expect(
        present == sorted(COPIES),
        "carried prefix has files outside the publication scope",
    )
    return files


def cross_declarations(carried: dict[str, bytes], files: dict[str, dict]) -> dict:
    """Every hash a carried document declares for a publication file.

    A changed source document cannot be re-pinned by editing the manifest alone:
    the publication's own protocol, integrity and bindings documents each name
    those bytes, and those documents are themselves pinned by this projection.
    """
    protocol = json.loads(carried["protocol.json"])
    integrity = json.loads(carried["integrity.json"])
    bindings = json.loads(carried["bindings.json"])
    manifest = json.loads(carried["manifest.json"])
    bridge = json.loads(carried["bridge.json"])

    declared: dict[str, list[str]] = {}

    def add(name: str, where: str, value) -> None:
        expect(isinstance(value, str), f"{where} declares no hash")
        declared.setdefault(name, []).append(where)
        expect(
            value == files[name]["sha256"],
            f"{name}: {where} does not match the publication manifest",
        )

    expect(
        set(integrity["hashes"]) == FROZEN_DIGEST_FILES | {"evidence.json"},
        "integrity.json hash key set changed",
    )
    for name, value in integrity["hashes"].items():
        if name == "evidence.json":
            continue
        add(name, f"integrity.json hashes.{name}", value)
    expect(
        set(bindings["files"]) == FROZEN_SOURCE_FILES,
        "bindings.json file key set changed",
    )
    for name, value in bindings["files"].items():
        add(name, f"bindings.json files.{name}", value)
    expect(
        set(manifest["hashes"]) == {"inventory.json", "requests.json"},
        "manifest.json hash key set changed",
    )
    for name, value in manifest["hashes"].items():
        add(name, f"manifest.json hashes.{name}", value)
    sources = protocol["sources"]
    expect(set(sources) == PROTOCOL_SOURCES, "protocol source key set changed")
    for key, value in sources.items():
        if key == "evidence":
            continue
        add(f"{key}.json", f"protocol.json sources.{key}", value)
    add(
        "predictions.json",
        "protocol.json predictions_sha256",
        protocol["predictions_sha256"],
    )
    add(
        "catalogs.json",
        "bridge.json catalog.sha256_catalogs_json",
        bridge["catalog"]["sha256_catalogs_json"],
    )

    assertion_names = {assertion["name"] for assertion in integrity["assertions"]}
    expected_assertions = {f"frozen_file_{name}" for name in FROZEN_SOURCE_FILES}
    expect(
        expected_assertions <= assertion_names,
        "the publication does not assert one of its frozen files",
    )

    for name in LINKED:
        expect(
            len(declared.get(name, [])) >= 2,
            f"{name}: the linked source is declared by fewer than two carried documents",
        )
    return {name: sorted(set(entries)) for name, entries in declared.items()}


def check_external_evidence(carried: dict[str, bytes]) -> dict:
    """The raw outside-v1 evidence is not in this publication; it is named."""
    protocol = json.loads(carried["protocol.json"])
    manifest = json.loads(carried["manifest.json"])
    record = {
        "file": "outside-v1/evidence.json",
        "accepted_base": PUBLICATION["accepted_base"],
        "sha256": protocol["sources"]["evidence"],
        "bytes": manifest["source"]["evidence_bytes"],
        "role": "raw_native_evidence_linked_at_the_accepted_base",
    }
    expect(
        record["sha256"] == manifest["source"]["evidence_sha256"],
        "the accepted evidence hash is declared twice and differs",
    )
    expect(record["bytes"] == 7651131, "the accepted evidence size changed")
    return record


def check_semantics(carried: dict[str, bytes]) -> dict:
    protocol = json.loads(carried["protocol.json"])
    bindings = json.loads(carried["bindings.json"])
    integrity = json.loads(carried["integrity.json"])

    expect(protocol["study"] == STUDY, "protocol names another study")
    expect(protocol["model_version"] == STUDY, "protocol model version changed")
    expect(protocol["schema"] == 1, "protocol schema changed")
    expect(protocol["rules"] == RULES, "the frozen rule family changed")
    expect(protocol["baselines"] == BASELINES, "the frozen baselines changed")
    expect(
        protocol["primary_rule"] == PRIMARY_RULE, "the registered primary rule changed"
    )
    expect(protocol["rules_per_mode"] == len(RULES), "rules per mode changed")
    expect(protocol["prediction_count"] == 378, "prediction count changed")
    expect(protocol["predictions_bytes"] == 845394, "frozen prediction size changed")
    expect(protocol["absent"] == [], "the publication now records an absent rule")
    expect(
        protocol["frozen_at"] == "2026-11-23T08:53:14.972926+00:00",
        "the protocol freeze timestamp changed",
    )

    domain = protocol["domain"]
    for key, value in EXPECTED_DOMAIN.items():
        expect(
            domain[key] == value,
            f"protocol domain {key} is not the corrected per-mode protocol",
        )
    expect(
        domain["collector_source"]["sha256"] == COLLECTOR["sha256"],
        "collector hash changed",
    )
    expect(
        domain["collector_source"]["revision"] == COLLECTOR["revision"],
        "collector revision changed",
    )
    expect(
        domain["collector_source"]["path"] == COLLECTOR["path"],
        "collector path changed",
    )
    for text in PROTOCOL_TEXT:
        expect(
            text in protocol["protocol_copied_from_source"],
            f"protocol text lost {text!r}",
        )
    expect(
        protocol["pairings"] and protocol["uturns"],
        "the hypothesis families were dropped",
    )
    expect(set(protocol["strata"]) <= set(STRATA), "protocol names an unknown stratum")

    expect(bindings["schema"] == 1, "bindings schema changed")
    expect(bindings["study"] == STUDY, "bindings name another study")
    expect(
        bindings["source_revisions"]
        == {
            "accepted_base": PUBLICATION["accepted_base"],
            "outside_v1": PUBLICATION["native_sources"]["outside_v1"],
            "targeted_v2": PUBLICATION["native_sources"]["targeted_v2"],
        },
        "the frozen source revisions changed",
    )
    expect(
        bindings["protocol_semantic_sha256"]
        == digest({k: v for k, v in protocol.items() if k != "frozen_at"}),
        "the frozen protocol semantics changed",
    )
    expect(
        bindings["domain_sha256"] == digest(protocol["domain"]),
        "the frozen protocol domain changed",
    )
    expect(
        bindings["features_sha256"]
        == digest(
            {key: protocol[key] for key in ("features_allowed", "features_forbidden")}
        ),
        "the frozen protocol features changed",
    )

    expect(integrity["schema"] == 1, "integrity schema changed")
    expect(integrity["study"] == STUDY, "integrity names another study")
    expect(
        integrity["all_ok"] is True,
        "the publication's own integrity check did not pass",
    )
    expect(
        len(integrity["assertions"]) == 116,
        "the publication's integrity assertion set changed",
    )
    expect(
        [a for a in integrity["assertions"] if not a["ok"]] == [],
        "a recorded integrity assertion is not ok",
    )
    names = {a["name"] for a in integrity["assertions"]}
    for required in (
        "exact_required_source_keys",
        "exact_frozen_file_keys",
        "fixed_source_revisions",
        "frozen_protocol_semantics",
        "frozen_domain",
        "frozen_features",
        "inventory_reconstructed_from_raw",
        "requests_reconstructed_from_raw",
        "manifest_reconstructed_from_raw",
        "predictions_bind_requests",
        "requests_bind_inventory",
        "every_eligible_query_has_a_strict_boolean_label",
        "global_best_is_in_frozen_family",
        "midpoint_repeats_agree",
        "chord_bridge_error_cannot_flip_the_length_test",
        "opening_protocol_source_pittsburgh_native-v2-6",
        "only_known_missing_networks",
    ):
        expect(required in names, f"the publication lost its {required} binding")
    for slug in PACKAGE_NAMES:
        for prefix in ("package_lineage", "cpu_evidence", "reproduction_evidence"):
            expect(
                f"{prefix}_{slug}" in names,
                f"the publication lost its {slug} {prefix.replace('_', ' ')}",
            )
    for opening in json.loads(carried["manifest.json"])["openings"]:
        expect(
            f"opening_protocol_source_{opening['slug']}_{opening['attempt_id']}"
            in names,
            f"{opening['slug']}/{opening['attempt_id']}: the collector source binding is gone",
        )
    return protocol


def check_packages(carried: dict[str, bytes]) -> dict:
    packages = json.loads(carried["packages.json"])
    expect(
        packages["schema"] == 1 and packages["study"] == STUDY,
        "packages header changed",
    )
    expect(
        tuple(sorted(packages["packages"])) == PACKAGE_NAMES, "the package set changed"
    )
    for slug, package in packages["packages"].items():
        expect(len(package["sha256"]) == 64, f"{slug}: package hash malformed")
        expect(
            package["bytes"] > 0 and package["locator"], f"{slug}: package locator lost"
        )
    return packages["packages"]


def check_openings(carried: dict[str, bytes], packages: dict) -> list[dict]:
    manifest = json.loads(carried["manifest.json"])
    openings = manifest["openings"]
    expect(len(openings) == EXPECTED_COUNTS["openings"], "the opening count changed")
    rows = []
    for opening in openings:
        slug, attempt = opening["slug"], opening["attempt_id"]
        expect(
            opening["artifact_sha256"] == packages[slug]["sha256"],
            f"{slug}/{attempt}: opening package identity changed",
        )
        for digest in (opening["collector_sha256"], opening["build_dll_sha256"]):
            expect(
                digest is None or (isinstance(digest, str) and len(digest) == 64),
                f"{slug}/{attempt}: malformed collector identity",
            )
        networks = opening["networks"]
        if opening["paths"]:
            expect(
                networks["sha256"],
                f"{slug}/{attempt}: a queried opening lost its network snapshot",
            )
        rows.append(
            {
                "slug": slug,
                "attempt_id": attempt,
                "study": opening["study"],
                "artifact_sha256": opening["artifact_sha256"],
                "collector_sha256": opening["collector_sha256"],
                "build_dll_sha256": opening["build_dll_sha256"],
                "runtime_build_matches": opening["runtime_build_matches"],
                "paths": opening["paths"],
                "segments": networks["segments"],
                "node_flag_conflicts": networks["node_flag_conflicts"],
                "networks_sha256": networks["sha256"],
                "observation_sha256": opening["observation"]["sha256"],
                "observation_bytes": opening["observation"]["bytes"],
                "completed": opening["completed"],
            }
        )
    counter: dict[tuple, int] = {}
    for opening in openings:
        key = (opening["collector_sha256"], opening["build_dll_sha256"])
        counter[key] = counter.get(key, 0) + 1
    expect(counter == EXPECTED_BUILDS, "the per-opening collector builds changed")
    expect(
        sum(counter.values()) == EXPECTED_COUNTS["openings"],
        "the collector ledger lost an opening",
    )
    expect(
        sum(1 for opening in openings if opening["runtime_build_matches"] is True) == 5,
        "the runtime build match count changed",
    )

    anomalies = manifest["anomalies"]
    expect(len(anomalies) == EXPECTED_COUNTS["anomalies"], "the anomaly count changed")
    expect(
        sorted((a["slug"], a["attempt_id"], a["kind"]) for a in anomalies)
        == [
            ("asheville", "attempt-1", "missing_networks"),
            ("pittsburgh", "native-v2-2", "missing_networks"),
            ("rio", "native-v2-1", "missing_networks"),
        ],
        "the recorded anomalies changed",
    )
    return rows


def confusion(pairs) -> dict:
    """Score (prediction, observed label) pairs. A label is success/failure/None."""
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "abstain": 0, "unknown": 0}
    for prediction, label in pairs:
        if prediction in ("abstain", "unknown"):
            counts[prediction] += 1
        elif label is None:
            counts["unknown"] += 1
        elif prediction == "success" and label == "success":
            counts["tp"] += 1
        elif prediction == "success" and label == "failure":
            counts["fp"] += 1
        elif prediction == "no_path" and label == "failure":
            counts["tn"] += 1
        elif prediction == "no_path" and label == "success":
            counts["fn"] += 1
        else:
            fail(f"unlabelable pair {prediction!r} {label!r}")
    tp, fp, tn, fn = counts["tp"], counts["fp"], counts["tn"], counts["fn"]
    positives, actual, scored = tp + fp, tp + fn, tp + fp + tn + fn
    precision = tp / positives if positives else None
    recall = tp / actual if actual else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall)
        else None
    )
    return {
        "counts": counts,
        "rates": {
            "n": scored + counts["abstain"] + counts["unknown"],
            "scored": scored,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "coverage": scored / (scored + counts["abstain"] + counts["unknown"]),
            "candidate_fraction": positives / scored if scored else None,
            "classes": {
                "positives": actual,
                "negatives": tn + fp,
                "estimable": actual > 0 and (tn + fp) > 0,
            },
        },
    }


def rounded(value):
    return round(value, 12) if isinstance(value, float) else value


def table_block(pairs_by_rule: dict[str, list]) -> dict:
    out = {}
    for rule, pairs in pairs_by_rule.items():
        conf = confusion(pairs)
        out[rule] = {
            "counts": conf["counts"],
            "rates": {key: rounded(value) for key, value in conf["rates"].items()},
        }
    return out


def derive_rows(docs: dict[str, bytes]) -> list[dict]:
    inventory = json.loads(docs["inventory.json"])
    predictions = json.loads(docs["predictions.json"])
    requests = json.loads(docs["requests.json"])

    expect(
        inventory["study"] == STUDY and inventory["schema"] == 1,
        "inventory header changed",
    )
    expect(
        predictions["study"] == STUDY and predictions["schema"] == 1,
        "predictions header changed",
    )
    expect(
        requests["study"] == STUDY and requests["schema"] == 1,
        "requests header changed",
    )
    expect(predictions["rules"] == RULES, "predictions use another rule family")
    expect(
        predictions["primary_rule"] == PRIMARY_RULE,
        "predictions use another primary rule",
    )
    expect(
        predictions["model_version"] == STUDY, "predictions name another model version"
    )
    expect(
        predictions["requests_sha256"] == sha(docs["requests.json"]),
        "predictions do not bind the requests file",
    )
    expect(
        requests["inventory_sha256"] == sha(docs["inventory.json"]),
        "requests do not bind the inventory file",
    )

    by_query = {}
    for query in inventory["queries"]:
        expect(
            query["query_id"] not in by_query,
            f"duplicate inventory query {query['query_id']}",
        )
        by_query[query["query_id"]] = query
    eligible = {qid: query for qid, query in by_query.items() if query["eligible"]}

    predicted = {}
    for record in predictions["predictions"]:
        expect(
            record["query_id"] not in predicted,
            f"duplicate prediction {record['query_id']}",
        )
        expect(
            record["query_id"] in by_query,
            f"prediction outside the inventory: {record['query_id']}",
        )
        expect(
            set(record["rules"]) == set(RULES),
            f"{record['query_id']}: a prediction lost a frozen rule",
        )
        query = by_query[record["query_id"]]
        for key in ("slug", "attempt_id", "mode", "stratum"):
            expect(
                record[key] == query[key],
                f"{record['query_id']}: prediction {key} does not match the inventory",
            )
        expect(
            record["request"] == query["request"],
            f"{record['query_id']}: request drift",
        )
        predicted[record["query_id"]] = record
    expect(
        set(predicted) == set(eligible),
        "predictions and eligible inventory rows disagree",
    )

    request_ids = [record["query_id"] for record in requests["requests"]]
    expect(len(set(request_ids)) == len(request_ids), "duplicate request query ids")
    expect(
        set(request_ids) == set(eligible),
        "requests and eligible inventory rows disagree",
    )

    for query in eligible.values():
        expect(
            query["label"] in ("success", "failure")
            and isinstance(query["observed"], bool),
            f"{query['query_id']}: an eligible query has no strict boolean label",
        )
        expect(
            query["label_status"] == "eligible",
            f"{query['query_id']}: eligible status changed",
        )

    rows = []
    for query in inventory["queries"]:
        row = {
            "id": query["query_id"],
            "mode": query["mode"],
            "stratum": query["stratum"],
            "eligible": query["eligible"],
            "exclusion": query["exclusion"],
            "label_status": query["label_status"],
            "label": query["label"],
            "recorded_outcome": query["observed"],
            "package": query["slug"],
            "attempt": query["attempt_id"],
            "study": query["study"],
            "runtime_bound": query["runtime_bound"],
            "request": query["request"],
        }
        if query["eligible"]:
            row["predicted"] = {
                rule: predicted[query["query_id"]]["rules"][rule]["prediction"]
                for rule in RULES
            }
        rows.append(row)
    return rows


def derive(
    rows: list[dict], carried: dict[str, bytes], inventory_counts: dict | None = None
) -> dict:
    evaluation = json.loads(carried["evaluation.json"])
    integrity = json.loads(carried["integrity.json"])
    manifest = json.loads(carried["manifest.json"])
    bridge = json.loads(carried["bridge.json"])
    packages = json.loads(carried["packages.json"])["packages"]

    for name, counts in (
        ("manifest", manifest["counts"]),
        ("integrity", integrity["counts"]),
    ):
        expect(counts == EXPECTED_COUNTS, f"{name} counts changed")
    if inventory_counts is not None:
        expect(inventory_counts == EXPECTED_COUNTS, "inventory counts changed")
    expect(
        evaluation["counts"]
        == {
            "by_mode": EXPECTED_COUNTS["eligible_by_mode"],
            "by_package": {
                "asheville": 20,
                "boston": 24,
                "charleston": 24,
                "hong-kong": 138,
                "pittsburgh": 148,
                "rio": 24,
            },
            "eligible": EXPECTED_COUNTS["eligible"],
            "primary": PRIMARY_ROWS,
            "same_edge": SAME_EDGE_ROWS,
        },
        "the accepted evaluation counts changed",
    )

    eligible = [row for row in rows if row["eligible"]]
    primary = [row for row in eligible if row["stratum"] == "primary_distinct_edge"]
    same_edge = [row for row in eligible if row["stratum"] == "same_edge"]
    expect(len(rows) == 876 and len(eligible) == 378, "retained row counts changed")
    expect(
        len(primary) == PRIMARY_ROWS and len(same_edge) == SAME_EDGE_ROWS,
        "scored stratum counts changed",
    )
    expect(
        sum(1 for row in rows if row["request"] is not None) == 820,
        "the literal-request row count changed",
    )
    expect(
        sum(1 for row in rows if row["label"] is None) == 92,
        "the unlabelled row count changed",
    )
    expect(
        sum(1 for row in rows if row["recorded_outcome"] is not None) == 848,
        "the recorded-outcome row count changed",
    )

    def by_rule(selection, rule):
        return [(row["predicted"][rule], row["label"]) for row in selection]

    primary_tables = {rule: confusion(by_rule(primary, rule)) for rule in RULES}
    same_tables = {rule: confusion(by_rule(same_edge, rule)) for rule in RULES}
    all_tables = {rule: confusion(by_rule(eligible, rule)) for rule in RULES}

    def quad(conf):
        counts = conf["counts"]
        return counts["tp"], counts["fp"], counts["tn"], counts["fn"]

    expect(
        quad(primary_tables[FITTED_RULE]) == (93, 19, 230, 0),
        "the fitted primary confusion changed",
    )
    expect(
        quad(primary_tables[PRIMARY_RULE]) == (93, 19, 230, 0),
        "the registered primary is no longer tied with the fitted rule on this evidence",
    )
    expect(
        quad(same_tables[FITTED_RULE]) == (9, 0, 27, 0),
        "the same-edge confusion changed",
    )

    modes = {}
    for mode in MODES:
        selected = [row for row in primary if row["mode"] == mode]
        expected = EXPECTED_MODES[mode]
        expect(
            len(selected) == expected["primary"], f"{mode}: primary row count changed"
        )
        expect(
            quad(confusion(by_rule(selected, FITTED_RULE))) == expected["fitted"],
            f"{mode}: primary confusion changed",
        )
        successes = sum(1 for row in selected if row["label"] == "success")
        expect(successes == expected["fitted"][0], f"{mode}: success count changed")
        modes[mode] = {
            "primary": len(selected),
            "same_edge": sum(1 for row in same_edge if row["mode"] == mode),
            "successes": successes,
            "failures": len(selected) - successes,
            "fitted": table_block({rule: by_rule(selected, rule) for rule in RULES}),
            "discrimination_estimable": expected["estimable"],
        }

    groups = {}
    for label, study in (
        ("PL-1121 first openings", "v1"),
        ("PL-1142 targeted openings", "targeted-v2"),
    ):
        selected = [row for row in eligible if row["study"] == study]
        conf = confusion(by_rule(selected, FITTED_RULE))["counts"]
        got = {
            "n": len(selected),
            **{k: conf[k] for k in ("tp", "fp", "tn", "fn")},
            "fidelity": EXPECTED_GROUPS[label]["fidelity"],
        }
        expect(got == EXPECTED_GROUPS[label], f"{label}: group confusion changed")
        groups[label] = got
    expect(
        sum(group["n"] for group in groups.values()) == 378,
        "the study groups do not partition the eligible rows",
    )
    expect(
        [name for name, group in groups.items() if group["fp"]]
        == ["PL-1142 targeted openings"],
        "every false positive must sit in the targeted second openings",
    )

    package_groups = {}
    for slug, expected in EXPECTED_PACKAGES.items():
        selected = [row for row in primary if row["package"] == slug]
        conf = confusion(by_rule(selected, FITTED_RULE))["counts"]
        got = {"n": len(selected), **{k: conf[k] for k in ("tp", "fp", "tn", "fn")}}
        expect(got == expected, f"{slug}: package confusion changed")
        package_groups[slug] = got
    expect(
        sum(group["fp"] for group in package_groups.values()) == 19,
        "the false-positive count across packages changed",
    )
    expect(
        {slug for slug, group in package_groups.items() if group["fp"]}
        == {"hong-kong", "pittsburgh"},
        "the false positives moved out of the two targeted packages",
    )

    # Leave-one-package-out: select on the remaining packages by F1, then recall,
    # then frozen rule order; score the held-out package with the selected rule.
    folds = []
    for held_out in PACKAGE_NAMES:
        if held_out not in package_groups:
            continue
        training = [row for row in primary if row["package"] != held_out]
        held = [row for row in primary if row["package"] == held_out]
        scores = {}
        for index, rule in enumerate(RULES):
            rates = confusion(by_rule(training, rule))["rates"]
            scores[rule] = (
                rates["f1"] if rates["f1"] is not None else -1.0,
                rates["recall"] if rates["recall"] is not None else -1.0,
                -index,
            )
        selected = max(RULES, key=lambda rule: scores[rule])
        expect(
            selected == FITTED_RULE,
            f"{held_out}: leave-one-package-out selection changed to {selected}",
        )
        held_conf = confusion(by_rule(held, selected))["counts"]
        folds.append(
            {
                "held_out": held_out,
                "training_rows": len(training),
                "held_out_rows": len(held),
                "successes": sum(1 for row in held if row["label"] == "success"),
                "failures": sum(1 for row in held if row["label"] == "failure"),
                "selected_rule": selected,
                **{k: held_conf[k] for k in ("tp", "fp", "tn", "fn")},
            }
        )
    expect(len(folds) == 6, "the leave-one-package-out fold set changed")
    expect(
        sum(fold["held_out_rows"] for fold in folds) == 342,
        "the folds do not partition the primary rows",
    )

    # Cross-check every recomputed table against the accepted evaluator's own.
    def recorded_quad(table):
        return table["TP"], table["FP"], table["TN"], table["FN"]

    for rule in RULES:
        recorded = evaluation["by_rule"][rule]
        expect(
            recorded_quad(recorded["all_strata"]) == quad(all_tables[rule]),
            f"{rule}: recomputed all-eligible confusion differs from the accepted evaluation",
        )
        expect(
            recorded_quad(recorded["primary_distinct_edge"])
            == quad(primary_tables[rule]),
            f"{rule}: recomputed primary confusion differs from the accepted evaluation",
        )
        expect(
            recorded_quad(recorded["same_edge"]) == quad(same_tables[rule]),
            f"{rule}: recomputed same-edge confusion differs from the accepted evaluation",
        )
        for mode in MODES:
            expect(
                recorded["by_mode_primary"][mode]["TP"]
                == modes[mode]["fitted"][rule]["counts"]["tp"]
                and recorded["by_mode_primary"][mode]["FP"]
                == modes[mode]["fitted"][rule]["counts"]["fp"]
                and recorded["by_mode_primary"][mode]["TN"]
                == modes[mode]["fitted"][rule]["counts"]["tn"]
                and recorded["by_mode_primary"][mode]["FN"]
                == modes[mode]["fitted"][rule]["counts"]["fn"],
                f"{rule}: recomputed {mode} confusion differs from the accepted evaluation",
            )
    for slug, group in package_groups.items():
        recorded = evaluation["groups"]["by_package"][slug][FITTED_RULE]
        expect(
            recorded_quad(recorded)
            == tuple(group[k] for k in ("tp", "fp", "tn", "fn")),
            f"{slug}: recomputed package table differs from the accepted evaluation",
        )
    for key, group in (
        ("False", groups["PL-1121 first openings"]),
        ("True", groups["PL-1142 targeted openings"]),
    ):
        recorded = evaluation["groups"]["by_fidelity"][key][FITTED_RULE]
        expect(
            recorded_quad(recorded)
            == tuple(group[k] for k in ("tp", "fp", "tn", "fn")),
            f"fidelity {key}: recomputed group table differs from the accepted evaluation",
        )
    for record in evaluation["leave_one_package_out"]:
        held = next(fold for fold in folds if fold["held_out"] == record["held_out"])
        expect(
            record["selected_rule"] == held["selected_rule"],
            f"{record['held_out']}: the accepted fold selected another rule",
        )
        for count in ("TP", "FP", "TN", "FN"):
            expect(
                record["held_out_metrics"][count] == held[count.lower()],
                f"{record['held_out']}: recomputed held-out confusion differs",
            )
        expect(
            record["identical_to_global_best"] is True,
            f"{record['held_out']}: a held-out fold no longer reproduces the global best",
        )

    identical = {}
    for mode in MODES:
        observed: dict[str, list[str]] = {}
        for rule in RULES:
            observed.setdefault(
                canon(modes[mode]["fitted"][rule]["counts"]), []
            ).append(rule)
        identical[mode] = list(observed.values())
    expect(
        {frozenset(group) for group in identical["road"]}
        == {
            frozenset({"always_fail"}),
            frozenset({"always_candidate", "weak_component"}),
            frozenset(
                {"directed_segment", "lane:any_lane:allowed", "lane:any_lane:forbidden"}
            ),
            frozenset(
                {"lane:index_mirror:forbidden", "lane:orientation_mirror:forbidden"}
            ),
            frozenset(
                {
                    "lane:index_same:allowed",
                    "lane:index_same:forbidden",
                    "lane:orientation_index:allowed",
                    "lane:orientation_index:forbidden",
                }
            ),
        },
        "the road rule equivalence classes changed",
    )
    for mode in ("ship", "air"):
        expect(
            [sorted(group) for group in identical[mode] if len(group) > 1]
            == [sorted(group) for group in evaluation["identical_rules"][mode]],
            f"{mode}: the tied rule classes changed",
        )
        tied = next(group for group in identical[mode] if FITTED_RULE in group)
        expect(
            set(tied) == set(RULES) - {"always_fail"},
            f"{mode}: a one-class tie stopped covering every non-constant rule",
        )

    disagreements = evaluation["disagreements"][FITTED_RULE]
    expect(
        [row["query_id"] for row in disagreements] == DISAGREEMENT_IDS,
        "the disagreement set changed",
    )
    for record in disagreements:
        expect(
            record["relation"] == "false_positive",
            "a disagreement is no longer a false positive",
        )
        expect(record["mode"] == "road", "a disagreement left the road mode")
        expect(record["mechanism_status"] == "unknown", "a failure mechanism was named")
        expect(
            record["native"]["complete"] is True
            and record["native"]["released"] is True,
            "a disagreement is no longer a complete released result",
        )
        expect(
            record["native"]["success"] is False,
            "a disagreement's native result changed",
        )
        expect(
            record["native"]["flags"] == 8 and record["native"]["length"] == 100000.0,
            "the retained sentinel fields changed",
        )
        expect(
            record["returned_endpoints_match"] is False,
            "a disagreement returned endpoints",
        )
        row = next(item for item in primary if item["id"] == record["query_id"])
        expect(
            row["predicted"][FITTED_RULE] == "success",
            "a disagreement is not a predicted success",
        )
        expect(row["label"] == "failure", "a disagreement is not an observed failure")
    expect(
        [row["query_id"] for row in evaluation["unexplained_disagreements"]]
        == DISAGREEMENT_IDS,
        "the unexplained disagreement set changed",
    )
    expect(
        {row["package"] for row in disagreements} == {"hong-kong", "pittsburgh"},
        "the disagreements left their two packages",
    )
    lengths = [row["model"]["path_lower_bound_length"] for row in disagreements]
    expect(
        round(min(lengths) / 1000, 1) == 21.7 and round(max(lengths) / 1000, 1) == 30.9,
        "the disagreement chord lower bounds changed",
    )

    repeats = evaluation["repeats"]
    expect(
        repeats["midpoint"] == {"agree": 378, "pairs": 378},
        "the midpoint repeat count changed",
    )
    expect(
        repeats["cross_opening_pairs"] == 8 and repeats["cross_opening_agree"] == 8,
        "the cross-opening repeat count changed",
    )
    expect(
        all(record["agree"] for record in repeats["cross_opening"]),
        "a repeated opening now disagrees",
    )

    one_class = evaluation["one_class"]
    for mode in ("ship", "air"):
        expect(
            one_class[mode]["discrimination_estimable"] is False,
            f"{mode}: discrimination became estimable",
        )
        expect(one_class[mode]["negatives"] == 0, f"{mode}: a negative appeared")
        expect(
            one_class[mode]["precision"] == 1.0,
            f"{mode}: the trivial precision changed",
        )
    expect(
        one_class["road"]["discrimination_estimable"] is True,
        "road lost its two classes",
    )
    expect(one_class["road"]["precision"] == 67 / 86, "the road precision changed")

    length_check = evaluation["length_check"]
    expect(length_check["binds"] is False, "the maxLength lower bound now binds")
    expect(
        length_check["bridge_error_cannot_flip"] is True,
        "the chord bridge error can now flip a prediction",
    )
    expect(
        length_check["cap_sensitive_no_path"] == [],
        "a no-path prediction became cap-sensitive",
    )
    expect(length_check["max_length"] == 100000.0, "the audited maxLength changed")
    expect(
        round(length_check["max_directed_chord_over_cap"], 11) == 0.48886885468,
        "the longest directed chord fraction changed",
    )

    # The bridge: every model field recovered from the nine unchanged packages.
    expect(bridge["answer"] == "yes", "the bridge answer changed")
    expect(
        isinstance(bridge["question"], str) and bridge["question"],
        "the bridge question was dropped",
    )
    totals = {
        key: sum(
            package.get(key) or 0 for package in bridge["packages_report"].values()
        )
        for key in BRIDGE_TOTALS
    }
    expect(totals == BRIDGE_TOTALS, "the bridge totals changed")
    expect(
        tuple(sorted(bridge["packages_report"])) == PACKAGE_NAMES,
        "the bridge package set changed",
    )
    for slug, package in bridge["packages_report"].items():
        expect(
            package["mode_inputs_equal"] is True,
            f"{slug}: a mode input digest diverged",
        )
        expect(package["missing"] == [], f"{slug}: the bridge lost a catalog field")
        expect(
            package["positions_within_tolerance"] <= package["segments_native"],
            f"{slug}: the position tolerance count is impossible",
        )
        expect(
            package["chord_relative_error_max"] <= 0.2,
            f"{slug}: a chord error left the tolerance",
        )
    uncovered = {
        slug: len(record["node_flag_values_uncovered"])
        for slug, record in bridge["fold_cross_validation"].items()
    }
    expect(
        uncovered
        == {
            slug: (1 if slug == "asheville" else 2 if slug == "hong-kong" else 0)
            for slug in PACKAGE_NAMES
        },
        "the leave-one-package-out catalog coverage changed",
    )
    for slug, record in bridge["fold_cross_validation"].items():
        expect(record["prefab_uncovered"] == [], f"{slug}: a prefab left the catalog")
        expect(
            record["segment_flag_values_uncovered"] == [],
            f"{slug}: a segment flag left the catalog",
        )
    expect(bridge["catalog"]["prefabs"] == 12, "the prefab catalog size changed")
    expect(
        bridge["catalog"]["node_flag_values"] == 31,
        "the node-flag catalog size changed",
    )
    expect(
        bridge["catalog"]["segment_flag_values"] == 2,
        "the segment-flag catalog size changed",
    )
    expect(
        sorted(bridge["catalog"]["outside_values"])
        == [17409, 4211713, 16794625, 268452865],
        "the Outside node flag values changed",
    )
    expect(len(bridge["limitations"]) == 3, "the bridge limitations changed")
    expect(
        "99.80% of segments still have a chord length within 2%"
        in bridge["limitations"][2],
        "the bridge chord tolerance statement changed",
    )

    return {
        "rows": rows,
        "selection": {
            "queries": EXPECTED_COUNTS["queries"],
            "eligible": EXPECTED_COUNTS["eligible"],
            "primary": PRIMARY_ROWS,
            "same_edge": SAME_EDGE_ROWS,
            "literal_request_rows": 820,
            "unlabelled_rows": 92,
            "excluded_rows": len(manifest["excluded"]),
            "openings": EXPECTED_COUNTS["openings"],
            "packages": len(PACKAGE_NAMES),
            "labels": EXPECTED_COUNTS["labels"],
            "by_stratum": EXPECTED_COUNTS["by_stratum"],
            "by_exclusion": EXPECTED_COUNTS["by_exclusion"],
            "eligible_by_mode": EXPECTED_COUNTS["eligible_by_mode"],
            "midpoint_repeats": {"agree": 378, "pairs": 378},
            "cross_opening_repeats": {"agree": 8, "pairs": 8},
            "groups": groups,
            "package_groups": package_groups,
        },
        "modes": modes,
        "rules": {
            "names": RULES,
            "baselines": BASELINES,
            "primary": PRIMARY_RULE,
            "fitted": FITTED_RULE,
            "primary_stratum": table_block(
                {rule: by_rule(primary, rule) for rule in RULES}
            ),
            "same_edge": table_block(
                {rule: by_rule(same_edge, rule) for rule in RULES}
            ),
            "all_eligible": table_block(
                {rule: by_rule(eligible, rule) for rule in RULES}
            ),
            "identical": identical,
        },
        "folds": folds,
        "repeats": repeats,
        "disagreements": [
            {
                "query_id": record["query_id"],
                "package": record["package"],
                "mode": record["mode"],
                "relation": record["relation"],
                "mechanism_status": record["mechanism_status"],
                "path_lower_bound_length": record["model"]["path_lower_bound_length"],
                "native": record["native"],
                "endpoint_roles": record["endpoint_roles"],
                "endpoint_edges": record["endpoint_edges"],
                "request": {
                    "from": record["request"]["from"],
                    "to": record["request"]["to"],
                    "lane_directions": record["request"].get("lane_directions"),
                },
            }
            for record in disagreements
        ],
        "length_check": length_check,
        "one_class": one_class,
        "bridge": {
            "question": bridge["question"],
            "answer": bridge["answer"],
            "totals": BRIDGE_TOTALS,
            "catalog": bridge["catalog"],
            "packages": {
                slug: {
                    key: package[key]
                    for key in (
                        "segments_native",
                        "nodes_native",
                        "mode_segments",
                        "mode_inputs_equal",
                        "start_end_equal",
                        "prefab_equal",
                        "lanes_equal",
                        "invert_equal",
                        "outside_nodes_equal",
                        "node_flags_differ_count",
                        "node_flags_differ_outside_disagreements",
                        "positions_within_tolerance",
                        "chords_equal_within_2pct",
                        "chords_equal_within_20pct",
                        "chord_relative_error_max",
                    )
                }
                for slug, package in bridge["packages_report"].items()
            },
            "catalog_uncovered": uncovered,
            "limitations": bridge["limitations"],
        },
        "exclusions": manifest["excluded"],
        "anomalies": manifest["anomalies"],
        "eligibility_rules": manifest["eligibility_rules"],
        "openings": check_openings(carried, packages),
        "packages": packages,
    }


def carried_subset(docs: dict[str, bytes]) -> dict[str, bytes]:
    return {name: raw for name, raw in docs.items() if name in COPIES}


def build_projection(docs: dict[str, bytes]) -> tuple[dict, dict]:
    carried = carried_subset(docs)
    manifest = build_manifest(docs)
    manifest_sha = sha((json.dumps(manifest, indent=1) + "\n").encode())
    files = check_manifest(manifest, carried)
    protocol = check_semantics(carried)
    declarations = cross_declarations(carried, files)
    external = check_external_evidence(carried)
    check_packages(carried)
    rows = derive_rows(docs)
    derived = derive(rows, carried, json.loads(docs["inventory.json"])["counts"])
    bindings = json.loads(carried["bindings.json"])
    integrity = json.loads(carried["integrity.json"])

    study = {
        "study": STUDY,
        "kind": PUBLICATION["kind"],
        "title": PUBLICATION["title"],
        "evidence_only": True,
        "certificates": "none",
        "scope": SCOPE,
        "method": METHOD,
        "limits": LIMITS,
        "source": {
            "publication_commit": PUBLICATION["publication_commit"],
            "publication_base": PUBLICATION["publication_base"],
            "accepted_base": PUBLICATION["accepted_base"],
            "internal_merge": PUBLICATION["internal_merge"],
            "pull_request": PUBLICATION["pull_request"],
            "branch": PUBLICATION["branch"],
            "source_issue": PUBLICATION["source_issue"],
            "review": {
                "pass": PUBLICATION["review_pass"],
                "engineering_note": PUBLICATION["engineering_note"],
                "parent_acceptance": PUBLICATION["parent_acceptance"],
            },
            "native_sources": PUBLICATION["native_sources"],
            "publication_prefix": PREFIX,
        },
        "closure": {
            "commit": PUBLICATION["publication_commit"],
            "prefix": PREFIX,
            "publication_files": EXPECTED_PUBLICATION_FILES,
            "copied_files": len(COPIES),
            "linked_files": len(LINKED),
        },
        "documents": list(DOCUMENTS),
        "files": [
            {
                "path": f"{PREFIX}/{relative}",
                "sha256": files[relative]["sha256"],
                "bytes": files[relative]["bytes"],
                "git_blob": files[relative]["git_blob"],
                "role": COPIES[relative],
            }
            for relative in COPIES
        ],
        "linked": [
            {
                "path": f"{PREFIX}/{relative}",
                "sha256": files[relative]["sha256"],
                "bytes": files[relative]["bytes"],
                "git_blob": files[relative]["git_blob"],
                "role": LINKED[relative],
                "declared_by": declarations[relative],
            }
            for relative in LINKED
        ],
        "freeze": {
            "name": protocol["model_version"],
            "frozen_at": protocol["frozen_at"],
            "predictions_sha256": protocol["predictions_sha256"],
            "predictions_bytes": protocol["predictions_bytes"],
            "prediction_count": protocol["prediction_count"],
            "protocol_semantic_sha256": bindings["protocol_semantic_sha256"],
            "domain_sha256": bindings["domain_sha256"],
            "features_sha256": bindings["features_sha256"],
            "retrospective": True,
            "frozen_before_observations": False,
            "observation_dates": "unknown",
        },
        "protocol": {
            key: protocol[key]
            for key in (
                "scope",
                "positive_label",
                "negative_label",
                "unknown_label",
                "protocol_copied_from_source",
                "features_allowed",
                "features_forbidden",
                "domain",
                "pairings",
                "uturns",
                "rules",
                "baselines",
                "lane_rules",
                "primary_rule",
                "primary_rule_basis",
                "selection_criterion",
                "strata",
                "sources",
                "snapshots",
                "model_version",
                "predictions_sha256",
                "predictions_bytes",
                "prediction_count",
                "rules_per_mode",
            )
        },
        "runtime": {
            "collector": COLLECTOR,
            "external_evidence": external,
            "integrity_assertions": len(integrity["assertions"]),
            "integrity_all_ok": integrity["all_ok"],
            "lineage": {
                slug: {
                    "cpu_evidence": f"cpu_evidence_{slug}",
                    "reproduction_evidence": f"reproduction_evidence_{slug}",
                    "package_lineage": f"package_lineage_{slug}",
                }
                for slug in PACKAGE_NAMES
            },
            "note": (
                "Old CPU and reproduction receipts bind each package and each opening to its retained "
                "build; they are the publication's own lineage, not a fresh native re-hash."
            ),
        },
        "declarations": declarations,
        **derived,
    }
    projection = {
        "schema": 1,
        "note": (
            "One accepted outside-connection query-model publication as a typed evidence study, "
            "referenced from Road, Ship and Air. It is not pooled with the native outside-v1/v2 studies, "
            "it is not a promise or a certificate, and no research code runs as a product check."
        ),
        "source_manifest": {
            "schema": 1,
            "file": MANIFEST_FILE,
            "sha256": manifest_sha,
            "commit": PUBLICATION["publication_commit"],
            "prefix": PREFIX,
            "publication_files": EXPECTED_PUBLICATION_FILES,
            "copied_files": len(COPIES),
            "linked_files": len(LINKED),
        },
        "studies": {STUDY: study},
    }
    return projection, manifest


def verify(projection: dict, carried: dict[str, bytes], manifest: dict) -> dict:
    """Re-check a committed projection against every carried declaration."""
    expect(projection.get("schema") == 1, "outside research projection schema changed")
    expect(
        list(projection["studies"]) == [STUDY],
        "outside research projection lost its study",
    )
    files = check_manifest(manifest, carried)
    check_semantics(carried)
    declarations = cross_declarations(carried, files)
    check_external_evidence(carried)
    packages = check_packages(carried)
    study = projection["studies"][STUDY]

    expect(
        study["study"] == STUDY and study["kind"] == PUBLICATION["kind"],
        "study identity changed",
    )
    expect(
        study["evidence_only"] is True and study["certificates"] == "none",
        "the study is no longer evidence only",
    )
    expect(
        study["source"]["publication_commit"] == PUBLICATION["publication_commit"],
        "the study names another publication",
    )
    expect(
        study["source"]["publication_base"] == PUBLICATION["publication_base"],
        "the study names another base",
    )
    expect(
        study["source"]["internal_merge"] == PUBLICATION["internal_merge"],
        "the study's internal merge changed",
    )
    expect(
        study["source"]["pull_request"] == PUBLICATION["pull_request"],
        "the study's PR changed",
    )
    expect(
        study["source"]["source_issue"] == PUBLICATION["source_issue"],
        "the study's source issue changed",
    )
    expect(
        study["source"]["native_sources"] == PUBLICATION["native_sources"],
        "the study's native sources changed",
    )
    expect(
        study["source"]["review"]
        == {
            "pass": PUBLICATION["review_pass"],
            "engineering_note": PUBLICATION["engineering_note"],
            "parent_acceptance": PUBLICATION["parent_acceptance"],
        },
        "the study's review record changed",
    )
    expect(
        study["freeze"]["retrospective"] is True, "the study is no longer retrospective"
    )
    expect(
        study["freeze"]["frozen_before_observations"] is False,
        "the study now claims a pre-observation freeze",
    )
    expect(
        study["freeze"]["observation_dates"] == "unknown",
        "the study now claims observation dates",
    )
    expect(
        study["freeze"]["frozen_at"]
        == json.loads(carried["protocol.json"])["frozen_at"],
        "the study's freeze timestamp changed",
    )

    expect(
        study["closure"]
        == {
            "commit": PUBLICATION["publication_commit"],
            "prefix": PREFIX,
            "publication_files": EXPECTED_PUBLICATION_FILES,
            "copied_files": len(COPIES),
            "linked_files": len(LINKED),
        },
        "the study's file scope changed",
    )
    expect(study["documents"] == list(DOCUMENTS), "the study's document list changed")
    expect(len(study["files"]) == len(COPIES), "the carried evidence count changed")
    for record in study["files"]:
        relative = record["path"][len(PREFIX) + 1 :]
        expect(
            relative in COPIES, f"carried evidence outside the prefix: {record['path']}"
        )
        expect(
            record["sha256"] == files[relative]["sha256"],
            f"carried evidence changed: {relative}",
        )
        expect(
            record["bytes"] == files[relative]["bytes"],
            f"carried evidence size changed: {relative}",
        )
        expect(
            record["git_blob"] == files[relative]["git_blob"],
            f"carried evidence blob changed: {relative}",
        )
        expect(
            record["role"] == COPIES[relative],
            f"carried evidence role changed: {relative}",
        )
    expect(
        [record["path"][len(PREFIX) + 1 :] for record in study["files"]]
        == list(COPIES),
        "the carried evidence order changed",
    )
    expect(len(study["linked"]) == len(LINKED), "the linked source count changed")
    for record in study["linked"]:
        relative = record["path"][len(PREFIX) + 1 :]
        expect(
            relative in LINKED, f"linked evidence outside the prefix: {record['path']}"
        )
        expect(
            record["sha256"] == files[relative]["sha256"],
            f"linked source pin changed: {relative}",
        )
        expect(
            record["bytes"] == files[relative]["bytes"],
            f"linked source size changed: {relative}",
        )
        expect(
            record["git_blob"] == files[relative]["git_blob"],
            f"linked source blob changed: {relative}",
        )
        expect(
            record["role"] == LINKED[relative],
            f"linked source role changed: {relative}",
        )
        expect(
            record["declared_by"] == declarations[relative],
            f"linked source provenance changed: {relative}",
        )
    expect(
        study["declarations"] == declarations,
        "the publication's hash declarations changed",
    )
    expect(study["packages"] == packages, "the package identities changed")
    manifest_doc = json.loads(carried["manifest.json"])
    expect(
        study["anomalies"] == manifest_doc["anomalies"],
        "the recorded anomalies changed",
    )
    expect(study["exclusions"] == manifest_doc["excluded"], "the excluded rows changed")
    expect(
        study["eligibility_rules"] == manifest_doc["eligibility_rules"],
        "the eligibility rules changed",
    )

    rows = study["rows"]
    expect(len(rows) == 876, "the retained row count changed")
    eligible = [row for row in rows if row["eligible"]]
    primary = [row for row in eligible if row["stratum"] == "primary_distinct_edge"]
    same_edge = [row for row in eligible if row["stratum"] == "same_edge"]
    expect(
        len(eligible) == 378 and len(primary) == 342 and len(same_edge) == 36,
        "the scored row sets changed",
    )
    expect(
        sum(1 for row in rows if row["request"] is not None) == 820,
        "the literal-request row count changed",
    )
    expect(len({row["id"] for row in rows}) == 876, "duplicate retained rows")
    for row in rows:
        expect(row["mode"] in MODES, f"{row['id']}: unknown mode")
        expect(row["stratum"] in STRATA, f"{row['id']}: unknown stratum")
        if row["eligible"]:
            expect(
                row["label"] in ("success", "failure"),
                f"{row['id']}: eligible row without a label",
            )
            expect(
                set(row["predicted"]) == set(RULES),
                f"{row['id']}: prediction rule set changed",
            )
            for label in row["predicted"].values():
                expect(
                    label in ("success", "no_path", "unknown", "abstain"),
                    f"{row['id']}: unknown prediction label",
                )
        else:
            expect(row["exclusion"], f"{row['id']}: excluded row without a reason")
        if row["label"] is None:
            expect(
                row["label_status"] in ("unknown", "excluded"),
                f"{row['id']}: unlabelled status changed",
            )

    protocol = json.loads(carried["protocol.json"])
    expect(
        study["protocol"]["predictions_sha256"] == protocol["predictions_sha256"],
        "the study's frozen predictions hash changed",
    )
    expect(
        study["protocol"]["sources"] == protocol["sources"],
        "the study's source map changed",
    )
    expect(
        study["protocol"]["primary_rule"] == PRIMARY_RULE,
        "the study's primary rule changed",
    )
    expect(
        study["protocol"]["domain"] == protocol["domain"], "the study's domain changed"
    )
    expect(
        study["protocol"]["snapshots"] == protocol["snapshots"],
        "the study's snapshot ledger changed",
    )
    expect(
        study["runtime"]["collector"] == COLLECTOR,
        "the study's collector identity changed",
    )
    expect(
        study["runtime"]["external_evidence"] == check_external_evidence(carried),
        "the study's raw-evidence reference changed",
    )

    derived = derive(rows, carried)
    for key in (
        "selection",
        "modes",
        "rules",
        "folds",
        "repeats",
        "disagreements",
        "length_check",
        "one_class",
        "bridge",
        "openings",
    ):
        expect(
            study[key] == derived[key],
            f"the study's {key} is stale or was edited by hand",
        )
    return {
        "study": STUDY,
        "publication": PUBLICATION["publication_commit"],
        "rows": len(rows),
        "eligible": len(eligible),
        "primary": len(primary),
        "carried_files": len(study["files"]),
        "linked_files": len(study["linked"]),
        "declarations": sum(len(value) for value in declarations.values()),
    }


def summarise(study: dict, projection_sha: str, manifest_sha: str) -> dict:
    return {
        "kind": study["kind"],
        "study": study["study"],
        "source_commit": study["source"]["publication_commit"],
        "source_base": study["source"]["publication_base"],
        "internal_merge": study["source"]["internal_merge"],
        "source_issue": study["source"]["source_issue"],
        "pull_request": study["source"]["pull_request"],
        "publication_files": study["closure"]["publication_files"],
        "copied_files": study["closure"]["copied_files"],
        "linked_files": study["closure"]["linked_files"],
        "projection_file": PROJECTION_FILE,
        "projection_sha256": projection_sha,
        "projection_tool_file": "tools/map-factory/integrate_outside_research.py",
        "source_manifest_file": MANIFEST_FILE,
        "source_manifest_sha256": manifest_sha,
        "freeze": {
            "name": study["freeze"]["name"],
            "frozen_at": study["freeze"]["frozen_at"],
            "predictions_sha256": study["freeze"]["predictions_sha256"],
            "retrospective": True,
            "frozen_before_observations": False,
            "observation_dates": "unknown",
        },
        "selected_queries": study["selection"]["eligible"],
        "primary_queries": study["selection"]["primary"],
        "rows": study["selection"]["queries"],
        "packages": study["selection"]["packages"],
        "modes": {
            mode: {
                "primary": record["primary"],
                "successes": record["successes"],
                "failures": record["failures"],
                "discrimination_estimable": record["discrimination_estimable"],
                "fitted": record["fitted"][FITTED_RULE]["counts"],
            }
            for mode, record in study["modes"].items()
        },
        "primary_fitted": study["rules"]["primary_stratum"][FITTED_RULE]["counts"],
        "same_edge_fitted": study["rules"]["same_edge"][FITTED_RULE]["counts"],
        "evidence_files_sha256": sha(
            canon(
                [[record["path"], record["sha256"]] for record in study["files"]]
            ).encode()
        ),
        "certificates": "none",
    }


CAPABILITY_LIMITS = {
    "road": "Counts do not prove direction, pathfinding or the player's ability to join. The real-roads path remains opt-in.",
    "ship": (
        "Not restricted by place names or ocean labels. Initial water is not stable water. A negative "
        "browser estimate is unknown because coarse sampling can miss a route."
    ),
    "air": (
        "Fixture airport fallbacks in the existing generator are not geographic evidence for arbitrary "
        "squares. Terrain clearance at high altitude and service remain unverified."
    ),
}
LEDGER_FILE = "capabilities.json"


def ledger_summary(study: dict, projection_sha: str, manifest_sha: str) -> dict:
    """The exact derived summary the renderer recomputes and the ledger carries."""
    return {
        "kind": study["kind"],
        "study": study["study"],
        "source_commit": study["source"]["publication_commit"],
        "source_base": study["source"]["publication_base"],
        "internal_merge": study["source"]["internal_merge"],
        "source_issue": study["source"]["source_issue"],
        "pull_request": study["source"]["pull_request"],
        "publication_files": study["closure"]["publication_files"],
        "copied_files": study["closure"]["copied_files"],
        "linked_files": study["closure"]["linked_files"],
        "projection_file": PROJECTION_FILE,
        "projection_sha256": projection_sha,
        "projection_tool_file": "tools/map-factory/integrate_outside_research.py",
        "projection_tool_sha256": sha(Path(__file__).resolve().read_bytes()),
        "source_manifest_file": MANIFEST_FILE,
        "source_manifest_sha256": manifest_sha,
        "freeze": {
            "name": study["freeze"]["name"],
            "frozen_at": study["freeze"]["frozen_at"],
            "predictions_sha256": study["freeze"]["predictions_sha256"],
            "retrospective": True,
            "frozen_before_observations": False,
            "observation_dates": "unknown",
        },
        "selected_queries": study["selection"]["eligible"],
        "primary_queries": study["selection"]["primary"],
        "rows": study["selection"]["queries"],
        "packages": study["selection"]["packages"],
        "modes": {
            mode: {
                "primary": record["primary"],
                "successes": record["successes"],
                "failures": record["failures"],
                "discrimination_estimable": record["discrimination_estimable"],
                "fitted": record["fitted"][FITTED_RULE]["counts"],
            }
            for mode, record in study["modes"].items()
        },
        "primary_fitted": study["rules"]["primary_stratum"][FITTED_RULE]["counts"],
        "same_edge_fitted": study["rules"]["same_edge"][FITTED_RULE]["counts"],
        "evidence_files_sha256": sha(
            canon(
                [[record["path"], record["sha256"]] for record in study["files"]]
            ).encode()
        ),
        "certificates": "none",
    }


def indent_block(value) -> str:
    text = json.dumps(value, indent=2)
    first, *rest = text.split("\n")
    return "\n".join([first, *("  " + line for line in rest)])


def update_ledger(summary: dict) -> None:
    """Add the one study's binding to the ledger without rewriting other bytes.

    The ledger is a Python-produced document with non-escaped Unicode and its own
    float formatting, so this edits the two exact places instead of reserialising
    entries the research study does not own.
    """
    path = ROOT / LEDGER_FILE
    raw = path.read_text()
    block = f'      "outside_research_studies": [\n        "{STUDY}"\n      ]'
    for capability, limits in CAPABILITY_LIMITS.items():
        bare = f'      "limits": {json.dumps(limits)}\n'
        with_comma = bare[:-1] + ",\n"
        if bare in raw:
            raw = raw.replace(bare, with_comma, 1)
        if f"{with_comma}{block}" not in raw:
            expect(with_comma in raw, f"{capability}: ledger limits line not found")
            raw = raw.replace(with_comma, f"{with_comma}{block}\n", 1)

    marker = '\n  "outside_research_studies": {'
    index = raw.find(marker)
    if index >= 0:
        head = raw[:index]
        if head.endswith(","):
            head = head[:-1]
        raw = head + "\n}\n"
    end = "\n  }\n}\n"
    expect(raw.endswith(end), "ledger tail is not the expected closing block")
    raw = (
        raw[: -len(end)]
        + '\n  },\n  "outside_research_studies": '
        + indent_block(summary)
        + "\n}\n"
    )
    path.write_text(raw)
    ledger = json.loads(raw)
    for capability in ("road", "ship", "air"):
        entry = next(
            item for item in ledger["capabilities"] if item["id"] == capability
        )
        expect(
            entry.get("outside_research_studies") == [STUDY],
            f"{capability}: the study reference was not written",
        )
    expect(
        ledger["outside_research_studies"] == summary,
        "the written ledger summary differs from the projection",
    )


def main() -> int:
    args = sys.argv[1:]
    if "--source" in args:
        source = Path(args[args.index("--source") + 1]).resolve()
        docs = publication_documents(source)
        projection, manifest = build_projection(docs)
        summary = verify(projection, carried_subset(docs), manifest)
        raw = (json.dumps(projection, indent=1) + "\n").encode()
        manifest_raw = (json.dumps(manifest, indent=1) + "\n").encode()
        (ROOT / MANIFEST_FILE).write_bytes(manifest_raw)
        (ROOT / PROJECTION_FILE).write_bytes(raw)
        summary = ledger_summary(
            projection["studies"][STUDY], sha(raw), sha(manifest_raw)
        )
        update_ledger(summary)
        print(
            f"wrote {MANIFEST_FILE} ({len(manifest_raw)} bytes, {sha(manifest_raw)}), "
            f"{PROJECTION_FILE} ({len(raw)} bytes, {sha(raw)}) and the ledger binding"
        )
        print(json.dumps(summary, indent=1))
        return 0

    manifest_raw = (ROOT / MANIFEST_FILE).read_bytes()
    manifest = json.loads(manifest_raw)
    carried = read_carried()
    projection_raw = (ROOT / PROJECTION_FILE).read_bytes()
    projection = json.loads(projection_raw)
    summary = verify(projection, carried, manifest)
    if "--check" in args:
        print(
            f"outside research projection is current: {sha(projection_raw)} "
            f"(manifest {sha(manifest_raw)})"
        )
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
