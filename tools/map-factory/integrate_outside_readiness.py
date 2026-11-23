"""Integrate the accepted PL-1313 stopped control-readiness study as one typed study.

This reads archived bytes only. It never runs the study's frozen collector,
driver, auditor, bundle builder, evaluator or reporter, never imports the
staged harness, never re-derives a prediction and never opens the game. It
re-checks the publication's exact 26-file scope, re-derives the canonical
82-file study-tree digest and the versioned 30-file contract digest by parsing
two constant declarations as data, verifies the 51 retained raw hashes, and
writes one projection the ledger page renders under Road, Ship and Air.

The study is evidence only, and its outcome is Unknown: both corrected controls
ran and returned their required literal labels, then the byte-backed readiness
gate refused admission, so zero holdout requests exist and all six planned
cells stay Unknown. Saved-label and digest arithmetic are the only "replays"
here; no archived executable or outcome function is imported or executed.

Three modes:

    python3 tools/map-factory/integrate_outside_readiness.py \
        --source <worktree-at-4eca> --raw <private-raw-holding>
        Derive the manifest and projection from the exact producer worktree at
        the publication commit and the same-owner raw holding. Requires the
        producer commit and the pre-control freeze commit to be reachable.

    python3 tools/map-factory/integrate_outside_readiness.py
        Re-derive both documents from the carried evidence and the committed
        manifest, then write them. Deterministic; sibling studies and the four
        retained native certificates are untouched.

    python3 tools/map-factory/integrate_outside_readiness.py --check
        Re-derive and refuse any committed projection, manifest, carried byte,
        raw byte, ledger binding or derived table that differs.
"""

from __future__ import annotations

import ast
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tools/map-factory/capability-evidence"
STUDY = "outside-readiness-stock-v2"
PREFIX = f"tools/map-factory/capability-evidence/{STUDY}"
MANIFEST_FILE = "tools/map-factory/capability-evidence/outside-readiness-sources.json"
PROJECTION_FILE = "tools/map-factory/capability-evidence/outside-readiness-studies.json"
LEDGER_FILE = "capabilities.json"
LEDGER_KEY = "outside_readiness_studies"
RAW_PREFIX = f"tools/map-factory/capability-evidence/{STUDY}-raw"

MODES = ("road", "ship", "air")
CELLS = tuple(f"{mode}:{kind}" for mode in MODES for kind in ("success", "no_path"))
RULE = "lane:any_lane:forbidden"
REFERENCE = "weak_component"

PUBLICATION = {
    "study": STUDY,
    "kind": "outside_readiness_stock_study",
    "title": "Corrected outside-query controls on a frozen unseen stock cohort",
    "publication_commit": "4eca4d291cc133513e8bac6484185d3a3b6e80ae",
    "publication_base": "86fee78d9517eff3c0e715813202b7b81b7e11d1",
    "frozen_commit": "bd00a4cd1719afb32a67601949103ca8ef9cf76d",
    "internal_merge": "10be1b73598d7080afae44010c9de8b99d295316",
    "pull_request": 93,
    "branch": "PL-1313-stock-v2",
    "target": "PL-1142-native-v2",
    "source_issue": "01a2097f-7ea5-7803-ad5b-21f13dc72289",
    "review_pass": "01a2099e-0d6c-7a16-8749-a3544357356a",
    "acceptance": "01a209a4-8c98-7e83-b6e3-0fbcb257f550",
}

# The 25 files carried here byte for byte. The publication's 26th file,
# features.json.gz, is a bulk frozen feature dump and stays at the publication
# commit as an immutable Git blob.
CARRIED = (
    "README.md",
    "RESULTS.md",
    "assemble_v2.py",
    "audit_v2.py",
    "build_v2.py",
    "bundle.json",
    "bundle_v2.py",
    "check_study.py",
    "collect_v2.py",
    "evaluate_v2.py",
    "evaluation.json",
    "exclusions.json",
    "finalize_v2.py",
    "freeze.json",
    "inventory.json",
    "module.json",
    "predictions.json",
    "readiness_v3.py",
    "report_v2.py",
    "requests.json",
    "run_v2.py",
    "schema_v3.py",
    "selection.json",
    "stock_v2.py",
    "test_study_v2.py",
)
LINKED = {"features.json.gz": "frozen_features"}

MODULE_MEMBERS = frozenset((set(CARRIED) | set(LINKED)) - {"module.json"})
# Files that did not exist at the pre-control freeze commit bd00a4c. They were
# written after the two control openings, outside the frozen measurement
# closure, and measure nothing.
POST_CONTROL = frozenset(
    {
        "RESULTS.md",
        "assemble_v2.py",
        "bundle.json",
        "evaluation.json",
        "finalize_v2.py",
        "report_v2.py",
    }
)
# Files whose bytes changed between the freeze and the publication. The freeze
# record pins their pre-control bytes; that record is a declaration, not a
# second copy, and the page never presents it as one.
FROZEN_CHANGED = frozenset({"README.md", "module.json"})

# Five small retained raw files are carried gzip-compressed so the page can
# serve observation windows and the verbatim refusal without copying the
# private holding or the game bytes. Each must decompress to its original
# bytes, and each original hash is one of the 51 recorded hashes below.
RAW_CARRIED = {
    "drivers/stock-1/driver-launch.json": "raw_driver_launch",
    "drivers/stock-2/driver-launch.json": "raw_driver_launch",
    "stock-1/auditor-receipt.json": "raw_auditor_receipt",
    "stock-2/auditor-receipt.json": "raw_auditor_receipt",
    "readiness-result.json": "raw_readiness_result",
}

DOCUMENTS = ("README.md", "RESULTS.md")
TOOLS = frozenset(name for name in CARRIED if name.endswith(".py"))

EXPECTED_PUBLICATION_FILES = 26
EXPECTED_MODULE_MEMBERS = 25
EXPECTED_CARRIED = 25
EXPECTED_LINKED = 1
EXPECTED_FROZEN_PUBLICATION_FILES = 20
EXPECTED_POST_CONTROL = 6
EXPECTED_RAW_FILES = 51
EXPECTED_RAW_CARRIED = 5
EXPECTED_FROZEN_SOURCE_FILES = 82
EXPECTED_CONTRACT_SOURCE_FILES = 30
EXPECTED_MODULE_VERSION = 3
EXPECTED_TESTS = 59
EXPECTED_OLD_FACTS = 84
EXPECTED_OLD_PUBLICATION_FILES = 142
EXPECTED_READINESS_FILES = 24
EXPECTED_POOL = 25
EXPECTED_PACKAGES = 1
EXPECTED_HOLDOUT = 6
EXPECTED_CONTROLS = 12
EXPECTED_REQUESTS = 18
EXPECTED_POPULATION = {"packages": 105, "eligible": 25, "excluded_hashes": 26}
EXPECTED_INVENTORY = {"files": 45, "roots": 11, "plugins": 7, "assemblies": 23}
EXPECTED_OWNED_PROCESSES = 10
EXPECTED_INVENTORIES_PER_OPENING = 3

DLL = {
    "bytes": 145408,
    "mvid": "65019b31-a6bb-4e72-a75d-ca664806ef23",
    "sha256": "7b15fba2e424954e51120a9fdbe79e7d43606e5922f2fdd6389a3044a6944d75",
}
GAME_EXECUTABLE_SHA256 = (
    "a18607b230f20b5653379a8debb6d5fe69e3ccd45863798f2e2a5ec403b8a9ca"
)
PROTOCOL = {
    "entry": "NewGameFromMap",
    "invert_traffic": False,
    "max_length": 100000,
    "seed": 857,
    "version": 2,
}
STUDY_SOURCE_SHA256 = "03f7fb7c8eb8e3d6dd94f6444c5cd0cbd2156c325148b1006b564776a34f226d"
CONTRACT_SOURCE_SHA256 = (
    "561e4b522bc27fe9c06eb59a0ed875461b47277a2379c18d5998b8e753854860"
)
BUNDLE_SHA256 = "767de08aeb6df62a5e81dcc5d4ec98f03d282f6685347e39a07796e0df38018b"
FROZEN_SHA256 = "8e8d6a52043adfb3a4e542991934325bcaba61721cbc31a1ab89ce4ea8c97d1f"
ASSEMBLER_SHA256 = "d8c41863b6ed62b02d3e6f9dfa3d0f55283d978850b9b6243183e163956a7961"
PREDICTIONS_SHA256 = "2f881983ae9bce49b387c90469a8bdc31ea17a26a42a446115a7c98f44635d7f"
REQUESTS_SHA256 = "e656ce84e6344c456bdeefefbb9e1809d92d261c402f6cf05b25030fbbbbef6d"
SELECTION_SHA256 = "50b44bb9ce7d76691974527db970b182d6968eb4a0cc3036493e943d0ae2a092"
EXCLUSIONS_SHA256 = "8bd8392301c7f358b38af7c41e23c6d7702380f23f265bc8e03b9ff1babcc68b"
INVENTORY_SHA256 = "a9704585c2d4a008030d2d65c574badaf1157f0ece042b7e3e4e7730ad1f7ee5"
CATALOG_SHA256 = "3b2136cd959f23cc77cfb8d28821e58b9a046300ee5f0e9f9e179ca1bf577241"
EXCLUSION_DIGEST = "8746db45b9a620c52c0cbf47eb0f760c0610ed03d9325635430bfc041a0ab8ca"
PRIOR_STOCK_FREEZE_SHA256 = (
    "20dfb33d863deb4fd13abcbeb952a59e139f93910216771c74fd21c069935a18"
)
OLD_QUERY_MODEL_PACKAGES_SHA256 = (
    "06a3ce9a85241d1260af85f14e13627da2f46731464e6b3887d05d120cd42ccb"
)
STOCK_EXCLUSION_COMMIT = "914c153687106197e5f3a745d3ff7e181181ea8a"
OUTSIDE_QUERY_MODEL_COMMIT = "030db86ce470b972b6ef3462a2698744dff40ebb"
CAVERN_COAST_SHA256 = "8888d2e4cff59babd69afa0a11417e97f4c8486bcffde6891e9dd8afb29245ac"
ASANU_SHA256 = "254f5ee48d22dae83d002915b76b89bb90a5bd184f74dc49a39984826de31166"
HANAMI_SHA256 = "f621eaa42d1236db722e8ed70d870a94bf85ca21cac3357509129b84057319c6"

