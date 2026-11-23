"""PL-1313 frozen unseen stock cohort, prepared before any new native request.

This module is the study-local preparation for the bounded corrected-control
stock study accepted in PL-1307.  It reuses the accepted pinned CRP reader and
the fixed eleven-package lane catalog unchanged, decodes the installed stock
inventory once, applies the frozen exclusions, selects at most three previously
unqueried packages covering the six package-mode/class strata, and freezes the
literal requests, input-only predictions, separate controls, protocol constants,
structural runtime expectations and stop policy.

Nothing here reads a new native outcome.  `prepare` only writes preparation
artifacts and `freeze.json`; `verify` recomputes them and checks that accepted
old publications are byte-identical.  The encoding is compact sorted JSON so a
declared digest is also the SHA-256 of the retained file.
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COLLECTOR_SOURCES = (
    "stock_v2.py",
    "schema_v3.py",
    "readiness_v3.py",
    "check_study.py",
    "build_v2.py",
    "collect_v2.py",
    "run_v2.py",
    "audit_v2.py",
    "bundle_v2.py",
    "evaluate_v2.py",
)
CAP = HERE.parent
MAP = CAP.parent
ROOT = MAP.parents[1]
OLD = CAP / "outside-stock-budget-v1"
QUERY = CAP / "outside-query-model-v1"
HARNESS = ROOT / "tools/cs1-harness"
sys.path[:0] = [str(OLD), str(CAP / "outside-readiness-v1")]

import study as old  # noqa: E402  (accepted unchanged source)

# The accepted study prepends tools/map-factory; put the accepted readiness
# module ahead of it so its own `evidence`/`schema`/`protocol` resolve.
sys.path.insert(0, str(CAP / "outside-readiness-v1"))

SOURCE = "86fee78d9517eff3c0e715813202b7b81b7e11d1"
TARGET = "PL-1142-native-v2"
STOCK_COMMIT = "914c153687106197e5f3a745d3ff7e181181ea8a"
STOCK_PATH = "tools/map-factory/capability-evidence/rail-stock-holdout-v1/freeze.json"
MAPS = old.MAPS
RULES = old.RULES
RULE = RULES[0]
MODES = old.MODES
MODE_ORDER = ["road", "ship", "air"]
CLASS_ORDER = ["success", "no_path"]
MAX_PACKAGES = 3
MAX_HOLDOUT_REQUESTS = 18
MAX_OPENINGS = 5
BUDGET = 100000
CONTROL_BUDGET = 100000
SEED = 857
STOP_POLICY = {
    "max_openings": MAX_OPENINGS,
    "max_control_openings": 2,
    "max_package_openings": MAX_PACKAGES,
    "max_path_requests": 30,
    "max_control_requests": 12,
    "max_holdout_requests": MAX_HOLDOUT_REQUESTS,
    "seconds_per_query": 30,
    "seconds_load": 600,
    "seconds_per_opening": 900,
    "seconds_total": 4500,
    "stop_on": [
        "failed_or_missing_control",
        "decoder_or_catalog_ambiguity",
        "missing_required_fact",
        "graph_or_context_drift",
        "source_request_prediction_or_schema_change",
        "plugin_assembly_or_pid_start_coverage_change",
        "unreleased_handle",
        "deadline_or_count_limit",
    ],
    "no_retry": True,
    "preserve_failed_opening_and_planned_requests": True,
}


def now():
    return datetime.datetime.now(datetime.UTC).isoformat()


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    return json.loads(raw)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))
    return sha(path)


def write_gzip(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(canonical(value), mtime=0))
    return sha(path)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def git_bytes(spec):
    return subprocess.check_output(["git", "show", spec], cwd=ROOT)


# --- frozen source closure -------------------------------------------------
# Code and fixed inputs only.  Generated preparation artifacts are bound by
# their own digests below so `freeze.json` never hashes itself.
SOURCE_GROUPS = {
    "reader": [
        MAP / "survey/measure_maps.py",
        MAP / "netcodec.py",
        MAP / "network_writer.py",
        MAP / "template.py",
        MAP / "crp.py",
    ],
    "model": [QUERY / p for p in ("model.py", "topology.py", "bridge.py")],
    "harness": sorted((HARNESS / "cs1_harness").glob("*.py"))
    + sorted((HARNESS / "mod").glob("*.cs")),
    "prior_study": [
        OLD / p
        for p in (
            "study.py",
            "prior-stock-catalogs.json",
            "build_study.py",
            "build.json",
        )
    ],
    "readiness_v1": [
        CAP / "outside-readiness-v1" / p
        for p in ("protocol.py", "readiness.py", "schema.py", "evidence.py")
    ],
    "stock_v2": [HERE / name for name in COLLECTOR_SOURCES],
}


def source_manifest():
    manifest = {}
    for group, paths in SOURCE_GROUPS.items():
        for path in paths:
            rel = str(Path(path).relative_to(ROOT))
            manifest[rel] = sha(path)
    return manifest


# --- exclusions ------------------------------------------------------------
def exclusion_sources():
    """Accepted inventories the frozen exclusion table is derived from."""
    stock_bytes = git_bytes(f"{STOCK_COMMIT}:{STOCK_PATH}")
    if hashlib.sha256(stock_bytes).hexdigest() != sha(OLD / "prior-stock-freeze.json"):
        raise ValueError("accepted stock control inventory binding differs")
    stock = json.loads(stock_bytes)
    geographic = read(QUERY / "packages.json")["packages"]
    old_freeze = read(OLD / "freeze.json")
    return stock, geographic, old_freeze


def exclusion_table():
    stock, geographic, old_freeze = exclusion_sources()
    table = {}

    def add(hashed, category, source):
        row = table.setdefault(hashed, {"categories": [], "sources": []})
        if category not in row["categories"]:
            row["categories"].append(category)
        if source not in row["sources"]:
            row["sources"].append(source)

    for slug, record in geographic.items():
        add(record["sha256"], "old_geographic_cohort", f"outside-query-model-v1/packages.json#{slug}")
    for record in stock["controls"]:
        add(record["sha256"], "PL-1239-control", f"{STOCK_PATH}#controls/{record['slug']}")
    for record in stock["selected"]:
        add(record["sha256"], "PL-1239-selected-including-metadata", f"{STOCK_PATH}#selected/{record['slug']}")
    for record in old_freeze["selected"]:
        add(
            record["sha256"],
            "PL-1294-selected-including-unsupported",
            f"outside-stock-budget-v1/freeze.json#selected/{record['case_id']}",
        )
    for row in table.values():
        row["categories"].sort()
        row["sources"].sort()
    return table


def blank_co():
    return [p for p in sorted(MAPS.glob("*.crp")) if p.name == "CO.crp"]


# --- inventory and decode --------------------------------------------------
def cell_counts(decoded):
    counts = {}
    for mode in MODE_ORDER:
        rows = decoded["modes"][mode]["candidates"]
        for label in CLASS_ORDER:
            counts[f"{mode}:{label}"] = sum(
                1
                for c in rows
                if c["endpoint_edges"][0] != c["endpoint_edges"][1]
                and c["rules"][RULE]["prediction"] == label
            )
    return counts


def inventory(catalog):
    """Sorted (sha256, path) installed inventory, decoded once when eligible."""
    table = exclusion_table()
    rows = []
    decoded = {}
    packages = {}
    seen = {}
    for path in sorted(MAPS.glob("*.crp")):
        hashed = sha(path)
        row = {
            "file": path.name,
            "locator": str(path),
            "sha256": hashed,
            "bytes": path.stat().st_size,
        }
        categories = []
        if path.name == "CO.crp":
            categories.append("blank_co")
        if hashed in table:
            categories.extend(table[hashed]["categories"])
        duplicate = seen.get(hashed)
        if duplicate is not None:
            categories.append("duplicate_hash")
        seen.setdefault(hashed, str(path))
        row["exclusion"] = sorted(set(categories)) or None
        if row["exclusion"]:
            row.update(
                supported=None,
                missing=None,
                cells=None,
                feature_sha256=None,
                duplicate_of=duplicate,
            )
        else:
            result, package = old.inventory_package(path, catalog)
            row["supported"] = bool(result["supported"]) and package is not None
            row["missing"] = result["missing"]
            row["cells"] = cell_counts(result) if row["supported"] else None
            row["duplicate_of"] = None
            row["feature_sha256"] = (
                digest(old.serial_features(package)) if row["supported"] else None
            )
            row["lineage"] = result.get("lineage")
            if row["supported"]:
                decoded[hashed] = result
                packages[hashed] = package
        rows.append(row)
    if not any(r["exclusion"] and "blank_co" in r["exclusion"] for r in rows):
        raise ValueError("blank CO package not found in installed inventory")
    rows.sort(key=lambda r: (r["sha256"], r["locator"]))
    return rows, decoded, packages


def eligible(rows):
    return [r for r in rows if not r["exclusion"] and r["supported"]]


def available_cells(row):
    return {
        (mode, label)
        for mode in MODE_ORDER
        for label in CLASS_ORDER
        if row["cells"][f"{mode}:{label}"]
    }


def select(rows):
    """First package covering six cells, else greedy first-addition up to three."""
    pool = sorted(eligible(rows), key=lambda r: (r["sha256"], r["locator"]))
    required = {(m, c) for m in MODE_ORDER for c in CLASS_ORDER}
    full = [r for r in pool if required <= available_cells(r)]
    if full:
        chosen = [full[0]]
        rule = "first_package_covering_six_strata"
    else:
        chosen = []
        covered = set()
        for row in pool:
            gained = available_cells(row) - covered
            if not gained:
                continue
            chosen.append(row)
            covered |= gained
            if len(chosen) >= MAX_PACKAGES:
                break
        rule = "greedy_first_package_adding_uncovered_stratum"
    covered = set()
    for row in chosen:
        covered |= available_cells(row)
    return {
        "ordered_pool": [
            {"sha256": r["sha256"], "locator": r["locator"], "cells": r["cells"]}
            for r in pool
        ],
        "selected": [
            {
                "sha256": r["sha256"],
                "locator": r["locator"],
                "file": r.get("file") or Path(r["locator"]).name,
            }
            for r in chosen
        ],
        "covered_cells": sorted(f"{m}:{c}" for m, c in covered),
        "missing_cells": sorted(f"{m}:{c}" for m, c in required - covered),
        "rule": rule,
        "max_packages": MAX_PACKAGES,
    }


def first_request(decoded_row, mode, label):
    for candidate in decoded_row["modes"][mode]["candidates"]:
        if candidate["endpoint_edges"][0] == candidate["endpoint_edges"][1]:
            continue
        if candidate["rules"][RULE]["prediction"] == label:
            return candidate
    raise KeyError(f"no distinct-edge {mode}:{label} candidate")


def holdout_requests(rows, selection, decoded):
    requests = []
    for index, chosen in enumerate(selection["selected"], 1):
        case_id = f"stock-v2-{index:02d}"
        row = next(r for r in rows if r["sha256"] == chosen["sha256"])
        for mode in MODE_ORDER:
            for label in CLASS_ORDER:
                if not row["cells"][f"{mode}:{label}"]:
                    continue
                candidate = first_request(decoded[row["sha256"]], mode, label)
                requests.append(
                    {
                        "query_id": f"{case_id}/{mode}/{label}",
                        "case_id": case_id,
                        "mode": mode,
                        "class": label,
                        "max_length": BUDGET,
                        "request": candidate["request"],
                        "endpoint_edges": candidate["endpoint_edges"],
                        "prediction": label,
                        "rule": RULE,
                        "package_sha256": row["sha256"],
                        "package_locator": row["locator"],
                    }
                )
        if sum(1 for r in requests if r["case_id"] == case_id) == 0:
            raise ValueError(f"selected package {case_id} produced no request")
    if len(requests) > MAX_HOLDOUT_REQUESTS:
        raise ValueError("holdout request cap exceeded")
    return requests


def controls():
    """Recompute the accepted fixed stock control plans, unchanged.

    The literal requests come from the retained accepted control inventories;
    the accepted PL-1294 freeze is used only as an equality check, never as a
    source of new labels.
    """
    accepted = read(OLD / "freeze.json")
    accepted_by_case = {c["case_id"]: c for c in accepted["controls"]}
    result = []
    for case in old.controls():
        if case["unavailable"]:
            raise ValueError(f"control inventory cannot supply all modes: {case['case_id']}")
        expected = accepted_by_case.get(case["case_id"])
        if expected is None:
            raise ValueError("control case absent from accepted freeze")
        plan = sorted(
            (
                {
                    "query_id": r["query_id"],
                    "mode": r["mode"],
                    "kind": r["kind"],
                    "max_length": r["max_length"],
                    "request": r["request"],
                }
                for r in case["requests"]
            ),
            key=lambda r: (r["mode"], r["kind"]),
        )
        if len(plan) != 6:
            raise ValueError("control plan is not six requests")
        if {(r["mode"], r["kind"]) for r in plan} != {
            (m, k) for m in MODE_ORDER for k in ("positive", "invalid-vehicle")
        }:
            raise ValueError("control plan does not cover every mode/kind")
        accepted = sorted(
            (
                {k: r[k] for k in ("query_id", "mode", "kind", "max_length", "request")}
                for r in expected["requests"]
            ),
            key=lambda r: (r["mode"], r["kind"]),
        )
        if canonical(plan) != canonical(accepted):
            raise ValueError("recomputed control requests differ from accepted freeze")
        result.append(
            {
                "case_id": case["case_id"],
                "locator": case["locator"],
                "sha256": case["sha256"],
                "inventory_source": "outside-stock-budget-v1/control-%s-networks.json.gz" % case["case_id"],
                "inventory_sha256": case["inventory_sha256"],
                "requests": plan,
                "predictions": {
                    r["query_id"]: ("success" if r["kind"] == "positive" else "no_path")
                    for r in plan
                },
            }
        )
    result.sort(key=lambda c: c["case_id"])
    return result


# --- old accepted fact immutability ---------------------------------------
OLD_PUBLICATION = CAP / "outside-stock-budget-v1"
READINESS_V1 = CAP / "outside-readiness-v1"


def old_facts():
    """The 84 accepted old facts, read from the accepted audit artifact.

    These are the retained labels of 48 holdout, 24 intervention and 12 control
    requests.  Reading them is not a replay of any scorer or predictor.
    """
    audit = read(OLD_PUBLICATION / "audit.json.gz")
    rows = audit["rows"]
    result = {}
    for row in rows:
        key = f"{row['kind']}:{row['plan']['query_id']}"
        if key in result:
            raise ValueError("duplicate old fact")
        result[key] = row["label"]
    if len(result) != 84:
        raise ValueError(f"expected 84 old facts, found {len(result)}")
    from collections import Counter

    counts = Counter(result.values())
    if counts.get("success", 0) + counts.get("no_path", 0) + counts.get("unknown", 0) != 84:
        raise ValueError("unsupported old fact label")
    return result


def prior_sessions():
    """Accepted PL-1294 opening identifiers; a new opening may not reuse one."""
    result = []
    for path in sorted((OLD / "raw").glob("*/observation.json.gz")):
        record = read(path)
        result.append(f"PL-1294/{record['case_id']}/{record['started_at']}")
    if not result:
        raise ValueError("no accepted prior opening identity")
    return sorted(set(result))


def old_publication_files():
    integrity = json.loads((OLD_PUBLICATION / "integrity.json").read_bytes())
    files = dict(integrity["files"])
    files["integrity.json"] = sha(OLD_PUBLICATION / "integrity.json")
    return files


def readiness_files():
    manifest = json.loads((READINESS_V1 / "module.json").read_bytes())
    files = dict(manifest["files"])
    files["module.json"] = sha(READINESS_V1 / "module.json")
    return files


# --- freeze and verification ----------------------------------------------
def protocol():
    return {
        "version": 2,
        "seed": SEED,
        "max_length": BUDGET,
        "entry": "NewGameFromMap",
        "invert_traffic": False,
    }


def expected_policy():
    """Structural requirements fixed before controls; no observed claim."""
    return {
        "executable_name": "Cities.x64",
        "root_suffixes": {
            "managed": "Cities_Data/Managed",
            "mono": "Cities_Data/Mono",
            "builtin_mods": "Files/Mods",
        },
        "user_mods_suffix": "Addons/Mods",
        "harness_plugin": "Cs1Harness",
        "harness_assembly": "Cs1Harness",
        "process_roles": ["game", "driver", "collector", "auditor", "monitor"],
        "protocol": protocol(),
        "lane_mask": {
            "road": ["Vehicle"],
            "ship": ["CargoVehicle", "TransportVehicle", "Vehicle"],
            "air": ["CargoVehicle", "TransportVehicle", "Vehicle"],
        },
        "vehicle": {"road": "Car", "ship": "Ship", "air": "Plane"},
        "category": {"road": "PassengerCar", "ship": "All", "air": "All"},
        "offsets": [0, 255],
        "launch_args": ["--noWorkshop"],
        "mods_enabled": True,
        "invert_traffic": "False",
        "required_plugin_roots": True,
        "required_assembly_fields": ["path", "sha256", "mvid"],
        "excluded_dynamic": ["Anonymously Hosted DynamicMethods Assembly"],
    }


def prepare():
    if (HERE / "freeze.json").exists():
        raise FileExistsError("freeze exists; never overwrite")
    if git("merge-base", SOURCE, "HEAD") != SOURCE:
        raise ValueError("branch does not descend from the pinned source")
    sources = source_manifest()
    catalog = old.fixed_catalog()
    rows, decoded, packages = inventory(catalog)
    selection = select(rows)
    holdout = holdout_requests(rows, selection, decoded)
    control_plans = controls()
    features = {
        hashed: old.serial_features(package) for hashed, package in packages.items()
    }
    facts = old_facts()
    table = exclusion_table()
    inventory_sha = write(HERE / "inventory.json", rows)
    exclusions_sha = write(
        HERE / "exclusions.json",
        {
            "table": table,
            "blank_co": [
                {"file": p.name, "locator": str(p), "sha256": sha(p)} for p in blank_co()
            ],
            "sources": {
                "stock_freeze": {
                    "commit": STOCK_COMMIT,
                    "path": STOCK_PATH,
                    "sha256": sha(OLD / "prior-stock-freeze.json"),
                },
                "old_query_model_packages": {
                    "path": "outside-query-model-v1/packages.json",
                    "sha256": sha(QUERY / "packages.json"),
                },
                "PL-1294_freeze": {
                    "path": "outside-stock-budget-v1/freeze.json",
                    "sha256": sha(OLD / "freeze.json"),
                },
            },
            "rule": "exclude by content hash: blank CO, old nine geographic, both accepted controls, all ten PL-1239 selected, every PL-1294 selection including unsupported, and duplicate hashes after the first path",
        },
    )
    features_sha = write_gzip(HERE / "features.json.gz", features)
    selection_sha = write(HERE / "selection.json", selection)
    requests_sha = write(
        HERE / "requests.json",
        {
            "controls": control_plans,
            "holdout": holdout,
            "query_ids": sorted(
                [r["query_id"] for c in control_plans for r in c["requests"]]
                + [r["query_id"] for r in holdout]
            ),
        },
    )
    predictions = {
        r["query_id"]: r["prediction"] for r in holdout
    }
    for control in control_plans:
        predictions.update(control["predictions"])
    predictions_sha = write(HERE / "predictions.json", predictions)
    import build_v2

    build = build_v2.build()
    freeze = {
        "schema": 2,
        "build": build,
        "issue": "PL-1313",
        "source": SOURCE,
        "target": TARGET,
        "frozen_at": now(),
        "canonical": "compact sorted JSON, UTF-8, no trailing newline",
        "git_commit_at_freeze": git("rev-parse", "HEAD"),
        "source_files": sources,
        "source_sha256": digest(sources),
        "catalog": {
            "path": "outside-stock-budget-v1/prior-stock-catalogs.json",
            "sha256": sha(OLD / "prior-stock-catalogs.json"),
        },
        "inventory": {
            "file_sha256": inventory_sha,
            "digest": digest(rows),
            "packages": len(rows),
            "eligible": len(eligible(rows)),
        },
        "exclusions": {"file_sha256": exclusions_sha, "digest": digest(table)},
        "features_sha256": features_sha,
        "selection": {"file_sha256": selection_sha, "digest": digest(selection)},
        "requests": {"file_sha256": requests_sha, "digest": digest(holdout)},
        "controls": control_plans,
        "holdout": holdout,
        "predictions": {"file_sha256": predictions_sha, "digest": digest(predictions)},
        "protocol": protocol(),
        "expected_policy": expected_policy(),
        "stop_policy": STOP_POLICY,
        "prior_sessions": prior_sessions(),
        "old_facts_sha256": digest(facts),
        "old_fact_count": len(facts),
        "old_publication_sha256": digest(old_publication_files()),
        "old_publication_files": len(old_publication_files()) + 1,
        "readiness_sha256": digest(readiness_files()),
        "readiness_files": len(readiness_files()),
        "issues": {
            "parent": "PL-1119",
            "accepted_readiness": "PL-1307",
            "prior_study": "PL-1294",
        },
    }
    write(HERE / "freeze.json", freeze)
    return freeze


def _built_binding(freeze):
    """Require the live study build to be the frozen build."""
    from cs1_harness.config import Config

    cfg = Config.for_host()
    frozen = freeze["build"]
    dll = cfg.build_dir / "Cs1Harness.dll"
    if sha(dll) != frozen["dll"]["sha256"]:
        raise ValueError("built DLL differs from the frozen build")
    stage = Path(frozen["source_stage"])
    actual = {p.name: sha(p) for p in sorted(stage.glob("*.cs"))}
    if actual != frozen["staged_sources"]:
        raise ValueError("staged study sources differ from the frozen build")
    return frozen


def preflight():
    """Pure verification against the committed freeze; no native contact."""
    freeze = read(HERE / "freeze.json")
    if freeze["source"] != SOURCE:
        raise ValueError("freeze source pin differs")
    if freeze["target"] != TARGET:
        raise ValueError("freeze target differs")
    if git("merge-base", SOURCE, "HEAD") != SOURCE:
        raise ValueError("wrong base")
    # The freeze must already be published in a commit, before any control.
    published = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{(HERE / 'freeze.json').relative_to(ROOT)}"],
        cwd=ROOT,
        capture_output=True,
    ).returncode == 0
    if not published:
        raise ValueError("freeze.json is not committed at pre-query HEAD")
    committed = git_bytes(f"HEAD:{(HERE / 'freeze.json').relative_to(ROOT)}")
    if committed != (HERE / "freeze.json").read_bytes():
        raise ValueError("committed freeze differs from working tree")
    sources = source_manifest()
    if sources != freeze["source_files"]:
        raise ValueError("source manifest changed after freeze")
    if digest(sources) != freeze["source_sha256"]:
        raise ValueError("source manifest digest differs")
    for name, hashed in sources.items():
        committed_blob = git_bytes(f"HEAD:{name}")
        if hashlib.sha256(committed_blob).hexdigest() != hashed:
            raise ValueError(f"source not committed as frozen: {name}")
    if sha(HERE / "inventory.json") != freeze["inventory"]["file_sha256"]:
        raise ValueError("inventory file changed")
    if sha(HERE / "exclusions.json") != freeze["exclusions"]["file_sha256"]:
        raise ValueError("exclusions file changed")
    if sha(HERE / "features.json.gz") != freeze["features_sha256"]:
        raise ValueError("features changed")
    if sha(HERE / "selection.json") != freeze["selection"]["file_sha256"]:
        raise ValueError("selection changed")
    if sha(HERE / "requests.json") != freeze["requests"]["file_sha256"]:
        raise ValueError("requests changed")
    if sha(HERE / "predictions.json") != freeze["predictions"]["file_sha256"]:
        raise ValueError("predictions changed")
    built = _built_binding(freeze)
    if read(HERE / "requests.json")["holdout"] != freeze["holdout"]:
        raise ValueError("holdout requests differ from frozen bytes")
    if read(HERE / "requests.json")["controls"] != freeze["controls"]:
        raise ValueError("control plans differ from frozen bytes")
    facts = old_facts()
    if digest(facts) != freeze["old_facts_sha256"] or len(facts) != 84:
        raise ValueError("accepted old facts changed")
    if digest(old_publication_files()) != freeze["old_publication_sha256"]:
        raise ValueError("old publication files changed")
    if digest(readiness_files()) != freeze["readiness_sha256"]:
        raise ValueError("accepted readiness files changed")
    if len(old_publication_files()) + 1 != freeze["old_publication_files"]:
        raise ValueError("old publication file count differs")
    if len(readiness_files()) + 1 != freeze["readiness_files"]:
        raise ValueError("readiness file count differs")
    if freeze["selection"]["digest"] != digest(read(HERE / "selection.json")):
        raise ValueError("selection digest differs")
    selection = read(HERE / "selection.json")
    return {
        "preflight": "pass",
        "build_dll": built["dll"]["sha256"],
        "build_mvid": built["dll"]["mvid"],
        "selected": [r["file"] for r in selection["selected"]],
        "covered_cells": selection["covered_cells"],
        "missing_cells": selection["missing_cells"],
        "holdout_requests": len(freeze["holdout"]),
        "control_requests": sum(len(c["requests"]) for c in freeze["controls"]),
        "old_facts": len(facts),
        "old_publication_files": len(old_publication_files()) + 1,
        "readiness_files": len(readiness_files()) + 1,
        "collection_ready": not freeze["selection"]["missing_cells"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "preflight", "plan"])
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
        print(json.dumps({"frozen": True, "freeze_sha256": sha(HERE / "freeze.json")}, sort_keys=True))
    elif args.command == "preflight":
        print(json.dumps(preflight(), sort_keys=True))
    else:
        print(json.dumps(read(HERE / "selection.json"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
