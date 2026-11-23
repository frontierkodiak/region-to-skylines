"""PL-1294 preparation from exact accepted inputs; never reads new outcomes."""

from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import itertools
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE.parent
MAP = CAP.parent
ROOT = MAP.parents[1]
OLD = CAP / "outside-query-model-v1"
HARNESS = ROOT / "tools/cs1-harness"
sys.path[:0] = [str(OLD), str(MAP), str(HARNESS)]
import bridge  # noqa: E402
import model  # noqa: E402
import topology  # noqa: E402
import netcodec  # noqa: E402
import network_writer  # noqa: E402
from survey import measure_maps  # noqa: E402

sys.path.insert(0, str(HERE))

SOURCE = "030db86ce470b972b6ef3462a2698744dff40ebb"
STOCK_SOURCE = "914c153687106197e5f3a745d3ff7e181181ea8a"
STOCK_PATH = "tools/map-factory/capability-evidence/rail-stock-holdout-v1/freeze.json"
MAPS = Path("/peach/Games/SteamLibrary/steamapps/common/Cities_Skylines/Files/Maps")
RULES = ["lane:any_lane:forbidden", "weak_component"]
MODES = {"road": "car", "ship": "ship", "air": "plane"}
BUDGETS = [100000, 200000, 1000000]
RUN = Path.home() / "experiments/PL-1294-stock-budget"


def configure():
    import os

    os.environ["CS1_HARNESS_CACHE"] = str(RUN / "cache")
    return RUN


PROTOCOL = {
    "api": "PathManager.CreatePath",
    "result_schema": [
        "id",
        "flags",
        "complete",
        "success",
        "length",
        "positions",
        "released",
    ],
    "effective_schema": [
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
    ],
    "query_freeze_schema": [
        "frozen_at",
        "requests",
        "freeze_sha256",
        "build_sha256",
        "opening_graph",
        "pre_query_commit",
        "networks_sha256",
    ],
    "seed": 857,
    "vehicle": topology.VEHICLE,
    "category": topology.CATEGORY_BY_MODE,
    "lane_types": {m: sorted(v) for m, v in topology.LANE_TYPES_BY_MODE.items()},
    "entry": "NewGameFromMap",
    "invert_traffic": False,
    "launch_args": ["--noWorkshop"],
    "mods_enabled": True,
    "offsets": [0, 255],
    "default_max_length": 100000,
    "intervention_max_length": BUDGETS,
    "control_requirement": "mode qualified only with stock positive and invalid-vehicle rejection; preserve missing or failed controls",
    "build_index": "current SimulationManager.m_currentBuildIndex; record actual per call",
    "other_arguments": "public overload defaults unchanged; no extra position or flags arguments",
    "rules": RULES,
    "model_max_length_chord_parameter": model.MAX_LENGTH,
    "unit_limit": "chord geometry and native cost/budget are not identified units",
    "labels": {
        "success": "complete=true, released=true, success=true; returned first/last exactly requested",
        "no_path": "complete=true, released=true, success=false; this literal request only",
        "unknown": "error, missing, incomplete, unreleased, or endpoint mismatch",
    },
    "query_selection": "first four of each primary class, fill lexical order to eight; reserve first reciprocal pair before class fill",
    "candidate_order": "distinct edge first, from/to lexicographic; allocation IDs are references/order only",
    "matching": "without replacement; nearest primary predicted successful directed chord sum; tie artifact/request hash",
}


def now():
    return datetime.datetime.now(datetime.UTC).isoformat()


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def read(path):
    path = Path(path)
    return json.loads(
        gzip.decompress(path.read_bytes())
        if path.suffix == ".gz"
        else path.read_bytes()
    )


def freeze_gzip(path, value):
    with Path(path).open("xb") as stream:
        stream.write(gzip.compress(encoded(value), mtime=0))
    return sha(path)


def freeze(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encoded(value))
    return sha(path)


