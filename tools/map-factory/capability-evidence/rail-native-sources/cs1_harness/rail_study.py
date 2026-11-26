"""PL-1215: stock-calibrated directed rail queries, never map absence tests."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import itertools
import json
import os
from pathlib import Path

from . import connections
from .config import Config

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "tools/map-factory/capability-evidence/rail-v3"
LIMIT = 128  # Boundary candidates, plus matching midpoint diagnostics.
PROTOCOL = {
    "id": "PL-1215-directed-rail-v3",
    "entry": "NewGameFromMap/noWorkshop/non-inverted/mods-enabled",
    "query": "NetworkOps.path_start mode=train; existing CreatePath overload",
    "lane_types": ["Vehicle", "TransportVehicle", "CargoVehicle"],
    "vehicle": "Train",
    "category": "All",
    "max_length": 100000,
    "random_seed": 857,
    "rule": "source away from outside node, destination towards it; swap direction for segment Invert; test native Forward/Backward bits directly, not composite Avoid enum values or display names",
    "order": "distinct-edge first, then lexicographic from/to [segment,lane,offset]; first 128 boundary requests",
    "diagnostics": "midpoint per selected directed pair; reverse first boundary without changing lanes (not assumed invalid); Train query from first boundary source to smallest Car-but-not-Train segment/lane at offset128 (invalid vehicle pair)",
    "prediction": "direction-compatible candidates, not predicted native successes; all finite misses remain Unknown",
    "scope": "sampled_native_lane_paths_at_opening; file identity, not memory attestation or strict no-mods",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.datetime.now(datetime.UTC).isoformat()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def freeze(path, value):
    """Exclusive durable write: a freeze cannot silently change on a retry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    return digest(path)


def sources():
    harness = ROOT / "tools/cs1-harness"
    files = sorted((harness / "mod").glob("*.cs")) + sorted((harness / "cs1_harness").glob("*.py"))
    return {str(path.relative_to(ROOT)): digest(path) for path in files}


def tokens(value):
    return set(value.split(", "))


def inventory(networks):
    directions = networks["direction_enum_values"]
    segments = {s["id"]: s for s in networks["segments"]}
    ends = connections.outside_endpoints(networks, "Train")
    for end in ends:
        segment = segments[end["segment"]]
        end["segment_flags"] = segment["flags"]
        end["node_flags"] = segment["start_flags" if end["offset"] == 0 else "end_flags"]
        end["lanes"] = sorted(end["lanes"], key=lambda lane: lane["index"])
        for lane in end["lanes"]:
            if (
                not {"direction", "direction_bits", "forward", "backward", "type", "category", "id", "flags"}
                <= lane.keys()
            ):
                raise ValueError("incomplete native lane inventory")
            if lane["forward"] != bool(lane["direction_bits"] & directions["Forward"]) or lane["backward"] != bool(
                lane["direction_bits"] & directions["Backward"]
            ):
                raise ValueError("normalized lane direction differs from native bits")
    return sorted(ends, key=lambda end: (end["segment"], end["node"], end["offset"]))


def compatible(end, lane, *, source):
    if not tokens(lane["type"]) & set(PROTOCOL["lane_types"]):
        return False
    forward = (end["offset"] == 0) == source
    if "Invert" in tokens(end["segment_flags"]):
        forward = not forward
    return lane["forward" if forward else "backward"]