SCOPE = (
    "One corrected control-readiness opening on a frozen, previously unqueried stock cohort. Both "
    "control openings ran as frozen and returned the required literal labels; the byte-backed readiness "
    "gate then refused admission, so no holdout request was issued and all six planned mode/class cells "
    "stay Unknown. It is not a model, a qualification, an admission repair, a new calibration score, a "
    "retry of the old study or a game run."
)

METHOD = (
    "The frozen pre-control plan bound source, build, catalog, inputs, selection, requests, "
    "predictions, controls, protocol, structural expectations and stop policy before the first control "
    "request. This ledger re-checks the archived bytes, re-derives the canonical 82-file study-tree "
    "digest, derives the versioned 30-file contract closure from the two constant declarations it "
    "parses as data, and checks that every closure file is present in the freeze with the same hash. It "
    "then re-derives the control arithmetic and the retained raw hashes. It does not run the collector, "
    "driver, auditor, bundle builder, evaluator, reporter, scorer, model or game."
)

SURVIVES = (
    "The two corrected controls are complete, released and returned the required literal labels: six "
    "positive requests succeeded and six invalid-vehicle requests failed. The independent pre-request "
    "build index equals the request's effective argument on all twelve rows, the opening graph equals "
    "the post graph on both openings, and all ten owned PID/start identities are gone after the driver "
    "exited, verified by a post-exit audit rather than a self-attestation. Controls are known controls, "
    "not holdout predictions and not independent capability votes."
)

STOPPED = (
    "The frozen freeze.json binds an 82-file study-tree source manifest. The accepted readiness "
    "contract requires frozen.source_files to be exactly the versioned 30-file closure and requires "
    "the runtime phase's source_sha256 to equal that closure's digest. The collector recorded the "
    "82-file digest instead. Those two values cannot both be true of one measured opening. Correcting "
    "the recorded binding would rewrite a measured field after the controls; changing the closure "
    "would change the frozen source digest and require new controls. The no-retry rule forbids both, "
    "so the unchanged checker is left refusing and both digests stay recorded."
)

LIMITS = (
    "The outcome is Unknown and limited: zero of six planned holdout requests were issued, so no "
    "holdout accuracy, precision or recall exists; those denominators stay null and not estimable, "
    "never 0%. The two controls are control-readiness observations, not a decision law, not holdout "
    "votes and not a qualification. No geographic negative, service, spawning, sustained-navigation, "
    "stable-water or admission claim follows. The old PL-1294 six Unknowns are unchanged and the new "
    "controls do not rescue them. Replaying the retained checks needs the exact licensed game bytes "
    "and CRPs named by hash in bundle.json; they stay in the same-owner private blade holding and are "
    "neither in this repository nor attached to the issue. A fresh clone cannot reproduce the full "
    "verify: it expects the untracked .build/Cs1Harness.dll and the original absolute staged-source "
    "path. File identity is not memory attestation, compiler trust or strict-no-mods evidence. "
    "Assemble_v2, finalize_v2 and report_v2 were written after the controls, are outside the frozen "
    "measurement closure, and measure and qualify nothing. No certificate, app adoption, model refit, "
    "public merge or Shelf page follows."
)


def fail(message: str) -> None:
    raise SystemExit(f"outside-readiness: {message}")