def source_files():
    groups = {
        "reader": [
            MAP / p
            for p in [
                "survey/measure_maps.py",
                "netcodec.py",
                "network_writer.py",
                "template.py",
                "crp.py",
            ]
        ],
        "model": [OLD / p for p in ["model.py", "topology.py", "bridge.py"]],
        "harness": sorted((HARNESS / "cs1_harness").glob("*.py"))
        + sorted((HARNESS / "mod").glob("*.cs")),
        "study": sorted(HERE.glob("*.py")) + sorted(HERE.glob("*.cs")),
        "prior_stock_inputs": sorted(HERE.glob("prior-stock-*.json"))
        + sorted(HERE.glob("control-*-networks.json.gz")),
        "old_inputs": [
            OLD / p
            for p in [
                "catalogs.json",
                "requests.json",
                "packages.json",
                "inventory.json",
                "predictions.json",
                "bindings.json",
                "protocol.json",
            ]
        ],
    }
    return {
        g: {str(p.relative_to(ROOT)): sha(p) for p in paths}
        for g, paths in groups.items()
    }


def relevant_lane(lane):
    return bool(
        set(lane[2].split(", ")) & set(topology.VEHICLE.values())
        and set(lane[1].split(", ")) & topology.ACCEPTED_LANE_TYPES
    )


def native_package(networks):
    import copy

    networks = copy.deepcopy(networks)
    for segment in networks["segments"]:
        segment["lanes"] = [
            lane
            for lane in segment["lanes"]
            if relevant_lane(
                [lane["index"], lane["type"], lane["vehicle"], lane["category"], 0]
            )
        ]
    return topology.from_native(networks)


def fixed_catalog():
    c = read(HERE / "prior-stock-catalogs.json")["union"]
    # Exact fixed eleven-package catalog from accepted stock-rail source.
    for key in [
        "node_names",
        "segment_names",
        "node_name_conflicts",
        "segment_name_conflicts",
    ]:
        c[key] = {int(k): v for k, v in c[key].items()}
    directions = {0: "None", 1: "Forward", 2: "Backward", 3: "Both"}
    c["prefab_lanes"] = {
        name: (
            [
                tuple(lane[:4]) + (directions[lane[4]],)
                for lane in variants[0]["lanes"]
                if relevant_lane(lane)
            ]
            if len(variants) == 1
            and all(
                lane[4] in directions
                for lane in variants[0]["lanes"]
                if relevant_lane(lane)
            )
            else None
        )
        for name, variants in c["prefab_lanes"].items()
    }
    return c


def read_net(path):
    raw = Path(path).read_bytes()
    package, assets = measure_maps.read_any(raw)
    payloads = [a["payload"] for a in assets if a["kind"] == 52]
    if len(payloads) != 1:
        raise ValueError(f"expected one simulator asset, found {len(payloads)}")
    payload = payloads[0]
    version = measure_maps.data_version(payload)
    start = network_writer.section_start(payload, "NetManager")
    net = netcodec.NetSection(payload, start, version=version)
    return net, {
        "crp_format": package["format"],
        "data_version": version,
        "simulator_sha256": hashlib.sha256(payload).hexdigest(),
        "netmanager_offset": start,
        "nodes": len(net.nodes),
        "segments": len(net.segments),
    }