def plan(networks):
    ends = inventory(networks)
    boundary = []
    for a, b in itertools.permutations(ends, 2):
        if a["segment"] == b["segment"] or a["node"] == b["node"]:
            continue
        for la, lb in itertools.product(a["lanes"], b["lanes"]):
            if compatible(a, la, source=True) and compatible(b, lb, source=False):
                boundary.append(
                    {
                        "capability": "rail",
                        "name": "directed-outside-to-outside",
                        "position_kind": "boundary",
                        "diagnostic": False,
                        "endpoint_edges": [a["edge"], b["edge"]],
                        "from": [a["segment"], la["index"], a["offset"]],
                        "to": [b["segment"], lb["index"], b["offset"]],
                    }
                )
    boundary.sort(key=lambda r: (r["endpoint_edges"][0] == r["endpoint_edges"][1], r["from"], r["to"]))
    requests = []
    for row in boundary[:LIMIT]:
        requests.append(row)
        requests.append(
            {
                **row,
                "position_kind": "midpoint",
                "diagnostic": True,
                "from": [*row["from"][:2], 128],
                "to": [*row["to"][:2], 128],
            }
        )
    if boundary:
        row = boundary[0]
        # Stock rail has one-way lanes; if a lane is bidirectional this is
        # explicitly only a reversed-position diagnostic, not a known failure.
        requests.append(
            {
                **row,
                "name": "reversed-positions-diagnostic",
                "diagnostic": True,
                "from": row["to"],
                "to": row["from"],
                "endpoint_edges": row["endpoint_edges"][::-1],
            }
        )
        invalid_destinations = sorted(
            [segment["id"], lane["index"], 128]
            for segment in networks["segments"]
            for lane in segment["lanes"]
            if "Car" in tokens(lane["vehicle"]) and "Train" not in tokens(lane["vehicle"])
        )
        if invalid_destinations:
            requests.append(
                {
                    **row,
                    "name": "invalid-train-to-car-lane",
                    "position_kind": "invalid_vehicle_pair",
                    "diagnostic": True,
                    "from": row["from"],
                    "to": invalid_destinations[0],
                    "endpoint_edges": [row["endpoint_edges"][0], None],
                }
            )
    return {"endpoints": ends, "candidate_boundary_count": len(boundary), "boundary_limit": LIMIT, "requests": requests}


def context_valid(observation):
    """New harness bytes cannot borrow a previous opening's identity."""
    launch, opening = (observation.get(k, {}) for k in ("launch_runtime_identity", "runtime_identity"))
    for identity in (launch, opening):
        if not identity.get("build_matches") or not identity.get("assemblies"):
            return False
        if identity.get("unresolved_loaded_assemblies") or identity.get("excluded_dynamic_assemblies") is None:
            return False
        status = identity.get("status", {})
        if not status.get("plugins") or not {"errors", "error_count", "enabled_mod_count"} <= status.keys():
            return False
        if not {"host_pid", "process_start_ticks", "executable", "observed_at"} <= identity.keys():
            return False
        from .runtime_identity import validate_identity

        try:
            validate_identity(identity, observation["build_receipt"])
        except (KeyError, ValueError):
            return False
    if (launch["host_pid"], launch["process_start_ticks"]) != (opening["host_pid"], opening["process_start_ticks"]):
        return False
    context = observation.get("native_context", {})
    return (
        context.get("update_mode") == "NewGameFromMap"
        and context.get("invert_traffic") == "False"
        and context.get("no_workshop") is True
        and context.get("mods_enabled") is True
    )


def classify(row):
    result = row.get("result", {})
    if not result.get("complete") or not result.get("released"):
        return "Unknown"
    if not result.get("success"):
        return "selected_query_failure"
    positions = result.get("positions", [])
    request = row["request"]
    if not positions or positions[0] != request["from"] or positions[-1] != request["to"]:
        return "returned_endpoint_mismatch"
    return "exact_path_success"


