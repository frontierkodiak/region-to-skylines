"""Inventory and eligibility for the retained outside-connection road/ship/air queries.

Reads the accepted outside-v1 evidence bundle and re-derives every retained
request from its raw observation bytes. Nothing is trusted from the assembled
`evidence.json` row without a byte-level re-check:

* the gzip member must decompress to bytes whose SHA-256 equals the recorded
  SHA-256 of the original observation / network snapshot;
* every native-path row must equal exactly one raw `paths` entry of its attempt,
  request and result included, one-to-one and in the same count;
* the row's label must be the one the raw result implies;
* the annotated `literal_boundary_request` must equal the recomputed one
  wherever the request carries the protocol's `position_kind` field.

Rows that cannot be bound are retained with `label_status = unknown` and an
explicit reason; they never become a no-path label.

Run:  python3 inventory.py
Writes: inventory.json
"""

from __future__ import annotations

import collections
import gzip
import hashlib
import json
from pathlib import Path

import topology

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "outside-v1"
EVIDENCE = SOURCE / "evidence.json"
MODES = ("road", "ship", "air")
MODE_VEHICLE = {"road": "car", "ship": "ship", "air": "plane"}
CAPABILITY_VEHICLE = {"car": "road", "ship": "ship", "plane": "air"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=1, sort_keys=True) + "\n").encode()


def load_raw(ref, cache):
    path = ref["path"]
    if path not in cache:
        raw = gzip.decompress((SOURCE / path).read_bytes())
        recorded = ref["sha256"]
        actual = sha(raw)
        cache[path] = {
            "raw": raw,
            "data": json.loads(raw),
            "recorded_sha256": recorded,
            "actual_sha256": actual,
            "bytes": len(raw),
        }
    return cache[path]


def tokens(value):
    return frozenset(part for part in (value or "").split(", ") if part)


def endpoint_edge(segment, offset):
    key = "start_flags" if int(offset) == 0 else "end_flags"
    position = "a" if int(offset) == 0 else "b"
    if "Outside" not in tokens(segment.get(key, "")):
        return None
    x, _, z = segment[position]
    if abs(x) > abs(z):
        return "east" if x > 0 else "west"
    return "north" if z > 0 else "south"


def endpoint_roles(segment, offset):
    key = "start_flags" if int(offset) == 0 else "end_flags"
    return sorted(
        flag
        for flag in tokens(segment.get(key, ""))
        if flag in {"Outside", "OneWayIn", "OneWayOut"}
    )


def boundary_evidence(segments, request):
    """Recompute the source study's literal-boundary test from the snapshot.

    `boundary` is the two-edge test: both endpoints at a 0/255 offset on two
    distinct `Outside` nodes of two distinct segments. A literal boundary
    request additionally has its ends on different map edges; the same-edge
    case is a separate stratum, exactly as the accepted study records it.
    """
    empty = {
        "boundary": False,
        "literal": False,
        "same_edge": False,
        "source_roles": None,
        "target_roles": None,
        "source_edge": None,
        "target_edge": None,
    }
    if request.get("from")[2] not in (0, 255) or request.get("to")[2] not in (0, 255):
        return empty
    source = segments.get(int(request["from"][0]))
    target = segments.get(int(request["to"][0]))
    if source is None or target is None:
        return empty
    source_node = topology.endpoint_node(source, request["from"][2])
    target_node = topology.endpoint_node(target, request["to"][2])
    boundary = (
        source_node != target_node
        and source["id"] != target["id"]
        and "Outside" in tokens(source["start_flags" if request["from"][2] == 0 else "end_flags"])
        and "Outside" in tokens(target["start_flags" if request["to"][2] == 0 else "end_flags"])
    )
    source_edge = endpoint_edge(source, request["from"][2])
    target_edge = endpoint_edge(target, request["to"][2])
    return {
        "boundary": boundary,
        "literal": boundary and source_edge != target_edge,
        "same_edge": boundary and source_edge == target_edge,
        "source_roles": endpoint_roles(source, request["from"][2]),
        "target_roles": endpoint_roles(target, request["to"][2]),
        "source_edge": source_edge,
        "target_edge": target_edge,
    }