def build_package(path, catalog):
    net, lineage = read_net(path)
    built = bridge.bridge_package(net, catalog)
    built["missing"] = [
        m
        for m in built["missing"]
        if m.startswith("prefab:") or m.startswith("node_record:")
    ]
    built["segments"] = {
        sid: record
        for sid, record in built["segments"].items()
        if any(topology.mode_lanes(record, mode) for mode in MODES)
    }
    used_nodes = {
        node
        for record in built["segments"].values()
        for node in [record["start"], record["end"]]
    }
    built["nodes"] = {
        nid: record for nid, record in built["nodes"].items() if nid in used_nodes
    }
    # bridge's majority full-name catalog is not permission to guess a used bit.
    for kind, records, values, token in [
        ("node", built["nodes"], net.node_flags, "Outside"),
        ("segment", built["segments"], net.segment_flags, "Invert"),
    ]:
        for key, record in records.items():
            value = int(values[key - 1])
            names = catalog[kind + "_names"].get(value)
            options = catalog[kind + "_name_conflicts"].get(value)
            variants = (
                [s.replace(" + ", ", ").split(", ") for s in options]
                if options
                else [names]
            )
            facts = {token in v for v in variants if v is not None}
            if names is None or len(facts) != 1:
                built["missing"].append(f"{kind}_{token}:{value}")
            record["flags"] = {token} if facts == {True} else set()
    built["missing"] = sorted(set(built["missing"]))
    return built, lineage


def side(position):
    x, _, z = position
    return (
        ("east" if x > 0 else "west")
        if abs(x) > abs(z)
        else ("north" if z > 0 else "south")
    )


def candidates(package, mode):
    ends = []
    for sid, s in sorted(package["segments"].items()):
        for node, offset, pos in [(s["start"], 0, s["a"]), (s["end"], 255, s["b"])]:
            if "Outside" in package["nodes"][node]["flags"]:
                for lane in topology.mode_lanes(s, mode):
                    ends.append((sid, node, lane["index"], offset, side(pos)))
    rows = []
    prepared = model.Prepared(package, mode)
    for a, b in itertools.permutations(ends, 2):
        if a[0] == b[0] or a[1] == b[1]:
            continue
        request = {
            "capability": mode,
            "name": "outside-to-outside",
            "position_kind": "boundary",
            "from": [a[0], a[2], a[3]],
            "to": [b[0], b[2], b[3]],
        }
        rows.append(
            {
                "request": request,
                "endpoint_edges": [a[4], b[4]],
                "rules": {r: model.predict(prepared, request, r) for r in RULES},
            }
        )
    return sorted(
        rows,
        key=lambda r: (
            r["endpoint_edges"][0] == r["endpoint_edges"][1],
            r["request"]["from"],
            r["request"]["to"],
        ),
    )


def request_key(row):
    r = row["request"]
    return tuple(r["from"]), tuple(r["to"])


def select_queries(rows):
    selected = []

    def add(row):
        if row not in selected and len(selected) < 8:
            selected.append(row)

    # Reserve a literal reciprocal when available. It consumes the class quota.
    for row in rows:
        reverse = next(
            (r for r in rows if request_key(r) == request_key(row)[::-1]), None
        )
        if reverse is not None:
            add(row)
            add(reverse)
            break
    for label in ["success", "no_path"]:
        for row in rows:
            if sum(r["rules"][RULES[0]]["prediction"] == label for r in selected) >= 4:
                break
            if row["rules"][RULES[0]]["prediction"] == label:
                add(row)
    for row in rows:
        add(row)
    return selected, [r for r in rows if r not in selected]


def inventory_package(path, catalog):
    row = {
        "file": path.name,
        "locator": str(path),
        "sha256": sha(path),
        "bytes": path.stat().st_size,
    }
    try:
        package, lineage = build_package(path, catalog)
        row.update(
            lineage=lineage,
            missing=package["missing"],
            supported=not package["missing"],
        )
        if package["missing"]:
            row["modes"] = {
                m: {
                    "prediction": None,
                    "reason": "unresolved model inputs",
                    "candidates": [],
                }
                for m in MODES
            }
        else:
            row["feature_sha256"] = digest(serial_features(package))
            row["modes"] = {
                m: {
                    "prediction": None,
                    "reason": "no_mode_lane"
                    if not model.Prepared(package, m).segments
                    else None,
                    "candidates": candidates(package, m),
                }
                for m in MODES
            }
        return row, package
    except (ValueError, IndexError, KeyError, UnicodeDecodeError) as error:
        row.update(supported=False, missing=[f"{type(error).__name__}: {error}"])
        row["modes"] = {
            m: {"prediction": None, "reason": row["missing"][0], "candidates": []}
            for m in MODES
        }
        return row, None