def prepare(study, maps):
    corpus = ROOT / "tools/map-factory/survey/basemaps.json"
    rows = [row for row in json.loads(corpus.read_text()) if row["file"] != "CO.crp"]
    if len(rows) != 104:
        raise ValueError("expected the original 104-map corpus")
    eligible = sorted(
        (
            r
            for r in rows
            if r.get("meta", {}).get("builtin") == 1
            and r["meta"].get("incomingTrainTracks", 0) > 0
            and r["meta"].get("outgoingTrainTracks", 0) > 0
        ),
        key=lambda r: r["file"],
    )
    controls = [
        {
            "slug": f"stock-{i + 1}",
            "file": r["file"],
            "package": str(maps / r["file"]),
            "artifact_sha256": digest(maps / r["file"]),
            "metadata": r["meta"],
        }
        for i, r in enumerate(eligible[:2])
    ]
    if len(controls) != 2:
        raise ValueError("two stock controls not available")
    selection = ROOT / "tools/map-factory/capability-evidence/outside-v1/selection.json"
    original = json.loads(selection.read_text())
    cfg = Config.for_host()
    return freeze(
        study / "selection.json",
        {
            "schema": 1,
            "frozen_at": now(),
            "source_base": "29b095475ba2f93c7e918fefc08c736493670304",
            "protocol": PROTOCOL,
            "sources": sources(),
            "build_receipt": json.loads((cfg.build_dir / "build-receipt.json").read_text()),
            "stock_rule": "first two builtin corpus filenames lexicographically with metadata incoming/outgoing train > 0; no replacement after native inspection",
            "corpus_sha256": digest(corpus),
            "corpus_inventory": {r["file"]: digest(maps / r["file"]) for r in rows},
            "controls": controls,
            "original_selection_sha256": digest(selection),
            "cohort": original["cases"],
            "cohort_gate": "both stock controls completed and bound; at least one exact directed literal-boundary success; each control rejects the invalid Train-to-Car query; freeze cohort enumeration only after this gate",
        },
    )


def summarize(case_dir, selection):
    observation = json.loads((case_dir / "observation.json").read_text())
    result = {
        "artifact_sha256": observation["artifact_sha256"],
        "completed": observation.get("completed", False),
        "error": observation.get("error"),
        "context_bound": context_valid(observation),
        "boundary_successes": 0,
        "distinct_edge_boundary_successes": 0,
        "boundary_failures": 0,
        "boundary_unknown": 0,
        "diagnostics": [],
    }
    path = case_dir / "query-freeze.json"
    if not path.exists():
        return result
    frozen = json.loads(path.read_text())
    networks = json.loads((case_dir / "networks.json").read_text())
    if (
        observation.get("query_freeze_sha256") != digest(path)
        or frozen["selection_sha256"] != digest(selection)
        or frozen["plan"] != plan(networks)
        or frozen["networks_sha256"] != digest(case_dir / "networks.json")
        or frozen["artifact_sha256"] != observation["artifact_sha256"]
        or frozen["runtime_identity"] != observation["runtime_identity"]
        or frozen["protocol"] != PROTOCOL
        or observation["build_receipt"] != json.loads(selection.read_text())["build_receipt"]
    ):
        raise ValueError("query freeze is not bound to this observation")
    rows = observation.get("paths", [])
    if [r["request"] for r in rows] != frozen["plan"]["requests"][: len(rows)]:
        raise ValueError("queries differ from frozen prefix")
    if observation.get("completed") and len(rows) != len(frozen["plan"]["requests"]):
        raise ValueError("completed observation omitted frozen requests")
    if any(r.get("submitted_at", "") < frozen["frozen_at"] for r in rows):
        raise ValueError("query predates inventory freeze or lacks dated submission")
    result["candidate_boundary_count"] = frozen["plan"]["candidate_boundary_count"]
    result["unqueried_boundary_candidates"] = max(0, frozen["plan"]["candidate_boundary_count"] - LIMIT)
    result["missing_reason"] = "no_pair_or_directed_lane" if not frozen["plan"]["requests"] else None
    for index, request in enumerate(frozen["plan"]["requests"]):
        outcome = classify(rows[index]) if index < len(rows) else "Unknown"
        if request["diagnostic"]:
            result["diagnostics"].append({"request": request, "outcome": outcome})
        elif outcome == "exact_path_success" and result["context_bound"]:
            result["boundary_successes"] += 1
            if request["endpoint_edges"][0] != request["endpoint_edges"][1]:
                result["distinct_edge_boundary_successes"] += 1
        elif outcome == "selected_query_failure":
            result["boundary_failures"] += 1
        else:
            result["boundary_unknown"] += 1
    return result


