"""Prospective stock holdout. Freeze uses CRPs and the OLD catalog only."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
CAP = HERE.parent
MAP = HERE.parents[1]
ROOT = HERE.parents[3]
FIT = CAP / "rail-junction-fit-v1"
OLD = CAP / "rail-query-model-v1"
HARNESS = ROOT / "tools/cs1-harness"
sys.path[:0] = [str(FIT), str(OLD), str(MAP), str(HARNESS)]

import export_topology as exports  # noqa: E402
import junction_model as jm  # noqa: E402
import model  # noqa: E402
import topology  # noqa: E402

# The retained modules adjust sys.path for their own imports. Restore this
# study's entrypoint directory so names such as evaluate cannot select an old
# scorer when this module is imported by tests or another entrypoint.
sys.path.insert(0, str(HERE))

SOURCE = "49cf49516f4aa8b24a154d9923c1a6fd149bf1a3"
QUERY_SOURCE = "364628b81701c134e3f469f9e175c4fe40f7a311"
NATIVE_SOURCE = "1a0e45c65745ba5f05cf22f947da2e88fed25277"
RULES = ["tangent:continuation:any_lane", "chord:continuation:any_lane"]
STRATA = ["pair_difference", "no_pair_difference", "unsupported_or_no_pair"]
PROTOCOL = {
    "id": "PL-1239-stock-holdout-v1",
    "mode": "train",
    "vehicle": "Train",
    "category": "All",
    "lane_types": ["Vehicle", "TransportVehicle", "CargoVehicle"],
    "forward": 1,
    "backward": 2,
    "segment_invert": True,
    "offsets": [0, 255],
    "seed": 857,
    "max_length": 100000,
    "launch": "NewGameFromMap/noWorkshop/non-inverted/mods-enabled",
    "limit": 64,
    "rules": RULES,
    "selection": "first4 per disjoint stratum, filename order; no replacement",
    "query_order": "distinct edge first, from/to lexicographic; add first available reciprocal segment-pair immediately, then continue; at most64",
    "unsupported": "any unresolved export/catalog field => package prediction abstains; no native-derived replacement requests",
    "labels": {
        "success": "complete and released, success=true, exact literal returned endpoints",
        "no_path": "complete and released, success=false; this request only",
        "unknown": "missing, incomplete, unreleased, refused, error or endpoint mismatch",
    },
    "scoring": ["all-complete intent-to-test", "snapshot-matched"],
    "snapshot_matched": "opening/post model fields and native tangent table match CRP; query pre/post rail metadata digest matches opening",
    "field_comparison": "exact parsed JSON numbers/lists after tuple-to-list normalization; no rounding or null imputation",
    "path_diagnostic": "every completed successful native path: report distinct-segment transitions absent from every frozen rule resolution, even when an alternative predicted path makes the request label correct",
    "file_inventory": "fresh executable plus every file in Managed, Mono, builtin/local mod trees and reported plugin directories at launch, opening and post-batch; loaded assembly hashes/MVIDs/dynamic exclusions retained separately; not memory attestation or strict no-mods",
    "controls": "unchanged Asanu/Hanami packages, old boundary+midpoint/reverse/invalid-car plans; both complete/context-bound, at least one literal boundary success, each invalid-car fails; no tuning or retry after failure",
    "scope": "direct stock CRP-bound request evidence; no prepared-input/CPU lineage, activation, geographic prevalence, service or generic junction law",
    "pittsburgh": "not replayed in this study; optional fixed mechanism diagnostic remains separate",
}


def now():
    return datetime.datetime.now(datetime.UTC).isoformat()


def encoded(value):
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def read(path):
    return exports.load_json(path)


def freeze(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    return sha(path)


def source_files():
    """Closed inner key sets: include actual reader and all harness sources."""
    groups = {
        "reader": [
            MAP / p
            for p in [
                "survey/measure_maps.py",
                "netcodec.py",
                "network_writer.py",
                "template.py",
            ]
        ],
        "model": [OLD / p for p in ["bridge.py", "model.py", "topology.py"]]
        + [FIT / p for p in ["export_topology.py", "junction_model.py"]],
        "harness": sorted((HARNESS / "cs1_harness").glob("*.py"))
        + sorted((HARNESS / "mod").glob("*.cs")),
        "study": [
            HERE / p
            for p in [
                "study.py",
                "collect.py",
                "build_metadata.py",
                "RailMetadata.cs",
                "evaluate.py",
                "run_one.py",
            ]
        ],
        "old_inputs": [OLD / p for p in ["openings.json", "packages.json"]],
    }
    return {
        group: {str(p.relative_to(ROOT)): sha(p) for p in paths}
        for group, paths in groups.items()
    }


def old_catalogs():
    """No new native snapshot can enter this catalog union."""
    packages = read(OLD / "packages.json")
    entries = read(OLD / "openings.json")["openings"]
    if len(entries) != 11 or len({e["package"] for e in entries}) != 11:
        raise ValueError("old 11-package union changed")
    bindings = {}
    for name, row in packages["packages"].items():
        if sha(row["locator"]) != row["sha256"]:
            raise ValueError(f"old package changed: {name}")
        bindings[row["locator"]] = row["sha256"]
    for e in entries:
        path = CAP / e["raw"] / "networks.json.gz"
        bindings[str(path.relative_to(ROOT))] = sha(path)
    catalogs = exports.catalogs_for(entries, packages)
    serial = {
        "prefab_lanes": {
            name: [
                {"lanes": template, "count": count}
                for template, count in sorted(templates.items())
            ]
            for name, templates in sorted(catalogs["prefab_lanes"].items())
        },
        "node_names": catalogs["node_names"],
        "segment_names": catalogs["segment_names"],
        "node_name_conflicts": catalogs["node_name_conflicts"],
        "segment_name_conflicts": catalogs["segment_name_conflicts"],
        "outside_values": sorted(catalogs["outside_values"]),
    }
    return catalogs, serial, bindings


def boundary_side(position):
    x, _, z = position
    return (
        ("east" if x > 0 else "west")
        if abs(x) > abs(z)
        else ("north" if z > 0 else "south")
    )


def candidates(package):
    ends = []
    for sid, s in sorted(package["segments"].items()):
        for node, offset, position in [
            (s["start"], 0, s["a"]),
            (s["end"], 255, s["b"]),
        ]:
            if "Outside" in package["nodes"][node]["flags"]:
                ends.append((sid, node, offset, boundary_side(position)))
    rows = []
    for a, b in itertools.permutations(ends, 2):
        if a[0] == b[0] or a[1] == b[1]:
            continue
        sa, sb = package["segments"][a[0]], package["segments"][b[0]]
        for la, lb in itertools.product(
            topology.train_lanes(sa), topology.train_lanes(sb)
        ):
            if model.can_travel(sa, la, a[1]) and model.can_travel(
                sb, lb, model.other_node(sb, b[1])
            ):
                rows.append(
                    {
                        "capability": "rail",
                        "name": "directed-outside-to-outside",
                        "position_kind": "boundary",
                        "diagnostic": False,
                        "endpoint_edges": [a[3], b[3]],
                        "from": [a[0], la["index"], a[2]],
                        "to": [b[0], lb["index"], b[2]],
                    }
                )
    return sorted(
        rows,
        key=lambda r: (
            r["endpoint_edges"][0] == r["endpoint_edges"][1],
            r["from"],
            r["to"],
        ),
    )


def request_key(row):
    return tuple(row["from"]), tuple(row["to"])


def select_queries(rows, limit=64):
    selected, seen = [], set()
    for row in rows:
        if len(selected) >= limit:
            break
        if request_key(row) in seen:
            continue
        selected.append(row)
        seen.add(request_key(row))
        reciprocal = next(
            (
                r
                for r in rows
                if r["from"][0] == row["to"][0]
                and r["to"][0] == row["from"][0]
                and r["from"][2] == row["to"][2]
                and r["to"][2] == row["from"][2]
                and request_key(r) not in seen
            ),
            None,
        )
        if reciprocal is not None and len(selected) < limit:
            selected.append(reciprocal)
            seen.add(request_key(reciprocal))
    if len(seen) != len(selected):
        raise ValueError("duplicate selected query")
    return selected, [r for r in rows if request_key(r) not in seen]


def build_package(path, catalogs):
    container = exports.read_net(path)
    package = exports.exported_package(container["net"], catalogs)
    nodes, segments = exports.crp_records(container["net"])
    missing = []
    # An unclassified prefab might carry Train lanes. Known non-Train records
    # cannot affect this model; do not demand their unrelated flags.
    for sid, record in segments.items():
        template = exports.accepted_bridge.single_template(
            catalogs["prefab_lanes"], record["prefab"]
        )
        if template is None:
            missing.append(f"prefab:{record['prefab']}")
        elif (
            topology.train_lanes(
                {"lanes": exports.accepted_bridge.decode_lanes(template)}
            )
            and sid not in package["segments"]
        ):
            missing.append(f"train_segment_not_built:{sid}")
    train = {
        sid: s for sid, s in package["segments"].items() if topology.train_lanes(s)
    }
    used_nodes = {node for s in train.values() for node in [s["start"], s["end"]]}
    flag_facts = {"invert": {}, "outside": {}}
    for sid, s in train.items():
        flags = model_flag(catalogs, "segment", segments[sid]["flags"], "Invert")
        flag_facts["invert"][sid] = flags
        if flags is None:
            missing.append(f"segment_invert:{sid}:{segments[sid]['flags']}")
        s["flags"] = {"Invert"} if flags else set()
    for nid in used_nodes:
        outside = model_flag(catalogs, "node", nodes[nid]["flags"], "Outside")
        flag_facts["outside"][nid] = outside
        if outside is None:
            missing.append(f"node_outside:{nid}:{nodes[nid]['flags']}")
        package["nodes"][nid]["flags"] = {"Outside"} if outside else set()
    # Preserve raw integer flags and ambiguity separately; only the two
    # consensus model facts above can feed a prediction.
    package["raw_flag_records"] = {"nodes": nodes, "segments": segments}
    package["segments"] = train
    package["nodes"] = {nid: package["nodes"][nid] for nid in used_nodes}
    package["missing"] = sorted(set(missing))
    package["flag_facts"] = flag_facts
    # Nulls in old-format records stay null; only the two directions feed rules.
    table = {}
    for sid, record in container["net"].segments.items():
        table[int(sid)] = {
            k: record.get(k)
            for k in [
                "start_direction",
                "end_direction",
                "override_direction_limit",
                "start_node",
                "end_node",
            ]
        }
    package = exports.attach(package, table)
    for sid, s in package["segments"].items():
        if topology.train_lanes(s):
            for key in ["start_direction", "end_direction"]:
                value = s.get(key)
                if (
                    value is None
                    or len(value) != 3
                    or not all(math.isfinite(float(v)) for v in value)
                    or math.hypot(value[0], value[2]) == 0
                ):
                    package["missing"].append(f"tangent:{sid}:{key}")
    return container, package


def model_flag(catalogs, kind, value, token):
    names = catalogs[kind + "_names"].get(value)
    if names is None:
        return None
    conflicts = catalogs[kind + "_name_conflicts"].get(value)
    options = list(conflicts) if conflicts else [", ".join(names)]
    facts = {token in option.split(", ") for option in options}
    return next(iter(facts)) if len(facts) == 1 else None


def inventory_package(path, catalogs):
    row = {
        "file": path.name,
        "locator": str(path),
        "sha256": sha(path),
        "bytes": path.stat().st_size,
    }
    try:
        container, package = build_package(path, catalogs)
        row["lineage"] = container["lineage"]
        row["missing"] = package["missing"]
        row["model_input_digest"] = (
            exports.accepted_bridge.model_input_digest(package)
            if not package["missing"]
            else None
        )
        row["tangents_sha256"] = digest(
            {
                str(sid): {
                    key: s.get(key) for key in ["start_direction", "end_direction"]
                }
                for sid, s in sorted(package["segments"].items())
            }
        )
        if package["missing"]:
            row.update(
                supported=False,
                pair_difference=None,
                candidate_count=None,
                distinct_edge=None,
            )
            return row
        engine = jm.Engine(package)
        differences = []
        for node, sids in sorted(engine.incident.items()):
            if len(sids) < 3:
                continue
            values = [
                jm._continuation_matchings(
                    package, node, list(dict.fromkeys(sids)), measure
                )
                for measure in ["chord", "tangent"]
            ]
            if values[0] != values[1]:
                differences.append(node)
        rows = candidates(package)
        row.update(
            supported=True,
            pair_difference=bool(differences),
            differing_nodes=differences,
            candidate_count=len(rows),
            distinct_edge=any(
                r["endpoint_edges"][0] != r["endpoint_edges"][1] for r in rows
            ),
        )
    except Exception as error:
        row.update(
            supported=False,
            pair_difference=None,
            candidate_count=None,
            distinct_edge=None,
            error=f"{type(error).__name__}: {error}",
        )
    return row


def stratum(row):
    if not row["supported"] or not row["distinct_edge"]:
        return STRATA[2]
    return STRATA[0] if row["pair_difference"] else STRATA[1]


def preserve(row, package_store):
    if package_store is None:
        return
    package_store.mkdir(parents=True, exist_ok=True)
    target = package_store / row.get("file", Path(row["locator"]).name)
    if not target.exists():
        shutil.copyfile(row["locator"], target)
    if sha(target) != row["sha256"]:
        raise ValueError("preserved package differs")
    row["preserved_locator"] = str(target)


def prepare(maps, output, package_store=None):
    catalogs, serial, bindings = old_catalogs()
    freeze(output / "catalogs.json", {"bindings": bindings, "union": serial})
    excluded_hashes = {
        r["sha256"] for r in read(OLD / "packages.json")["packages"].values()
    }
    inventory = []
    for path in sorted(maps.glob("*.crp"), key=lambda p: p.name):
        h = sha(path)
        exclusion = (
            "blank_CO"
            if path.name == "CO.crp"
            else "previous_rail_package_hash"
            if h in excluded_hashes
            else None
        )
        if exclusion:
            row = {
                "file": path.name,
                "locator": str(path),
                "sha256": h,
                "bytes": path.stat().st_size,
                "exclusion": exclusion,
            }
        else:
            row = {**inventory_package(path, catalogs), "exclusion": None}
            row["stratum"] = stratum(row)
        inventory.append(row)
        print(
            json.dumps(
                {
                    k: row.get(k)
                    for k in [
                        "file",
                        "exclusion",
                        "stratum",
                        "candidate_count",
                        "error",
                    ]
                }
            ),
            flush=True,
        )
    selected = []
    counts = {}
    for group in STRATA:
        available = [r for r in inventory if r.get("stratum") == group]
        chosen = available[:4]
        counts[group] = {
            "available": len(available),
            "selected": len(chosen),
            "zero_power": not chosen,
        }
        selected.extend(chosen)
    predictions = []
    features = {}
    for index, row in enumerate(selected):
        row["slug"] = f"holdout-{index + 1:02d}"
        preserve(row, package_store)
        if "lineage" in row:
            _, package = build_package(row["locator"], catalogs)
            features[row["slug"]] = input_fields(package)
        else:
            features[row["slug"]] = None
        if not row["supported"]:
            row.update(
                selected_requests=[],
                unqueried_candidates=None,
                predictions="abstain:unsupported_input",
            )
            continue
        _, package = build_package(row["locator"], catalogs)
        chosen, unqueried = select_queries(candidates(package))
        row.update(selected_requests=chosen, unqueried_candidates=unqueried)
        engine = jm.Engine(package)
        predictions.extend(
            {
                "id": f"{row['slug']}:{i:03d}",
                "slug": row["slug"],
                "stratum": row["stratum"],
                "request": q,
                "predictions": {rule: engine.predict(q, rule) for rule in RULES},
            }
            for i, q in enumerate(chosen)
        )
    controls = []
    from cs1_harness import rail_study

    for name in ["stock-1", "stock-2"]:
        old = read(OLD / "packages.json")["packages"][name]
        entry = next(
            e for e in read(OLD / "openings.json")["openings"] if e["package"] == name
        )
        controls.append(
            {
                "slug": name,
                "locator": old["locator"],
                "sha256": old["sha256"],
                "requests": rail_study.plan(
                    read(CAP / entry["raw"] / "networks.json.gz")
                )["requests"],
            }
        )
        preserve(controls[-1], package_store)
    freeze(output / "features.json", features)
    frozen = {
        "schema": 1,
        "frozen_at": now(),
        "source": SOURCE,
        "query_source": QUERY_SOURCE,
        "native_source": NATIVE_SOURCE,
        "protocol": PROTOCOL,
        "sources": source_files(),
        "catalogs_sha256": sha(output / "catalogs.json"),
        "features_sha256": sha(output / "features.json"),
        "metadata_build_sha256": sha(HERE / "metadata-build.json"),
        "inventory": inventory,
        "excluded_hashes": sorted(excluded_hashes),
        "strata": counts,
        "selected": selected,
        "controls": controls,
        "predictions": predictions,
        "query_ids": [r["id"] for r in predictions],
        "discordant_predictions": sum(
            len({p["prediction"] for p in r["predictions"].values()}) > 1
            for r in predictions
        ),
    }
    freeze(output / "freeze.json", frozen)
    print(
        json.dumps(
            {
                "freeze_sha256": sha(output / "freeze.json"),
                "strata": counts,
                "queries": len(predictions),
            }
        )
    )


def validate(frozen):
    if frozen["protocol"] != PROTOCOL or frozen["sources"] != source_files():
        raise ValueError(
            "closed protocol or exact inner source-map keys/values changed"
        )
    selected_hashes = [r["sha256"] for r in frozen["selected"]]
    if len(set(selected_hashes)) != len(selected_hashes) or set(selected_hashes) & set(
        frozen["excluded_hashes"]
    ):
        raise ValueError("selected packages overlap each other or exclusions")
    chosen = [
        r["file"]
        for group in STRATA
        for r in [r for r in frozen["inventory"] if r.get("stratum") == group][:4]
    ]
    if chosen != [r["file"] for r in frozen["selected"]]:
        raise ValueError("selected packages differ from deterministic stratum prefixes")
    expected = [
        (r["slug"], q) for r in frozen["selected"] for q in r["selected_requests"]
    ]
    actual = [(r["slug"], r["request"]) for r in frozen["predictions"]]
    ids = [r["id"] for r in frozen["predictions"]]
    if (
        actual != expected
        or ids != frozen["query_ids"]
        or len(set(ids)) != len(ids)
        or len({(s, request_key(q)) for s, q in actual}) != len(actual)
    ):
        raise ValueError("selected query set not unique and complete")
    if any(set(r["predictions"]) != set(RULES) for r in frozen["predictions"]):
        raise ValueError("rule set changed")
    if any(
        p["prediction"] not in {jm.SUCCESS, jm.NO_PATH, jm.ABSTAIN}
        for r in frozen["predictions"]
        for p in r["predictions"].values()
    ):
        raise ValueError("unknown prediction label")


def validate_artifacts(frozen):
    validate(frozen)
    if (
        frozen["catalogs_sha256"] != sha(HERE / "catalogs.json")
        or frozen["metadata_build_sha256"] != sha(HERE / "metadata-build.json")
        or frozen["features_sha256"] != sha(HERE / "features.json")
    ):
        raise ValueError("catalog or metadata build artifact changed")
    for locator, expected in read(HERE / "catalogs.json")["bindings"].items():
        path = Path(locator) if Path(locator).is_absolute() else ROOT / locator
        if sha(path) != expected:
            raise ValueError(f"catalog input changed: {locator}")


def input_fields(package):
    """Every consumed Train field, with unsupported facts left null."""
    rows = []
    for sid, s in sorted(package["segments"].items()):
        if not topology.train_lanes(s):
            continue
        invert = (
            package.get("flag_facts", {})
            .get("invert", {})
            .get(sid, "Invert" in s["flags"])
        )
        outside = package.get("flag_facts", {}).get("outside", {})
        rows.append(
            {
                "id": sid,
                "start": s["start"],
                "end": s["end"],
                "a": list(s["a"]),
                "b": list(s["b"]),
                "invert": invert,
                "start_outside": outside.get(
                    s["start"], "Outside" in package["nodes"][s["start"]]["flags"]
                ),
                "end_outside": outside.get(
                    s["end"], "Outside" in package["nodes"][s["end"]]["flags"]
                ),
                "prefab": s["prefab"],
                "lanes": [
                    {**lane, "vehicle": sorted(lane["vehicle"])} for lane in s["lanes"]
                ],
                "start_direction": s.get("start_direction"),
                "end_direction": s.get("end_direction"),
            }
        )
    return json.loads(encoded(rows))


def reproduce(frozen):
    """Recompute package selection/features/predictions, never open outcomes."""
    validate_artifacts(frozen)
    catalogs, serial, _ = old_catalogs()
    if json.loads(encoded(serial)) != read(HERE / "catalogs.json")["union"]:
        raise ValueError("old catalog union differs")
    maps = Path(frozen["inventory"][0]["locator"]).parent
    if [p.name for p in sorted(maps.glob("*.crp"), key=lambda p: p.name)] != [
        r["file"] for r in frozen["inventory"]
    ]:
        raise ValueError("installed stock filename inventory changed")
    for row in frozen["inventory"]:
        if sha(row["locator"]) != row["sha256"]:
            raise ValueError("inventory bytes changed")
        if row["exclusion"] is None:
            current = inventory_package(Path(row["locator"]), catalogs)
            if any(current[k] != row[k] for k in current):
                raise ValueError(f"input-only inventory differs: {row['file']}")
    features = read(HERE / "features.json")
    for row in frozen["selected"]:
        if "lineage" not in row:
            if features[row["slug"]] is not None:
                raise ValueError("unsupported decoder features invented")
            continue
        _, package = build_package(row["locator"], catalogs)
        if input_fields(package) != features[row["slug"]]:
            raise ValueError("model-used features differ")
        if not row["supported"]:
            if row["selected_requests"]:
                raise ValueError("unsupported package acquired post-native requests")
            continue
        chosen, unqueried = select_queries(candidates(package))
        if (
            chosen != row["selected_requests"]
            or unqueried != row["unqueried_candidates"]
        ):
            raise ValueError("query set not deterministic/complete")
        engine = jm.Engine(package)
        expected = [
            {
                "id": f"{row['slug']}:{i:03d}",
                "slug": row["slug"],
                "stratum": row["stratum"],
                "request": q,
                "predictions": {rule: engine.predict(q, rule) for rule in RULES},
            }
            for i, q in enumerate(chosen)
        ]
        if expected != [p for p in frozen["predictions"] if p["slug"] == row["slug"]]:
            raise ValueError("frozen predictions differ")


def label(row):
    if row is None or row.get("error"):
        return "unknown"
    result = row.get("result", {})
    if result.get("complete") is not True or result.get("released") is not True:
        return "unknown"
    if result.get("success") is False:
        return "no_path"
    if result.get("success") is not True:
        return "unknown"
    positions = result.get("positions", [])
    q = row["request"]
    return (
        "success"
        if positions and positions[0] == q["from"] and positions[-1] == q["to"]
        else "unknown"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "check"])
    parser.add_argument("--output", type=Path, default=HERE)
    parser.add_argument("--package-store", type=Path)
    parser.add_argument(
        "--maps",
        type=Path,
        default=Path(
            "/peach/Games/SteamLibrary/steamapps/common/Cities_Skylines/Files/Maps"
        ),
    )
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.maps, args.output, args.package_store)
    else:
        reproduce(read(args.output / "freeze.json"))
        print("closed source/protocol/query-set validation passed")


if __name__ == "__main__":
    main()
