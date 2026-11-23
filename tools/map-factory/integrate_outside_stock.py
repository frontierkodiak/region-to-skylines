"""Integrate the accepted outside-stock and road-budget publication as one typed study.

This reads archived bytes only. It never runs the study's frozen scorer, its
post-control scorer, the audit, the collectors, the model, a native game or a
browser, and it never rejudges an old label. It re-checks the publication's
exact 142-file scope and the integrity record over its 141 members, re-derives
the saved population, request, label, bridge, control, intervention, runtime and
cleanup arithmetic the publication itself carries, then writes one projection
the ledger page renders under Road, Ship and Air.

The study is evidence only: not pooled with the outside-query, rail or native
studies, not a qualification, not a promise, not a certificate and not a live
rule. Saved-label and count arithmetic plus integrity reconstruction are the only
"replays" here; no archived executable or outcome function is imported.

Three modes:

    python3 tools/map-factory/integrate_outside_stock.py --source <dir>
        Derive the manifest and projection from an exact checkout of the
        publication's 142 files (a worktree at the publication commit, or the
        same files read from Git blobs; a plain `git archive` omits tools/**
        because .gitattributes marks it export-ignore).

    python3 tools/map-factory/integrate_outside_stock.py
        Re-derive both documents from the carried evidence and the committed
        manifest, then write them. Deterministic; sibling studies and the four
        retained native certificates are untouched.

    python3 tools/map-factory/integrate_outside_stock.py --check
        Re-derive and refuse any committed projection, manifest, carried byte,
        ledger binding or derived table that differs.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tools/map-factory/capability-evidence"
STUDY = "outside-stock-budget-v1"
PREFIX = f"tools/map-factory/capability-evidence/{STUDY}"
MANIFEST_FILE = "tools/map-factory/capability-evidence/outside-stock-sources.json"
PROJECTION_FILE = "tools/map-factory/capability-evidence/outside-stock-studies.json"
LEDGER_FILE = "capabilities.json"
LEDGER_KEY = "outside_stock_studies"

MODES = ("road", "ship", "air")
RULES = ("lane:any_lane:forbidden", "weak_component")
PRIMARY_RULE = "lane:any_lane:forbidden"
REFERENCE_RULE = "weak_component"
BUDGETS = (100000, 200000, 1000000)

PUBLICATION = {
    "study": STUDY,
    "kind": "outside_stock_budget_study",
    "title": "Frozen outside-query stock validation and road budget limits",
    "publication_commit": "d745b14e3e207ee67f91033811958a2934fb38a4",
    "publication_base": "030db86ce470b972b6ef3462a2698744dff40ebb",
    "accepted_base": "030db86ce470b972b6ef3462a2698744dff40ebb",
    "internal_merge": "62b48a01a195f7632747fe52c72b348539dc7f8a",
    "pull_request": 89,
    "branch": "PL-1294-stock-budget",
    "source_issue": "01a20799-865c-75cc-bdc1-05a81193aff4",
    "review_pass": "01a2086c-06d0-7461-9bf1-65fbd1b478d2",
    "engineering_note": "01a2086a-f275-7104-87a9-8215b81a07e9",
    "parent_acceptance": "01a20870-8dad-7705-8ab8-c81868a3e7d1",
    "superseded_review": "01a20867-f3e6-778e-abfc-9610a7f2c922",
    "superseded_head": "7b5b4ab4214cd6027844dd7ed7f13cd414ab69e0",
    "history": (
        "The earlier 7b5b4ab report was rejected for a missing holdout-03 graph-drift statement and "
        "wrong reference-disagreement IDs. The corrected d745 report is the accepted source; that "
        "rejection stays recorded and is not erased by the later pass."
    ),
    "native_sources": {
        "outside_query_model": "030db86ce470b972b6ef3462a2698744dff40ebb",
        "stock_holdout_catalog": "914c153687106197e5f3a745d3ff7e181181ea8a",
    },
}

# The 31 files carried here byte for byte (integrity.json is the 32nd committed
# file of the prefix and pins the other 141 members).
CARRIED = {
    "JOURNAL.md": "document",
    "README.md": "document",
    "RESULTS.md": "document",
    "analysis/audit.py": "tool",
    "analysis/evaluate.py": "tool",
    "analysis/frozen-scorer-failure.log": "retained_failure",
    "analysis/header_coverage.py": "tool",
    "analysis/retain.py": "tool",
    "analysis/schema-fix.diff.gz": "schema_repair_diff",
    "analysis/source-fix.json": "provenance",
    "analysis/test_wire_schema.py": "test",
    "analysis/verify.py": "tool",
    "audit.json.gz": "report",
    "audit_processes.py": "tool",
    "build.json": "provenance",
    "build_study.py": "tool",
    "catalog-membership.json": "provenance",
    "collect.py": "tool",
    "control-stock-1-networks.json.gz": "control_graph",
    "control-stock-2-networks.json.gz": "control_graph",
    "evaluate.py": "tool",
    "evaluation.json.gz": "report",
    "header-coverage.json": "provenance",
    "history/pre-query-freeze.json.gz": "history",
    "integrity.json": "integrity",
    "prior-stock-catalogs.json": "provenance",
    "prior-stock-freeze.json": "provenance",
    "retention.json": "provenance",
    "run_one.py": "tool",
    "stock-exclusion-source.json": "provenance",
    "study.py": "tool",
    "test_study.py": "test",
}

# The 110 bulky members served as immutable blobs at the publication commit:
# the frozen plan, the frozen feature dump, the three preparation archives and
# every retained raw gzip. No archive is shipped inside the product.
LINKED_BULK = {
    "features.json.gz": "frozen_features",
    "freeze.json": "frozen_plan",
    "pre-native-checksum-correction.zip": "preparation_archive",
    "pre-native-preparation-v0.zip": "preparation_archive",
    "pre-native-preparation-v1.zip": "preparation_archive",
}
RAW_ROLE = {
    "game.log.gz": "raw_game_log",
    "gpu.csv.gz": "raw_gpu_sample",
    "networks.json.gz": "raw_network_snapshot",
    "networks-post.json.gz": "raw_network_snapshot_post",
    "observation.json.gz": "raw_observation",
    "query-freeze.json.gz": "raw_query_freeze",
    "audit.py.txt.gz": "raw_process_audit",
    "launch.json.gz": "raw_driver_launch",
    "completion.json.gz": "raw_driver_completion",
    "collector.log.gz": "raw_driver_log",
    "auditor-launch.json.gz": "raw_auditor_launch",
    "audit-completion.json.gz": "raw_auditor_completion",
    "audit-source-freeze.json.gz": "raw_auditor_source_freeze",
}
DOCUMENTS = ("README.md", "RESULTS.md", "JOURNAL.md")

EXPECTED_PUBLICATION_FILES = 142
EXPECTED_INTEGRITY_MEMBERS = 141
EXPECTED_CARRIED = len(
    CARRIED
)  # 32 present files: 31 evidence files plus integrity.json
EXPECTED_LINKED = 110
EXPECTED_RAW_FILES = 105

# Population, as the report, the inventory and the header recheck state it.
EXPECTED_POPULATION = {
    "installed": 105,
    "excluded_packages": 13,
    "excluded_hashes": 21,
    "eligible": 92,
    "supported": 28,
    "abstaining": 64,
    "decode_errors": 23,
}

SELECTED_CASES = {
    "holdout-01": {
        "file": "CCP Map 1.crp",
        "supported": True,
        "reason": (
            "first road positive, first road negative, first ship positive and first air positive; "
            "first package in sorted order"
        ),
    },
    "holdout-02": {
        "file": "DN Fisher Enclave.crp",
        "supported": True,
        "reason": "first ship negative; also carries road and air requests",
    },
    "holdout-03": {
        "file": "CL Roslyn Peninsula.crp",
        "supported": True,
        "reason": "first air negative; also carries road and ship requests",
    },
    "holdout-04": {
        "file": "CCMP2 Desert Map 2.crp",
        "supported": False,
        "reason": "first sorted unsupported package; metadata only, null predictions",
    },
    "holdout-05": {
        "file": "CCMP2 Euro Map 1.crp",
        "supported": False,
        "reason": "second sorted unsupported package; metadata only, null predictions",
    },
}
CONTROL_CASES = {"stock-1": "Asanu", "stock-2": "Hanami"}
OPENINGS = (
    "stock-1",
    "stock-2",
    "holdout-01",
    "holdout-02",
    "holdout-03",
    "holdout-04",
    "holdout-05",
    "budget-01",
    "budget-02",
)
INTERVENTION_CASES = ("budget-01", "budget-02")

EXPECTED_REQUESTS = 84
EXPECTED_OBSERVED = 78
EXPECTED_UNKNOWN_CONTROLS = 6
EXPECTED_STOCK_REQUESTS = 48
EXPECTED_CONTROL_REQUESTS = 12
EXPECTED_INTERVENTION_REQUESTS = 24
EXPECTED_SELECTED_REQUESTS = 48
EXPECTED_NULL_PACKAGE_MODE_RECORDS = 6

EXPECTED_PRIMARY = {
    "road": (12, 0, 12, 0),
    "ship": (8, 0, 4, 0),
    "air": (8, 0, 4, 0),
}
EXPECTED_PRIMARY_TOTAL = (28, 0, 20, 0)
EXPECTED_WEAK = {
    "road": (12, 12, 0, 0),
    "ship": (8, 0, 4, 0),
    "air": (8, 0, 4, 0),
}
EXPECTED_SNAPSHOT_PRIMARY = (8, 0, 8, 0)
EXPECTED_SNAPSHOT_WEAK = (8, 8, 0, 0)
EXPECTED_SNAPSHOT_REQUESTS = 16
# One package tag applies to every request of that package, in every mode: the
# overlap is why these counts (84) must never be summed to 48 samples.
EXPECTED_SELECTION_TAGS = {
    "road:success:distinct_edge": 12,
    "road:no_path:distinct_edge": 12,
    "ship:success:distinct_edge": 12,
    "ship:no_path:distinct_edge": 18,
    "air:success:distinct_edge": 12,
    "air:no_path:distinct_edge": 18,
}
# Bridge: ship and air endpoints move in height at opening, never horizontally.
EXPECTED_BRIDGE = {
    "holdout-01": {"max_vertical": 33.029134, "fields": ("a", "b")},
    "holdout-02": {"max_vertical": 161.935462, "fields": ("a", "b")},
    "holdout-03": {"max_vertical": 8.026451, "fields": ("a", "b")},
}
EXPECTED_ROSLYN_PREFAB_SEGMENTS = (428, 8772, 24652, 35418)
EXPECTED_ROSLYN_AIR_SEGMENTS = (17396, 20340, 21466, 26056, 29446, 32716, 35098)
EXPECTED_ROSLYN_SHIP_SEGMENTS = (9993, 31169)
EXPECTED_BUDGET_AIR_SEGMENTS = (5973, 5974)
EXPECTED_PRE_POST_CHANGES = (
    "holdout-03/air/002",
    "holdout-03/air/007",
    "holdout-03/road/006",
)
EXPECTED_OPENING_FINGERPRINT_MISMATCH_REPORTED = 17
EXPECTED_OPENING_FINGERPRINT_MISMATCH_REDERIVED = 18
EXPECTED_PHASE_INVENTORIES = 25
EXPECTED_PROCESS_IDENTITIES = 45
EXPECTED_INSTALLED_CRP_RECEIPTS = 9
EXPECTED_RAW_REPORTS = 2

# The accepted stock freeze this study copies its declared exclusion source from.
STOCK_SOURCE = {
    "commit": "914c153687106197e5f3a745d3ff7e181181ea8a",
    "path": "tools/map-factory/capability-evidence/rail-stock-holdout-v1/freeze.json",
    "carried_copy": "stock-exclusion-source.json",
}
BUILD_RECEIPT = {
    "dll_sha256": "7cfb994191efd7a7b21eeabee283100e8b45627836bf65b621e04b1a134f7063",
    "game_executable_sha256": "a18607b230f20b5653379a8debb6d5fe69e3ccd45863798f2e2a5ec403b8a9ca",
    "game_assemblies": 8,
    "sources": 17,
}
FRAMED_PROTOCOL = {
    "api": "PathManager.CreatePath",
    "entry": "NewGameFromMap",
    "seed": 857,
    "default_max_length": 100000,
    "budgets": list(BUDGETS),
    "mode_vehicle": {"road": "Car", "ship": "Ship", "air": "Plane"},
    "native_modes": {"road": "car", "ship": "ship", "air": "plane"},
    "category_by_mode": {"road": "PassengerCar", "ship": "All", "air": "All"},
    "lane_types": {
        "road": ["Vehicle"],
        "ship": ["CargoVehicle", "TransportVehicle", "Vehicle"],
        "air": ["CargoVehicle", "TransportVehicle", "Vehicle"],
    },
    "invert_traffic": False,
    "offsets": [0, 255],
    "launch_args": ["--noWorkshop"],
    "mods_enabled": True,
    "unit_limit": "chord geometry and native cost/budget are not identified units",
    "candidate_order": (
        "distinct edge first, from/to lexicographic; allocation IDs are references/order only"
    ),
    "query_selection": (
        "first four of each primary class, fill lexical order to eight; reserve first reciprocal "
        "pair before class fill"
    ),
    "matching": (
        "without replacement; nearest primary predicted successful directed chord sum; tie "
        "artifact/request hash"
    ),
    "labels": {
        "success": "complete=true, released=true, success=true; returned first/last exactly requested",
        "no_path": "complete=true, released=true, success=false; this literal request only",
        "unknown": "error, missing, incomplete, unreleased, or endpoint mismatch",
    },
}

SCOPE = (
    "One prospective stock validation and one separate retained-road budget intervention on unchanged "
    "Cities: Skylines packages. The stock half asks whether the frozen lane:any_lane:forbidden rule and "
    "the weak_component reference predict new literal outside-connection requests on packages never "
    "opened in the earlier cohorts. The budget half repeats eight old road requests under three "
    "predeclared requested maxLength floats. Neither half is a product port, a qualification, a "
    "certificate, a map repair or a promise."
)

METHOD = (
    "The stock catalog and the frozen rules, selected requests, predictions and controls were written "
    "before any new native request; the first Asanu control opening then failed before a single path "
    "query and was retained without retry. Eight further openings produced the stock labels and the "
    "budget repeats. This ledger re-checks the archived bytes, reconstructs the integrity table, and "
    "re-derives the saved population, request, label, bridge, control, intervention, runtime and "
    "cleanup arithmetic. It does not run the frozen scorer, the post-control scorer, the audit, the "
    "collectors or the game, and it does not rejudge or replace an old label."
)

LIMITS = (
    "Descriptive and status-scoped: 48 correlated new stock requests agree with the primary rule "
    "28 TP / 0 FP / 20 TN / 0 FN, but all three modes remain UNQUALIFIED because the retained "
    "all-controls completion requirement fails on the first Asanu opening. Only 16 road requests on the "
    "first two packages have exact export/native field identity; the other 32 requests are not exact "
    "bridge matches. The weak reference's 12 road false positives show that weak connectivity cannot "
    "represent lane-direction restrictions; they are descriptive disagreements, not geographic "
    "negatives. Ship and air carry one class on some packages, so their arithmetic precision of 1 "
    "carries no information there. The budget intervention is a separate correlated observation "
    "stratum, not a holdout and not a rejudge: four retained road errors fail at 100000, 200000 and "
    "1000000, and one matched old-success request fails at 100000 and succeeds at both larger "
    "budgets. That is a measured response, not an identified search-budget mechanism, cost or metre "
    "conversion; all four error mechanisms remain Unknown. The requested floats and the returned "
    "flags=8/length sentinel are not proof of native exhaustion. The Pittsburgh 093 group's all-mode "
    "graph changed during its opening, so it is not a clean single-variable trial. This is not "
    "qualification, global accuracy, a geographic 'no', a service, spawning or sustained-navigation "
    "evidence, or a promise, and it does not transfer to the current runtime checker, the live "
    "estimate, a certificate or any other study. File identity is not memory attestation or a strict "
    "no-mods claim; dynamic exclusions, plugin state and the three DLL errors remain limitations. "
    "Cleanup coverage is a historical statement about named PID/start identities, not a description "
    "of blade's current slot or process state. Stock packages carry no invented physical-input or CPU "
    "lineage; old exports retain only their exact CRP and old receipts. Observation windows are the "
    "recorded driver start/finish times, and they are not replaced by the freeze or publication time."
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
    for relative in CARRIED:
        path = EVIDENCE / STUDY / relative
        expect(path.is_file(), f"missing carried evidence {relative}")
        carried[relative] = path.read_bytes()
    return carried


def publication_documents(source: Path) -> dict[str, bytes]:
    """Every file the publication commit adds, byte for byte."""
    if not source.is_dir():
        fail(f"publication source is not a directory: {source}")
    docs = {}
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix()
        if "__pycache__" in relative.split("/"):
            fail(f"publication source contains a bytecode cache: {relative}")
        docs[relative] = path.read_bytes()
    expect(
        len(docs) == EXPECTED_PUBLICATION_FILES,
        f"publication is {len(docs)} files, expected {EXPECTED_PUBLICATION_FILES}",
    )
    expect(set(CARRIED) <= set(docs), "publication is missing a carried file")
    expect(
        set(LINKED_BULK) <= set(docs),
        "publication is missing a linked bulk document",
    )
    raw = sorted(name for name in docs if name.startswith("raw/"))
    expect(len(raw) == EXPECTED_RAW_FILES, "publication raw set changed")
    for name in raw:
        role = raw_role(name)
        expect(role is not None, f"raw file has no declared role: {name}")
    linked = sorted(set(LINKED_BULK) | set(raw))
    expect(len(linked) == EXPECTED_LINKED, "linked file count changed")
    expect(
        set(docs) == set(CARRIED) | set(linked),
        "carried and linked do not partition the publication",
    )
    return docs


def raw_role(name: str) -> str | None:
    if not name.startswith("raw/"):
        return None
    base = name.rsplit("/", 1)[-1]
    return RAW_ROLE.get(base)


def file_role(relative: str) -> str:
    if relative in CARRIED:
        return CARRIED[relative]
    if relative in LINKED_BULK:
        return LINKED_BULK[relative]
    role = raw_role(relative)
    expect(role is not None, f"no role for {relative}")
    return role


def check_manifest(manifest: dict, carried: dict[str, bytes]) -> dict:
    expect(manifest.get("schema") == 1, "outside-stock source manifest schema changed")
    expect(
        list(manifest.get("publications", {})) == [STUDY],
        "outside-stock source manifest lost its publication",
    )
    publication = manifest["publications"][STUDY]
    expect(
        publication["commit"] == PUBLICATION["publication_commit"],
        "source manifest names another publication",
    )
    expect(publication["prefix"] == PREFIX, "source manifest prefix changed")
    files = publication["files"]
    expect(len(files) == EXPECTED_PUBLICATION_FILES, "publication file scope changed")
    expect(
        sorted(publication["copied"]) == sorted(CARRIED), "carried-file list changed"
    )
    linked = publication["linked"]
    expect(len(linked) == EXPECTED_LINKED, "linked-file list changed")
    expect(
        sorted(linked)
        == sorted(set(LINKED_BULK) | {n for n in files if n.startswith("raw/")}),
        "linked-file list does not name every bulky member",
    )
    expect(
        sorted(publication["copied"] + linked) == sorted(files),
        "carried and linked files do not partition the publication",
    )
    expect(
        publication.get("integrity_file") == "integrity.json"
        and publication.get("publication_files") == EXPECTED_PUBLICATION_FILES
        and publication.get("integrity_members") == EXPECTED_INTEGRITY_MEMBERS,
        "publication closure header changed",
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
        expect(
            record.get("role") == file_role(relative), f"role changed for {relative}"
        )
        if relative in CARRIED:
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
        present == sorted(CARRIED),
        "carried prefix has files outside the publication scope",
    )
    return files


def load_gz(carried: dict[str, bytes], name: str):
    return json.loads(gzip.decompress(carried[name]))


def check_integrity(
    carried: dict[str, bytes], files: dict[str, dict], docs: dict[str, bytes] | None
) -> dict:
    """Reconstruct the publication's own closed 141-file hash table.

    The carried bytes are hashed directly. A linked member is re-hashed only when
    a full publication checkout is at hand (`--source`); otherwise its pinned
    manifest entry is checked against every carried document that declares it.
    """
    integrity = json.loads(carried["integrity.json"])
    expect(
        integrity["scope"]
        == "closed file key set; excludes only integrity.json itself and Python bytecode caches",
        "integrity scope changed",
    )
    table = integrity["files"]
    expect(
        len(table) == EXPECTED_INTEGRITY_MEMBERS,
        f"integrity record is {len(table)} members, expected {EXPECTED_INTEGRITY_MEMBERS}",
    )
    expected_names = set(files) - {"integrity.json"}
    expect(
        set(table) == expected_names,
        "integrity record does not name exactly the publication minus itself",
    )
    for relative, declared in table.items():
        expect(
            isinstance(declared, str) and len(declared) == 64,
            f"{relative}: malformed integrity hash",
        )
        expect(
            declared == files[relative]["sha256"],
            f"{relative}: integrity hash differs from the manifest",
        )
        if relative in carried:
            expect(
                sha(carried[relative]) == declared, f"carried bytes changed: {relative}"
            )
        elif docs is not None:
            expect(
                sha(docs[relative]) == declared,
                f"linked publication bytes changed: {relative}",
            )
    if docs is not None:
        expect(
            set(docs) - {"integrity.json"} == expected_names,
            "publication checkout is not exactly the manifest file set",
        )
        for relative, raw in docs.items():
            if relative == "integrity.json":
                continue
            expect(
                sha(raw) == files[relative]["sha256"],
                f"publication byte differs from the manifest: {relative}",
            )
    return integrity


def cross_declarations(
    carried: dict[str, bytes], files: dict[str, dict], docs: dict[str, bytes] | None
) -> dict:
    """Every hash a carried document declares for another publication file.

    A changed source document cannot be re-pinned by editing the manifest alone:
    the publication's retention, source-fix, evaluation, audit, build and header
    records each name those bytes, and those documents are themselves pinned.
    """
    declared: dict[str, list[str]] = {}

    def add(name: str, where: str, value, document: str) -> None:
        expect(isinstance(value, str) and len(value) == 64, f"{where} declares no hash")
        declared.setdefault(name, []).append(document)
        expect(
            value == files[name]["sha256"],
            f"{name}: {where} does not match the publication manifest",
        )

    integrity = json.loads(carried["integrity.json"])
    for name, value in integrity["files"].items():
        add(name, f"integrity.json files.{name}", value, "integrity.json")

    retention = json.loads(carried["retention.json"])
    raw_members = {n[len("raw/") : -len(".gz")] for n in files if n.startswith("raw/")}
    expect(
        set(retention["files"]) == raw_members,
        "retention record does not cover exactly the retained raw files",
    )
    for raw_name, record in retention["files"].items():
        retained = record["retained"]
        add(
            retained,
            f"retention.json files.{raw_name}.retained",
            record["retained_sha256"],
            "retention.json",
        )
        expect(
            retained == f"raw/{raw_name}.gz",
            f"{raw_name}: retention path is not its own compressed member",
        )
        expect(
            record["raw_bytes"] > 0 and len(record["raw_sha256"]) == 64,
            f"{raw_name}: retention raw record is malformed",
        )
    expect(
        sorted(retention["reports"]) == ["audit", "evaluation"],
        "retention report set changed",
    )
    for name, record in retention["reports"].items():
        add(
            record["retained"],
            f"retention.json reports.{name}",
            record["retained_sha256"],
            "retention.json",
        )

    source_fix = json.loads(carried["analysis/source-fix.json"])
    add(
        "freeze.json",
        "analysis/source-fix.json frozen_plan_sha256",
        source_fix["frozen_plan_sha256"],
        "analysis/source-fix.json",
    )
    add(
        "analysis/frozen-scorer-failure.log",
        "analysis/source-fix.json frozen_scorer_failure_sha256",
        source_fix["frozen_scorer_failure_sha256"],
        "analysis/source-fix.json",
    )
    add(
        "analysis/schema-fix.diff.gz",
        "analysis/source-fix.json diff_retained_sha256",
        source_fix["diff_retained_sha256"],
        "analysis/source-fix.json",
    )
    add(
        "analysis/evaluate.py",
        "analysis/source-fix.json evaluator_sha256",
        source_fix["evaluator_sha256"],
        "analysis/source-fix.json",
    )
    add(
        "evaluate.py",
        "analysis/source-fix.json base_evaluator_sha256",
        source_fix["base_evaluator_sha256"],
        "analysis/source-fix.json",
    )
    expect(
        source_fix["analysis_sources"]
        == {
            f"{PREFIX}/analysis/{name}": files[f"analysis/{name}"]["sha256"]
            for name in (
                "audit.py",
                "evaluate.py",
                "header_coverage.py",
                "retain.py",
                "test_wire_schema.py",
                "verify.py",
            )
        },
        "source-fix analysis source key set or bytes changed",
    )
    expect(
        source_fix["source_key_set"] == sorted(source_fix["analysis_sources"]),
        "source-fix source key set changed",
    )
    diff_raw = sha(gzip.decompress(carried["analysis/schema-fix.diff.gz"]))
    expect(
        diff_raw == source_fix["diff_raw_sha256"],
        "the carried schema-repair diff does not decompress to its recorded bytes",
    )

    evaluation = load_gz(carried, "evaluation.json.gz")
    add(
        "freeze.json",
        "evaluation.json.gz freeze_sha256",
        evaluation["freeze_sha256"],
        "evaluation.json.gz",
    )
    expect(
        set(evaluation["raw_integrity"]) == raw_members,
        "evaluation raw integrity does not cover the retained raw files",
    )
    for raw_name, raw_hash in evaluation["raw_integrity"].items():
        retained = f"raw/{raw_name}.gz"
        add(
            retained,
            f"evaluation.json.gz raw_integrity.{raw_name}",
            files[retained]["sha256"],
            "evaluation.json.gz",
        )
        expect(
            raw_hash == retention["files"][raw_name]["raw_sha256"],
            f"{raw_name}: evaluation raw hash and retention raw hash differ",
        )

    audit = load_gz(carried, "audit.json.gz")
    add(
        "analysis/audit.py",
        "audit.json.gz source_sha256",
        audit["source_sha256"],
        "audit.json.gz",
    )
    header = json.loads(carried["header-coverage.json"])
    add(
        "analysis/header_coverage.py",
        "header-coverage.json source_sha256",
        header["source_sha256"],
        "header-coverage.json",
    )

    build = json.loads(carried["build.json"])
    expect(
        build["build_receipt"]["dll_sha256"] == BUILD_RECEIPT["dll_sha256"]
        and build["build_receipt"]["game_executable_sha256"]
        == BUILD_RECEIPT["game_executable_sha256"],
        "build receipt identity changed",
    )
    expect(
        len(build["build_receipt"]["game_assemblies"])
        == BUILD_RECEIPT["game_assemblies"]
        and len(build["original_sources"]) == BUILD_RECEIPT["sources"]
        and build["original_sources"]
        == {key: value for key, value in build["original_sources"].items()},
        "build receipt source/assembly key sets changed",
    )
    expect(
        build["build_receipt"]["sources"]["NetworkOps.cs"]
        != build["original_sources"]["NetworkOps.cs"],
        "the staged collector no longer differs from its original",
    )
    for token in ("PathManager", "CreatePath", "maxLength", "m_currentBuildIndex"):
        expect(
            token in build["staged_NetworkOps"],
            f"the staged collector no longer binds {token}",
        )

    expect(
        sha(carried[STOCK_SOURCE["carried_copy"]])
        == json.loads(carried["integrity.json"])["files"][STOCK_SOURCE["carried_copy"]],
        "the carried stock source copy is not its own integrity member",
    )
    return {name: sorted(set(entries)) for name, entries in declared.items()}


def check_stock_source(carried: dict[str, bytes]) -> dict:
    """The accepted eleven-package stock freeze, copied byte for byte."""
    copy = carried[STOCK_SOURCE["carried_copy"]]
    expect(
        carried["prior-stock-freeze.json"] == copy,
        "the two carried copies of the accepted stock freeze differ",
    )
    stock = json.loads(copy)
    expect(
        stock["source"] == "49cf49516f4aa8b24a154d9923c1a6fd149bf1a3",
        "the accepted stock freeze names another study source",
    )
    expect(
        stock["native_source"] == "1a0e45c65745ba5f05cf22f947da2e88fed25277"
        and stock["query_source"] == "364628b81701c134e3f469f9e175c4fe40f7a311",
        "the accepted stock freeze names another native or query source",
    )
    expect(
        len(stock["inventory"]) == 105 and len(stock["selected"]) == 10,
        "the accepted stock freeze inventory changed",
    )
    expect(
        len(stock["excluded_hashes"]) == 11
        and sorted(stock["excluded_hashes"]) == sorted(set(stock["excluded_hashes"])),
        "the accepted stock exclusion list changed",
    )
    repository = ROOT / STOCK_SOURCE["path"]
    if repository.is_file():
        expect(
            repository.read_bytes() == copy,
            "the carried stock source copy differs from the accepted repository file",
        )
    return {
        "publication_commit": STOCK_SOURCE["commit"],
        "path": STOCK_SOURCE["path"],
        "carried_copy": STOCK_SOURCE["carried_copy"],
        "carried_sha256": sha(copy),
        "source_commit": stock["source"],
        "native_source": stock["native_source"],
        "query_source": stock["query_source"],
        "inventory": len(stock["inventory"]),
        "excluded_hashes": len(stock["excluded_hashes"]),
        "selected": len(stock["selected"]),
        "repository_bytes_equal": repository.is_file(),
    }


def check_population(carried: dict[str, bytes]) -> dict:
    header = json.loads(carried["header-coverage.json"])
    expect(
        header["scope"].startswith(
            "read_any header-only recheck of unchanged bytes after capture"
        ),
        "header recheck scope changed",
    )
    packages = header["packages"]
    expect(
        len(packages) == EXPECTED_POPULATION["installed"],
        "installed package count changed",
    )
    expect(
        len({p["sha256"] for p in packages}) == len(packages),
        "installed inventory contains a duplicate package hash",
    )
    excluded = [p for p in packages if p["pre_query_exclusion"]]
    supported = [p for p in packages if p["pre_query_supported"]]
    abstaining = [
        p
        for p in packages
        if not p["pre_query_exclusion"] and not p["pre_query_supported"]
    ]
    decode = [
        p
        for p in abstaining
        if (p["pre_query_missing"] or [None])[0]
        == "ValueError: Encoded array run exceeds its declared size"
    ]
    blank = [p for p in packages if "blankCO" in (p["pre_query_exclusion"] or [])]
    counts = {
        "installed": len(packages),
        "excluded_packages": len(excluded),
        "excluded_hashes": 0,
        "eligible": len(packages) - len(excluded),
        "supported": len(supported),
        "abstaining": len(abstaining),
        "decode_errors": len(decode),
    }
    expect(
        counts == {**EXPECTED_POPULATION, "excluded_hashes": counts["excluded_hashes"]}
        or True,
        "unreachable",
    )
    for key, value in EXPECTED_POPULATION.items():
        if key == "excluded_hashes":
            continue
        expect(
            counts[key] == value, f"population {key} is {counts[key]}, expected {value}"
        )
    expect(
        len(blank) == 1 and blank[0]["file"] == "CO.crp",
        "blank CO is not the editor package",
    )
    expect(
        sum(len(p["pre_query_missing"] or []) for p in abstaining) > 0,
        "abstaining packages record no missing model inputs",
    )

    stock = json.loads(carried["stock-exclusion-source.json"])
    old = set(stock["excluded_hashes"])
    pl1239 = {
        p["sha256"]
        for p in packages
        if "PL-1239-selected-including-metadata" in (p["pre_query_exclusion"] or [])
    }
    controls = {
        p["sha256"]
        for p in packages
        if "PL-1239-controls" in (p["pre_query_exclusion"] or [])
    }
    expect(
        len(pl1239) == 10 and len(controls) == 2,
        "the PL-1239 exclusion tags no longer cover ten selected and two control packages",
    )
    exclusions = {}
    for digest_value in old:
        exclusions[digest_value] = (
            ["PL-1239-controls"]
            if digest_value in controls
            else ["old_geographic_cohort"]
        )
    for digest_value in pl1239:
        exclusions[digest_value] = ["PL-1239-selected-including-metadata"]
    expect(
        len(exclusions) == EXPECTED_POPULATION["excluded_hashes"],
        "union exclusion set changed",
    )
    expect(
        set(exclusions) == old | pl1239,
        "union exclusion set is not the accepted cohort plus the PL-1239 cases",
    )
    counts["excluded_hashes"] = len(exclusions)
    expect(
        counts["excluded_hashes"] == EXPECTED_POPULATION["excluded_hashes"],
        "excluded hash count changed",
    )
    normalized = [
        {
            "file": p["file"],
            "sha256": p["sha256"],
            "crp_format": p["crp_format"],
            "exclusion": p["pre_query_exclusion"] or [],
            "supported": bool(p["pre_query_supported"]),
            "missing": p["pre_query_missing"] or [],
        }
        for p in packages
    ]
    return {
        "counts": counts,
        "formats": header["formats"],
        "exclusions": dict(sorted(exclusions.items())),
        "blank_co": "CO.crp",
        "packages": normalized,
        "by_file": {p["file"]: p for p in normalized},
    }


def check_selection(carried: dict[str, bytes], population: dict) -> dict:
    catalog = json.loads(carried["catalog-membership.json"])
    expect(
        catalog["catalog_source_commit"]
        == PUBLICATION["native_sources"]["stock_holdout_catalog"],
        "catalog source commit changed",
    )
    expect(
        len(catalog["packages"]) == 11,
        "the accepted stock catalog lost a package",
    )
    expect(
        catalog["complete_bindings"] and len(catalog["complete_bindings"]) == 22,
        "catalog complete bindings changed",
    )
    for slug, record in catalog["packages"].items():
        expect(
            isinstance(record["sha256"], str)
            and len(record["sha256"]) == 64
            and record["bytes"] > 0,
            f"{slug}: catalog package is malformed",
        )
    from_controls = {
        "stock-1": catalog["packages"]["stock-1"],
        "stock-2": catalog["packages"]["stock-2"],
    }
    from_controls_files = {
        "stock-1": "AP Asanu Beach.crp",
        "stock-2": "AP Hanami Bay.crp",
    }
    for case, record in from_controls.items():
        expect(
            record["sha256"]
            == population["by_file"][from_controls_files[case]]["sha256"],
            f"{case}: installed control package differs from the accepted catalog",
        )
    prior = json.loads(carried["prior-stock-freeze.json"])
    expect(
        prior["frozen_at"] and prior["query_ids"] and prior["selected"],
        "the accepted stock freeze lost its frozen selection",
    )
    return {"catalog": catalog, "controls": from_controls}


def check_evaluation(carried: dict[str, bytes], population: dict) -> dict:
    evaluation = load_gz(carried, "evaluation.json.gz")
    expect(evaluation["schema"] == 1, "evaluation schema changed")
    rows = evaluation["holdout_rows"]
    expect(len(rows) == 102, "evaluation holdout rows changed")
    ruled = [r for r in rows if "rule" in r]
    expect(
        len(ruled) == 96
        and len({r["query_id"] for r in ruled}) == EXPECTED_STOCK_REQUESTS,
        "the stock request set changed",
    )
    nulls = [r for r in rows if "rule" not in r]
    expect(len(nulls) == 6, "the control row set changed")
    expect(
        sorted(r["rule"] for r in ruled).count(PRIMARY_RULE) == EXPECTED_STOCK_REQUESTS,
        "a stock request lacks its primary prediction",
    )
    expect(
        sorted(r["rule"] for r in ruled).count(REFERENCE_RULE)
        == EXPECTED_STOCK_REQUESTS,
        "a stock request lacks its reference prediction",
    )
    for row in ruled:
        expect(row["label"] in ("success", "no_path", "unknown"), "stock label changed")
        expect(row["prediction"] in ("success", "no_path"), "stock prediction changed")
        expect(
            row["qualified_mode"] is False,
            "a stock row now claims a qualified mode",
        )
    by_case = {}
    for row in ruled:
        by_case.setdefault(row["case_id"], set()).add(row["query_id"])
    expect(
        sorted(by_case) == ["holdout-01", "holdout-02", "holdout-03"],
        "the queried stock packages changed",
    )
    for case, expected_file in SELECTED_CASES.items():
        record = population["by_file"][expected_file["file"]]
        expect(
            record["supported"] is expected_file["supported"],
            f"{case}: support flag changed",
        )
        if expected_file["supported"]:
            expect(
                case in by_case, f"{case}: supported selected package has no queries"
            )
        else:
            expect(
                case not in by_case, f"{case}: unsupported package now carries queries"
            )

    primary = {mode: [0, 0, 0, 0] for mode in MODES}
    reference = {mode: [0, 0, 0, 0] for mode in MODES}
    snapshot = {rule: [0, 0, 0, 0] for rule in RULES}
    tags = {tag: 0 for tag in EXPECTED_SELECTION_TAGS}
    snapshot_ids = set()
    for row in ruled:
        pair = (row["prediction"], row["label"])
        slot = {
            ("success", "success"): 0,
            ("success", "no_path"): 1,
            ("no_path", "no_path"): 2,
            ("no_path", "success"): 3,
        }.get(pair)
        if slot is not None:
            target = primary if row["rule"] == PRIMARY_RULE else reference
            target[row["mode"]][slot] += 1
        if row["snapshot_matched"]:
            snapshot_ids.add(row["query_id"])
            slot = {
                ("success", "success"): 0,
                ("success", "no_path"): 1,
                ("no_path", "no_path"): 2,
                ("no_path", "success"): 3,
            }.get(pair)
            if slot is not None:
                snapshot[row["rule"]][slot] += 1
        if row["rule"] == PRIMARY_RULE:
            for tag in row["selection_reasons"]:
                tags[tag] += 1
    expect(
        {mode: tuple(primary[mode]) for mode in MODES} == EXPECTED_PRIMARY,
        "per-mode primary confusion changed",
    )
    expect(
        {mode: tuple(reference[mode]) for mode in MODES} == EXPECTED_WEAK,
        "per-mode reference confusion changed",
    )
    expect(
        tuple(sum(primary[mode][i] for mode in MODES) for i in range(4))
        == EXPECTED_PRIMARY_TOTAL,
        "primary totals changed",
    )
    expect(
        tuple(snapshot[PRIMARY_RULE]) == EXPECTED_SNAPSHOT_PRIMARY
        and tuple(snapshot[REFERENCE_RULE]) == EXPECTED_SNAPSHOT_WEAK,
        "the snapshot-matched subset changed",
    )
    expect(
        len(snapshot_ids) == EXPECTED_SNAPSHOT_REQUESTS,
        "the strict bridge subset is no longer sixteen requests",
    )
    expect(
        tags == EXPECTED_SELECTION_TAGS,
        "the overlapping selection tags changed",
    )
    expect(
        sum(tags.values()) > EXPECTED_STOCK_REQUESTS,
        "selection tags no longer overlap",
    )
    coverage = evaluation["package_mode_coverage"]
    expect(len(coverage) == 15, "package/mode coverage changed")
    null_records = [c for c in coverage if c["null_prediction"]]
    expect(
        len(null_records) == EXPECTED_NULL_PACKAGE_MODE_RECORDS,
        "null package-mode record count changed",
    )
    expect(
        all(
            c["selected_requests"] == 0 and c["supported_package"] is False
            for c in null_records
        ),
        "an unsupported package now carries requests",
    )
    for record in coverage:
        if record["supported_package"]:
            expect(
                record["selected_requests"] > 0, "a supported package lost its requests"
            )
    return {
        "evaluation": evaluation,
        "rows": ruled,
        "coverage": coverage,
        "primary": primary,
        "reference": reference,
        "snapshot": snapshot,
        "snapshot_ids": sorted(snapshot_ids),
        "tags": tags,
        "null_records": null_records,
        "by_case": {case: sorted(ids) for case, ids in sorted(by_case.items())},
    }


def confusion(pairs) -> dict:
    counts = dict.fromkeys(
        ["TP", "FP", "TN", "FN", "null_prediction", "unknown_label"], 0
    )
    for prediction, actual in pairs:
        if prediction not in ("success", "no_path"):
            counts["null_prediction"] += 1
        elif actual == "unknown":
            counts["unknown_label"] += 1
        else:
            counts[
                {
                    ("success", "success"): "TP",
                    ("success", "no_path"): "FP",
                    ("no_path", "no_path"): "TN",
                    ("no_path", "success"): "FN",
                }[(prediction, actual)]
            ] += 1
    counts["n"] = len(pairs)
    counts["precision"] = (
        counts["TP"] / (counts["TP"] + counts["FP"])
        if counts["TP"] + counts["FP"]
        else None
    )
    counts["recall"] = (
        counts["TP"] / (counts["TP"] + counts["FN"])
        if counts["TP"] + counts["FN"]
        else None
    )
    counts["prediction_coverage"] = (
        (len(pairs) - counts["null_prediction"]) / len(pairs) if pairs else None
    )
    counts["absent_class_power"] = not (
        counts["TP"] + counts["FN"] and counts["TN"] + counts["FP"]
    )
    return counts


def rederive_metrics(rows) -> dict:
    groups: dict[str, list] = {}
    for row in rows:
        pairs = [(row["prediction"], row["label"])]
        keys = [
            f"mode:{row['mode']}",
            f"package:{row['case_id']}",
            *[f"stratum:{tag}" for tag in row["selection_reasons"]],
        ]
        for key in keys:
            groups.setdefault(f"{row['rule']}/{key}", []).extend(pairs)
            if row["snapshot_matched"]:
                groups.setdefault(f"snapshot_matched/{row['rule']}/{key}", []).extend(
                    pairs
                )
    return {key: confusion(pairs) for key, pairs in sorted(groups.items())}


def check_metrics(evaluation: dict, rows) -> dict:
    rederived = rederive_metrics(rows)
    recorded = evaluation["metrics"]
    expect(set(rederived) == set(recorded), "the recorded metric groups changed")
    for key, value in rederived.items():
        expect(
            recorded[key] == value,
            f"{key}: the recorded group does not follow from the saved rows",
        )
    return {"groups": rederived}


def audit_label(observed) -> str:
    if not observed:
        return "unknown"
    result = observed.get("result") or {}
    plan = observed.get("plan") or {}
    request = plan.get("request") or {}
    if (
        observed.get("error")
        or result.get("complete") is not True
        or result.get("released") is not True
    ):
        return "unknown"
    if result.get("success") is False:
        return "no_path"
    positions = result.get("positions")
    if (
        result.get("success") is True
        and isinstance(positions, list)
        and positions
        and positions[0] == request.get("from")
        and positions[-1] == request.get("to")
    ):
        return "success"
    return "unknown"


def check_requests(
    carried: dict[str, bytes], evaluation: dict, selection: dict
) -> dict:
    audit = load_gz(carried, "audit.json.gz")
    rows = audit["rows"]
    expect(len(rows) == EXPECTED_REQUESTS, "planned request set changed")
    ids = [row["plan"]["query_id"] for row in rows]
    expect(
        len(set(ids)) == EXPECTED_REQUESTS,
        "planned request IDs are not complete and unique",
    )
    kinds = {
        kind: sum(1 for row in rows if row["kind"] == kind)
        for kind in ("holdout", "control", "intervention")
    }
    expect(
        kinds
        == {
            "holdout": EXPECTED_STOCK_REQUESTS,
            "control": EXPECTED_CONTROL_REQUESTS,
            "intervention": EXPECTED_INTERVENTION_REQUESTS,
        },
        "the planned 48/12/24 split changed",
    )
    observed = [row for row in rows if row["observed"] is not None]
    unknown = [row for row in rows if row["observed"] is None]
    expect(len(observed) == EXPECTED_OBSERVED, "observed request count changed")
    expect(len(unknown) == EXPECTED_UNKNOWN_CONTROLS, "unknown request count changed")
    expect(
        all(
            row["kind"] == "control" and row["case_id"] == "stock-1" for row in unknown
        ),
        "an unknown label appeared outside the retained first control opening",
    )
    expect(
        not audit["fidelity"]["invalid_requests"],
        "the audit retains an invalid request",
    )

    labels = {}
    for row in rows:
        plan = row["plan"]
        observed_row = row["observed"]
        label = audit_label(observed_row)
        if observed_row is None:
            expect(row["label"] == "unknown", "an unobserved request is not Unknown")
        expect(
            row["label"] in ("success", "no_path", "unknown"),
            "a saved label is outside the three recorded values",
        )
        labels[plan["query_id"]] = label
        if observed_row is not None:
            expect(
                label == row["label"],
                f"{plan['query_id']}: the saved label does not follow from its result",
            )
    expect(
        all(
            labels[query] == "unknown"
            for query in labels
            if query.startswith("stock-1/")
        ),
        "the retained first control opening now has a label",
    )

    records = []
    for row in rows:
        plan = row["plan"]
        request = plan.get("request") or {}
        has_observed = row["observed"] is not None
        observed_row = row["observed"] or {}
        records.append(
            {
                "id": plan["query_id"],
                "kind": row["kind"],
                "case_id": row["case_id"],
                "mode": plan.get("mode"),
                "request_kind": plan.get("kind"),
                "max_length": plan.get("max_length"),
                "capability": request.get("capability"),
                "name": request.get("name"),
                "from": request.get("from"),
                "to": request.get("to"),
                "label": row["label"],
                "observed": has_observed,
                "reason": row.get("missing_reason"),
            }
        )
    # The stock rows must be exactly the evaluated stock set.
    stock_ids = {row["query_id"] for row in evaluation["holdout_rows"] if "rule" in row}
    expect(
        stock_ids == {r["id"] for r in records if r["kind"] == "holdout"},
        "the planned stock rows and the evaluated stock rows differ",
    )
    return {"audit": audit, "rows": rows, "records": records, "labels": labels}


def check_stock_labels(rows, requests: dict) -> dict:
    """Re-derive the published per-mode/package/stratum tables from saved rows."""
    primary = {mode: [0, 0, 0, 0] for mode in MODES}
    reference = {mode: [0, 0, 0, 0] for mode in MODES}
    disagreements = []
    for row in rows:
        slot = {
            ("success", "success"): 0,
            ("success", "no_path"): 1,
            ("no_path", "no_path"): 2,
            ("no_path", "success"): 3,
        }.get((row["prediction"], row["label"]))
        if slot is not None:
            target = primary if row["rule"] == PRIMARY_RULE else reference
            target[row["mode"]][slot] += 1
        if row["label"] != "unknown" and row["prediction"] != row["label"]:
            disagreements.append(
                {
                    "query_id": row["query_id"],
                    "case_id": row["case_id"],
                    "mode": row["mode"],
                    "rule": row["rule"],
                    "prediction": row["prediction"],
                    "label": row["label"],
                }
            )
    expect(
        {mode: tuple(primary[mode]) for mode in MODES} == EXPECTED_PRIMARY,
        "primary confusion changed",
    )
    expect(
        {mode: tuple(reference[mode]) for mode in MODES} == EXPECTED_WEAK,
        "reference confusion changed",
    )
    per_mode = {}
    for mode in MODES:
        tp, fp, tn, fn = primary[mode]
        per_mode[mode] = {
            "requests": 24 if mode == "road" else 12,
            "successes": tp + fp,
            "failures": tn + fn,
            "primary": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            "reference": {
                "tp": reference[mode][0],
                "fp": reference[mode][1],
                "tn": reference[mode][2],
                "fn": reference[mode][3],
            },
            "discrimination_estimable": bool((tp + fp) and (tn + fn)),
        }
    for mode, record in per_mode.items():
        expect(
            record["requests"]
            == sum(
                1 for row in rows if row["mode"] == mode and row["rule"] == PRIMARY_RULE
            ),
            f"{mode}: request count changed",
        )
    expect(
        not any(row["mode"] != "road" for row in disagreements),
        "a disagreement appeared outside road",
    )
    expect(
        len(disagreements) == 4 * 3,
        "the reference disagreement count changed",
    )
    expect(
        all(row["rule"] == REFERENCE_RULE for row in disagreements),
        "a primary disagreement appeared",
    )
    expected_ids = {
        f"{case}/road/{index:03d}"
        for case in ("holdout-01", "holdout-02")
        for index in (1, 6, 7, 8)
    } | {f"holdout-03/road/{index:03d}" for index in (1, 2, 7, 8)}
    expect(
        {row["query_id"] for row in disagreements} == expected_ids,
        "the reference disagreement IDs changed",
    )

    # Results-table cross-check: every budget-free stock row is in the audit.
    for row in rows:
        expect(
            row["query_id"] in {record["id"] for record in requests["records"]},
            f"{row['query_id']}: a stock row is missing from the planned request set",
        )

    # The publication's recorded groups do not cross package with mode; the
    # ledger derives that cross so a one-class package-mode stays visible.
    package_mode: dict[str, dict] = {}
    for row in rows:
        if row["rule"] != PRIMARY_RULE:
            continue
        pair = (row["prediction"], row["label"])
        slot = {
            ("success", "success"): 0,
            ("success", "no_path"): 1,
            ("no_path", "no_path"): 2,
            ("no_path", "success"): 3,
        }.get(pair)
        package_mode.setdefault(f"{row['case_id']}/{row['mode']}", []).append(pair)
    derived = {key: confusion(pairs) for key, pairs in sorted(package_mode.items())}
    expect(
        set(derived)
        == {
            f"{case}/{mode}"
            for case in SELECTED_CASES
            if SELECTED_CASES[case]["supported"]
            for mode in MODES
        },
        "the selected package-mode set changed",
    )
    return {
        "modes": per_mode,
        "total": tuple(sum(primary[mode][i] for mode in MODES) for i in range(4)),
        "reference_modes": reference,
        "disagreements": disagreements,
        "package_mode": derived,
    }


def check_bridge(carried: dict[str, bytes], population: dict) -> dict:
    evaluation = load_gz(carried, "evaluation.json.gz")
    bridge = evaluation["bridge"]
    expect(
        sorted(bridge) == sorted(SELECTED_CASES),
        "the bridge package set changed",
    )
    packages = {}
    for case, record in SELECTED_CASES.items():
        expect(
            bridge[case]["supported"] is record["supported"],
            f"{case}: bridge support flag changed",
        )
        if not record["supported"]:
            expect(
                bridge[case]["by_mode"] == {}
                and bridge[case]["reason"]
                == "unsupported or no opening; predictions remain null",
                f"{case}: unsupported bridge changed",
            )
            packages[case] = {
                "supported": False,
                "reason": bridge[case]["reason"],
                "modes": {},
                "missing": list(population["by_file"][record["file"]]["missing"]),
            }
            continue
        by_mode = {}
        package_max = 0.0
        for mode, mode_record in bridge[case]["by_mode"].items():
            mismatches = mode_record["mismatches"]
            fields: dict[str, int] = {}
            largest = 0.0
            horizontal = True
            prefab = []
            for item in mismatches:
                for field in item["fields"]:
                    fields[field] = fields.get(field, 0) + 1
                    if field in ("a", "b"):
                        before, after = item["export"][field], item["native"][field]
                        largest = max(largest, abs(before[1] - after[1]))
                        if (
                            abs(before[0] - after[0]) > 1e-9
                            or abs(before[2] - after[2]) > 1e-9
                        ):
                            horizontal = False
                if "prefab" in item["fields"]:
                    prefab.append(
                        {
                            "segment": item["segment"],
                            "export": item["export"]["prefab"],
                            "native": item["native"]["prefab"],
                        }
                    )
            for field in ("lanes", "invert", "outside", "start", "end"):
                expect(
                    field not in fields,
                    f"{case}/{mode}: an observed {field} mismatch contradicts the report",
                )
            expect(
                horizontal, f"{case}/{mode}: a horizontal coordinate changed at opening"
            )
            expect(
                mode_record["exact_equal"] == (not mismatches),
                f"{case}/{mode}: exact_equal no longer follows from its mismatches",
            )
            by_mode[mode] = {
                "exact_equal": mode_record["exact_equal"],
                "mismatches": len(mismatches),
                "fields": dict(sorted(fields.items())),
                "max_vertical": round(largest, 6),
                "horizontal_equal": horizontal,
                "prefab_changes": prefab,
                "export_sha256": mode_record["export_sha256"],
                "native_sha256": mode_record["native_sha256"],
            }
            package_max = max(package_max, largest)
        expect(
            round(package_max, 6) == EXPECTED_BRIDGE[case]["max_vertical"],
            f"{case}: maximum vertical difference changed",
        )
        packages[case] = {
            "supported": True,
            "reason": None,
            "modes": by_mode,
            "max_vertical": round(package_max, 6),
        }
    roslyn = packages["holdout-03"]["modes"]["road"]["prefab_changes"]
    expect(
        tuple(change["segment"] for change in roslyn)
        == EXPECTED_ROSLYN_PREFAB_SEGMENTS,
        "the Roslyn prefab-change segments changed",
    )
    expect(
        all(
            (change["export"], change["native"]) == ("Highway", "Highway Connection")
            for change in roslyn
        ),
        "the Roslyn prefab change is no longer Highway to Highway Connection",
    )
    expect(
        all(
            packages[case]["modes"]["road"]["exact_equal"] is True
            for case in ("holdout-01", "holdout-02")
        ),
        "the first two packages' road fields are no longer exact",
    )
    expect(
        packages["holdout-03"]["modes"]["road"]["mismatches"] == 4,
        "the Roslyn road mismatch count changed",
    )
    return packages


def check_opening_drift(carried: dict[str, bytes]) -> dict:
    audit = load_gz(carried, "audit.json.gz")
    evaluation = load_gz(carried, "evaluation.json.gz")
    changes = {record["case_id"]: record for record in audit["opening_changes"]}
    expect(
        set(changes) == set(OPENINGS) - {"stock-1"},
        "the opening-change record set changed (the failed first control has no snapshot)",
    )
    summary = {}
    for case, record in changes.items():
        modes = {}
        for mode, mode_record in record["by_mode"].items():
            changed = [item["segment"] for item in mode_record["changes"]]
            modes[mode] = {
                "changed_segments": changed,
                "before_sha256": mode_record["before_sha256"],
                "after_sha256": mode_record["after_sha256"],
                "changed": mode_record["before_sha256"] != mode_record["after_sha256"],
            }
        summary[case] = modes
    expect(
        tuple(summary["holdout-03"]["air"]["changed_segments"])
        == EXPECTED_ROSLYN_AIR_SEGMENTS,
        "the Roslyn air drift segments changed",
    )
    expect(
        tuple(summary["holdout-03"]["ship"]["changed_segments"])
        == EXPECTED_ROSLYN_SHIP_SEGMENTS,
        "the Roslyn ship drift segments changed",
    )
    expect(
        tuple(summary["budget-01"]["air"]["changed_segments"])
        == EXPECTED_BUDGET_AIR_SEGMENTS,
        "the budget-01 air drift segments changed",
    )
    expect(
        not summary["holdout-03"]["road"]["changed"]
        and summary["holdout-03"]["air"]["changed"]
        and summary["holdout-03"]["ship"]["changed"],
        "the Roslyn opening no longer drifts in air and ship only",
    )
    # Pre/post-query changes, from the carried rows.
    rows = audit["rows"]
    holdout_03 = [
        row for row in rows if row["case_id"] == "holdout-03" and row["observed"]
    ]
    expect(len(holdout_03) == 18, "holdout-03 no longer carries eighteen requests")
    changed = [
        row["plan"]["query_id"]
        for row in holdout_03
        if row["observed"]["pre_graph"] != row["observed"]["post_graph"]
    ]
    expect(
        tuple(changed) == EXPECTED_PRE_POST_CHANGES,
        "the pre/post-query changes changed",
    )
    mismatch = 0
    for row in holdout_03:
        mode = row["plan"]["mode"]
        before = summary["holdout-03"][mode]["before_sha256"]
        if row["observed"]["pre_graph"] != before:
            mismatch += 1
    expect(
        mismatch == EXPECTED_OPENING_FINGERPRINT_MISMATCH_REDERIVED,
        "the re-derivable pre-query/opening fingerprint mismatch count changed",
    )
    opening_state = {
        record["case_id"]: {
            "completed": record["completed"],
            "error": record["error"],
            "opening_post_graph_equal": record["opening_post_graph_equal"],
            "cleanup_coverage_valid": record["cleanup_coverage_valid"],
        }
        for record in evaluation["openings"]
    }
    expect(
        sorted(opening_state) == sorted(OPENINGS),
        "the opening set changed",
    )
    expect(
        opening_state["holdout-03"]["opening_post_graph_equal"] is False
        and opening_state["budget-01"]["opening_post_graph_equal"] is False
        and opening_state["stock-1"]["completed"] is False,
        "the retained opening anomalies changed",
    )
    return {
        "openings": opening_state,
        "opening_changes": summary,
        "pre_query_opening_fingerprint_mismatches": mismatch,
        "reported_opening_fingerprint_mismatches": EXPECTED_OPENING_FINGERPRINT_MISMATCH_REPORTED,
        "pre_post_query_changes": changed,
    }


def check_controls(carried: dict[str, bytes], requests: dict) -> dict:
    evaluation = load_gz(carried, "evaluation.json.gz")
    controls = evaluation["controls"]
    expect(sorted(controls) == sorted(MODES), "control mode set changed")
    for mode, record in controls.items():
        expect(
            record["qualified"] is False,
            f"{mode}: a mode is now qualified without its retained control failure",
        )
        expect(
            record["unavailable"] == {},
            f"{mode}: control availability changed",
        )
    stock_2 = [
        row
        for row in requests["records"]
        if row["kind"] == "control" and row["case_id"] == "stock-2"
    ]
    stock_1 = [
        row
        for row in requests["records"]
        if row["kind"] == "control" and row["case_id"] == "stock-1"
    ]
    expect(len(stock_1) == 6 and len(stock_2) == 6, "the control request split changed")
    expect(
        all(not row["observed"] and row["label"] == "unknown" for row in stock_1),
        "the first control opening is no longer wholly Unknown",
    )
    expect(
        all(row["observed"] for row in stock_2),
        "the second control opening lost a request",
    )
    expect(
        all(
            row["label"]
            == ("success" if row["request_kind"] == "positive" else "no_path")
            for row in stock_2
        ),
        "the completed control labels changed",
    )
    failure = json.loads(carried["analysis/source-fix.json"])
    expect(
        failure["reason"].startswith("Owned frozen Harness.cs appends ok=true"),
        "the retained scorer failure reason changed",
    )
    expect(
        controls["road"]["positive_labels"] == ["success"]
        and controls["road"]["invalid_vehicle_labels"] == ["no_path"],
        "the recorded control label sets changed",
    )
    return {
        "cases": {
            "stock-1": {
                "name": CONTROL_CASES["stock-1"],
                "planned": 6,
                "observed": 0,
                "labels": sorted({row["label"] for row in stock_1}),
                "reason": (
                    "opening stopped before any path request: the collector read the native MetaBool "
                    'string "False" as a Python boolean. The opening and its six Unknown controls are '
                    "retained without retry."
                ),
            },
            "stock-2": {
                "name": CONTROL_CASES["stock-2"],
                "planned": 6,
                "observed": 6,
                "labels": sorted({row["label"] for row in stock_2}),
                "reason": "complete: one exact positive and one invalid-vehicle rejection per mode",
            },
        },
        "modes": {
            mode: {
                "positive_labels": controls[mode]["positive_labels"],
                "invalid_vehicle_labels": controls[mode]["invalid_vehicle_labels"],
                "qualified": False,
            }
            for mode in MODES
        },
        "all_controls_complete": False,
        "hanami_complete": True,
    }


def check_intervention(carried: dict[str, bytes], requests: dict) -> dict:
    evaluation = load_gz(carried, "evaluation.json.gz")
    audit = load_gz(carried, "audit.json.gz")
    groups = evaluation["intervention"]
    expect(len(groups) == 8, "the intervention group set changed")
    budget = {record["old_query_id"]: record for record in audit["budget"]}
    expect(
        sorted(budget) == sorted(group["old_query_id"] for group in groups),
        "the audited budget groups and the scored groups differ",
    )
    records = []
    for group in groups:
        old = group["old_query_id"]
        audited = budget[old]
        expect(
            deep_equal(
                [row["requested_max_length"] for row in group["new_intervention_rows"]],
                list(BUDGETS),
            ),
            f"{old}: the budget set changed",
        )
        expect(
            group["immutable_old_label"] == audited["immutable_old_label"],
            f"{old}: the immutable old label changed",
        )
        expect(
            group["selection"] == audited["selection"],
            f"{old}: the selection reason changed",
        )
        expect(
            audited["non_budget_effective_arguments_equal"] is True,
            f"{old}: non-budget effective arguments are no longer equal",
        )
        expect(
            audited["entry_context_unchanged"] is True,
            f"{old}: the entry context changed",
        )
        effective = {
            key: value
            for row in group["new_intervention_rows"]
            for key, value in (row["effective"] or {}).items()
            if key not in ("id", "max_length")
        }
        base = None
        for row in group["new_intervention_rows"]:
            item = row["effective"]
            expect(
                item is not None, f"{old}: a budget row lost its effective arguments"
            )
            non_budget = {
                k: v for k, v in item.items() if k not in ("id", "max_length")
            }
            if base is None:
                base = non_budget
            else:
                expect(
                    non_budget == base,
                    f"{old}: a non-budget effective argument differs within the group",
                )
        del effective
        rows = []
        for row in group["new_intervention_rows"]:
            result = row["result"] or {}
            rows.append(
                {
                    "budget": row["requested_max_length"],
                    "label": row["label"],
                    "snapshot_matched": row["snapshot_matched"],
                    "effective_max_length": (row["effective"] or {}).get("max_length"),
                    "flags": result.get("flags"),
                    "returned_length": result.get("length"),
                    "complete": result.get("complete"),
                    "released": result.get("released"),
                    "success": result.get("success"),
                }
            )
            if row["label"] == "no_path":
                expect(
                    result.get("flags") == 8
                    and result.get("length") == row["requested_max_length"],
                    f"{old}: the retained no_path sentinel no longer tracks its requested budget",
                )
            if (
                row["effective"]
                and row["requested_max_length"] != row["effective"]["max_length"]
            ):
                expect(
                    False,
                    f"{old}: the requested budget was not the effective budget",
                )
        records.append(
            {
                "old_query_id": old,
                "old_label": group["immutable_old_label"],
                "selection": group["selection"],
                "source_length": audited["source_length"],
                "source_request_sha256": audited["source_request_sha256"],
                "non_budget_effective_arguments_equal": True,
                "entry_context_unchanged": True,
                "all_mode_graph_constant": audited[
                    "graph_unchanged_across_all_budgets"
                ],
                "labels": [row["label"] for row in rows],
                "sensitive": group["sensitive"],
                "rows": rows,
            }
        )
    false_positive = [record for record in records if record["old_label"] == "failure"]
    matched = [record for record in records if record["old_label"] == "success"]
    expect(
        len(false_positive) == 4 and len(matched) == 4,
        "the intervention cohort changed",
    )
    expect(
        all(
            record["selection"] == "first_four_false_positive"
            for record in false_positive
        ),
        "the false-positive selection reason changed",
    )
    expect(
        all(record["selection"] == "matched_success" for record in matched),
        "the matched-success selection reason changed",
    )
    for record in false_positive:
        expect(
            record["labels"] == ["no_path", "no_path", "no_path"],
            f"{record['old_query_id']}: a retained error now resolves at some budget",
        )
    sensitive = [record for record in records if record["sensitive"]]
    expect(len(sensitive) == 1, "the measured budget response changed")
    expect(
        sensitive[0]["old_query_id"] == "hong-kong/native-v2-5/road/167"
        and sensitive[0]["labels"] == ["no_path", "success", "success"],
        "the one measured budget response changed",
    )
    drifted = [record for record in records if not record["all_mode_graph_constant"]]
    expect(
        len(drifted) == 1
        and drifted[0]["old_query_id"] == "pittsburgh/native-v2-6/road/093",
        "the drifting intervention group changed",
    )
    expect(
        drifted[0]["rows"][2]["snapshot_matched"] is False,
        "the drifting row now claims a per-query snapshot",
    )
    expect(
        not any(record["sensitive"] for record in drifted),
        "the drifting group was also labelled a clean single-variable result",
    )
    return {
        "cohort": {
            "old_false_positives": len(false_positive),
            "matched_old_successes": len(matched),
            "budgets": list(BUDGETS),
            "not_a_holdout": True,
            "not_a_rejudge": True,
            "clean_single_variable_trials": len(records) - len(drifted),
            "drifting_groups": len(drifted),
        },
        "groups": records,
        "measured_response": {
            "old_query_id": sensitive[0]["old_query_id"],
            "labels": sensitive[0]["labels"],
            "scope": (
                "measured response of one matched old-success request under the requested maxLength "
                "floats; it neither explains the four retained errors nor establishes a budget cause"
            ),
        },
        "drift": {
            "old_query_id": drifted[0]["old_query_id"],
            "opening": "budget-01",
            "air_segments": list(EXPECTED_BUDGET_AIR_SEGMENTS),
            "per_query_road_snapshot_retained": False,
            "scope": (
                "all-mode graph changed inside the opening that carried the million-budget row; the "
                "opening/post-batch road fields are identical but no per-query road-only snapshot was "
                "retained, so this group is not a clean single-variable trial"
            ),
        },
        "error_mechanisms": "unknown",
        "units": (
            "requested maxLength is a float handed to the public API; returned length and flags=8 are "
            "not proof of native exhaustion, cost, metres or an SI conversion"
        ),
    }


def deep_equal(left, right) -> bool:
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def check_runtime(
    carried: dict[str, bytes], requests: dict, intervention: dict
) -> dict:
    audit = load_gz(carried, "audit.json.gz")
    fidelity = audit["fidelity"]
    inventories = fidelity["file_inventories"]
    expect(
        len(inventories) == EXPECTED_PHASE_INVENTORIES,
        "the phase inventory count changed",
    )
    phases = {}
    for record in inventories:
        phases.setdefault(record["case_id"], []).append(record["phase"])
        expect(
            record["excluded_dynamic_assemblies"]
            == ["Anonymously Hosted DynamicMethods Assembly"],
            f"{record['case_id']}/{record['phase']}: the excluded dynamic assembly changed",
        )
        expect(
            record["unresolved_loaded_assemblies"] == [],
            f"{record['case_id']}/{record['phase']}: a loaded assembly is now unresolved",
        )
        expect(
            record["files"] > 0 and all(record["roots"].values()),
            f"{record['case_id']}/{record['phase']}: a declared file root is missing",
        )
    for case in OPENINGS:
        expect(
            case in phases,
            f"{case}: no phase inventory",
        )
    expect(
        sorted(phases["stock-1"]) == ["launch_runtime_identity"],
        "the failed first control opening's inventory changed",
    )
    cleanup = audit["cleanup"]
    expect(
        cleanup["all_observed_processes_gone"] is True,
        "a historical observed process is no longer cleared",
    )
    identities = {}
    for case in cleanup["cases"]:
        for identity in case["identities"]:
            identities[(identity["pid"], identity["start_ticks"])] = identity
    expect(
        len(identities) == EXPECTED_PROCESS_IDENTITIES,
        "the historical process identity count changed",
    )
    expect(
        all(
            identity["verified_still_running"] is False
            for identity in identities.values()
        ),
        "a historical identity is still running",
    )
    kinds = {
        case["case_id"]: sorted({i["kind"] for i in case["identities"]})
        for case in cleanup["cases"]
    }
    expect(
        kinds["stock-1"]
        == ["auditor", "collector", "driver", "game", "session_gpu_monitor"],
        "the supplemental first-opening auditor chain changed",
    )
    expect(
        all(kinds[case] == kinds["stock-1"] for case in kinds),
        "a clearing case lost one of its process kinds",
    )
    windows = [
        {
            "case_id": record["case_id"],
            "started_at": record["started_at"],
            "finished_at": record["finished_at"],
            "host": record["host"],
            "gpu": record["gpu"],
            "power_limit_watts": record["power_limit_reported_watts"],
            "power_peak_watts": record["power_peak_watts"],
            "temperature_peak_c": record["temperature_peak_c"],
            "total_gpu_memory_peak_mib": record["total_gpu_memory_peak_mib"],
            "game_memory_menu_samples_mib": record["game_memory_menu_samples_mib"],
        }
        for record in sorted(audit["run_log"], key=lambda item: item["started_at"])
    ]
    expect(len(windows) == len(OPENINGS), "the observation window set changed")
    expect(
        len({window["started_at"] for window in windows}) == len(windows),
        "two openings share a recorded start time",
    )
    receipts = {
        "stock-1": "AP Asanu Beach.crp",
        "stock-2": "AP Hanami Bay.crp",
        "holdout-01": "CCP Map 1.crp",
        "holdout-02": "DN Fisher Enclave.crp",
        "holdout-03": "CL Roslyn Peninsula.crp",
        "holdout-04": "CCMP2 Desert Map 2.crp",
        "holdout-05": "CCMP2 Euro Map 1.crp",
        "budget-01": "old pittsburgh CRP",
        "budget-02": "old pittsburgh CRP",
    }
    expect(
        len(receipts) == EXPECTED_INSTALLED_CRP_RECEIPTS,
        "the installed receipt set changed",
    )
    build = json.loads(carried["build.json"])
    expect(
        build["scope"].startswith("one explicit float maxLength passed unchanged"),
        "the build scope changed",
    )
    expect(
        not deep_equal(build["staged_NetworkOps"], build["build_receipt"]["sources"]),
        "unreachable",
    )
    return {
        "openings": len(OPENINGS),
        "phase_inventories": len(inventories),
        "phase_inventory_names": {
            case: sorted(names) for case, names in sorted(phases.items())
        },
        "process_identities": len(identities),
        "process_kinds": kinds,
        "installed_crp_receipts": receipts,
        "build": {
            "dll_sha256": build["build_receipt"]["dll_sha256"],
            "game_executable_sha256": build["build_receipt"]["game_executable_sha256"],
            "game_assemblies": sorted(build["build_receipt"]["game_assemblies"]),
            "source_files": len(build["build_receipt"]["sources"]),
            "staged_collector_sha256": sha(build["staged_NetworkOps"].encode()),
            "original_collector_sha256": build["original_sources"]["NetworkOps.cs"],
            "scope": build["scope"],
        },
        "observation_windows": windows,
        "launch_caption_used_as_evidence": False,
        "cleanup_note": (
            "Historical coverage of every named game, collector, driver, auditor and GPU-monitor "
            "PID/start identity at the time of collection. It is not a description of blade's current "
            "slot or process state."
        ),
    }


def check_schema_repair(carried: dict[str, bytes]) -> dict:
    source_fix = json.loads(carried["analysis/source-fix.json"])
    log = carried["analysis/frozen-scorer-failure.log"]
    diff = gzip.decompress(carried["analysis/schema-fix.diff.gz"])
    expect(
        sha(log) == source_fix["frozen_scorer_failure_sha256"],
        "the retained scorer failure bytes changed",
    )
    expect(
        sha(diff) == source_fix["diff_raw_sha256"],
        "the schema-repair diff does not decompress to its recorded bytes",
    )
    text = log.decode("utf-8", "replace")
    expect(
        "native result schema differs" in text and "evaluate.py" in text,
        "the retained scorer failure no longer records the body-schema mismatch",
    )
    expect(
        '"queries": 48' in text,
        "the retained scorer failure lost its frozen selection record",
    )
    expect(
        source_fix["wire_schema"]["transport_required"] == {"ok": True},
        "the repaired wire schema no longer requires ok=true",
    )
    expect(
        source_fix["wire_schema"]["body_effective_keys"]
        == [
            "id",
            "mode",
            "max_length",
            "build_index",
            "seed",
            "from",
            "to",
            "vehicle",
            "category",
            "lane_types",
        ]
        and source_fix["wire_schema"]["body_result_keys"]
        == ["id", "flags", "complete", "success", "length", "positions", "released"],
        "the frozen body key sets changed",
    )
    expect(
        source_fix["timing"]
        == "analysis correction after stock-2 control outcomes; no model refit",
        "the correction timing changed",
    )
    return {
        "retained_failure": {
            "path": "analysis/frozen-scorer-failure.log",
            "sha256": sha(log),
            "bytes": len(log),
        },
        "repair": {
            "path": "analysis/schema-fix.diff.gz",
            "sha256": sha(carried["analysis/schema-fix.diff.gz"]),
            "decompressed_sha256": sha(diff),
            "source_fix": "analysis/source-fix.json",
            "transport_required": {"ok": True},
            "body_effective_keys": source_fix["wire_schema"]["body_effective_keys"],
            "body_result_keys": source_fix["wire_schema"]["body_result_keys"],
            "timing": source_fix["timing"],
        },
        "retained_selection": json.loads(log.decode().splitlines()[0]),
        "scope": (
            "The original frozen scorer omitted the transport's ok=true field; its retained failure is "
            "evidence. The separate post-control scorer requires exactly the frozen body keys plus "
            "ok=true. This is a schema correction, not a hidden re-freeze: no rule, request, native row, "
            "label, threshold or qualification gate changed."
        ),
    }


def check_protocol(
    carried: dict[str, bytes], requests: dict, intervention: dict
) -> dict:
    observed = [row for row in requests["rows"] if row["observed"]]
    modes = {}
    for mode in MODES:
        rows = [row for row in observed if row["plan"].get("mode") == mode]
        expect(rows, f"{mode}: no observed request")
        effective = {
            k: v
            for row in rows
            for k, v in (row["observed"].get("effective") or {}).items()
        }
        expect(
            effective["seed"] == FRAMED_PROTOCOL["seed"],
            f"{mode}: seed changed",
        )
        expect(
            effective["mode"] == FRAMED_PROTOCOL["native_modes"][mode],
            f"{mode}: native mode label changed",
        )
        expect(
            effective["vehicle"] == FRAMED_PROTOCOL["mode_vehicle"][mode],
            f"{mode}: vehicle changed",
        )
        expect(
            effective["category"] == FRAMED_PROTOCOL["category_by_mode"][mode],
            f"{mode}: category changed",
        )
        expect(
            set(effective["lane_types"].split(", "))
            == set(FRAMED_PROTOCOL["lane_types"][mode]),
            f"{mode}: lane types changed",
        )
        modes[mode] = {
            "native_mode": effective["mode"],
            "vehicle": effective["vehicle"],
            "category": effective["category"],
            "lane_types": sorted(effective["lane_types"].split(", ")),
        }
    for row in requests["records"]:
        if row["kind"] == "control":
            continue
        expect(
            row["max_length"]
            in (FRAMED_PROTOCOL["default_max_length"], *FRAMED_PROTOCOL["budgets"]),
            f"{row['id']}: an undeclared budget was requested",
        )
    expect(
        {row["max_length"] for row in requests["records"] if row["kind"] == "holdout"}
        == {FRAMED_PROTOCOL["default_max_length"]},
        "a stock request no longer uses the default budget",
    )
    results = FRAMED_PROTOCOL["labels"]
    return {
        **FRAMED_PROTOCOL,
        "modes": modes,
        "results": results,
    }


def check_integrity_reconstruction(
    carried: dict[str, bytes], integrity: dict, population: dict
) -> dict:
    retention = json.loads(carried["retention.json"])
    expect(
        len(retention["files"]) == EXPECTED_RAW_FILES,
        "the retained raw file count changed",
    )
    expect(
        len(retention["reports"]) == EXPECTED_RAW_REPORTS,
        "the retained report count changed",
    )
    raw_members = sorted(name for name in integrity["files"] if name.startswith("raw/"))
    expect(
        len(raw_members) == EXPECTED_RAW_FILES, "the integrity raw member count changed"
    )
    for raw_name, record in retention["files"].items():
        expect(
            record["retained"] == f"raw/{raw_name}.gz",
            f"{raw_name}: retained path changed",
        )
        expect(
            integrity["files"][record["retained"]] == record["retained_sha256"],
            f"{raw_name}: retained hash differs from the integrity record",
        )
    return {
        "publication_files": EXPECTED_PUBLICATION_FILES,
        "integrity_members": len(integrity["files"]),
        "raw_members": len(raw_members),
        "retained_reports": len(retention["reports"]),
        "reconstruction": (
            "Every carried member is re-hashed and every linked member's pinned hash is corroborated by "
            "the carried retention, source-fix, evaluation, audit, build and header records. The "
            "publication's own exact-byte replay of the 105 raw members is recorded, not re-run."
        ),
    }


def check_semantics(carried: dict[str, bytes]) -> dict:
    results = carried["RESULTS.md"].decode()
    readme = carried["README.md"].decode()
    journal = carried["JOURNAL.md"].decode()
    for phrase in (
        "48 new stock request labels",
        "All three modes remain **unqualified**",
        "Only 16 road requests have exact export/native field identity",
        "Increasing the requested budget does not resolve any of the four retained road",
        "17 of its 18 queries",
        "holdout-03",
        'MetaBool string `"False"`',
        "Hanami completes all six",
        "remain unexplained",
        "no invented physical-input/CPU lineage",
        "Internal limits and cost units remain unidentified",
    ):
        expect(
            phrase.replace("\n", " ") in results.replace("\n", " "),
            f"RESULTS.md lost a bound: {phrase!r}",
        )
    for phrase in (
        "105 raw files reconstruct",
        "45 observed game/collector/driver/auditor/GPU-monitor PID/start",
        "Twenty-five phase inventories",
        "Seven groups keep the all-mode graph fingerprint unchanged",
    ):
        expect(phrase in results, f"RESULTS.md lost a verification fact: {phrase!r}")
    for phrase in (
        "No map writer, app, ledger, gate, default, old study, or certificate changes",
        "not new holdout observations",
    ):
        expect(
            phrase.replace("\n", " ") in readme.replace("\n", " "),
            f"README.md lost a scope fact: {phrase!r}",
        )
    expect(
        "PL-1294" in journal and "pre-query guard failure" in journal,
        "JOURNAL.md lost its opening record",
    )
    return {
        "documents": {
            "README.md": sha(carried["README.md"]),
            "RESULTS.md": sha(carried["RESULTS.md"]),
            "JOURNAL.md": sha(carried["JOURNAL.md"]),
        },
        "results_claims": (
            "The page quotes the report's own counts and bounds verbatim where it states them; the "
            "importer re-derives every count it can from carried bytes and refuses a document that "
            "lost one of those claims."
        ),
    }


# ---------------------------------------------------------------------------
# Projection assembly


def derive(carried: dict[str, bytes], docs: dict[str, bytes] | None = None) -> dict:
    integrity = check_integrity(carried, _manifest_files_from_carried(carried), docs)
    population = check_population(carried)
    stock_source = check_stock_source(carried)
    selection = check_selection(carried, population)
    evaluation = check_evaluation(carried, population)
    metrics = check_metrics(evaluation["evaluation"], evaluation["rows"])
    requests = check_requests(carried, evaluation["evaluation"], selection)
    labels = check_stock_labels(evaluation["rows"], requests)
    bridge = check_bridge(carried, population)
    drift = check_opening_drift(carried)
    controls = check_controls(carried, requests)
    intervention = check_intervention(carried, requests)
    runtime = check_runtime(carried, requests, intervention)
    repair = check_schema_repair(carried)
    protocol = check_protocol(carried, requests, intervention)
    reconstruction = check_integrity_reconstruction(carried, integrity, population)
    semantics = check_semantics(carried)
    return {
        "integrity": integrity,
        "population": population,
        "stock_source": stock_source,
        "catalog": selection["catalog"],
        "evaluation": evaluation,
        "metrics": metrics,
        "requests": requests,
        "labels": labels,
        "bridge": bridge,
        "drift": drift,
        "controls": controls,
        "intervention": intervention,
        "runtime": runtime,
        "repair": repair,
        "protocol": protocol,
        "reconstruction": reconstruction,
        "semantics": semantics,
    }


def _manifest_files_from_carried(carried: dict[str, bytes]) -> dict[str, dict]:
    """A hash table over every publication member, from carried documents.

    The linked members are not present in this repository, so their entries come
    from the publication's own integrity record; every one of those entries is
    then corroborated by at least one other carried document where the
    publication provides one.
    """
    integrity = json.loads(carried["integrity.json"])
    files = {
        name: {"sha256": value, "bytes": 0, "git_blob": "", "role": "unknown"}
        for name, value in integrity["files"].items()
    }
    for name, raw in carried.items():
        files[name] = {
            "sha256": sha(raw),
            "bytes": len(raw),
            "git_blob": git_blob(raw),
            "role": file_role(name),
        }
    return files


def assemble(facts: dict, files: dict[str, dict]) -> tuple[dict, dict]:
    evaluation = facts["evaluation"]["evaluation"]
    selection = facts["evaluation"]
    labels = facts["labels"]
    requests = facts["requests"]
    population = facts["population"]
    intervention = facts["intervention"]
    runtime = facts["runtime"]
    repair = facts["repair"]
    protocol = facts["protocol"]
    bridge = facts["bridge"]
    drift = facts["drift"]
    controls = facts["controls"]

    carried = _carried_for_projection()
    declared = cross_declarations(carried, files, None)

    linked_records = []
    for relative in sorted(
        set(LINKED_BULK) | {n for n in files if n.startswith("raw/")}
    ):
        record = files[relative]
        linked_records.append(
            {
                "path": f"{PREFIX}/{relative}",
                "sha256": record["sha256"],
                "bytes": record["bytes"],
                "git_blob": record["git_blob"],
                "role": record["role"],
                "declared_by": declared.get(relative, []),
                "corroborated": len(declared.get(relative, [])) >= 2,
            }
        )
    carried_records = [
        {
            "path": f"{PREFIX}/{relative}",
            "sha256": files[relative]["sha256"],
            "bytes": files[relative]["bytes"],
            "git_blob": files[relative]["git_blob"],
            "role": files[relative]["role"],
        }
        for relative in sorted(CARRIED)
    ]

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
            "history": {
                "superseded_head": PUBLICATION["superseded_head"],
                "superseded_review": PUBLICATION["superseded_review"],
                "note": PUBLICATION["history"],
            },
            "native_sources": PUBLICATION["native_sources"],
            "publication_prefix": PREFIX,
        },
        "closure": {
            "commit": PUBLICATION["publication_commit"],
            "prefix": PREFIX,
            "publication_files": EXPECTED_PUBLICATION_FILES,
            "copied_files": EXPECTED_CARRIED,
            "linked_files": EXPECTED_LINKED,
            "integrity_members": EXPECTED_INTEGRITY_MEMBERS,
        },
        "documents": list(DOCUMENTS),
        "files": carried_records,
        "linked": linked_records,
        "population": {
            "counts": population["counts"],
            "excluded_hashes": population["exclusions"],
            "blank_co": population["blank_co"],
            "formats": population["formats"],
            "selection": {
                "requested_packages": len(
                    [c for c in SELECTED_CASES.values() if c["supported"]]
                ),
                "metadata_only_packages": len(
                    [c for c in SELECTED_CASES.values() if not c["supported"]]
                ),
                "cases": {
                    case: {
                        "file": record["file"],
                        "sha256": population["by_file"][record["file"]]["sha256"],
                        "supported": record["supported"],
                        "reason": record["reason"],
                        "requests": len(selection["by_case"].get(case, [])),
                    }
                    for case, record in SELECTED_CASES.items()
                },
            },
            "packages": population["packages"],
            "limit": (
                "Selection tags overlap across packages and modes and are not independent samples; "
                "the five selected packages are three queried cases plus two metadata-only "
                "unsupported cases, not eight."
            ),
        },
        "requests": {
            "planned": len(requests["records"]),
            "observed": sum(1 for record in requests["records"] if record["observed"]),
            "unknown": sum(
                1 for record in requests["records"] if not record["observed"]
            ),
            "by_kind": {
                kind: sum(1 for record in requests["records"] if record["kind"] == kind)
                for kind in ("holdout", "control", "intervention")
            },
            "records": requests["records"],
            "limit": (
                "No request was replaced, retried or relabelled. The six Unknown controls stay "
                "Unknown, and an unobserved request never becomes a negative."
            ),
        },
        "stock": {
            "rules": list(RULES),
            "primary_rule": PRIMARY_RULE,
            "reference_rule": REFERENCE_RULE,
            "requests": EXPECTED_STOCK_REQUESTS,
            "primary": {
                mode: {
                    "tp": labels["modes"][mode]["primary"]["tp"],
                    "fp": labels["modes"][mode]["primary"]["fp"],
                    "tn": labels["modes"][mode]["primary"]["tn"],
                    "fn": labels["modes"][mode]["primary"]["fn"],
                }
                for mode in MODES
            },
            "reference": {
                mode: {
                    "tp": labels["modes"][mode]["reference"]["tp"],
                    "fp": labels["modes"][mode]["reference"]["fp"],
                    "tn": labels["modes"][mode]["reference"]["tn"],
                    "fn": labels["modes"][mode]["reference"]["fn"],
                }
                for mode in MODES
            },
            "total": {
                "tp": labels["total"][0],
                "fp": labels["total"][1],
                "tn": labels["total"][2],
                "fn": labels["total"][3],
            },
            "modes": labels["modes"],
            "rows": stock_rows(evaluation),
            "groups": facts["metrics"]["groups"],
            "selection_tags": selection["tags"],
            "package_mode_coverage": selection["coverage"],
            "snapshot_matched": {
                "requests": len(selection["snapshot_ids"]),
                "request_ids": selection["snapshot_ids"],
                "primary": {
                    "tp": selection["snapshot"][PRIMARY_RULE][0],
                    "fp": selection["snapshot"][PRIMARY_RULE][1],
                    "tn": selection["snapshot"][PRIMARY_RULE][2],
                    "fn": selection["snapshot"][PRIMARY_RULE][3],
                },
                "reference": {
                    "tp": selection["snapshot"][REFERENCE_RULE][0],
                    "fp": selection["snapshot"][REFERENCE_RULE][1],
                    "tn": selection["snapshot"][REFERENCE_RULE][2],
                    "fn": selection["snapshot"][REFERENCE_RULE][3],
                },
                "not_matched": EXPECTED_STOCK_REQUESTS - len(selection["snapshot_ids"]),
            },
            "disagreements": labels["disagreements"],
            "qualified_modes": {mode: False for mode in MODES},
            "qualification_reason": (
                "The retained all-controls completion requirement fails on the first Asanu opening, so "
                "every mode stays unqualified even though the primary rule matches all 48 labels."
            ),
            "package_mode": labels["package_mode"],
            "one_class": {
                mode: {
                    "packages": [
                        case
                        for case in ("holdout-01", "holdout-02", "holdout-03")
                        if labels["package_mode"][f"{case}/{mode}"][
                            "absent_class_power"
                        ]
                    ]
                }
                for mode in MODES
            },
            "selection_strata": facts["repair"]["retained_selection"]["strata"],
        },
        "bridge": {
            "packages": bridge,
            "subset": {
                "requests": len(selection["snapshot_ids"]),
                "packages": ["holdout-01", "holdout-02"],
                "mode": "road",
                "not_matched": EXPECTED_STOCK_REQUESTS - len(selection["snapshot_ids"]),
                "primary": {
                    "tp": selection["snapshot"][PRIMARY_RULE][0],
                    "fp": selection["snapshot"][PRIMARY_RULE][1],
                    "tn": selection["snapshot"][PRIMARY_RULE][2],
                    "fn": selection["snapshot"][PRIMARY_RULE][3],
                },
                "reference": {
                    "tp": selection["snapshot"][REFERENCE_RULE][0],
                    "fp": selection["snapshot"][REFERENCE_RULE][1],
                    "tn": selection["snapshot"][REFERENCE_RULE][2],
                    "fn": selection["snapshot"][REFERENCE_RULE][3],
                },
                "note": (
                    "Only these 16 road requests have exact export/native field identity. The other 32 "
                    "requests fail exact bridge identity and are not admitted to this subset."
                ),
            },
            "height_drift": {
                package: bridge[package]["max_vertical"]
                for package in ("holdout-01", "holdout-02", "holdout-03")
            },
            "roslyn_prefabs": bridge["holdout-03"]["modes"]["road"]["prefab_changes"],
            "horizontal_unchanged": True,
            "lane_connectivity_invert_outside_mismatches": 0,
            "post_opening_diagnostic": (
                "Applying the unchanged rule to opening-native fields reproduces the classifications, "
                "but that is a post-outcome diagnostic, never a replacement pre-export prediction or an "
                "exact bridge subset."
            ),
            "scope": (
                "Bridge differences are retained and inspected per selected package. Ship and air "
                "endpoint heights change at opening while horizontal coordinates do not; the CL Roslyn "
                "Peninsula road prefabs change from Highway to Highway Connection on four segments. No "
                "lane, connectivity, Invert or Outside-role mismatch was observed."
            ),
        },
        "drift": {
            **drift,
            "scope": (
                "Opening-to-post-batch drift is reported separately from the bridge. CL Roslyn Peninsula "
                "changes seven air and two ship endpoint heights, and three pre/post-query fingerprints "
                "change; the budget-01 opening changes two air endpoint heights. The publication reports "
                "17 of 18 opening-fingerprint mismatches against the query-freeze opening graph; the "
                "ledger does not re-run that comparison because the freeze is linked, but it does "
                "re-derive that every pre-query model-field fingerprint differs from the recorded "
                "per-mode opening snapshot."
            ),
        },
        "controls": controls,
        "intervention": intervention,
        "protocol": protocol,
        "runtime": runtime,
        "schema_repair": repair,
        "integrity_reconstruction": facts["reconstruction"],
        "stock_exclusion_source": facts["stock_source"],
        "documents_semantics": facts["semantics"],
        "limitations": {
            "correlated": "Requests, reciprocal pairs, lanes and repeated openings of one package are correlated, not independent votes.",
            "one_class": "Empty strata and absent native classes are not estimable; arithmetic precision can be 1 with no information.",
            "unqualified": "All three modes remain unqualified after the retained first-control failure.",
            "unknown_mechanisms": "All four retained road error mechanisms remain Unknown; a requested float and flags=8 are not exhaustion proof.",
            "no_geography": "No request is a geographic negative, and no result is a service, spawning or sustained-navigation claim.",
            "file_identity": "File identity is not memory attestation or a strict no-mods claim; dynamic exclusions, plugin state and three DLL errors remain.",
            "cleanup_history": "Cleanup coverage is historical; it is not blade's current slot or process state.",
            "no_lineage": "Stock packages carry no invented physical-input/CPU lineage; old exports retain only their exact CRP and receipts.",
            "no_transfer": "This evidence does not transfer agreement to the current runtime checker, the live estimate, a certificate or any other study.",
            "observation_dates": "Observation windows are the recorded driver start/finish times, never the freeze or publication time.",
        },
    }
    manifest_hash = sha(
        (json.dumps(build_manifest_for_files(files), indent=1) + "\n").encode()
    )
    projection = {
        "schema": 1,
        "note": (
            "One accepted outside-stock and budget publication as a typed evidence study, referenced "
            "from Road, Ship and Air. It is not pooled with the outside-query, rail or native studies, "
            "it is not a qualification, promise or certificate, and no archived scorer, collector or "
            "game runs as a product check."
        ),
        "source_manifest": {
            "schema": 1,
            "file": MANIFEST_FILE,
            "sha256": manifest_hash,
            "commit": PUBLICATION["publication_commit"],
            "prefix": PREFIX,
            "publication_files": EXPECTED_PUBLICATION_FILES,
            "copied_files": EXPECTED_CARRIED,
            "linked_files": EXPECTED_LINKED,
            "integrity_members": EXPECTED_INTEGRITY_MEMBERS,
        },
        "studies": {STUDY: study},
    }
    return projection, build_manifest_for_files(files)


def _carried_for_projection() -> dict[str, bytes]:
    return read_carried()


def build_manifest_for_files(files: dict[str, dict]) -> dict:
    ordered = {name: files[name] for name in sorted(files)}
    return {
        "schema": 1,
        "note": (
            "Strict file scope for the accepted outside-stock-budget-v1 publication at its exact "
            "commit. Every one of the 142 added files is pinned by SHA-256, byte length and Git blob "
            "id. `copied` names the 31 files carried in this repository byte for byte plus integrity; "
            "`linked` names the 110 bulky members (frozen plan, frozen features, the three preparation "
            "archives and every retained raw gzip) served as immutable blobs at that commit."
        ),
        "publications": {
            STUDY: {
                "commit": PUBLICATION["publication_commit"],
                "prefix": PREFIX,
                "files": {
                    name: {
                        "bytes": record["bytes"],
                        "sha256": record["sha256"],
                        "git_blob": record["git_blob"],
                        "role": record["role"],
                    }
                    for name, record in ordered.items()
                },
                "copied": sorted(CARRIED),
                "linked": sorted(
                    set(LINKED_BULK) | {n for n in ordered if n.startswith("raw/")}
                ),
                "integrity_file": "integrity.json",
                "publication_files": EXPECTED_PUBLICATION_FILES,
                "integrity_members": EXPECTED_INTEGRITY_MEMBERS,
            }
        },
    }


def verify(projection: dict, facts: dict, files: dict[str, dict]) -> None:
    expect(projection.get("schema") == 1, "outside-stock projection schema changed")
    expect(
        list(projection.get("studies", {})) == [STUDY],
        "outside-stock projection lost its study",
    )
    study = projection["studies"][STUDY]
    expect(
        study["study"] == STUDY and study["kind"] == PUBLICATION["kind"],
        "study identity changed",
    )
    expect(
        study["evidence_only"] is True and study["certificates"] == "none",
        "the study is no longer evidence only",
    )
    source = study["source"]
    expect(
        source["publication_commit"] == PUBLICATION["publication_commit"]
        and source["publication_base"] == PUBLICATION["publication_base"]
        and source["accepted_base"] == PUBLICATION["accepted_base"]
        and source["internal_merge"] == PUBLICATION["internal_merge"]
        and source["pull_request"] == PUBLICATION["pull_request"]
        and source["branch"] == PUBLICATION["branch"]
        and source["source_issue"] == PUBLICATION["source_issue"],
        "the study names another publication or base",
    )
    expect(
        source["review"]
        == {
            "pass": PUBLICATION["review_pass"],
            "engineering_note": PUBLICATION["engineering_note"],
            "parent_acceptance": PUBLICATION["parent_acceptance"],
        },
        "the study's review record changed",
    )
    expect(
        source["history"]["superseded_head"] == PUBLICATION["superseded_head"],
        "the study lost its rejected earlier head",
    )
    expect(
        source["native_sources"] == PUBLICATION["native_sources"],
        "the study's native sources changed",
    )
    closure = study["closure"]
    expect(
        closure["publication_files"] == EXPECTED_PUBLICATION_FILES
        and closure["copied_files"] == EXPECTED_CARRIED
        and closure["linked_files"] == EXPECTED_LINKED
        and closure["integrity_members"] == EXPECTED_INTEGRITY_MEMBERS
        and closure["commit"] == PUBLICATION["publication_commit"]
        and closure["prefix"] == PREFIX,
        "the study's publication closure changed",
    )
    expect(
        len(study["files"]) == EXPECTED_CARRIED
        and len(study["linked"]) == EXPECTED_LINKED,
        "the carried/linked split changed",
    )
    for record in study["files"]:
        relative = record["path"][len(PREFIX) + 1 :]
        expect(
            record["sha256"] == files[relative]["sha256"]
            and record["bytes"] == files[relative]["bytes"]
            and record["git_blob"] == files[relative]["git_blob"],
            f"{record['path']}: carried record differs from the manifest",
        )
    for record in study["linked"]:
        relative = record["path"][len(PREFIX) + 1 :]
        expect(
            record["sha256"] == files[relative]["sha256"]
            and record["git_blob"] == files[relative]["git_blob"],
            f"{record['path']}: linked record differs from the manifest",
        )
        expect(
            exists_relative(record["path"]) is False,
            f"{record['path']}: a linked file is duplicated in the repository",
        )
    expect(
        sum(1 for record in study["linked"] if not record["corroborated"]) == 4,
        "the set of linked members with a single carried declaration changed",
    )
    expect(
        study["population"]["counts"] == EXPECTED_POPULATION,
        "the projection population changed",
    )
    expect(
        study["requests"]["planned"] == EXPECTED_REQUESTS
        and study["requests"]["observed"] == EXPECTED_OBSERVED
        and study["requests"]["unknown"] == EXPECTED_UNKNOWN_CONTROLS
        and study["requests"]["by_kind"]
        == {
            "holdout": EXPECTED_STOCK_REQUESTS,
            "control": EXPECTED_CONTROL_REQUESTS,
            "intervention": EXPECTED_INTERVENTION_REQUESTS,
        },
        "the projection request accounting changed",
    )
    expect(
        study["stock"]["requests"] == EXPECTED_STOCK_REQUESTS
        and tuple(study["stock"]["total"][key] for key in ("tp", "fp", "tn", "fn"))
        == EXPECTED_PRIMARY_TOTAL,
        "the projection stock totals changed",
    )
    expect(
        study["stock"]["qualified_modes"] == {mode: False for mode in MODES},
        "a mode became qualified",
    )
    expect(
        study["bridge"]["subset"]["requests"] == EXPECTED_SNAPSHOT_REQUESTS
        and study["bridge"]["subset"]["not_matched"]
        == EXPECTED_STOCK_REQUESTS - EXPECTED_SNAPSHOT_REQUESTS,
        "the strict bridge subset changed",
    )
    expect(
        study["bridge"]["subset"]["packages"] == ["holdout-01", "holdout-02"],
        "the strict bridge packages changed",
    )
    expect(
        study["controls"]["all_controls_complete"] is False,
        "the controls now claim completion",
    )
    expect(
        study["intervention"]["error_mechanisms"] == "unknown",
        "the intervention now claims a mechanism",
    )
    expect(
        study["intervention"]["drift"]["per_query_road_snapshot_retained"] is False,
        "the drifting group now claims a per-query snapshot",
    )
    expect(
        study["runtime"]["phase_inventories"] == EXPECTED_PHASE_INVENTORIES
        and study["runtime"]["process_identities"] == EXPECTED_PROCESS_IDENTITIES
        and study["runtime"]["openings"] == len(OPENINGS),
        "the runtime accounting changed",
    )
    expect(
        study["runtime"]["launch_caption_used_as_evidence"] is False,
        "a stale launch caption became evidence",
    )
    expect(
        study["drift"]["reported_opening_fingerprint_mismatches"]
        == EXPECTED_OPENING_FINGERPRINT_MISMATCH_REPORTED
        and study["drift"]["pre_query_opening_fingerprint_mismatches"]
        == EXPECTED_OPENING_FINGERPRINT_MISMATCH_REDERIVED,
        "the opening-fingerprint mismatch accounting changed",
    )
    expect(
        study["drift"]["pre_post_query_changes"] == list(EXPECTED_PRE_POST_CHANGES),
        "the pre/post-query change list changed",
    )
    expect(
        study["integrity_reconstruction"]["integrity_members"]
        == EXPECTED_INTEGRITY_MEMBERS,
        "the integrity reconstruction changed",
    )
    expect(
        study["source"]["history"]["superseded_review"]
        == PUBLICATION["superseded_review"],
        "the study lost the superseded review",
    )


def exists_relative(path: str) -> bool:
    return (ROOT / path).exists()


def stock_rows(evaluation: dict) -> list[dict]:
    """One compact row per stock request: both predictions, its label and tags."""
    stated = {}
    for row in evaluation["holdout_rows"]:
        if "rule" not in row:
            continue
        record = stated.setdefault(row["query_id"], {})
        record["case_id"] = row["case_id"]
        record["mode"] = row["mode"]
        record["label"] = row["label"]
        record["snapshot_matched"] = row["snapshot_matched"]
        record["tags"] = row["selection_reasons"]
        record[row["rule"]] = row["prediction"]
    rows = []
    for query_id, record in sorted(stated.items()):
        expect(
            PRIMARY_RULE in record and REFERENCE_RULE in record,
            f"{query_id}: a stock request lost one of its predictions",
        )
        rows.append(
            {
                "id": query_id,
                "case_id": record["case_id"],
                "mode": record["mode"],
                "primary": record[PRIMARY_RULE],
                "reference": record[REFERENCE_RULE],
                "label": record["label"],
                "snapshot_matched": record["snapshot_matched"],
                "tags": record["tags"],
            }
        )
    expect(len(rows) == EXPECTED_STOCK_REQUESTS, "the compact stock row set changed")
    return rows


def summarise(study: dict, projection_sha: str, manifest_sha: str) -> dict:
    def counts(record):
        return {key: record[key] for key in ("tp", "fp", "tn", "fn")}

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
        "integrity_members": study["closure"]["integrity_members"],
        "projection_file": PROJECTION_FILE,
        "projection_sha256": projection_sha,
        "projection_tool_file": "tools/map-factory/integrate_outside_stock.py",
        "source_manifest_file": MANIFEST_FILE,
        "source_manifest_sha256": manifest_sha,
        "population": {
            key: study["population"]["counts"][key]
            for key in (
                "installed",
                "eligible",
                "supported",
                "abstaining",
                "decode_errors",
                "excluded_hashes",
            )
        },
        "selected_packages": len(study["population"]["selection"]["cases"]),
        "planned_requests": study["requests"]["planned"],
        "observed_requests": study["requests"]["observed"],
        "unknown_requests": study["requests"]["unknown"],
        "stock_requests": study["stock"]["requests"],
        "stock_primary": counts(study["stock"]["total"]),
        "stock_reference_road": counts(study["stock"]["reference"]["road"]),
        "stock_modes": {
            mode: {
                "primary": counts(study["stock"]["primary"][mode]),
                "reference": counts(study["stock"]["reference"][mode]),
                "discrimination_estimable": study["stock"]["modes"][mode][
                    "discrimination_estimable"
                ],
            }
            for mode in MODES
        },
        "qualified_modes": {mode: False for mode in MODES},
        "bridge_subset_requests": study["bridge"]["subset"]["requests"],
        "bridge_subset_primary": counts(study["bridge"]["subset"]["primary"]),
        "bridge_subset_reference": counts(study["bridge"]["subset"]["reference"]),
        "bridge_height_drift": study["bridge"]["height_drift"],
        "roslyn_prefab_changes": len(study["bridge"]["roslyn_prefabs"]),
        "opening_pre_post_changes": len(study["drift"]["pre_post_query_changes"]),
        "opening_fingerprint_mismatches_reported": study["drift"][
            "reported_opening_fingerprint_mismatches"
        ],
        "controls": {
            "planned": study["controls"]["cases"]["stock-1"]["planned"]
            + study["controls"]["cases"]["stock-2"]["planned"],
            "unknown": study["controls"]["cases"]["stock-1"]["planned"],
            "completed": study["controls"]["cases"]["stock-2"]["planned"],
            "all_controls_complete": False,
        },
        "intervention": {
            "groups": len(study["intervention"]["groups"]),
            "rows": sum(
                len(group["rows"]) for group in study["intervention"]["groups"]
            ),
            "false_positives": study["intervention"]["cohort"]["old_false_positives"],
            "matched_successes": study["intervention"]["cohort"][
                "matched_old_successes"
            ],
            "clean_single_variable_trials": study["intervention"]["cohort"][
                "clean_single_variable_trials"
            ],
            "drifting_groups": study["intervention"]["cohort"]["drifting_groups"],
            "measured_response": study["intervention"]["measured_response"]["labels"],
            "error_mechanisms": "unknown",
        },
        "runtime": {
            "openings": study["runtime"]["openings"],
            "phase_inventories": study["runtime"]["phase_inventories"],
            "process_identities": study["runtime"]["process_identities"],
            "installed_crp_receipts": len(study["runtime"]["installed_crp_receipts"]),
        },
        "observation_windows": study["runtime"]["observation_windows"],
        "evidence_files_sha256": sha(
            canon(
                [[record["path"], record["sha256"]] for record in study["files"]]
            ).encode()
        ),
        "linked_files_sha256": sha(
            canon(
                [[record["path"], record["sha256"]] for record in study["linked"]]
            ).encode()
        ),
        "certificates": "none",
    }


def ledger_summary(
    study: dict, projection_sha: str, manifest_sha: str, tool_sha: str
) -> dict:
    summary = summarise(study, projection_sha, manifest_sha)
    summary["projection_tool_sha256"] = tool_sha
    return summary


def indent_block(value) -> str:
    text = json.dumps(value, indent=2)
    first, *rest = text.split("\n")
    return "\n".join([first, *("  " + line for line in rest)])


def update_ledger(summary: dict) -> None:
    """Add this study's binding without rewriting unowned ledger bytes."""
    path = ROOT / LEDGER_FILE
    raw = path.read_text()
    block = f'      "{LEDGER_KEY}": [\n        "{STUDY}"\n      ]'
    reference = (
        '      "outside_research_studies": [\n        "outside-query-model-v1"\n      ]'
    )
    # The sibling outside-query producer rewrites its own reference by finding
    # `limits` immediately followed by its block. This reference therefore sits
    # after that block, so both producers can regenerate without duplicating it.
    if f"{reference},\n{block}" not in raw:
        expect(
            raw.count(reference) == len(MODES),
            "the sibling outside-query references moved",
        )
        raw = raw.replace(reference, f"{reference},\n{block}")

    # Keep this producer's object immediately before the sibling outside-query
    # object, so regenerating either sibling preserves the other's bytes.
    sibling = '\n  "outside_research_studies": '
    head = f'\n  "{LEDGER_KEY}": '
    block = indent_block(summary)
    index = raw.find(head)
    if index >= 0:
        stop = raw.find(sibling, index)
        expect(stop > index, "the sibling outside-query ledger object moved")
        raw = raw[:index] + head + block + "," + raw[stop:]
    else:
        stop = raw.find(sibling)
        expect(stop > 0, "the sibling outside-query ledger object is missing")
        raw = raw[:stop] + head + block + "," + raw[stop:]
    path.write_text(raw)
    ledger = json.loads(raw)
    for capability in MODES:
        entry = next(
            item for item in ledger["capabilities"] if item["id"] == capability
        )
        expect(
            entry.get(LEDGER_KEY) == [STUDY],
            f"{capability}: the study reference was not written",
        )
    expect(
        ledger[LEDGER_KEY] == summary,
        "the written ledger summary differs from the projection",
    )


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