def returned_match(request, result):
    positions = (result or {}).get("positions") or []
    return bool(
        len(positions) >= 2
        and positions[0] == request["from"]
        and positions[-1] == request["to"]
    )


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def classify(row, segments):
    """Return (stratum, eligible, exclusion_reason, label_status).

    `label_status` is `eligible` for a scored request, `excluded` for an
    observed request outside the scored strata, and `unknown` when the response
    cannot label the query at all. A `success = true` result whose returned path
    does not end at the requested offsets is unknown, not a positive: the label
    contract in `protocol.json` requires the endpoints to match.
    """
    request = row.get("request")
    result = row.get("path_result") or {}
    if row.get("archive_context"):
        return "archived_player_run", False, "player_construction_not_unchanged_map", "excluded"
    if not request:
        return "unrequested", False, "no_request_recorded", "unknown"
    if "position_kind" not in request:
        # The earliest collector version recorded neither a position kind nor a
        # direction, so its requests cannot be assigned to a stratum and stay
        # unknown rather than becoming a label.
        return "unclassified_protocol", False, "protocol_fields_absent", "unknown"
    if request.get("rail") is True or request.get("capability") == "rail":
        return "rail_flagged", False, "request_is_rail", "excluded"
    evidence = boundary_evidence(segments, request)
    if request.get("position_kind") == "midpoint":
        stratum, eligible, exclusion = (
            "midpoint_diagnostic",
            False,
            "midpoint_diagnostic_unscored",
        )
    elif not evidence["boundary"]:
        stratum, eligible, exclusion = (
            "non_boundary",
            False,
            "not_a_literal_boundary_request",
        )
    elif evidence["same_edge"]:
        # Same-edge pairs are literal boundary requests whose ends sit on one
        # map edge; scored as their own stratum, never pooled with distinct-edge.
        stratum, eligible, exclusion = "same_edge", True, None
    else:
        stratum, eligible, exclusion = "primary_distinct_edge", True, None
    complete = type(result.get("complete")) is bool and result.get("complete")
    released = type(result.get("released")) is bool and result.get("released")
    success = type(result.get("success")) is bool and result.get("success")
    if not (complete and released):
        return stratum, False, "incomplete_or_unreleased_response", "unknown"
    if type(result.get("success")) is not bool:
        return stratum, False, "non_boolean_success", "unknown"
    if success and not returned_match(request, result):
        return stratum, False, "returned_endpoints_mismatch", "unknown"
    return stratum, eligible, exclusion, ("eligible" if eligible else "excluded")