def model_fields(package, mode):
    rows = []
    for sid, segment in sorted(package["segments"].items()):
        lanes = topology.mode_lanes(segment, mode)
        if not lanes:
            continue
        rows.append(
            {
                "id": int(sid),
                "start": segment["start"],
                "end": segment["end"],
                "a": list(segment["a"]),
                "b": list(segment["b"]),
                "invert": "Invert" in segment["flags"],
                "prefab": segment["prefab"],
                "outside": [
                    "Outside" in package["nodes"][node]["flags"]
                    for node in [segment["start"], segment["end"]]
                ],
                "lanes": [
                    {
                        "index": lane["index"],
                        "lane_type": lane["lane_type"],
                        "vehicle": sorted(lane["vehicle"]),
                        "category": lane["category"],
                        "forward": lane["forward"],
                        "backward": lane["backward"],
                    }
                    for lane in lanes
                ],
            }
        )
    return rows


def serial_features(package):
    return json.loads(json.dumps(package, default=lambda v: sorted(v)))


def intervention():
    inventory = read(OLD / "inventory.json")["queries"]
    predictions = {
        r["query_id"]: r for r in read(OLD / "predictions.json")["predictions"]
    }
    rows = []
    for row in inventory:
        if not row["eligible"] or row["mode"] != "road":
            continue
        p = predictions[row["query_id"]]["rules"][RULES[0]]
        if p["prediction"] != "success":
            continue
        rows.append(
            {
                "old_query_id": row["query_id"],
                "artifact_sha256": row["raw"]["artifact_sha256"],
                "canonical_request_sha256": digest(row["request"]),
                "request": row["request"],
                "old_label": row["label"],
                "geometric_length": p["detail"]["path_lower_bound_length"],
                "raw": row["raw"],
                "slug": row["slug"],
            }
        )

    def key(r):
        return (r["artifact_sha256"], r["canonical_request_sha256"], r["old_query_id"])

    # Deduplicate identical requests from repeated openings; labels stay immutable.
    unique = {}
    for row in sorted(rows, key=key):
        unique.setdefault(key(row)[:2], row)
    fps = sorted([r for r in unique.values() if r["old_label"] == "failure"], key=key)[
        :4
    ]
    successes = [r for r in unique.values() if r["old_label"] == "success"]
    selected = []
    for fp in fps:
        match = min(
            successes,
            key=lambda r: (
                abs(r["geometric_length"] - fp["geometric_length"]),
                *key(r),
            ),
        )
        successes.remove(match)
        selected.extend(
            [
                {**fp, "selection": "first_four_false_positive"},
                {
                    **match,
                    "selection": "matched_success",
                    "matched_to": fp["old_query_id"],
                },
            ]
        )
    if len(selected) != 8:
        raise ValueError("retained intervention cohort unavailable")
    return selected


def controls():
    result = []
    prior = read(HERE / "prior-stock-freeze.json")
    for case in prior["controls"]:
        slug = case["slug"]
        path = HERE / f"control-{slug}-networks.json.gz"
        package = native_package(read(path))
        requests = []
        unavailable = {}
        for mode in MODES:
            rows = candidates(package, mode)
            positives = [
                r for r in rows if r["rules"][RULES[0]]["prediction"] == "success"
            ]
            if not positives:
                unavailable[mode] = (
                    "no positive request derivable from retained stock inventory"
                )
                continue
            q = dict(positives[0]["request"])
            requests.append(
                {
                    "query_id": f"{slug}/{mode}/positive",
                    "mode": mode,
                    "request": q,
                    "max_length": 100000,
                    "kind": "positive",
                }
            )
            invalid = None
            for sid, segment in sorted(package["segments"].items()):
                for lane in segment["lanes"]:
                    if topology.VEHICLE[mode] not in lane["vehicle"] and lane[
                        "vehicle"
                    ] != ["None"]:
                        invalid = [sid, lane["index"], 128]
                        break
                if invalid:
                    break
            if invalid is None:
                unavailable[mode] = "invalid-vehicle endpoint unavailable"
            else:
                requests.append(
                    {
                        "query_id": f"{slug}/{mode}/invalid-vehicle",
                        "mode": mode,
                        "request": {**q, "to": invalid},
                        "max_length": 100000,
                        "kind": "invalid-vehicle",
                    }
                )
        result.append(
            {
                "case_id": slug,
                "locator": case["locator"],
                "sha256": case["sha256"],
                "requests": requests,
                "unavailable": unavailable,
                "inventory_source_commit": STOCK_SOURCE,
                "inventory_sha256": sha(path),
            }
        )
    return result