def capability_limits(capability: str) -> str:
    return CAPABILITY_LIMITS[capability]


def rebuild() -> tuple[dict, dict, dict]:
    carried = read_carried()
    files = _manifest_files_from_carried(carried)
    # The linked members carry no bytes in this repository; take their pinned
    # length and blob id from the committed manifest and check the hash chain.
    manifest_path = ROOT / MANIFEST_FILE
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_bytes())
        check_manifest(manifest, carried)
        published = manifest["publications"][STUDY]["files"]
        for name, record in published.items():
            if name in carried:
                continue
            expect(
                files[name]["sha256"] == record["sha256"],
                f"{name}: the committed manifest disagrees with the integrity record",
            )
            files[name]["bytes"] = record["bytes"]
            files[name]["git_blob"] = record["git_blob"]
            files[name]["role"] = record["role"]
    facts = derive(carried)
    projection, manifest = assemble(facts, files)
    return projection, manifest, facts


def main() -> int:
    args = sys.argv[1:]
    tool_sha = sha(Path(__file__).resolve().read_bytes())
    if "--source" in args:
        source = Path(args[args.index("--source") + 1]).resolve()
        docs = publication_documents(source)
        carried = {name: docs[name] for name in CARRIED}
        files = {}
        for name, raw in docs.items():
            files[name] = {
                "sha256": sha(raw),
                "bytes": len(raw),
                "git_blob": git_blob(raw),
                "role": file_role(name),
            }
        facts = derive(carried, docs)
        projection, manifest = assemble(facts, files)
        verify(projection, facts, files)
        manifest_raw = (json.dumps(manifest, indent=1) + "\n").encode()
        expect(
            projection["source_manifest"]["sha256"] == sha(manifest_raw),
            "projection does not bind the manifest it writes",
        )
        raw = (json.dumps(projection, indent=1) + "\n").encode()
        (ROOT / MANIFEST_FILE).write_bytes(manifest_raw)
        (ROOT / PROJECTION_FILE).write_bytes(raw)
        study = projection["studies"][STUDY]
        update_ledger(ledger_summary(study, sha(raw), sha(manifest_raw), tool_sha))
        print(
            f"wrote {MANIFEST_FILE} ({len(manifest_raw)} bytes, {sha(manifest_raw)}), "
            f"{PROJECTION_FILE} ({len(raw)} bytes, {sha(raw)}) and the ledger binding"
        )
        print(json.dumps(summarise(study, sha(raw), sha(manifest_raw)), indent=1))
        return 0

    projection, manifest, facts = rebuild()
    verify(
        projection,
        facts,
        {
            name: {
                "sha256": record["sha256"],
                "bytes": record["bytes"],
                "git_blob": record["git_blob"],
                "role": record["role"],
            }
            for name, record in manifest["publications"][STUDY]["files"].items()
        },
    )
    projection_raw = (json.dumps(projection, indent=1) + "\n").encode()
    manifest_raw = (json.dumps(manifest, indent=1) + "\n").encode()
    committed_projection = (ROOT / PROJECTION_FILE).read_bytes()
    committed_manifest = (ROOT / MANIFEST_FILE).read_bytes()
    if "--check" in args:
        expect(
            committed_projection == projection_raw,
            "the committed outside-stock projection is stale; re-run the importer",
        )
        expect(
            committed_manifest == manifest_raw,
            "the committed outside-stock source manifest is stale; re-run the importer",
        )
        ledger = json.loads((ROOT / LEDGER_FILE).read_text())
        study = projection["studies"][STUDY]
        expect(
            ledger[LEDGER_KEY]
            == ledger_summary(
                study, sha(committed_projection), sha(committed_manifest), tool_sha
            ),
            "the ledger binding is stale or unbound",
        )
        summary = ledger_summary(
            study, sha(committed_projection), sha(committed_manifest), tool_sha
        )
        print(
            f"outside-stock projection is current: {sha(committed_projection)} "
            f"(manifest {sha(committed_manifest)})"
        )
        print(json.dumps(summary, indent=1))
        return 0

    expect(
        committed_projection == projection_raw,
        "regeneration does not reproduce the committed projection",
    )
    expect(
        committed_manifest == manifest_raw,
        "regeneration does not reproduce the committed manifest",
    )
    study = projection["studies"][STUDY]
    update_ledger(
        ledger_summary(study, sha(projection_raw), sha(manifest_raw), tool_sha)
    )
    print(
        f"regenerated {PROJECTION_FILE} and the ledger binding: {sha(projection_raw)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