def expect(condition, message: str) -> None:
    if not condition:
        fail(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def canon(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value) -> str:
    return sha(canon(value).encode())


# --- reading the exact producer worktree, without executing any of it ---------


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def git_text(repo: Path, *args: str) -> str:
    return git(repo, *args).decode()


def publication_documents(source: Path) -> dict[str, bytes]:
    """Every file of the publication prefix at its exact commit, by Git object."""
    head = git_text(source, "rev-parse", "HEAD").strip()
    expect(
        head == PUBLICATION["publication_commit"],
        f"source worktree HEAD is {head}, not the publication commit",
    )
    expect(
        git_text(source, "cat-file", "-t", PUBLICATION["frozen_commit"]).strip()
        == "commit",
        "the pre-control freeze commit is not reachable from the source worktree",
    )
    paths = git_text(
        source,
        "ls-tree",
        "-r",
        "--name-only",
        PUBLICATION["publication_commit"],
        "--",
        PREFIX + "/",
    ).split()
    relative = sorted(path[len(PREFIX) + 1 :] for path in paths)
    expected = sorted(CARRIED + tuple(LINKED))
    expect(
        relative == expected,
        f"the publication prefix is not the exact 26-file scope: {relative}",
    )
    return {
        name: git(
            source, "show", f"{PUBLICATION['publication_commit']}:{PREFIX}/{name}"
        )
        for name in relative
    }


def frozen_documents(source: Path) -> dict[str, bytes]:
    """The files that already existed at the pre-control freeze commit."""
    paths = git_text(
        source,
        "ls-tree",
        "-r",
        "--name-only",
        PUBLICATION["frozen_commit"],
        "--",
        PREFIX + "/",
    ).split()
    relative = sorted(path[len(PREFIX) + 1 :] for path in paths)
    expect(
        len(relative) == EXPECTED_FROZEN_PUBLICATION_FILES,
        f"the frozen prefix has {len(relative)} files, not 20",
    )
    expect(
        len(set(relative) & POST_CONTROL) == 0,
        "a post-control file already existed at the freeze commit",
    )
    expect(
        relative == sorted((set(CARRIED) | set(LINKED)) - POST_CONTROL),
        "the pre-control file set is not the carried set minus the six post-control files",
    )
    return {
        name: git(source, "show", f"{PUBLICATION['frozen_commit']}:{PREFIX}/{name}")
        for name in relative
    }


def _strings(node) -> list[str] | None:
    """Evaluate only the constant string-list shapes used by the source closure."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple)):
        out: list[str] = []
        for element in node.elts:
            part = _strings(element)
            if part is None:
                return None
            out += part
        return out
    if isinstance(node, (ast.ListComp, ast.GeneratorExp, ast.SetComp)):
        if len(node.generators) != 1:
            return None
        generator = node.generators[0]
        if not isinstance(generator.target, ast.Name) or generator.ifs:
            return None
        names = _strings(generator.iter)
        if names is None or not isinstance(node.elt, ast.BinOp):
            return None
        if not isinstance(node.elt.op, ast.Add) or not isinstance(
            node.elt.right, ast.Name
        ):
            return None
        if node.elt.right.id != generator.target.id:
            return None
        left = node.elt.left
        if not isinstance(left, ast.Constant) or not isinstance(left.value, str):
            return None
        return [left.value + name for name in names]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        right = _strings(node.right)
        left = _strings(node.left)
        if left is None or right is None:
            return None
        return left + right
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        right = _strings(node.right)
        left = _strings(node.left)
        if left is None or right is None:
            return None
        return sorted(set(left) | set(right))
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "frozenset"
        and len(node.args) == 1
    ):
        return _strings(node.args[0])
    return None


def declared_strings(text: str, name: str, where: str) -> list[str]:
    """Parse one module-level constant declaration as data; execute nothing."""
    tree = ast.parse(text)
    for statement in tree.body:
        target = None
        value = None
        if isinstance(statement, ast.Assign):
            if len(statement.targets) == 1 and isinstance(
                statement.targets[0], ast.Name
            ):
                target, value = statement.targets[0].id, statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            target, value = statement.target.id, statement.value
        if target == name and value is not None:
            strings = _strings(value)
            expect(strings is not None, f"{where}: {name} is not a constant string set")
            expect(len(set(strings)) == len(strings), f"{where}: {name} repeats a name")
            return sorted(strings)
    fail(f"{where}: {name} is missing")


def closure_keys(source: Path) -> list[str]:
    """Derive the versioned closure from the two exact constant declarations."""
    v1 = git_text(
        source,
        "show",
        f"{PUBLICATION['publication_commit']}:"
        "tools/map-factory/capability-evidence/outside-readiness-v1/schema.py",
    )
    v3 = git_text(
        source,
        "show",
        f"{PUBLICATION['publication_commit']}:{PREFIX}/schema_v3.py",
    )
    accepted = declared_strings(v1, "SOURCE_KEYS", "outside-readiness-v1/schema.py")
    added = declared_strings(v3, "NEW_SOURCES", f"{STUDY}/schema_v3.py")
    keys = sorted(set(accepted) | set(added))
    expect(
        len(accepted) == 20
        and len(added) == 10
        and len(keys) == EXPECTED_CONTRACT_SOURCE_FILES,
        f"the versioned closure is {len(accepted)} + {len(added)} = {len(keys)} files",
    )
    expect(
        not set(accepted) & set(added),
        "a required closure file is declared twice",
    )
    return keys


def raw_manifest(raw: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in sorted(raw.rglob("*")):
        if path.is_file():
            files[str(path.relative_to(raw))] = path.read_bytes()
    expect(
        len(files) == EXPECTED_RAW_FILES,
        f"the raw holding has {len(files)} files, not 51",
    )
    return files


# --- deriving the study facts from archived bytes only -----------------------


def check_module(
    documents: dict[str, bytes], linked_hashes: dict[str, str] | None = None
) -> dict:
    module = json.loads(documents["module.json"])
    expect(module.get("module") == STUDY, "module.json names another study")
    expect(
        module.get("source") == PUBLICATION["publication_base"], "module source changed"
    )
    expect(module.get("target") == PUBLICATION["target"], "module target changed")
    expect(module.get("version") == EXPECTED_MODULE_VERSION, "module version changed")
    files = module.get("files") or {}
    expect(
        set(files) == MODULE_MEMBERS and len(files) == EXPECTED_MODULE_MEMBERS,
        "module.json no longer lists the exact 25 members",
    )
    linked_hashes = linked_hashes or {}
    for name, hashed in files.items():
        if name in documents:
            expect(
                sha(documents[name]) == hashed,
                f"{name}: module hash disagrees with its bytes",
            )
        else:
            expect(
                linked_hashes.get(name) == hashed,
                f"{name}: the linked module member does not match the manifest",
            )
    return {
        "version": module["version"],
        "source": module["source"],
        "target": module["target"],
        "members": len(files),
        "created_at": module["created_at"],
    }


def check_evaluation(evaluation: dict) -> dict:
    expect(evaluation.get("schema") == 2, "evaluation schema changed")
    expect(
        evaluation.get("result") == "unknown",
        "the retained outcome is no longer Unknown",
    )
    expect(evaluation.get("issue") == "PL-1313", "evaluation names another issue")
    expect(
        evaluation.get("bundle_sha256") == BUNDLE_SHA256,
        "evaluation bundle hash changed",
    )
    expect(
        evaluation.get("freeze_sha256") == FROZEN_SHA256,
        "evaluation freeze hash changed",
    )
    expect(
        evaluation.get("holdout_planned") == EXPECTED_HOLDOUT,
        "planned holdout count changed",
    )
    expect(evaluation.get("holdout_observed") == 0, "a holdout request is now observed")
    holdout = evaluation["holdout"]
    expect(len(holdout) == EXPECTED_HOLDOUT, "holdout record count changed")
    for row in holdout:
        expect(
            row["status"] == "unobserved_unknown",
            f"{row['query_id']}: a planned cell is no longer Unknown",
        )
        expect(
            row["package_sha256"] == CAVERN_COAST_SHA256,
            f"{row['query_id']}: the selected package changed",
        )
        expect(
            row["prediction"] == row["class"]
            and row["class"] in ("success", "no_path"),
            f"{row['query_id']}: prediction and class disagree",
        )
    controls = evaluation["controls"]
    expect(len(controls) == 2, "control opening count changed")
    rows = []
    for case in controls:
        expect(case["case_id"] in ("stock-1", "stock-2"), "control case name changed")
        expect(
            case["inventory_files"] == 45,
            f"{case['case_id']}: inventory file count changed",
        )
        expect(
            case["inventory_roots"] == 11,
            f"{case['case_id']}: inventory root count changed",
        )
        expect(len(case["plugins"]) == 7, f"{case['case_id']}: plugin set changed")
        expect(case["assemblies"] == 23, f"{case['case_id']}: assembly count changed")
        expect(
            case["opening_graph_sha256"] == case["post_graph_sha256"],
            f"{case['case_id']}: the opening and post graphs differ",
        )
        expect(len(case["rows"]) == 6, f"{case['case_id']}: control row count changed")
        for role, record in case["cleanup"].items():
            expect(
                record["gone"] is True,
                f"{case['case_id']}/{role}: an owned process is not gone",
            )
        for row in case["rows"]:
            expect(row["complete"] is True, f"{row['query_id']}: control is incomplete")
            expect(
                row["released"] is True, f"{row['query_id']}: control was not released"
            )
            expect(
                row["pre_build_index"] == row["effective_build_index"],
                f"{row['query_id']}: the independent build index does not equal the effective one",
            )
            expect(
                row["label"] == ("success" if row["kind"] == "positive" else "no_path"),
                f"{row['query_id']}: control label changed",
            )
            rows.append(
                {
                    "case_id": case["case_id"],
                    "query_id": row["query_id"],
                    "mode": row["mode"],
                    "kind": row["kind"],
                    "label": row["label"],
                    "flags": row["flags"],
                    "complete": row["complete"],
                    "released": row["released"],
                    "pre_build_index": row["pre_build_index"],
                    "effective_build_index": row["effective_build_index"],
                }
            )
    expect(len(rows) == EXPECTED_CONTROLS, "control request count changed")
    expect(
        sum(1 for row in rows if row["label"] == "success") == 6
        and sum(1 for row in rows if row["label"] == "no_path") == 6,
        "the control label split changed",
    )
    owned = {
        case["case_id"]: {role: record for role, record in case["cleanup"].items()}
        for case in controls
    }
    return {
        "result": evaluation["result"],
        "holdout": holdout,
        "controls": controls,
        "rows": rows,
        "owned": owned,
        "created_at": evaluation["created_at"],
        "limits": evaluation["limits"],
        "raw_files": evaluation["raw_files"],
    }


def check_freeze(freeze: dict) -> dict:
    expect(freeze.get("schema") == 2, "freeze schema changed")
    expect(freeze.get("issue") == "PL-1313", "freeze names another issue")
    expect(
        freeze.get("source") == PUBLICATION["publication_base"], "freeze source changed"
    )
    expect(freeze.get("target") == PUBLICATION["target"], "freeze target changed")
    expect(
        freeze.get("canonical") == "compact sorted JSON, UTF-8, no trailing newline",
        "canonical encoding changed",
    )
    expect(
        freeze.get("git_commit_at_freeze")
        == "5e5343b6e254952a27e622df25028f3229c7c688",
        "the recorded freeze commit changed",
    )
    sources = freeze["source_files"]
    expect(
        len(sources) == EXPECTED_FROZEN_SOURCE_FILES,
        "the frozen 82-file manifest changed",
    )
    expect(
        digest(sources) == STUDY_SOURCE_SHA256,
        "the frozen study-tree digest is not re-derivable from its own map",
    )
    expect(
        freeze.get("source_sha256") == STUDY_SOURCE_SHA256,
        "the frozen source digest changed",
    )
    old = (
        freeze.get("old_fact_count"),
        freeze.get("old_publication_files"),
        freeze.get("readiness_files"),
    )
    expect(
        old
        == (
            EXPECTED_OLD_FACTS,
            EXPECTED_OLD_PUBLICATION_FILES,
            EXPECTED_READINESS_FILES,
        ),
        "the immutable old fact and file counts changed",
    )
    expect(
        freeze.get("old_facts_sha256")
        == "2599600ea9e2bdb2b051171d29f7ffea52fc6f3f7882fc80884958b550a8fc38",
        "the old facts digest changed",
    )
    expect(
        freeze.get("old_publication_sha256")
        == "0e655b600002e72164d6fd25d73cb37d50faeb6ddcecb1173b0af22aa0080313"
        and freeze.get("readiness_sha256")
        == "818901d912af1e4f74c756a20e2c56f5d8b404b2f7beab4f5618f41eb783c072",
        "an immutable sibling digest changed",
    )
    build = freeze["build"]
    expect(
        build["dll"]["sha256"] == DLL["sha256"]
        and build["dll"]["mvid"] == DLL["mvid"]
        and build["dll"]["bytes"] == DLL["bytes"],
        "the frozen DLL identity changed",
    )
    expect(
        build["game_executable_sha256"] == GAME_EXECUTABLE_SHA256,
        "the frozen game executable hash changed",
    )
    expect(
        len(build["original_sources"]) == 17 and len(build["staged_sources"]) == 17,
        "the staged harness source count changed",
    )
    expect(freeze["protocol"] == PROTOCOL, "the frozen protocol frame changed")
    expect(
        freeze["catalog"]
        == {
            "path": "outside-stock-budget-v1/prior-stock-catalogs.json",
            "sha256": CATALOG_SHA256,
        },
        "the frozen catalog binding changed",
    )
    expect(
        freeze["predictions"]
        == {"digest": PREDICTIONS_SHA256, "file_sha256": PREDICTIONS_SHA256},
        "the frozen prediction binding changed",
    )
    expect(
        freeze["requests"]
        == {
            "digest": "3d8b8980a6306fc8aa8d807d79fdc33ef723928c0a3aae6fe3ef57f7a748c9de",
            "file_sha256": REQUESTS_SHA256,
        },
        "the frozen request binding changed",
    )
    expect(
        freeze["selection"]
        == {"digest": SELECTION_SHA256, "file_sha256": SELECTION_SHA256}
        and freeze["exclusions"]
        == {"digest": EXCLUSION_DIGEST, "file_sha256": EXCLUSIONS_SHA256},
        "the frozen selection or exclusion binding changed",
    )
    expect(
        freeze["inventory"]["file_sha256"] == INVENTORY_SHA256
        and freeze["inventory"]["packages"] == 105
        and freeze["inventory"]["eligible"] == 25,
        "the frozen inventory binding changed",
    )
    expect(
        all(row["rule"] == RULE for row in freeze["holdout"]),
        "the frozen rule changed",
    )
    expect(
        len(freeze["holdout"]) == EXPECTED_HOLDOUT and len(freeze["controls"]) == 2,
        "the frozen plan count changed",
    )
    stop = freeze["stop_policy"]
    expect(
        stop["no_retry"] is True
        and stop["max_holdout_requests"] == 18
        and stop["max_path_requests"] == 30
        and stop["max_openings"] == 5,
        "the frozen stop policy changed",
    )
    expect(
        stop["max_control_openings"] == 2 and stop["max_control_requests"] == 12,
        "the frozen control budget changed",
    )
    return {
        "frozen_at": freeze["frozen_at"],
        "git_commit_at_freeze": freeze["git_commit_at_freeze"],
        "source_files": len(sources),
        "source_sha256": STUDY_SOURCE_SHA256,
        "protocol": freeze["protocol"],
        "stop_policy": stop,
        "old_fact_count": old[0],
        "old_publication_files": old[1],
        "readiness_files": old[2],
        "dll": build["dll"],
        "game_executable_sha256": build["game_executable_sha256"],
        "compiler": build["compiler"],
        "prior_sessions": freeze["prior_sessions"],
    }


def check_requests(requests: dict, predictions: dict, freeze: dict) -> dict:
    expect(
        set(predictions) == set(requests["query_ids"]),
        "predictions and query ids disagree",
    )
    expect(len(predictions) == EXPECTED_REQUESTS, "prediction count changed")
    expect(
        len(requests["controls"]) == 2 and len(requests["holdout"]) == 6,
        "request plan count changed",
    )
    control_ids = [
        request["query_id"]
        for case in requests["controls"]
        for request in case["requests"]
    ]
    holdout_ids = [request["query_id"] for request in requests["holdout"]]
    expect(
        len(control_ids) == EXPECTED_CONTROLS and len(holdout_ids) == EXPECTED_HOLDOUT,
        "request rows changed",
    )
    expect(
        set(control_ids) & set(holdout_ids) == set(),
        "a request is both control and holdout",
    )
    expect(
        sorted(control_ids + holdout_ids) == sorted(predictions),
        "a planned request has no prediction",
    )
    for case in requests["controls"]:
        expect(
            case["predictions"]
            == {
                request["query_id"]: predictions[request["query_id"]]
                for request in case["requests"]
            },
            f"{case['case_id']}: control predictions disagree",
        )
        for request in case["requests"]:
            expect(
                request["max_length"] == 100000,
                f"{request['query_id']}: the request budget changed",
            )
    for request in requests["holdout"]:
        expect(
            request["rule"] == RULE, f"{request['query_id']}: the holdout rule changed"
        )
        expect(
            request["prediction"] == predictions[request["query_id"]],
            f"{request['query_id']}: prediction disagrees",
        )
        expect(
            request["package_sha256"] == CAVERN_COAST_SHA256,
            f"{request['query_id']}: package changed",
        )
        expect(
            request["package_locator"].endswith("PL Cavern Coast.crp"),
            f"{request['query_id']}: package locator changed",
        )
        expect(
            request["max_length"] == 100000,
            f"{request['query_id']}: the request budget changed",
        )
    frozen_requests = [row["query_id"] for row in freeze["holdout"]]
    expect(
        sorted(frozen_requests) == sorted(holdout_ids),
        "the freeze and requests disagree",
    )
    return {
        "planned": EXPECTED_REQUESTS,
        "controls": EXPECTED_CONTROLS,
        "holdout": EXPECTED_HOLDOUT,
        "query_ids": requests["query_ids"],
    }


def check_selection(selection: dict, population: dict) -> dict:
    expect(
        selection["rule"] == "first_package_covering_six_strata",
        "selection rule changed",
    )
    expect(selection["max_packages"] == 3, "selection package cap changed")
    expect(sorted(selection["covered_cells"]) == sorted(CELLS), "covered cells changed")
    expect(selection["missing_cells"] == [], "a cell became missing")
    expect(len(selection["ordered_pool"]) == EXPECTED_POOL, "the ordered pool changed")
    expect(
        len(selection["selected"]) == EXPECTED_PACKAGES,
        "the selected package count changed",
    )
    selected = selection["selected"][0]
    expect(
        selected["file"] == "PL Cavern Coast.crp"
        and selected["sha256"] == CAVERN_COAST_SHA256,
        "the selected package changed",
    )
    expect(
        all(selection["covered_cells"].count(cell) == 1 for cell in CELLS),
        "a covered cell is not listed exactly once",
    )
    packages = population["packages"]
    expect(
        len(packages) == EXPECTED_POPULATION["packages"],
        "the installed package count changed",
    )
    eligible = [row for row in packages if row.get("cells")]
    expect(
        len(eligible) == EXPECTED_POPULATION["eligible"],
        "the eligible package count changed",
    )
    expect(
        sum(1 for row in eligible if row["file"] == "PL Cavern Coast.crp") == 1,
        "the selected package is not in the eligible pool",
    )
    excluded = population["excluded_hashes"]
    expect(
        len(excluded) == EXPECTED_POPULATION["excluded_hashes"],
        "the excluded hash set changed",
    )
    return {
        "rule": selection["rule"],
        "max_packages": selection["max_packages"],
        "covered_cells": selection["covered_cells"],
        "missing_cells": selection["missing_cells"],
        "pool": len(selection["ordered_pool"]),
        "selected": selected,
        "excluded_hashes": len(excluded),
    }


def check_exclusions(exclusions: dict) -> dict:
    expect(len(exclusions["table"]) == 26, "the exclusion table changed")
    expect(
        [row["file"] for row in exclusions["blank_co"]] == ["CO.crp"],
        "the blank control changed",
    )
    sources = exclusions["sources"]
    expect(
        sources["PL-1294_freeze"]["sha256"]
        == "717f6c0335f4558c77d2d23b4b1181a540f70ca21779365eeae6939c8c1ef3c8",
        "the prior freeze binding changed",
    )
    expect(
        sources["old_query_model_packages"]["sha256"]
        == OLD_QUERY_MODEL_PACKAGES_SHA256,
        "the old query-model package binding changed",
    )
    expect(
        sources["stock_freeze"]["commit"] == STOCK_EXCLUSION_COMMIT
        and sources["stock_freeze"]["sha256"] == PRIOR_STOCK_FREEZE_SHA256,
        "the stock exclusion source changed",
    )
    return {
        "rows": len(exclusions["table"]),
        "sources": sources,
        "rule": exclusions["rule"],
    }


def observation_windows(raw: dict[str, bytes]) -> list[dict]:
    windows = []
    for case in ("stock-1", "stock-2"):
        launch = json.loads(raw[f"drivers/{case}/driver-launch.json"])
        receipt = json.loads(raw[f"{case}/auditor-receipt.json"])
        expect(
            launch["case_id"] == case and receipt.get("role") == "auditor",
            f"{case}: retained raw context names another opening",
        )
        expect(
            launch["started_at"] < receipt["finished_at"],
            f"{case}: the observation window is inverted",
        )
        expect(
            receipt["collector"] == launch["roles"]["collector"]["pid"],
            f"{case}: the auditor did not observe the launched collector",
        )
        windows.append(
            {
                "case_id": case,
                "started_at": launch["started_at"],
                "finished_at": receipt["finished_at"],
                "source": [
                    f"raw/drivers/{case}/driver-launch.json",
                    f"raw/{case}/auditor-receipt.json",
                ],
            }
        )
    return windows


def derive(
    documents: dict[str, bytes],
    raw: dict[str, bytes],
    contract: list[str],
    linked_hashes: dict[str, str] | None = None,
) -> dict:
    module = check_module(documents, linked_hashes)
    freeze = check_freeze(json.loads(documents["freeze.json"]))
    requests = json.loads(documents["requests.json"])
    predictions = json.loads(documents["predictions.json"])
    selection = json.loads(documents["selection.json"])
    exclusions = json.loads(documents["exclusions.json"])
    inventory = json.loads(documents["inventory.json"])
    evaluation = json.loads(documents["evaluation.json"])
    bundle = json.loads(documents["bundle.json"])

    expect(
        sha(documents["predictions.json"]) == PREDICTIONS_SHA256,
        "predictions.json changed",
    )
    expect(sha(documents["requests.json"]) == REQUESTS_SHA256, "requests.json changed")
    expect(
        sha(documents["selection.json"]) == SELECTION_SHA256, "selection.json changed"
    )
    expect(
        sha(documents["exclusions.json"]) == EXCLUSIONS_SHA256,
        "exclusions.json changed",
    )
    expect(
        sha(documents["inventory.json"]) == INVENTORY_SHA256, "inventory.json changed"
    )
    expect(sha(documents["bundle.json"]) == BUNDLE_SHA256, "bundle.json changed")
    expect(sha(documents["freeze.json"]) == FROZEN_SHA256, "freeze.json changed")

    evaluated = check_evaluation(evaluation)
    checked_requests = check_requests(
        requests, predictions, json.loads(documents["freeze.json"])
    )
    population = {
        "packages": inventory,
        "excluded_hashes": sorted(exclusions["table"]),
    }
    checked_selection = check_selection(selection, population)
    checked_exclusions = check_exclusions(exclusions)

    # The versioned contract closure: every required file is present in the
    # frozen 82-file map with the same hash, and its digest is exactly the
    # recorded contract digest.
    expect(
        len(contract) == EXPECTED_CONTRACT_SOURCE_FILES,
        "the recorded contract closure changed size",
    )
    sources = json.loads(documents["freeze.json"])["source_files"]
    missing = [name for name in contract if name not in sources]
    expect(
        not missing, f"a required closure file is missing from the freeze: {missing}"
    )
    subset = {name: sources[name] for name in contract}
    expect(
        digest(subset) == CONTRACT_SOURCE_SHA256,
        "the required closure digest is not re-derivable",
    )
    extra = sorted(set(sources) - set(contract))
    expect(
        len(extra) == EXPECTED_FROZEN_SOURCE_FILES - EXPECTED_CONTRACT_SOURCE_FILES,
        "the non-contract source count changed",
    )

    readiness = evaluation["readiness"]
    expect(readiness["ready_for_measurement"] is False, "readiness now reports ready")
    expect(
        readiness["pre_export_qualification"] == "unknown",
        "pre-export qualification changed",
    )
    expect(
        readiness["contract_source_files"] == EXPECTED_CONTRACT_SOURCE_FILES
        and readiness["contract_source_sha256"] == CONTRACT_SOURCE_SHA256,
        "the readiness contract binding changed",
    )
    expect(
        readiness["study_source_files"] == EXPECTED_FROZEN_SOURCE_FILES
        and readiness["study_source_sha256"] == STUDY_SOURCE_SHA256,
        "the readiness study binding changed",
    )
    expect(
        readiness["bundle_sha256"] == BUNDLE_SHA256
        and readiness["assembler_sha256"] == ASSEMBLER_SHA256,
        "the refusal bundle binding changed",
    )
    expect(len(readiness["reasons"]) == 2, "the refusal reason count changed")
    expect(
        all(
            reason.endswith("runtime policy differs from freeze")
            for reason in readiness["reasons"]
        ),
        "the refusal reasons changed",
    )

    policy = bundle["policy"]
    expect(bundle.get("version") == 2, "the bundle version changed")
    expect(
        policy["source_sha256"] == STUDY_SOURCE_SHA256,
        "the runtime policy no longer records the 82-file digest",
    )
    expect(
        policy["source_sha256"] != CONTRACT_SOURCE_SHA256,
        "the runtime policy silently equals the contract closure",
    )
    expect(policy["dll_sha256"] == DLL["sha256"], "the bundle DLL hash changed")
    expect(
        len(policy["files"]) == 45
        and len(policy["plugins"]) == 7
        and len(policy["assemblies"]) == 23
        and len(policy["roots"]) == 11,
        "the bundle runtime inventory changed",
    )
    expect(
        policy["process_roles"]
        == ["game", "driver", "collector", "auditor", "monitor"],
        "the bundle process roles changed",
    )
    expect(len(bundle["observations"]) == 2, "the bundle observation count changed")
    for case, record in bundle["observations"].items():
        expect(
            record["opening_graph"] == record["post_graph"],
            f"{case}: the bundle graphs differ",
        )
        expect(
            record["cleanup"]
            and all(item["gone"] for item in record["cleanup"].values()),
            f"{case}: bundle cleanup is incomplete",
        )
        expect(len(record["paths"]) == 6, f"{case}: bundle path count changed")

    expect(
        set(raw) == set(RAW_CARRIED),
        "the carried raw context is not the five retained files",
    )
    for relative, original in raw.items():
        expect(
            evaluated["raw_files"].get(relative) == sha(original),
            f"{relative}: the carried raw bytes do not match the recorded 51-file hash",
        )
    windows = observation_windows(raw)
    owned = sum(len(case["cleanup"]) for case in evaluation["controls"])
    expect(owned == EXPECTED_OWNED_PROCESSES, "the owned process count changed")

    facts = {
        "module": module,
        "evaluation": evaluated,
        "freeze": freeze,
        "requests": checked_requests,
        "exclusions": checked_exclusions,
        "readiness": {
            "ready_for_measurement": readiness["ready_for_measurement"],
            "pre_export_qualification": readiness["pre_export_qualification"],
            "missing_native_fact": readiness["missing_native_fact"],
            "reasons": readiness["reasons"],
            "scope": readiness["scope"],
            "contract_source_files": readiness["contract_source_files"],
            "contract_source_sha256": readiness["contract_source_sha256"],
            "study_source_files": readiness["study_source_files"],
            "study_source_sha256": readiness["study_source_sha256"],
            "bundle_sha256": readiness["bundle_sha256"],
            "assembler_sha256": readiness["assembler_sha256"],
            "assembler_file": "assemble_v2.py",
        },
        "contract": {
            "files": contract,
            "sha256": CONTRACT_SOURCE_SHA256,
            "non_contract_files": len(extra),
        },
        "controls": {
            "openings": len(evaluation["controls"]),
            "inventories_per_opening": EXPECTED_INVENTORIES_PER_OPENING,
            "inventory": EXPECTED_INVENTORY,
            "requests": len(evaluated["rows"]),
            "successes": sum(
                1 for row in evaluated["rows"] if row["label"] == "success"
            ),
            "failures": sum(
                1 for row in evaluated["rows"] if row["label"] == "no_path"
            ),
            "pre_equals_effective": sum(
                1
                for row in evaluated["rows"]
                if row["pre_build_index"] == row["effective_build_index"]
            ),
            "all_complete": all(row["complete"] for row in evaluated["rows"]),
            "all_released": all(row["released"] for row in evaluated["rows"]),
            "graph_opening_equals_post": all(
                case["opening_graph_sha256"] == case["post_graph_sha256"]
                for case in evaluation["controls"]
            ),
            "owned_processes": owned,
            "owned_processes_gone": sum(
                1
                for case in evaluation["controls"]
                for record in case["cleanup"].values()
                if record["gone"]
            ),
            "rows": evaluated["rows"],
        },
        "selection": checked_selection,
        "raw": {
            "files": evaluated["raw_files"],
            "carried": RAW_CARRIED,
        },
        "windows": windows,
        "bundle": {
            "version": bundle["version"],
            "policy_source_sha256": policy["source_sha256"],
            "policy_dll_sha256": policy["dll_sha256"],
            "files": len(policy["files"]),
            "roots": len(policy["roots"]),
            "plugins": len(policy["plugins"]),
            "assemblies": len(policy["assemblies"]),
            "process_roles": policy["process_roles"],
        },
        "tests": EXPECTED_TESTS,
    }
    return facts


# --- assembling the projection and the strict manifest ----------------------


def file_role(relative: str) -> str:
    if relative in DOCUMENTS:
        return "document"
    if relative == "module.json":
        return "module"
    if relative == "evaluation.json":
        return "report"
    if relative == "freeze.json":
        return "frozen_plan"
    if relative == "bundle.json":
        return "readiness_bundle"
    if relative.endswith(".py"):
        return "test" if relative.startswith("test_") else "tool"
    if relative.endswith(".json"):
        return "provenance"
    return "evidence"


def _frozen(record: dict | None) -> dict | None:
    if record is None:
        return None
    return {
        "bytes": record["bytes"],
        "sha256": record["sha256"],
        "git_blob": record["git_blob"],
    }


def assemble(
    facts: dict,
    publication: dict[str, dict],
    frozen_map: dict[str, dict],
    raw_carried: dict[str, bytes],
    raw_originals: dict[str, bytes],
) -> tuple[dict, dict]:
    contract_block = {
        "publication_commit": PUBLICATION["publication_commit"],
        "publication_base": PUBLICATION["publication_base"],
        "frozen_commit": PUBLICATION["frozen_commit"],
        "internal_merge": PUBLICATION["internal_merge"],
        "pull_request": PUBLICATION["pull_request"],
        "branch": PUBLICATION["branch"],
        "target": PUBLICATION["target"],
        "source_issue": PUBLICATION["source_issue"],
        "review": {
            "pass": PUBLICATION["review_pass"],
            "acceptance": PUBLICATION["acceptance"],
        },
        "native_sources": {
            "outside_query_model": OUTSIDE_QUERY_MODEL_COMMIT,
            "stock_exclusion_source": STOCK_EXCLUSION_COMMIT,
        },
        "module": facts["module"],
    }

    study = {
        "study": STUDY,
        "kind": PUBLICATION["kind"],
        "title": PUBLICATION["title"],
        "evidence_only": True,
        "certificates": "none",
        "scope": SCOPE,
        "method": METHOD,
        "survives": SURVIVES,
        "stopped": STOPPED,
        "result": "unknown",
        "limits": LIMITS,
        "source": contract_block,
        "closure": {
            "prefix": PREFIX,
            "publication_files": EXPECTED_PUBLICATION_FILES,
            "copied_files": EXPECTED_CARRIED,
            "linked_files": EXPECTED_LINKED,
            "frozen_publication_files": EXPECTED_FROZEN_PUBLICATION_FILES,
            "post_control_files": sorted(POST_CONTROL),
            "frozen_changed_files": sorted(FROZEN_CHANGED),
            "module_members": EXPECTED_MODULE_MEMBERS,
        },
        "population": {
            "packages": EXPECTED_POPULATION["packages"],
            "eligible": EXPECTED_POPULATION["eligible"],
            "excluded_hashes": facts["selection"]["excluded_hashes"],
        },
        "selection": {
            "rule": facts["selection"]["rule"],
            "max_packages": facts["selection"]["max_packages"],
            "covered_cells": facts["selection"]["covered_cells"],
            "missing_cells": facts["selection"]["missing_cells"],
            "pool": facts["selection"]["pool"],
            "selected": [facts["selection"]["selected"]],
        },
        "requests": {
            "planned": facts["requests"]["planned"],
            "controls": facts["requests"]["controls"],
            "holdout": facts["requests"]["holdout"],
            "query_ids": facts["requests"]["query_ids"],
        },
        "holdout": {
            "planned": EXPECTED_HOLDOUT,
            "observed": 0,
            "unknown": EXPECTED_HOLDOUT,
            "accuracy": None,
            "precision": None,
            "recall": None,
            "records": facts["evaluation"]["holdout"],
        },
        "controls": {
            key: value for key, value in facts["controls"].items() if key != "rows"
        },
        "control_rows": facts["controls"]["rows"],
        "freeze": {
            "frozen_at": facts["freeze"]["frozen_at"],
            "git_commit_at_freeze": facts["freeze"]["git_commit_at_freeze"],
            "source_files": facts["freeze"]["source_files"],
            "source_sha256": facts["freeze"]["source_sha256"],
            "contract_source_files": facts["contract"]["files"],
            "contract_source_sha256": facts["contract"]["sha256"],
            "non_contract_source_files": facts["contract"]["non_contract_files"],
            "protocol": facts["freeze"]["protocol"],
            "stop_policy": facts["freeze"]["stop_policy"],
            "old_fact_count": facts["freeze"]["old_fact_count"],
            "old_publication_files": facts["freeze"]["old_publication_files"],
            "readiness_files": facts["freeze"]["readiness_files"],
            "dll": facts["freeze"]["dll"],
            "game_executable_sha256": facts["freeze"]["game_executable_sha256"],
            "compiler": facts["freeze"]["compiler"],
            "prior_sessions": facts["freeze"]["prior_sessions"],
        },
        "readiness": facts["readiness"],
        "runtime": {
            "openings": facts["controls"]["openings"],
            "phase_inventories": facts["controls"]["openings"]
            * facts["controls"]["inventories_per_opening"],
            "process_identities": facts["controls"]["owned_processes"],
            "sessions": [
                case["session_id"] for case in facts["evaluation"]["controls"]
            ],
        },
        "observation_windows": facts["windows"],
        "bundle": facts["bundle"],
        "verification": {
            "tests": facts["tests"],
            "check_study_verify": "original_producer_build_context_only",
            "fresh_clone_limit": "requires the untracked .build/Cs1Harness.dll and the original absolute staged-source path",
            "retained_byte_replay": True,
            "retained_byte_replay_scope": "51 raw hashes, the built DLL SHA-256 and MVID, and all ten owned PID/start chains, without rebuilding",
        },
        "exclusions": facts["exclusions"],
        "files": [],
        "linked": [],
        "raw_manifest": [],
        "raw": [],
    }

    for name in CARRIED:
        record = dict(publication[name])
        record["path"] = f"{PREFIX}/{name}"
        record["source"] = PUBLICATION["publication_base"]
        record["frozen"] = _frozen(frozen_map.get(name))
        study["files"].append(record)

    for name, role in LINKED.items():
        record = dict(publication[name])
        record["path"] = f"{PREFIX}/{name}"
        record["role"] = role
        record["source"] = PUBLICATION["publication_base"]
        record["frozen"] = _frozen(frozen_map.get(name))
        study["linked"].append(record)

    for relative, hashed in sorted(facts["raw"]["files"].items()):
        study["raw_manifest"].append({"path": relative, "sha256": hashed})

    for relative, role in sorted(RAW_CARRIED.items()):
        study["raw"].append(
            {
                "path": f"{RAW_PREFIX}/{relative}.gz",
                "role": role,
                "raw_path": relative,
                "raw_sha256": sha(raw_originals[relative]),
                "raw_bytes": len(raw_originals[relative]),
                "sha256": sha(raw_carried[relative]),
                "bytes": len(raw_carried[relative]),
            }
        )

    study["evidence_sha256"] = digest(
        [[item["path"], item["sha256"]] for item in study["files"]]
    )
    study["linked_sha256"] = digest(
        [[item["path"], item["sha256"]] for item in study["linked"]]
    )
    study["raw_manifest_sha256"] = digest(
        [[item["path"], item["sha256"]] for item in study["raw_manifest"]]
    )
    study["raw_evidence_sha256"] = digest(
        [[item["path"], item["sha256"], item["raw_sha256"]] for item in study["raw"]]
    )

    projection = {
        "schema": 1,
        "note": (
            "One accepted outside-readiness stopped-study publication as a typed evidence study, "
            "referenced from Road, Ship and Air. Its outcome is Unknown: both controls ran, then the "
            "byte-backed gate refused admission and no holdout request exists. It is not pooled with "
            "the outside-query, outside-stock, rail or native studies, not a qualification, promise or "
            "certificate, and no archived collector, evaluator, scorer or game runs as a product check."
        ),
        "source_manifest": {
            "schema": 1,
            "file": MANIFEST_FILE,
            "sha256": "",
            "commit": PUBLICATION["publication_commit"],
            "frozen_commit": PUBLICATION["frozen_commit"],
            "prefix": PREFIX,
            "publication_files": EXPECTED_PUBLICATION_FILES,
            "copied_files": EXPECTED_CARRIED,
            "linked_files": EXPECTED_LINKED,
            "raw_files": EXPECTED_RAW_FILES,
            "raw_copied_files": EXPECTED_RAW_CARRIED,
        },
        "studies": {STUDY: study},
    }

    manifest = {
        "schema": 1,
        "note": (
            "Strict file scope for the accepted outside-readiness-stock-v2 publication at its exact "
            "commit and its pre-control freeze commit. All 26 publication files are pinned by Git "
            "blob, byte length and SHA-256. `copied` names the 25 files carried in this repository "
            "byte for byte; `linked` names the one bulk frozen feature dump served as an immutable "
            "blob at the publication commit. The `raw` section pins all 51 retained raw file hashes "
            "and the five small files carried here gzip-compressed. Licensed game bytes and CRPs are "
            "named by hash only and are never copied."
        ),
        "publications": {
            STUDY: {
                "commit": PUBLICATION["publication_commit"],
                "base": PUBLICATION["publication_base"],
                "frozen_commit": PUBLICATION["frozen_commit"],
                "target": PUBLICATION["target"],
                "prefix": PREFIX,
                "module_version": EXPECTED_MODULE_VERSION,
                "module_members": sorted(MODULE_MEMBERS),
                "files": publication,
                "copied": sorted(CARRIED),
                "linked": sorted(LINKED),
                "post_control": sorted(POST_CONTROL),
                "frozen_changed": sorted(FROZEN_CHANGED),
                "publication_files": EXPECTED_PUBLICATION_FILES,
                "copied_files": EXPECTED_CARRIED,
                "linked_files": EXPECTED_LINKED,
                "frozen_publication_files": EXPECTED_FROZEN_PUBLICATION_FILES,
                "raw": {
                    "holding": "PL-1313-stock-v2/raw",
                    "files": facts["raw"]["files"],
                    "carried": [
                        {
                            "path": f"{RAW_PREFIX}/{relative}.gz",
                            "raw_path": relative,
                            "role": role,
                            "raw_sha256": sha(raw_originals[relative]),
                            "raw_bytes": len(raw_originals[relative]),
                            "sha256": sha(raw_carried[relative]),
                            "bytes": len(raw_carried[relative]),
                        }
                        for relative, role in sorted(RAW_CARRIED.items())
                    ],
                },
                "contract_source_files": facts["contract"]["files"],
                "contract_source_sha256": CONTRACT_SOURCE_SHA256,
                "study_source_files": EXPECTED_FROZEN_SOURCE_FILES,
                "study_source_sha256": STUDY_SOURCE_SHA256,
            }
        },
    }
    projection["source_manifest"]["sha256"] = sha(
        (json.dumps(manifest, indent=1) + "\n").encode()
    )
    return projection, manifest


def publication_manifest(
    files: dict[str, bytes], frozen: dict[str, bytes]
) -> dict[str, dict]:
    records = {}
    for name in sorted(CARRIED + tuple(LINKED)):
        raw = files[name]
        record = {
            "bytes": len(raw),
            "sha256": sha(raw),
            "git_blob": git_blob(raw),
            "role": file_role(name) if name not in LINKED else LINKED[name],
            "source": PUBLICATION["publication_base"],
        }
        if name in frozen:
            record["frozen"] = {
                "bytes": len(frozen[name]),
                "sha256": sha(frozen[name]),
                "git_blob": git_blob(frozen[name]),
            }
        else:
            record["frozen"] = None
        records[name] = record
    return records


def verify(
    projection: dict,
    facts: dict,
    carried: dict[str, bytes],
    raw_carried: dict[str, bytes],
) -> None:
    expect(projection["schema"] == 1, "projection header changed")
    expect(
        list(projection["studies"]) == [STUDY],
        "projection is not the one accepted publication",
    )
    study = projection["studies"][STUDY]
    expect(study["result"] == "unknown", "projection claims another outcome")
    expect(
        study["evidence_only"] is True and study["certificates"] == "none",
        "projection is not evidence only",
    )
    expect(
        study["holdout"]["observed"] == 0
        and study["holdout"]["unknown"] == EXPECTED_HOLDOUT,
        "projection claims an observed holdout",
    )
    expect(
        study["holdout"]["accuracy"] is None
        and study["holdout"]["precision"] is None
        and study["holdout"]["recall"] is None,
        "projection invents a holdout metric",
    )
    expect(
        study["requests"]["planned"] == EXPECTED_REQUESTS
        and len(study["requests"]["query_ids"]) == EXPECTED_REQUESTS,
        "projection request count changed",
    )
    expect(
        len(study["control_rows"]) == EXPECTED_CONTROLS,
        "projection control rows changed",
    )
    expect(
        study["controls"]["pre_equals_effective"] == EXPECTED_CONTROLS,
        "projection lost a build-index equality",
    )
    expect(
        study["controls"]["all_complete"] is True
        and study["controls"]["all_released"] is True,
        "projection control completion changed",
    )
    expect(
        study["controls"]["owned_processes"]
        == study["controls"]["owned_processes_gone"]
        == EXPECTED_OWNED_PROCESSES,
        "projection cleanup coverage changed",
    )
    expect(
        len(study["files"]) == EXPECTED_CARRIED
        and len(study["linked"]) == EXPECTED_LINKED,
        "projection file split changed",
    )
    expect(
        len(study["raw_manifest"]) == EXPECTED_RAW_FILES
        and len(study["raw"]) == EXPECTED_RAW_CARRIED,
        "projection raw split changed",
    )
    expect(
        len(study["freeze"]["contract_source_files"]) == EXPECTED_CONTRACT_SOURCE_FILES,
        "projection closure changed",
    )
    expect(
        study["freeze"]["source_files"] == EXPECTED_FROZEN_SOURCE_FILES,
        "projection study source count changed",
    )
    expect(
        study["freeze"]["source_sha256"] == STUDY_SOURCE_SHA256,
        "projection study digest changed",
    )
    expect(
        study["freeze"]["contract_source_sha256"] == CONTRACT_SOURCE_SHA256,
        "projection contract digest changed",
    )
    expect(
        study["bundle"]["policy_source_sha256"] == STUDY_SOURCE_SHA256,
        "projection runtime policy digest changed",
    )
    expect(
        study["bundle"]["policy_source_sha256"] != CONTRACT_SOURCE_SHA256,
        "projection runtime policy equals the contract closure",
    )
    expect(
        study["readiness"]["ready_for_measurement"] is False,
        "projection claims readiness",
    )
    expect(
        study["readiness"]["contract_source_files"] == EXPECTED_CONTRACT_SOURCE_FILES,
        "projection readiness closure changed",
    )
    expect(
        len(study["observation_windows"]) == 2, "projection observation windows changed"
    )
    expect(
        study["source"]["frozen_commit"] == PUBLICATION["frozen_commit"]
        and study["source"]["publication_commit"] == PUBLICATION["publication_commit"],
        "projection source identity changed",
    )
    expect(
        study["source"]["module"]["members"] == EXPECTED_MODULE_MEMBERS,
        "projection module members changed",
    )
    for record in study["files"]:
        raw = carried[record["path"].rsplit("/", 1)[-1]]
        expect(
            sha(raw) == record["sha256"] and len(raw) == record["bytes"],
            f"{record['path']}: carried bytes changed",
        )
    for record in study["raw"]:
        raw = raw_carried[record["raw_path"]]
        expect(
            sha(raw) == record["sha256"] and len(raw) == record["bytes"],
            f"{record['path']}: carried raw bytes changed",
        )
        original = gzip.decompress(raw)
        expect(
            sha(original) == record["raw_sha256"]
            and len(original) == record["raw_bytes"],
            f"{record['path']}: decompressed raw bytes changed",
        )


def summarise(study: dict, projection_sha: str, manifest_sha: str) -> dict:
    return {
        "kind": study["kind"],
        "study": study["study"],
        "source_commit": study["source"]["publication_commit"],
        "source_base": study["source"]["publication_base"],
        "frozen_commit": study["source"]["frozen_commit"],
        "internal_merge": study["source"]["internal_merge"],
        "source_issue": study["source"]["source_issue"],
        "pull_request": study["source"]["pull_request"],
        "publication_files": study["closure"]["publication_files"],
        "copied_files": study["closure"]["copied_files"],
        "linked_files": study["closure"]["linked_files"],
        "raw_files": len(study["raw_manifest"]),
        "raw_copied_files": len(study["raw"]),
        "module_version": study["source"]["module"]["version"],
        "module_members": study["source"]["module"]["members"],
        "projection_file": PROJECTION_FILE,
        "projection_sha256": projection_sha,
        "projection_tool_file": "tools/map-factory/integrate_outside_readiness.py",
        "source_manifest_file": MANIFEST_FILE,
        "source_manifest_sha256": manifest_sha,
        "result": study["result"],
        "holdout": {
            "planned": study["holdout"]["planned"],
            "observed": study["holdout"]["observed"],
            "unknown": study["holdout"]["unknown"],
        },
        "controls": {
            "openings": study["controls"]["openings"],
            "requests": study["controls"]["requests"],
            "successes": study["controls"]["successes"],
            "failures": study["controls"]["failures"],
            "pre_equals_effective": study["controls"]["pre_equals_effective"],
            "owned_processes_gone": study["controls"]["owned_processes_gone"],
            "inventories_per_opening": study["controls"]["inventories_per_opening"],
            "inventory_files": study["controls"]["inventory"]["files"],
        },
        "freeze": {
            "source_files": study["freeze"]["source_files"],
            "source_sha256": study["freeze"]["source_sha256"],
            "contract_source_files": len(study["freeze"]["contract_source_files"]),
            "contract_source_sha256": study["freeze"]["contract_source_sha256"],
            "git_commit_at_freeze": study["freeze"]["git_commit_at_freeze"],
            "old_fact_count": study["freeze"]["old_fact_count"],
            "old_publication_files": study["freeze"]["old_publication_files"],
            "readiness_files": study["freeze"]["readiness_files"],
        },
        "readiness": {
            "ready_for_measurement": study["readiness"]["ready_for_measurement"],
            "reasons": study["readiness"]["reasons"],
            "missing_native_fact": study["readiness"]["missing_native_fact"],
        },
        "selection": {
            "packages": len(study["selection"]["selected"]),
            "pool": study["selection"]["pool"],
            "covered_cells": len(study["selection"]["covered_cells"]),
            "missing_cells": len(study["selection"]["missing_cells"]),
            "file": study["selection"]["selected"][0]["file"],
        },
        "verification": {
            "tests": study["verification"]["tests"],
            "check_study_verify": study["verification"]["check_study_verify"],
            "fresh_clone_limit": study["verification"]["fresh_clone_limit"],
            "retained_byte_replay": study["verification"]["retained_byte_replay"],
        },
        "observation_windows": study["observation_windows"],
        "evidence_files_sha256": study["evidence_sha256"],
        "linked_files_sha256": study["linked_sha256"],
        "raw_manifest_sha256": study["raw_manifest_sha256"],
        "raw_evidence_sha256": study["raw_evidence_sha256"],
        "certificates": "none",
    }


def indent_block(value) -> str:
    text = json.dumps(value, indent=2)
    first, *rest = text.split("\n")
    return "\n".join([first, *("  " + line for line in rest)])


def capability_reference() -> str:
    return f'      "{LEDGER_KEY}": [\n        "{STUDY}"\n      ]'


def update_ledger(summary: dict) -> None:
    """Add this study's binding without rewriting unowned ledger bytes.

    The sibling outside-stock producer rewrites its own top-level object by
    replacing everything between its key and the outside-query key. This
    producer's object therefore sits after the outside-query object and before
    the closing brace, and its capability references sit after the sibling's
    references, so regenerating either producer preserves the other.
    """
    path = ROOT / LEDGER_FILE
    raw = path.read_text()
    stock_reference = (
        '      "outside_stock_studies": [\n        "outside-stock-budget-v1"\n      ]'
    )
    reference = capability_reference()
    if f"{stock_reference},\n{reference}" not in raw:
        expect(
            raw.count(stock_reference) == len(MODES),
            "the sibling outside-stock references moved",
        )
        raw = raw.replace(stock_reference, f"{stock_reference},\n{reference}")

    sibling = '\n  "outside_research_studies": '
    head = f'\n  "{LEDGER_KEY}": '
    block = indent_block(summary)
    closing = raw.rfind("\n}")
    expect(closing > 0, "the ledger has no closing brace")
    index = raw.find(head)
    if index >= 0:
        expect(index < closing, "this study's ledger object moved outside the ledger")
        raw = raw[:index] + head + block + raw[closing:]
    else:
        expect(
            raw.find(sibling) > 0, "the sibling outside-query ledger object is missing"
        )
        raw = raw[:closing] + "," + head + block + raw[closing:]
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
            entry.get("outside_stock_studies") == ["outside-stock-budget-v1"],
            f"{capability}: the sibling outside-stock reference was lost",
        )
    expect(
        ledger[LEDGER_KEY] == summary,
        "the written ledger summary differs from the projection",
    )
    expect(
        ledger["outside_stock_studies"]["study"] == "outside-stock-budget-v1",
        "the sibling outside-stock summary was lost",
    )
    expect(
        len(ledger["native_path_certificates"]) == 4,
        "the retained native certificate set changed",
    )


def ledger_summary(
    study: dict, projection_sha: str, manifest_sha: str, tool_sha: str
) -> dict:
    summary = summarise(study, projection_sha, manifest_sha)
    summary["projection_tool_sha256"] = tool_sha
    return summary


# --- raw carriage -----------------------------------------------------------


def raw_carried_bytes(raw: dict[str, bytes]) -> dict[str, bytes]:
    carried = {}
    for relative in RAW_CARRIED:
        expect(relative in raw, f"{relative}: the raw holding lost a retained file")
        carried[relative] = gzip.compress(raw[relative], mtime=0)
    return carried


def read_carried() -> dict[str, bytes]:
    files = {}
    for name in CARRIED:
        files[name] = (ROOT / PREFIX / name).read_bytes()
    return files


def read_frozen_carried() -> dict[str, bytes]:
    return {
        name: (ROOT / PREFIX / name).read_bytes()
        for name in CARRIED
        if name not in POST_CONTROL
    }


def rebuild() -> tuple[dict, dict, dict]:
    carried = read_carried()
    manifest_path = ROOT / MANIFEST_FILE
    expect(manifest_path.exists(), "the committed source manifest is missing")
    manifest = json.loads(manifest_path.read_bytes())
    publication = manifest["publications"][STUDY]
    frozen_map = {
        name: record["frozen"]
        for name, record in publication["files"].items()
        if record["frozen"]
    }
    raw_carried = {
        relative: (ROOT / RAW_PREFIX / f"{relative}.gz").read_bytes()
        for relative in RAW_CARRIED
    }
    raw_originals = {name: gzip.decompress(raw) for name, raw in raw_carried.items()}
    linked_hashes = {
        name: record["sha256"]
        for name, record in publication["files"].items()
        if name in LINKED
    }
    facts = derive(
        carried, raw_originals, publication["contract_source_files"], linked_hashes
    )
    projection, manifest = assemble(
        facts, publication["files"], frozen_map, raw_carried, raw_originals
    )
    verify(projection, facts, carried, raw_carried)
    return projection, manifest, facts


def main() -> int:
    args = sys.argv[1:]
    tool_sha = sha(Path(__file__).resolve().read_bytes())
    if "--source" in args:
        source = Path(args[args.index("--source") + 1]).resolve()
        expect("--raw" in args, "publication mode requires --raw <holding>")
        raw_dir = Path(args[args.index("--raw") + 1]).resolve()
        documents = publication_documents(source)
        frozen_at = frozen_documents(source)
        contract = closure_keys(source)
        raw = raw_manifest(raw_dir)
        evaluated = json.loads(documents["evaluation.json"])
        expect(
            sorted(raw) == sorted(evaluated["raw_files"]),
            "the raw holding does not match the recorded 51-file map",
        )
        for relative, original in raw.items():
            expect(
                sha(original) == evaluated["raw_files"][relative],
                f"{relative}: retained raw hash changed",
            )
        frozen_map = {
            name: {
                "sha256": sha(raw_bytes),
                "bytes": len(raw_bytes),
                "git_blob": git_blob(raw_bytes),
            }
            for name, raw_bytes in frozen_at.items()
        }
        publication = publication_manifest(documents, frozen_at)
        raw_originals = {name: raw[name] for name in RAW_CARRIED}
        raw_carried = raw_carried_bytes(raw)
        facts = derive(documents, raw_originals, contract)
        projection, manifest = assemble(
            facts, publication, frozen_map, raw_carried, raw_originals
        )
        verify(projection, facts, documents, raw_carried)
        manifest_raw = (json.dumps(manifest, indent=1) + "\n").encode()
        expect(
            projection["source_manifest"]["sha256"] == sha(manifest_raw),
            "projection does not bind the manifest it writes",
        )
        projection_raw = (json.dumps(projection, indent=1) + "\n").encode()
        (ROOT / MANIFEST_FILE).write_bytes(manifest_raw)
        (ROOT / PROJECTION_FILE).write_bytes(projection_raw)
        for name in CARRIED:
            (ROOT / PREFIX / name).write_bytes(documents[name])
        for name in RAW_CARRIED:
            target = ROOT / RAW_PREFIX / f"{name}.gz"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw_carried[name])
        study = projection["studies"][STUDY]
        update_ledger(
            ledger_summary(study, sha(projection_raw), sha(manifest_raw), tool_sha)
        )
        print(
            f"wrote {MANIFEST_FILE} ({len(manifest_raw)} bytes, {sha(manifest_raw)}), "
            f"{PROJECTION_FILE} ({len(projection_raw)} bytes, {sha(projection_raw)}) and the ledger binding"
        )
        print(
            json.dumps(
                summarise(study, sha(projection_raw), sha(manifest_raw)), indent=1
            )
        )
        return 0

    projection, manifest, facts = rebuild()
    projection_raw = (json.dumps(projection, indent=1) + "\n").encode()
    manifest_raw = (json.dumps(manifest, indent=1) + "\n").encode()
    committed_projection = (ROOT / PROJECTION_FILE).read_bytes()
    committed_manifest = (ROOT / MANIFEST_FILE).read_bytes()
    if "--check" in args:
        expect(
            committed_projection == projection_raw,
            "the committed outside-readiness projection is stale; re-run the importer",
        )
        expect(
            committed_manifest == manifest_raw,
            "the committed outside-readiness source manifest is stale; re-run the importer",
        )
        ledger = json.loads((ROOT / LEDGER_FILE).read_text())
        study = projection["studies"][STUDY]
        summary = ledger_summary(
            study, sha(committed_projection), sha(committed_manifest), tool_sha
        )
        expect(ledger[LEDGER_KEY] == summary, "the ledger binding is stale or unbound")
        print(
            f"outside-readiness projection is current: {sha(committed_projection)} (manifest {sha(committed_manifest)})"
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