def prepare():
    if (HERE / "freeze.json").exists():
        raise FileExistsError("freeze exists; never overwrite")
    if (
        subprocess.check_output(
            ["git", "merge-base", SOURCE, "HEAD"], cwd=ROOT, text=True
        ).strip()
        != SOURCE
    ):
        raise ValueError("wrong base")
    stock_bytes = subprocess.check_output(
        ["git", "show", f"{STOCK_SOURCE}:{STOCK_PATH}"], cwd=ROOT
    )
    stock = json.loads(stock_bytes)
    for locator, expected in read(HERE / "prior-stock-catalogs.json")[
        "bindings"
    ].items():
        path = Path(locator) if locator.startswith("/") else ROOT / locator
        if not path.exists():
            raw = subprocess.check_output(
                ["git", "show", f"{STOCK_SOURCE}:{locator}"], cwd=ROOT
            )
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("prior catalog binding differs")
        elif sha(path) != expected:
            raise ValueError("prior catalog input changed")
    catalog = fixed_catalog()
    memberships = read(OLD / "requests.json")["openings"]
    membership = [e for e in memberships if e["networks"]["path"]]
    for e in membership:
        p = CAP / "outside-v1" / e["networks"]["path"]
        if (
            hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest()
            != e["networks"]["sha256"]
        ):
            raise ValueError("old catalog source changed")
    excluded = {
        v["sha256"]: ["old_geographic_cohort"]
        for v in read(OLD / "packages.json")["packages"].values()
    }
    for r in stock["controls"] + stock["selected"]:
        excluded.setdefault(r["sha256"], []).append(
            "PL-1239-controls"
            if r in stock["controls"]
            else "PL-1239-selected-including-metadata"
        )
    inventory, features = [], {}
    for path in sorted(MAPS.glob("*.crp")):
        if path.name == "CO.crp":
            row = {
                "file": path.name,
                "locator": str(path),
                "sha256": sha(path),
                "exclusion": ["blankCO"],
            }
        elif sha(path) in excluded:
            row = {
                "file": path.name,
                "locator": str(path),
                "sha256": sha(path),
                "exclusion": excluded[sha(path)],
            }
        else:
            row, package = inventory_package(path, catalog)
            row["exclusion"] = None
            if package is not None:
                features[row["sha256"]] = serial_features(package)
        inventory.append(row)
    selected = {}
    strata = []
    for mode in MODES:
        for label in ["success", "no_path"]:
            eligible = [
                r
                for r in inventory
                if not r["exclusion"]
                and r.get("supported")
                and any(
                    c["endpoint_edges"][0] != c["endpoint_edges"][1]
                    and c["rules"][RULES[0]]["prediction"] == label
                    for c in r["modes"][mode]["candidates"]
                )
            ]
            reason = f"{mode}:{label}:distinct_edge"
            strata.append(
                {
                    "stratum": reason,
                    "available": len(eligible),
                    "selected_sha256": eligible[0]["sha256"] if eligible else None,
                }
            )
            if eligible:
                row = eligible[0]
                selected.setdefault(row["sha256"], {**row, "selection_reasons": []})[
                    "selection_reasons"
                ].append(reason)
    unsupported = [
        r for r in inventory if not r["exclusion"] and not r.get("supported")
    ][:2]
    for row in unsupported:
        selected[row["sha256"]] = {
            **row,
            "selection_reasons": ["first_two_unsupported:metadata_only"],
        }
    for i, row in enumerate(selected.values(), 1):
        row["case_id"] = f"holdout-{i:02d}"
        for mode, entry in row["modes"].items():
            queries, unqueried = select_queries(entry["candidates"])
            entry["selected"], entry["unqueried"] = queries, unqueried
            for j, query in enumerate(queries, 1):
                query["query_id"] = f"{row['case_id']}/{mode}/{j:03d}"
    interventions = intervention()
    packages = read(OLD / "packages.json")["packages"]
    for row in interventions:
        row["locator"] = packages[row["slug"]]["locator"]
        if sha(row["locator"]) != row["artifact_sha256"]:
            raise ValueError("old intervention package missing/changed")
    artifacts = {
        r["slug"]: r for r in read(CAP / "outside-v1/evidence.json")["artifacts"]
    }
    lineage = {}
    for row in interventions:
        record = artifacts[row["slug"]]
        receipts = {}
        for key in ["cpu_evidence", "reproduction_evidence"]:
            ref = record[key]
            path = CAP / "outside-v1" / ref["path"]
            if (
                hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()
                != ref["sha256"]
            ):
                raise ValueError("old CPU receipt binding differs")
            receipts[key] = ref
        lineage[row["artifact_sha256"]] = {
            "old_exporter_source": record["exporter_source_sha"],
            "receipts": receipts,
            "scope": "exact old CRP/CPU lineage only; no fresh physical input rehash",
        }
    control_plan = controls()
    query_ids = [
        q["query_id"]
        for r in selected.values()
        for _, m in sorted(r["modes"].items())
        for q in m["selected"]
    ]
    query_ids += [r["query_id"] for c in control_plan for r in c["requests"]]
    query_ids += [
        f"intervention/{r['canonical_request_sha256']}/{budget}"
        for r in interventions
        for budget in BUDGETS
    ]
    if len(query_ids) != len(set(query_ids)):
        raise ValueError("duplicate planned query IDs")
    freeze_gzip(HERE / "features.json.gz", features)
    freeze(
        HERE / "catalog-membership.json",
        {
            "catalog_source_commit": STOCK_SOURCE,
            "catalog_source_path": STOCK_PATH.replace("freeze.json", "catalogs.json"),
            "catalog_sha256": sha(HERE / "prior-stock-catalogs.json"),
            "complete_bindings": read(HERE / "prior-stock-catalogs.json")["bindings"],
            "packages": read(CAP / "rail-query-model-v1/packages.json")["packages"],
            "note": "fixed accepted eleven-package union; nine geographic plus Asanu/Hanami, not the PL-1239 holdout inventories",
        },
    )
    freeze(HERE / "stock-exclusion-source.json", stock)
    freeze(
        HERE / "freeze.json",
        {
            "schema": 1,
            "issue": "PL-1294",
            "source": SOURCE,
            "frozen_at": now(),
            "build_sha256": sha(HERE / "build.json"),
            "preparation_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "protocol": PROTOCOL,
            "sources": source_files(),
            "catalog_membership_sha256": sha(HERE / "catalog-membership.json"),
            "features_sha256": sha(HERE / "features.json.gz"),
            "exclusion_source": {
                "commit": STOCK_SOURCE,
                "path": STOCK_PATH,
                "sha256": hashlib.sha256(stock_bytes).hexdigest(),
                "retained_sha256": sha(HERE / "stock-exclusion-source.json"),
            },
            "old_package_lineage": lineage,
            "request_sha256": digest(
                [
                    q["request"]
                    for r in selected.values()
                    for _, m in sorted(r["modes"].items())
                    for q in m["selected"]
                ]
            ),
            "predictions_sha256": digest(
                [
                    q["rules"]
                    for r in selected.values()
                    for _, m in sorted(r["modes"].items())
                    for q in m["selected"]
                ]
            ),
            "intervention_sha256": digest(interventions),
            "excluded_hashes": excluded,
            "inventory": inventory,
            "selection_strata": strata,
            "selected": list(selected.values()),
            "intervention": interventions,
            "controls": control_plan,
            "query_ids": sorted(query_ids),
            "collection_ready": True,
        },
    )