def build():
    """Reconstruct all three documents from retained bytes, without writing."""
    evidence_raw = EVIDENCE.read_bytes()
    evidence = json.loads(evidence_raw)
    cache = {}
    attempts_by_path = {}
    for case in evidence["artifacts"]:
        for attempt in case.get("attempts", []):
            attempts_by_path[attempt["observation_evidence"]["path"]] = (case, attempt)

    anomalies = []
    openings = {}
    rows_by_attempt = collections.defaultdict(list)
    for row in evidence["rows"]:
        if row["oracle_type"] != "native_path" or row["capability_id"] not in MODES:
            continue
        rows_by_attempt[(row["slug"], row.get("attempt_id"))].append(row)

    queries = []
    for (slug, attempt_id), rows in sorted(
        rows_by_attempt.items(), key=lambda item: (item[0][0], str(item[0][1]))
    ):
        case = next(item for item in evidence["artifacts"] if item["slug"] == slug)
        if attempt_id is None:
            # Two kinds of row reach here. An archived first-hour player run
            # carries a named probe result but no literal request and no opening;
            # a placeholder row carries nothing at all. Neither is a negative.
            for index, row in enumerate(rows):
                result = row.get("path_result") or {}
                archived = bool(row.get("archive_context"))
                complete = type(result.get("complete")) is bool and result.get("complete")
                observed = (
                    result.get("success")
                    if archived and complete and type(result.get("success")) is bool
                    else None
                )
                queries.append(
                    {
                        "query_id": f"{slug}/no-attempt/{row['capability_id']}/{index:03d}",
                        "slug": slug,
                        "attempt_id": None,
                        "study": "archive" if archived else None,
                        "mode": row["capability_id"],
                        "stratum": "archived_player_run" if archived else "unrequested",
                        "eligible": False,
                        "exclusion": (
                            "player_construction_not_unchanged_map"
                            if archived
                            else "no_request_recorded"
                        ),
                        "label_status": "excluded" if archived else "unknown",
                        "label": (
                            None
                            if observed is None
                            else "success"
                            if observed is True
                            else "failure"
                        ),
                        "observed": observed,
                        "request": None,
                        "position_kind": None,
                        "direction": None,
                        "endpoint_roles": None,
                        "endpoint_edges": None,
                        "returned_endpoints_match": None,
                        "result": None,
                        "runtime_bound": None,
                        "raw": {
                            "observation": None,
                            "observation_sha256": None,
                            "networks": None,
                            "networks_sha256": None,
                            "artifact_sha256": row.get("artifact_sha256"),
                        },
                    }
                )
            continue
        attempt = next(
            item
            for item in case["attempts"]
            if item.get("attempt_id") == attempt_id
        )
        observation_ref = attempt["observation_evidence"]
        observation = load_raw(observation_ref, cache)
        if observation["recorded_sha256"] != observation["actual_sha256"]:
            anomalies.append(
                {
                    "kind": "observation_sha_mismatch",
                    "slug": slug,
                    "attempt_id": attempt_id,
                    "path": observation_ref["path"],
                }
            )
        network_ref = attempt["native_evidence"].get("networks.json")
        if network_ref is None:
            anomalies.append(
                {"kind": "missing_networks", "slug": slug, "attempt_id": attempt_id}
            )
            networks = {"segments": []}
        else:
            networks = load_raw(network_ref, cache)
            if networks["recorded_sha256"] != networks["actual_sha256"]:
                anomalies.append(
                    {
                        "kind": "networks_sha_mismatch",
                        "slug": slug,
                        "attempt_id": attempt_id,
                        "path": network_ref["path"],
                    }
                )
            networks = networks["data"]
        segments = {segment["id"]: segment for segment in networks["segments"]}
        package = topology.from_native(networks, f"{slug}/{attempt_id}")
        observation_data = observation["data"]
        # Only the modes this study covers; the same observation also holds the
        # rail requests that have separately reviewed research.
        paths = [
            path
            for path in observation_data.get("paths", [])
            if CAPABILITY_VEHICLE.get(path.get("mode")) in MODES
        ]
        placeholder_rows = [row for row in rows if not row.get("request")]
        rows = [row for row in rows if row.get("request")]
        openings[f"{slug}/{attempt_id}"] = {
            "slug": slug,
            "attempt_id": attempt_id,
            "artifact_sha256": attempt["artifact_sha256"],
            "study": "targeted-v2" if str(attempt_id).startswith("native-v2") else "v1",
            "observation": {
                "path": observation_ref["path"],
                "sha256": observation["recorded_sha256"],
                "bytes": observation["bytes"],
            },
            "networks": {
                "path": network_ref["path"] if network_ref else None,
                "sha256": network_ref["sha256"] if network_ref else None,
                "segments": len(segments),
                "node_flag_conflicts": len(package["node_flag_conflicts"]),
            },
            "collector_sha256": observation_data.get("collector_sha256"),
            "build_dll_sha256": (observation_data.get("build_receipt") or {}).get("dll_sha256"),
            "game_executable_sha256": (observation_data.get("build_receipt") or {}).get(
                "game_executable_sha256"
            ),
            "runtime_build_matches": bool(
                (observation_data.get("runtime_identity") or {}).get("build_matches")
            ),
            "native_context": observation_data.get("native_context"),
            "protocol": observation_data.get("protocol"),
            "completed": observation_data.get("completed"),
            "requested_capabilities": observation_data.get("requested_capabilities"),
            "paths": len(paths),
        }
        # One-to-one binding between assembled rows and raw paths.
        by_request = collections.Counter(canonical(path["request"]) for path in paths)
        by_request_and_result = collections.Counter(
            canonical({"request": path["request"], "result": path.get("result")})
            for path in paths
        )
        used = collections.Counter()
        matched = 0
        for row in rows:
            key = canonical(row.get("request"))
            key2 = canonical(
                {"request": row.get("request"), "result": row.get("path_result")}
            )
            if by_request[key] == 0:
                anomalies.append(
                    {
                        "kind": "row_without_raw_path",
                        "slug": slug,
                        "attempt_id": attempt_id,
                        "request": row.get("request"),
                    }
                )
                row["_bind"] = "missing"
                continue
            if by_request_and_result[key2] - used[key2] <= 0:
                anomalies.append(
                    {
                        "kind": "result_differs_from_raw",
                        "slug": slug,
                        "attempt_id": attempt_id,
                        "request": row.get("request"),
                    }
                )
                row["_bind"] = "result_mismatch"
                continue
            used[key2] += 1
            matched += 1
            row["_bind"] = "bound"
        if matched != len(paths):
            anomalies.append(
                {
                    "kind": "count_mismatch",
                    "slug": slug,
                    "attempt_id": attempt_id,
                    "raw_paths": len(paths),
                    "bound_rows": matched,
                }
            )

        for index, row in enumerate(placeholder_rows):
            queries.append(
                {
                    "query_id": f"{slug}/{attempt_id}/{row['capability_id']}/nil-{index:02d}",
                    "slug": slug,
                    "attempt_id": attempt_id,
                    "study": openings[f"{slug}/{attempt_id}"]["study"],
                    "mode": row["capability_id"],
                    "stratum": "unrequested",
                    "eligible": False,
                    "exclusion": "no_request_recorded",
                    "label_status": "unknown",
                    "label": None,
                    "observed": None,
                    "request": None,
                    "position_kind": None,
                    "direction": None,
                    "endpoint_roles": None,
                    "endpoint_edges": None,
                    "returned_endpoints_match": None,
                    "result": None,
                    "runtime_bound": openings[f"{slug}/{attempt_id}"]["runtime_build_matches"],
                    "raw": {
                        "observation": observation_ref["path"],
                        "observation_sha256": observation["recorded_sha256"],
                        "networks": network_ref["path"] if network_ref else None,
                        "networks_sha256": network_ref["sha256"] if network_ref else None,
                        "artifact_sha256": attempt["artifact_sha256"],
                    },
                }
            )

        for index, row in enumerate(rows):
            request = row.get("request")
            mode = row["capability_id"]
            result = row.get("path_result") or {}
            complete = type(result.get("complete")) is bool and result.get("complete")
            released = type(result.get("released")) is bool and result.get("released")
            success = result.get("success")
            observed = success if complete and type(success) is bool else None
            if observed != row.get("observed"):
                anomalies.append(
                    {
                        "kind": "label_differs_from_raw",
                        "slug": slug,
                        "attempt_id": attempt_id,
                        "request": request,
                        "row": row.get("observed"),
                        "recomputed": observed,
                    }
                )
            stratum, eligible, exclusion, label_status = classify(row, segments)
            bounds = boundary_evidence(segments, request) if request else None
            source_roles = bounds["source_roles"] if bounds else None
            target_roles = bounds["target_roles"] if bounds else None
            if (
                request
                and "position_kind" in request
                and bounds is not None
                and row.get("literal_boundary_request") is not None
                and bool(row.get("literal_boundary_request")) != bool(bounds["literal"])
            ):
                anomalies.append(
                    {
                        "kind": "boundary_annotation_differs",
                        "slug": slug,
                        "attempt_id": attempt_id,
                        "request": request,
                        "annotated": row.get("literal_boundary_request"),
                        "recomputed": bounds["literal"],
                    }
                )
            source_lanes = (
                topology.mode_lanes(package["segments"][int(request["from"][0])], mode)
                if request and int(request["from"][0]) in package["segments"]
                else []
            )
            target_lanes = (
                topology.mode_lanes(package["segments"][int(request["to"][0])], mode)
                if request and int(request["to"][0]) in package["segments"]
                else []
            )
            if eligible:
                if row.get("_bind") != "bound":
                    eligible, exclusion, label_status = (
                        False,
                        "row_does_not_bind_to_raw_observation",
                        "unknown",
                    )
                elif not source_lanes or not target_lanes:
                    eligible, exclusion = False, "mode_lane_absent_at_endpoint"
                elif request["from"][1] not in {lane["index"] for lane in source_lanes}:
                    eligible, exclusion = False, "requested_source_lane_absent"
                elif request["to"][1] not in {lane["index"] for lane in target_lanes}:
                    eligible, exclusion = False, "requested_target_lane_absent"
            remaining = [flag for flag in ("_bind",)]
            for flag in remaining:
                row.pop(flag, None)
            queries.append(
                {
                    "query_id": f"{slug}/{attempt_id}/{mode}/{index:03d}",
                    "slug": slug,
                    "attempt_id": attempt_id,
                    "study": openings[f"{slug}/{attempt_id}"]["study"],
                    "mode": mode,
                    "stratum": stratum,
                    "eligible": eligible,
                    "exclusion": exclusion,
                    "label_status": label_status,
                    "label": (
                        None
                        if label_status == "unknown"
                        else "success"
                        if observed is True
                        else "failure"
                        if observed is False
                        else None
                    ),
                    "observed": observed,
                    "request": request,
                    "position_kind": (request or {}).get("position_kind"),
                    "direction": (request or {}).get("direction"),
                    "endpoint_roles": [source_roles, target_roles],
                    "endpoint_edges": [
                        endpoint_edge(segments[int(request["from"][0])], request["from"][2])
                        if request and int(request["from"][0]) in segments
                        else None,
                        endpoint_edge(segments[int(request["to"][0])], request["to"][2])
                        if request and int(request["to"][0]) in segments
                        else None,
                    ]
                    if request
                    else None,
                    "returned_endpoints_match": returned_match(request, result)
                    if request and result
                    else None,
                    "result": {
                        "complete": complete,
                        "released": released,
                        "success": success,
                        "flags": result.get("flags"),
                        "length": result.get("length"),
                        "positions": len(result.get("positions") or []),
                    }
                    if result
                    else None,
                    "runtime_bound": openings[f"{slug}/{attempt_id}"]["runtime_build_matches"],
                    "raw": {
                        "observation": observation_ref["path"],
                        "observation_sha256": observation["recorded_sha256"],
                        "networks": network_ref["path"] if network_ref else None,
                        "networks_sha256": network_ref["sha256"] if network_ref else None,
                        "artifact_sha256": attempt["artifact_sha256"],
                    },
                }
            )

    # Correlated repeats: the same (square, mode, request) asked in two openings
    # of the same unchanged package; and the reversed-direction sibling inside
    # one opening.
    seen = {}
    for query in queries:
        if not query["request"]:
            continue
        key = (
            query["slug"],
            query["mode"],
            canonical(query["request"]["from"]),
            canonical(query["request"]["to"]),
        )
        if key in seen and seen[key][0] != query["attempt_id"]:
            query["repeat_of"] = seen[key][1]
        else:
            seen.setdefault(key, (query["attempt_id"], query["query_id"]))
    siblings = {}
    for query in queries:
        request = query["request"]
        if not request:
            continue
        key = (
            query["slug"],
            query["attempt_id"],
            query["mode"],
            canonical(request["from"]),
            canonical(request["to"]),
        )
        sibling = (
            query["slug"],
            query["attempt_id"],
            query["mode"],
            canonical(request["to"]),
            canonical(request["from"]),
        )
        if sibling in siblings:
            query["reverse_of"] = siblings[sibling]["query_id"]
            siblings[sibling]["reverse_of"] = query["query_id"]
        else:
            siblings[key] = query

    # A midpoint request is the same segment pair asked at offset 128; its
    # outcome is compared with its boundary sibling as a correlated repeat.
    by_key = collections.defaultdict(list)
    for query in queries:
        if not query["request"] or query["stratum"] not in {
            "primary_distinct_edge",
            "same_edge",
            "midpoint_diagnostic",
        }:
            continue
        by_key[
            (
                query["slug"],
                query["attempt_id"],
                query["mode"],
                query["request"]["from"][0],
                query["request"]["to"][0],
                query["request"]["from"][1],
                query["request"]["to"][1],
                query["direction"],
            )
        ].append(query)
    midpoint_pairs = []
    for group in by_key.values():
        boundary = [
            item for item in group if item["stratum"] != "midpoint_diagnostic"
        ]
        midpoint = [
            item for item in group if item["stratum"] == "midpoint_diagnostic"
        ]
        if len(boundary) == 1 and len(midpoint) == 1:
            midpoint_pairs.append(
                {
                    "boundary": boundary[0]["query_id"],
                    "midpoint": midpoint[0]["query_id"],
                    "boundary_label": boundary[0]["observed"],
                    "midpoint_label": midpoint[0]["observed"],
                    "agree": boundary[0]["observed"] == midpoint[0]["observed"],
                }
            )

    def count(predicate):
        return sum(1 for query in queries if predicate(query))

    counts = {
        "queries": len(queries),
        "by_mode": dict(collections.Counter(query["mode"] for query in queries)),
        "by_stratum": dict(
            collections.Counter(query["stratum"] for query in queries)
        ),
        "by_exclusion": dict(
            collections.Counter(query["exclusion"] for query in queries if query["exclusion"])
        ),
        "eligible": count(lambda query: query["eligible"]),
        "eligible_by_mode": dict(
            collections.Counter(query["mode"] for query in queries if query["eligible"])
        ),
        "eligible_by_stratum": dict(
            collections.Counter(query["stratum"] for query in queries if query["eligible"])
        ),
        "labels": dict(
            collections.Counter(
                str(query["observed"]) for query in queries if query["eligible"]
            )
        ),
        "labels_by_mode": {
            mode: dict(
                collections.Counter(
                    str(query["observed"])
                    for query in queries
                    if query["eligible"] and query["mode"] == mode
                )
            )
            for mode in MODES
        },
        "openings": len(openings),
        "anomalies": len(anomalies),
        "midpoint_pairs": len(midpoint_pairs),
        "midpoint_agree": sum(1 for pair in midpoint_pairs if pair["agree"]),
    }
    inventory = {
        "schema": 1,
        "study": "outside-query-model-v1",
        "scope": (
            "inventory and eligibility of every retained road, ship and air native "
            "path request in the accepted outside-v1 study (PL-1121 v1 and PL-1142 "
            "targeted v2). Rail has separately reviewed research and is out of scope."
        ),
        "source": {
            "evidence": "outside-v1/evidence.json",
            "evidence_sha256": sha(evidence_raw),
            "evidence_bytes": len(evidence_raw),
        },
        "eligibility_rules": {
            "primary_distinct_edge": (
                "literal boundary request (offsets 0/255 at two distinct Outside "
                "nodes on two segments), ends on different map edges, complete and "
                "released native response"
            ),
            "same_edge": "same literal boundary test, both ends on one map edge",
            "midpoint_diagnostic": "offset 128 diagnostic; never scored, its boundary sibling is the correlated repeat",
            "unclassified_protocol": "earliest collector version: no position_kind or rail field; unknown, not scored",
            "not_a_literal_boundary_request": "endpoint not at 0/255, not at an Outside node, same node or same segment",
            "player_construction_not_unchanged_map": "archived first-hour player run; excluded",
            "mode_lane_absent_at_endpoint": "endpoint segment carries no lane of the mode's vehicle",
            "requested_source_lane_absent": "the request names a lane the endpoint segment does not have",
            "requested_target_lane_absent": "the request names a lane the endpoint segment does not have",
        },
        "openings": [openings[key] for key in sorted(openings)],
        "counts": counts,
        "anomalies": anomalies,
        "midpoint_pairs": midpoint_pairs,
        "queries": queries,
    }
    inventory_bytes = json_bytes(inventory)

    # Label-free model inputs. `predict.py` reads only this file, so a frozen
    # prediction cannot have seen an outcome, a returned path or a panel count.
    requests = {
        "schema": 1,
        "study": "outside-query-model-v1",
        "source_evidence_sha256": sha(evidence_raw),
        "inventory_sha256": sha(inventory_bytes),
        "note": (
            "Only pre-query fields: opening locator and SHA-256, mode, protocol "
            "stratum and the literal request. No label, result, path or panel "
            "field appears here."
        ),
        "openings": [
            {
                "key": f"{opening['slug']}/{opening['attempt_id']}",
                "slug": opening["slug"],
                "attempt_id": opening["attempt_id"],
                "artifact_sha256": opening["artifact_sha256"],
                "networks": opening["networks"],
            }
            for opening in inventory["openings"]
        ],
        "requests": [
            {
                "query_id": query["query_id"],
                "slug": query["slug"],
                "attempt_id": query["attempt_id"],
                "mode": query["mode"],
                "stratum": query["stratum"],
                "request": query["request"],
            }
            for query in queries
            if query["request"]
            and query["stratum"] in {"primary_distinct_edge", "same_edge"}
        ],
    }
    requests_bytes = json_bytes(requests)

    manifest = {
        "schema": 1,
        "study": "outside-query-model-v1",
        "source": inventory["source"],
        "hashes": {
            "inventory.json": sha(inventory_bytes),
            "requests.json": sha(requests_bytes),
        },
        "openings": inventory["openings"],
        "counts": counts,
        "anomalies": anomalies,
        "eligibility_rules": inventory["eligibility_rules"],
        "excluded": [
            {
                "query_id": query["query_id"],
                "mode": query["mode"],
                "stratum": query["stratum"],
                "exclusion": query["exclusion"],
                "label": query["label"],
            }
            for query in queries
            if not query["eligible"]
        ],
        "midpoint_repeats": {
            "pairs": counts["midpoint_pairs"],
            "agree": counts["midpoint_agree"],
            "note": (
                "Each offset-128 midpoint request is the correlated repeat of one "
                "boundary request on the same segments, lanes and direction. They "
                "are not independent votes and are not scored."
            ),
        },
    }
    return inventory, requests, manifest


def main():
    inventory, requests, manifest = build()
    for name, document in (("inventory", inventory), ("requests", requests), ("manifest", manifest)):
        (HERE / f"{name}.json").write_bytes(json_bytes(document))
    print(json.dumps(inventory["counts"], indent=1, sort_keys=True))
    if inventory["anomalies"]:
        print(json.dumps(inventory["anomalies"][:10], indent=1))
    return inventory


if __name__ == "__main__":
    main()