def controls_valid(study):
    selection_path = study / "selection.json"
    selection = json.loads(selection_path.read_text())
    results = []
    for case in selection["controls"]:
        case_dir = study / "raw" / case["slug"]
        if not (case_dir / "observation.json").exists():
            return False
        result = summarize(case_dir, selection_path)
        if result["artifact_sha256"] != case["artifact_sha256"] or not result["completed"]:
            return False
        results.append(result)
    return all(
        r["context_bound"]
        and any(
            d["request"]["name"] == "invalid-train-to-car-lane" and d["outcome"] == "selected_query_failure"
            for d in r["diagnostics"]
        )
        for r in results
    ) and any(r["boundary_successes"] for r in results)


def collect_case(study, case):
    selection_path = study / "selection.json"
    selection = json.loads(selection_path.read_text())
    if selection["sources"] != sources() or selection["protocol"] != PROTOCOL:
        raise ValueError("source/protocol changed since prelaunch freeze; create a new study")
    package = Path(case["package"])
    if digest(package) != case["artifact_sha256"]:
        raise ValueError("selected package changed")
    if json.loads((Config.for_host().build_dir / "build-receipt.json").read_text()) != selection["build_receipt"]:
        raise ValueError("build differs from prelaunch freeze")

    def request_plan(networks, observation, out):
        if not context_valid(observation):
            raise ValueError("missing/unbound runtime or plugin inventory")
        planned = plan(networks)
        observation["protocol"] = PROTOCOL
        observation["candidate_coverage"] = {
            "rail": {
                "candidate_boundary_requests": planned["candidate_boundary_count"],
                "planned_boundary_requests": min(LIMIT, planned["candidate_boundary_count"]),
                "diagnostic_requests": sum(r["diagnostic"] for r in planned["requests"]),
                "boundary_limit": LIMIT,
            }
        }
        observation["query_freeze_sha256"] = freeze(
            out / "query-freeze.json",
            {
                "frozen_at": now(),
                "selection_sha256": digest(selection_path),
                "artifact_sha256": observation["artifact_sha256"],
                "protocol": PROTOCOL,
                "runtime_identity": observation["runtime_identity"],
                "networks_sha256": digest(out / "networks.json"),
                "plan": planned,
            },
        )
        return planned["requests"]

    return connections.collect(
        package, {}, study / "raw" / case["slug"], 0, {"rail"}, request_plan=request_plan, issue="PL-1215"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "controls", "cohort", "verify"])
    parser.add_argument("--study", type=Path, default=STUDY)
    parser.add_argument("--maps", type=Path, default=Config.for_host().game_dir / "Files/Maps")
    parser.add_argument("--only")
    args = parser.parse_args()
    if args.action == "prepare":
        print(prepare(args.study, args.maps))
        return
    selection = json.loads((args.study / "selection.json").read_text())
    if args.action == "cohort" and not controls_valid(args.study):
        raise ValueError("no validated stock-positive protocol; cohort queries forbidden")
    if args.action in {"controls", "cohort"}:
        for case in selection["controls" if args.action == "controls" else "cohort"]:
            if args.only and case["slug"] != args.only:
                continue
            result = collect_case(args.study, case)
            print(
                json.dumps({"slug": case["slug"], "completed": result.get("completed"), "error": result.get("error")}),
                flush=True,
            )
            if not result.get("completed"):
                break
    else:
        results = {
            case["slug"]: summarize(args.study / "raw" / case["slug"], args.study / "selection.json")
            for case in selection["controls"] + selection["cohort"]
            if (args.study / "raw" / case["slug"] / "observation.json").exists()
        }
        print(json.dumps({"stock_gate": controls_valid(args.study), "cases": results}, indent=2))


if __name__ == "__main__":
    main()