def check():
    frozen = read(HERE / "freeze.json")
    if (
        frozen["source"] != SOURCE
        or frozen["sources"] != source_files()
        or frozen["protocol"] != PROTOCOL
    ):
        raise ValueError("source key set, bytes, or protocol changed")
    for key, name in [
        ("catalog_membership_sha256", "catalog-membership.json"),
        ("features_sha256", "features.json.gz"),
    ]:
        if frozen[key] != sha(HERE / name):
            raise ValueError("frozen artifact changed")
    ids = [
        q["query_id"]
        for r in frozen["selected"]
        for _, m in sorted(r["modes"].items())
        for q in m["selected"]
    ]
    if len(ids) != len(set(ids)) or len(frozen["selected"]) > 8:
        raise ValueError("duplicate query IDs or too many packages")
    build = read(HERE / "build.json")
    if frozen["build_sha256"] != sha(HERE / "build.json") or build[
        "generator_sha256"
    ] != sha(HERE / "build_study.py"):
        raise ValueError("build source/receipt changed")
    if frozen["exclusion_source"]["retained_sha256"] != sha(
        HERE / "stock-exclusion-source.json"
    ):
        raise ValueError("exclusions changed")
    if digest(frozen["intervention"]) != frozen["intervention_sha256"]:
        raise ValueError("intervention changed")
    if (
        digest(
            [
                q["request"]
                for r in frozen["selected"]
                for _, m in sorted(r["modes"].items())
                for q in m["selected"]
            ]
        )
        != frozen["request_sha256"]
        or digest(
            [
                q["rules"]
                for r in frozen["selected"]
                for _, m in sorted(r["modes"].items())
                for q in m["selected"]
            ]
        )
        != frozen["predictions_sha256"]
    ):
        raise ValueError("request/prediction hashes differ")
    expected_ids = sorted(
        ids
        + [q["query_id"] for c in frozen["controls"] for q in c["requests"]]
        + [
            f"intervention/{r['canonical_request_sha256']}/{budget}"
            for r in frozen["intervention"]
            for budget in BUDGETS
        ]
    )
    if expected_ids != frozen["query_ids"] or len(expected_ids) != len(
        set(expected_ids)
    ):
        raise ValueError("complete query ID set differs")
    controls_now = controls()
    if controls_now != frozen["controls"]:
        raise ValueError("control plan changed")
    expected_inventory = [(p.name, sha(p)) for p in sorted(MAPS.glob("*.crp"))]
    if expected_inventory != [(r["file"], r["sha256"]) for r in frozen["inventory"]]:
        raise ValueError("installed package inventory changed")
    for row in frozen["selected"]:
        if sha(row["locator"]) != row["sha256"]:
            raise ValueError("selected package changed")
    for row in frozen["intervention"]:
        if sha(row["locator"]) != row["artifact_sha256"]:
            raise ValueError("intervention package changed")
    print(
        json.dumps(
            {
                "verified": True,
                "collection_ready": frozen["collection_ready"],
                "queries": len(ids),
                "selected": [
                    (r["case_id"], r["file"], r["supported"])
                    for r in frozen["selected"]
                ],
                "strata": frozen["selection_strata"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "check"])
    args = parser.parse_args()
    {"prepare": prepare, "check": check}[args.command]()
